"""Tamper tests against an actual read-only MFM2 zero-lease capture."""
import copy,hashlib,importlib.util,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path[:0]=[str(HERE.parent),str(HERE.parent.parent/'integration'),str(HERE.parent.parent/'production')]
p=HERE.parent/'mission_formation_v3_gate_no_lease.py';s=importlib.util.spec_from_file_location('test_formation_gate',p);h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
RAW=HERE.parent.parent/'acceptance/runs/20261025-105617-commander/coord2-mission02.json';SIDE=RAW.with_suffix('.native-gate.json')
class ActualGateTests(unittest.TestCase):
 def fixture(self):return json.loads(SIDE.read_text(encoding='utf-8')),json.loads(RAW.read_text(encoding='utf-8')),hashlib.sha256(RAW.read_bytes()).hexdigest()
 def test_actual_two_actor_capture(self):
  e,r,sha=self.fixture();v=h.verify(e,r,sha);self.assertTrue(v['exclusive_control_never_held']);self.assertFalse(v['completion_claim']);self.assertFalse(v['return_verified'])
 def test_support_sdk_count_not_zero(self):
  e,r,sha=self.fixture();e['snapshots'][0]['support']['detach_calls']=1;self.assertFalse(h.verify(e,r,sha)['no_actor_lease_verified'])
 def test_one_original_byte_corrupted(self):
  e,r,sha=self.fixture();e['snapshots'][1]['entries'][0]['actual']='00';self.assertFalse(h.verify(e,r,sha)['no_actor_lease_verified'])
 def test_other_child_token_rejected(self):
  e,r,sha=self.fixture();e['snapshots'][0]['token']+=1;self.assertFalse(h.verify(e,r,sha)['no_actor_lease_verified'])
 def test_actor_order_cannot_be_swapped(self):
  e,r,sha=self.fixture();e['snapshots'][0]['object_ids'].reverse();self.assertFalse(h.verify(e,r,sha)['no_actor_lease_verified'])
 def test_sdk_tagged_event_rejects_no_lease_claim(self):
  e,r,sha=self.fixture();r['events'].append(dict(tag=6,kind=50));self.assertFalse(h.verify(e,r,sha)['no_actor_lease_verified'])
 def test_completion_claim_cannot_hide_in_gate(self):
  e,r,sha=self.fixture();e['completed']=True;self.assertFalse(h.verify(e,r,sha)['no_actor_lease_verified'])
if __name__=='__main__':unittest.main()
