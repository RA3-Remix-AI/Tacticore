"""Stubbed model-authorized production/Native coordination; no real I/O APIs."""
import copy
import ctypes
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import types
import unittest
import uuid
from reserve_controller import ReserveController,ROOT,digest,runtime_type
import held_formations
from unittest.mock import patch

SESSION='11111111-1111-4111-8111-111111111111'
COMMANDER='22222222-2222-4222-8222-222222222222'
PLAN='33333333-3333-4333-8333-333333333333'
BUILD='44444444-4444-4444-8444-444444444444'
class Producer:
    factory_address=0x500000;candidate={'object_id':50};min_interval=150
    def __init__(self,ops):self.ops=ops;self.commands=[];self.rows=[];self.frame=1500;self.reject=False
    def submit(self,command):
        self.ops.append('submit-'+command['unit']);self.commands.append(copy.deepcopy(command))
        receipt=dict(command_id=command['command_id'],task_id=command['task_id'],seq=command['seq'],queue_id=10+command['seq'],enqueue_frame=self.frame,accepted=not self.reject,status='no_dispatch_rejected' if self.reject else 'queued')
        self.rows.append(receipt);return receipt
    def status(self):return dict(ledger=copy.deepcopy(self.rows))
class Tactical:
    def __init__(self,ops):self.ops=ops;self.owner=None;self.allow=True
    def claim_controller_channel(self,controller):
        if not self.allow:return False
        self.owner=controller;self.ops.append('claim-channel');return True
    def release_controller_channel(self,controller,*,independently_verified=False):
        if self.owner!=controller or independently_verified is not True:raise ValueError('channel-release')
        self.owner=None;self.ops.append('release-channel')
class Agent:
    def __init__(self):self.feedback=[];self.pairs={}
    def jobs(self):return {'jobs':[dict(task_id=BUILD,plan_id=PLAN,generation=4,module='build',focus='balanced',host_dispatch_candidate=True,expires_at_game_seconds=145,budget={'fraction':.5})]}
    def set_prebound_paid_pairs(self,value):self.pairs=dict(value)
class Runtime:
    def __init__(self,session,config,output,natural,ops):
        self.config=config;self.output=Path(output);self.session_path=Path(session);self.ops=ops;self.commits=[];self.closed=False;self.retreats=0;self.fail_arm=False;self.no_launch_proven=True
        self.report={'status':'running','native':{'slots':[{'receipt':{'stub':'front'}},{'receipt':{'stub':'support'}}]},'events':[]}
        self.facts={'verified':False,'clock':{'verified':False},'claims':[],'ready':{'verified':False},'source_sha256':'a'*64}
        self.release={'control_release_verified':False,'actors':[],'source_sha256':'f'*64}
    def arm(self):
        self.ops.append('arm')
        if self.fail_arm:raise ValueError('stub_preflight_failure')
    def verified_no_launch(self):
        if not self.no_launch_proven:raise ValueError('stub_unknown_launch')
        data=dict(session_id=SESSION,commander_id=COMMANDER,pid=123,controller_id=self.config['controller_id'],lease_id=self.config['lease_id'],verified=True,never_attached=True,mapping_closed=True,native_launch_intent_persisted=False,native_host_created=False,heartbeat_started=False,game_memory_writes=False,sdk_calls=0,scope='only_this_unlaunched_controller_code_path',controller_config_sha256=digest(self.config),wrapper_sha256=hashlib.sha256(getattr(self,'wrapper_path',ROOT/'tactical/mission-formation-v13/lease.py').read_bytes()).hexdigest(),session_source={'sha256':hashlib.sha256(self.session_path.read_bytes()).hexdigest()})
        path=self.output.with_name('stub-no-launch.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data))
        return dict(data,source_report=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    def poll(self):self.ops.append('poll')
    def verified_facts(self):return copy.deepcopy(self.facts)
    def verified_release(self):return copy.deepcopy(self.release)
    def commit(self,*args,**kwargs):self.commits.append((copy.deepcopy(args[:2]),kwargs));return {'published':True,'completion_claim':False}
    def request_retreat(self):self.retreats+=1
    def stop(self):self.report['status']='finished'
    def close(self):self.closed=True

class Coordination(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.ops=[]
        host=self.host=types.SimpleNamespace(binding=types.SimpleNamespace(session_id=SESSION,commander_id=COMMANDER,player_id=3),output=self.root,args=types.SimpleNamespace(session=self.root/'session.json',execute=True,reserve=1000),phase='running',executor_ready=True,engine=types.SimpleNamespace(current=types.SimpleNamespace(origin='model',production_focus='balanced',expires_at_game_seconds=145,plan_id=PLAN,snapshot_id=1)),agent=Agent(),evidence={'supported_foci':['balanced']},last_snapshot={'source':'game_bridge','paused':False,'game_time_seconds':100,'resources':{'credits':5000},'battlefield':{'formations':[],'contacts':[]}},tactical=types.SimpleNamespace(sent={},executor=Tactical(self.ops)),sent={},sequence=0,remaining_budget=1000,counters={'dispatches':0},natural_path=self.root/'natural.json')
        host.session={'pid':123};host.args.session.write_text(json.dumps({'session_id':SESSION,'pid':123}))
        host.collector=types.SimpleNamespace(region_of=lambda point:'home_base',private_targets={},private_held_formations={})
        host.last_snapshot['battlefield']['contacts']=[dict(contact_id='opportunity',relation='enemy',currently_visible=True,role='structure')]
        host.collector.private_targets={'opportunity':dict(xyz=[1000,0,0],observed_frame=1500)}
        host.executor=Producer(self.ops);self.events=[];host.event=lambda kind,**data:self.events.append(dict(kind=kind,**data));host.feedback=lambda *data:host.agent.feedback.append(data)
        (self.root/'own-state.json').write_text(json.dumps({'factories':[{'address':'0x500000','production_interface_available':True,'interface':'0x600000','xyz':[0,0,0]}]}))
        self.runtime=None
        def create(*args):self.runtime=Runtime(*args,self.ops);return self.runtime
        self.coordinator=ReserveController(host,dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v13'),runtime_factory=create)
    async def asyncTearDown(self):self.temp.cleanup()
    async def prepare(self):self.assertTrue(await self.coordinator.maybe_prepare())
    def facts(self,pair=False,ready=False):
        claims=[dict(role=0,verified=True,object_id=800,type_hash=0x19ab11af,paid_cost=85,borrow_frame=1710,proof_sha256='b'*64)]
        if pair:claims.append(dict(role=1,verified=True,object_id=801,type_hash=0x2c358c61,paid_cost=220,borrow_frame=1800,proof_sha256='c'*64))
        return dict(verified=True,clock=dict(verified=True,start=1710,reserve_deadline=2010,hard_deadline=6210),claims=claims,ready=dict(verified=ready,roles=[dict(role=0,latest_hold_frame=1830,proof_sha256='d'*64,anchor=[0,0,0]),dict(role=1,latest_hold_frame=1830,proof_sha256='e'*64,anchor=[80,0,0])]),source_sha256='a'*64)
    def offer(self):
        self.host.last_snapshot['game_time_seconds']=122
        self.host.last_snapshot['battlefield']['formations']=self.coordinator.held_registry.public_formations(1830)
        self.host.last_snapshot['battlefield']['contacts']=[dict(contact_id='contact_visible',owner_player_id=4,currently_visible=True,relation='enemy',role='economy')]
        self.host.collector.private_held_formations=self.coordinator.held_registry.private_formations()
        self.host.collector.private_targets={'contact_visible':dict(object_id=999,type_hash='0xc45aaeab',observed_frame=1830)}
    async def test_trusted_fourteen_grant_selects_actual_fourteen_factory_without_sdk(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v14')
        coordinator=ReserveController(self.host,grant)
        self.assertEqual(coordinator.directory,'mission-formation-v14')
        with patch.object(ctypes,'WinDLL',side_effect=AssertionError('no Windows API during factory selection')),patch.object(subprocess,'Popen',side_effect=AssertionError('no host launch during factory selection')),patch.object(subprocess,'run',side_effect=AssertionError('no SDK subprocess during factory selection')):
            factory=runtime_type(coordinator.directory)
            runtime=factory(self.host.args.session,{'test':'unarmed'},self.root/'unarmed14.json',self.host.natural_path)
            self.assertEqual(Path(factory.arm.__globals__['__file__']).resolve(),(ROOT/'tactical/mission-formation-v14/lease.py').resolve())
            self.assertIsNone(runtime.host);self.assertFalse(runtime.intent);self.assertIsNone(runtime.shared)
            legacy=runtime_type()
            self.assertEqual(Path(legacy.arm.__globals__['__file__']).resolve(),(ROOT/'tactical/mission-formation-v13/lease.py').resolve())
        for directory in ('mission-formation-v12','../mission-formation-v14','mission-formation-v19',None):
            with self.subTest(directory=directory),self.assertRaises(ValueError):runtime_type(directory)
            bad=dict(grant,executor_directory=directory)
            with self.assertRaises(ValueError):ReserveController(self.host,bad)
    async def test_trusted_fifteen_grant_selects_actual_fifteen_factory_without_sdk(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v15')
        coordinator=ReserveController(self.host,grant)
        with patch.object(ctypes,'WinDLL',side_effect=AssertionError('no Windows API')),patch.object(subprocess,'Popen',side_effect=AssertionError('no host launch')),patch.object(subprocess,'run',side_effect=AssertionError('no SDK subprocess')):
            factory=runtime_type(coordinator.directory)
            runtime=factory(self.host.args.session,{'test':'unarmed'},self.root/'unarmed15.json',self.host.natural_path)
            self.assertEqual(Path(factory.arm.__globals__['__file__']).resolve(),(ROOT/'tactical/mission-formation-v15/lease.py').resolve())
            self.assertIsNone(runtime.host);self.assertFalse(runtime.intent);self.assertIsNone(runtime.shared)
    async def test_trusted_sixteen_grant_selects_actual_factory_and_450_clock_without_sdk(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v16',stop_schema={'reserve_duration_frames':450})
        coordinator=ReserveController(self.host,grant,runtime_factory=self.coordinator.runtime_factory)
        self.assertEqual(coordinator.reserve_duration_frames,450)
        with patch.object(ctypes,'WinDLL',side_effect=AssertionError('no Windows API')),patch.object(subprocess,'Popen',side_effect=AssertionError('no host launch')),patch.object(subprocess,'run',side_effect=AssertionError('no SDK subprocess')):
            factory=runtime_type(coordinator.directory)
            runtime=factory(self.host.args.session,{'test':'unarmed'},self.root/'unarmed16.json',self.host.natural_path)
            self.assertEqual(Path(factory.arm.__globals__['__file__']).resolve(),(ROOT/'tactical/mission-formation-v16/lease.py').resolve())
            self.assertIsNone(runtime.host);self.assertFalse(runtime.intent);self.assertIsNone(runtime.shared)
        await coordinator.maybe_prepare()
        self.assertEqual(coordinator.held_registry.controller(coordinator.config['controller_id'])['reserve_offset_frames'],450)
        self.runtime.facts=dict(self.facts(),clock=dict(verified=True,start=1710,reserve_deadline=2160,hard_deadline=6210))
        await coordinator.poll()
        state=coordinator.held_registry.controller(coordinator.config['controller_id'])
        self.assertEqual((state['reserve_start_frame'],state['reserve_deadline_frame'],state['hard_deadline_frame']),(1710,2160,6210))
    async def test_trusted_seventeen_main_factory_without_sdk_and_450_policy(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v17',stop_schema={'reserve_duration_frames':450,'wrapper_filename':'lease.py'})
        coordinator=ReserveController(self.host,grant,runtime_factory=self.coordinator.runtime_factory)
        with patch.object(ctypes,'WinDLL',side_effect=AssertionError('no Windows API')),patch.object(subprocess,'Popen',side_effect=AssertionError('no host launch')),patch.object(subprocess,'run',side_effect=AssertionError('no SDK subprocess')):
            factory=runtime_type(coordinator.directory,coordinator.wrapper_filename)
            runtime=factory(self.host.args.session,{'test':'unarmed'},self.root/'unarmed17.json',self.host.natural_path)
            self.assertEqual(Path(factory.arm.__globals__['__file__']).resolve(),(ROOT/'tactical/mission-formation-v17/lease.py').resolve())
            self.assertIsNone(runtime.host);self.assertFalse(runtime.intent);self.assertIsNone(runtime.shared)
        self.assertTrue(await coordinator.maybe_prepare())
        self.assertEqual(coordinator.held_registry.controller(coordinator.config['controller_id'])['reserve_offset_frames'],450)
        self.runtime.facts=dict(self.facts(),clock=dict(verified=True,start=1710,reserve_deadline=2160,hard_deadline=6210))
        await coordinator.poll()
        state=coordinator.held_registry.controller(coordinator.config['controller_id'])
        self.assertEqual((state['reserve_deadline_frame'],state['hard_deadline_frame']),(2160,6210))
    async def test_trusted_eighteen_main_factory_without_sdk_and_450_policy(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v18',stop_schema={'reserve_duration_frames':450,'wrapper_filename':'lease.py'})
        coordinator=ReserveController(self.host,grant,runtime_factory=self.coordinator.runtime_factory)
        with patch.object(ctypes,'WinDLL',side_effect=AssertionError('no Windows API')),patch.object(subprocess,'Popen',side_effect=AssertionError('no host launch')),patch.object(subprocess,'run',side_effect=AssertionError('no SDK subprocess')):
            factory=runtime_type(coordinator.directory,coordinator.wrapper_filename)
            runtime=factory(self.host.args.session,{'test':'unarmed'},self.root/'unarmed18.json',self.host.natural_path)
            self.assertEqual(Path(factory.arm.__globals__['__file__']).resolve(),(ROOT/'tactical/mission-formation-v18/lease.py').resolve())
            self.assertIsNone(runtime.host);self.assertFalse(runtime.intent);self.assertIsNone(runtime.shared)
        self.assertTrue(await coordinator.maybe_prepare())
        self.assertEqual(coordinator.held_registry.controller(coordinator.config['controller_id'])['reserve_offset_frames'],450)
        self.runtime.facts=dict(self.facts(),clock=dict(verified=True,start=1710,reserve_deadline=2160,hard_deadline=6210))
        await coordinator.poll()
        state=coordinator.held_registry.controller(coordinator.config['controller_id'])
        self.assertEqual((state['reserve_deadline_frame'],state['hard_deadline_frame']),(2160,6210))
    async def test_trusted_sixteen_v2_factory_import_and_same_path_no_launch_hash(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v16',stop_schema={'reserve_duration_frames':450,'wrapper_filename':'lease_v2.py'})
        original=self.coordinator.runtime_factory
        def create(*args):
            runtime=original(*args);runtime.fail_arm=True;runtime.wrapper_path=ROOT/'tactical/mission-formation-v16/lease_v2.py';return runtime
        coordinator=ReserveController(self.host,grant,runtime_factory=create)
        self.assertEqual(coordinator.wrapper_path,ROOT/'tactical/mission-formation-v16/lease_v2.py')
        with patch.object(ctypes,'WinDLL',side_effect=AssertionError('no Windows API')),patch.object(subprocess,'Popen',side_effect=AssertionError('no host launch')),patch.object(subprocess,'run',side_effect=AssertionError('no SDK subprocess')):
            factory=runtime_type(coordinator.directory,coordinator.wrapper_filename)
            runtime=factory(self.host.args.session,{'test':'unarmed'},self.root/'unarmed16v2.json',self.host.natural_path)
            self.assertEqual(Path(factory.arm.__globals__['__file__']).resolve(),coordinator.wrapper_path.resolve())
            self.assertIsNone(runtime.host);self.assertFalse(runtime.intent);self.assertIsNone(runtime.shared)
        with self.assertRaisesRegex(ValueError,'preflight'):await coordinator.maybe_prepare()
        self.assertFalse(coordinator.owns_channel());self.assertIsNone(self.host.tactical.executor.owner)
        self.assertEqual(coordinator.record['release_kind'],'verified_no_launch_only')
    async def test_v2_certificate_cannot_substitute_legacy_wrapper_hash(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v16',stop_schema={'reserve_duration_frames':450,'wrapper_filename':'lease_v2.py'})
        original=self.coordinator.runtime_factory
        def create(*args):
            runtime=original(*args);runtime.fail_arm=True;runtime.wrapper_path=ROOT/'tactical/mission-formation-v16/lease.py';return runtime
        coordinator=ReserveController(self.host,grant,runtime_factory=create)
        with self.assertRaisesRegex(ValueError,'preflight'):await coordinator.maybe_prepare()
        self.assertTrue(coordinator.owns_channel());self.assertIsNotNone(self.host.tactical.executor.owner)
        self.assertTrue(coordinator.record['no_launch_unproved'])
    async def test_wrapper_allowlist_rejects_other_families_and_paths(self):
        for family,wrapper in (('mission-formation-v13','lease_v2.py'),('mission-formation-v14','lease_v2.py'),('mission-formation-v15','lease_v2.py'),('mission-formation-v17','lease_v2.py'),('mission-formation-v18','lease_v2.py'),('mission-formation-v16','../lease.py'),('mission-formation-v16','C:/lease.py'),('mission-formation-v16','other.py'),('mission-formation-v16',None)):
            grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory=family,stop_schema={'reserve_duration_frames':450 if family in ('mission-formation-v16','mission-formation-v17','mission-formation-v18') else 300,'wrapper_filename':wrapper})
            with self.subTest(family=family,wrapper=wrapper):
                with self.assertRaises(ValueError):ReserveController(self.host,grant)
                with self.assertRaises(ValueError):runtime_type(family,wrapper)
    async def test_trusted_grant_clock_policy_must_match_runtime_family(self):
        for family,duration in (('mission-formation-v13',450),('mission-formation-v14',450),('mission-formation-v15',450),('mission-formation-v16',300),('mission-formation-v16',True),('mission-formation-v16',451),('mission-formation-v17',300),('mission-formation-v17',True),('mission-formation-v17',451),('mission-formation-v18',300),('mission-formation-v18',True),('mission-formation-v18',451)):
            grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory=family,stop_schema={'reserve_duration_frames':duration})
            with self.subTest(family=family,duration=duration),self.assertRaises(ValueError):ReserveController(self.host,grant)
        with self.assertRaises(ValueError):ReserveController(self.host,dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v16'))
        for schema in (None,[],450):
            with self.subTest(schema=schema),self.assertRaises(ValueError):ReserveController(self.host,dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v16',stop_schema=schema))
    async def test_only_accepted_model_balanced_build_authorizes_money(self):
        for attribute,value in (('origin','local_fallback'),('production_focus','infantry')):
            previous=getattr(self.host.engine.current,attribute);setattr(self.host.engine.current,attribute,value)
            self.assertFalse(await self.coordinator.maybe_prepare());setattr(self.host.engine.current,attribute,previous)
        self.host.remaining_budget=304;self.assertFalse(await self.coordinator.maybe_prepare())
        self.assertEqual(self.ops,[]);self.assertEqual(self.host.executor.commands,[])
    async def test_verified_no_launch_failure_rolls_back_only_zero_slot_channel(self):
        original=self.coordinator.runtime_factory
        def factory(*args):
            runtime=original(*args);runtime.fail_arm=True;return runtime
        self.coordinator.runtime_factory=factory
        with self.assertRaisesRegex(ValueError,'preflight'):await self.coordinator.maybe_prepare()
        self.assertFalse(self.coordinator.owns_channel());self.assertIsNone(self.host.tactical.executor.owner);self.assertEqual(self.host.executor.commands,[])
        self.assertEqual(self.coordinator.record['release_kind'],'verified_no_launch_only');self.assertIsNone(self.coordinator.held_registry.audit()['controllers'][0]['reserve_start_frame'])
    async def test_unproven_arm_failure_keeps_both_channel_claims(self):
        original=self.coordinator.runtime_factory
        def factory(*args):
            runtime=original(*args);runtime.fail_arm=True;runtime.no_launch_proven=False;return runtime
        self.coordinator.runtime_factory=factory
        with self.assertRaises(ValueError):await self.coordinator.maybe_prepare()
        self.assertTrue(self.coordinator.owns_channel());self.assertIsNotNone(self.host.tactical.executor.owner);self.assertTrue(self.coordinator.record['no_launch_unproved'])
    async def test_scene_seventeen_releases_only_verified_claims_and_never_marks_effect_completed(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v17',stop_schema={'reserve_duration_frames':450})
        coordinator=ReserveController(self.host,grant,runtime_factory=self.coordinator.runtime_factory)
        self.assertTrue(await coordinator.maybe_prepare());runtime=self.runtime
        runtime.facts=dict(self.facts(True),clock=dict(verified=True,start=1710,reserve_deadline=2160,hard_deadline=6210))
        coordinator.normalize(runtime.facts);runtime.report.update(status='finished',host_exit=9,events=[dict(frame=1830),dict(frame=0)],assessment={'effect_verified':True})
        runtime.output.write_text('{}');sidecar=coordinator.output/'scene.json';sidecar.write_text('{}');file_sha=hashlib.sha256(sidecar.read_bytes()).hexdigest()
        proof=dict(sidecar_path=str(sidecar),sidecar_sha256=file_sha,source_sha256=hashlib.sha256(runtime.output.read_bytes()).hexdigest(),controller_id=coordinator.config['controller_id'],lease_id=coordinator.config['lease_id'],session_id=SESSION,pid=123,scene_closed_verified=True,scene_disposed_control_release=True,control_release_verified=True,actors=[dict(role=0,object_id=800,released=True,never_held=False),dict(role=1,object_id=801,released=True,never_held=False)],**{key:False for key in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')})
        runtime.release=dict(proof,scene_release=copy.deepcopy(proof))
        fake_reader=types.SimpleNamespace(verify_path=lambda *args:proof);spec=types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda module:None))
        with patch('reserve_controller.importlib.util.spec_from_file_location',return_value=spec),patch('reserve_controller.importlib.util.module_from_spec',return_value=fake_reader),patch.object(self.host.executor,'status',side_effect=AssertionError('no ended-scene producer query')):
            await coordinator.poll()
        state=coordinator.held_registry.controller(coordinator.config['controller_id'])
        self.assertEqual(state['terminal']['status'],'failed');self.assertEqual(state['terminal']['reason_code'],'scene_closed');self.assertEqual(state['release']['proof_sha256'],file_sha)
        self.assertTrue(coordinator.closed);self.assertFalse(coordinator.owns_channel());self.assertIsNone(self.host.tactical.executor.owner);self.assertEqual(coordinator.record['release_kind'],'scene_closed_exclusive_control_only')
    async def test_scene_eighteen_releases_only_verified_claims_and_never_marks_effect_completed(self):
        grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v18',stop_schema={'reserve_duration_frames':450})
        coordinator=ReserveController(self.host,grant,runtime_factory=self.coordinator.runtime_factory)
        self.assertTrue(await coordinator.maybe_prepare());runtime=self.runtime
        runtime.facts=dict(self.facts(True),clock=dict(verified=True,start=1710,reserve_deadline=2160,hard_deadline=6210))
        coordinator.normalize(runtime.facts);runtime.report.update(status='finished',host_exit=9,events=[dict(frame=1830),dict(frame=0)],assessment={'effect_verified':True})
        runtime.output.write_text('{}');sidecar=coordinator.output/'scene.json';sidecar.write_text('{}');file_sha=hashlib.sha256(sidecar.read_bytes()).hexdigest()
        proof=dict(sidecar_path=str(sidecar),sidecar_sha256=file_sha,source_sha256=hashlib.sha256(runtime.output.read_bytes()).hexdigest(),controller_id=coordinator.config['controller_id'],lease_id=coordinator.config['lease_id'],session_id=SESSION,pid=123,scene_closed_verified=True,scene_disposed_control_release=True,control_release_verified=True,actors=[dict(role=0,object_id=800,released=True,never_held=False),dict(role=1,object_id=801,released=True,never_held=False)],**{key:False for key in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')})
        runtime.release=dict(proof,scene_release=copy.deepcopy(proof))
        fake_reader=types.SimpleNamespace(verify_path=lambda *args:proof);spec=types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda module:None))
        with patch('reserve_controller.importlib.util.spec_from_file_location',return_value=spec),patch('reserve_controller.importlib.util.module_from_spec',return_value=fake_reader),patch.object(self.host.executor,'status',side_effect=AssertionError('no ended-scene producer query')):
            await coordinator.poll()
        state=coordinator.held_registry.controller(coordinator.config['controller_id'])
        self.assertEqual(state['terminal']['status'],'failed');self.assertEqual(state['terminal']['reason_code'],'scene_closed');self.assertEqual(state['release']['proof_sha256'],file_sha)
        self.assertTrue(coordinator.closed);self.assertFalse(coordinator.owns_channel());self.assertIsNone(self.host.tactical.executor.owner);self.assertEqual(coordinator.record['release_kind'],'scene_closed_exclusive_control_only')
    async def test_failed_scene_attempt_keeps_claims_and_global_channel(self):
        await self.prepare();self.coordinator.normalize(self.facts(True));self.runtime.report.update(status='finished',events=[dict(frame=1830)])
        self.runtime.release={'control_release_verified':False,'source_sha256':'a'*64,'scene_release':{'scene_disposed_control_release':False,'control_release_verified':False}}
        await self.coordinator.poll()
        self.assertTrue(self.coordinator.owns_channel());self.assertFalse(self.coordinator.closed);self.assertEqual(self.coordinator.held_registry.claimed_actor_ids(),{800,801});self.assertIsNotNone(self.host.tactical.executor.owner)
    async def test_no_current_visible_ground_opportunity_waits_without_channel_or_one_use(self):
        target=self.host.collector.private_targets['opportunity']
        for position in ([100,0,0],[3000,0,0]):
            target['xyz']=position;self.assertFalse(await self.coordinator.maybe_prepare())
        target['xyz']=[1000,0,0];target['observed_frame']=1400;self.assertFalse(await self.coordinator.maybe_prepare())
        target['observed_frame']=1500;self.host.tactical.executor.allow=False;self.assertFalse(await self.coordinator.maybe_prepare())
        self.assertFalse(self.coordinator.attempted);self.assertEqual(self.host.sequence,0);self.assertFalse(self.coordinator.owns_channel());self.assertEqual(self.ops,[])
    async def test_prearm_before_first_submit_two_predeclared_sequences_and_budget(self):
        await self.prepare();self.assertEqual(self.ops[:3],['claim-channel','arm','submit-conscript']);self.assertEqual(self.host.sequence,2)
        self.assertTrue(self.coordinator.blocks_build());self.assertEqual(self.coordinator.reserved_budget(),220)
        state=self.coordinator.held_registry.audit();self.assertIsNotNone(state['channel_owner']);self.assertFalse(state['controllers'][0]['lease_clock_bound'])
        saved=json.loads(self.coordinator.path.read_text());self.assertEqual(saved['authorization']['model_plan_generation'],4);self.assertEqual(saved['authorization']['parent_build_task_id'],BUILD);self.assertNotIn('calibration',saved['authorization']['authorization_kind'])
        self.host.last_snapshot['game_time_seconds']=109;await self.coordinator.poll();self.assertEqual(len(self.host.executor.commands),1)
        self.host.last_snapshot['game_time_seconds']=110;self.host.executor.frame=1650;await self.coordinator.poll()
        self.assertEqual([c['seq'] for c in self.host.executor.commands],[1,2]);self.assertEqual(sum(c['budget'] for c in self.host.executor.commands),305);self.assertFalse(self.coordinator.blocks_build())
        self.assertFalse(await self.coordinator.maybe_prepare())
    async def test_partial_claim_immediately_excludes_first_actor_and_waiting_never_releases(self):
        await self.prepare();self.runtime.facts=self.facts();await self.coordinator.poll()
        self.assertEqual(self.coordinator.held_registry.claimed_actor_ids(),{800})
        clock=self.coordinator.held_registry.audit()['controllers'][0];self.assertEqual((clock['reserve_start_frame'],clock['reserve_deadline_frame']),(1710,2010))
        self.runtime.facts={'verified':False,'clock':{'verified':False},'claims':[],'ready':{'verified':False},'source_sha256':'a'*64};await self.coordinator.poll()
        self.assertEqual(self.coordinator.held_registry.claimed_actor_ids(),{800})
    async def test_changed_proven_claim_or_clock_fails_without_dropping_claim(self):
        await self.prepare();self.coordinator.normalize(self.facts());changed=self.facts();changed['claims'][0]['object_id']=802
        with self.assertRaisesRegex(ValueError,'claim_changed'):self.coordinator.normalize(changed)
        changed=self.facts();changed['clock']['hard_deadline']+=1
        with self.assertRaisesRegex(ValueError,'clock_changed'):self.coordinator.normalize(changed)
        self.assertEqual(self.coordinator.held_registry.claimed_actor_ids(),{800})
    async def test_ready_scope_needs_real_current_public_pair_and_urgent_only_once(self):
        await self.prepare();self.coordinator.normalize(self.facts(True,True));self.coordinator.update_scope();self.assertEqual(self.host.agent.pairs,{})
        self.offer();self.coordinator.update_scope();self.assertEqual(len(self.host.agent.pairs),1)
        self.assertIsNotNone(self.coordinator.urgent_ready_epoch());self.assertIsNone(self.coordinator.urgent_ready_epoch())
    async def test_commit_reuses_same_runtime_and_exact_original_deadline(self):
        await self.prepare();self.coordinator.normalize(self.facts(True,True));self.offer();fid=next(iter(self.coordinator.held_registry.private_formations()))
        request=dict(session_id=SESSION,player_id=3,commander_id=COMMANDER,command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=1,module='combined_arms',purpose='coordinate_force',formation_ids=[fid],formation_versions=[(fid,1)],required_roles=['infantry','anti_air'],force_fraction=1,target_contact_id='contact_visible',expires_frame=6210)
        proof=self.root/'proof.json';proof.write_text('{}');formation=self.coordinator.formation(fid)
        changed=dict(request,expires_frame=6310)
        with self.assertRaisesRegex(ValueError,'original_deadline'):await self.coordinator.commit(changed,formation,proof)
        result=await self.coordinator.commit(request,formation,proof);self.assertTrue(result['published']);self.assertFalse(result['completion_claim']);self.assertEqual(len(self.runtime.commits),1);self.assertEqual(self.ops.count('arm'),1)
        self.assertEqual(self.coordinator.record['mission_mapping']['hard_deadline_frame'],6210)
        self.host.last_snapshot['game_time_seconds']=123
        self.assertTrue((await self.coordinator.commit(request,formation,proof))['published'])
        self.assertEqual(self.coordinator.record['mission_mapping']['commit_frame'],1830)
        with self.assertRaisesRegex(ValueError,'write_once'):await self.coordinator.commit(dict(request,command_id=str(uuid.uuid4())),formation,proof)
    async def test_no_independent_release_keeps_channel_and_untasked_terminal_pending(self):
        await self.prepare();self.runtime.facts=self.facts();self.runtime.report['events']=[{'frame':1850}]
        with self.assertRaisesRegex(ValueError,'release_unverified'):await self.coordinator.stop()
        self.assertTrue(self.coordinator.owns_channel());self.assertEqual(self.coordinator.held_registry.claimed_actor_ids(),{800});self.assertIn('native_terminal_seen',self.coordinator.record)
    async def test_independent_exact_release_closes_untasked_lifecycle_not_completion(self):
        await self.prepare();self.runtime.facts=self.facts();self.runtime.report['events']=[{'frame':1850}];self.runtime.release.update(control_release_verified=True,actors=[{'object_id':800,'released':True,'never_held':False},{'object_id':0,'released':True,'never_held':True}])
        await self.coordinator.stop();self.assertFalse(self.coordinator.owns_channel());self.assertTrue(self.runtime.closed)
        state=self.coordinator.held_registry.audit()['controllers'][0];self.assertIsNone(state['mission_commit']);self.assertEqual(state['terminal']['status'],'failed');self.assertEqual(len(self.host.executor.commands),1)
    async def test_parent_build_completed_only_after_both_paid_correlated_receipts(self):
        await self.prepare();self.host.last_snapshot['game_time_seconds']=110;self.host.executor.frame=1650;await self.coordinator.poll()
        for row,order in zip(self.host.executor.rows,self.coordinator.record['orders']):row.update(status='completed',completed=True,paid_verified=True,paid=order['command']['budget'],cost=order['command']['budget'],created=True,completion_observed=True,live_samples=1,payment_error=0,queue_preserved=True,object_id=800 if row['seq']==1 else 801)
        await self.coordinator.receive_production();self.assertEqual(self.host.agent.feedback[-1][1],'completed');self.assertTrue(self.host.sent[BUILD]['terminal'])
        await self.coordinator.receive_production();self.assertEqual(sum(row[1]=='completed' for row in self.host.agent.feedback),1)

if __name__=='__main__':unittest.main()
