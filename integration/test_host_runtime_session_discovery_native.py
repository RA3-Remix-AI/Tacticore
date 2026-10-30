"""Offline policy, Win32-boundary and match-identity simulation only."""
import copy
import ctypes as c
from ctypes import wintypes as w
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from host_runtime.contracts import ContractError, SessionBinding, canonical_json
from host_runtime.session_discovery import DiscoveryPolicy, ProcessIdentity, TrustedFiles
from host_runtime import session_discovery_native as native


def uid():return str(uuid.uuid4())
def write(path,value):path.write_text(json.dumps(value),encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.state=self.root/'state';self.state.mkdir()
        self.sessions=self.root/'sessions';self.sessions.mkdir()
        self.run=self.sessions/'source';self.run.mkdir()
        self.deploy=self.root/'deploy';self.deploy.mkdir()
        self.game=self.root/'RA3_1.12.game';self.game.write_bytes(b'offline game')
        self.big=self.deploy/'TFMacroProbe.big';self.big.write_bytes(b'offline package')
        self.config=self.deploy/'macro.skudef';self.config.write_text('mod-game 1.12\nadd-big TFMacroProbe.big\n')
        self.registry=self.run/'registry.json';self.personality='macro_personality'
        write(self.registry,dict(package_sha256=sha(self.big),compiled_ids_verified=True,commanders=[dict(
            id=native.COMMANDER,assets=[dict(asset_id=self.personality,instance_id='0x799613e0',side='Soviet')])]))
        self.package=self.root/'package-report.json'
        write(self.package,dict(compiled=True,big_sha256=sha(self.big),commander_id=native.COMMANDER,
            personality=self.personality,assets=[dict(name='AIPersonalityDefinition:'+self.personality,instance_id='0x799613e0')]))
        self.build=self.root/'build';self.build.mkdir();self.manifest=self.build/'build-manifest.json'
        write(self.manifest,dict(epoch=37,package_sha256=sha(self.big)))
        self.bundle=self.run/'macro-budget-bundle.json'
        write(self.bundle,dict(schema_version=9,kind='verified_macro_group_roles_bootstrap',build=str(self.build),
                               pins={str(self.manifest):sha(self.manifest)}))
        self.ticks=134376534415833801
        self.session=self.run/'desktop-session.json'
        self.record=dict(session_id=uid(),pid=101,start_time=native.creation_start(self.ticks),
            process_creation_filetime=self.ticks,run_directory=str(self.run),game=str(self.game),
            mod_config=str(self.config),mod_big=str(self.big),mod_sha256=sha(self.big),registry=str(self.registry),
            macro_package_report=str(self.package),scenario=dict(commander_id=native.COMMANDER,
                computer_player_index=3,opponent_player_index=4,observer_player_index=2,participant_count=2,
                map_id='map_mp_2_black1b'))
        write(self.session,self.record)
        self.sha_patch=patch.object(native,'GAME_SHA',sha(self.game));self.sha_patch.start()
        self.loader_patch=patch.object(native,'load_bundle',return_value=({},SimpleNamespace(
            required_origin_region='region_8_3',package_sha256=sha(self.big))))
        self.loader=self.loader_patch.start()
        self.backend=SimpleNamespace(state_dir=self.state,store=SimpleNamespace(state_dir=self.state))

    def tearDown(self):
        self.loader_patch.stop();self.sha_patch.stop();self.temp.cleanup()

    def assertCode(self,code,call):
        with self.assertRaises(ContractError) as caught:call()
        self.assertEqual(code,caught.exception.code)

    def register(self,**options):
        return native.register_policy(self.session,self.bundle,self.state,self.sessions,**options)

    def policy(self):
        self.register()
        return native.load_policy(self.state)[1]


class PolicyTests(Fixture):
    def test_schema10_explicit_large_bundle_metadata_is_accepted_without_live_access(self):
        value=json.loads(self.bundle.read_text());value.update(schema_version=10,kind='verified_macro_expansion_bootstrap')
        value['pins'].update({str(self.root/('proof'+str(i))):'a'*64 for i in range(700)})
        write(self.bundle,value);self.assertGreater(self.bundle.stat().st_size,65536)
        with patch.object(native,'Win32ReadOnly',side_effect=AssertionError('no process access')):
            self.assertTrue(self.register()['registered'])
            self.assertEqual(native.load_policy(self.state)[1].native_epoch,37)

    def test_legacy_bundle_limits_not_broadened_by_schema10(self):
        value=json.loads(self.bundle.read_text());value['pins'].update({str(self.root/('proof'+str(i))):'a'*64 for i in range(700)})
        write(self.bundle,value)
        self.assertCode('discovery_policy_invalid',self.register)

    def test_only_explicit_schema10_and_schema11_have_large_metadata_bound(self):
        original=json.loads(self.bundle.read_text())
        for version in (10,11):
            value=dict(original,schema_version=version,kind='verified_macro_fixed_consumer_bootstrap' if version==11 else 'verified_macro_expansion_bootstrap')
            value['pins']=dict(original['pins'],**{str(self.root/('proof'+str(i))):'a'*64 for i in range(700)})
            write(self.bundle,value)
            with patch.object(native,'Win32ReadOnly',side_effect=AssertionError('no process access')):
                self.assertEqual(native.read_macro_bundle(self.bundle)[0]['schema_version'],version)
        for version in (9,12,99,True,'11'):
            value['schema_version']=version;write(self.bundle,value)
            self.assertCode('discovery_policy_invalid',lambda:native.read_macro_bundle(self.bundle))
        value.update(schema_version=11,kind='verified_macro_expansion_bootstrap');write(self.bundle,value)
        self.assertCode('discovery_policy_invalid',lambda:native.read_macro_bundle(self.bundle))

    def test_explicit_policy_registration_pins_sources_without_any_native_access(self):
        with patch.object(native,'Win32ReadOnly',side_effect=AssertionError('no process access')):
            result=self.register()
        self.assertTrue(result['registered']);self.assertFalse(result['game_access'])
        self.assertFalse(result['credentials_accessed']);self.assertEqual(result['model_calls'],0)
        record,policy=native.load_policy(self.state)
        self.assertEqual(record['source_session_sha256'],sha(self.session))
        self.assertEqual(policy.files.game,self.game);self.assertEqual(policy.native_epoch,37)
        self.assertEqual(policy.origin_region,'region_8_3')
        self.assertEqual(self.loader.call_count,1)
        self.assertFalse(list(self.state.glob('*.dpapi')))

    def test_same_explicit_registration_is_byte_identical_and_idempotent(self):
        first=self.register();raw=(self.state/native.NAME).read_bytes()
        self.assertEqual(self.register(),first)
        self.assertEqual((self.state/native.NAME).read_bytes(),raw)

    def test_missing_policy_does_not_construct_adapter_or_scan(self):
        with patch.object(native,'NativeAdapter',side_effect=AssertionError('must not scan')):
            self.assertIsNone(native.create_discovery(self.backend))

    def test_invalid_policy_returns_only_discovery_refusal(self):
        (self.state/native.NAME).write_text('{bad json')
        with patch.object(native,'NativeAdapter',side_effect=AssertionError('must not scan')):
            refused=native.create_discovery(self.backend)
        self.assertCode('discovery_policy_invalid',lambda:refused.discover({},uid()))
        self.assertCode('discovery_policy_invalid',lambda:refused.prepare({},uid()))
        refused.close()

    def test_policy_cannot_broaden_scope_or_introduce_extra_fields(self):
        self.register();path=self.state/native.NAME;original=json.loads(path.read_text())
        for mutate in (lambda r:r.update(arbitrary_path='PRIVATE'),lambda r:r['scope'].update(player_id=4),
                       lambda r:r['scope'].update(faction='Allied'),lambda r:r['scope'].update(origin_region='region_0_0')):
            value=copy.deepcopy(original);mutate(value);write(path,value)
            refused=native.create_discovery(self.backend)
            self.assertCode('discovery_policy_invalid',lambda:refused.discover({},uid()))
        self.assertEqual(self.loader.call_count,1)

    def test_changed_fixed_sources_are_refused_without_starting_native_reader(self):
        self.register();self.registry.write_bytes(self.registry.read_bytes()+b' ')
        with patch.object(native,'NativeAdapter',side_effect=AssertionError('no native construction')):
            refused=native.create_discovery(self.backend)
        self.assertCode('discovery_source_changed',lambda:refused.discover({},uid()))

    def test_unqualified_bundle_does_not_create_policy_or_root(self):
        self.loader.side_effect=ContractError('macro_bundle_not_qualified')
        self.assertCode('macro_bundle_not_qualified',self.register)
        self.assertFalse((self.state/native.NAME).exists())
        self.assertFalse((self.state/'session-root-registration.json').exists())

    def test_registry_side_and_compiled_asset_identity_must_match_real_package(self):
        original=json.loads(self.registry.read_text())
        for mutate in (lambda r:r['commanders'][0]['assets'][0].update(side='Allied'),
                       lambda r:r['commanders'][0]['assets'][0].update(instance_id='0x1234'),
                       lambda r:r.update(compiled_ids_verified=False)):
            value=copy.deepcopy(original);mutate(value);write(self.registry,value)
            self.assertCode('discovery_policy_invalid',self.register)
        self.assertFalse((self.state/native.NAME).exists())

    def test_extra_mod_directive_or_other_package_cannot_be_registered(self):
        for text in ('mod-game 1.12\nadd-big other.big\n','mod-game 1.12\nadd-big TFMacroProbe.big\nadd-big other.big\n'):
            self.config.write_text(text)
            self.assertCode('discovery_policy_invalid',self.register)

    def test_replacement_requires_explicit_stopped_gate_and_preserves_old_policy_on_failure(self):
        self.register();before=(self.state/native.NAME).read_bytes()
        self.record['session_id']=uid();write(self.session,self.record)
        self.assertCode('session_registration_conflict',self.register)
        history=SimpleNamespace(close=lambda:None)
        with patch('host_runtime.desktop_backend.DesktopBackend',return_value=history),patch.object(native,'run_records',
            return_value=[SimpleNamespace(state='running',native_release_verified=False,unresolved_count=1)]):
            self.assertCode('run_state_conflict',lambda:self.register(replace_stopped=True))
        self.assertEqual((self.state/native.NAME).read_bytes(),before)

    def test_explicit_replacement_after_verified_release_creates_new_policy(self):
        first=self.register();self.record['session_id']=uid();write(self.session,self.record)
        with patch('host_runtime.desktop_backend.DesktopBackend',return_value=SimpleNamespace(close=lambda:None)),\
             patch.object(native,'run_records',return_value=[]):
            second=self.register(replace_stopped=True)
        self.assertNotEqual(first['policy_id'],second['policy_id'])

    def test_factory_is_lazy_and_supplies_only_fixed_callbacks(self):
        self.register()
        adapter=SimpleNamespace(enumerate_processes=lambda:[],probe_match=lambda *args:None)
        with patch.object(native,'NativeAdapter',return_value=adapter):
            broker=native.create_discovery(self.backend)
        try:
            self.assertEqual(broker.discover({})['candidates'],[])
            self.assertEqual(broker.policy.files.macro_bundle,self.bundle)
        finally:broker.close()

    def test_bad_policy_cannot_block_profiles_or_resume_in_actual_rpc_process(self):
        from test_host_runtime_profile_store import library
        config=self.root/'library.v2.json';write(config,library())
        (self.state/native.NAME).write_text('not JSON')
        requests=[dict(schema_version=1,request_id=uid(),operation=op,args={})
                  for op in ('profiles.list','session.discover','run.resume')]
        result=subprocess.run([sys.executable,'-X','utf8','-B','-m','host_runtime.bridge_service',
            '--library',str(config),'--state-dir',str(self.state)],
            input=''.join(canonical_json(value)+'\n' for value in requests).encode(),capture_output=True,
            cwd=Path(__file__).parent,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        values=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertTrue(values[0]['ok']);self.assertEqual(values[1]['error']['code'],'discovery_policy_invalid')
        self.assertTrue(values[2]['ok']);self.assertIsNone(values[2]['result']['run'])


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.game=Path('C:/trusted/RA3_1.12.game');self.config=Path('C:/trusted/macro.skudef')
    def assertCode(self,code,call):
        with self.assertRaises(ContractError) as caught:call()
        self.assertEqual(code,caught.exception.code)
    def test_unique_modconfig_switch_is_exact_and_case_insensitive(self):
        argv=[str(self.game),'-win','-modConfig',str(self.config)]
        self.assertEqual(native.parse_mod_config(argv,self.game,self.config),self.config)
        argv[2]='-MODCONFIG';self.assertEqual(native.parse_mod_config(argv,self.game,self.config),self.config)
    def test_duplicate_inline_relative_and_mismatched_configs_are_refused(self):
        for argv in ([str(self.game)], [str(self.game),'-modConfig'],[str(self.game),'-modConfig','relative.skudef'],
            [str(self.game),'-modConfig','C:/other.skudef'],[str(self.game),'-modConfig='+str(self.config)],
            [str(self.game),'-modConfig',str(self.config),'-modconfig',str(self.config)]):
            self.assertCode('session_scope_unsupported',lambda:native.parse_mod_config(argv,self.game,self.config))
    def test_argv_identity_and_embedded_nul_cannot_hide_other_arguments(self):
        for argv in (['C:/other.game','-modConfig',str(self.config)],
                     [str(self.game),'-modConfig',str(self.config)+'\x00-other']):
            self.assertCode('session_probe_invalid',lambda:native.parse_mod_config(argv,self.game,self.config))
    def test_creation_filetime_keeps_submicrosecond_digit(self):
        ticks=134376534415833801
        text=native.creation_start(ticks)
        self.assertIn('.5833801+',text)
        native.require_creation(text,ticks)
        self.assertCode('run_history_unverifiable',lambda:native.require_creation(text,ticks+10))

    def command_reader(self,text,*,bad_pointer=False,status=0,needed_override=None):
        api=native.Win32ReadOnly.__new__(native.Win32ReadOnly)
        payload=text.encode('utf-16-le');size=c.sizeof(native.UNICODE_STRING)+len(payload)
        def query(handle,kind,buffer,capacity,required):
            self.assertEqual(kind,60)
            c.cast(required,c.POINTER(w.ULONG))[0]=size if needed_override is None else needed_override
            if buffer is not None:
                value=native.UNICODE_STRING.from_buffer(buffer)
                value.Length=len(payload);value.MaximumLength=len(payload)
                value.Buffer=c.addressof(buffer)+size+100 if bad_pointer else c.addressof(buffer)+c.sizeof(native.UNICODE_STRING)
                if not bad_pointer:c.memmove(value.Buffer,payload,len(payload))
            return status
        api.nt=SimpleNamespace(NtQueryInformationProcess=query)
        return api
    def test_nt_command_line_reader_decodes_only_bounded_inline_unicode(self):
        text='"C:/trusted/RA3_1.12.game" -modConfig "C:/trusted/macro.skudef"'
        self.assertEqual(self.command_reader(text).command_line(123),text)
    def test_nt_buffer_length_pointer_status_and_nul_are_fail_closed(self):
        for options,code in (({'bad_pointer':True},'session_probe_invalid'),({'status':-1},'session_probe_unavailable'),
                             ({'needed_override':65537},'session_probe_unavailable')):
            self.assertCode(code,lambda:self.command_reader('test',**options).command_line(123))
        self.assertCode('session_probe_invalid',lambda:self.command_reader('game\x00hidden').command_line(123))
    def test_toolhelp_filters_exact_basename_and_always_closes_snapshot(self):
        api=native.Win32ReadOnly.__new__(native.Win32ReadOnly);closed=[];records=iter([('other.exe',8),('RA3_1.12.game',101)])
        def advance(handle,pointer):
            try:name,pid=next(records)
            except StopIteration:return False
            row=c.cast(pointer,c.POINTER(native.PROCESSENTRY32W)).contents
            row.szExeFile=name;row.th32ProcessID=pid;return True
        api.k=SimpleNamespace(CreateToolhelp32Snapshot=lambda flags,pid:123,Process32FirstW=advance,
                              Process32NextW=advance,CloseHandle=lambda handle:closed.append(handle))
        self.assertEqual(api.process_ids('ra3_1.12.game'),[101]);self.assertEqual(closed,[123])

    def test_raw_creation_filetime_is_read_without_float_conversion(self):
        api=native.Win32ReadOnly.__new__(native.Win32ReadOnly);ticks=134376534415833801
        def times(handle,creation,exit,kernel,user):
            value=c.cast(creation,c.POINTER(w.FILETIME)).contents
            value.dwHighDateTime=ticks>>32;value.dwLowDateTime=ticks&0xffffffff;return True
        api.k=SimpleNamespace(GetProcessTimes=times)
        self.assertEqual(api.creation_filetime(123),ticks)

    def test_mismatched_image_is_rejected_before_command_line_read_and_handle_is_closed(self):
        api=native.Win32ReadOnly.__new__(native.Win32ReadOnly);access=[];closed=[]
        def image(handle,flags,buffer,size):buffer.value='C:/other/RA3_1.12.game';return True
        api.k=SimpleNamespace(OpenProcess=lambda flags,inherit,pid:access.append(flags) or 123,
                              QueryFullProcessImageNameW=image,CloseHandle=lambda handle:closed.append(handle))
        api.command_line=lambda handle:self.fail('must not read another image command line')
        self.assertIsNone(api.inspect_process(101,self.game))
        self.assertEqual(access,[0x1000]);self.assertEqual(closed,[123])


class FakeMemory:
    def __init__(self,game):
        self.path=str(game);self.handle=555;self.closed=0;self.logic=0x1000000;self.owner=0x2000000;self.players=0x3000000
        self.map_pointer=0x4000000
        self.words={0xcd8ce4:self.logic,self.logic:0xbeb630,0xce8c9c:self.players,
                    self.players+0x30+12:self.owner,self.logic+0x98:self.map_pointer}
        self.bytes=dict(native.PINS)
        self.bytes[self.map_pointer]=b'map_mp_2_black1b\\map_mp_2_black1b.map\x00'.ljust(260,b'\x00')
    def u32(self,address):return self.words[address]
    def read(self,address,length):return self.bytes[address][:length]
    def close(self):self.closed+=1


class ProbeTests(Fixture):
    def setUp(self):
        super().setUp();self.p=self.policy();self.memory=FakeMemory(self.game)
        self.process=ProcessIdentity(101,self.ticks,native.creation_start(self.ticks),self.game,self.config)
        self.identity=dict(player_index=3,store_membership_verified=True,side_matches_player=True,instance_id='0x799613e0',
                           personality_wrapper='0x5000000',personality_data='0x6000000',player_template='0x7000000',ai_player='0x8000000')
        self.resolved=dict(commander_id=native.COMMANDER,personality_binding_verified=True,side='Soviet')
        self.participants=dict(two_ai_combatants_verified=True,mutual_enemy_relationship_verified=True,
                               observer_separate_from_combatants=True,opponent_native_ai_verified=True)
        self.census=dict(frame=100,enemy_details_read=False,own_objects=[dict(type_hash='0xc16ff13f',hp=1000,xyz=[4404.1,2016.0,0])])
        self.frames=[100,101];self.snap_calls=0;self.inspect_calls=0;self.seed=None
        def memory(pid,seed):self.seed=seed;self.assertEqual(pid,101);return self.memory
        def snapshot(read):
            frame=self.frames[min(self.snap_calls,len(self.frames)-1)];self.snap_calls+=1
            return dict(game_logic=hex(self.memory.logic),simulation_frame=frame,pause_flag_candidate=0,result_records=[])
        def inspect(read,owner):self.inspect_calls+=1;self.assertEqual(owner,self.memory.owner);return copy.deepcopy(self.identity)
        self.readers=SimpleNamespace(Memory=memory,snapshot=snapshot,inspect_player=inspect,
            resolve_registry=lambda *args:copy.deepcopy(self.resolved),verify_two_ai=lambda *args:copy.deepcopy(self.participants),
            own_census=lambda *args:copy.deepcopy(self.census))
        self.api=SimpleNamespace(creation_filetime=lambda handle:self.ticks)
        self.adapter=native.NativeAdapter(self.p,win32=self.api,readers=self.readers)
    def probe(self):return self.adapter.probe_match(self.process,self.p)
    def test_probe_binds_native_side_origin_and_stable_identity_without_exposing_pointers(self):
        first=self.probe();self.frames=[105,106];self.snap_calls=0;self.census['frame']=105
        second=self.probe()
        self.assertEqual(first.game_instance_id,second.game_instance_id)
        self.assertEqual(first.faction,'Soviet');self.assertEqual(first.origin_region,'region_8_3')
        self.assertEqual(len(first.game_instance_id),64)
        self.assertNotIn('0x',first.game_instance_id)
        self.assertEqual(self.memory.closed,2)
        self.assertEqual(self.seed['process_creation_filetime'],self.ticks)
    def test_actual_creation_time_mismatch_rejects_before_match_read(self):
        self.api.creation_filetime=lambda handle:self.ticks+1
        self.assertCode('session_changed',self.probe);self.assertEqual(self.snap_calls,0)
        self.assertEqual(self.memory.closed,1)
    def test_changed_memory_signature_is_rejected(self):
        self.memory.bytes[next(iter(native.PINS))]=b'\x90'*6
        self.assertCode('session_probe_invalid',self.probe);self.assertEqual(self.memory.closed,1)
    def test_registry_side_is_observed_not_copied_from_policy(self):
        self.resolved['side']='Allied'
        self.assertCode('session_scope_unsupported',self.probe)
    def test_unverified_personality_or_wrong_commander_are_refused(self):
        for changes in ({'personality_binding_verified':False},{'commander_id':uid()}):
            self.resolved.update(changes)
            self.assertCode('session_scope_unsupported',self.probe)
    def test_observer_or_enemy_relationship_must_be_independently_verified(self):
        self.participants['mutual_enemy_relationship_verified']=False
        self.assertCode('session_scope_unsupported',self.probe)
    def test_wrong_map_and_other_origin_are_unsupported(self):
        self.memory.bytes[self.memory.map_pointer]=b'other\\other.map\x00'.ljust(260,b'\x00')
        self.assertCode('session_scope_unsupported',self.probe)
        self.memory.bytes[self.memory.map_pointer]=b'map_mp_2_black1b\\map_mp_2_black1b.map\x00'.ljust(260,b'\x00')
        self.snap_calls=0;self.census['own_objects'][0]['xyz']=[400,500,0]
        self.assertCode('session_scope_unsupported',self.probe)
    def test_missing_or_ambiguous_yard_is_not_a_guessed_birth_position(self):
        self.census['own_objects']*=2
        self.assertCode('session_scope_unsupported',self.probe)
    def test_census_must_be_owned_and_within_the_same_observation_window(self):
        self.census['enemy_details_read']=True
        self.assertCode('session_probe_invalid',self.probe)
        self.census['enemy_details_read']=False;self.census['frame']=99;self.snap_calls=0
        self.assertCode('session_changed',self.probe)
    def test_lifecycle_change_and_frame_regression_are_refused(self):
        self.frames=[100,99]
        self.assertCode('session_changed',self.probe)
    def test_ended_or_paused_match_remains_explicit_for_broker_refusal(self):
        snapshot=self.readers.snapshot
        def paused(read):
            value=snapshot(read);value['pause_flag_candidate']=1;value['result_records']=[dict(defeat_frame=90)];return value
        self.readers.snapshot=paused
        result=self.probe();self.assertTrue(result.paused);self.assertTrue(result.ended)
    def test_enumeration_queries_only_fixed_image_then_strict_modconfig(self):
        self.api.process_ids=lambda name:[101]
        self.api.inspect_process=lambda pid,game:(self.game,self.ticks,[str(self.game),'-modConfig',str(self.config)])
        self.assertEqual(self.adapter.enumerate_processes(),[self.process])
        self.api.inspect_process=lambda pid,game:(self.game,self.ticks,[str(self.game),'-modConfig','C:/wrong.skudef'])
        self.assertCode('session_scope_unsupported',self.adapter.enumerate_processes)


class HistoryTests(Fixture):
    def setUp(self):
        super().setUp();self.output=self.run/'battle-host';self.output.mkdir();self.source=self.output/'source';self.source.mkdir()
        self.host_source=self.root/'macro_host.py';self.host_source.write_text('offline frozen host')
        self.freeze()
        self.run_id=uid();self.binding=SessionBinding(1,self.record['session_id'],3,native.COMMANDER,101,
            self.record['start_time'],uid(),sha(self.game),sha(self.big))
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE launches (run_id TEXT,binding_json TEXT,session_path TEXT,output_path TEXT)')
        self.db.execute('INSERT INTO launches VALUES (?,?,?,?)',(self.run_id,canonical_json(self.binding.public()),str(self.session),str(self.output)))
        self.status=dict(run_id=self.run_id,session_id=self.binding.session_id,state='stopped',native_release_verified=True)
        self.backend=SimpleNamespace(_db=self.db,_status=lambda row:copy.deepcopy(self.status),journal=SimpleNamespace(unresolved=lambda run_id:[]))
    def freeze(self):
        rows=[]
        for index,path in enumerate((self.host_source,self.session,self.bundle)):
            target=self.source/(str(index)+'-'+path.name);target.write_bytes(path.read_bytes())
            rows.append(dict(path=str(path),copy=target.name,sha256=sha(target)))
        write(self.output/'sources.json',dict(kind='pre_execution_macro_host_sources',sources=rows))
    def tearDown(self):self.db.close();super().tearDown()
    def test_prior_epoch_is_pinned_frozen_manifest_not_current_policy_guess(self):
        rows=native.run_records(self.backend)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0].native_epoch,37)
        self.assertTrue(rows[0].native_release_verified);self.assertTrue(rows[0].native_delivery_attempted)
        self.assertEqual(rows[0].creation_filetime,self.ticks)
    def test_frozen_schema10_larger_metadata_retains_exact_epoch_binding(self):
        value=json.loads(self.bundle.read_text());value.update(schema_version=10,kind='verified_macro_expansion_bootstrap')
        value['pins'].update({str(self.root/('proof'+str(i))):'a'*64 for i in range(700)})
        write(self.bundle,value);self.freeze()
        self.assertEqual(native.run_records(self.backend)[0].native_epoch,37)
    def test_frozen_schema11_larger_metadata_retains_original_binding_and_unknown_lock(self):
        value=json.loads(self.bundle.read_text());value.update(schema_version=11,kind='verified_macro_fixed_consumer_bootstrap',
            fixed_consumer_contracts=[dict(schema_version=1,kind='fixed_consumer_primed_v1',action='producesickle',directory=str(self.run))])
        value['pins'].update({str(self.root/('proof'+str(i))):'a'*64 for i in range(700)})
        write(self.bundle,value);self.freeze()
        self.status['native_release_verified']=False
        self.backend.journal.unresolved=lambda run_id:[dict(status='uncertain')]
        row=native.run_records(self.backend)[0]
        self.assertEqual(row.native_epoch,37);self.assertEqual(row.creation_filetime,self.ticks)
        self.assertFalse(row.native_release_verified);self.assertEqual(row.unresolved_count,1)
    def test_missing_filetime_or_legacy_source_contract_refuses_entire_history(self):
        value=copy.deepcopy(self.record);value.pop('process_creation_filetime');write(self.session,value)
        self.assertCode('run_history_unverifiable',lambda:native.run_records(self.backend))
        write(self.session,self.record);write(self.output/'sources.json',dict(kind='old_micro_sources',sources=[]))
        self.assertCode('run_history_unverifiable',lambda:native.run_records(self.backend))
    def test_changed_manifest_and_mismatched_binding_are_not_silently_skipped(self):
        self.manifest.write_bytes(self.manifest.read_bytes()+b' ')
        self.assertCode('run_history_unverifiable',lambda:native.run_records(self.backend))
    def test_only_independent_no_execution_status_can_mark_delivery_unattempted(self):
        self.status['no_native_execution_started']=True
        self.assertFalse(native.run_records(self.backend)[0].native_delivery_attempted)
        self.status['no_native_execution_started']='true'
        self.assertTrue(native.run_records(self.backend)[0].native_delivery_attempted)
    def test_unresolved_commands_and_unverified_release_remain_explicit(self):
        self.status['native_release_verified']=False
        self.backend.journal.unresolved=lambda run_id:[dict(status='uncertain')]
        row=native.run_records(self.backend)[0]
        self.assertFalse(row.native_release_verified);self.assertEqual(row.unresolved_count,1)


if __name__=='__main__':unittest.main()
