"""Raw MF7 publication only; synthetic events never confer movement evidence."""
import ctypes as c
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mf7_raw_bootstrap_wrapper',H/'lease.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class Capture(unittest.TestCase):
 def fixture(self):
  n=w.Tactical();n.count=3;n.crumb_count[1]=21
  crumb=n.crumbs[1][20];crumb.index=20;crumb.published_seq=1;crumb.role=1;crumb.mission_stage=3;crumb.frame=100;crumb.xyz[:]=[1790,1870,210]
  for i,kind in enumerate((80,98,99)):
   e=n.events[i];e.seq=i+1;e.kind=kind;e.role=1;e.frame=100+i;e.mission_stage=3;e.breadcrumb=crumb;e.argument_path=100;e.argument_limit=249.2;e.actual_gap=249.2;e.arg=1 if kind==99 else 0
  return n,dict(request=dict(task_id='00000000-0000-0000-0000-000000000001'),events=[])
 def test98_99_echo_original_nonzero_index_and_published_seq_without_new_trail(self):
  n,r=self.fixture();before=bytes(n.crumbs)
  with patch.object(w,'progress',return_value=None):w.capture(r,n)
  self.assertEqual([e['kind'] for e in r['events']],[80,98,99]);self.assertEqual(len(r['native']['crumbs'][1]),21)
  for e in r['events'][1:]:self.assertEqual((e['breadcrumb']['index'],e['breadcrumb']['published_seq'],e['argument_path']),(20,1,100))
  self.assertEqual(bytes(n.crumbs),before);self.assertEqual(r['native']['crumbs'][1][20]['xyz'],[1790,1870,210])
 def test_diagnostics_preserve_real_unknown_gap_instead_of_default_zero(self):
  n,r=self.fixture();n.events[1].argument_limit=float('nan')
  with patch.object(w,'progress',return_value=None):w.capture(r,n)
  self.assertIsNone(r['events'][1]['argument_limit']);self.assertIn('event.argument_limit',r['events'][1]['invalid_float_fields'])
 def test_unpublished99_cannot_be_promoted_by_header_or_polled_twice(self):
  n,r=self.fixture();n.events[2].seq=0
  with patch.object(w,'progress',return_value=None):
   w.capture(r,n);self.assertEqual(len(r['events']),2)
   n.events[2].seq=3;w.capture(r,n);self.assertEqual(len(r['events']),3)
   w.capture(r,n);self.assertEqual(len(r['events']),3)
if __name__=='__main__':unittest.main()
