"""Read-only admission for the bounded idle/normal-move/exact attack-state foot actor scope.

Point grounding and command admission are independent. A ground point can be a
valid observation while its actor is entering a structure and unsafe to borrow.
The native in-lease interference guard remains mandatory after this snapshot.
"""
import hashlib,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
_s=importlib.util.spec_from_file_location('mission_admission_ground_v2',HERE/'grounded_status_v2.py');g=importlib.util.module_from_spec(_s);_s.loader.exec_module(g)
PROTOCOL='grounded_idle_normal_move_or_exact_attack_admission_v2'

def fingerprints():return dict(helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),ground_helper_sha256=hashlib.sha256((HERE/'grounded_status_v2.py').read_bytes()).hexdigest(),status_helper_sha256=hashlib.sha256((HERE/'grounded_status.py').read_bytes()).hexdigest())

def unknown(reason,ground=None):return dict(protocol=PROTOCOL,status='unknown_or_ineligible',admission_verified=False,reason_code=reason,grounded_status=ground,mutations=False,**fingerprints())

def actor_admission(memory,thing):
 ground=g.grounded_status(memory,thing)
 if not g.verify_evidence(ground)['verified']:return unknown('ground_evidence_unavailable',ground)
 try:
  def sample():
   update=memory.u32(thing+0x374);sm=memory.u32(update+0x3c);state=memory.u32(sm+4)
   return dict(update=hex(update),update_vtable=hex(memory.u32(update)),facade_vtable=hex(memory.u32(update+0x24)),update_backref=hex(memory.u32(update+8)),sm=hex(sm),sm_owner=hex(memory.u32(sm+0x24)),state=hex(state),state_id=memory.u32(state+4),state_vtable=hex(memory.u32(state)),state_owner_sm=hex(memory.u32(state+0x18)),command_source=memory.u32(update+0x50),path=hex(memory.u32(update+0x150)),sm_flags=memory.u32(sm+0x78))
  first=sample();second=sample();after=g.grounded_status(memory,thing)
  if first!=second or ground!=after:return unknown('admission_changed_during_same_frame_sample',ground)
  result=dict(protocol=PROTOCOL,status='verified_owned_actor_state',object_id=ground['object_id'],address=hex(thing),owner=ground['owner'],type_hash=ground['type_hash'],frame=ground['frame'],end_frame=after['end_frame'],grounded_status=ground,state_snapshot=first,mutations=False,atomic_sample_verified=True,**fingerprints())
  checks=_checks(result);result['admission_verified']=all(checks.values());result['checks']=checks
  if not result['admission_verified']:result['reason_code']='outside_bounded_idle_normal_move_or_exact_attack_scope'
  return result
 except Exception as error:return unknown(type(error).__name__,ground)

def _checks(record):
 checks={};ground=record.get('grounded_status',{});state=record.get('state_snapshot',{})
 try:
  number=lambda x:int(x,0) if isinstance(x,str) else x
  checks['ground_evidence']=g.verify_evidence(ground)['verified']
  checks['source']=record.get('protocol')==PROTOCOL and record.get('status')=='verified_owned_actor_state' and all(record.get(k)==v for k,v in fingerprints().items())
  checks['identity_frame']=record.get('atomic_sample_verified') is True and all(record.get(k)==ground.get(k) for k in ['object_id','address','owner','type_hash','frame','end_frame'])
  checks['known_foot_update']=state.get('update_vtable')=='0xc48670' and state.get('facade_vtable')=='0xc48528' and state.get('update_backref')==record.get('address')
  checks['state_owner_binding']=number(state.get('update'))>0 and number(state.get('state'))>0 and number(state.get('state_vtable'))>0 and number(state.get('sm'))>0 and state.get('state_owner_sm')==state.get('sm') and state.get('sm_owner')==record.get('address')
  checks['demonstrated_state_only']=type(state.get('state_id')) is int and state['state_id'] in [1,10,16] and (state['state_id']!=16 or number(state.get('path'))==0)
  checks['exact_attack_state_vtable']=state.get('state_id')!=10 or state.get('state_vtable')=='0xc548c0'
  checks['no_deferred_command_lock']=type(state.get('sm_flags')) is int and state['sm_flags']&0xffff==0 and type(state.get('command_source')) is int and state['command_source'] in [0,1,2,3]
  checks['no_mutations']=record.get('mutations') is False
 except (TypeError,ValueError,KeyError):checks['well_formed']=False
 return checks

def verify_evidence(record):
 checks=_checks(record);checks['positive_claim']=record.get('admission_verified') is True
 return dict(verified=all(checks.values()),checks=checks,protocol=PROTOCOL,command_ownership_guaranteed_after_snapshot=False,mutations=False)
