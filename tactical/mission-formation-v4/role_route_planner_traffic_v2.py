"""Pure role-aware planning from owned, positively grounded source records.

No process, game command, enemy enumeration, interpolation, or claim of walkable
edges. The frozen wrapper still validates explicit-route provenance and actors.
"""
import collections
import hashlib
import heapq
import importlib.util
import json
import math
import time
from pathlib import Path

ALLOWED={'0x19ab11af':'SovietAntiInfantryInfantry','0x2c358c61':'SovietAntiVehicleInfantry'}
_traffic_spec=importlib.util.spec_from_file_location('mfm4_traffic_planner_policy',Path(__file__).parent/'traffic_occupancy_v2.py')
traffic=importlib.util.module_from_spec(_traffic_spec);_traffic_spec.loader.exec_module(traffic)
_SOURCE_CACHE={}
LAST_DIAGNOSTICS={}
class RoutePlanningError(ValueError):
    def __init__(self,reason,diagnostics):super().__init__(reason);self.diagnostics=diagnostics

def point(p):
    return isinstance(p,(list,tuple)) and len(p)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in p)

def xy(a,b):return math.dist(a[:2],b[:2])

def pair_priority(front,support,visible_target):
    """Prioritize a front already ahead toward the explicit observed target."""
    a=front['xyz'];s=support['xyz'];v=visible_target
    wx,wy=a[0]-s[0],a[1]-s[1];vx,vy=v[0]-a[0],v[1]-a[1]
    denom=math.hypot(wx,wy)*math.hypot(vx,vy)
    return (-(vx*wx+vy*wy)/denom if denom else 1,math.hypot(vx,vy))

def segment_clearance(a,b,p):
    vx,vy=b[0]-a[0],b[1]-a[1]
    t=max(0.,min(1.,((p[0]-a[0])*vx+(p[1]-a[1])*vy)/(vx*vx+vy*vy))) if vx*vx+vy*vy else 0.
    return math.hypot(a[0]+t*vx-p[0],a[1]+t*vy-p[1])

def leg_geometry(front,support,goal,first=False):
    if not all(point(x) for x in (front,support,goal)):return False
    return _finite_leg_geometry(front,support,goal,first)

def _finite_leg_geometry(front,support,goal,first=False):
    vx,vy=goal[0]-front[0],goal[1]-front[1];wx,wy=front[0]-support[0],front[1]-support[1]
    length2=vx*vx+vy*vy
    if not (3600<=length2<=19600 if first else 1600<=length2<=25600):return False
    if abs(front[2]-goal[2])>100:return False
    # The moving front must continue away from its held support, not reverse
    # through that actor. Both straight commanded segments exclude the holder.
    # With v dot w >= 0 the closest point on front->goal to support is
    # front, and the closest point on support->front to goal is front.
    # Thus both original segment tests reduce exactly to these squared bounds.
    return vx*wx+vy*wy>=0 and wx*wx+wy*wy>=625

def route_geometry(front,support,route):
    if not 25<=xy(front,support)<=180 or not 2<=len(route)<=16:return False
    f,s=front,support
    pairs=[(list(f),list(s))]
    for i,node in enumerate(route):
        q=node['xyz']
        if not leg_geometry(f,s,q,i==0):return False
        f,s=q,f;pairs.append((list(f),list(s)))
    # Reverse sequence is support-first, exactly as the native backend. Exclude
    # the stationary front and then stationary support at every reverse stage.
    for (f,s),(fg,sg) in zip(reversed(pairs[1:]),reversed(pairs[:-1])):
        if segment_clearance(s,sg,f)<25 or segment_clearance(f,fg,sg)<25:return False
    return True

def positive_ground(row,fingerprints=None):
    """Independently verify version-2 native surface evidence, never flag160."""
    g=row.get('grounded_status',{});words=g.get('status_words')
    if row.get('grounded_verified') is not True or g.get('grounded_verified') is not True or not isinstance(words,list) or len(words)!=7:return False
    if g.get('schema_version')!=2 or g.get('status')!='verified_native_surface_sample' or g.get('source')!='ground_only_template_plus_valid_native_surface_cache_and_air_exclusions_v2':return False
    if g.get('atomic_sample_verified') is not True:return False
    fingerprints=fingerprints or {key:hashlib.sha256((Path(__file__).parent.parent/name).read_bytes()).hexdigest() for key,name in [('helper_sha256','grounded_status_v2.py'),('native_status_helper_sha256','grounded_status.py')]}
    if any(g.get(key)!=value for key,value in fingerprints.items()):return False
    if row.get('type_hash') not in ALLOWED or g.get('template')!=ALLOWED[row['type_hash']]:return False
    try:words=[int(x,0) if isinstance(x,str) else x for x in words]
    except (TypeError,ValueError):return False
    if any(type(x) is not int or not 0<=x<=0xffffffff for x in words):return False
    bit=lambda i:bool(words[i>>5]&(1<<(i&31)))
    if any(bit(i) for i in (0,7,8,161,207,211,51,61)):return False
    flags={k:bit(i) for k,i in [('AIRBORNE_TARGET',7),('PARACHUTING',8),('GROUND_LOCOMOTOR_ACTIVE',160),('AIR_LOCOMOTOR_ACTIVE',161),('LANDING_IN_PROGRESS',207),('LIFTED_INTO_AIR',211),('INSIDE_GARRISON',61),('IMMOBILE',51)]}
    if g.get('flags')!=flags or g.get('known_air_state') is not False or g.get('ground160_diagnostic')!=bit(160) or g.get('ground_positive') is not True:return False
    try:cache=int(g['height_cache_flags'],0);holder=int(g['holder'],0);owner=int(g['owner'],0);address=int(g['address'],0)
    except (KeyError,TypeError,ValueError):return False
    if owner<=0 or address<=0 or type(g.get('object_id')) is not int or g['object_id']<=0 or type(g.get('frame')) is not int or g['frame']<=0 or g['frame']!=g.get('end_frame'):return False
    h=g.get('cached_height_distance');hp=g.get('hp')
    return (cache&4!=0 and g.get('height_cache_valid') is True and holder==0 and type(h) in (int,float) and math.isfinite(h) and abs(h)<=.5 and g.get('height_tolerance')==.5 and type(hp) in (int,float) and math.isfinite(hp) and hp>0 and hp==row.get('hp') and point(g.get('xyz')) and g['xyz']==row.get('xyz') and g.get('mutations') is False and g.get('walkable_route_verified') is False)

def plan_from_history(history_dir,pre,session,front,support,current_visible_xyz,own_candidates,planning_deadline=None):
    global LAST_DIAGNOSTICS
    started=time.monotonic();stats=dict(phase='load_sources',source_records=0,ground_nodes=0,expanded_states=0,reject_reasons={})
    def fail(reason):
        global LAST_DIAGNOSTICS
        stats['elapsed_seconds']=time.monotonic()-started;LAST_DIAGNOSTICS=dict(stats);raise RoutePlanningError(reason,dict(stats))
    def reject(reason):stats['reject_reasons'][reason]=stats['reject_reasons'].get(reason,0)+1
    deadline=time.monotonic()+1 if planning_deadline is None else planning_deadline
    if time.monotonic()>=deadline:fail('role_route_search_budget_exhausted')
    if not all(point(p) for p in (front['xyz'],support['xyz'],current_visible_xyz)):raise ValueError('finite_private_points_required')
    nodes={};selected={front['object_id'],support['object_id']}
    hard_occupants,mobile_traffic=traffic.partition(own_candidates,selected,pre['owner'])
    fingerprints={key:hashlib.sha256((Path(__file__).parent.parent/name).read_bytes()).hexdigest() for key,name in [('helper_sha256','grounded_status_v2.py'),('native_status_helper_sha256','grounded_status.py')]};reader_sha=fingerprints['helper_sha256']
    for source in sorted(Path(history_dir).glob('*.json')):
        if time.monotonic()>=deadline:fail('role_route_search_budget_exhausted')
        stats['source_records']+=1
        stat=source.stat();key=str(source.resolve());stamp=(stat.st_mtime_ns,stat.st_size);cached=_SOURCE_CACHE.get(key)
        if cached and cached[0]==stamp:record,source_sha=cached[1:]
        else:
            raw=source.read_bytes();record=json.loads(raw.decode('utf-8-sig'));source_sha=hashlib.sha256(raw).hexdigest();_SOURCE_CACHE[key]=(stamp,record,source_sha)
        frame=record.get('logic_frame_candidate',0)
        if record.get('session_id')!=session['session_id'] or record.get('pid')!=session['pid'] or record.get('player_id')!=3 or not 0<frame<=pre['frame']:reject('source_session_or_clock');continue
        if record.get('method')!='same_frame_owned_position_with_verified_native_surface' or record.get('ground_reader_sha256')!=reader_sha:reject('source_method_or_reader');continue
        for row in record.get('own_objects',[]):
            p=row.get('xyz');g=row.get('grounded_status',{})
            if row.get('type_hash') not in ALLOWED or not point(p) or row.get('hp',0)<=0 or not positive_ground(row,fingerprints):reject('not_positive_native_surface');continue
            if g.get('object_id')!=row['object_id'] or g.get('type_hash')!=row['type_hash'] or g.get('frame')!=frame or g.get('end_frame')!=frame:reject('surface_identity_or_clock');continue
            if any(xy(o['xyz'],p)<20 and abs(o['xyz'][2]-p[2])<10 for o in hard_occupants):reject('current_hard_own_occupant');continue
            key=tuple(math.floor(v/40) for v in p)
            nodes[key]=dict(xyz=list(p),observed_frame=frame,own_source_path=str(source.resolve()),own_source_sha256=source_sha,own_source_object_id=row['object_id'],traffic_cost=sum(xy(o['xyz'],p)<20 and abs(o['xyz'][2]-p[2])<10 for o in mobile_traffic))
    data=list(nodes.values())
    stats.update(hard_occupants=len(hard_occupants),verified_mobile_traffic=len(mobile_traffic))
    stats['ground_nodes']=len(data);stats['phase']='role_graph_search'
    if not data:fail('no_positive_native_ground_history_unknown_is_not_ground')
    stats['closest_ground_point_to_target']=min(xy(n['xyz'],current_visible_xyz) for n in data)
    stats['goal_nodes']=sum(xy(n['xyz'],current_visible_xyz)<=300 for n in data)
    stats['first_leg_candidates']=sum(_finite_leg_geometry(front['xyz'],support['xyz'],n['xyz'],True) for n in data)
    if not stats['goal_nodes']:fail('no_positive_ground_history_near_explicit_visible_contact')
    if not stats['first_leg_candidates']:fail('no_role_safe_first_leg_from_current_pair')
    # State includes the held support node: visiting one front node with another
    # predecessor is a different formation state and may admit a safe turn.
    buckets=collections.defaultdict(list)
    for i,n in enumerate(data):buckets[(math.floor(n['xyz'][0]/160),math.floor(n['xyz'][1]/160))].append(i)
    heuristic=lambda xyz:math.ceil(max(0,xy(xyz,current_visible_xyz)-300)/160)
    states=[(0,heuristic(front['xyz']),0,0,front['xyz'],support['xyz'],[])];serial=0
    seen={};solutions=[];expansions=0
    while states and expansions<12000:
        if time.monotonic()>=deadline:fail('role_route_search_budget_exhausted')
        _,_,cost,_,f,s,route=heapq.heappop(states);expansions+=1
        stats['expanded_states']=expansions
        if len(route)>=2 and xy(f,current_visible_xyz)<=300 and route_geometry(front['xyz'],support['xyz'],route):
            solutions.append(route)
            break  # A verified feasible route is sufficient; never exhaust all paths.
        if len(route)>=16:continue
        cell=(math.floor(f[0]/160),math.floor(f[1]/160));near=[]
        for x in range(cell[0]-1,cell[0]+2):
            for y in range(cell[1]-1,cell[1]+2):near.extend(buckets.get((x,y),[]))
        order=sorted(near,key=lambda i:(data[i]['traffic_cost'],xy(data[i]['xyz'],current_visible_xyz)))
        for i in order:
            n=data[i];q=n['xyz']
            if not _finite_leg_geometry(f,s,q,not route):reject('leg_geometry');continue
            if any(x['own_source_path']==n['own_source_path'] for x in route):reject('route_source_cycle');continue
            state=(i,tuple(round(v,2) for v in f))
            depth=len(route)+1
            if seen.get(state,17)<=depth:continue
            seen[state]=depth;serial+=1
            first_distance=xy(front['xyz'],route[0]['xyz'] if route else q)
            first_margin_penalty=max(0,100-first_distance,first_distance-120)
            next_cost=cost+n['traffic_cost']
            heapq.heappush(states,(first_margin_penalty,depth+heuristic(q)+next_cost*.25,next_cost,serial,q,f,route+[n]))
    if not solutions:fail('no_role_safe_bounded_actual_own_route')
    route=min(solutions,key=lambda r:(xy(r[-1]['xyz'],current_visible_xyz),len(r)))
    if sum(xy(a,z['xyz']) for a,z in zip([front['xyz']]+[n['xyz'] for n in route[:-1]],route))<=120:raise ValueError('route_does_not_establish_far_approach')
    stats['elapsed_seconds']=time.monotonic()-started;LAST_DIAGNOSTICS=dict(stats)
    return dict(schema_version=1,session_id=session['session_id'],pid=session['pid'],player_id=3,front_id=front['object_id'],support_id=support['object_id'],route=route,model_eligible=False,source='positive_ground_own_positions_role_aware',walkable_route_verified=False,target_selection='explicit_current_visible_contact_only',planning_diagnostics=stats)
