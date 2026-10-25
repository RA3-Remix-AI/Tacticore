"""Bounded current-position feasibility hints. Never a native dispatch or plan input.

All process access is read-only and owned-unit or currently verified full-FOV
enemy data. A paused current pose is not claimed valid after Transfer/Stop.
"""
import argparse,collections,hashlib,importlib.util,json,math,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent.parent;B=P.parent;D=P/'mission-formation-v4'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def xy(a,b):return math.dist(a[:2],b[:2])
def capture(session_path,history,baseline=None):
 w=load('readonly_feasibility_backend',D/'lease.py');pre,session,_,*rest=w.b.readiness(session_path);memory=rest[-1]
 try:
  sys.path[:0]=[str(B/'visibility'),str(P)]
  from capability import bind_session
  from projection import VisibilityProjection
  from collector import VisibilityCollector
  admission=load('readonly_feasibility_admission',P/'mission_actor_admission_v2.py');traffic=load('readonly_feasibility_traffic',D/'traffic_occupancy_v2.py')
  proof,safety=bind_session(memory,session,3);reader=VisibilityCollector(memory,session,3,VisibilityProjection(session['session_id'],3,session['mod_sha256'],proof,safety));frame=memory.u32(int(pre['logic'],0)+0x50);reader.collect(frame/15)
  candidates=w.b.own_candidates(memory,3,w.b.load_catalog())['candidates'];census=traffic.classify_owned(memory,candidates,pre['owner'],int(pre['logic'],0));admitted=[];all_admissions=[]
  for row in candidates:
   if row['type_hash'] not in ['0x19ab11af','0x2c358c61']:continue
   evidence=admission.actor_admission(memory,int(row['address'],0));verified=admission.verify_evidence(evidence)['verified'];all_admissions.append(dict(object_id=row['object_id'],type_hash=row['type_hash'],admission=evidence))
   if verified and evidence['grounded_status']['hp']>=50:admitted.append(dict(row,xyz=evidence['grounded_status']['xyz'],hp=evidence['grounded_status']['hp'],mission_admission=evidence))
  end=memory.u32(int(pre['logic'],0)+0x50);pre['frame']=end
  if not frame<=end<=frame+4:raise ValueError('readonly_capture_changed_frame')
  contacts=[dict(t,contact_id=cid,role=safety['templates'][t['type_hash']]['role']) for cid,t in reader.private_targets.items()];static=[t for t in contacts if t['role'] in ['structure','economy']]
  source_files=[dict(path=str(f.resolve()),sha256=sha(f)) for f in sorted(Path(history).glob('*.json'))]
  return dict(schema_version=1,semantics='readonly_current_pose_hint_not_after_stop_or_native_plan',session=session,preflight=pre,frame_start=frame,frame_end=end,paused=bool(memory.u32(int(pre['logic'],0)+0x15c)),all_owned_candidates=candidates,classified_census=census,all_foot_admissions=all_admissions,admitted=admitted,current_full_fov_contacts=contacts,current_static_contacts=static,visibility_proof=proof,safety_sha256=sha(B/'visibility/template-safety-2d7873e1.json'),history_directory=str(Path(history).resolve()),history_manifest=source_files,baseline_report=str(Path(baseline).resolve()) if baseline else None,baseline_sha256=sha(baseline) if baseline else None,mutations=False,sdk_calls=0,native_plan_eligible=False,reader_sha256=sha(__file__))
 finally:memory.close()
def graph_hint(planner,history,pre,session,front,support,target,owned,deadline):
 """An optimistic, undirected local-leg graph. Not walkability or role proof."""
 hard,mobile=planner.traffic.partition(owned,{front['object_id'],support['object_id']},pre['owner']);nodes={};stats=collections.Counter()
 for path in sorted(Path(history).glob('*.json')):
  if time.monotonic()>=deadline:return dict(status='graph_diagnostic_budget_exhausted')
  record=json.loads(path.read_text(encoding='utf-8-sig'));frame=record.get('logic_frame_candidate',0)
  if record.get('session_id')!=session['session_id'] or record.get('pid')!=session['pid'] or record.get('player_id')!=3 or not 0<frame<=pre['frame']:stats['source_session_or_frame_cutoff']+=1;continue
  if record.get('method')!='same_frame_owned_position_with_verified_native_surface' or record.get('ground_reader_sha256')!=sha(P/'grounded_status_v2.py'):stats['source_method_or_reader']+=1;continue
  for row in record.get('own_objects',[]):
   g=row.get('grounded_status',{});pos=row.get('xyz')
   if row.get('type_hash') not in planner.ALLOWED or not planner.point(pos) or not planner.positive_ground(row) or g.get('object_id')!=row.get('object_id') or g.get('frame')!=frame or g.get('end_frame')!=frame or g.get('type_hash')!=row.get('type_hash'):stats['invalid_ground_source']+=1;continue
   if any(xy(o['xyz'],pos)<20 and abs(o['xyz'][2]-pos[2])<10 for o in hard):stats['hard_occupied_source_rows']+=1;continue
   nodes[tuple(math.floor(v/40) for v in pos)]=pos
 data=list(nodes.values());first=[i for i,p in enumerate(data) if planner.leg_geometry(front['xyz'],support['xyz'],p,True)];goal={i for i,p in enumerate(data) if xy(p,target)<=300};queue=collections.deque((i,1) for i in first);seen=set(first);minimum=None
 while queue:
  if time.monotonic()>=deadline:return dict(status='graph_diagnostic_budget_exhausted',nodes=len(data),first_nodes=len(first),goal_nodes=len(goal))
  i,depth=queue.popleft()
  if i in goal:minimum=depth;break
  for j,p in enumerate(data):
   if j not in seen and 40<=xy(data[i],p)<=160 and abs(data[i][2]-p[2])<=100:seen.add(j);queue.append((j,depth+1))
 return dict(status='optimistic_undirected_geometry_only_not_a_role_route',nodes=len(data),first_nodes=len(first),goal_nodes=len(goal),reachable_nodes_before_first_goal=len(seen),optimistic_minimum_legs=minimum,optimistic_connected=minimum is not None,proven_depth_lower_bound_exceeds_16=minimum is not None and minimum>16,reject_counts=dict(stats),hard_occupants=len(hard),soft_mobile_traffic=len(mobile),walkable_route_verified=False)
def evaluate(snapshot,wall_seconds=30):
 started=time.monotonic();deadline=started+min(30,wall_seconds);planner=load('readonly_feasibility_planner',D/'role_route_planner_traffic_v2.py');pre=snapshot['preflight'];session=snapshot['session'];admitted=snapshot['admitted'];contacts=snapshot['current_static_contacts'];all_contacts=snapshot['current_full_fov_contacts'];owned=snapshot['classified_census']['owned_positions'];baseline={}
 if snapshot.get('baseline_report'):baseline=json.loads(Path(snapshot['baseline_report']).read_text(encoding='utf-8-sig'))
 wanted=baseline.get('request',{});preferred=(wanted.get('front_id'),wanted.get('support_id'));target_id=wanted.get('target_object_id')
 contacts=sorted(contacts,key=lambda t:(t['object_id']!=target_id,t['object_id']))[:3];fronts=[u for u in admitted if u['type_hash']=='0x19ab11af'];supports=[u for u in admitted if u['type_hash']=='0x2c358c61'];cases=[];pair_census=[]
 for target in contacts:
  pairs=[]
  for f in fronts:
   for s in supports:
    gap=xy(f['xyz'],s['xyz']);dot=sum((target['xyz'][i]-f['xyz'][i])*(f['xyz'][i]-s['xyz'][i]) for i in (0,1));threats=[t['object_id'] for t in all_contacts if xy(f['xyz'],t['xyz'])<350 or xy(s['xyz'],t['xyz'])<350]
    if 25<=gap<=180 and dot>=0:pairs.append((bool(threats),(f['object_id'],s['object_id'])!=preferred,planner.pair_priority(f,s,target['xyz']),f,s,threats))
  pairs.sort(key=lambda p:p[:3]);pair_census.append(dict(target_id=target['object_id'],legal_geometry_ahead_pairs=len(pairs),origin_safe_pairs=sum(not x[0] for x in pairs)))
  for blocked,_,__,f,s,threats in pairs[:8]:
   if time.monotonic()>=deadline:break
   start=time.monotonic();item=dict(front_id=f['object_id'],support_id=s['object_id'],contact_id=target['contact_id'],target_id=target['object_id'],pair_gap=xy(f['xyz'],s['xyz']),front_distance=xy(f['xyz'],target['xyz']),source_frame_cutoff=pre['frame'],origin_threat_clear=not blocked,current_visible_origin_threat_ids=threats,planning_budget_seconds=min(2.,max(0.,deadline-start)),native_plan_eligible=False)
   try:
    plan=planner.plan_from_history(snapshot['history_directory'],pre,session,f,s,target['xyz'],owned,planning_deadline=min(deadline,start+2.));item.update(feasible_current_pose_hint=True,plan=plan,diagnostics=plan.get('planning_diagnostics'))
   except planner.RoutePlanningError as error:item.update(feasible_current_pose_hint=False,reason=str(error),diagnostics=error.diagnostics)
   except ValueError as error:item.update(feasible_current_pose_hint=False,reason=str(error),diagnostics=dict(planner.LAST_DIAGNOSTICS))
   item['wall_seconds']=time.monotonic()-start
   if not item['feasible_current_pose_hint'] and time.monotonic()+.1<deadline:item['optimistic_connectivity']=graph_hint(planner,snapshot['history_directory'],pre,session,f,s,target['xyz'],owned,min(deadline,time.monotonic()+1))
   cases.append(item)
  if time.monotonic()>=deadline:break
 return dict(semantics=snapshot['semantics'],session_id=session['session_id'],pid=session['pid'],frame=pre['frame'],paused=snapshot['paused'],owned_count=len(snapshot['all_owned_candidates']),classified_hard=sum(x['traffic_class']=='hard_or_unknown' for x in owned),classified_verified_mobile=sum(x['traffic_class']=='verified_mobile_foot' for x in owned),admitted_conscripts=len(fronts),admitted_flak=len(supports),current_contacts=len(all_contacts),current_static_contacts=len(snapshot['current_static_contacts']),pair_census=pair_census,cases=cases,any_actual_legal_geometry_graph_hint=any(x['feasible_current_pose_hint'] and x['origin_threat_clear'] for x in cases),no_route_conclusion='no_current_visible_static_target_no_targeted_route_can_be_evaluated' if not contacts else 'see_per_pair_diagnostics_not_original_failure_census',wall_seconds=time.monotonic()-started,budget_exhausted=time.monotonic()>=deadline,planner_sha256=sha(D/'role_route_planner_traffic_v2.py'),snapshot_reader_sha256=sha(__file__),sdk_calls=0,mutations=False,after_stop_route_validity_claim=False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path);p.add_argument('--history',type=Path);p.add_argument('--baseline-report',type=Path);p.add_argument('--replay',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 if a.output.exists():raise ValueError('existing_feasibility_report_preserved')
 snap=json.loads(a.replay.read_text(encoding='utf-8-sig')) if a.replay else capture(a.session,a.history,a.baseline_report)
 snapshot_path=a.output.with_name(a.output.stem+'-snapshot.json')
 if not a.replay:
  with snapshot_path.open('x',encoding='utf-8') as f:json.dump(snap,f,indent=2,allow_nan=False)
 result=evaluate(snap);result.update(snapshot_path=str((a.replay or snapshot_path).resolve()),snapshot_sha256=sha(a.replay or snapshot_path))
 with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
 print(json.dumps({k:result[k] for k in ['frame','paused','owned_count','admitted_conscripts','admitted_flak','current_contacts','current_static_contacts','any_actual_legal_geometry_graph_hint','no_route_conclusion','wall_seconds']}))
