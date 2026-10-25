"""Independent MFM8 raw pending-Command lineage audit; no game access or grant.

Only a complete own copy/unpack/dispatch/private chain can explain a tag-zero
Move. Equal goals, callers, counters and a native accepted flag cannot do so.
"""
import math,struct
PROOF_KINDS=set(range(110,121))
SCALARS=('generation','step','issued_frame','mission_stage','goal_kind','goal_event_seq','slot','input_command','output_command','copy_caller','unpack_caller','dispatch_caller','private_caller','delivered','role','invalid_reason','own_facade_seq','private_seq','observed_this','observed_thing','observed_command')
COPY_CALLER=0x787d42
UNPACK_CALLER=0x7da0b3
DISPATCH_CALLER=0x7da0d9
PRIVATE_CALLER=0x6d3b7d

def num(v):return int(v,0) if isinstance(v,str) else v
def uint(v):return type(v) is int and 0<=v<=0xffffffff
def words(v,n):return isinstance(v,list) and len(v)==n and all(uint(x) for x in v)
def point(v):return isinstance(v,(list,tuple)) and len(v)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in v)
def bits(v):return struct.unpack('<I',struct.pack('<f',v))[0]
def exact(a,b):return point(a) and point(b) and all(bits(x)==bits(y) for x,y in zip(a,b))

def pure_move(command,goal):
 return words(command,23) and point(goal) and command[0:2]==[0,1] and command[2:5]==[bits(x) for x in goal] and all(command[i]==0 for i in (5,6,7,8,9,11,12,13,15,16,17,18,20,21)) and command[22]&255==1

def mapped(command,stored):
 return words(command,23) and words(stored,24) and command[:6]==stored[:6] and command[6]==stored[6]==stored[7]==0 and command[7:10]==stored[8:11] and command[11:14]==stored[12:15] and command[15:19]==stored[16:20] and command[20]==stored[21] and command[21]==stored[22] and command[22]&255==stored[23]&255

def audit(report):
 try:return _audit(report)
 except (KeyError,TypeError,ValueError,IndexError,OverflowError,struct.error):
  return dict(verified=False,observed=True,field_verified=False,accepted=[],accepted_private_sequences=[],checks={'well_formed_raw_lineage':False})

def _audit(report):
 ev=report.get('events',[]);proofs=[e for e in ev if e.get('kind') in PROOF_KINDS];byseq={e.get('seq'):e for e in ev};pre=report.get('preflight',{});groups={};checks=dict(typed_unique_proofs=True,every_ticket_valid=True,unique_private_delivery=True);results=[];accepted=[]
 for e in proofs:
  p=e.get('lineage',{});key=(e.get('role'),p.get('generation'))
  good=e.get('role') in (0,1) and all(uint(p.get(k)) for k in SCALARS) and all(words(p.get(k),size) for k,size in (('command',23),('stored_before',24),('stored_after',24),('unpacked',23),('observed_slot',24))) and uint(p.get('generation')) and 0<p['generation']<=160 and p.get('step')==e['kind'] and p.get('role')==e['role'] and type(e.get('seq')) is int and byseq.get(e['seq']) is e
  checks['typed_unique_proofs'] &= good
  groups.setdefault(key,[]).append(e)
 for (role,generation),rows in groups.items():
  p=rows[0].get('lineage',{});facade=byseq.get(p.get('own_facade_seq'));marker=byseq.get(p.get('goal_event_seq'));goal=p.get('goal');issued=p.get('issued_frame');stage=p.get('mission_stage');u=pre.get('support' if role else 'selected',{});parts={k:[e for e in rows if e['kind']==k] for k in PROOF_KINDS};case={}
  case['own_frozen_ticket']=bool(role in (0,1) and facade and marker and facade.get('kind')==50 and facade.get('tag')==6 and facade.get('arg')==1 and facade.get('role')==role and facade.get('frame')==issued and facade.get('mission_stage')==stage in (1,3) and marker.get('kind')==p.get('goal_kind') in (81,85,92,95) and marker.get('role')==role and marker.get('mission_stage')==stage and marker['seq']<facade['seq'] and exact(facade.get('command_xyz'),goal))
  frozen=('generation','issued_frame','mission_stage','goal_kind','goal_event_seq','slot','role','own_facade_seq')
  case['same_actual_actor_generation_phase_goal']=all(all(e['lineage'].get(k)==p.get(k) for k in frozen) and exact(e['lineage'].get('goal'),goal) and e.get('role')==role and e.get('unit_id')==u.get('object_id') and e.get('owner')==num(pre.get('owner')) and e.get('thread')==pre.get('window_thread') and e.get('mission_stage')==stage and e['lineage'].get('slot')==num(u.get('ai_address'))+0x310 for e in rows)
  case['single_own_dispatch_scope']=len(parts[110])==len(parts[120])==len(parts[119])==1
  if not case['single_own_dispatch_scope']:
   results.append(dict(role=role,generation=generation,verified=False,checks=case));continue
  begin,dispatch,finish=parts[110][0],parts[120][0],parts[119][0];command=dispatch['lineage'].get('command');input_pointer=dispatch['lineage'].get('input_command');own_ends=[e for e in ev if facade and e.get('role')==role and e.get('kind')==51 and e.get('tag')==6 and facade['seq']<e['seq']<finish['seq']]
  case['actual_own_command_and_facade_scope']=bool(facade and facade['seq']<begin['seq']<dispatch['seq']<finish['seq'] and begin['frame']==dispatch['frame']==finish['frame']==issued and pure_move(command,goal) and uint(input_pointer) and input_pointer>0 and len(own_ends)==1 and own_ends[0].get('arg')==1 and own_ends[0].get('frame')==issued and exact(own_ends[0].get('command_xyz'),goal))
  case['observed_own_facade_dispatch_arguments']=all(e['lineage'].get('observed_this')==num(u.get('ai_address'))+0x24 and e['lineage'].get('observed_thing')==0 and e.get('tag')==6 for e in (begin,dispatch,finish)) and uint(begin['lineage'].get('observed_command')) and begin['lineage']['observed_command']>0 and begin['lineage'].get('observed_command')==finish['lineage'].get('observed_command') and dispatch['lineage'].get('observed_command')==input_pointer
  copied=bool(parts[111] or parts[112]);delayed=bool(copied or any(parts[k] for k in (113,114,115,116,117)))
  if not delayed:
   case['no_unearned_deferred_credit']=not any(parts[k] for k in (111,112,113,114,115,116,117))
   valid=all(v is True for v in case.values());results.append(dict(role=role,generation=generation,observed=False,verified=valid,checks=case));continue
  required=(111,112,113,114,115,116,117);case['one_complete_copy_consume_delivery']=all(len(parts[k])==1 for k in required)
  if not case['one_complete_copy_consume_delivery']:
   results.append(dict(role=role,generation=generation,observed=True,verified=False,checks=case));continue
  before,after,unpack_before,unpack_after,consumer,credit,consumer_end=[parts[k][0] for k in required];a=after['lineage'];b=before['lineage'];out=unpack_after['lineage'];private=byseq.get(credit['lineage'].get('private_seq'));done_candidates=[e for e in ev if private and e.get('kind')==11 and e.get('role')==role and private['seq']<e['seq']<consumer_end['seq']];done=done_candidates[0] if len(done_candidates)==1 else None
  order=[begin,dispatch,before,after,own_ends[0] if len(own_ends)==1 else {},finish,unpack_before,unpack_after,consumer,private or {},credit,done or {},consumer_end]
  case['strict_actual_nested_order']=all(type(e.get('seq')) is int for e in order) and all(x['seq']<y['seq'] for x,y in zip(order,order[1:]))
  active=[e for e in rows if begin['seq']<=e['seq']<=consumer_end['seq']]
  case['original_250_frame_deadline']=type(issued) is int and all(type(e.get('frame')) is int and 0<=e['frame']-issued<=250 and type(facade.get('mission_deadline_frame')) is int and e['frame']<facade['mission_deadline_frame'] for e in active) and all(e.get('mission_deadline_frame')==facade.get('mission_deadline_frame')==report.get('native',{}).get('mission_deadline_frame') for e in active)
  case['copy_live_input_not_same_goal']=all(e['lineage'].get('input_command')==input_pointer and e['lineage'].get('command')==command and e['lineage'].get('copy_caller')==COPY_CALLER and e['lineage'].get('observed_this')==p.get('slot') and e['lineage'].get('observed_command')==input_pointer and e['lineage'].get('observed_thing')==0 and e.get('tag')==6 for e in (before,after)) and b.get('observed_slot')==b.get('stored_before') and words(b.get('stored_before'),24) and a.get('stored_before')==b.get('stored_before') and a.get('observed_slot')==a.get('stored_after') and mapped(command,a.get('stored_after')) and b['stored_before']!=a['stored_after'] and b['stored_before'][0]==0xffffffff
  case['exact_original_stored_bytes_before_consume']=unpack_before['lineage'].get('observed_slot')==a.get('stored_after') and all(e['lineage'].get('stored_before')==a.get('stored_before') and e['lineage'].get('stored_after')==a.get('stored_after') and e['lineage'].get('command')==command and e['lineage'].get('input_command')==input_pointer and e['lineage'].get('copy_caller')==COPY_CALLER for e in (finish,unpack_before,unpack_after,consumer,credit,consumer_end))
  unpacked=out.get('unpacked');output_pointer=out.get('output_command');case['actual_unpacked_command_pointer_and_payload']=uint(output_pointer) and output_pointer>0 and pure_move(unpacked,goal) and mapped(unpacked,a.get('stored_after')) and all(e['lineage'].get('unpacked')==unpacked and e['lineage'].get('output_command')==output_pointer and e['lineage'].get('unpack_caller')==UNPACK_CALLER for e in (unpack_after,consumer,credit,consumer_end))
  case['observed_consumer_thing_and_dispatch_arguments']=all(e['lineage'].get('observed_this')==p.get('slot') and e['lineage'].get('observed_thing')==num(u.get('address')) and e['lineage'].get('observed_command')==output_pointer and e.get('tag')==0 for e in (unpack_before,unpack_after)) and all(e['lineage'].get('observed_this')==num(u.get('ai_address'))+0x24 and e['lineage'].get('observed_thing')==0 and e['lineage'].get('observed_command')==output_pointer and e.get('tag')==0 for e in (consumer,consumer_end))
  case['observed_private_actor_arguments']=credit['lineage'].get('observed_this')==num(u.get('ai_address')) and credit['lineage'].get('observed_thing')==num(u.get('address')) and uint(credit['lineage'].get('observed_command')) and credit['lineage']['observed_command']==output_pointer+8
  case['actual_scoped_dispatch_and_single_tag_zero_private']=bool(private and done and private.get('kind')==10 and done.get('kind')==11 and all(e.get('tag')==0 and e.get('arg')==1 and e.get('role')==role and e.get('source')==1 and e.get('mission_stage')==stage and e.get('frame')==consumer.get('frame')==consumer_end.get('frame') and exact(e.get('command_xyz'),goal) and e.get('argument_path')==0 and bits(e.get('argument_limit'))==0x7f7fffff for e in (private,done)) and private.get('caller')==PRIVATE_CALLER and all(e['lineage'].get('dispatch_caller')==DISPATCH_CALLER for e in (consumer,credit,consumer_end)) and credit['lineage'].get('private_caller')==PRIVATE_CALLER and credit['lineage'].get('delivered')==consumer_end['lineage'].get('delivered')==1 and consumer_end['lineage'].get('private_seq')==private['seq'])
  invalidators=[e for e in ev if facade and e.get('role')==role and facade['seq']<e.get('seq',0)<consumer_end['seq'] and ((e.get('kind') in (30,34,12,5,50)) or e.get('kind')==118)]
  case['no_invalidating_stop_attack_new_facade_return_or_credit']=not invalidators and not any(e['kind']==118 and e['seq']<consumer_end['seq'] for e in rows) and all(e['lineage'].get('invalid_reason')==0 for e in active)
  scoped=[e for e in ev if consumer['seq']<e.get('seq',0)<consumer_end['seq'] and e.get('role')==role and e.get('kind') in (10,11,111,112,113,114,115,116)]
  case['one_private_and_no_redefer']=bool(private and done and [e['kind'] for e in scoped]==[10,116,11])
  valid=all(v is True for v in case.values());result=dict(role=role,generation=generation,observed=True,verified=valid,checks=case,facade_seq=p.get('own_facade_seq'),private_move_seq=private.get('seq') if private else None,private_done_seq=done.get('seq') if done else None);results.append(result)
  if valid:accepted.append({k:result[k] for k in ('role','generation','verified','facade_seq','private_move_seq','private_done_seq')})
 checks['every_ticket_valid']=all(r['verified'] for r in results);private_sequences=[x['private_move_seq'] for x in accepted];checks['unique_private_delivery']=len(private_sequences)==len(set(private_sequences)) and len({x['facade_seq'] for x in accepted})==len(accepted)
 checks['role_generation_never_reset']=all([e['lineage']['generation'] for e in proofs if e['kind']==110 and e.get('role')==role]==list(range(1,1+sum(e['kind']==110 and e.get('role')==role for e in proofs))) for role in (0,1))
 verified=all(v is True for v in checks.values())
 return dict(verified=verified,observed=any(r.get('observed') for r in results),field_verified=False,checks=checks,tickets=results,accepted=accepted if verified else [],accepted_private_sequences=private_sequences if verified else [],semantics='independent_raw_command_lineage_only_no_field_grant')
