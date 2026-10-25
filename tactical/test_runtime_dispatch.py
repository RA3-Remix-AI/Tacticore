"""Offline fake child/kernel checks: no game process, hooks, or SDK calls."""
import copy,ctypes as c,hashlib,importlib.util,json,sys,tempfile,threading,unittest,uuid
from pathlib import Path
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import client as m
class RuntimeDispatchTests(unittest.TestCase):
 def fixture(self):return json.loads((ROOT/'../acceptance/runs/20261024-234355-commander/formation-stop-v2-03.json').read_text(encoding='utf-8'))
 def fake(self,folder):
  raw=self.fixture();e=m.TacticalExecutor('unused','unused',raw['preflight']['commander_id']);e.session={'session_id':raw['session_id'],'pid':123};e.run=Path(folder);e.native_seq=100;e._binding=lambda:None;e._validate_task_dispatch=lambda r:None;e._audit=lambda r:None
  cmd=str(uuid.uuid4());r=dict(command_id=cmd,task_id=str(uuid.uuid4()),object_ids=[u['id'] for u in raw['units']],unit_results=[],executor_directory='formation-stop-v2',dx=-40.,dy=-40.,rear_spacing=56.5685424949,started=False,issued_frame=0);e.ledger[cmd]=r
  return raw,e,cmd,r
 def dispatch(self,mask=None):
  with tempfile.TemporaryDirectory() as folder:
   raw,e,cmd,r=self.fake(folder);seen=[]
   def spawn(args,**kwargs):
    raw['preflight']['pid']=e.session['pid'];seen.extend(args);p=Path(args[args.index('--output')+1]);command=args[args.index('--command-id')+1];task=args[args.index('--task-id')+1];seq=int(args[args.index('--seq')+1]);raw['native'].update(command_id=command,task_id=task,seq=seq);raw['request'].update(command_id=command,task_id=task,seq=seq)
    if mask is not None:raw['native']['restore_mask']=mask
    p.write_text(json.dumps(raw),encoding='utf-8');child=MagicMock();child.poll.return_value=0;child.returncode=0;return child
   with patch.object(m.subprocess,'Popen',side_effect=spawn):
    if mask==31:
     with self.assertRaises(ValueError):e._execute_formation(cmd,r)
    else:e._execute_formation(cmd,r)
   return seen,r
 def test_real_worker_uses_stop2_script_and_mask(self):
  args,r=self.dispatch();self.assertEqual(Path(args[1]).resolve(),ROOT/'formation-stop-v2/lease.py');self.assertTrue(r['completed']);self.assertTrue(r['restoration_verified']);self.assertEqual(r['unit_results'][0]['expected_restore_mask'],127)
 def test_old_restore31_cannot_complete_new_executor(self):
  _,r=self.dispatch(31);self.assertFalse(r.get('completed',False));self.assertFalse(r['unit_results'][0]['batch_restoration']['restoration_verified'])
 def test_stop_uses_exact_new_mapping_and_layout(self):
  with tempfile.TemporaryDirectory() as folder:
   raw,e,cmd,r=self.fake(folder);path=Path(folder)/'report.json';path.write_text(json.dumps(raw),encoding='utf-8');r['active_report']=str(path);e.active=cmd;schema,runtime=m.runtime_backend('formation-stop-v2');shared=runtime.Tactical();shared.token=raw['request']['token'];shared.pid=123
   kernel=MagicMock();kernel.OpenFileMappingW.return_value=1;kernel.MapViewOfFile.return_value=c.addressof(shared)
   with patch.object(m.backend,'k',kernel):e._request_native_stop(path)
   self.assertEqual(shared.stop_requested,1);name=kernel.OpenFileMappingW.call_args.args[2];self.assertEqual(name,'Local\\RA3TacticalFormationStop2_123_'+str(shared.token))
 def test_grant_directory_drift_rejects_before_child(self):
  with tempfile.TemporaryDirectory() as folder:
   _,e,cmd,r=self.fake(folder);del e._validate_task_dispatch;e._binding=lambda:None;r.update(module='combined_arms',purpose='coordinate_force');e.capability_grants[('combined_arms','coordinate_force')]={'executor_directory':'formation'}
   with self.assertRaisesRegex(ValueError,'executor_grant_binding_changed'):e._validate_task_dispatch(r)
 def test_grant_binary_drift_rejects_before_child(self):
  with tempfile.TemporaryDirectory() as folder:
   _,e,cmd,r=self.fake(folder);del e._validate_task_dispatch;e._binding=lambda:None;r.update(module='combined_arms',purpose='coordinate_force');e.capability_grants[('combined_arms','coordinate_force')]=dict(executor_directory='formation-stop-v2',native_binary_sha256='wrong',native_host_sha256='wrong')
   with self.assertRaisesRegex(ValueError,'executor_revision_changed'):e._validate_task_dispatch(r)
if __name__=='__main__':unittest.main()
