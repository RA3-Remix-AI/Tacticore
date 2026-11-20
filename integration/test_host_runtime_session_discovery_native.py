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
        write(self.manifest,dict(epoch=6,package_sha256=sha(self.big)))
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
                map_id='map_mp_2_black1b',origin_region='region_8_3'))
        write(self.session,self.record)
        self.loader_patch=patch.object(native,'load_bundle',return_value=({},SimpleNamespace(
            required_origin_region='region_8_3',package_sha256=sha(self.big))))
        self.loader=self.loader_patch.start()
        self.backend=SimpleNamespace(state_dir=self.state,store=SimpleNamespace(state_dir=self.state))

    def tearDown(self):
        self.loader_patch.stop();self.temp.cleanup()

    def assertCode(self,code,call):
        with self.assertRaises(ContractError) as caught:call()
        self.assertEqual(code,caught.exception.code)

    def policy(self):
        """The trusted policy beta_setup would install for these offline files."""
        values={}
        for key,path in dict(game=self.game,mod_config=self.config,mod_big=self.big,registry=self.registry,
                             macro_bundle=self.bundle,package_report=self.package).items():
            values[key]=path;values['mod_sha256' if key=='mod_big' else key+'_sha256']=sha(path)
        return DiscoveryPolicy(TrustedFiles(**values),self.sessions,self.state,native.COMMANDER,7)


class PolicyTests(Fixture):





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










    def test_factory_is_lazy_and_supplies_only_fixed_callbacks(self):
        (self.state/native.NAME).write_text('{}')
        adapter=SimpleNamespace(enumerate_processes=lambda:[],probe_match=lambda *args:None)
        policy=self.policy()
        with patch.object(native,'NativeAdapter',return_value=adapter),\
                patch.object(native,'load_policy',return_value=({},policy)):
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
            except StopIteration:c.set_last_error(18);return False
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
        self.participants=dict(participants_verified=True,model_player_id=3,alliances=[],participants=[
            dict(player_id=3,kind='model_ai',relation='self'),dict(player_id=4,kind='native_ai',relation='enemy')])
        self.starts=[dict(name='Player_1_Start',xyz=[857.5,2015.4,0.]),dict(name='Player_2_Start',xyz=[4404.1,2016.0,0.])]
        self.ally_points={}
        self.census=dict(frame=100,enemy_details_read=False,own_objects=[dict(type_hash='0xc16ff13f',hp=1000,xyz=[4404.1,2016.0,0])])
        self.frames=[100,101];self.snap_calls=0;self.inspect_calls=0;self.seed=None
        def memory(pid,seed):self.seed=seed;self.assertEqual(pid,101);return self.memory
        def snapshot(read):
            frame=self.frames[min(self.snap_calls,len(self.frames)-1)];self.snap_calls+=1
            return dict(game_logic=hex(self.memory.logic),simulation_frame=frame,pause_flag_candidate=0,result_records=[])
        def inspect(read,owner):self.inspect_calls+=1;self.assertEqual(owner,self.memory.owner);return copy.deepcopy(self.identity)
        self.readers=SimpleNamespace(Memory=memory,snapshot=snapshot,inspect_player=inspect,
            resolve_registry=lambda *args:copy.deepcopy(self.resolved),
            verify_participants=lambda *args:copy.deepcopy(self.participants),
            controlled_match_result=lambda state,*args,**kwargs:dict(terminal=bool(state.get('result_records'))),
            public_start_waypoints=lambda read:copy.deepcopy(self.starts),
            owned_object_points=lambda memory,logic,owner:list(self.ally_points.get(owner,[])),
            own_census=lambda *args:copy.deepcopy(self.census))
        self.api=SimpleNamespace(creation_filetime=lambda handle:self.ticks)
        self.adapter=native.NativeAdapter(self.p,win32=self.api,readers=self.readers)
    def probe(self):return self.adapter.probe_match(self.process,self.p)
    def test_any_map_is_read_and_its_own_start_derived(self):
        self.memory.bytes[self.memory.map_pointer]=b'Maps\\My Custom Map\\My Custom Map.map\x00'.ljust(260,b'\x00')
        self.census['own_objects'][0]['xyz']=[3981.3955,2188.4282,0]
        value=self.probe()
        self.assertEqual(value.scenario['map_id'],'my custom map')
        self.assertEqual(value.scenario['own_region'],'region_7_4')
        self.assertEqual(value.scenario['own_start_waypoint'],'Player_2_Start')
        self.assertEqual(value.scenario['enemy_regions'],['region_1_3'])
        self.assertEqual(value.scenario['mode'],'ai_vs_native')
        self.assertEqual(value.scenario['model_player_id'],3)
        self.assertEqual(self.memory.closed,1)

    def test_map_outside_its_own_folder_is_unsupported(self):
        for raw in (b'map_mp_2_black1b\\map_mp_2_rao1.map',b'map_mp_2_rao1\\map_mp_2_rao1.txt'):
            with self.subTest(raw=raw):
                self.snap_calls=0
                self.memory.bytes[self.memory.map_pointer]=(raw+b'\x00').ljust(260,b'\x00')
                self.assertCode('session_scope_unsupported',self.probe)

    def test_human_teammate_is_a_combatant_and_its_start_is_not_an_enemy_region(self):
        self.participants['participants'][:0]=[dict(player_id=2,kind='human',relation='ally')]
        self.participants['participants'].append(dict(player_id=5,kind='native_ai',relation='enemy'))
        self.participants['alliances']=[[4,5]]
        self.starts=[dict(name='Player_1_Start',xyz=[700.,700.,0.]),dict(name='Player_2_Start',xyz=[3800.,700.,0.]),
                     dict(name='Player_3_Start',xyz=[700.,3800.,0.]),dict(name='Player_4_Start',xyz=[3800.,3800.,0.])]
        self.census['own_objects'][0]['xyz']=[3700.,800.,0]
        self.memory.words[self.memory.players+0x30+8]=0x9000000
        self.ally_points[0x9000000]=[(650.,720.),(800.,900.),(3000.,3000.)]
        value=self.probe().scenario
        self.assertEqual(value['mode'],'human_with_ai')
        self.assertEqual(value['enemy_regions'],['region_1_7','region_7_7'])
        self.assertTrue(value['enemy_regions_exact'])
        self.assertEqual([(row['player_id'],row['kind'],row['team']) for row in value['players']],
                         [(2,'human',1),(3,'model_ai',1),(4,'native_ai',2),(5,'native_ai',2)])

    def test_probe_binds_native_side_origin_and_stable_identity_without_exposing_pointers(self):
        first=self.probe();self.frames=[105,106];self.snap_calls=0;self.census['frame']=105
        second=self.probe()
        self.assertEqual(first.game_instance_id,second.game_instance_id)
        self.assertEqual(first.scenario['players'][0]['faction'],'Soviet')
        self.assertEqual(first.scenario['own_region'],'region_8_3')
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
    def test_participants_must_be_independently_verified(self):
        self.participants['participants_verified']=False
        self.assertCode('session_scope_unsupported',self.probe)
        self.snap_calls=0;self.participants['participants_verified']=True
        self.participants['participants'][1]['relation']='neutral'
        self.assertCode('session_scope_unsupported',self.probe)
        def refused(*args):raise ValueError('Combatant is not a mutual ally or mutual enemy of the model')
        self.snap_calls=0;self.readers.verify_participants=refused
        self.assertCode('session_probe_unavailable',self.probe)
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

class RunRecordTests(Fixture):
    """Run history comes from the backend's own status; archived runs never block."""
    def setUp(self):
        super().setUp()
        self.run_id=uid();self.binding=SessionBinding(1,self.record['session_id'],3,native.COMMANDER,101,
            self.record['start_time'],uid(),sha(self.game),sha(self.big))
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE launches (run_id TEXT,binding_json TEXT,session_path TEXT,output_path TEXT)')
        self.db.execute('INSERT INTO launches VALUES (?,?,?,?)',(self.run_id,canonical_json(self.binding.public()),
            str(self.session),str(self.run/'battle-host')))
        self.status=dict(run_id=self.run_id,session_id=self.binding.session_id,state='stopped',native_release_verified=True)
        self.unresolved=[]
        self.stop=dict(created_at='2026-10-29T00:00:10')
        journal=SimpleNamespace(unresolved=lambda run_id:list(self.unresolved),
                                get_command=lambda run_id,request:self.stop)
        self.backend=SimpleNamespace(_db=self.db,_status=lambda row:copy.deepcopy(self.status),journal=journal)

    def tearDown(self):self.db.close();super().tearDown()

    def test_current_run_is_one_native_epoch_with_its_process_identity(self):
        row=native.run_records(self.backend)[0]
        self.assertEqual(row.native_epoch,7);self.assertEqual(row.creation_filetime,self.ticks)
        self.assertTrue(row.native_release_verified);self.assertTrue(row.native_delivery_attempted)

    def test_unknown_delivery_before_stop_is_settled_only_by_a_verified_return(self):
        self.unresolved=[dict(request_id=uid(),operation='macro_policy',status='uncertain',
                              created_at='2026-10-29T00:00:05')]
        self.assertEqual(native.run_records(self.backend)[0].unresolved_count,0)
        self.status['native_release_verified']=False
        self.assertEqual(native.run_records(self.backend)[0].unresolved_count,1)
        self.status['native_release_verified']=True
        self.unresolved[0]['created_at']='2026-10-29T00:00:20'
        self.assertEqual(native.run_records(self.backend)[0].unresolved_count,1)

    def test_archived_run_is_finished_history_without_reading_its_files(self):
        self.status.update(history_archived=True,reason_code='run_history_archived')
        self.session.unlink()
        row=native.run_records(self.backend)[0]
        self.assertEqual(row.history_protocol,'archived_before_runtime_change')
        self.assertFalse(row.native_delivery_attempted);self.assertIsNone(row.native_epoch)

    def test_changed_process_identity_refuses_entire_history(self):
        value=copy.deepcopy(self.record);value.pop('process_creation_filetime');write(self.session,value)
        self.assertCode('run_history_unverifiable',lambda:native.run_records(self.backend))
        value=dict(self.record,pid=202);write(self.session,value)
        self.assertCode('run_history_unverifiable',lambda:native.run_records(self.backend))

    def test_only_independent_no_execution_status_can_mark_delivery_unattempted(self):
        self.status['no_native_execution_started']=True
        self.assertFalse(native.run_records(self.backend)[0].native_delivery_attempted)
        self.status['no_native_execution_started']='true'
        self.assertTrue(native.run_records(self.backend)[0].native_delivery_attempted)


if __name__=='__main__':unittest.main()
