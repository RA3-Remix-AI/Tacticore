"""MFM7 one-shot retreat departure raw audit. No process access or field grant.

98/99 echo an immutable published phase-three leader origin, never snapshot 97.
The existing home, Stop, follow and physical return audits remain authoritative.
"""
import importlib.util
from pathlib import Path
_actor_spec=importlib.util.spec_from_file_location('mf18_actual_slot_actor',Path(__file__).with_name('actor_binding.py'));_actors=importlib.util.module_from_spec(_actor_spec);_actor_spec.loader.exec_module(_actors)
import importlib.util,math
from pathlib import Path

def finite(v):return type(v) in (int,float) and math.isfinite(v)
def point(v):return isinstance(v,(list,tuple)) and len(v)==3 and all(finite(x) for x in v)
def xyz(e):return [e.get(k) for k in ('x','y','z')]
def dist(a,b):return math.dist(a[:2],b[:2]) if point(a) and point(b) else math.inf
def same(a,b):return point(a) and point(b) and all(abs(x-y)<=.01 for x,y in zip(a,b))
def near(a,b):return finite(a) and finite(b) and abs(a-b)<=.05

def audit(report):
 try:return _audit(report)
 except (KeyError,TypeError,ValueError,IndexError,OverflowError):
  return dict(verified=False,observed=True,success_verified=False,field_verified=False,checks={'well_formed_raw_evidence':False})

def _audit(report):
 ev=report.get('events',[]);n=report.get('native',{});opens=[e for e in ev if e.get('kind')==98];closes=[e for e in ev if e.get('kind')==99]
 checks=dict(one_shot_closed_window=len(opens)==len(closes)==1)
 if not opens or not closes:
  return dict(verified=False,observed=bool(opens or closes),success_verified=False,field_verified=False,checks=checks)
 start=opens[0];end=closes[0];firsts={r:next((e for e in ev if e.get('kind')==80 and e.get('role')==r and e.get('mission_stage')==3),None) for r in (0,1)};source=firsts[1];c=source.get('breadcrumb',{}) if source else {};frame=start.get('frame');until=end.get('seq');deadline=n.get('mission_deadline_frame')
 spec=importlib.util.spec_from_file_location('mfm7_departure_stop',Path(__file__).with_name('wait_anchor_replan.py'));stop=importlib.util.module_from_spec(spec);spec.loader.exec_module(stop)
 checks['real_first_published_origin']=bool(source and c.get('role')==1 and c.get('mission_stage')==3 and type(c.get('index')) is int and 0<=c['index']<128 and source.get('arg')==c['index'] and c.get('published_seq')==source.get('seq')<start['seq'] and c.get('frame')==source.get('frame')==frame and near(c.get('path_distance'),0) and same(c.get('xyz'),xyz(source)))
 checks['immutable_full_echo']=all(e.get('breadcrumb')==c and e.get('argument_path')==frame and e.get('role')==e.get('leader_role')==1 and e.get('follower_role')==0 and e.get('follow_active')==0 and e.get('mission_stage')==3 and e.get('motion_state')==1 and e.get('mission_deadline_frame')==deadline for e in (start,end)) and start.get('arg')==0 and start['seq']<until
 checks['both_stop_three_and_positive_surface']=True
 for role in (0,1):
  origin=firsts[role];gates=[e for e in ev if origin and e.get('kind')==58 and e.get('role')==role and e.get('mission_stage')==3 and e.get('frame')==frame and e['seq']<origin['seq']]
  if not origin or not gates:
   checks['both_stop_three_and_positive_surface']=False;continue
  crumb=origin.get('breadcrumb',{});snapshot=dict(origin,kind=97,breadcrumb=dict(crumb,index=0,published_seq=0))
  checks['both_stop_three_and_positive_surface'] &= origin['seq']<start['seq'] and stop.actual_stop_gate(ev,role,gates[-1]) and stop.surface_snapshot(report,snapshot)['verified']
 checks['source_header_unchanged']=isinstance(n.get('crumbs'),list) and len(n['crumbs'])==2 and c in n['crumbs'][1]
 initial_gap=dist(xyz(firsts[0]) if firsts[0] else None,c.get('xyz'));checks['initial_gap_and_fixed_start']=near(start.get('actual_gap'),initial_gap) and all(near(e.get('argument_limit'),initial_gap) for e in (start,end))
 samples=[e for e in ev if e.get('kind')==3 and e.get('mission_stage')==3 and source and source['seq']<e.get('seq',0)<until and e.get('frame',-1)>frame];frames=sorted(set(e['frame'] for e in samples));previous=c.get('xyz');path=0.;rounds=[];complete=True
 for f in frames:
  pairs={r:[e for e in samples if e.get('frame')==f and e.get('role')==r] for r in (0,1)}
  if any(len(pairs[r])!=1 for r in (0,1)):complete=False;continue
  a,b=pairs[0][0],pairs[1][0];complete &= a.get('tick')==b.get('tick');path+=dist(previous,xyz(b));previous=xyz(b);gap=dist(xyz(a),xyz(b));clear=dist(c.get('xyz'),xyz(b));reason=3 if gap>350 else 2 if f-frame>30 else 1 if path>=25 and clear>=25 else 0
  rounds.append(dict(frame=f,path=path,clear=clear,gap=gap,reason=reason,leader=xyz(b)))
 # Initial >350 closes immediately, before start_move or a later raw sample.
 if initial_gap>350:rounds.insert(0,dict(frame=frame,path=0.,clear=0.,gap=initial_gap,reason=3,leader=c.get('xyz')))
 eligible=next((r for r in rounds if r['reason']),None);last=rounds[-1] if rounds else None
 checks['raw_paired_path_and_first_eligible_close']=bool(complete and eligible and last and eligible==last and eligible['frame']==end.get('frame') and eligible['reason']==end.get('arg') and same(xyz(end),eligible['leader']) and near(end.get('actual_gap'),eligible['gap']))
 checks['window_no_follow_regroup_or_restart']=not any(e.get('mission_stage')==3 and start['seq']<e.get('seq',0)<until and e.get('kind') in (81,82,89,96,98) for e in ev)
 follows=[e for e in ev if e.get('kind')==81 and e.get('mission_stage')==3];success=end.get('arg')==1
 checks['success_before_immediate_original_follow']=bool(follows and follows[0]['seq']>until and follows[0].get('frame')==end.get('frame') and follows[0].get('breadcrumb')==c and follows[0].get('role')==0 and follows[0].get('follow_crumb_role')==1 and follows[0].get('follow_crumb_index')==c.get('index')) if success else not follows
 checks['failure_cleanup_without_reopen']=success or (any(e.get('kind') in (53,66,5) and e['seq']>until for e in ev) and not any(e.get('kind') in (10,12,34,50,81,85,92,95,96,98) and e['seq']>until for e in ev))
 verified=all(v is True for v in checks.values())
 return dict(verified=verified,observed=True,success_verified=bool(verified and success),field_verified=False,checks=checks,start_seq=start['seq'],end_seq=until,start_frame=frame,end_frame=end.get('frame'),reason=end.get('arg'),initial_gap=initial_gap if finite(initial_gap) else None,actual_path=path if finite(path) else None,rounds=rounds,source_index=c.get('index'),source_published_seq=c.get('published_seq'),semantics='raw_protocol_only_no_field_capability')
