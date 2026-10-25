"""DG11 is raw evidence, never a Move/Stop/effect or capability allowance."""
import copy,json,unittest
from test_common_qualification import q

def fixture(cause=5):
 r=dict(preflight=dict(owner='0x3000',window_thread=9,selected=dict(object_id=42,address='0x2000',ai_address='0x4000'),support=dict(object_id=43,address='0x5000',ai_address='0x6000')),native=dict(native_move=1 if cause else 0,support=dict(native_move=0)),events=[])
 w=[0]*80;w[0]=0x44473131;w[1]=1;w[4:10]=[0,0x4024,0x2000,0x8000,0x7da0d9,0];w[20:24]=[1,1,1,1];w[28:30]=[16,1];w[51]=0xffffffff;w[75:80]=[0x4310,100,100,42,0x3000]
 def add(kind,words):r['events'].append(dict(seq=len(r['events'])+1,kind=kind,arg=words[2],caller=words[8],role=0,unit_id=42,owner=0x3000,thread=9,frame=100,tick=1000,tag=words[9],stack_word_count=80,stack_words=copy.deepcopy(words)+[0]*48))
 add(124,w);w[1:4]=[2,cause,1];w[11]=1 if cause else 0;w[12]=3 if cause else 1;add(125,w);return r

class DispatchDiagnostic(unittest.TestCase):
 def test_actual_cpp_capture_counter_inputs_are_not_move_authority(self):
  r=json.loads((q.HERE/'pending-native-positive.json').read_text());self.assertEqual(r['sdk_calls'],0);a=q.dispatch_diagnostic_audit(r);self.assertTrue(a['verified'],a);self.assertTrue(a['observed']);self.assertFalse(a['field_verified']);self.assertFalse(a['move_authority_granted'])
 def test_rejected_input_and_exact_counter_are_preserved_without_credit(self):
  r=fixture();a=q.dispatch_diagnostic_audit(r);self.assertTrue(a['verified'],a);self.assertEqual(a['foreign_increment_count'],1);self.assertEqual(a['records'][0]['opcode_word'],16);self.assertEqual(a['records'][0]['command_source_word'],1);self.assertFalse(a['move_authority_granted']);self.assertFalse(a['completion_claim']);self.assertFalse(q.lease_audit(r)['verified'])
 def test_ordinary_decision_zero_delta_is_not_a_new_action(self):
  a=q.dispatch_diagnostic_audit(fixture(0));self.assertTrue(a['verified'],a);self.assertEqual(a['foreign_increment_count'],0);self.assertFalse(a['field_verified'])
 def test_unlinked_extra_or_missing_pre_post_is_rejected(self):
  for index in (0,1):
   r=fixture();r['events'].pop(index);self.assertFalse(q.dispatch_diagnostic_audit(r)['verified'])
  r=fixture();r['events'].append(copy.deepcopy(r['events'][-1]));self.assertFalse(q.dispatch_diagnostic_audit(r)['verified'])
  r=fixture();r['events'][-1]['stack_words'][3]=9;self.assertFalse(q.dispatch_diagnostic_audit(r)['verified'])
 def test_caller_scope_tag_role_and_raw_capture_are_bound(self):
  for index,value in [(0,0),(1,1),(2,7),(4,1),(5,0x4000),(6,0x5000),(7,0x9000),(8,1),(9,6),(75,0),(76,101),(77,101),(78,99),(79,1)]:
   r=fixture();r['events'][-1]['stack_words'][index]=value;self.assertFalse(q.dispatch_diagnostic_audit(r)['verified'],index)
  r=fixture();r['events'][0]['stack_words'][22]=False;self.assertFalse(q.dispatch_diagnostic_audit(r)['verified'])
 def test_each_foreign_counter_cause_recomputes_one_increment(self):
  for cause in (1,2,3,4,6,7):
   r=fixture();r['events']=r['events'][1:];e=r['events'][0];e['seq']=1;e['arg']=cause;e['stack_words'][2:4]=[cause,0];self.assertTrue(q.dispatch_diagnostic_audit(r)['verified'],cause)
  for index,value in [(10,1),(11,2),(2,0)]:
   r=fixture();r['events'][-1]['stack_words'][index]=value;self.assertFalse(q.dispatch_diagnostic_audit(r)['verified'])
 def test_header_counter_cannot_hide_unlogged_observer_rejection(self):
  r=fixture();r['native']['native_move']=4;self.assertFalse(q.dispatch_diagnostic_audit(r)['verified']);r['events']=[];self.assertFalse(q.dispatch_diagnostic_audit(r)['verified'])
 def test_unreadable_command_is_unknown_not_opcode_zero(self):
  r=fixture()
  for e in r['events']:e['stack_words'][22]=0
  a=q.dispatch_diagnostic_audit(r);self.assertTrue(a['verified'],a);self.assertIsNone(a['records'][0]['opcode_word']);self.assertFalse(a['move_authority_granted'])
 def test_no_observed_diagnostics_no_field_claim(self):
  r=fixture();r['events']=[];r['native']['native_move']=0;a=q.dispatch_diagnostic_audit(r);self.assertTrue(a['verified']);self.assertFalse(a['observed']);self.assertFalse(a['completion_claim'])

if __name__=='__main__':unittest.main()
