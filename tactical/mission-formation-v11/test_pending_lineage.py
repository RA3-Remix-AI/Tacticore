"""Raw command lineage counterexamples. No SDK, game, or field certificate."""
import copy,importlib.util,json,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('pending8_tests',H/'pending_lineage.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
s=importlib.util.spec_from_file_location('pending8_q',H/'formation_mission_qualification.py');q=importlib.util.module_from_spec(s);s.loader.exec_module(q)

def fixture():
 r=dict(preflight=dict(owner='0x3000',window_thread=9,selected=dict(address='0x2000',object_id=42,ai_address='0x4000'),support=dict(address='0x5000',object_id=43,ai_address='0x6000')),native=dict(mission_deadline_frame=4600,move_calls=0,support=dict(move_calls=1)),events=[])
 goal=[100.,200.,210.];command=[0]*23;command[1]=1;command[2:5]=[m.bits(v) for v in goal];command[10]=0x111;command[14]=0x222;command[19]=0x333;command[22]=1;before=[0]*24;before[0]=0xffffffff;stored=[0]*24;stored[:6]=command[:6];stored[11]=0x111;stored[15]=0x222;stored[20]=0x333;stored[23]=1
 p=dict(generation=1,step=0,issued_frame=100,mission_stage=1,goal_kind=81,goal_event_seq=1,slot=0x6310,input_command=0,output_command=0,copy_caller=0,unpack_caller=0,dispatch_caller=0,private_caller=0,delivered=0,role=1,invalid_reason=0,own_facade_seq=2,private_seq=0,goal=goal,command=[0]*23,stored_before=[0]*24,stored_after=[0]*24,unpacked=[0]*23,observed_slot=before,observed_this=0x6024,observed_thing=0,observed_command=0x7000)
 def add(kind,frame=100,tag=6,**fields):
  e=dict(seq=len(r['events'])+1,kind=kind,role=1,unit_id=43,owner=0x3000,thread=9,frame=frame,tick=frame*60,tag=tag,arg=1,caller=0,source=1,mission_stage=1,mission_deadline_frame=4600,command_xyz=list(goal),argument_path=0,argument_limit=3.4028234663852886e38);e.update(fields)
  if kind in m.PROOF_KINDS:p['step']=kind;e['lineage']=copy.deepcopy(p)
  r['events'].append(e);return e
 add(81,tag=0);add(50);add(110);p.update(input_command=0x8000,command=command,observed_command=0x8000);add(120)
 p.update(copy_caller=m.COPY_CALLER,stored_before=before,observed_this=0x6310);add(111);p.update(stored_after=stored,observed_slot=stored);add(112)
 add(51);p.update(observed_this=0x6024,observed_command=0x7000);add(119)
 p.update(unpack_caller=m.UNPACK_CALLER,output_command=0x9000,observed_this=0x6310,observed_thing=0x5000,observed_command=0x9000);add(113,200,0)
 unpacked=list(command);unpacked[10]=0x999;p.update(unpacked=unpacked);add(114,200,0)
 p.update(dispatch_caller=m.DISPATCH_CALLER,observed_this=0x6024,observed_thing=0);add(115,200,0)
 private=add(10,200,0,caller=m.PRIVATE_CALLER);p.update(private_caller=m.PRIVATE_CALLER,private_seq=private['seq'],delivered=1,observed_this=0x6000,observed_thing=0x5000,observed_command=0x9008);add(116,200,0);add(11,200,0);p.update(observed_this=0x6024,observed_thing=0,observed_command=0x9000);add(117,200,0)
 return r

def event(r,kind):return next(e for e in r['events'] if e['kind']==kind)

class PendingLineage(unittest.TestCase):
 def test_actual_cpp_hook_raw_positive_matches_independent_audit(self):
  r=json.loads((H/'pending-native-positive.json').read_text());self.assertEqual(r['sdk_calls'],0);self.assertIs(r['game_access'],False);a=m.audit(r);self.assertTrue(a['verified'],a);self.assertEqual(len(a['accepted_private_sequences']),1);self.assertFalse(a['field_verified'])
  event(r,113)['lineage']['observed_thing']^=4;self.assertFalse(m.audit(r)['verified'])
 def test_complete_actual_raw_chain_accepts_only_one_private(self):
  r=fixture();a=m.audit(r);self.assertTrue(a['verified'],a);self.assertTrue(a['observed']);self.assertEqual(a['accepted_private_sequences'],[12]);self.assertFalse(a['field_verified']);b=q.normal_move_audit(r);self.assertTrue(b['verified'],b);self.assertEqual(b['groups'][0]['last_seq'],14)
 def test_same_goal_caller_without_complete_proof_never_credit(self):
  for kind in (110,120,111,112,113,114,115,116,117,119):
   r=fixture();r['events'].remove(event(r,kind));self.assertFalse(m.audit(r)['verified'],kind);self.assertFalse(q.normal_move_audit(r)['verified'],kind)
 def test_wrong_scope_this_thing_command_pointer_and_slot_rejected(self):
  for kind in (110,120,111,112,113,114,115,116,117,119):
   for key in ('observed_this','observed_command','observed_thing'):
    r=fixture();event(r,kind)['lineage'][key]=0xdead;self.assertFalse(m.audit(r)['verified'],(kind,key))
  for key in ('slot','input_command','output_command'):
   r=fixture();event(r,114)['lineage'][key]=0xdead;self.assertFalse(m.audit(r)['verified'],key)
 def test_all_pure_command_fields_are_recomputed(self):
  for index in (0,1,2,3,4,5,6,7,8,9,11,12,13,15,16,17,18,20,21,22):
   r=fixture()
   for e in r['events']:
    if e.get('lineage',{}).get('command')==event(r,120)['lineage']['command']:e['lineage']['command'][index]^=1
   self.assertFalse(m.audit(r)['verified'],index)
 def test_stored_before_after_and_current_full_bytes_cannot_be_forged(self):
  for kind,field in ((111,'observed_slot'),(112,'stored_before'),(112,'stored_after'),(112,'observed_slot'),(113,'observed_slot'),(114,'stored_after')):
   r=fixture();event(r,kind)['lineage'][field][20]^=1;self.assertFalse(m.audit(r)['verified'],(kind,field))
  r=fixture()
  for kind in (111,112,119,113,114,115,116,117):event(r,kind)['lineage']['stored_before'][0]=0
  event(r,111)['lineage']['observed_slot'][0]=0;self.assertFalse(m.audit(r)['verified'])
 def test_wrong_unpacked_payload_pointer_and_original_goal_rejected(self):
  for key,value in [('unpacked',[0]*23),('output_command',0),('goal',[100.,201.,210.]),('goal_event_seq',2),('goal_kind',85),('own_facade_seq',1),('mission_stage',3),('generation',2),('issued_frame',101)]:
   r=fixture();event(r,114)['lineage'][key]=value;self.assertFalse(m.audit(r)['verified'],key)
 def test_changed_callers_typed_step_and_actor_identity_rejected(self):
  for kind,key in ((111,'copy_caller'),(114,'unpack_caller'),(115,'dispatch_caller'),(116,'private_caller'),(116,'private_seq'),(116,'step'),(117,'delivered')):
   r=fixture();event(r,kind)['lineage'][key]=0;self.assertFalse(m.audit(r)['verified'],(kind,key))
  for key,value in [('unit_id',42),('role',0),('thread',10),('owner',1),('mission_stage',3)]:
   r=fixture();event(r,113)[key]=value;self.assertFalse(m.audit(r)['verified'],key)
 def test_no_timeout_reset_duplicate_consume_or_redelivery(self):
  r=fixture()
  for e in r['events']:
   if e['frame']==200:e['frame']=351
  self.assertFalse(m.audit(r)['verified'])
  r=fixture();r['native']['mission_deadline_frame']=200
  for e in r['events']:e['mission_deadline_frame']=200
  self.assertFalse(m.audit(r)['verified'])
  for kind in (111,112,113,114,115,116,117):
   r=fixture();r['events'].append(copy.deepcopy(event(r,kind)));self.assertFalse(m.audit(r)['verified'],kind)
 def test_stop_attack_new_facade_return_and_explicit_invalidation_destroy_credit(self):
  for kind in (30,34,12,5,50,118):
   r=fixture();e=copy.deepcopy(event(r,113));e.update(kind=kind,seq=8.5);r['events'].insert(8,e);self.assertFalse(m.audit(r)['verified'],kind)
 def test_private_remains_tag_zero_path_zero_source_one_fltmax_once(self):
  for key,value in [('tag',6),('arg',0),('source',0),('caller',0),('argument_path',1),('argument_limit',1000.),('frame',201),('command_xyz',[1.,2.,3.])]:
   r=fixture();event(r,10)[key]=value;self.assertFalse(m.audit(r)['verified'],key)
  r=fixture();e=copy.deepcopy(event(r,10));e['seq']=12.5;r['events'].insert(12,e);self.assertFalse(m.audit(r)['verified'])
 def test_unobserved_immediate_protocol_keeps_zero_deferred_credit(self):
  a=m.audit({});self.assertTrue(a['verified']);self.assertFalse(a['observed']);self.assertEqual(a['accepted'],[]);self.assertFalse(a['field_verified'])

if __name__=='__main__':unittest.main()
