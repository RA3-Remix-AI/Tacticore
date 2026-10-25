"""Real worker failure aggregation with fake child and read-only collector only."""
import importlib.abc,importlib.util,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import MagicMock,patch
import client
HERE=Path(__file__).resolve().parent
class DisposalDispatchTests(unittest.TestCase):
 def run_case(self,released):
  raw=json.loads((HERE/'../acceptance/runs/20261025-010403-commander/ordered-ak03-static.json').read_text(encoding='utf-8'));raw['native'].update(phase=4,error=32,return_calls=0,return_verified=0)
  with tempfile.TemporaryDirectory() as folder:
   e=client.TacticalExecutor('unused','unused',raw['preflight']['commander_id']);e.session=dict(session_id=raw['session_id'],pid=raw['preflight']['pid']);e.run=Path(folder);e._binding=lambda:None;e._validate_task_dispatch=lambda r:None;e._audit=lambda value:e.stopping.set() if value.get('event')=='task_feedback' else None
   command=str(uuid.uuid4());task=str(uuid.uuid4());oid=raw['preflight']['selected']['object_id'];r=dict(command_id=command,task_id=task,object_ids=[oid],unit_results=[],executor_directory='ordered-attack',kind='attack',module='attack',purpose='main_attack',target_contact_id=raw['request']['target_contact_id'],visibility_proof_path='unused',dispatch_attempted=False,restoration_verified=False,goal_observed=False,started=False,issued_frame=0,expires_frame=raw['native']['issued_frame']+600);e.ledger[command]=r;e.pending.put(command);e.reserved_units={oid};original_spec=importlib.util.spec_from_file_location
   class Loader(importlib.abc.Loader):
    def create_module(self,spec):return None
    def exec_module(self,module):module.collect=lambda *args,**kwargs:dict(restoration_verified=released,control_release_verified=released,disposed_verified=released,return_verified=False,completion_claim=False,semantics='actor_id_disposed_exclusive_control_released' if released else 'unknown',evidence_path='fake.disposal.json',evidence_sha256='fake')
   def spec(name,path,*args,**kwargs):return importlib.util.spec_from_loader(name,Loader()) if name=='tactical_readonly_disposal' else original_spec(name,path,*args,**kwargs)
   def child(args,**kwargs):
    raw['request'].update(command_id=args[args.index('--command-id')+1],task_id=args[args.index('--task-id')+1],seq=int(args[args.index('--seq')+1]));raw['native'].update(command_id=raw['request']['command_id'],task_id=raw['request']['task_id'],seq=raw['request']['seq']);Path(args[args.index('--output')+1]).write_text(json.dumps(raw),encoding='utf-8');p=MagicMock();p.poll.return_value=0;p.returncode=0;return p
   with patch.object(client.importlib.util,'spec_from_file_location',side_effect=spec),patch.object(client.subprocess,'Popen',side_effect=child):e._work()
   return r,e.reserved_units
 def test_disposed_remains_failed_but_releases_reservation(self):
  r,reserved=self.run_case(True);self.assertEqual(r['status'],'failed');self.assertFalse(r['completed']);self.assertFalse(r['goal_observed']);self.assertTrue(r['restoration_verified']);self.assertFalse(reserved);self.assertFalse(r['unit_results'][0]['control_release']['return_verified'])
 def test_unproven_death_remains_quarantined(self):
  r,reserved=self.run_case(False);self.assertFalse(r['restoration_verified']);self.assertTrue(reserved);self.assertFalse(r['completed'])
if __name__=='__main__':unittest.main()
