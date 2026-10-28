"""Pure mocked-live tests of continuation guards and non-mutating preparation."""
import copy
import ast
from contextlib import contextmanager
import importlib
import inspect
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import uuid

import prepare_macro_continuation_fixture as continuation
from host_runtime.contracts import SessionBinding,canonical_json


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')


@contextmanager
def db_at(path):
    db=sqlite3.connect(path)
    try:
        with db:yield db
    finally:db.close()


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.run=self.root/'acceptance/runs/original';self.run.mkdir(parents=True)
        self.ledger=self.root/'host-runtime.sqlite3';self.output=self.root/'acceptance/runs/continued'
        self.game=self.root/'game.exe';self.game.write_bytes(b'FAKE GAME; NEVER EXECUTED')
        self.big=self.root/'mod.big';self.big.write_bytes(b'FAKE MOD')
        self.xml=b'<MacroProbe /><!-- MOCK -->'
        self.package=dict(compiled=True,big_sha256=sha(self.big),macro_xml_sha256=hashlib.sha256(self.xml).hexdigest())
        self.package_path=self.root/'native/package-build-report.json';write(self.package_path,self.package)
        (self.run/'package-build-report.json').write_bytes(self.package_path.read_bytes());(self.run/'MacroProbe.xml').write_bytes(self.xml)
        self.names=['mock-flag-'+str(i) for i in range(13)]
        self.native=dict(player='0x12345000',player_index=3,player_template='0x12345010',ai_player='0x12346000',
            personality_wrapper='0x12347000',personality_data='0x12348000',instance_id='0x799613e0',
            store_membership_verified=True,side_matches_player=True)
        self.session=dict(session_id=str(uuid.uuid4()),pid=1234,start_time='2026-10-28T10:00:00+00:00',
            process_creation_filetime=123456789,game=str(self.game),mod_sha256=sha(self.big),mod_big=str(self.big),
            arguments='mock-not-executed',mod_config=str(self.root/'mod.skudef'),
            macro_package_report=str(self.package_path),baseline_mod_sha256='b'*64,seed_controlled=False,
            run_directory=str(self.run),real_model_calls=0)
        write(self.run/'session.json',self.session)
        with db_at(self.ledger) as db:
            db.executescript('PRAGMA user_version=1; CREATE TABLE runs(run_id TEXT PRIMARY KEY,binding TEXT); '
                'CREATE TABLE commands(command_id TEXT PRIMARY KEY,run_id TEXT,request_id TEXT,operation TEXT,'
                'fingerprint TEXT,payload TEXT,status TEXT,receipt TEXT,created_at TEXT,updated_at TEXT);')
        self.run_id,self.release,self.final=self.install_host(self.run,self.session)
        self.calls=0

    def install_host(self,run,session,requests=2):
        ident=str(uuid.uuid4());host=run/'battle-host';host.mkdir()
        transport=self.root/'reports'/('macro-desktop-'+ident);(transport/'source').mkdir(parents=True)
        build=self.root/'native/build';build.mkdir(parents=True,exist_ok=True)
        sources={}
        for name in ('shared.h','native.cpp','host.cpp','build.py'):
            p=build/name;p.write_bytes(('mock-'+name).encode());sources[name]=sha(p)
        for name in ('Mock.dll','macro_policy_host.exe'):(build/name).write_bytes(('never execute '+name).encode())
        manifest=dict(kind='native_macro_policy_transport_candidate',epoch=37,mapping_prefix='Local\\RA3MacroPolicyV37_',package_sha256=session['mod_sha256'],sources=sources,
            artifacts={name:sha(build/name) for name in ('Mock.dll','macro_policy_host.exe')},flags=self.names,
            package_report_sha256=sha(self.package_path),package_report=str(self.package_path))
        write(build/'build-manifest.json',manifest)
        entries=[]
        for i,path in enumerate([*[build/name for name in sources],build/'build-manifest.json',run/'session.json']):
            name=str(i)+'-'+path.name;target=transport/'source'/name;target.write_bytes(path.read_bytes())
            entries.append(dict(path=str(path),copy=name,sha256=sha(target)))
        pre=dict(sources=entries,session_sha256=sha(run/'session.json'),process_creation_filetime=session['process_creation_filetime'],native=self.native)
        write(transport/'preflight.json',pre)
        flags=dict(flags=[dict(name=name,present=False,value=None) for name in self.names])
        final=dict(session_id=session['session_id'],pid=session['pid'],mod_sha256=session['mod_sha256'],
            process_creation_filetime=session['process_creation_filetime'],cleanup_verified=True,unknown_command_ids=[],
            host_returncode=0,native=dict(**continuation.NATIVE_STOP,personality_id=0x799613e0,last_frame=2000),independent_flags=flags)
        write(transport/'final-state.json',final);(transport/'policy-probe.jsonl').write_text(json.dumps(dict(kind='attach_prepared',mapping_name=manifest['mapping_prefix']+str(session['pid'])))+'\n',encoding='utf8')
        binding=SessionBinding(1,session['session_id'],3,continuation.COMMANDER,session['pid'],session['start_time'],
            str(uuid.uuid4()),sha(self.game),session['mod_sha256'])
        release=dict(kind='macro_policy_native_release',binding=binding.public(),run_id=ident,host_pid=777,
            host_start_time='2026-10-28T10:01:00+00:00',native_release_verified=True,final_state_sha256=sha(transport/'final-state.json'))
        write(host/'macro-release.json',release)
        status=dict(state='stopped',reason_code='user_stop',session_id=session['session_id'],pid=session['pid'],
            process_start=session['start_time'],runtime_macro=dict(run_id=ident,binding_hash=binding.binding_hash),
            host_pid=release['host_pid'],host_start_time=release['host_start_time'])
        write(host/'host-status.json',status)
        write(host/'visibility-proof.json',dict(session_id=session['session_id'],package_sha256=session['mod_sha256'],
            commander_id=continuation.COMMANDER,target_player_id=3,footprint_live_verified=True,
            terrain_view_live_verified=True,object_view_live_verified=True,no_observer_fallback=True,
            handshake=dict(game_logic=0x12340000,player=int(self.native['player'],0),ai_player=int(self.native['ai_player'],0))))
        receipt=dict(real_network_verified=True,injected_transport=False,expected_origin=True,https=True,loopback=False,
            http_status=200,response_complete=True)
        events=[]
        for i in range(requests):
            events.extend([dict(kind='commander_model_call_started'),dict(kind='commander_model_response_returned',transport_receipt=receipt),
                dict(kind='plan_applied')])
        events.extend([dict(kind='macro_host_stop_started'),dict(kind='host_stopped')])
        for event in events:event['session_id']=session['session_id']
        (host/'host-events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in events),encoding='utf8')
        stop_receipt=dict(binding_hash=binding.binding_hash,host_pid=release['host_pid'],host_start_time=release['host_start_time'],
            native_release_verified=True,final_state_sha256=release['final_state_sha256'],release_sha256=sha(host/'macro-release.json'))
        with db_at(self.ledger) as db:
            db.execute('INSERT INTO runs VALUES (?,?)',(ident,canonical_json(binding.public())))
            for request,operation,state,receipt in [('start','host_start','completed',release),('macro-stop','macro_policy_stop','released',stop_receipt)]:
                db.execute('INSERT INTO commands VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()),ident,request,operation,'fingerprint','{}',state,json.dumps(receipt),'mock','mock'))
        return ident,release,final

    def probe(self,session,names,host_pid,host_start,expected_native):
        self.calls+=1
        raise AssertionError('blocked compatibility tool must never call a live probe')

    def prepare(self,**kwargs):
        return continuation.prepare(self.run/'session.json',self.output,self.ledger,root=self.root,probe=kwargs.pop('probe',self.probe),**kwargs)

    def mutate(self,path,**values):
        path=self.run/path;value=json.loads(path.read_text(encoding='utf8'));value.update(values);write(path,value)


class ContinuationCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='macro-continuation-blocked-mock-')
        self.addCleanup(self.temp.cleanup);self.f=Fixture(self.temp.name)

    def test_dry_run_and_creation_attempt_both_refuse_without_any_write(self):
        before={p:sha(p) for p in self.f.root.rglob('*') if p.is_file()}
        for dry in (True,False):
            value=self.f.prepare(dry_run=dry)
            self.assertFalse(value['ready']);self.assertFalse(value['created'])
            self.assertEqual(value['reason_code'],'macro_runtime_same_epoch_reattach_unsupported')
            self.assertTrue(value['previous_attach_recorded'])
            self.assertEqual(value['runtime_epoch'],37)
            self.assertFalse(self.f.output.exists());self.assertEqual(self.f.calls,0)
            self.assertEqual({p:sha(p) for p in before},before)

    def test_ledger_probe_and_directory_creation_are_never_called(self):
        import ctypes
        forbidden=Mock(side_effect=AssertionError('must not inspect live state'))
        with patch.object(sqlite3,'connect',side_effect=AssertionError('must not read ledger')), \
                patch.object(ctypes,'WinDLL',side_effect=AssertionError('must not load live APIs'),create=True), \
                patch.object(Path,'mkdir',side_effect=AssertionError('must not create run')):
            value=self.f.prepare(probe=forbidden)
        forbidden.assert_not_called()
        self.assertFalse(value['ledger_read']);self.assertFalse(value['live_process_read'])
        self.assertEqual(value['kernel_object_calls'],0)

    def test_release_proves_ownership_return_not_semaphore_object_absence(self):
        value=self.f.prepare(dry_run=True)
        self.assertTrue(value['recorded_native_cleanup_verified'])
        self.assertEqual(value['recorded_lease_held'],0)
        self.assertEqual(value['lease_object_type'],'semaphore')
        self.assertEqual(value['lease_object_existence'],'not_queried')
        self.assertFalse(value['mapping_live_existence_verified'])
        self.assertNotIn('native_macro_lease_absent',value)
        self.assertNotIn('live_lease_absent',value)
        self.assertFalse(value['formal_G7_eligible']);self.assertFalse(value['fresh_match'])
        self.assertEqual(value['previous_run_model_counts'],dict(requests_started=2,responses_returned=2,plans_applied=2))

    def test_unstopped_or_result_candidate_never_receives_compatibility_report(self):
        for state in ('running','sampling_wait','result_candidate'):
            self.f.mutate(Path('battle-host/host-status.json'),state=state)
            with self.subTest(state=state),self.assertRaises(ValueError):
                self.f.prepare(dry_run=True)
        self.assertFalse(self.f.output.exists());self.assertEqual(self.f.calls,0)

    def test_bad_release_hash_or_session_identity_is_rejected(self):
        self.f.mutate(Path('battle-host/macro-release.json'),final_state_sha256='f'*64)
        with self.assertRaises(ValueError):self.f.prepare(dry_run=True)
        self.assertFalse(self.f.output.exists())

    def test_native_unknown_mask_hook_and_lease_fail_closed(self):
        transport=self.f.root/'reports'/('macro-desktop-'+self.f.run_id)
        for mutation in ('unknown','mask','hook','lease'):
            final=copy.deepcopy(self.f.final)
            if mutation=='unknown':final['unknown_command_ids']=['unknown-command']
            else:final['native'][{'mask':'applied_mask','hook':'self_hook_installed','lease':'lease_held'}[mutation]]=1
            write(transport/'final-state.json',final)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.f.prepare(dry_run=True)
        self.assertFalse(self.f.output.exists());self.assertEqual(self.f.calls,0)

    def test_existing_or_outside_destination_is_rejected(self):
        self.f.output.mkdir()
        with self.assertRaises(ValueError):self.f.prepare(dry_run=True)
        self.f.output=self.f.root/'outside'
        with self.assertRaises(ValueError):self.f.prepare(dry_run=True)
        self.assertEqual(self.f.calls,0)

    def test_cli_returns_refusal_status_even_without_dry_run(self):
        import contextlib,io
        argv=['prepare_macro_continuation_fixture.py','--session',str(self.f.run/'session.json'),'--output',str(self.f.output)]
        capture=io.StringIO()
        with patch.object(continuation,'ROOT',self.f.root),patch.object(continuation.sys,'argv',argv), \
                patch.object(continuation,'prepare',return_value=self.f.prepare()) as prepare, \
                contextlib.redirect_stdout(capture):
            self.assertEqual(continuation.main(),2)
        value=json.loads(capture.getvalue())
        self.assertFalse(value['ready']);self.assertFalse(value['created']);self.assertFalse(self.f.output.exists())
        prepare.assert_called_once()

    def test_tool_contains_no_live_kernel_or_process_api_calls(self):
        tree=ast.parse(inspect.getsource(continuation))
        forbidden={'OpenMutexW','OpenSemaphoreW','OpenFileMappingW','MapViewOfFile','NtQuerySemaphore',
            'WaitForSingleObject','ReleaseSemaphore','OpenProcess','Memory','Popen','StartProcess','TerminateProcess'}
        calls={node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id
            for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,(ast.Attribute,ast.Name))}
        self.assertFalse(calls&forbidden)

    def test_current_static_runtime_contract_explains_the_blocker(self):
        root=Path(__file__).resolve().parents[1]
        native=(root/'native-ai/macro-policy-runtime/native.cpp').read_text(encoding='utf8')
        client=(root/'native-ai/macro-policy-runtime/client_group_roles.py').read_text(encoding='utf8')
        self.assertIn('policy_lease=CreateSemaphoreA',native)
        self.assertIn('ReleaseSemaphore(policy_lease,1,NULL)',native)
        self.assertNotIn('CloseHandle(policy_lease)',native)
        self.assertIn('static Shared* p;',native)
        self.assertIn("macro_runtime_epoch_already_exists",client)
        self.assertIn('c.get_last_error()==183',client)


if __name__=='__main__':unittest.main()
