"""Raw bounded scheduler proofs never stand in for Stop, arrival or damage."""
import copy,importlib.util,json,struct,unittest,uuid
from pathlib import Path
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('q9_schedule',H/'formation_mission_qualification.py');q=importlib.util.module_from_spec(s);s.loader.exec_module(q)

def fixture():
 rq=dict(command_id='00000000-0000-0000-0000-000000000001',task_id='00000000-0000-0000-0000-000000000002',seq=10,token=20,expires_frame=4600)
 r=dict(request=rq,preflight=dict(window_thread=9),native=dict(callback_thread=9,mission_deadline_frame=4600,pulse_requested=100490,pulse_acknowledged=100490,paused_samples=0),events=[dict(seq=1,kind=0,frame=100,tick=100000,thread=9)])
 def proof(origin,frame,tick,previous,advances,nonce,count,lasttick):
  w=[0x53434839,origin,20,10]+list(struct.unpack('<4I',uuid.UUID(rq['command_id']).bytes))+list(struct.unpack('<4I',uuid.UUID(rq['task_id']).bytes))+[nonce,nonce,frame,previous,9,100,350,lasttick,advances,4600,count,1000]
  r['events'].append(dict(seq=len(r['events'])+1,kind=120+origin,arg=origin,frame=frame,tick=tick,thread=9,stack_word_count=24,stack_words=w+[0]*104))
 proof(1,100,100000,0xffffffff,1,0,0,0);proof(2,102,100500,100,2,100490,1,100500)
 for role in (0,1):r['events'].append(dict(seq=len(r['events'])+1,kind=3,role=role,frame=102,tick=100500))
 return r

class Schedule(unittest.TestCase):
 def test_actual_cpp_scheduler_raw_contract(self):
  r=json.loads((H/'scheduler-native-positive.json').read_text());self.assertEqual(r['sdk_calls'],0);self.assertFalse(r['field_verified']);a=q.schedule_audit(r);self.assertTrue(a['verified'],a);self.assertFalse(a['field_verified'])
 def test_queued_fresh_nonce_before_inline_capture_is_not_an_advance(self):
  r=fixture();r['events'][1]['stack_words'][12]=99990;a=q.schedule_audit(r);self.assertTrue(a['verified'],a);self.assertEqual(a['captures'][0]['actual_advance_count'],1)
 def test_original_inline_and_posted_raw_proofs(self):
  a=q.schedule_audit(fixture());self.assertTrue(a['verified'],a);self.assertTrue(a['posted_pulse_observed']);self.assertFalse(a['fallback_observed']);self.assertFalse(a['field_verified'])
 def test_raw_original_binding_period_thread_deadline_and_shape(self):
  for index,value in [(0,0),(1,1),(2,21),(3,11),(4,2),(8,2),(14,103),(16,10),(17,101),(18,351),(21,4601),(23,1001)]:
   r=fixture();r['events'][2]['stack_words'][index]=value;self.assertFalse(q.schedule_audit(r)['verified'],index)
  for field,value in [('stack_word_count',22),('thread',10),('arg',3)]:
   r=fixture();r['events'][2][field]=value;self.assertFalse(q.schedule_audit(r)['verified'],field)
 def test_wrong_zero_old_future_and_expired_nonce(self):
  for nonce in (0,101000,99000):
   r=fixture();r['events'][2]['stack_words'][12:14]=[nonce,nonce];self.assertFalse(q.schedule_audit(r)['verified'],nonce)
  r=fixture();r['events'][2]['stack_words'][12]=100491;self.assertFalse(q.schedule_audit(r)['verified'])
 def test_inline_is_same_actual_frame_and_first_counter(self):
  for index,value in [(15,99),(20,2),(12,1),(13,1),(19,1),(22,1)]:
   r=fixture();r['events'][1]['stack_words'][index]=value;self.assertFalse(q.schedule_audit(r)['verified'],index)
  r=fixture();r['events'][0]['frame']=99;self.assertFalse(q.schedule_audit(r)['verified'])
 def test_ack_never_creates_three_stop_or_arrival_samples(self):
  r=fixture();r['events'].append(copy.deepcopy(r['events'][-2]));self.assertFalse(q.schedule_audit(r)['verified'])
  r=fixture();r['native']['pulse_requested']=r['native']['pulse_acknowledged']=100900;a=q.schedule_audit(r);self.assertTrue(a['verified']);self.assertEqual(len([e for e in r['events'] if e['kind']==3]),2);self.assertEqual(len(a['captures']),2)
 def test_sparse_periodic_proof_and_nonce_clock_wrap(self):
  r=fixture();row=copy.deepcopy(r['events'][2]);row.update(seq=6,frame=180,tick=106800);w=row['stack_words'];w[12:14]=[106790,106790];w[14:16]=[180,178];w[19:21]=[106800,65];w[22]=64;r['events'].append(row);r['native'].update(pulse_requested=106790,pulse_acknowledged=106790);self.assertTrue(q.schedule_audit(r)['verified'])
  first=r['events'][2];first.update(tick=0xfffffff8);first['stack_words'][12:14]=[0xfffffff0]*2;first['stack_words'][19]=0xfffffff8;nonce=(0xfffffff0+6300)&0xffffffff;row['tick']=(nonce+8)&0xffffffff;row['stack_words'][12:14]=[nonce]*2;row['stack_words'][19]=row['tick'];r['native'].update(pulse_requested=nonce,pulse_acknowledged=nonce);self.assertTrue(q.schedule_audit(r)['verified'])
  row['stack_words'][22]=63;self.assertFalse(q.schedule_audit(r)['verified'])
 def test_paused_first_capture_has_no_invented_inline_advance(self):
  r=fixture();r['events'].pop(1);w=r['events'][1]['stack_words'];w[15]=0xffffffff;w[20]=1;r['native']['paused_samples']=10;a=q.schedule_audit(r);self.assertTrue(a['verified'],a);r['native']['paused_samples']=0;self.assertFalse(q.schedule_audit(r)['verified'])
 def test_host_loss_fallback_is_scheduling_only_and_requires_lost_pulse(self):
  r=fixture();row=copy.deepcopy(r['events'][2]);row.update(seq=6,kind=123,arg=3,frame=200,tick=100851);w=row['stack_words'];w[1]=3;w[14:16]=[200,102];w[20]=3;r['events'].append(row);a=q.schedule_audit(r);self.assertTrue(a['verified'],a);self.assertTrue(a['fallback_observed']);self.assertFalse(a['field_verified']);row['tick']=100850;self.assertFalse(q.schedule_audit(r)['verified'])
 def test_final_nonce_cannot_reset_or_reverse(self):
  for request,ack in [(0,100490),(100490,0),(100400,100490),(0,0)]:
   r=fixture();r['native'].update(pulse_requested=request,pulse_acknowledged=ack);self.assertFalse(q.schedule_audit(r)['verified'],(request,ack))
 def test_missing_or_untyped_raw_proof_fails_closed(self):
  for value in ({},dict(events=[])):
   self.assertFalse(q.schedule_audit(value)['verified'])
  r=fixture();r['events'][2]['stack_words'][2]=False;self.assertFalse(q.schedule_audit(r)['verified'])

if __name__=='__main__':unittest.main()
