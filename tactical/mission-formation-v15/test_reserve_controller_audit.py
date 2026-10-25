"""Adversarial software evidence, never a game/source certificate."""
import copy
import ctypes as c
import hashlib
import ast
import inspect
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import uuid

P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf15_controller_under_test',P/'reserve_controller_audit.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

def bits(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def raw(obj):return list(struct.unpack('<%dI'%(c.sizeof(obj)//4),bytes(obj)))
def uid(index):return list(struct.unpack('<4I',uuid.UUID(int=index).bytes))
def sample(frame=10,role=0):
 s=q.L.ReserveSample13();s.frame=frame;s.thing=0x10000+role*0x100;s.id=100+role;s.type_hash=q.TYPES[role];s.owner=0x20000;s.template_ptr=0x30000;s.update=0x40000+role*0x100;s.update_vtable=0xc48670;s.update_backref=s.thing;s.team=0x50000
 s.stance_module=0x60000+role*0x100;s.stance_vtable=0xc37f90;s.stance_backref=s.thing;s.stance_data=0x70000;s.stance_enum_list=0x80000;s.stance_enum_count=2;s.stance_enum_entries[:4]=[0,0,2,0]
 s.sm=0x90000;s.sm_owner=s.thing;s.state=0xa0000;s.state_id=10;s.state_vtable=0xc548c0;s.state_owner_sm=s.sm;s.height_flags=4;s.hp=100 if role==0 else 120;s.xyz[:]=[0,0,210]
 return s
def event(kind=141,frame=10,role=0,arg=1,seq=1,s=None):
 s=s or sample(frame,role);w=[0]*128;w[:8]=[0x52533133,1,role,kind,frame,1,arg,arg];w[8:68]=raw(s);w[68:78]=[0x544d5034,s.team,0xb0000,s.owner,s.team,0xb0000,s.owner,frame,0,0];w[92]=bits(s.hp)
 return dict(kind=kind,role=role,frame=frame,arg=arg,seq=seq,stack_words=w,stack_word_count=128)
def origin(enemy=False,visible=True,gap=351):
 h=[0x4f533133,10,0,0x10000,100,0x20000,bits(0),bits(0),bits(210),0x10000,0xc0000,0xc6aefc,0xd0000,0x100000,1000,1000,bits(0),bits(0),bits(1),1]
 h += [0x4e4f4445,0x10000,0xc4db60,100,0x20000,0x11000 if enemy else 0,0,0xc5bce0,3,0,0x454e444e]
 count=1;authorized=0
 if enemy:
  h += [0x4e4f4445,0x11000,0xc4db60,200,0x21000,0,0,0xc5bce0,4,2 if visible else 1]
  h += [0x12000,0x13000,8,0x14000,0x15000,0x15000,4,0,0,0x454e4452]
  h += [0x16000,0xd0000,0x17000,1,0 if visible else 1,0]
  if visible:
   center=0x100000+int(gap)*0x34
   h += [1,0,center,1,0,0x464f4f54,0x16000,0xd0000,0x17000,1,0,0,center,1,0,center,1,0,0xc4db60,200,0x21000,0,0,0x16000,0xd0000,bits(gap),bits(0),bits(210),bits(gap)]
   authorized=1
  h += [0x454e444e];count=2
 h += [0x504f5354,*h[10:20],h[9],10]
 h += [0x454e4453,count,authorized,bits(gap) if authorized else 0x7f7fffff,int(not authorized or gap>350),1,10,0x10000]
 return h
def chunks(words,result=1):
 def row(kind,offset,count,payload):
  w=[0x4f533133,1,1,0,10,offset,count,result]+payload
  w += [0]*(128-len(w))
  return dict(kind=kind,role=0,frame=10,arg=1,seq=1,stack_words=w,stack_word_count=128)
 es=[row(160,0,0,[])]+[row(161,i,len(words[i:i+120]),words[i:i+120]) for i in range(0,len(words),120)]+[row(162,len(words),0,[])]
 for k,e in enumerate(es,1):e['seq']=k
 return es

class TypedEvidence(unittest.TestCase):
 def test_actual_layout(self):
  self.assertEqual((c.sizeof(q.L.ReserveSample13),c.sizeof(q.L.MissionCommitBody13),q.L.MissionCommitBody13.digest_sha256.offset),(240,284,252))
 def test_rs_fixed_sample_is_not_common_pose(self):
  e=event();e.update(x=999,y=999,z=999)
  self.assertEqual(q.reserve_record(e)['sample']['xyz'],[0.,0.,210.])
 def test_rs_frame_mismatch_rejected(self):
  e=event();e['stack_words'][8]=11
  with self.assertRaises(ValueError):q.reserve_record(e)
 def test_rs_reserved_words_rejected(self):
  e=event();e['stack_words'][127]=1
  with self.assertRaises(ValueError):q.reserve_record(e)
 def test_rs_unknown_role_rejected(self):
  e=event();e['role']=2
  with self.assertRaises(ValueError):q.reserve_record(e)
 def test_duplicate_or_short_stack_rejected(self):
  for key,value in [('stack_word_count',127),('stack_words',[0]*127)]:
   e=event();e[key]=value
   with self.assertRaises(ValueError):q.reserve_record(e)
 def test_real_positive_surface_not_status160(self):
  s=q.plain(sample());self.assertTrue(q.surface(s,s,s['owner']))
  s['holder']=1;self.assertFalse(q.surface(s,s,s['owner']))
 def test_state16_is_not_hold(self):
  s=q.plain(sample());s.update(team=0x51000,stance=2,state_id=16)
  self.assertFalse(q.holding(s,s,s['owner'],s['team']))
 def test_wrong94_vtable_is_not_hold(self):
  s=q.plain(sample());s.update(stance=2,state_id=94,state_vtable=0xc551a0,source=1)
  self.assertTrue(q.holding(s,s,s['owner'],s['team']))
  s['state_vtable']=0xc55130;self.assertFalse(q.holding(s,s,s['owner'],s['team']))
 def test_no_controller_evidence_fails_closed(self):
  out=q.audit({});self.assertFalse(out['verified']);self.assertFalse(out['tactical_source_granted'])

class RawOrigin(unittest.TestCase):
 def test_complete_own_list_clear(self):
  out=q.origin_stream(origin());self.assertTrue(out['clear']);self.assertEqual(out['live_node_count'],1)
 def test_visible_enemy_above350(self):
  out=q.origin_stream(origin(True,True,351));self.assertTrue(out['clear']);self.assertEqual(out['visible_enemies'][0]['gap'],351)
 def test_visible_enemy_exact350_rejected_as_clear(self):
  self.assertFalse(q.origin_stream(origin(True,True,350))['clear'])
 def test_hidden_enemy_has_no_position(self):
  out=q.origin_stream(origin(True,False));self.assertTrue(out['clear']);self.assertEqual(out['visible_enemies'],[])
 def test_hidden_xyz_smuggled_rejected(self):
  w=origin(True,False);w[-8:-8]=[bits(100),bits(100),bits(210)]
  with self.assertRaises(ValueError):q.origin_stream(w)
 def test_incomplete_live_list_rejected(self):
  w=origin();w[20+5]=0x12000
  with self.assertRaises(ValueError):q.origin_stream(w)
 def test_wrong_viewer_owner_rejected(self):
  w=origin();w[5]+=4
  with self.assertRaises(ValueError):q.origin_stream(w)
 def test_bad_after_frame_rejected(self):
  w=origin();w[-2]+=1
  with self.assertRaises(ValueError):q.origin_stream(w)
 def test_center_cell_not_authorized_by_min_gap(self):
  w=origin(True,True);w[-20]=0 # break a real typed authorized row
  with self.assertRaises(ValueError):q.origin_stream(w)
 def test_chunk_reassembly(self):
  r={'events':chunks(origin())};self.assertTrue(q.origin_audit(r,[])['verified'])
 def test_missing_chunk_not_filled(self):
  es=chunks(origin());del es[1]
  with self.assertRaises(ValueError):q.origin_audit({'events':es},[])
 def test_chunk_replay_not_accepted(self):
  es=chunks(origin());es.insert(2,copy.deepcopy(es[1]))
  with self.assertRaises(ValueError):q.origin_audit({'events':es},[])
 def test_positive_bool_cannot_replace_clear_scan(self):
  es=chunks(origin(True,True,350),result=1)
  with self.assertRaises(ValueError):q.origin_audit({'events':es},[])
 def test_crossframe_chunk_rejected(self):
  es=chunks(origin());es[1]['frame']=11
  with self.assertRaises(ValueError):q.origin_audit({'events':es},[])
 def test_changed_footprint_between_reads_is_unknown(self):
  w=origin(True,True);i=w.index(0x464f4f54);w[i+8]+=1
  with self.assertRaises(ValueError):q.origin_stream(w)
 def test_grid_change_cannot_be_hidden_fallback(self):
  w=origin(True,False);i=w.index(0x504f5354);w[i+5]+=1
  with self.assertRaises(ValueError):q.origin_stream(w)
 def test_complete_missing_relation_key_is_neutral(self):
  w=origin();head=w[:20];own=w[20:31];own[5]=0x11000
  foreign=[0x4e4f4445,0x11000,0xc4db60,200,0x21000,0,0,0xc5bce0,4,0]
  # target index4 is absent after a complete original hash chain toNULL.
  relation=[0x12000,0x13000,8,0x14000,0x15000,0x15000,7,2,0,0x454e4452]
  ws=head+own+foreign+relation+[0x454e444e]+[0x504f5354,*head[10:20],head[9],10]+[0x454e4453,2,0,0x7f7fffff,1,1,10,head[9]]
  self.assertTrue(q.origin_stream(ws)['clear'])
  # Truncating the same chain is not a neutral fact.
  ws[ws.index(0x15000)+4]=0x16000
  with self.assertRaises(ValueError):q.origin_stream(ws)

class FrozenClock(unittest.TestCase):
 def fixture(self):
  ctl=dict(clock_frozen=1,reserve_start_frame=10,lease_issued_frame=10,reserve_deadline_frame=310,hard_deadline_frame=4510,mission_commit_frame=20)
  es=[dict(kind=1,tag=1,frame=10,seq=2,role=0),dict(kind=1,tag=1,frame=12,seq=3,role=1)]
  z=dict(event=dict(kind=145,seq=1),sample=dict(frame=10),first_role=0,start=10,reserve_deadline=310,deadline=4510)
  return dict(native=dict(controller=ctl,issued_frame=10,mission_deadline_frame=4510),events=es),[z]
 def test_first_borrow_freezes_both_deadlines(self):
  r,z=self.fixture();self.assertTrue(q.clock_audit(r,z)['verified'])
 def test_second_role_cannot_renew(self):
  r,z=self.fixture();z.append(dict(z[0],event=dict(kind=141,seq=4),start=12,reserve_deadline=312,deadline=4512))
  self.assertFalse(q.clock_audit(r,z)['verified'])

 def test_freeze_after_transfer_is_not_credit(self):
  r,z=self.fixture();z[0]['event']['seq']=4
  self.assertFalse(q.clock_audit(r,z)['verified'])
 def test_commit_at_deadline_is_late(self):
  r,z=self.fixture();r['native']['controller']['mission_commit_frame']=310
  self.assertFalse(q.clock_audit(r,z)['verified'])
 def test_pause_ack_does_not_create_borrow(self):
  r,z=self.fixture();r['events'][1]['kind']=122
  self.assertFalse(q.clock_audit(r,z)['verified'])

class ActualCppTransport(unittest.TestCase):
 """The original software bytes retain their fake-engine limitations."""
 def fixture(self):
  data=(P/'controller-commit-accepted.bin').read_bytes()
  self.assertEqual(len(data),13269420)
  t=q.L.Tactical.from_buffer_copy(data)
  n={name:q.plain(getattr(t,name)) for name,*_ in t._fields_ if name!='events'}
  for dest,src in [('command_id','command'),('task_id','task'),('session_id','session'),('commander_id','commander')]:n[dest]=q.ident(n[src])
  es=[q.plain(e) for e in t.events[:t.count]]
  r=dict(native=n,events=es,session_id=n['session_id'],preflight=dict(window_thread=n['thread'],frame=100))
  return r,[q.reserve_record(e) for e in es if e['kind'] in q.RS_KINDS]
 def test_actual_input_cohort_clock_and_ready(self):
  r,z=self.fixture()
  self.assertTrue(q.input_audit(r)['verified'])
  for fn in (q.cohort_audit,q.clock_audit,q.ready_audit,q.origin_audit):self.assertTrue(fn(r,z)['verified'],fn.__name__)
 def test_actual_stop_samples_without_fake_sdk_credit(self):
  r,z=self.fixture();out=q.stop_audit(r,z)
  self.assertTrue(out['checks']['fixed_actual_frame_coverage'])
  self.assertTrue(out['checks']['three_initial_and_brake_stops'])
  self.assertFalse(out['checks']['explicit_normal_stop_source'])
 def test_software_receipt_zero_issue_frame_not_field_provenance(self):
  r,z=self.fixture();out=q.producer_audit(r)
  self.assertTrue(out['checks']['original_rpc1_pairs'])
  self.assertFalse(out['checks']['paid_original_receipts'])
 def test_missing_middle_stop_sample_fails(self):
  r,z=self.fixture();one=next(x for x in z if x['event']['kind']==163 and x['words'][5]==4);z.remove(one)
  self.assertFalse(q.stop_audit(r,z)['checks']['fixed_actual_frame_coverage'])
 def test_changed_output_anchor_not_raw_commit(self):
  r,z=self.fixture();r['native']['slots'][0]['anchor'][0]+=1
  self.assertFalse(q.ready_audit(r,z)['verified'])
 def test_ready_gap_not_filled_with_acks(self):
  r,z=self.fixture();one=next(x for x in z if x['event']['kind']==155);z.remove(one)
  self.assertFalse(q.ready_audit(r,z)['verified'])
 def test_receipt_actor_replacement_projection_fails(self):
  r,z=self.fixture();es=[e for e in r['events'] if e['kind']==140 and e['role']==0];es[-2]['stack_words'][116]+=1;es[-1]['stack_words'][116]+=1
  self.assertFalse(q.producer_audit(r)['checks']['immutable_payment_projection'])
 def test_final_cohort_team_must_be_actual_output(self):
  r,z=self.fixture();r['native']['slots'][0]['admitted_team']+=4
  self.assertFalse(q.cohort_audit(r,z)['verified'])
 def test_brake_sample3_not_duplicate_frame(self):
  r,z=self.fixture();one=[x for x in z if x['event']['kind']==148 and x['event']['role']==0][-1];one['sample']['frame']-=1
  self.assertFalse(q.ready_audit(r,z)['verified'])
 def test_observed_path_is_frozen_not_same_goal(self):
  r,z=self.fixture();one=next(x for x in z if x['event']['kind']==163 and x['words'][5]==3 and x['sample']['path']);one['sample']['path']+=4
  self.assertFalse(q.ready_audit(r,z)['checks']['frozen_observed_path'])
 def test_actual_visible_blocked_and_hidden_cpp_scans(self):
  for filename,clear in [('origin-visible-positive.bin',True),('origin-visible-blocked.bin',False),('origin-hidden-positive.bin',True)]:
   t=q.L.Tactical.from_buffer_copy((P/filename).read_bytes());r=dict(events=[q.plain(e) for e in t.events[:t.count]])
   out=q.origin_audit(r,[]);self.assertTrue(out['verified'],filename);self.assertEqual(out['scans'][-1]['clear'],clear)
   if filename=='origin-hidden-positive.bin':self.assertEqual(out['scans'][-1]['visible_enemies'],[])

class BinaryCommit(unittest.TestCase):
 def fixture(self):
  b=q.L.MissionCommitBody13()
  for key,index in [('controller',1),('lease',2),('formation',3),('parent_command',4),('parent_task',5)]:getattr(b,key)[:]=uid(index)
  parent_command=q.ident(list(b.parent_command));parent_task=q.ident(list(b.parent_task))
  b.command[:]=struct.unpack('<4I',uuid.uuid5(uuid.UUID(parent_command),'formation').bytes)
  b.task[:]=struct.unpack('<4I',uuid.uuid5(uuid.UUID(parent_task),'formation').bytes)
  b.seq=7;b.formation_version=1;b.front_id=100;b.support_id=101
  for key in ('module','purpose','allocation_scope','force_numerator','force_denominator','threat_clear'):setattr(b,key,1)
  for key,val in [('target_unit',0x12000),('target_id',201),('target_hash',2),('target_owner',0x22000),('target_template',0x32000),('button',0x42000),('button_schema',0x52000),('command_set',2),('target_observed_frame',20),('threat_frame',20),('reserve_start_frame',5),('reserve_deadline_frame',305),('hard_deadline_frame',4505),('combat_frames',60)]:setattr(b,key,val)
  b.visible_target[:]=[600,500,210];b.visibility_proof_sha256[0]=1
  prefix=bytes(b)[:252];digest=hashlib.sha256(prefix).digest();b.digest_sha256[:]=struct.unpack('<8I',digest)
  mr=dict(parent_command_id=parent_command,parent_task_id=parent_task,child_command_id=q.ident(list(b.command)),child_task_id=q.ident(list(b.task)),commit_body_hex=bytes(b).hex(),commit_prefix_hex=prefix.hex(),digest_sha256=digest.hex())
  body=q.plain(b);i={k:body[k] for k in ('controller','lease','formation','formation_version')}
  ctl=dict(reserve_start_frame=5,reserve_deadline_frame=305,hard_deadline_frame=4505,mission_commit_frame=20,approach_frame=20,lease_issued_frame=5)
  n=dict(owner=0x20000,controller_input=i,controller=ctl,slots=[dict(id=100),dict(id=101)],mission_commit=dict(generation=2,status=1,reason=0,ack_frame=20,body=body))
  e=dict(kind=153,seq=10,frame=20);z=[dict(event=e,sample=dict(frame=20))]
  es=[dict(kind=1,tag=1,frame=5,seq=1),dict(kind=1,tag=1,frame=6,seq=2),e,dict(kind=76,frame=20,seq=11,role=0),dict(kind=76,frame=20,seq=12,role=1)]
  return dict(native=n,events=es,mission_request=mr),z
 def test_actual_binary_prefix_seal(self):
  r,z=self.fixture();self.assertTrue(q.commit_audit(r,z)['verified'])
 def test_json_hash_is_not_the_binary_seal(self):
  r,z=self.fixture();r['mission_request']['digest_sha256']=hashlib.sha256(b'{}').hexdigest()
  self.assertFalse(q.commit_audit(r,z)['checks']['original_body_seal'])
 def test_changed_body_after_publication_rejected(self):
  r,z=self.fixture();r['native']['mission_commit']['body']['target_id']+=1
  self.assertFalse(q.commit_audit(r,z)['checks']['original_body_seal'])
 def test_second_generation_rejected(self):
  r,z=self.fixture();r['native']['mission_commit']['generation']=4
  self.assertFalse(q.commit_audit(r,z)['verified'])
 def test_parent_task_cannot_be_child_task(self):
  r,z=self.fixture();r['mission_request']['child_task_id']=r['mission_request']['parent_task_id']
  self.assertFalse(q.commit_audit(r,z)['checks']['separate_exact_parent_child_and_lease'])
 def test_commit_cannot_renew_deadline(self):
  r,z=self.fixture();r['native']['mission_commit']['body']['hard_deadline_frame']+=1
  self.assertFalse(q.commit_audit(r,z)['checks']['no_clock_renewal'])
 def test_rejected_commit_not_accepted_from_ready_bool(self):
  r,z=self.fixture();r['native']['mission_commit']['status']=2
  self.assertFalse(q.commit_audit(r,z)['verified'])
 def test_no_reborrow_during_dispatch(self):
  r,z=self.fixture();r['events'].append(dict(kind=1,tag=1,frame=21,seq=13))
  self.assertFalse(q.commit_audit(r,z)['checks']['same_lease_dispatch_no_reborrow'])

class TeamCohort(unittest.TestCase):
 def fixture(self):
  es=[];slots=[];inputs=[];script=0x51000
  for role in (0,1):
   specs=[(10,141,1,0x50000,0,0),(11,141,2,0x50000,0x50000,1)]
   if role==0:specs += [(12,142,1,0x52000,0x50000,2),(12,141,1,0x52000,0x50000,2),(13,141,2,0x52000,0x52000,1),(14,141,3,0x52000,0x52000,2),(14,144,3,0x52000,0x52000,3)]
   else:specs += [(12,141,3,0x50000,0x50000,2),(12,144,3,0x50000,0x50000,3)]
   source=[]
   for frame,k,arg,team,previous,count in specs:
    s=sample(frame,role);s.team=team;e=event(k,frame,role,arg,s=s);w=e['stack_words'];w[68:78]=[0x544d5034,team,0xb0000,s.owner,team,0xb0000,s.owner,frame,previous,count]
    w[78:88]=[0xc0000,50,0x20000,0xd0000,0x80d4ea1e,frame,bits(0),bits(0),bits(100),0xc4db60];w[7]=arg if k==141 else 2 if k==142 else 3
    es.append(e);source.append(q.plain(s))
   last=source[-1];first=source[-4] if role==0 else source[0];final_frame=last['frame']
   slots.append(dict(initial_factory_gap=0.,admission_first=first,admission_last=last,admitted_team=last['team'],cohort_count=3,cohort_first_frame=first['frame'],cohort_last_frame=final_frame,cohort_reset_count=int(role==0),borrow_frame=final_frame,completion_observed_frame=9,receipt=dict(completion_frame=9)))
   inputs.append(dict(factory=0xc0000,factory_id=50,factory_template=0xd0000))
   es.append(dict(kind=1,tag=1,role=role,frame=final_frame,team=script,seq=0))
  es.sort(key=lambda e:e['frame'])
  for seq,e in enumerate(es,1):e['seq']=seq
  n=dict(owner=0x20000,script_team=script,slots=slots,controller_input=dict(slots=inputs));r=dict(native=n,events=es)
  return r,[q.reserve_record(e) for e in es if e['kind'] in q.RS_KINDS]
 def test_owned_team_reset_uses_final_cohort_not_input_team(self):
  r,z=self.fixture();out=q.cohort_audit(r,z);self.assertTrue(out['verified'],out['checks']);self.assertEqual(out['roles'][0]['frames'],[12,13,14])
 def test_team_reset_does_not_reset_hp_baseline(self):
  r,z=self.fixture();one=next(x for x in z if x['event']['role']==0 and x['event']['kind']==141 and x['sample']['frame']==13);one['sample']['hp']-=1
  self.assertFalse(q.cohort_audit(r,z)['checks']['immutable_first_baseline'])
 def test_foreign_owner_cannot_get_team_reset_credit(self):
  r,z=self.fixture();one=next(x for x in z if x['event']['kind']==142);one['team'][6]+=4
  self.assertFalse(q.cohort_audit(r,z)['checks']['actual_team_chain_and_cohort'])

 def test_reset_missing_actual_frame_fails(self):
  r,z=self.fixture();one=next(x for x in z if x['event']['role']==0 and x['event']['kind']==141 and x['sample']['frame']==13);one['sample']['frame']=14
  self.assertFalse(q.cohort_audit(r,z)['checks']['actual_team_chain_and_cohort'])

class ProducerLoadedEntries(unittest.TestCase):
 def fixture(self):
  # Software-only RPM representation; original frozen producer file/source used.
  r,_=ActualCppTransport.fixture(self);n=r['native'];i=n['controller_input'];h=q.L.ProductionHeader13()
  for k in ('pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high'):setattr(h,k,i['producer_'+k])
  h.session[:]=i['producer_session'];h.commander[:]=i['producer_commander'];h.magic=0x50434d44;h.version=1;h.phase=1;h.callback_thread=h.thread;h.reserve_floor=1000;h.total_budget=305;h.heartbeat=1000;h.count=0
  expected={k:i['producer_'+k] for k in ('pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high')};s=i['slots'][0]
  expected.update(command_id=q.ident(s['command']),task_id=q.ident(s['task']),seq=s['seq'],unit='conscript',cost=85,factory=s['factory'],factory_id=s['factory_id'],iface=s['iface'],object=0,object_id=0)
  runtime=dict(owner_vtable=0xc5bce0,player_index=3,player_template=h.player_template,ai=h.ai,ai_vtable=0xc60f60,ai_owner=h.owner,ai_owner_second=h.owner,personality=h.personality,personality_id=h.personality_id,logic=n['logic'],frame=100)
  path=P.parent.parent/'production/persistent/bin-v2/ProductionPersistent.dll';data=path.read_bytes();nt=struct.unpack_from('<I',data,0x3c)[0];size=struct.unpack_from('<I',data,nt+80)[0];base=0x50000000
  source=(P.parent.parent/'production/persistent/executor.cpp').read_text();block=source.split('static Hook hooks[]={',1)[1].split(';',1)[0];entries=[]
  for num,(address,escaped,length) in enumerate(q.re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block)):
   address=int(address,0);original=bytes.fromhex(escaped.replace('\\x',''));target=base+0x1000+num*16;actual=b'\xe9'+struct.pack('<i',target-address-5)+original[5:]
   entries.append(dict(address=hex(address),expected=original.hex(),length=int(length),actual=actual.hex(),jump_target=hex(target)))
  r['producer_readonly_at_arm']=dict(protocol='mf15_running_producer_readonly_at_arm_v1',pid=n['pid'],mutations=False,sdk_calls=0,game_memory_writes=False,header_before_hex=bytes(h).hex(),header_after_hex=bytes(h).hex(),tick_before=1000,tick_after=1001,runtime=runtime,expected=expected,loaded=dict(module_path=str(path.resolve()),module_sha256=hashlib.sha256(data).hexdigest(),module_base=hex(base),pe_offset=nt,image_size=size,entries=entries),reader_sha256=hashlib.sha256((P/'producer_binding.py').read_bytes()).hexdigest(),running_helper_sha256=hashlib.sha256((P.parent/'running_birth_source_v1.py').read_bytes()).hexdigest())
  return r
 def test_count_zero_is_valid_before_prebound_orders(self):
  out=q.producer_arm_audit(self.fixture());self.assertTrue(out['verified'],out['checks']);self.assertFalse(out['actor_admission_credit'])
 def test_running_service_5000_budget_not_pair_spend(self):
  r=self.fixture();a=r['producer_readonly_at_arm']
  for key in ('header_before_hex','header_after_hex'):
   h=q.L.ProductionHeader13.from_buffer_copy(bytes.fromhex(a[key]));h.total_budget=5000;h.spent=2500;h.reserve_floor=500;a[key]=bytes(h).hex()
  self.assertTrue(q.producer_arm_audit(r)['verified'])
 def test_e9_to_another_module_rejected(self):
  r=self.fixture();e=r['producer_readonly_at_arm']['loaded']['entries'][0];addr=int(e['address'],0);raw=bytes.fromhex(e['actual']);e['actual']=(b'\xe9'+struct.pack('<i',0x60000000-addr-5)+raw[5:]).hex();e['jump_target']=hex(0x60000000)
  self.assertFalse(q.producer_arm_audit(r)['checks']['all_five_actual_installed_entries'])

 def test_callback_zero_not_an_actual_thread_observation(self):
  r=self.fixture();a=r['producer_readonly_at_arm'];h=q.L.ProductionHeader13.from_buffer_copy(bytes.fromhex(a['header_before_hex']));h.callback_thread=0;a['header_before_hex']=bytes(h).hex()
  self.assertFalse(q.producer_arm_audit(r)['verified'])

 def test_expired_header_cannot_be_fixed_by_later_header(self):
  r=self.fixture();r['producer_readonly_at_arm']['tick_before']=4001
  self.assertFalse(q.producer_arm_audit(r)['checks']['header_before_hex'])

 def test_arm_does_not_preclaim_receipt_actor(self):
  r=self.fixture();r['producer_readonly_at_arm']['expected']['object']=0x12000
  self.assertFalse(q.producer_arm_audit(r)['checks']['exact_arm_command_and_process'])

 def test_three_original_bytes_and_bad_tail_rejected(self):
  r=self.fixture();e=next(e for e in r['producer_readonly_at_arm']['loaded']['entries'] if e['length']>5);raw=bytearray.fromhex(e['actual']);raw[-1]^=1;e['actual']=raw.hex()
  self.assertFalse(q.producer_arm_audit(r)['checks']['all_five_actual_installed_entries'])


class ParentEnvelope(unittest.TestCase):
 def fixture(self):
  r,_=BinaryCommit.fixture(self);n=r['native'];b=n['mission_commit']['body'];mr=r['mission_request'];session=q.ident(uid(99));commander=q.ident(uid(100));n.update(session_id=session,commander_id=commander);r['session_id']=session
  native=str(uuid.uuid5(uuid.UUID(q.ident(b['controller'])),'paid_pair'));fid='formation_'+uuid.UUID(native).hex[:16];b['formation']=list(struct.unpack('<4I',uuid.UUID(native).bytes))
  public=dict(command_id=mr['parent_command_id'],task_id=mr['parent_task_id'],seq=b['seq'],session_id=session,commander_id=commander,player_id=3,module='combined_arms',purpose='coordinate_force',formation_ids=[fid],formation_versions=[[fid,1]],required_roles=['infantry','anti_air'],force_fraction=1,target_contact_id='contact_own_fov',expires_frame=4505)
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);path=Path(temp.name)/'original-public.json';raw=json.dumps(public).encode();path.write_bytes(raw)
  mr.update(public_command=public,public_command_path=str(path),public_command_sha256=hashlib.sha256(raw).hexdigest(),native_formation_uuid=native,contact_id='contact_own_fov',formation=dict(formation_id=fid,version=1,roles={'infantry':1,'anti_air':1},region_id='region_1_1',available=True))
  return r
 def test_original_parent_envelope_not_model_http_proof(self):
  out=q.parent_request_audit(self.fixture());self.assertTrue(out['verified'],out['checks']);self.assertFalse(out['model_http_origin_verified'])
 def test_original_32hex_parent_task_is_uuid_equivalent_without_rewriting(self):
  r=self.fixture();mr=r['mission_request'];public=mr['public_command'];public['task_id']=uuid.UUID(public['task_id']).hex;public['command_id']=uuid.UUID(public['command_id']).hex
  data=json.dumps(public).encode();Path(mr['public_command_path']).write_bytes(data);mr['public_command_sha256']=hashlib.sha256(data).hexdigest();before=copy.deepcopy(r)
  self.assertTrue(q.parent_request_audit(r)['verified']);self.assertEqual(r,before);self.assertEqual(len(public['task_id']),32)
 def test_public_file_echo_alone_does_not_bind(self):
  r=self.fixture();r['mission_request']['public_command']['force_fraction']=.5
  self.assertFalse(q.parent_request_audit(r)['verified'])
 def test_other_controller_formation_id_rejected(self):
  r=self.fixture();r['mission_request']['formation']['formation_id']='formation_wrong'
  self.assertFalse(q.parent_request_audit(r)['checks']['registered_public_formation'])
 def test_public_descriptor_cannot_hide_private_actor_id(self):
  r=self.fixture();r['mission_request']['formation']['object_ids']=[100,101]
  self.assertFalse(q.parent_request_audit(r)['checks']['registered_public_formation'])
 def test_force_true_is_not_fraction_one(self):
  r=self.fixture();r['mission_request']['public_command']['force_fraction']=True
  self.assertFalse(q.parent_request_audit(r)['checks']['exact_combined_arms_public_request'])
 def test_parent_task_not_outer_lease(self):
  r=self.fixture();r['mission_request']['public_command']['task_id']=q.ident(r['native']['mission_commit']['body']['lease'])
  self.assertFalse(q.parent_request_audit(r)['checks']['parent_process_session_and_sequence'])
 def test_earlier_parent_deadline_not_extended_to_controller(self):
  r=self.fixture();r['mission_request']['public_command']['expires_frame']-=1
  self.assertFalse(q.parent_request_audit(r)['checks']['original_parent_deadline_is_existing_lease_hard'])
 def test_later_parent_deadline_cannot_renew_lease(self):
  r=self.fixture();r['mission_request']['public_command']['expires_frame']+=1
  self.assertFalse(q.parent_request_audit(r)['checks']['original_parent_deadline_is_existing_lease_hard'])

class PaidReceiptMath(unittest.TestCase):
 """New synthetic receipt words, not patched field evidence or an SDK grant."""
 def fixture(self):
  r,_=ActualCppTransport.fixture(self);n=r['native'];i=n['controller_input'];es=[]
  for role in (0,1):
   h=q.L.ProductionHeader13();h.magic=0x50434d44;h.version=1;h.phase=1;h.count=2;h.total_budget=5000;h.spent=305;h.reserve_floor=1000;h.heartbeat=1000
   for k in ('pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high'):setattr(h,k,i['producer_'+k])
   h.callback_thread=h.thread;h.session[:]=i['producer_session'];h.commander[:]=i['producer_commander']
   p=q.L.ProductionReceipt13();s=i['slots'][role];p.version=1;p.command.seq=s['seq'];p.command.id[:]=s['command'];p.command.task[:]=s['task'];p.command.session[:]=i['producer_session'];p.command.commander[:]=i['producer_commander']
   p.command.hash=s['unit_hash'];p.command.budget=1000;p.command.reserve=1000;p.command.expires=500;p.command.queue_limit=2;p.command.factory=s['factory'];p.command.factory_id=s['factory_id'];p.command.iface=s['iface']
   p.state=2;p.attempted=p.preserved=p.created=p.completed=p.live_samples=p.debit_count=1;p.frame=90;p.completion_frame=99;p.queue_id=100+role;p.node=0x22000+role*4;p.object=n['slots'][role]['thing'];p.object_id=n['slots'][role]['id'];p.object_owner=n['owner'];p.object_hash=s['unit_hash'];p.cost=p.quoted_cost=p.paid=q.COSTS[role];p.cash=1000+p.cost
   for copy_index in (1,2):
    w=[0x52504331,1,role,100,role,100,100,role+1]+raw(h)+raw(p);es.append(dict(kind=140,role=role,arg=copy_index,seq=len(es)+1,frame=100,tick=1000,stack_words=w,stack_word_count=128))
   n['slots'][role].update(receipt=q.plain(p),receipt_version=1,receipt_index=role,receipt_observed_frame=100,completion_observed_frame=100)
  n['controller']['producer_snapshots']=2;r['events']=es
  return r
 def test_exact_305_pair_inside_running5000_service(self):
  r=self.fixture();out=q.producer_audit(r);self.assertTrue(out['verified'],out['checks'])
  self.assertEqual(sum(x['receipt']['paid'] for x in out['observations']),305)
 def test_one_cash_below_preserved_reserve_rejected(self):
  r=self.fixture()
  for e in r['events'][:2]:e['stack_words'][72+q.L.ProductionReceipt13.cash.offset//4]-=1
  self.assertFalse(q.producer_audit(r)['checks']['paid_original_receipts'])
 def test_other_service_spend_not_added_to_pair(self):
  r=self.fixture()
  for e in r['events']:
   h=q.L.ProductionHeader13.from_buffer_copy(struct.pack('<64I',*e['stack_words'][8:72]));h.spent=4000;e['stack_words'][8:72]=raw(h)
  self.assertTrue(q.producer_audit(r)['checks']['paid_original_receipts'])
 def test_pair_price_cannot_be_credited_as_service_budget(self):
  r=self.fixture()
  for e in r['events'][:2]:e['stack_words'][72+q.L.ProductionReceipt13.paid.offset//4]+=1
  self.assertFalse(q.producer_audit(r)['checks']['paid_original_receipts'])

class OriginalBorrowBoundary(unittest.TestCase):
 def fixture(self):
  s=q.plain(sample(14));w=[0]*128;w[:6]=[0x53544e31,1,5,0,14,14];w[6]=s['thing'];w[7]=s['id'];w[9]=s['owner'];w[10]=s['update'];w[13:19]=[s['stance_module'],s['stance_vtable'],s['stance_backref'],s['stance_data'],s['stance_enum_list'],s['stance_enum_count']];w[19:27]=s['stance_enum_entries'];w[64]=14
  es=[]
  for seq,k in enumerate((144,132,14,18,19,15,1),1):
   es.append(dict(kind=k,seq=seq,frame=14,role=0,tag=0 if k in (144,132) else 1,team=s['team'] if k in (144,132,14) else 0x51000,arg=0x25104 if k in (18,19) else 0,caller=0x838877 if k==18 else 0,unit_id=s['id'],owner=s['owner'],thread=7,own_hp=100.,target_id=0,target_visible=0))
  es[1].update(stack_words=w,stack_word_count=68)
  slot=dict(id=s['id'],admission_last=s,admitted_team=s['team'],borrow_frame=14)
  n=dict(owner=s['owner'],ai=0x25000,script_team=0x51000,thread=7,slots=[slot,{}],stances=[dict(capture_frame=14,original_enum=0,module=s['stance_module']),{}],detach_calls=1)
  return dict(native=n,events=es)
 def test_normal_transfer_and_remove_are_original_borrow(self):
  out=q.borrow_boundary(self.fixture(),0);self.assertTrue(out['verified']);self.assertEqual(out['borrow_seq'],7)
 def test_passive_tag0_transfer_never_own_credit(self):
  r=self.fixture();r['events'][2]['tag']=0
  self.assertFalse(q.borrow_boundary(r,0)['verified'])
 def test_missing_capture_cannot_be_filled_from_header(self):
  r=self.fixture();r['events'].pop(1)
  self.assertFalse(q.borrow_boundary(r,0)['verified'])
 def test_actual_borrow_team_must_be_script(self):
  r=self.fixture();r['events'][-1]['team']+=4
  self.assertFalse(q.borrow_boundary(r,0)['verified'])
 def test_before_transfer_team_is_final_admitted_team(self):
  r=self.fixture();r['events'][2]['team']+=4
  self.assertFalse(q.borrow_boundary(r,0)['verified'])
 def test_precommit_unknown_attack_never_a_model_order(self):
  r=self.fixture();r['events'].append(dict(kind=34,tag=0,role=0,seq=8,target_id=0,target_visible=0))
  self.assertFalse(q.precommit_audit(r)['checks']['no_controlled_attack_before_model'])

class IncrementalFacts(unittest.TestCase):
 def test_empty_prefix_is_waiting(self):
  out=q.live_facts({});self.assertFalse(out['verified']);self.assertEqual(out['claims'],[]);self.assertFalse(out['tactical_source_granted'])
 def test_one_role_cohort_does_not_require_future_peer(self):
  r,z=TeamCohort.fixture(self);r['events']=[e for e in r['events'] if e['role']==0];z=[x for x in z if x['event']['role']==0]
  self.assertTrue(q.cohort_audit(r,z,roles=(0,))['verified'])
  self.assertFalse(q.cohort_audit(r,z)['verified'])
 def test_one_role_original_paid_source_without_peer_receipt(self):
  r=PaidReceiptMath.fixture(self);r['events']=[e for e in r['events'] if e['role']==0];r['native']['controller']['producer_snapshots']=1
  self.assertTrue(q.producer_audit(r,roles=(0,))['verified'])
  self.assertFalse(q.producer_audit(r)['verified'])
 def test_first_real_borrow_clock_does_not_wait_second(self):
  r,z=FrozenClock.fixture(self);r['events']=r['events'][:1]
  self.assertTrue(q.clock_audit(r,z,require_pair=False)['verified'])
  self.assertFalse(q.clock_audit(r,z)['verified'])
 def test_half_producer_pair_does_not_acquire_claim(self):
  r=PaidReceiptMath.fixture(self);r['events']=r['events'][:1];r['native']['controller']['producer_snapshots']=1
  self.assertFalse(q.producer_audit(r,roles=(0,))['verified'])
 def test_sdk_stub_event1_is_not_a_complete_borrow(self):
  r,_=ActualCppTransport.fixture(self)
  self.assertFalse(q.borrow_boundary(r,0)['verified'])
 def test_header_masks_cannot_manufacture_live_claim(self):
  r=ProducerLoadedEntries.fixture(self);n=r['native'];r['controller_input']=copy.deepcopy(n['controller_input']);r['request']={k:n[k] for k in ('command_id','task_id','seq','token')};n['controller'].update(held_mask=3,ready_mask=3)
  out=q.live_facts(r);self.assertFalse(out['verified']);self.assertEqual(out['claims'],[]);self.assertFalse(out['ready']['verified']);self.assertTrue(out['source_pins_required'])

class SplitPaymentsAndWaitDiagnostics(unittest.TestCase):
 def test_split_positive_charges_are_paid_provenance_not_actor_admission(self):
  r=PaidReceiptMath.fixture(self)
  for e in r['events']:
   role=e['role'];e['stack_words'][72+q.L.ProductionReceipt13.debit_count.offset//4]=[60,90][role]
  for role in (0,1):r['native']['slots'][role]['receipt']['debit_count']=[60,90][role]
  out=q.producer_audit(r);self.assertTrue(out['verified'],out['checks'])
  self.assertEqual(out['scope'],'historical_paid_provenance_not_current_actor_admission')
 def test_zero_or_more_charges_than_paid_is_not_valid(self):
  for count in (0,86):
   r=PaidReceiptMath.fixture(self)
   for e in r['events'][:2]:e['stack_words'][72+q.L.ProductionReceipt13.debit_count.offset//4]=count
   self.assertFalse(q.producer_audit(r)['checks']['paid_original_receipts'])
 def test_actual_phase2_split_receipts_are_not_running_source(self):
  data=(P/'actual-split-payment-receipts.bin').read_bytes();self.assertEqual(len(data),704)
  h=q.plain(q.L.ProductionHeader13.from_buffer_copy(data[:256]));self.assertEqual((h['magic'],h['version'],h['phase']),(0x50434d44,1,2))
  receipts=[q.plain(q.L.ProductionReceipt13.from_buffer_copy(data[256+k*224:480+k*224])) for k in (0,1)]
  self.assertEqual([(p['debit_count'],p['paid'],p['cost'],p['payment_error']) for p in receipts],[(60,85,85,0),(90,220,220,0)])
  self.assertTrue(all(1<=p['debit_count']<=p['paid'] for p in receipts))
 def wait_fixture(self):
  t=q.L.Tactical.from_buffer_copy((P/'controller-producer-wait.bin').read_bytes());n=q.plain(q.L.Header.from_buffer_copy(bytes(t)[:31148]))
  return dict(native=n,events=[q.plain(e) for e in t.events[:t.count]])
 def test_actual_cpp_failed_payment_pair_is_diagnostic_only(self):
  r=self.wait_fixture();out=q.producer_wait_audit(r);self.assertTrue(out['verified'],out['checks']);self.assertTrue(out['observed'])
  self.assertEqual(len(out['records']),1);self.assertEqual(out['records'][0]['reason'],9)
  self.assertTrue(out['records'][0]['independently_decisive_raw_witness']);self.assertFalse(out['records'][0]['paid_or_admission_credit']);self.assertFalse(out['source_authority_granted']);self.assertFalse(out['all_failures_covered'])
  self.assertFalse(q.producer_audit(r)['verified'])
 def test_unclosed_wait_pair_rejected(self):
  r=self.wait_fixture();r['events'].pop();self.assertFalse(q.producer_wait_audit(r)['verified'])
 def test_wrong_wait_flags_or_counter_or_link_rejected(self):
  for pos,value in ((6,15),(5,0),(4,8)):
   r=self.wait_fixture();r['events'][1]['stack_words'][pos]=value
   self.assertFalse(q.producer_wait_audit(r)['verified'])
 def test_read_failure_never_claims_complete_raw_witness(self):
  r=self.wait_fixture()
  for e in r['events']:
   e['arg']=2;e['stack_words'][4]=2;e['stack_words'][6]=0;e['stack_words'][7]=0xffffffff
  out=q.producer_wait_audit(r);self.assertTrue(out['verified']);self.assertIsNone(out['records'][0]['independently_decisive_raw_witness']);self.assertTrue(out['records'][0]['read_failure_is_not_a_complete_raw_capture'])

class PassiveSpawnWait(unittest.TestCase):
 def fixture(self,frame=10):
  s=sample(frame);s.state_id=7;s.state_vtable=0xc57a68;s.source=2;s.height_flags=1;s.path=0x100000;s.sm_flags=65536
  body=event(163,frame,arg=0,seq=2,s=s);wait=event(166,frame,arg=1,seq=3,s=s)
  for e in (body,wait):
   e.update(tag=0,thread=7,owner=s.owner,tick=1000);w=e['stack_words'];w[5]=1;w[7]=0;w[92]=0;w[97:99]=[9,9];w[78:88]=[0x11000,765,s.owner,0x12000,0x80d4ea1e,frame,bits(10),bits(10),bits(1000),0xc4db60]
  slot=dict(thing=s.thing,id=s.id,template_ptr=s.template_ptr,update=s.update,receipt=dict(completion_frame=9),receipt_observed_frame=9,completion_observed_frame=9)
  spec=dict(unit_hash=q.TYPES[0],factory=0x11000,factory_id=765,factory_template=0x12000)
  n=dict(owner=s.owner,thread=7,script_team=0x51000,slots=[slot,{}],controller=dict(reserve_start_frame=0,reserve_deadline_frame=0,hard_deadline_frame=0),controller_input=dict(startup_deadline_frame=900,startup_wall_ms=60000,slots=[spec,{}]))
  return dict(native=n,events=[dict(kind=0,seq=1,frame=frame-1,tick=980,role=0,tag=0),body,wait])
 def audit(self,r):return q.spawn_wait_audit(r,[q.reserve_record(e) for e in r['events'] if e['kind'] in q.RS_KINDS])
 def test_exact_spawn_wait_keeps_positive_ground_and_admission_false(self):
  r=self.fixture();out=self.audit(r);self.assertTrue(out['verified'],out['checks']);self.assertFalse(out['admission_authority_granted']);self.assertFalse(out['records'][0]['positive_ground_verified'])
  s=q.reserve_record(r['events'][-1])['sample'];self.assertFalse(q.surface(s,s,s['owner']));self.assertFalse(q.holding(s,s,s['owner'],r['native']['script_team']))
 def test_wrong_spawn_shape_does_not_become_passive_wait(self):
  for key,value in (('height_flags',0),('state_vtable',0xc55130),('source',1),('holder',4),('hp',79.),('sm_flags',65537)):
   r=self.fixture();z=q.reserve_record(r['events'][-1]);s=z['sample'];s[key]=value
   self.assertFalse(q.passive_wait_predicate(s,0,s['owner'],r['native']['script_team'])['exact_spawn_wait'],key)
 def test_only_original_known_ground_states_can_use_reason2(self):
  r=self.fixture();e=r['events'][-1];e['arg']=e['stack_words'][6]=2;e['stack_words'][8+q.L.ReserveSample13.height_flags.offset//4]=4
  # Fixed body and decision must contain the same unmodified Sample.
  r['events'][1]['stack_words'][8:68]=e['stack_words'][8:68]
  self.assertTrue(self.audit(r)['verified'])
  e['stack_words'][8+q.L.ReserveSample13.state_id.offset//4]=95;r['events'][1]['stack_words'][8:68]=e['stack_words'][8:68]
  self.assertFalse(self.audit(r)['verified'])
 def test_wait_is_never_a_replacement_for_three_cohort_frames(self):
  r=self.fixture();r['native']['slots'][0]['admission_last']=q.reserve_record(r['events'][-1])['sample']
  out=q.cohort_audit(r,[q.reserve_record(e) for e in r['events'] if e['kind'] in q.RS_KINDS],roles=(0,))
  self.assertFalse(out['verified']);self.assertFalse(out['checks']['exact_final_three'])
 def test_wait_after_first_positive_baseline_or_own_sdk_rejected(self):
  r=self.fixture();e=event(141,9,arg=1,seq=0);r['events'].insert(1,e);self.assertFalse(self.audit(r)['checks']['no_cohort_or_sdk_credit'])
  r=self.fixture();r['events'].insert(1,dict(kind=30,role=0,seq=1,tag=4));self.assertFalse(self.audit(r)['checks']['no_cohort_or_sdk_credit'])
 def test_age_and_startup_clock_are_not_renewed(self):
  self.assertFalse(self.audit(self.fixture(310))['checks']['unchanged_age_factory_and_clocks'])
  r=self.fixture();r['events'][-1]['stack_words'][93:96]=[1,301,4501];self.assertFalse(self.audit(r)['checks']['unchanged_age_factory_and_clocks'])
 def test_peer_wait_uses_existing_global_clock_after_first_borrow(self):
  r=self.fixture();r['native']['controller'].update(reserve_start_frame=1,reserve_deadline_frame=301,hard_deadline_frame=4501);r['native']['controller_input']['startup_deadline_frame']=5
  r['events'][0].update(frame=0,tick=0);r['events'][1]['seq']=3;r['events'][2]['seq']=4
  for e in r['events'][1:]:e['stack_words'][93:96]=[1,301,4501]
  freeze=event(145,1,role=1,arg=0,seq=2);freeze.update(tick=900,tag=0);r['events'].insert(1,freeze)
  self.assertTrue(self.audit(r)['verified'])
 def test_missing_fixed_body_or_team_owner_proof_rejected(self):
  r=self.fixture();r['events'].pop(1);self.assertFalse(self.audit(r)['checks']['original_fixed_sample'])
  r=self.fixture();r['events'][-1]['stack_words'][71]+=4;self.assertFalse(self.audit(r)['checks']['original_team_owner_chain'])
 def test_real_cpp_wait_component_preserves_missing_field_scope(self):
  t=q.L.Tactical.from_buffer_copy((P/'controller-spawn-wait.bin').read_bytes());e=q.plain(next(x for x in t.events[:t.count] if x.kind==166));z=q.reserve_record(e);s=z['sample']
  out=q.passive_wait_predicate(s,e['role'],t.owner,t.script_team);self.assertTrue(out['exact_spawn_wait']);self.assertFalse(out['positive_ground_verified']);self.assertFalse(out['admission_authority_granted'])
  self.assertFalse(q.surface(s,s,t.owner));self.assertEqual(e['stack_word_count'],128)

class AggregateCallBindings(unittest.TestCase):
 def test_every_aggregate_argument_tuple_binds_real_signature(self):
  tree=ast.parse(inspect.getsource(q.audit));loops=[x for x in ast.walk(tree) if isinstance(x,ast.For) and isinstance(x.iter,ast.List)]
  self.assertEqual(len(loops),1)
  for item in loops[0].iter.elts:
   name=item.elts[1].id;args=item.elts[2].elts
   inspect.signature(getattr(q,name)).bind(*[{} if a.id=='r' else [] for a in args])
 def test_real_precommit_function_runs_inside_aggregate(self):
  accepted=event(153,12,arg=0,seq=3)
  r=dict(events=[dict(kind=14,tag=1,role=0,seq=1,target_id=0,target_visible=0),dict(kind=14,tag=1,role=1,seq=2,target_id=0,target_visible=0),accepted])
  out=q.audit(r);self.assertFalse(out['verified']);self.assertTrue(out['precommit']['verified'],out['precommit']);self.assertFalse(out['tactical_source_granted'])

if __name__=='__main__':unittest.main()
