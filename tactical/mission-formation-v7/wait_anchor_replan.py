"""MF6 contingent wait replan, pure raw audit; no game or process operations.

97 is a new positive own snapshot, never a trail publication or proof that the
abandoned 96 goal was reached. Only a mid-regroup waiting leader may do this.
"""
import math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from stop_sequence import settled_stop
TYPES={0:0x19ab11af,1:0x2c358c61}
def finite(x):return type(x) in (float,int) and math.isfinite(x)
def point(p):return isinstance(p,list) and len(p)==3 and all(finite(x) for x in p)
def xyz(e):return [e.get(k) for k in ('x','y','z')]
def distance(a,b):return math.dist(a[:2],b[:2]) if point(a) and point(b) else math.inf
def same(a,b):return point(a) and point(b) and all(abs(x-y)<=.01 for x,y in zip(a,b))
def num(x):return int(x,0) if isinstance(x,str) else x

def actual_stop_gate(ev,role,gate):
 if not gate:return False
 rows=[e for e in ev if e.get('role')==role and e['seq']<gate['seq']];stops=[e for e in rows if e.get('kind')==33 and e.get('tag')==4 and e.get('caller')==0x787791 and e.get('arg')==1]
 if not stops:return False
 stop=stops[-1];chain=[e for e in rows if e.get('tag')==4 and e.get('kind') in (30,32,33,31) and e['frame']==stop['frame']];samples=[e for e in rows if e['kind']==3 and e['seq']>stop['seq']];last=list({e['frame']:e for e in samples}.values())[-3:]
 return [e['kind'] for e in chain]==[30,32,33,31] and all(e.get('arg')==1 for e in chain) and len(last)==3 and all(e.get('state_id')==16 and e.get('source')==1 and e.get('path')==e.get('holder')==0 and not e.get('sm_flags',65535)&65535 for e in last) and settled_stop([dict(stop,kind=23)]+samples+[dict(gate,kind=24)])['verified']

def surface_snapshot(report,event):
 c=event.get('breadcrumb',{});role=event.get('role');pre=report.get('preflight',{});u=pre.get('support' if role else 'selected',{});words=c.get('status_words');checks={}
 try:
  checks['typed_words']=role in (0,1) and isinstance(words,list) and len(words)==7 and all(type(x) is int and 0<=x<=0xffffffff for x in words)
  if not checks['typed_words']:return {'verified':False,'checks':checks}
  checks['same_actual_actor']=c.get('role')==role and c.get('thing')==num(u.get('address')) and c.get('object_id')==u.get('object_id')==event.get('unit_id') and c.get('type_hash')==TYPES[role] and c.get('owner')==num(pre.get('owner'))==event.get('owner') and c.get('update')==num(u.get('ai_address'))
  checks['surface_positive']=type(c.get('height_flags')) is int and c['height_flags']&4!=0 and finite(c.get('height')) and abs(c['height'])<=.5 and c.get('holder')==0 and not any(words[i//32]&(1<<(i%32)) for i in (0,7,8,51,61,161,207,211))
  checks['same_actual_position_health_clock']=point(c.get('xyz')) and same(c['xyz'],xyz(event)) and finite(c.get('hp')) and c['hp']>0 and finite(event.get('own_hp')) and abs(c['hp']-event['own_hp'])<.05 and type(c.get('frame')) is int and c['frame']==event.get('frame') and c.get('mission_stage')==event.get('mission_stage')
  checks['snapshot_not_published_trail']=c.get('published_seq')==0 and c.get('index')==0 and event.get('kind')==97
 except (ValueError,TypeError,KeyError):checks['well_formed']=False
 return {'verified':all(v is True for v in checks.values()),'checks':checks,'trail_publication':False}

def audit(report):
 ev=report.get('events',[]);n=report.get('native',{});starts=[e for e in ev if e.get('kind')==96];gates=[e for e in ev if e.get('kind')==97];results=[];checks=dict(bounded_attempts=len(starts)<=2,pairs_and_order=len(starts)==len(gates),old_origins_preserved=True)
 for role in (0,1):
  original=[e for e in ev if e.get('kind')==71 and e.get('role')==role]
  checks['old_origins_preserved'] &= len(original)==1 and same(xyz(original[0]),n.get('safe_support' if role else 'safe_front'))
 for i,start in enumerate(starts):
  role=start.get('role');stage=start.get('mission_stage');leader=0 if stage==1 else 1 if stage==3 else None;end=starts[i+1]['seq'] if i+1<len(starts) else len(ev)+1
  prior=[e for e in ev if e.get('kind') in (83,97) and e.get('role')==role and e.get('mission_stage')==stage and e['seq']<start['seq']];anchor=prior[-1].get('leader_hold_xyz') if prior else None
  matched=[e for e in gates if start['seq']<e['seq']<end and e.get('arg')==start.get('arg')];gate=matched[0] if len(matched)==1 else None;rows=[e for e in ev if gate and e.get('role')==role and start['seq']<e['seq']<gate['seq']]
  regroups=[e for e in ev if e.get('kind')==82 and e.get('role')==role and e.get('mission_stage')==stage and e['seq']<start['seq']];waiting=regroups[-1] if regroups else None;wait_gates=[e for e in ev if waiting and e.get('kind')==83 and e.get('role')==role and e.get('mission_stage')==stage and waiting['seq']<e['seq']<start['seq']];wait_gate=wait_gates[0] if wait_gates else None;closed=any(wait_gate and e.get('kind') in (85,64,89,91) and e.get('role')==role and wait_gate['seq']<e['seq']<start['seq'] for e in ev)
  chain=[e for e in rows if e.get('tag')==4 and e.get('kind') in (30,32,33,31)];stop=next((e for e in chain if e['kind']==33),None);samples=[e for e in rows if stop and e['kind']==3 and e['seq']>stop['seq']];last=list({e['frame']:e for e in samples}.values())[-3:]
  boundary=bool(gate and stop and [e['kind'] for e in chain]==[30,32,33,31] and len({e['frame'] for e in chain})==1 and all(e.get('arg')==1 for e in chain) and stop.get('caller')==0x787791 and len(last)==3 and last[-1]['frame']==gate['frame'] and all(e.get('state_id')==16 and e.get('source')==1 and e.get('path')==e.get('holder')==0 and not e.get('sm_flags',65535)&65535 for e in last) and settled_stop([dict(stop,kind=23)]+samples+[dict(gate,kind=24)])['verified'])
  snap=surface_snapshot(report,gate) if gate else {'verified':False};no_motion=not any(e['kind'] in (10,12,34,50) for e in rows)
  case=dict(mid_regroup_only=bool(role==leader and start.get('leader_role')==leader and start.get('motion_state')==3 and stage in (1,3) and wait_gate and wait_gate.get('motion_state')==3 and actual_stop_gate(ev,role,wait_gate) and not closed),real_old_anchor_abandoned=point(anchor) and same(start.get('leader_hold_xyz'),anchor) and distance(xyz(start),anchor)>15,unique_bounded_arg=type(start.get('arg')) is int and start['arg']==i+1,actual_source1_stop_three=boundary,no_leader_move_or_attack_while_replanning=no_motion,actual_positive_new_anchor=snap['verified'] and gate is not None and same(gate.get('leader_hold_xyz'),xyz(gate)),deadline_and_phase_unchanged=bool(gate and gate.get('role')==role and gate.get('mission_stage')==stage and gate.get('motion_state')==11 and gate.get('mission_deadline_frame')==start.get('mission_deadline_frame')==n.get('mission_deadline_frame') and 0<gate['frame']-start['frame']<=60))
  results.append(dict(start_seq=start['seq'],gate_seq=gate['seq'] if gate else None,abandoned_anchor=anchor,new_wait_anchor=xyz(gate) if gate else None,old_anchor_arrival_claim=False,stop_frames=[e['frame'] for e in last],checks=case,verified=all(v is True for v in case.values())))
 checks['every_observed_replan']=all(x['verified'] for x in results)
 return dict(verified=all(v is True for v in checks.values()),observed=bool(starts or gates),field_verified=bool(starts) and all(v is True for v in checks.values()),checks=checks,attempts=results,old_goal_arrival_claim=False,unobserved_status=None if starts else 'unproven_not_field_certified')
