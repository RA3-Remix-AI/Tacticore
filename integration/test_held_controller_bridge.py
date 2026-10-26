"""Parent dispatch into a pre-existing held controller; no game or HTTP."""
import copy,json,tempfile,types,unittest,uuid
from pathlib import Path
from tactical_bridge import TacticalBridge
from held_controller_receipts import receipt_for

def uid():return str(uuid.uuid4())

class HeldBridge(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.fid='formation_paid'
  binding=types.SimpleNamespace(session_id=uid(),commander_id=uid(),player_id=3)
  self.job=dict(task_id=uid(),module='combined_arms',purpose='coordinate_force',host_dispatch_candidate=True,formation_ids=[self.fid],formation_versions=[[self.fid,1]],required_roles=['infantry','anti_air'],force_fraction=1,target_contact_id='visible',expires_at_game_seconds=100,plan_id=uid(),generation=1)
  self.operations=[]
  def commit_task(task,**fields):self.operations.append(('host_commit',task,fields))
  self.host=types.SimpleNamespace(output=self.root,binding=binding,phase='running',last_snapshot=dict(paused=False,game_time_seconds=1000/15,battlefield={'contacts':[dict(contact_id='visible',relation='enemy',currently_visible=True)]}),agent=types.SimpleNamespace(jobs=lambda:{'jobs':[self.job]},host_commit_task=commit_task),event=lambda *a,**k:None)
  reservations=types.SimpleNamespace(reserved=set(),reserve=lambda ids:self.fail('Must not reserve held actors in the free registry'),release=lambda ids:None)
  collector=types.SimpleNamespace(private_formations={},private_regions={},formations=reservations,visibility_proof_path=self.root/'fov.json',private_targets={'visible':dict(object_id=990,type_hash='0xc45aaeab',owner_player_id=4,xyz=[1000,2000,210],observed_frame=1000)},mission_context={})
  self.host.collector=collector
  config=dict(controller_id=uid(),lease_id=uid())
  runtime=types.SimpleNamespace(output=self.root/'controller.json',report={})
  self.reserve=types.SimpleNamespace(config=config,runtime=runtime,closed=False,owns_channel=lambda:True,owns_formation=lambda fid:fid==self.fid,formation=lambda fid:dict(formation_id=fid,version=1,roles={'infantry':1,'anti_air':1},region_id='home_base',available=True),private_formation=lambda fid:dict(version=1,object_ids=[781,784],role='mixed'),hard_deadline=lambda fid:5300)
  async def commit(request,formation,proof,**options):
   self.assertEqual(self.operations[-1][0],'host_commit')
   persisted=json.loads(self.bridge.journal.read_text());entry=persisted[request['task_id']]
   self.assertEqual(entry['expires_frame'],5300)
   self.assertEqual(json.loads(Path(options['public_command_source']).read_text()),request)
   self.assertEqual(formation['formation_id'],self.fid)
   self.operations.append(('publish',copy.deepcopy(request)))
   runtime.report=dict(status='running',mission_request=dict(parent_command_id=str(uuid.UUID(request['command_id'])),parent_task_id=str(uuid.UUID(request['task_id'])),seq=request['seq'],public_command=copy.deepcopy(request)),native=dict(issued_frame=850,controller={'mission_commit_frame':0},mission_commit={'status':0}),progress=None)
  self.reserve.commit=commit;self.host.reserve_controller=self.reserve
  grant=dict(module='combined_arms',purpose='coordinate_force',executor_directory='mission-formation-v13',stop_schema=dict(mission_protocol='continuous_tactical_v1',mission_duration_frames=4500))
  self.bridge=TacticalBridge(self.host,dict(supported_purposes=(('combined_arms',('coordinate_force',)),),grants=[grant]))
  self.bridge.executor=types.SimpleNamespace(update_context=lambda *a:None,submit=lambda *a:self.fail('No worker may spawn for a paid pair'))
 async def asyncTearDown(self):self.temp.cleanup()
 async def test_held_dispatch_preserves_original_deadline_and_persists_before_publication(self):
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']]
  self.assertEqual(entry['expires_frame'],5300);self.assertEqual(entry['object_ids'],[781,784]);self.assertTrue(entry['queued']);self.assertFalse(entry['started'])
  self.assertEqual(self.operations[0][2]['mission_deadline_game_seconds'],5300/15)
 async def test_mf14_grant_uses_the_existing_controller_and_keeps_its_version(self):
  self.bridge.evidence['grants'][0]['executor_directory']='mission-formation-v14'
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']]
  receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(entry['executor_directory'],'mission-formation-v14');self.assertEqual(receipt['executor_directory'],'mission-formation-v14');self.assertEqual(entry['expires_frame'],5300)
 async def test_mf16_grant_keeps_the_paid_controller_route_and_original_hard_deadline(self):
  self.bridge.evidence['grants'][0].update(executor_directory='mission-formation-v16',stop_schema=dict(mission_protocol='continuous_tactical_v1',mission_duration_frames=4500,reserve_duration_frames=450))
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']]
  receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(receipt['executor_directory'],'mission-formation-v16');self.assertEqual(entry['expires_frame'],5300);self.assertFalse(entry['started'])
 async def test_same_task_cannot_publish_twice(self):
  await self.bridge.dispatch();await self.bridge.dispatch();self.assertEqual([r[0] for r in self.operations].count('publish'),1)
 async def test_real_goals_hex_task_id_keeps_its_ledger_key_and_matches_native_uuid(self):
  self.job['task_id']=uuid.uuid4().hex
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']]
  receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(receipt['task_id'],self.job['task_id']);self.assertEqual(len(receipt['task_id']),32)
  self.assertEqual(self.reserve.runtime.report['mission_request']['parent_task_id'],str(uuid.UUID(self.job['task_id'])))
 async def test_agent_dataclass_tuples_are_frozen_as_one_original_json_envelope(self):
  self.job.update(formation_ids=(self.fid,),formation_versions=((self.fid,1),),required_roles=('infantry','anti_air'))
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']]
  original=json.loads(Path(entry['public_command_path']).read_text());runtime_command=self.reserve.runtime.report['mission_request']['public_command']
  self.assertEqual(original,runtime_command);self.assertEqual(runtime_command['formation_ids'],[self.fid]);self.assertEqual(runtime_command['formation_versions'],[[self.fid,1]])
 async def test_an_occupied_controller_blocks_free_tasks_even_before_any_slot_exists(self):
  self.reserve.owns_formation=lambda fid:False
  await self.bridge.dispatch();self.assertEqual(self.operations,[]);self.assertEqual(self.bridge.sent,{})
 async def test_expired_original_hard_bound_does_not_get_renewed(self):
  self.reserve.hard_deadline=lambda fid:999
  await self.bridge.dispatch();self.assertEqual(self.operations,[])
 async def test_outer_borrow_does_not_mean_model_mission_started(self):
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']]
  receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(receipt['issued_frame'],0);self.assertFalse(receipt['started']);self.assertIsNone(receipt['mission'])
  self.reserve.runtime.report['native']['mission_commit']={'status':1};self.reserve.runtime.report['native']['controller']['mission_commit_frame']=1002
  receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(receipt['issued_frame'],1002);self.assertTrue(receipt['started']);self.assertFalse(receipt['completed'])
 async def test_old_or_foreign_mission_ack_is_rejected(self):
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']];raw=self.reserve.runtime.report
  raw['native']['mission_commit']={'status':1};raw['native']['controller']['mission_commit_frame']=900
  with self.assertRaisesRegex(ValueError,'commit_clock'):receipt_for(self.reserve,entry,self.host.binding)
  raw['mission_request']['parent_command_id']=uid()
  with self.assertRaisesRegex(ValueError,'parent_mapping'):receipt_for(self.reserve,entry,self.host.binding)
 async def test_native_finished_before_host_exit_cannot_claim_a_terminal_result(self):
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']];raw=self.reserve.runtime.report
  raw['status']='finished';raw['host_exit']=None
  receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(receipt['status'],'queued');self.assertEqual(receipt['unit_results'],[])
 async def test_partial_effect_is_failed_even_when_control_restoration_succeeded(self):
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']];raw=self.reserve.runtime.report
  raw.update(status='finished',host_exit=0,assessment=dict(combined_arms_verified=False,effect_verified=True,checks={'retreat':False},restoration={'restoration_verified':True}))
  raw['native']['mission_commit']={'status':1};raw['native']['controller']['mission_commit_frame']=1001
  receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(receipt['status'],'failed');self.assertFalse(receipt['goal_observed']);self.assertTrue(receipt['restoration_verified'])
 async def test_seventeen_paired_scene_certificate_stays_one_failed_paired_result(self):
  await self.bridge.dispatch();entry=self.bridge.sent[self.job['task_id']];entry['executor_directory']='mission-formation-v17';raw=self.reserve.runtime.report
  raw.update(status='finished',host_exit=9,assessment=dict(combined_arms_verified=True,checks={'cached':True},restoration={'restoration_verified':True}))
  raw['native']['mission_commit']={'status':1};raw['native']['controller']['mission_commit_frame']=1001
  proof=dict(scene_disposed_control_release=True,sidecar_path='software-scene.json',sidecar_sha256='a'*64,**{k:False for k in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')})
  self.reserve.record={'scene_release':proof};receipt=receipt_for(self.reserve,entry,self.host.binding)
  self.assertEqual(receipt['status'],'failed');self.assertFalse(receipt['completed']);self.assertFalse(receipt['goal_observed']);self.assertFalse(receipt['restoration_verified']);self.assertFalse(receipt['execution']['restoration_verified'])
  self.assertTrue(receipt['scene_disposed_control_release_verified']);self.assertEqual(len(receipt['unit_results']),1);self.assertEqual(receipt['unit_results'][0]['object_ids'],[781,784]);self.assertEqual(receipt['unit_results'][0]['scene_release'],proof)
  self.reserve.record['scene_release']['return_verified']=True
  with self.assertRaises(ValueError):receipt_for(self.reserve,entry,self.host.binding)

if __name__=='__main__':unittest.main()
