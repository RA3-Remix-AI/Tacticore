import copy,unittest
from lease import assessment
class AssessmentTests(unittest.TestCase):
 def good(self):
  pre=dict(owner=hex(0x10000),ai=hex(0x20000),default_team=hex(0x30000),script_team=hex(0x40000))
  native=dict(phase=3,restore_mask=31,active=0,error=0,detach_calls=1,move_calls=1,return_calls=1,arrival_samples=3,return_verified=1,lifecycle_fail=0,overflow=0,issued_frame=100,returned_frame=150)
  events=[]
  for kind,tag,caller,arg,frame,team in [(18,1,0x838877,0x20104,100,0x40000),(19,1,0,0x20104,100,0x40000),(3,0,0,0,110,0x40000),(16,3,0x83885b,0x20104,150,0x30000),(17,3,0,0x20104,150,0x30000),(3,0,0,0,180,0x30000)]:events.append(dict(kind=kind,tag=tag,caller=caller,arg=arg,frame=frame,team=team,owner=0x10000))
  return dict(preflight=pre,native=native,events=events)
 def test_primitive_is_not_tactical_capability(self):
  a=assessment(self.good());self.assertEqual(a['status'],'move_and_return_primitive_verified');self.assertFalse(a['raid_verified']);self.assertFalse(a['native_recruitment_observed'])
 def test_owner_drift_blocks_pass(self):
  r=self.good();r['events'][2]['owner']=0x10001;self.assertEqual(assessment(r)['status'],'not_passed')
 def test_ack_without_membership_trace_blocks_pass(self):
  r=self.good();r['events']=[x for x in r['events'] if x['kind']!=18];self.assertEqual(assessment(r)['status'],'not_passed')
 def test_unknown_caller_blocks_pass(self):
  r=self.good();r['events'][0]['caller']=123;self.assertEqual(assessment(r)['status'],'not_passed')
 def test_native_override_blocks_pass(self):
  r=self.good();r['events'].append(dict(kind=10,tag=0,frame=120,team=0x40000,owner=0x10000));self.assertEqual(assessment(r)['status'],'not_passed')
 def test_no_return_cannot_complete(self):
  r=self.good();r['native']['return_verified']=0;self.assertEqual(assessment(r)['status'],'not_passed')
 def test_actual_recruitment_is_separate(self):
  r=self.good();r['events'][-1]['team']=0x50000;self.assertTrue(assessment(r)['native_recruitment_observed'])
if __name__=='__main__':unittest.main()
