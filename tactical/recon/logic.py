"""Pure recon planning/assessment; no process access or commands."""
import hashlib,json,math

def digest_json(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def choose(units,frontiers,max_distance=550):
 pairs=[]
 points=list(frontiers.items()) if isinstance(frontiers,dict) else list(frontiers)
 for u in units:
  if not u.get('eligible') or u.get('hp',0)<=0:continue
  for region,point in points:
   d=math.hypot(u['xyz'][0]-point[0],u['xyz'][1]-point[1])
   if 40<=d<=max_distance:pairs.append((u.get('type_hash')!='0x19ab11af',d,-u['hp'],u['object_id'],region,u,list(point[:2])+[u['xyz'][2]]))
 if not pairs:raise ValueError('No eligible own unit within 40..550 of a player-view frontier')
 _,distance,_,_,region,unit,target=min(pairs,key=lambda x:x[:5]);return unit,region,target,distance

def planning_diagnostics(units,frontiers):
 points=list(frontiers.items()) if isinstance(frontiers,dict) else list(frontiers)
 eligible=[u for u in units if u.get('eligible') and u.get('hp',0)>0];roles={};pairs=[]
 for u in eligible:
  role={'0x19ab11af':'conscript','0x2c358c61':'flak'}.get(u.get('type_hash'),'unknown');roles[role]=roles.get(role,0)+1
  for region,p in points:pairs.append((math.hypot(u['xyz'][0]-p[0],u['xyz'][1]-p[1]),u['object_id'],region))
 pairs.sort()
 return {'eligible_unit_count':len(eligible),'eligible_role_counts':roles,'frontier_candidate_cell_count':len(points),'frontier_selection':'all_player_clear_adjacent_fog_cells','representative_region_limit_used':False,'minimum_frontier_distance':pairs[0][0] if pairs else None,'closest_own_candidates':[{'object_id':oid,'distance':distance,'region_id':region} for distance,oid,region in pairs[:3]],'planning_distance_bound':[40,550],'native_distance_bound':[20,600]}

def idle_report(report,session_id):
 n=report.get('native',{})
 if report.get('session_id')!=session_id or report.get('host_exit')!=0 or n.get('phase') not in (3,4) or n.get('active')!=0 or n.get('restore_mask') not in (31,63) or n.get('error')!=0:raise ValueError('Prior tactical hook report is not a clean terminal state')
 return True

def assessment(report):
 n=report.get('native',{});native=report.get('native_report',{});base=report.get('baseline',{});samples=report.get('samples',[]);plan=report['plan'];issued=n.get('issued_frame',0);returned=n.get('returned_frame',0);goal_index=plan['target']['grid_cell'];region=plan['target']['region_id']
 windows=[s for s in samples if issued and issued<=s['frame']<=returned+2]
 region_gain=max((s.get('new_clear_cells_in_target_region',0) for s in windows),default=0)
 target_clear=any(s.get('target_cell_newly_clear') for s in windows)
 checks=dict(session_bound=report.get('session_id')==plan['session_id']==native.get('session_id'),native_host_exited=native.get('host_exit')==0,native_move_primitive=native.get('assessment',{}).get('status')=='move_and_return_primitive_verified',one_native_move=n.get('detach_calls')==n.get('move_calls')==n.get('return_calls')==1,restored=n.get('phase')==3 and n.get('error')==0 and n.get('restore_mask')==31 and n.get('active')==0 and n.get('return_verified')==1,real_arrival=native.get('assessment',{}).get('checks',{}).get('arrival_independent') is True,native_request_target=all(abs(a-b)<.001 for a,b in zip(native.get('request',{}).get('target',[]),plan['target']['xyz'])) and len(native.get('request',{}).get('target',[]))==3,bounded_lease=0<issued<=returned<=issued+455,baseline_target_fogged=base.get('target_terrain_status')==0 and goal_index not in base.get('clear_cells',[]),target_region_new_vision=region_gain>=1,target_cell_new_vision=target_clear,own_identity_preserved=bool(samples) and all(s.get('own_identity_verified') is True for s in samples),no_error=report.get('error') is None)
 return {'status':'recon_arrival_new_vision_and_return_verified' if all(checks.values()) else 'not_passed','checks':checks,'target_region':region,'new_clear_cells_in_target_region_during_lease':region_gain,'target_cell_newly_visible_during_lease':target_clear,'raid_recon_verified_for_this_trial':all(checks.values()),'exclusive_vision_causality_verified':False,'note':'Same native lease window has real arrival, newly CLEAR target/region and restored AI control. Concurrent native scouts remain possible; no exclusive vision attribution or stable long-term recon claim.'}
