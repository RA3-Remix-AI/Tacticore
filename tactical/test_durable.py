import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('durable_backend',Path(__file__).parent/'reusable/lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class DurableTest(unittest.TestCase):
 def test_transient_windows_reader_lock_is_retried(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
   path=Path(folder)/'report.json';original=Path.replace;calls=[]
   def replace(source,target):
    calls.append(1)
    if len(calls)<3:raise PermissionError('simulated Windows sharing violation')
    return original(source,target)
   with patch.object(Path,'replace',replace),patch.object(m.time,'sleep') as sleep:m.durable(path,{'event':'complete'})
   self.assertEqual(json.loads(path.read_text()),{'event':'complete'});self.assertEqual(sleep.call_count,2)
 def test_permanent_lock_is_bounded_and_preserves_prior_evidence(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
   path=Path(folder)/'report.json';path.write_text('{"event":"prior"}')
   with patch.object(Path,'replace',side_effect=PermissionError('locked')),patch.object(m.time,'sleep') as sleep:
    with self.assertRaises(PermissionError):m.durable(path,{'event':'new'})
   self.assertEqual(json.loads(path.read_text()),{'event':'prior'});self.assertEqual(sleep.call_count,24)
if __name__=='__main__':unittest.main()
