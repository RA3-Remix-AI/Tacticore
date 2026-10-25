"""Exact AttackObject10 candidate admission; no game or SDK calls."""
import copy,hashlib,json,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from test_mission_actor_admission import Memory as BaseMemory
import mission_actor_admission_v2 as a
import mission_actor_admission as old
import test_client as boundary

class Memory(BaseMemory):
 def __init__(self):super().__init__();self.state_id=10;self.attack_vtable=0xc548c0
 def u32(self,address):
  if address==0x8000 and self.state_id==10:return self.attack_vtable
  return super().u32(address)

class Admission2Tests(unittest.TestCase):
 def test_exact_attack_ten_candidate_has_ground_backrefs_and_no_ownership_claim(self):
  for path in [0,0x9000]:
   m=Memory();m.path=path;r=a.actor_admission(m,0x2000);self.assertTrue(a.verify_evidence(r)['verified'],r);self.assertFalse(a.verify_evidence(r)['command_ownership_guaranteed_after_snapshot'])
 def test_one_and_sixteen_keep_their_original_scope(self):
  for state in [1,16]:
   m=Memory();m.state_id=state;self.assertTrue(a.verify_evidence(a.actor_admission(m,0x2000))['verified'])
 def test_only_exact_attack_vtable_is_added(self):
  m=Memory();m.attack_vtable=0xc55608;self.assertFalse(a.actor_admission(m,0x2000)['admission_verified'])
  for state in [7,54,77,96]:
   m=Memory();m.state_id=state;self.assertFalse(a.actor_admission(m,0x2000)['admission_verified'])
 def test_ground_lock_owner_and_state_binding_are_not_relaxed(self):
  for field,value in [('cache',0),('flags',0x10001),('sm_owner',0x9999)]:
   m=Memory();setattr(m,field,value);self.assertFalse(a.actor_admission(m,0x2000)['admission_verified'],field)
 def test_old_helper_source_and_old_ten_refusal_are_unchanged(self):
  root=Path(__file__).resolve().parent;self.assertEqual(hashlib.sha256((root/'mission_actor_admission.py').read_bytes()).hexdigest(),'9635d39a64e65ec95a67a757a4a4212c1835ae539cd00a44ba22a88ed999335b');self.assertFalse(old.actor_admission(Memory(),0x2000)['admission_verified'])
  r=a.actor_admission(Memory(),0x2000);r['state_snapshot']['state_vtable']='0xc55608';self.assertFalse(a.verify_evidence(r)['verified'])
 def test_client_explicit_filename_routes_to_new_helper_and_rejects_traversal(self):
  m=boundary.m;e=boundary.ModelBoundary().executor();memory=Memory();units=[dict(object_id=77,address='0x2000',type_hash='0x19ab11af',xyz=[0,0,0],hp=100)]
  self.assertFalse(e._surface_ground_candidates(memory,units,'0x3000'));self.assertEqual(len(e._surface_ground_candidates(memory,units,'0x3000','mission_actor_admission_v2.py')),1)
  with self.assertRaises(ValueError):e._surface_ground_candidates(memory,units,'0x3000','../mission_actor_admission_v2.py')

if __name__=='__main__':unittest.main()
