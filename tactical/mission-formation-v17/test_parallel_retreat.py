"""Original C++ pose replay is a component proof, never SDK or field Source."""
import copy,hashlib,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf17_parallel_test',HERE/'formation_mission_qualification.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

class ParallelRetreat(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=HERE/'simulation-2km-native.json';cls.original=cls.path.read_bytes();cls.report=json.loads(cls.original)
 def fixture(self):return copy.deepcopy(self.report['events'])
 def rows(self,ev):return [e for e in ev if e['kind']==169]
 def rejected(self,ev):
  try:self.assertFalse(q.parallel_geometry_audit(ev)['verified'])
  except (KeyError,ValueError,IndexError,TypeError):pass
 def test_actual_cpp_trace_replays_without_source_credit(self):
  out=q.parallel_geometry_audit(self.report['events']);self.assertTrue(out['verified'],out)
  self.assertTrue(all(v>120 for v in out['actual_paths']));self.assertFalse(out['source_authority_granted']);self.assertFalse(out['completion_claim'])
  self.assertEqual(q.qualify(self.report)['status'],'not_passed');self.assertFalse(q.source_pins(self.report));self.assertEqual(self.path.read_bytes(),self.original)
 def test_first_pair_may_equal_retreat_start_with_zero_predecision_masks(self):
  ev=self.fixture();start=next(e['frame'] for e in ev if e['kind']==89)
  for e in self.rows(ev)[:2]:e['frame']=start;e['stack_words'][3]=start;e['stack_words'][34]=start
  self.assertTrue(q.parallel_geometry_audit(ev)['verified'])
 def test_first_equal_frame_does_not_allow_motion13(self):
  ev=self.fixture();start=next(e['frame'] for e in ev if e['kind']==89)
  for e in self.rows(ev)[:2]:e['frame']=start;e['arg']=13;e['stack_words'][3]=start;e['stack_words'][4]=13;e['stack_words'][34]=start
  self.rejected(ev)
 def test_middle_duplicate_frame_rejected(self):
  ev=self.fixture();rows=self.rows(ev)
  for e in rows[8:10]:e['frame']=rows[6]['frame'];e['stack_words'][3]=e['frame'];e['stack_words'][34]=e['frame']
  self.rejected(ev)
 def test_missing_role_snapshot_rejected(self):
  ev=self.fixture();ev.remove(self.rows(ev)[1]);self.rejected(ev)
 def test_changed_private_home_rejected(self):
  ev=self.fixture();self.rows(ev)[8]['stack_words'][10]^=0x00800000;self.rejected(ev)
 def test_reset_hard_deadline_rejected(self):
  ev=self.fixture();self.rows(ev)[8]['stack_words'][9]+=1;self.rejected(ev)
 def test_fabricated_gap_or_minimum_rejected(self):
  for index in (28,29):
   ev=self.fixture();self.rows(ev)[8]['stack_words'][index]=0;self.rejected(ev)
 def test_after_decision_mask_cannot_replace_prior_mask(self):
  ev=self.fixture();self.rows(ev)[0]['stack_words'][5]=3;self.rejected(ev)
 def test_arrival_count_cannot_be_inferred_from_ack(self):
  ev=self.fixture();self.rows(ev)[8]['stack_words'][17]=3;self.rejected(ev)
 def test_no_home_marker_no_completion(self):
  self.rejected([e for e in self.fixture() if not(e['kind']==91 and e['role']==1)])
 def test_duplicate_home_move_rejected(self):
  ev=self.fixture();ev.append(copy.deepcopy(next(e for e in ev if e['kind']==168)));self.rejected(ev)
 def test_explicit_payload_padding_rejected(self):
  ev=self.fixture();self.rows(ev)[0]['stack_words'][127]=1;self.rejected(ev)
 def test_snapshot_is_not_published_trail_credit(self):
  ev=self.fixture();self.rows(ev)[0]['stack_words'][35]=123;self.rejected(ev)
 def test_new_scene_reader_is_exact_source_dependency(self):
  paths=q.source_paths();self.assertIn(HERE/'scene_terminal_release.py',paths);self.assertEqual(len(paths),len({p.name for p in paths}))

if __name__=='__main__':unittest.main()
