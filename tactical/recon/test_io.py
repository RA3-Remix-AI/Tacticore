import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('recon_io_backend',ROOT/'lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
class IOTests(unittest.TestCase):
 def test_atomic_replace_retries_permission_lock(self):
  original=Path.replace;attempts=[]
  def locked_then_ok(src,dst):
   attempts.append(1)
   if len(attempts)<3:raise PermissionError('reader briefly owns file')
   return original(src,dst)
  with tempfile.TemporaryDirectory(prefix='io-test-',dir=ROOT) as d:
   p=Path(d)/'out.json'
   with patch.object(Path,'replace',locked_then_ok),patch.object(b.time,'sleep') as sleep:b.durable(p,{'value':3})
   self.assertEqual(json.loads(p.read_text()),{'value':3});self.assertEqual(len(attempts),3);self.assertEqual(sleep.call_count,2)
 def test_atomic_replace_has_finite_retry_bound(self):
  with tempfile.TemporaryDirectory(prefix='io-test-',dir=ROOT) as d:
   with patch.object(Path,'replace',side_effect=PermissionError('locked')) as replace,patch.object(b.time,'sleep'):
    with self.assertRaises(PermissionError):b.durable(Path(d)/'out.json',{'value':3})
    self.assertEqual(replace.call_count,40)
if __name__=='__main__':unittest.main()
