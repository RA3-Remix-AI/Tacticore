"""Explicit external session bootstrap, invalidation and real-process loading."""
import hashlib,json,os,subprocess,sys,tempfile,time,unittest,uuid
from pathlib import Path
from host_runtime.contracts import ContractError
from host_runtime.desktop_backend import DesktopBackend,NativeHostSpawner
from host_runtime.desktop_session_registry import NAME,load_root,register_root,register_session_source
from host_runtime.profile_store import ProfileStore
from test_host_runtime_desktop_backend import Checks,Spawner,SESSION,START
from test_host_runtime_profile_store import PROFILE,library


class DesktopSessionRegistry(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.library=self.root/'library.json';self.library.write_text(json.dumps(library()),encoding='utf-8')
        self.store=ProfileStore(self.library,self.root/'state')
        self.acceptance=self.root/'external-acceptance';self.run=self.acceptance/'new-run';self.run.mkdir(parents=True)
        self.session=self.run/'session.json';self.session.write_text(json.dumps(dict(session_id=SESSION,pid=101,start_time=START,run_directory=str(self.run),scenario=dict(commander_id=PROFILE,computer_player_index=3))),encoding='utf-8')
        self.production=self.run/'production.json';self.production.write_text('{}');self.persistent=self.run/'persistent.json';self.persistent.write_text('{}')
    def tearDown(self):self.store.close();self.temp.cleanup()
    def register(self,**options):return register_session_source(self.store,self.acceptance,self.session,self.production,self.persistent,**options)
    def backend(self):return DesktopBackend(self.store,checks=Checks(),spawner=Spawner(),caller_alive=lambda:True)
    def assertCode(self,code,operation):
        with self.assertRaises(ContractError) as caught:operation()
        self.assertEqual(code,caught.exception.code)
    def test_explicit_registration_idempotent_and_bootstrap_keeps_external_root(self):
        first=self.register();second=self.register();self.assertEqual(first,second)
        backend=self.backend()
        try:
            self.assertEqual(backend.registration_root,self.acceptance)
            self.assertEqual(backend._registration().session_path,self.session)
            self.assertTrue(backend.run_check(self.store.get_profile(PROFILE)['profile'],{},str(uuid.uuid4()))['ready'])
        finally:backend.close()
    def test_changed_unlaunched_session_requires_explicit_registration_refresh(self):
        self.register()
        session=json.loads(self.session.read_text());session['scenario']['lobby_verified']=True
        self.session.write_text(json.dumps(session),encoding='utf-8')
        self.assertCode('session_unavailable',lambda:self.register())
        self.register(replace_stopped=True)
        backend=self.backend()
        try:self.assertEqual(backend._registration().session_path,self.session)
        finally:backend.close()
    def test_changed_session_cannot_replace_an_unresolved_launch(self):
        self.register();backend=self.backend()
        try:
            profile=self.store.get_profile(PROFILE)['profile'];ready=backend.run_check(profile,{},str(uuid.uuid4()))
            backend.run_start(profile,dict(profile_id=PROFILE,profile_revision=profile['revision'],session_id=SESSION,ready_token=ready['ready_token']),str(uuid.uuid4()))
            session=json.loads(self.session.read_text());session['scenario']['lobby_verified']=True
            self.session.write_text(json.dumps(session),encoding='utf-8')
            self.assertCode('run_state_conflict',lambda:self.register(replace_stopped=True))
        finally:backend.close()
    def test_missing_root_is_not_discovered_from_session_or_historical_directories(self):
        backend=self.backend()
        try:self.assertCode('session_unavailable',backend._registration)
        finally:backend.close()
        self.assertIsNone(load_root(self.store.state_dir))
        self.assertCode('session_root_invalid',lambda:register_session_source(self.store,Path('.'),self.session,self.production,self.persistent))
    def test_root_change_invalidates_readiness_without_rebinding_service(self):
        self.register();backend=self.backend()
        try:
            profile=self.store.get_profile(PROFILE)['profile'];self.assertTrue(backend.run_check(profile,{},str(uuid.uuid4()))['ready'])
            other=self.root/'other';other.mkdir();path=self.store.state_dir/NAME;record=json.loads(path.read_text());record['session_root']=str(other);path.write_text(json.dumps(record))
            self.assertCode('session_registration_changed',backend._registration)
            self.assertEqual(backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],0)
            self.assertEqual(backend.registration_root,self.acceptance)
        finally:backend.close()
    def test_conflict_and_escape_rejected_without_mutating_registered_source(self):
        original=self.register();outside=self.root/'outside.json';outside.write_text('{}')
        self.assertCode('session_unavailable',lambda:register_session_source(self.store,self.acceptance,self.session,outside,self.persistent))
        other=self.root/'other';other.mkdir();self.assertCode('session_root_conflict',lambda:register_root(other,self.store.state_dir))
        self.assertEqual(self.register(),original)
    def test_invalid_root_record_does_not_prevent_status_stop_backend_construction(self):
        self.register();(self.store.state_dir/NAME).write_text('{"schema_version":1,"schema_version":1}')
        backend=self.backend()
        try:self.assertCode('session_root_invalid',backend._registration)
        finally:backend.close()
    def test_old_runtime_registration_is_readable_but_cannot_enable_macro_launch(self):
        runtime=self.run/'runtime-report.json';runtime.write_text('{"offline_fixture":true}')
        pin=hashlib.sha256(runtime.read_bytes()).hexdigest()
        self.register(runtime_report=runtime,runtime_sha256=pin)
        backend=self.backend()
        try:
            registration=backend._registration()
            self.assertEqual((registration.runtime_report,registration.runtime_sha256),(runtime,pin))
            profile=self.store.get_profile(PROFILE)['profile'];ready=backend.run_check(profile,{},str(uuid.uuid4()))
            self.assertFalse(ready['ready'])
            self.assertEqual(ready['reason_code'],'macro_mode_rejects_unit_control_evidence')
            self.assertEqual(backend.spawner.commands,[])
            self.assertEqual(backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],0)
            self.assertEqual(backend._db.execute('SELECT COUNT(*) FROM launches').fetchone()[0],0)
            runtime.write_text('{"changed":true}')
            self.assertCode('runtime_evidence_pin_mismatch',backend._registration)
        finally:backend.close()
    def test_runtime_registration_requires_pair_and_hash_before_bootstrap_write(self):
        runtime=self.run/'runtime-report.json';runtime.write_text('{}')
        self.assertCode('runtime_evidence_pin_required',lambda:self.register(runtime_report=runtime))
        self.assertCode('runtime_evidence_pin_mismatch',lambda:self.register(runtime_report=runtime,runtime_sha256='a'*64))
        self.assertIsNone(load_root(self.store.state_dir))

    def recovery_options(self):
        basic=self.run/'runtime-basic.json';basic.write_text('{"synthetic_basic_registration":true}')
        recovery=self.run/'runtime-recovery.json';recovery.write_text('{"synthetic_recovery_registration":true}')
        return dict(runtime_report=basic,runtime_sha256=hashlib.sha256(basic.read_bytes()).hexdigest(),
            runtime_recovery_report=recovery,runtime_recovery_sha256=hashlib.sha256(recovery.read_bytes()).hexdigest())

    def test_old_recovery_registration_cannot_enable_macro_launch(self):
        options=self.recovery_options();self.register(**options);backend=self.backend()
        try:
            registration=backend._registration()
            self.assertEqual(registration.runtime_recovery_report,options['runtime_recovery_report'])
            self.assertEqual(registration.runtime_recovery_sha256,options['runtime_recovery_sha256'])
            profile=self.store.get_profile(PROFILE)['profile'];ready=backend.run_check(profile,{},str(uuid.uuid4()))
            self.assertFalse(ready['ready'])
            self.assertEqual(ready['reason_code'],'macro_mode_rejects_unit_control_evidence')
            self.assertEqual(backend.spawner.commands,[])
            self.assertEqual(backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],0)
            self.assertEqual(backend._db.execute('SELECT COUNT(*) FROM launches').fetchone()[0],0)
            self.assertTrue(backend.checks.test_only);self.assertTrue(backend.spawner.test_only)
        finally:backend.close()

    def test_recovery_half_pin_missing_basic_or_wrong_hash_cannot_bootstrap(self):
        options=self.recovery_options()
        self.assertCode('first_home_evidence_pin_required',lambda:self.register(runtime_recovery_report=options['runtime_recovery_report']))
        self.assertCode('first_home_requires_baseline_scope',lambda:self.register(runtime_recovery_report=options['runtime_recovery_report'],runtime_recovery_sha256=options['runtime_recovery_sha256']))
        options['runtime_recovery_sha256']='a'*64
        self.assertCode('first_home_evidence_pin_mismatch',lambda:self.register(**options))
        self.assertIsNone(load_root(self.store.state_dir))

    def test_recovery_report_escape_is_rejected_before_registration(self):
        options=self.recovery_options();outside=self.root/'recovery-outside.json';outside.write_text('{}')
        options.update(runtime_recovery_report=outside,runtime_recovery_sha256=hashlib.sha256(outside.read_bytes()).hexdigest())
        self.assertCode('first_home_evidence_registration_required',lambda:self.register(**options))
        self.assertIsNone(load_root(self.store.state_dir))

    def test_changed_historical_recovery_bundle_remains_detected_without_readiness(self):
        options=self.recovery_options();self.register(**options);backend=self.backend()
        try:
            profile=self.store.get_profile(PROFILE)['profile'];ready=backend.run_check(profile,{},str(uuid.uuid4()))
            self.assertFalse(ready['ready']);self.assertIsNone(ready['ready_token'])
            options['runtime_recovery_report'].write_text('{"changed":true}')
            self.assertCode('first_home_evidence_pin_mismatch',backend._registration)
            self.assertFalse(backend.run_check(profile,{},str(uuid.uuid4()))['ready'])
            self.assertEqual(backend.spawner.commands,[])
        finally:backend.close()

    def test_explicit_recovery_upgrade_invalidates_existing_readiness(self):
        options=self.recovery_options();self.register()
        backend=self.backend()
        try:
            profile=self.store.get_profile(PROFILE)['profile'];backend.run_check(profile,{},str(uuid.uuid4()))
            self.assertEqual(backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],1)
            self.register(replace_stopped=True,**options)
            self.assertEqual(backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],0)
            self.assertEqual(backend._registration().runtime_recovery_report,options['runtime_recovery_report'])
            self.assertFalse(backend.run_check(profile,{},str(uuid.uuid4()))['ready'])
        finally:backend.close()

    def test_recovery_upgrade_cannot_replace_unresolved_launch(self):
        self.register();backend=self.backend()
        try:
            profile=self.store.get_profile(PROFILE)['profile'];ready=backend.run_check(profile,{},str(uuid.uuid4()))
            backend.run_start(profile,dict(profile_id=PROFILE,profile_revision=profile['revision'],session_id=SESSION,ready_token=ready['ready_token']),str(uuid.uuid4()))
            original=backend.registration_path.read_bytes()
            self.assertCode('run_state_conflict',lambda:self.register(replace_stopped=True,**self.recovery_options()))
            self.assertEqual(backend.registration_path.read_bytes(),original)
        finally:backend.close()

    def test_real_python_process_reopens_trusted_recovery_pin_without_game_or_HTTP(self):
        options=self.recovery_options();self.register(**options)
        code="from pathlib import Path;import json,sys;from host_runtime.profile_store import ProfileStore;from host_runtime.desktop_backend import DesktopBackend;s=ProfileStore(Path(sys.argv[1]),Path(sys.argv[2]));b=DesktopBackend(s);r=b._registration();print(json.dumps(dict(recovery_matches=r.runtime_recovery_report==Path(sys.argv[3]),pin_matches=r.runtime_recovery_sha256==sys.argv[4])));b.close();s.close()"
        process=subprocess.run([sys.executable,'-B','-c',code,str(self.library),str(self.store.state_dir),str(options['runtime_recovery_report']),options['runtime_recovery_sha256']],
            cwd=Path(__file__).resolve().parent,capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout),dict(recovery_matches=True,pin_matches=True))
    def test_real_python_process_loads_explicit_root_without_game_or_http(self):
        result=self.register()
        code="from pathlib import Path;import json,sys;from host_runtime.profile_store import ProfileStore;from host_runtime.desktop_backend import DesktopBackend;s=ProfileStore(Path(sys.argv[1]),Path(sys.argv[2]));b=DesktopBackend(s);r=b._registration();print(json.dumps(dict(root_matches=b.registration_root==Path(sys.argv[3]),session_matches=r.session_path==Path(sys.argv[4]))));b.close();s.close()"
        process=subprocess.run([sys.executable,'-B','-c',code,str(self.library),str(self.store.state_dir),str(self.acceptance),str(self.session)],cwd=Path(__file__).resolve().parent,capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout),dict(root_matches=True,session_matches=True))

    @unittest.skipUnless(os.name=='nt','Windows process-identity integration')
    def test_real_surrogate_process_start_query_stop_and_no_automatic_registration_replacement(self):
        self.register();profile=self.store.get_profile(PROFILE)['profile'];run=self.run
        script=self.root/'offline-host.py'
        script.write_text("""import json,os,sys,time
from pathlib import Path
from host_runtime.desktop_backend import NativeHostSpawner
target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True)
status=json.loads(sys.argv[2]);status.update(host_pid=os.getpid(),host_start_time=NativeHostSpawner.identity(os.getpid()),state='running')
def save():
 temp=target.with_suffix('.tmp');temp.write_text(json.dumps(status));temp.replace(target)
save();deadline=time.monotonic()+8
while time.monotonic()<deadline and not target.with_name('stop.json').exists():time.sleep(.02)
status['state']='stopped';save()
""",encoding='utf-8')
        children=[];commands=[];integration=Path(__file__).resolve().parent
        class OfflineSpawner:
            test_only=True
            identity=staticmethod(NativeHostSpawner.identity)
            def spawn(self,command,log_path,admission):
                if not admission.test_only:raise AssertionError('surrogate_requires_test_admission')
                commands.append(command);binding=admission.binding
                status=dict(session_id=binding.session_id,pid=binding.game_process_id,process_start=binding.game_process_start,
                    runtime_production=dict(run_id=command[command.index('--runtime-run-id')+1],binding_hash=binding.binding_hash),
                    profile_application=dict(profile_id=PROFILE,profile_revision=profile['revision'],effective_hash=profile['effective']['effective_hash']))
                environment=dict(os.environ,PYTHONPATH=str(integration))
                prefix=command[:command.index(str(integration/'battle_host.py'))]
                child=subprocess.Popen(prefix+[str(script),str(run/'battle-host/host-status.json'),json.dumps(status)],cwd=integration,env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));children.append(child);return child
        backend=DesktopBackend(self.store,checks=Checks(),spawner=OfflineSpawner(),caller_alive=lambda:True)
        try:
            ready=backend.run_check(profile,{},str(uuid.uuid4()));request=str(uuid.uuid4())
            result=backend.run_start(profile,dict(profile_id=PROFILE,profile_revision=profile['revision'],session_id=SESSION,ready_token=ready['ready_token']),request)
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                status=backend.run_status(dict(run_id=result['run_id']),str(uuid.uuid4()))
                if status['state']=='running':break
                time.sleep(.02)
            self.assertEqual(status['state'],'running',dict(launch_pid=children[0].pid,status=json.loads((run/'battle-host/host-status.json').read_text()) if (run/'battle-host/host-status.json').exists() else None));self.assertEqual(status['profile_application']['effective_hash'],profile['effective']['effective_hash'])
            self.assertEqual(commands[0][commands[0].index('--acceptance-root')+1],str(self.acceptance))
            replacement=self.run/'second-session.json';replacement.write_bytes(self.session.read_bytes())
            self.assertCode('session_registration_conflict',lambda:register_session_source(self.store,self.acceptance,replacement,self.production,self.persistent))
            self.assertCode('run_state_conflict',lambda:register_session_source(self.store,self.acceptance,replacement,self.production,self.persistent,replace_stopped=True))
            backend.run_stop(dict(run_id=result['run_id'],session_id=SESSION),str(uuid.uuid4()));children[0].wait(timeout=3)
            status=backend.run_status(dict(run_id=result['run_id']),str(uuid.uuid4()));self.assertEqual(status['state'],'stopped')
            self.assertFalse(status['native_release_verified'])
            self.assertCode('run_state_conflict',lambda:register_session_source(self.store,self.acceptance,replacement,self.production,self.persistent,replace_stopped=True))
        finally:
            backend.close()
            for child in children:
                if child.poll() is None:child.terminate()
                child.wait(timeout=3)


if __name__=='__main__':unittest.main()
