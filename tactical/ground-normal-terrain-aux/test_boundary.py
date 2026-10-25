import ctypes as c,json,tempfile,unittest
from pathlib import Path
import lease as b
class Boundary(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'point.json';self.previous=b.own_candidates;b.own_candidates=lambda *a:{'candidates':[]};self.pre={'frame':20,'selected':{'object_id':1,'xyz':[0,0,210]}};self.session={'session_id':'test','pid':10};self.source={'session_id':'test','pid':10,'player_id':3,'logic_frame_candidate':10,'own_objects':[{'object_id':2,'type_hash':'0x19ab11af','hp':100,'xyz':[50,0,210]}]}
 def tearDown(self):b.own_candidates=self.previous;self.tmp.cleanup()
 def get(self):
  self.path.write_text(json.dumps(self.source),encoding='utf-8');return b.known_point(self.path,2,self.pre,self.session,None)
 def test_previous_actual_own_point(self):self.assertEqual(self.get()['xyz'],[50,0,210])
 def test_other_session(self):
  self.source['session_id']='other'
  with self.assertRaisesRegex(ValueError,'other_session'):self.get()
 def test_observer(self):
  self.source['player_id']=2
  with self.assertRaisesRegex(ValueError,'other_player'):self.get()
 def test_target_height_not_copied(self):
  self.source['own_objects'][0]['xyz'][2]=600
  with self.assertRaisesRegex(ValueError,'height'):self.get()
 def test_current_own_occupant_rejected(self):
  b.own_candidates=lambda *a:{'candidates':[{'object_id':3,'xyz':[49,0,210]}]}
  with self.assertRaisesRegex(ValueError,'occupant'):self.get()
 def test_air_history_rejected(self):
  self.source['own_objects'][0]['type_hash']='0x40acad6d'
  with self.assertRaisesRegex(ValueError,'ground_infantry'):self.get()
 def test_event_nonfinite_diagnostic_only(self):
  e=b.Event();e.requested[0]=float('nan');r=b.event_record(e);self.assertIsNone(r['requested'][0]);json.dumps(r,allow_nan=False)
 def test_terminal_mapping_fresh_copy(self):
  s=b.Tactical();s.phase=3;s.restore_mask=255;s.events[0].seq=1;s.events[0].frame=7;s.count=1;r={};self.assertTrue(b.capture_shared(r,s));self.assertEqual(r['native']['phase'],3);self.assertEqual(r['events'][0]['frame'],7)
if __name__=='__main__':unittest.main()
