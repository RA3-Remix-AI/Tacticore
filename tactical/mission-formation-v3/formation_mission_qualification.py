"""Pure raw-evidence review: two-role advance, front damage, physical retreat.

No SDK calls. Aggregate counters or a successful predecessor primitive cannot
replace the role-specific positions, current target visibility and damage packet.
"""
import hashlib,json,math,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from ordered_qualification import damage_packet,target_scope,EXE
from stop_sequence import settled_stop

def finite(v):return type(v) in (int,float) and math.isfinite(v)
def xyz(e):return [e.get(k) for k in ('x','y','z')]
def point(p):return isinstance(p,list) and len(p)==3 and all(finite(x) for x in p)
def distance(a,b):return math.dist(a[:2],b[:2]) if point(a) and point(b) else math.inf
def same(a,b):return point(a) and point(b) and all(abs(x-y)<.01 for x,y in zip(a,b))
def progress(report,mission_id):
 n=report.get('native',{});ev=report.get('events',[])
 if not n.get('issued_frame') or not ev:return None
 last=ev[-1];stage=last.get('mission_stage',0);prepared=stage==2 and last.get('lease_stage')!=1
 restored={e.get('role') for e in ev if e.get('kind')==5 and e.get('tag')==3}=={0,1}
 phase='restored' if restored else 'prepare' if prepared else {0:'approach',1:'approach',2:'engage',3:'retreat',4:'retreat',5:'retreat'}.get(stage,'retreat')
 roles={};remaining=None
 for e in ev:
  if e.get('role') in (0,1) and finite(e.get('own_hp')):roles[e['role']]=max(0,e['own_hp'])
  if e.get('role')==0 and e.get('target_visible')==1 and point(xyz(e)) and point(e.get('visible_target_xyz')):remaining=distance(xyz(e),e['visible_target_xyz'])
 damage=sum(e.get('damage_reported',0) for e in ev if e.get('kind')==20 and e.get('role')==0 and finite(e.get('damage_reported')) and e['damage_reported']>0)
 reason={0:'active',1:'source_damage',2:'fov_lost',3:'low_hp',4:'cancelled',5:'engage_limit',6:'retreat_failed',7:'prepare_failed',8:'approach_stalled'}.get(last.get('mission_reason'),'initial_binding')
 error=last.get('native_error',0)
 if error:reason={31:'initial_binding',32:'retreat_failed',34:'initial_binding',35:'initial_binding',37:'retreat_failed',38:'native_override',44:'prepare_failed',45:'retreat_failed',48:'deadline',49:'cancelled',50:'heartbeat_lost',52:'retreat_failed',53:'retreat_failed'}.get(error,'initial_binding')
 return dict(mission_id=mission_id,stage=phase,revision=last['seq'],observed_frame=last['frame'],deadline_frame=last['mission_deadline_frame'],approach_distance=remaining,own_hp=min(roles.values()) if roles else 0,damage=damage,reason=reason)
def raw_pairs(events):
 result=[];seen=set()
 for a,b in zip(events,events[1:]):
  key=(a.get('mission_stage'),a.get('route_index'),a.get('nav_step'),a.get('frame'))
  if a.get('kind')==b.get('kind')==3 and a.get('role')==0 and b.get('role')==1 and all(a.get(k)==b.get(k) for k in ('frame','tick','mission_stage','route_index','nav_step')) and key not in seen:
   result.append((a,b));seen.add(key)
 return result
def consecutive(rows,predicate):
 run=longest=0
 for row in rows:
  run=run+1 if predicate(row) else 0;longest=max(longest,run)
 return longest
def geometry(pair,front_goal,support_goal,combat=False):
 front,support=pair;f,s=xyz(front),xyz(support);gap=distance(f,s);v=[front_goal[i]-support_goal[i] for i in (0,1)] if point(front_goal) and point(support_goal) else [0,0]
 return distance(s,support_goal)<=15 and (combat or distance(f,front_goal)<=15) and 25<=gap<=(350 if combat else 200) and (f[0]-s[0])*v[0]+(f[1]-s[1])*v[1]>0
def stage_audit(events,route,safe_front,safe_support,mission_stage):
 pairs=raw_pairs(events);results=[];count=len(route)
 indices=range(count) if mission_stage==1 else range(count-1,-1,-1)
 for index in indices:
  fg=route[index] if mission_stage==1 else route[index-1] if index else safe_front
  sg=(route[index-1] if index else safe_front) if mission_stage==1 else (route[index-2] if index>1 else safe_front) if index else safe_support
  all_rows=[pair for pair in pairs if pair[0].get('mission_stage')==mission_stage and pair[0].get('route_index')==index]
  arrival=[pair for pair in all_rows if pair[0].get('nav_step')==2]
  complete=[e for e in events if e.get('kind')==60 and e.get('mission_stage')==mission_stage and e.get('route_index')==index]
  longest=consecutive(arrival,lambda p:geometry(p,fg,sg))
  holds=[]
  for pair in all_rows:
   if pair[0].get('nav_step')!=1:continue
   lead=pair[0] if mission_stage==1 else pair[1];held=pair[1] if mission_stage==1 else pair[0];goal=fg if mission_stage==1 else sg
   # Hold coordinate comes from the raw two-role clean-stop gate, not a claim.
   gates=[e for e in events if e.get('kind')==58 and e.get('mission_stage')==mission_stage and e.get('route_index')==index and e.get('role')==held['role']]
   if len(gates)==1:holds.append((pair,distance(xyz(held),xyz(gates[0]))<=15 and distance(xyz(lead),goal)<=15))
  held_run=consecutive(holds,lambda x:x[1])
  moves=[e for e in events if e.get('kind')==50 and e.get('tag')==6 and e.get('mission_stage')==mission_stage and e.get('route_index')==index]
  role_order=[0,1] if mission_stage==1 else [1,0]
  holds_before_follow=[row for row in holds if len(moves)==2 and row[0][0]['seq']<moves[1]['seq']]
  order=len(moves)==2 and [e['role'] for e in moves]==role_order and consecutive(holds_before_follow,lambda x:x[1])>=3
  results.append(dict(mission_stage=mission_stage,route_index=index,front_goal=fg,support_goal=sg,paired_arrival_run=longest,held_lead_arrival_run=held_run,completion_records=len(complete),role_order_verified=order,verified=longest>=3 and held_run>=3 and order and {e.get('role') for e in complete}=={0,1} and len(complete)==2))
 return results
def source_pins(report):
 files={'native_binary_sha256':HERE/'bin/TacticalMissionFormation3.dll','native_host_sha256':HERE/'bin/tactical_host.exe','native_source_sha256':HERE/'lease.cpp','native_shared_sha256':HERE/'shared.h','wrapper_sha256':HERE/'lease.py'}
 try:
  primary=all(report.get(key)==hashlib.sha256(path.read_bytes()).hexdigest() for key,path in files.items())
  supplements=report.get('supplemental_sources',{})
  expected=list(HERE.glob('*.cpp.inc'))+[HERE/'prepare_sources.py',HERE/'formation_mission_qualification.py',HERE/'mission_route.py',HERE/'inert-layout.json',HERE.parent/'mobility_guard.py']
  return primary and report.get('pre_dispatch_helper_sha256')==hashlib.sha256((HERE.parent/'pre_dispatch_formation_v3_contract.py').read_bytes()).hexdigest() and bool(supplements) and all(supplements.get(path.name)==hashlib.sha256(path.read_bytes()).hexdigest() for path in expected)
 except OSError:return False

def terminal_entries_verified(entries):
 try:
  block=(HERE/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
  expected=[dict(address=address,expected=escaped.replace('\\x','')) for address,escaped,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block)]
  return len(expected)==13 and [{k:e.get(k) for k in ['address','expected']} for e in entries]==expected and all(e.get('actual')==e.get('expected') and e.get('restored') is True for e in entries)
 except (OSError,IndexError,TypeError):return False

def disposal_binding_verified(d,report,role):
 pre=report.get('preflight',{});rq=report.get('request',{});oid=pre.get('support' if role else 'selected',{}).get('object_id');scans=d.get('scans',[])
 expected=dict(pid=pre.get('pid'),session_id=report.get('session_id'),commander_id=pre.get('commander_id'),command_id=rq.get('command_id'),task_id=rq.get('task_id'),seq=rq.get('seq'),token=rq.get('token'),owner=pre.get('owner'),logic=pre.get('logic'),native_binary_sha256=report.get('native_binary_sha256'))
 if any(v is None for v in expected.values()) or not all(d.get(k)==v for k,v in expected.items()):return False
 if d.get('object_id')!=oid or d.get('role')!=role or d.get('source_session_id')!=report.get('session_id') or d.get('mutations') is not False:return False
 if d.get('source_request_sha256')!=hashlib.sha256(json.dumps(rq,sort_keys=True,separators=(',',':')).encode()).hexdigest() or d.get('source_preflight_sha256')!=hashlib.sha256(json.dumps(pre,sort_keys=True,separators=(',',':')).encode()).hexdigest():return False
 states=[d.get('terminal_before',{}),d.get('terminal_after',{})]
 if not all(all(x.get(k)==v for k,v in expected.items()) and x.get('binding_verified') is True and x.get('mutations') is False and x.get('timer')==x.get('active')==0 and x.get('phase')==4 and x.get('restore_mask')==8191 and terminal_entries_verified(x.get('entries',[])) for x in states):return False
 if not states[0].get('shared_pointer') or states[0].get('shared_pointer')!=states[1].get('shared_pointer') or states[0].get('module_base')!=states[1].get('module_base'):return False
 return len(scans)==2 and all(x.get('logic')==pre.get('logic') and x.get('complete') is True and type(x.get('frame')) is int and x.get('end_frame')==x['frame'] and x['frame']>=report.get('native',{}).get('issued_frame',0) and isinstance(x.get('ids'),list) and 1<=len(x['ids'])==x.get('count')<=20000 and len(set(x['ids']))==x['count'] and all(type(i) is int and i>0 for i in x['ids']) and oid not in x['ids'] for x in scans) and scans[0]['frame']<scans[1]['frame']

def control_release(report):
 """Release is independent of effect and arrival; never claims task completion."""
 n=report.get('native',{});pre=report.get('preflight',{});events=report.get('events',[]);s=n.get('support',{});inert=report.get('terminal_readonly',{});manager=int(pre.get('ai','0'),0)+0x104
 inert_ok=n.get('phase') in (3,4) and n.get('restore_mask')==8191 and n.get('active')==0 and inert.get('binding_verified') is True and inert.get('timer')==0 and inert.get('phase') in (3,4) and inert.get('restore_mask')==8191 and inert.get('active')==0 and terminal_entries_verified(inert.get('entries',[]))
 roles=[]
 for role,u in [(0,n),(1,s)]:
  detach=u.get('detach_calls',0);returned=u.get('return_verified',u.get('returned',0));ev=[e for e in events if e.get('role')==role]
  transfer=[e for e in ev if e.get('kind')==15 and e.get('tag')==3 and e.get('arg')==1];added=[e for e in ev if e.get('kind')==16 and e.get('tag')==3 and e.get('arg')==manager and e.get('caller')==0x83885b];return_record=[e for e in ev if e.get('kind')==5 and e.get('tag')==3]
  gates=[e for e in ev if e.get('kind') in (66,67,68)]
  boundary=False
  if len(gates)==1:
   gate=gates[0];stops=[e for e in ev if e.get('kind')==33 and e.get('arg')==1 and e.get('caller')==0x787791 and e.get('seq',0)<gate['seq']]
   if stops:
    stop=stops[-1];translated=[dict(stop,kind=23)]+[e for e in ev if e.get('kind')==3 and stop['seq']<e.get('seq',0)<gate['seq']]+[dict(gate,kind=24)];boundary=settled_stop(translated)['verified']
  actual_return=boundary and detach==u.get('return_calls')==returned==1 and len(transfer)==len(added)==len(return_record)==1 and transfer[0]['seq']<return_record[0]['seq'] and added[0]['seq']<return_record[0]['seq'] and gates[0]['seq']<min(transfer[0]['seq'],added[0]['seq'])
  never_held=detach==0 and not any(e.get('kind')==14 and e.get('tag')==1 for e in ev)
  # Death is accepted only with independent full-list, two advancing-frame sidecar.
  disposition=report.get('disposal_readonly',{}).get(str(role),{});scans=disposition.get('scans',[]);oid=pre.get('support' if role else 'selected',{}).get('object_id')
  disposed=disposal_binding_verified(disposition,report,role)
  roles.append(dict(role=role,object_id=oid,returned=bool(actual_return),disposed=bool(disposed),never_held=bool(never_held),released=bool(actual_return or disposed or never_held)))
 ok=source_pins(report) and inert_ok and all(x['released'] for x in roles)
 return dict(restoration_verified=ok,control_release_verified=ok,return_verified=ok and all(x['returned'] for x in roles),disposed_verified=ok and any(x['disposed'] for x in roles),actors=roles,semantics='two_independent_native_pool_returns_or_readonly_disposal',completion_claim=False)

def origin_verified(report):
 rq=report.get('request',{});pre=report.get('preflight',{});origin=rq.get('safe_origin',{});front=pre.get('selected',{});support=pre.get('support',{})
 return origin.get('origin_method')=='current_verified_owned_movable_positions' and origin.get('viewer_player_id')==pre.get('player_id')==3 and origin.get('front_id')==front.get('object_id') and origin.get('support_id')==support.get('object_id') and origin.get('observed_frame')==pre.get('frame') and distance(origin.get('front_initial'),front.get('xyz'))<=.01 and distance(origin.get('support_initial'),support.get('xyz'))<=.01 and origin.get('currently_visible_enemy_threats_within350')==[]

def lease_override_audit(report):
 n=report.get('native',{});ev=report.get('events',[]);pre=report.get('preflight',{});roles=[]
 for role,counts in [(0,n),(1,n.get('support',{}))]:
  events=[e for e in ev if e.get('role')==role];starts=[e for e in events if e.get('kind')==1 and e.get('tag')==1];ends=[e for e in events if e.get('kind')==5 and e.get('tag')==3];baselines=[e for e in events if e.get('kind')==71]
  boundaries=len(starts)==len(ends)==len(baselines)==1 and baselines[0]['seq']<starts[0]['seq']<ends[0]['seq'] and starts[0].get('frame')==n.get('issued_frame') and starts[0].get('team')==int(pre.get('script_team','0'),0) and ends[0].get('team')==int(pre.get('default_team','0'),0)
  overrides=[e for e in events if boundaries and starts[0]['seq']<e['seq']<ends[0]['seq'] and e.get('tag')==0 and e.get('kind') in (10,12,14,16,18,30,50) and not(e.get('kind')==30 and e.get('lease_stage')==3)]
  counters_zero=all(counts.get('native_'+key)==0 for key in ['move','attack','add','remove','stop'])
  roles.append(dict(role=role,boundaries_verified=boundaries,override_event_sequences=[e['seq'] for e in overrides],counters_zero=counters_zero,verified=boundaries and not overrides and counters_zero))
 return dict(verified=all(r['verified'] for r in roles),roles=roles)

def qualify(report):
 n=report.get('native',{});rq=report.get('request',{});pre=report.get('preflight',{});events=report.get('events',[]);support=n.get('support',{});route=[p.get('xyz') for p in rq.get('route',[])];front_id=pre.get('selected',{}).get('object_id');support_id=pre.get('support',{}).get('object_id');owner=int(pre.get('owner','0'),0);thread=pre.get('window_thread');issued=n.get('issued_frame',0);returned=n.get('returned_frame',0);attack=n.get('attack_issued_frame',0);retreat=n.get('retreat_started',0);safe_front=n.get('safe_front');safe_support=n.get('safe_support');checks={}
 checks['finished_and_source_pinned']=report.get('status')=='finished' and report.get('host_exit')==0 and report.get('executable_sha256')==EXE and source_pins(report)
 checks['launch_intent']=report.get('native_launch_intent_persisted') is True
 checks['session_order_actor_binding']=bool(front_id) and bool(support_id) and front_id!=support_id and pre.get('player_id')==3 and pre.get('selected',{}).get('type_hash')=='0x19ab11af' and pre.get('support',{}).get('type_hash')=='0x2c358c61' and rq.get('front_id')==front_id and rq.get('support_id')==support_id==support.get('id') and n.get('session_id')==pre.get('session_id')==report.get('session_id') and n.get('commander_id')==pre.get('commander_id') and n.get('command_id')==rq.get('command_id') and n.get('task_id')==rq.get('task_id') and type(rq.get('seq')) is int and rq['seq']>0 and n.get('seq')==rq['seq']
 checks['explicit_current_ground_contact']=bool(rq.get('target_contact_id')) and report.get('private_target',{}).get('object_id')==rq.get('target_object_id')==n.get('target_id') and report.get('private_target',{}).get('owner_player_id') not in (None,3) and target_scope(report)
 checks['published_monotonic_finite']=bool(events) and all(e.get('seq')==i+1 and all(finite(e.get(k)) for k in ('x','y','z','own_hp','damage_before','damage_after','damage_reported')) for i,e in enumerate(events)) and all(b.get('frame',0)>=a.get('frame',0) and 0<=((b.get('tick',0)-a.get('tick',0))&0xffffffff)<0x80000000 for a,b in zip(events,events[1:]))
 checks['thread_and_role_identity']=bool(events) and n.get('callback_thread')==thread and all(e.get('thread')==thread and (e.get('kind')==4 or e.get('owner')==owner and e.get('unit_id')==(support_id if e.get('role')==1 else front_id)) for e in events)
 checks['deadline_and_stage_order']=0<issued<attack<retreat<returned<=rq.get('expires_frame',0) and n.get('mission_deadline_frame')==rq.get('expires_frame') and returned-issued<=rq.get('lease_frames',0) and n.get('mission_stage')==4
 checks['raw_route_and_safe_origin']=2<=len(route)<=16 and all(point(p) for p in route) and point(safe_front) and point(safe_support) and distance(safe_front,rq.get('safe_origin',{}).get('front_initial'))<=40 and distance(safe_support,rq.get('safe_origin',{}).get('support_initial'))<=40 and origin_verified(report)
 if not checks['raw_route_and_safe_origin'] or not checks['published_monotonic_finite']:
  return dict(status='not_passed',checks=checks,effect_verified=False,source_damage_amount=0,approach_verified=False,retreat_verified=False,restoration_verified=control_release(report)['restoration_verified'],combined_arms_verified=False,qualified_hits=[],paired_stages=[])
 checks['longer_than_old_primitive']=sum(distance(a,b) for a,b in zip([safe_front]+route[:-1],route))>120
 initial_visible=[e for e in events if e.get('role')==0 and e.get('target_visible')==1 and point(e.get('visible_target_xyz')) and issued<=e.get('frame',0)<attack]
 approach_end=[e for e in events if e.get('role')==0 and e.get('kind')==64]
 retreat_start=[e for e in events if e.get('role')==0 and e.get('kind')==63]
 retreat_end=[e for e in events if e.get('role')==0 and e.get('kind')==66]
 checks['long_approach_actual_displacement']=bool(initial_visible) and distance(safe_front,initial_visible[0]['visible_target_xyz'])>=300 and len(approach_end)==1 and distance(safe_front,xyz(approach_end[0]))>=120
 checks['long_retreat_actual_displacement']=len(retreat_start)==len(retreat_end)==1 and distance(xyz(retreat_start[0]),xyz(retreat_end[0]))>=120 and distance(xyz(retreat_end[0]),safe_front)<=15
 stages=stage_audit(events,route,safe_front,safe_support,1)+stage_audit(events,route,safe_front,safe_support,3)
 checks['every_approach_stage_raw']=n.get('approach_completed')==len(route) and all(s['verified'] for s in stages if s['mission_stage']==1)
 checks['every_retreat_stage_raw']=n.get('retreat_completed')==len(route) and all(s['verified'] for s in stages if s['mission_stage']==3) and n.get('front_retreat_arrivals')==n.get('support_retreat_arrivals')==3
 orders=[e for e in events if e.get('kind') in (34,12,13,35) and e.get('role')==0 and e.get('tag')==2]
 checks['one_new_normal_front_order']=len(orders)==4 and [e['kind'] for e in orders]==[34,12,13,35] and all(e.get('frame')==attack and e.get('arg')==rq.get('target_object_id') and e.get('arg_source')==1 and e.get('arg_shots')==0x7fffffff and e.get('target_visible')==1 and e.get('mission_stage')==2 for e in orders) and n.get('attack_calls')==n.get('attack_facade_calls')==n.get('attack_private_calls')==1
 # Source-bound direct AK packet + actual Body/commit + same-entry ammo, all inside this new order.
 hits=[];pairs=raw_pairs(events)
 for e in events:
  if e.get('kind')!=20 or e.get('role')!=0 or e.get('mission_stage')!=2 or e.get('target_visible')!=1 or e.get('damage_source')!=front_id or e.get('target_id')!=rq.get('target_object_id') or not attack<=e['frame']<retreat:continue
  packets=damage_packet(e,front_id,report.get('private_target',{}).get('address'))
  commits=[x for x in events if x.get('kind')==24 and x.get('role')==0 and x.get('target_visible')==1 and x.get('damage_source')==front_id and x.get('frame')==e['frame'] and x['seq']<e['seq'] and abs(x.get('damage_before',0)-e['damage_before'])<.05 and abs(x.get('damage_after',0)-e['damage_after'])<.05]
  ammo=[x for x in events if x.get('kind')==22 and x.get('role')==0 and x.get('damage_source')==front_id and 0<=x.get('frame',-100)-e['frame']<=3 and x.get('seq',0)>e['seq'] and x.get('active_weapon_asset')==0x447ea26e and x.get('active_weapon_entry')==n.get('weapon_entry') and x.get('damage_before',0)>x.get('damage_after',0)]
  near=[pair for pair in pairs if pair[0].get('mission_stage')==2 and abs(pair[0]['frame']-e['frame'])<=3 and geometry(pair,pair[0]['front_goal'],pair[0]['support_goal'],True)]
  if packets and commits and ammo and near and e['damage_before']>e['damage_after'] and abs(e['damage_before']-e['damage_after']-e['damage_reported'])<.05:hits.append(dict(body_event_seq=e['seq'],commit_event_seq=commits[0]['seq'],ammo_event_seq=ammo[0]['seq'],paired_support_frame=near[0][0]['frame'],damage=e['damage_reported'],packet=packets[0]))
 binding=report.get('weapon_asset_binding',{})
 checks['front_source_damage_and_support_position']=bool(hits) and binding.get('session_id')==report['session_id'] and binding.get('pid')==pre.get('pid') and binding.get('asset_type')=='0x94d4d96e' and binding.get('asset_id')=='0x447ea26e' and binding.get('reported_template')==hex(n.get('weapon_template',0)) and binding.get('reported_entry')==hex(n.get('weapon_entry',0))
 checks['support_never_assigned_ground_attack']=not any(e.get('role')==1 and e.get('kind') in (12,13,34,35) and issued<=e.get('frame',0)<returned for e in events) and support.get('native_attack')==0
 # Reconstruct each actual Stop boundary immediately preceding a route Move or front Attack gate.
 movements=[e for e in events if e.get('kind')==50 and e.get('tag')==6]
 move_bounds=[]
 for move in movements:
  role=move['role'];ev=[e for e in events if e.get('role')==role and e['seq']<move['seq']];stops=[e for e in ev if e.get('kind')==33 and e.get('caller')==0x787791 and e.get('arg')==1]
  if not stops:move_bounds.append(False);continue
  stop=stops[-1];samples=[dict(e,kind=3) for e in ev if e['kind']==3 and e['seq']>stop['seq']];gate=dict(move,kind=24);translated=[dict(stop,kind=23)]+samples+[gate];boundary=settled_stop(translated)
  following=[e for e in events if move['seq']<=e['seq']<=move['seq']+5 and e.get('role')==role and e.get('kind') in (50,10,11,51)]
  goal=move['support_goal'] if role else move['front_goal']
  move_bounds.append(boundary['verified'] and len(following)==4 and [e['kind'] for e in following]==[50,10,11,51] and all(e.get('arg')==1 and same(e.get('command_xyz'),goal) for e in following) and following[1].get('argument_path')==0)
 checks['normal_moves_have_raw_stop_and_input_chain']=len(movements)==len(route)*4 and bool(move_bounds) and all(move_bounds)
 checks['no_native_override']=lease_override_audit(report)['verified']
 manager=int(pre.get('ai','0'),0)+0x104
 returned_roles=[]
 for role in (0,1):
  removed=[e for e in events if e.get('role')==role and e.get('kind')==18 and e.get('tag')==1 and e.get('arg')==manager and e.get('caller')==0x838877]
  added=[e for e in events if e.get('role')==role and e.get('kind')==16 and e.get('tag')==3 and e.get('arg')==manager]
  gates=[e for e in events if e.get('role')==role and e.get('kind')==66];stops=[e for e in events if e.get('role')==role and e.get('kind')==33 and e.get('lease_stage')==2]
  final_stop=settled_stop([dict(e,kind=23 if e['kind']==33 else 24 if e['kind']==66 else 3) for e in events if e.get('role')==role and e.get('lease_stage')==2 and e.get('kind') in (3,33,66)])
  returned_roles.append(len(removed)==len(added)==len(gates)==len(stops)==1 and final_stop['verified'] and gates[0]['seq']<added[0]['seq'])
 checks['two_normal_pool_returns_after_retreat']=all(returned_roles) and n.get('detach_calls')==n.get('return_calls')==n.get('return_verified')==1 and support.get('detach_calls')==support.get('return_calls')==support.get('returned')==1
 inert=report.get('terminal_readonly',{})
 checks['native_hooks_timer_terminal']=n.get('phase')==3 and n.get('error')==0 and n.get('restore_mask')==8191 and n.get('active')==0 and n.get('overflow')==0 and n.get('lifecycle_fail')==0 and inert.get('timer')==0 and inert.get('binding_verified') is True and inert.get('phase')==3 and inert.get('error')==0 and inert.get('restore_mask')==8191 and inert.get('active')==0 and inert.get('front_return_verified')==inert.get('support_return_verified')==1 and terminal_entries_verified(inert.get('entries',[]))
 complete=all(checks.values())
 return dict(status='formation_mission_effect_retreat_verified' if complete else 'not_passed',checks=checks,effect_verified=bool(hits),source_damage_amount=sum(hit['damage'] for hit in hits),approach_verified=checks['every_approach_stage_raw'] and checks['long_approach_actual_displacement'],long_approach_verified=checks['long_approach_actual_displacement'],retreat_verified=checks['every_retreat_stage_raw'] and checks['long_retreat_actual_displacement'],long_retreat_verified=checks['long_retreat_actual_displacement'],restoration_verified=checks['native_hooks_timer_terminal'] and checks['two_normal_pool_returns_after_retreat'],combined_arms_verified=complete,qualified_hits=hits,paired_stages=stages,role_scope='Conscript actual direct AK damage; Flak positional following/holding only, no ground firing claim')
