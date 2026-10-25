"""Mission host boundary tests with fake memory and kernel; zero SDK calls."""
import copy,ctypes as c,importlib.util,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import MagicMock,patch
import test_client as boundary
Memory=boundary.Memory;m=boundary.m
import inspect_own_weapons
from test_mission_combat import fixture
import mission_readonly_disposal as disposal
ROOT=Path(__file__).resolve().parent
class MissionClientTests(unittest.TestCase):
 def setup_executor(self):
  helper=boundary.ModelBoundary();e=helper.executor();t=helper.task();t['expires_frame']=5500;e.capability_grants[('attack','main_attack')]=dict(executor_directory='mission-combat',stop_schema=dict(mission_protocol='continuous_tactical_v1',mission_duration_frames=4500));pre=helper.preflight();pre.update(frame=1000,selected=pre['units'][0],logic='0x1000');pre['selected']['hp']=100.;captured=[]
  def queue(**kwargs):
   captured.append(kwargs);r=dict(command_id=kwargs['command_id'],task_id=kwargs['task_id'],status='queued',accepted=True,started=False,completed=False,object_ids=[kwargs['object_id']],mission_input=kwargs['mission_input'],wrapper_attempted=False,dispatch_attempted=False,unit_results=[],issued_frame=0,session_id=e.session['session_id'],commander_id=e.commander_id,player_id=3,seq=kwargs['seq']);e.ledger[kwargs['command_id']]=r;return dict(r)
  e.submit_attack_probe=queue
  return e,t,pre,captured
 def submit(self,e,t,pre):
  with patch.object(m.backend,'readiness',return_value=(pre,None,None,None,None,None,Memory())),patch.object(inspect_own_weapons,'active_weapon',return_value={'selected':dict(template_id='0x41872ecc',ammo=1)}):return e.submit(t)
 def test_long_deadline_and_normal_prepare_are_queued_without_issued(self):
  e,t,pre,c=self.setup_executor();r=self.submit(e,t,pre);self.assertTrue(r['accepted'],r);self.assertFalse(r['started']);self.assertEqual(r['expires_frame'],5500);self.assertEqual(c[0]['mission_input']['retreat_point']['xyz'],pre['selected']['xyz']);self.assertEqual(c[0]['mission_input']['retreat_point']['source'],'own_actor_history')
 def test_untrusted_overlong_deadline_never_queues(self):
  e,t,pre,c=self.setup_executor();t['expires_frame']=5501;r=self.submit(e,t,pre);self.assertFalse(r['accepted']);self.assertFalse(c)
 def test_mission_input_frozen_after_context_changes(self):
  e,t,pre,c=self.setup_executor();r=self.submit(e,t,pre);e.mission_context={'schema_version':1,'retreat_point':{'xyz':[999,999,999]}};self.assertEqual(r['mission_input']['retreat_point']['xyz'],[0.,0.,210.])
 def test_old_primitive_grant_cannot_admit_long_expiry(self):
  e,t,pre,c=self.setup_executor();e.capability_grants[('attack','main_attack')]['stop_schema']={};r=self.submit(e,t,pre);self.assertFalse(r['accepted']);self.assertFalse(c)
 def test_public_rejection_echoes_exact_identity_and_never_queued(self):
  e,t,pre,c=self.setup_executor();e.capabilities={};r=self.submit(e,t,pre)
  self.assertEqual({k:r[k] for k in ['command_id','task_id','seq','session_id','player_id','commander_id']},dict(command_id=t['command_id'],task_id=t['task_id'],seq=t['seq'],session_id=e.session['session_id'],player_id=3,commander_id=e.commander_id));self.assertTrue(r['no_dispatch_verified']);self.assertFalse(r['dispatch_attempted']);self.assertFalse(e.ledger);self.assertTrue(e.pending.empty())
 def test_enqueued_metadata_fault_is_unknown_never_fake_refusal(self):
  e,t,pre,c=self.setup_executor()
  def broken_queue(**kwargs):
   r=dict(command_id=kwargs['command_id'],task_id=kwargs['task_id'],status='queued',accepted=True);e.ledger[r['command_id']]=r;e.pending.put(r['command_id']);return dict(r)
  e.submit_attack_probe=broken_queue;r=self.submit(e,t,pre);self.assertEqual(r['status'],'unknown');self.assertFalse(r['no_dispatch_verified']);self.assertEqual(e.ledger[t['command_id']]['status'],'cancelled')
 def test_internal_probe_refusal_is_bound_at_public_boundary(self):
  e,t,pre,c=self.setup_executor();e.submit_attack_probe=lambda **kwargs:dict(accepted=False,status='no_dispatch_rejected',reason_code='game_paused');r=self.submit(e,t,pre);self.assertEqual(r['command_id'],t['command_id']);self.assertTrue(r['no_dispatch_verified']);self.assertFalse(e.ledger)
 def test_ground_mission_never_accepts_air_target(self):
  e,t,pre,c=self.setup_executor();e.contacts['contact_c']['role']='air';self.assertFalse(self.submit(e,t,pre)['accepted']);self.assertFalse(c)
 def test_queued_retreat_cancel_is_idempotent_and_does_not_stop_executor(self):
  e,t,pre,c=self.setup_executor();r=self.submit(e,t,pre);self.assertTrue(e.request_mission_retreat(t['task_id'])['accepted']);self.assertTrue(e.request_mission_retreat(t['task_id'])['already_requested']);self.assertEqual(e.state,'running');self.assertFalse(e.reserved_units);self.assertFalse(e.ledger[r['command_id']]['completed'])
 def test_queue_expiry_certificate_is_bound_and_never_return_claim(self):
  e,t,pre,c=self.setup_executor();r=self.submit(e,t,pre);live=e.ledger[r['command_id']];self.assertTrue(e._certify_queue_rejection(live,'task_expired_before_dispatch'));certificate=live['pre_dispatch'];self.assertEqual(certificate['protocol'],'executor_queue_rejection_v1');self.assertEqual(certificate['task_id'],t['task_id']);self.assertEqual(certificate['object_ids'],[1]);self.assertTrue(live['no_dispatch_verified']);self.assertFalse(live['started']);self.assertFalse(live['execution']['restoration_verified'])
 def test_any_possible_wrapper_or_report_blocks_queue_certificate(self):
  for key,value in [('wrapper_attempted',True),('dispatch_attempted',True),('active_report','report.json'),('issued_frame',1001),('unit_results',[{'native':{}}])]:
   e,t,pre,c=self.setup_executor();r=self.submit(e,t,pre);live=e.ledger[r['command_id']];live[key]=value;self.assertFalse(e._certify_queue_rejection(live,'cancelled'),key)
 def test_active_retreat_sets_only_bound_shared_flag(self):
  raw=fixture();schema,runtime=m.runtime_backend('mission-combat');shared=runtime.Tactical();rq=raw['request'];shared.pid=raw['preflight']['pid'];shared.token=rq['token'];shared.seq=rq['seq'];shared.phase=1
  import struct
  for field,value in [('session',raw['session_id']),('commander',raw['preflight']['commander_id']),('command',rq['command_id']),('task',rq['task_id'])]:getattr(shared,field)[:]=struct.unpack('<4I',uuid.UUID(value).bytes)
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'raw.json';path.write_text(json.dumps(raw),encoding='utf-8');e=m.TacticalExecutor('unused','unused',raw['preflight']['commander_id']);e.session={'session_id':raw['session_id'],'pid':raw['preflight']['pid']};cmd=str(uuid.uuid4());e.active=cmd;e.ledger[cmd]=dict(command_id=cmd,task_id=rq['task_id'],status='started',object_ids=[804],executor_directory='mission-combat',active_report=str(path));kernel=MagicMock();kernel.OpenFileMappingW.return_value=1;kernel.MapViewOfFile.return_value=c.addressof(shared)
   with patch.object(m.backend,'k',kernel):r=e.request_mission_retreat(rq['task_id'])
   self.assertTrue(r['accepted']);self.assertEqual(shared.retreat_requested,1);self.assertEqual(shared.stop_requested,0);self.assertIsNone(e.worker)
 def test_mission_death_release_requires_all_fourteen_entries(self):
  r=fixture();r['native'].update(phase=4,error=32,return_calls=0,return_verified=0);r['events']=[e for e in r['events'] if e.get('tag')!=3];p=disposal.profile(r);state=dict(timer=0,phase=4,error=32,restore_mask=16383,active=0,shared_pointer='0x10000',module_base='0x20000',token=r['request']['token'],seq=r['request']['seq'],entries=[dict(x,actual=x['expected']) for x in disposal.trusted_entries(r)],pid=r['preflight']['pid'],thread=r['preflight']['window_thread'],session_id=r['session_id'],commander_id=r['preflight']['commander_id'],command_id=r['request']['command_id'],task_id=r['request']['task_id'],object_id=r['preflight']['selected']['object_id'],type_hash=r['preflight']['selected']['type_hash'],owner=r['preflight']['owner']);e=dict(source_sha256='source',session_id=r['session_id'],pid=r['preflight']['pid'],layout=p['layout'],completed=False,goal_observed=False,return_verified=False,inert_snapshots=[copy.deepcopy(state),copy.deepcopy(state)],scans=[dict(complete=True,logic=r['preflight']['logic'],frame=x,end_frame=x,ids=[1,2,3],count=3) for x in [200,202]])
  self.assertTrue(disposal.verify(e,r,'source')['restoration_verified']);e['inert_snapshots'][0]['entries']=e['inert_snapshots'][0]['entries'][:12];self.assertFalse(disposal.verify(e,r,'source')['restoration_verified'])
if __name__=='__main__':unittest.main()
