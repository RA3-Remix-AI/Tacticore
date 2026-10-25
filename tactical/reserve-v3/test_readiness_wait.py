"""Retry only harmless preflight windows; never retry Native or hide a binding fault."""
import importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('rsv3_readiness_tests',HERE/'lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Readiness(unittest.TestCase):
 def setup_paths(self,folder,wait):
  path=Path(folder);birth=path/'birth.json';birth.write_text('{}');session=path/'session.json';session.write_text('{}')
  args=types.SimpleNamespace(wait_ready_seconds=wait,session=session,commander='commander',actor_id=7,output=path/'out.json',command_id='command',task_id='task',seq=1)
  return args,dict(path=str(birth),sha256=m.sha(birth))
 def test_exhaustion_records_no_native_boundary_and_never_launches(self):
  with tempfile.TemporaryDirectory() as folder:
   args,birth=self.setup_paths(folder,0)
   with patch.object(m.preflight,'current_selection',side_effect=ValueError('reserve_requires_one_current_paid_actor')),patch.object(m.subprocess,'Popen',side_effect=AssertionError('No Native process')):
    with self.assertRaisesRegex(ValueError,'no_native'):m.current_selection_with_wait(args,birth)
   result=json.loads(args.output.read_text());self.assertEqual(result['sdk_calls'],0)
   self.assertFalse(result['native_host_started']);self.assertFalse(result['native_launch_intent_persisted'])
 def test_transient_then_ready_returns_original_live_handle_without_host(self):
  with tempfile.TemporaryDirectory() as folder:
   args,birth=self.setup_paths(folder,1);handle=object();ready=(1,2,3,4,5,6,7,handle)
   with patch.object(m.preflight,'current_selection',side_effect=[ValueError('reserve_requires_one_current_paid_actor'),ready]),patch.object(m.time,'sleep'),patch.object(m.subprocess,'Popen',side_effect=AssertionError('No Native process')):
    result=m.current_selection_with_wait(args,birth)
   self.assertIs(result[-1],handle);self.assertEqual(len(args.readiness_attempts),1);self.assertFalse(args.output.exists())
 def test_entry_or_binding_failure_is_never_retried(self):
  with tempfile.TemporaryDirectory() as folder:
   args,birth=self.setup_paths(folder,1)
   with patch.object(m.preflight,'current_selection',side_effect=ValueError('probe_entry_not_original')) as read:
    with self.assertRaisesRegex(ValueError,'entry_not_original'):m.current_selection_with_wait(args,birth)
   self.assertEqual(read.call_count,1);self.assertFalse(args.output.exists())

if __name__=='__main__':unittest.main()
