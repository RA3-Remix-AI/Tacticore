"""Read-only finite waypoint plan from this player's observed routes; no enemy scan."""
import argparse,collections,hashlib,importlib.util,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('finite_scout_ground',HERE.parent/'ground-normal-terrain-aux/lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--routes',type=Path,required=True);p.add_argument('--object-id',type=int,required=True);p.add_argument('--goal-point-report',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();pre,s,raw,*rest=b.readiness(a.session,a.object_id);m=rest[-1]
 try:
  own=b.own_candidates(m,3,b.load_catalog())['candidates'];homes=[u for u in own if u['type_hash']=='0xc16ff13f']
  if len(homes)!=1:raise ValueError('one_own_home_required')
  origin=homes[0]['xyz'];actor=pre['selected'];cells={}
  for path in a.routes.glob('*.json'):
   packet_raw=path.read_bytes();packet=json.loads(packet_raw.decode('utf-8-sig'))
   if packet.get('session_id')!=s['session_id'] or packet.get('pid')!=s['pid'] or packet.get('player_id')!=3 or not 0<packet.get('logic_frame_candidate',0)<=pre['frame']:continue
   for unit in packet.get('own_objects',[]):
    xyz=unit['xyz'];kind=unit['type_hash']
    if kind not in ('0x33026fa1','0x19ab11af','0x2c358c61') or unit['hp']<=0 or not all(math.isfinite(x) for x in xyz):continue
    if kind!='0x33026fa1' and ('status84' not in unit or int(unit['status84'],0)&(0x20000000|0x80000)):continue
    if any(u['object_id']!=actor['object_id'] and math.dist(u['xyz'][:2],xyz[:2])<30 and abs(u['xyz'][2]-xyz[2])<10 for u in own):continue
    cell=tuple(round(v/20) for v in xyz)
    cells[cell]=dict(path=str(path.resolve()),source_sha256=hashlib.sha256(packet_raw).hexdigest(),source_object_id=unit['object_id'],type_hash=kind,xyz=xyz,observed_frame=packet['logic_frame_candidate'])
  nodes=list(cells.values())
  if not nodes:raise ValueError('no_free_actual_own_route_points')
  if a.goal_point_report:
   desired=json.loads(a.goal_point_report.read_text(encoding='utf-8-sig'))
   if desired['session_id']!=s['session_id'] or desired['player_id']!=3 or desired['pid']!=s['pid']:raise ValueError('goal_not_own_current_session')
   goal=min(range(len(nodes)),key=lambda i:math.dist(nodes[i]['xyz'],desired['own_objects'][0]['xyz']))
  else:goal=max(range(len(nodes)),key=lambda i:math.dist(nodes[i]['xyz'][:2],origin[:2]))
  start=len(nodes);positions=[x['xyz'] for x in nodes]+[actor['xyz']];queue=collections.deque([start]);previous={start:None};depth={start:0}
  while queue and goal not in previous:
   at=queue.popleft()
   if depth[at]>=6:continue
   candidates=sorted((i for i in range(len(nodes)) if i not in previous),key=lambda i:math.dist(positions[i][:2],positions[goal][:2]))
   for i in candidates:
    distance=math.dist(positions[at][:2],positions[i][:2])
    if not 30<=distance<=550 or abs(positions[at][2]-positions[i][2])>300:continue
    previous[i]=at;depth[i]=depth[at]+1;queue.append(i)
  if goal not in previous:raise ValueError('no_bounded_six_lease_route')
  route=[];at=goal
  while at!=start:route.append(nodes[at]);at=previous[at]
  route.reverse();report=dict(session_id=s['session_id'],pid=s['pid'],frame=pre['frame'],actor=actor,own_home=origin,waypoints=route,model_eligible=False,sdk_calls=0,policy='up_to_six_actual_own_route_waypoints_toward_farthest_observed_own_ground_route_from_own_home',note='Only past own positions. Reaching each waypoint is unproven until actual native arrival; terrain/water/obstacle issues remain possible and must fail honestly.')
  b.durable(a.output,report);print(json.dumps(dict(output=str(a.output),actor=actor['object_id'],waypoints=len(route),points=[x['xyz'] for x in route])))
 finally:m.close()
if __name__=='__main__':main()
