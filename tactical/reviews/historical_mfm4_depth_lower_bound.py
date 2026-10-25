"""Historical visible coordinates only, offline optimistic depth lower bound.

No Memory object, collector, host, GUI, SDK, model or current enemy read occurs.
The 32-point branch is an in-memory counterfactual; never a Native input.
"""
import argparse,hashlib,importlib.util,json,time,types
from pathlib import Path
P=Path(__file__).resolve().parent.parent;D=P/'mission-formation-v4'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main(report,session_path,history,output,cutoff=5387):
 started=time.monotonic();raw=Path(report).read_bytes();r=json.loads(raw.decode('utf-8-sig'));session=json.loads(Path(session_path).read_text(encoding='utf-8-sig'));ready=[e for e in r['events'] if e.get('kind')==72];byrole={e['role']:e for e in ready}
 if len(ready)!=2 or set(byrole)!={0,1} or len({e['frame'] for e in ready})!=1 or any(e.get('target_visible')!=1 for e in ready):raise ValueError('historical_ready_visible_pair_required')
 helper=load('historical_depth_graph',P/'reviews/readonly_mfm4_feasibility.py');planner=helper.load('historical_depth_role16',D/'role_route_planner_traffic_v2.py');pre=dict(r['preflight'],frame=cutoff);front=dict(pre['selected'],xyz=[byrole[0][k] for k in ['x','y','z']]);support=dict(pre['support'],xyz=[byrole[1][k] for k in ['x','y','z']]);target=byrole[0]['visible_target_xyz']
 lower=helper.graph_hint(planner,history,pre,session,front,support,target,[],time.monotonic()+8)
 cases=[]
 for maximum in [16,32]:
  module=planner
  if maximum==32:
   code=(D/'role_route_planner_traffic_v2.py').read_text()
   for old,new in [('not 2<=len(route)<=16','not 2<=len(route)<=32'),('if len(route)>=16:continue','if len(route)>=32:continue'),('seen.get(state,17)','seen.get(state,33)')]:
    if code.count(old)!=1:raise ValueError('counterfactual_source_marker_changed')
    code=code.replace(old,new)
   module=types.ModuleType('historical_role32_counterfactual');module.__file__=str(D/'role_route_planner_traffic_v2.py');exec(compile(code,'<offline_counterfactual_route32_no_native>', 'exec'),module.__dict__)
  case=dict(maximum_points=maximum,hard_or_soft_occupants=[],semantics='historical_offline_counterfactual_no_native_eligibility',expansion_limit=12000,wall_limit_seconds=8)
  try:
   plan=module.plan_from_history(history,pre,session,front,support,target,[],planning_deadline=time.monotonic()+8);case.update(feasible=True,route_points=len(plan['route']),route=plan['route'],diagnostics=plan['planning_diagnostics'],full_forward_reverse_role_geometry=module.route_geometry(front['xyz'],support['xyz'],plan['route']))
  except module.RoutePlanningError as error:case.update(feasible=False,reason=str(error),diagnostics=error.diagnostics)
  case['expanded_limit_reached']=case['diagnostics'].get('expanded_states',0)>=12000;cases.append(case)
 result=dict(semantics='historical_seen_coordinate_only_offline_not_current_fov_or_after_stop_eligibility',source_report=str(Path(report).resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),source_ready_actual_frame=ready[0]['frame'],source_planning_history_cutoff=cutoff,session_id=session['session_id'],pid=session['pid'],front_id=front['object_id'],support_id=support['object_id'],actual_stopped_front=front['xyz'],actual_stopped_support=support['xyz'],historically_visible_static_target=target,optimistic_no_occupant_geometry_graph=lower,role_cases=cases,conclusion='A 17-leg optimistic lower bound proves the unchanged 16-point planner cannot reach this goal with this historical node set, even without occupancy. A 32-point simulation is diagnostic only; search success/failure is not Native passability.',limits=['optimistic undirected graph ignores turn, held-actor and unique-source constraints, making it a lower bound only','positive grounded points do not prove path edges walkable','role search retains existing source-cycle and seen-state pruning and the 12000 expansion cap','no current hidden enemy coordinates were read','no simulated route is sent to Native'],planner_source_sha256=helper.sha(D/'role_route_planner_traffic_v2.py'),reviewer_sha256=helper.sha(__file__),sdk_calls=0,native_plan_eligible=False,wall_seconds=time.monotonic()-started)
 with Path(output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
 print(json.dumps(dict(lower_bound=lower,cases=[{k:c.get(k) for k in ['maximum_points','feasible','route_points','reason','expanded_limit_reached']} for c in cases],wall_seconds=result['wall_seconds']),indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--session',required=True);p.add_argument('--history',required=True);p.add_argument('--output',required=True);p.add_argument('--cutoff',type=int,default=5387);a=p.parse_args();main(a.report,a.session,a.history,a.output,a.cutoff)
