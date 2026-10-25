"""Actual MCT6 client branches, fake child/kernel only. No game calls."""
import ctypes as c,json,struct,tempfile,types,unittest,uuid
from pathlib import Path
from unittest.mock import MagicMock,patch
import test_client as boundary
import test_mission_client as mission_boundary
from test_mission_combat_v6 import fixture
m=boundary.m
class Mission6ClientTests(unittest.TestCase):
 def test_public_molotov_queues_early_prepare_policy_with_ground_admission(self):
  helper=mission_boundary.MissionClientTests();e,t,pre,captured=helper.setup_executor();e.capability_grants[('attack','main_attack')]['executor_directory']='mission-combat-v6';e._surface_ground_candidates=MagicMock(side_effect=lambda memory,units,owner:units);r=helper.submit(e,t,pre)
  self.assertTrue(r['accepted'],r);self.assertFalse(r['started']);self.assertEqual(r['executor_directory'],'mission-combat-v6');self.assertEqual(captured[0]['mission_input']['engagement_policy'],'bounded_single_order_native_burst');self.assertEqual(captured[0]['mission_input']['engage_frames'],300);e._surface_ground_candidates.assert_called_once()
 def test_actual_single_worker_uses_v6_and_recomputes_raw_qualification(self):
  raw=fixture()
  with tempfile.TemporaryDirectory() as folder:
   e=m.TacticalExecutor('unused','unused',raw['preflight']['commander_id']);e.session={'session_id':raw['session_id'],'pid':raw['preflight']['pid']};e.run=Path(folder);e.native_seq=100;e._binding=lambda:None;e._validate_task_dispatch=lambda r:None
   command=str(uuid.uuid4());task=str(uuid.uuid4());r=dict(kind='attack',module='attack',purpose='main_attack',executor_directory='mission-combat-v6',command_id=command,task_id=task,object_ids=[raw['preflight']['selected']['object_id']],status='queued',unit_results=[],started=False,issued_frame=0,dispatch_attempted=False,wrapper_attempted=False,visibility_proof_path='unused',target_contact_id=raw['request']['target_contact_id'],mission_input=raw['request']['mission'],expires_frame=4599);e.ledger[command]=r;e.pending.put(command);seen=[]
   def audit(event):
    if event['event']=='task_feedback':e.stopping.set()
   e._audit=audit
   def spawn(args,**kwargs):
    seen.extend(args);value=lambda flag:args[args.index(flag)+1];rq=dict(command_id=value('--command-id'),task_id=value('--task-id'),seq=int(value('--seq')));raw['request'].update(rq);raw['native'].update(rq);raw['assessment']={'status':'not_passed','checks':{'old_diagnostic_only':False}};Path(value('--output')).write_text(json.dumps(raw),encoding='utf-8');return types.SimpleNamespace(poll=lambda:0,returncode=0)
   with patch.object(m.subprocess,'Popen',side_effect=spawn):e._work()
   self.assertEqual(Path(seen[1]).resolve(),Path(__file__).resolve().parent/'mission-combat-v6/lease.py');self.assertTrue(r['completed'],r);self.assertTrue(r['started']);self.assertTrue(r['unit_results'][0]['assessment']['sustained_engagement_verified']);self.assertEqual(r['unit_results'][0]['assessment']['observed_reload_count'],1)
 def test_active_retreat_uses_v6_mapping_and_real_new_layout(self):
  raw=fixture();schema,runtime=m.runtime_backend('mission-combat-v6');shared=runtime.Tactical();rq=raw['request'];shared.pid=raw['preflight']['pid'];shared.token=rq['token'];shared.seq=rq['seq'];shared.phase=1
  for field,value in [('session',raw['session_id']),('commander',raw['preflight']['commander_id']),('command',rq['command_id']),('task',rq['task_id'])]:getattr(shared,field)[:]=struct.unpack('<4I',uuid.UUID(value).bytes)
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'raw.json';path.write_text(json.dumps(raw),encoding='utf-8');e=m.TacticalExecutor('unused','unused',raw['preflight']['commander_id']);e.session={'session_id':raw['session_id'],'pid':shared.pid};cmd=str(uuid.uuid4());e.active=cmd;e.ledger[cmd]=dict(command_id=cmd,task_id=rq['task_id'],status='started',object_ids=[804],executor_directory='mission-combat-v6',active_report=str(path));kernel=MagicMock();kernel.OpenFileMappingW.return_value=1;kernel.MapViewOfFile.return_value=c.addressof(shared)
   with patch.object(m.backend,'k',kernel):result=e.request_mission_retreat(rq['task_id'])
   self.assertTrue(result['accepted']);self.assertEqual(shared.retreat_requested,1);self.assertEqual(shared.stop_requested,0);self.assertIn('RA3TacticalMissionCombat6_',kernel.OpenFileMappingW.call_args.args[2])
if __name__=='__main__':unittest.main()
