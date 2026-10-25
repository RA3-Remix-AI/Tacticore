"""Owned state admission regression for the actual enter/garrison failure."""
import copy,unittest
from test_grounded_status_v2 import Memory as GroundMemory
import mission_actor_admission as a

class Memory(GroundMemory):
 def __init__(self):super().__init__();self.state_id=16;self.path=0;self.flags=0x10000;self.sm_owner=0x2000
 def u32(self,address):
  return {0x2374:0x6000,0x6000:0xc48670,0x6024:0xc48528,0x6008:0x2000,0x603c:0x7000,0x7004:0x8000,0x7024:self.sm_owner,0x8000:0xc51818,0x8004:self.state_id,0x8018:0x7000,0x6050:0,0x6150:self.path,0x7078:self.flags}.get(address,super().u32(address))

class AdmissionTests(unittest.TestCase):
 def test_idle_and_normal_move_with_no_lock_are_admitted(self):
  for state,path in [(16,0),(1,0),(1,0x9000)]:
   m=Memory();m.state_id=state;m.path=path;r=a.actor_admission(m,0x2000);self.assertTrue(r['admission_verified'],r);self.assertTrue(a.verify_evidence(r)['verified'])
 def test_real_enter54_and_garrison77_never_borrowed_even_if_ground(self):
  for state in [54,77,68,96]:
   m=Memory();m.state_id=state;r=a.actor_admission(m,0x2000);self.assertTrue(r['grounded_status']['grounded_verified']);self.assertFalse(r['admission_verified']);self.assertFalse(a.verify_evidence(r)['verified'])
 def test_idle_path_lock_or_bad_owner_are_rejected(self):
  for attr,value in [('path',0x9000),('flags',0x10001),('sm_owner',0x9999)]:
   m=Memory();setattr(m,attr,value);self.assertFalse(a.actor_admission(m,0x2000)['admission_verified'])
 def test_unknown_ground_or_changing_state_is_not_eligible(self):
  m=Memory();m.cache=0;self.assertFalse(a.actor_admission(m,0x2000)['admission_verified'])
  m=Memory();original=m.u32;count=[0]
  def changed(address):
   if address==0x8004:count[0]+=1;return 16 if count[0]==1 else 54
   return original(address)
  m.u32=changed;self.assertFalse(a.actor_admission(m,0x2000)['admission_verified'])
 def test_pure_verifier_rejects_forged_bool_source_binding_and_state(self):
  r=a.actor_admission(Memory(),0x2000)
  for mutate in ['state','frame','owner','source','ground']:
   e=copy.deepcopy(r)
   if mutate=='state':e['state_snapshot']['state_id']=54
   elif mutate=='frame':e['frame']=101
   elif mutate=='owner':e['owner']='0x9999'
   elif mutate=='source':e['helper_sha256']='0'*64
   else:e['grounded_status']['height_cache_flags']='0x0'
   self.assertFalse(a.verify_evidence(e)['verified'],mutate)

if __name__=='__main__':unittest.main()
