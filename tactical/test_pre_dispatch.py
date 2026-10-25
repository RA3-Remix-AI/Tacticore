"""Real wrapper entrypoint boundary, fake main; no native process launch."""
import argparse,copy,importlib.util,json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import pre_dispatch_contract as q
HERE=Path(__file__).resolve().parent
class PreDispatchTests(unittest.TestCase):
 def fixture(self,folder):
  session=dict(session_id=str(uuid.uuid4()),pid=1234,mod_sha256='package',scenario=dict(commander_id='57e668b4-4d89-43bd-bc92-0dd436f046ef'));p=Path(folder);sp=p/'session.json';sp.write_text(json.dumps(session));args=argparse.Namespace(session=sp,command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=100,object_id=8,contact_id='contact_target',output=p/'report.json',execute=True)
  return session,args
 def verify(self,r,s,a,code=64):return q.verify_no_dispatch(r,child_exit_code=code,session=s,commander_id=s['scenario']['commander_id'],command_id=a.command_id,task_id=a.task_id,seq=a.seq,object_ids=[8],directory='mission-combat',target_contact_id=a.contact_id)
 def test_preflight_rejection_is_bound_but_never_completion(self):
  with tempfile.TemporaryDirectory() as f:
   s,a=self.fixture(f);r=q.rejection(a,HERE/'mission-combat',ValueError('current_visible_target_required'));v=self.verify(r,s,a);self.assertTrue(v['no_dispatch_verified']);self.assertFalse(v['completion_claim']);self.assertFalse(v['restoration_verified'])
 def test_unknown_child_exit_is_not_no_dispatch(self):
  with tempfile.TemporaryDirectory() as f:
   s,a=self.fixture(f);r=q.rejection(a,HERE/'mission-combat',ValueError('no_route'));self.assertFalse(self.verify(r,s,a,1)['no_dispatch_verified'])
 def test_any_possible_launch_or_native_state_rejected(self):
  with tempfile.TemporaryDirectory() as f:
   s,a=self.fixture(f);original=q.rejection(a,HERE/'mission-combat',ValueError('no_route'))
   for key,value in [('native_launch_intent_persisted',True),('native',{'phase':0}),('events',[{'kind':0}]),('host_exit',0),('wrapper_sha256','wrong')]:
    r=copy.deepcopy(original);r[key]=value;self.assertFalse(self.verify(r,s,a)['no_dispatch_verified'],key)
 def test_wrong_command_actor_or_contact_rejected(self):
  with tempfile.TemporaryDirectory() as f:
   s,a=self.fixture(f);original=q.rejection(a,HERE/'mission-combat',ValueError('no_route'))
   for key,value in [('command_id',str(uuid.uuid4())),('object_ids',[9]),('target_contact_id','contact_other')]:
    r=copy.deepcopy(original);r['request'][key]=value;self.assertFalse(self.verify(r,s,a)['no_dispatch_verified'])
 def test_unowned_original_report_never_rewritten(self):
  with tempfile.TemporaryDirectory() as f:
   s,a=self.fixture(f);a.output.write_text('original evidence')
   with self.assertRaises(ValueError):q.rejection(a,HERE/'mission-combat',ValueError('no_route'))
   self.assertEqual(a.output.read_text(),'original evidence')
 def test_actual_entrypoint_uses_exit64_only_before_intent(self):
  spec=importlib.util.spec_from_file_location('tested_mission_entrypoint',HERE/'mission-combat/lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as f:
   s,a=self.fixture(f);m.CLI_ARGS=a
   with patch.object(m,'main',side_effect=ValueError('no_route')):
    with self.assertRaises(SystemExit) as stop:m.entrypoint()
    self.assertEqual(stop.exception.code,64)
   self.assertTrue(self.verify(json.loads(a.output.read_text()),s,a)['no_dispatch_verified'])
   a.output.unlink();m.NATIVE_LAUNCH_INTENT=True
   with patch.object(m,'main',side_effect=ValueError('native_may_have_started')):
    with self.assertRaisesRegex(ValueError,'native_may_have_started'):m.entrypoint()
   self.assertFalse(a.output.exists())
if __name__=='__main__':unittest.main()
