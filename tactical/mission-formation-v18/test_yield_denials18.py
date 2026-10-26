"""Actual helper payloads remain private diagnostics, not full field Source."""
import copy,importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf18_yield_test',HERE/'formation_mission_qualification.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

class YieldDenials(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=HERE/'yield-denial-native-positive.json';cls.raw=cls.path.read_bytes();cls.report=json.loads(cls.raw)
 def fixture(self):return copy.deepcopy(self.report['events'])
 def rejected(self,events):self.assertFalse(q.yield_payload_audit(events)['verified'])
 def test_actual_production_helper_and_router_do_not_grant_source(self):
  out=q.yield_payload_audit(self.report['events']);self.assertTrue(out['verified'],out['checks'])
  self.assertFalse(out['model_eligible']);self.assertFalse(out['move_authority_granted']);self.assertFalse(out['fov_authority_granted']);self.assertFalse(out['completion_claim'])
  self.assertFalse(q.yield_denial_audit(self.report)['verified']);self.assertEqual(q.qualify(self.report)['status'],'not_passed');self.assertEqual(self.path.read_bytes(),self.raw)
 def test_no_denials_is_not_a_new_requirement_to_trigger_one(self):self.assertTrue(q.yield_payload_audit([])['verified'])
 def test_missing_after_or_diagnostic_is_not_closed(self):
  for index in (0,2,3):
   ev=self.fixture();ev.pop(index);self.rejected(ev)
 def test_unknown_opcode_source_or_caller_not_allowed(self):
  for word,value in ((53,49),(54,1),(51,0x6939ab)):
   ev=self.fixture()
   for e in ev[1:3]:e['stack_words'][word]=value
   self.rejected(ev)
 def test_owned_actor_source_and_backref_must_be_real(self):
  for word,value in ((23,2),(22,0),(25,0),(30,0),(32,0),(39,0)):
   ev=self.fixture();ev[1]['stack_words'][word]=value;self.rejected(ev)
 def test_partial_original_sample_cannot_be_positive(self):
  ev=self.fixture();ev[1]['stack_words'][77]&=~1;self.rejected(ev)
 def test_state_path_source_or_pose_change_cannot_be_hidden(self):
  for word in (19,23,28,31,33,36):
   ev=self.fixture();ev[2]['stack_words'][word]^=1;self.rejected(ev)
 def test_after_read_failure_cannot_keep_before_as_credit(self):
  ev=self.fixture();ev[2]['stack_words'][77]=0;ev[2]['stack_words'][11]=3;ev[3]['stack_words'][12]=7;self.rejected(ev)
 def test_command_raw_must_remain_exact(self):
  ev=self.fixture();ev[2]['stack_words'][63]^=1;self.rejected(ev)
 def test_forward_claim_or_sdk_counter_change_rejected(self):
  for word in (10,41,43):
   ev=self.fixture();ev[2]['stack_words'][word]+=1;self.rejected(ev)
 def test_tls_or_inflight_ticket_cannot_be_denied_as_idle(self):
  for word,value in ((46,1),(44,2),(44,1)):
   ev=self.fixture();ev[1]['stack_words'][word]=value;self.rejected(ev)
 def test_armed_but_delivered_ticket_can_remain_unchanged(self):
  ev=self.fixture()
  for e in ev[1:3]:e['stack_words'][44]=97
  for e in (ev[0],ev[3]):e['stack_words'][13]=1;e['stack_words'][18]=e['stack_words'][19]=1
  self.assertTrue(q.yield_payload_audit(ev)['verified'])
 def test_moving_path_is_preserved_without_new_move_credit(self):
  ev=self.fixture()
  for e in ev[1:3]:
   e['state_id']=1;e['path']=0x110000;e['stack_words'][28]=1;e['stack_words'][29]=0xc55598;e['stack_words'][31]=0x110000
  out=q.yield_payload_audit(ev);self.assertTrue(out['verified']);self.assertFalse(out['move_authority_granted'])
 def test_original_common_stack_and_surface_must_match_proof(self):
  ev=self.fixture();ev[2]['stack'][0]^=1;self.rejected(ev)
  ev=self.fixture();ev[2]['state_id']=26;self.rejected(ev)
 def test_unpaired_new_diagnostic_decision_not_silently_accepted(self):
  self.rejected([e for e in self.fixture() if e['kind'] not in (172,173)])
 def test_frame_and_thread_cannot_be_rewritten(self):
  ev=self.fixture();ev[2]['frame']+=1;self.rejected(ev)
  ev=self.fixture();ev[1]['thread']+=1;self.rejected(ev)
 def test_reserved_words_and_ordinal_reset_rejected(self):
  for word in (45,93,127,78):
   ev=self.fixture();ev[1]['stack_words'][word]+=1;self.rejected(ev)
 def many(self,count):
  result=[]
  for i in range(count):
   group=self.fixture();before=min(i,32);after=min(i+1,32)
   for j,e in enumerate(group):
    e['seq']=4*i+j+1;e['frame']+=2*i;w=e['stack_words']
    if e['kind'] in (172,173):
     e['arg']=i+1;w[4]=w[76]=e['frame'];w[7]=i+1;w[78]=before;w[79]=after if e['kind']==173 else before
     if e['kind']==173:w[6]=4*i+2;w[11]=2 if i>=32 else 1
    else:
     w[76]=w[77]=e['frame']
     if e['kind']==125:w[3]=4*i+1;w[12]=6 if i>=32 else 5
   result+=group
  return result
 def test_exactly32_denials_allowed_no_credit(self):
  out=q.yield_payload_audit(self.many(32));self.assertTrue(out['verified'],out['checks']);self.assertEqual(out['denials_by_role'],[0,32])
 def test_33rd_is_never_forwarded_and_never_success(self):
  out=q.yield_payload_audit(self.many(33));self.assertFalse(out['verified']);self.assertTrue(out['checks']['raw_before_after_decision']);self.assertFalse(out['checks']['bounded_normal_denials']);self.assertFalse(out['move_authority_granted'])

if __name__=='__main__':unittest.main()
