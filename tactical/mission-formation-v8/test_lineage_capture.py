"""MF8 typed raw output only; synthetic lineage never authorizes SDK actions."""
import ctypes as c
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mf8_lineage_capture_wrapper',H/'lease.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class RawLineage(unittest.TestCase):
 def fixture(self):
  n=w.Tactical();n.count=1;e=n.events[0];e.seq=1;e.kind=117;e.tag=0;e.role=1
  e.lineage.generation=4;e.lineage.step=7;e.lineage.role=1;e.lineage.delivered=1;e.lineage.slot=0x100000;e.lineage.input_command=0x200000;e.lineage.output_command=0x300000;e.lineage.goal[:]=[123,456,210];e.lineage.observed_this=0x100000;e.lineage.observed_thing=0x400000;e.lineage.observed_command=0x300000
  for name in ('command','stored_before','stored_after','unpacked','observed_slot'):
   array=getattr(e.lineage,name)
   for i in range(len(array)):array[i]=0x3f800000+i
  return n,dict(events=[],request=dict(task_id='00000000-0000-0000-0000-000000000001'))
 def test_actual_typed_tail_offsets_and_size_are_explicit(self):
  self.assertEqual(c.sizeof(w.MoveLineage),568);self.assertEqual(w.Event.lineage.offset,1048);self.assertEqual(c.sizeof(w.Event),1616);self.assertEqual(w.Tactical.events.offset,27900);self.assertEqual(c.sizeof(w.Tactical),13266172)
  self.assertEqual([(name,getattr(w.MoveLineage,name).offset) for name in ('goal','command','stored_before','stored_after','unpacked','observed_slot')],[('goal',72),('command',84),('stored_before',176),('stored_after',272),('unpacked',368),('observed_slot',460)])
 def test_all_current_slot_and_copy_snapshots_remain_distinct_raw_arrays(self):
  n,r=self.fixture();n.events[0].lineage.observed_slot[0]=0xffffffff
  with patch.object(w,'progress',return_value=None):w.capture(r,n)
  proof=r['events'][0]['lineage'];self.assertEqual(proof['observed_slot'][0],0xffffffff);self.assertNotEqual(proof['stored_after'][0],proof['observed_slot'][0]);self.assertEqual([len(proof[k]) for k in ('command','stored_before','stored_after','unpacked','observed_slot')],[23,24,24,23,24]);self.assertEqual(proof['generation'],4);self.assertEqual(proof['slot'],0x100000);self.assertEqual(proof['observed_this'],0x100000);self.assertEqual(proof['observed_thing'],0x400000);self.assertEqual(proof['observed_command'],0x300000)
 def test_capture_does_not_retag_late_delivery_as_synchronous_own_call(self):
  n,r=self.fixture()
  with patch.object(w,'progress',return_value=None):w.capture(r,n)
  self.assertEqual(r['events'][0]['tag'],0);self.assertEqual(r['events'][0]['lineage']['delivered'],1)
 def test_ordinary_zero_sample_and_breadcrumb_do_not_expand_empty_proof(self):
  for kind in (3,80,81,98,99):
   event=w.Event();event.kind=kind;event.seq=1;record=w.event_record(event)
   self.assertNotIn('lineage',record);self.assertIn('breadcrumb',record)
 def test_explicit_zero_proof_is_kept_for_strict_qualifier_rejection(self):
  for kind in w.LINEAGE_PROOF_KINDS:
   event=w.Event();event.kind=kind;record=w.event_record(event)
   self.assertIn('lineage',record);self.assertEqual(len(record['lineage']['observed_slot']),24);self.assertEqual(record['lineage']['generation'],0)
 def test_nonproof_private_with_any_real_or_corrupt_tail_keeps_all_fields(self):
  for kind in (3,10,11,80):
   event=w.Event();event.kind=kind;event.tag=0;event.lineage.observed_slot[23]=0x80000000;record=w.event_record(event)
   self.assertIn('lineage',record);self.assertEqual(record['lineage']['observed_slot'][23],0x80000000);self.assertEqual(record['tag'],0);self.assertEqual(len(record['lineage']['command']),23)
 def test_nonfinite_goal_is_unknown_but_raw_bit_arrays_never_coerced(self):
  n,r=self.fixture();n.events[0].lineage.goal[0]=float('nan');n.events[0].lineage.command[0]=0x7fc00000
  with patch.object(w,'progress',return_value=None):w.capture(r,n)
  event=r['events'][0];self.assertIsNone(event['lineage']['goal'][0]);self.assertIn('event.lineage.goal[0]',event['invalid_float_fields']);self.assertEqual(event['lineage']['command'][0],0x7fc00000)
if __name__=='__main__':unittest.main()
