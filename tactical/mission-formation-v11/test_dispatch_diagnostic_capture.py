"""New dispatcher observations remain raw evidence, never command credit."""
import importlib.util,json,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mfm11_diagnostic_capture',H/'lease.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class DispatchDiagnosticCapture(unittest.TestCase):
 def test_before_and_after_keep_all_words_without_retagging(self):
  for kind in (124,125):
   with self.subTest(kind=kind):
    e=w.Event();e.seq=7;e.kind=kind;e.tag=0;e.source=0;e.role=0;e.stack_word_count=128
    values=[(0xfedcba98+i)&0xffffffff for i in range(128)];e.stack_words[:]=values
    r=json.loads(json.dumps(w.event_record(e),allow_nan=False))
    self.assertEqual((r['kind'],r['tag'],r['source'],r['stack_word_count']),(kind,0,0,128))
    self.assertEqual(r['stack_words'],values)
    self.assertNotIn('lineage',r)
    self.assertNotIn('command_authorized',r)
    self.assertNotIn('completed',r)
 def test_nonzero_lineage_is_not_dropped_from_diagnostic_event(self):
  e=w.Event();e.kind=125;e.lineage.generation=9;e.lineage.observed_command=0xf1234567
  r=w.event_record(e)
  self.assertEqual(r['lineage']['generation'],9)
  self.assertEqual(r['lineage']['observed_command'],0xf1234567)
if __name__=='__main__':unittest.main()
