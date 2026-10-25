import ctypes as c,importlib.util,json,math,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('ordered_serialization',Path(__file__).parent/'ordered-attack/lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class SerializationTests(unittest.TestCase):
 def test_all_actual_ctypes_arrays_become_lists(self):
  e=m.Event();e.requested[:]=[1.,2.,3.];e.effective[:]=[4.,5.,6.];r=m.event_record(e);encoded=json.dumps(r,allow_nan=False);decoded=json.loads(encoded)
  for name,typ in m.Event._fields_:
   if issubclass(typ,c.Array):self.assertIsInstance(decoded[name],list)
  self.assertEqual(decoded['requested'],[1.,2.,3.]);self.assertEqual(decoded['effective'],[4.,5.,6.])
 def test_nonfinite_diagnostics_are_null_and_marked(self):
  e=m.Event();e.requested[0]=math.nan;e.effective[1]=math.inf;r=m.event_record(e);json.dumps(r,allow_nan=False);self.assertIsNone(r['requested'][0]);self.assertIsNone(r['effective'][1]);self.assertIn('requested[0]',r['invalid_float_fields']);self.assertIn('effective[1]',r['invalid_float_fields'])
 def test_target_request_json_remains_strict(self):
  with self.assertRaises(ValueError):json.dumps({'target':[math.nan,0.,0.]},allow_nan=False)
 def test_terminal_snapshot_replaces_stale_phase(self):
  s=m.Tactical();s.count=1;s.events[0].seq=1;s.events[0].requested[:]=[0.,0.,0.];r={'native':{'phase':0}};m.capture_shared(r,s);self.assertEqual(r['native']['phase'],0);s.phase=4;s.error=33;s.restore_mask=2047;s.active=0;m.capture_shared(r,s);self.assertEqual(r['native']['phase'],4);self.assertEqual(r['native']['error'],33);self.assertEqual(r['status'],'finished');json.dumps(r,allow_nan=False)
 def test_unpublished_event_not_serialized(self):
  s=m.Tactical();s.count=1;s.events[0].seq=0;r={};m.capture_shared(r,s);self.assertEqual(r['events'],[])
if __name__=='__main__':unittest.main()
