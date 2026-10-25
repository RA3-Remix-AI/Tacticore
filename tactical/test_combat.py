import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('combat_backend',Path(__file__).parent/'combat/lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CombatTests(unittest.TestCase):
 def good(self):
  events=[]
  for kind,tag,arg,caller,frame in [(18,1,0x20104,0x838877,100),(12,2,777,1,100),(13,2,777,0,100),(20,0,123,2,120),(16,3,0x20104,0x83885b,121)]:events.append(dict(kind=kind,tag=tag,arg=arg,caller=caller,frame=frame,owner=0x10000,thread=999,target_id=777,damage_source=123,damage_before=100.,damage_after=80.,damage_reported=20.))
  n=dict(phase=3,error=0,restore_mask=63,active=0,detach_calls=1,attack_calls=1,move_calls=0,return_calls=1,return_verified=1,callback_thread=999,damage_count=1,damage_total=20.,issued_frame=100,returned_frame=121,session_id='s',command_id='c',task_id='t',lifecycle_fail=0,overflow=0)
  return dict(session_id='s',preflight=dict(owner='0x10000',ai='0x20000',window_thread=999,session_id='s',selected=dict(object_id=123)),native=n,request=dict(target_object_id=777,lease_frames=180,command_id='c',task_id='t'),events=events)
 def test_goal_is_separate_from_capability(self):
  a=m.assessment(self.good());self.assertEqual(a['status'],'attack_damage_and_return_primitive_verified');self.assertFalse(a['attack_verified']);self.assertEqual(a['causal_damage'],20.)
 def test_other_shooter_rejected(self):
  r=self.good();r['events'][3]['damage_source']=124;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_other_target_rejected(self):
  r=self.good();r['events'][3]['target_id']=778;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_hp_delta_without_matching_reported_rejected(self):
  r=self.good();r['events'][3]['damage_reported']=40.;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_hit_before_order_rejected(self):
  r=self.good();r['events'][3]['frame']=99;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_wrong_attack_argument_rejected(self):
  r=self.good();r['events'][1]['arg']=778;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_unrestored_rejected(self):
  r=self.good();r['native']['restore_mask']=31;self.assertEqual(m.assessment(r)['status'],'not_passed')
if __name__=='__main__':unittest.main()
