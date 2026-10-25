"""Read-only goal coverage, not a route or walkability claim."""
import hashlib,importlib.util,json,math,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
roles=load('mfm4_coverage_ground',HERE/'role_route_planner.py')
proof=load('mfm4_coverage_source',HERE/'route_provenance.py')

def covered_goal(history,session,frame,owner,target,deadline):
 for path in sorted(Path(history).glob('*.json'),reverse=True):
  if time.monotonic()>deadline:raise ValueError('coverage_read_budget_exceeded')
  raw=path.read_bytes()
  try:
   source=json.loads(raw.decode('utf-8-sig'))
   if source.get('session_id')!=session['session_id'] or source.get('pid')!=session['pid'] or source.get('player_id')!=3 or not 0<source.get('logic_frame_candidate',0)<=frame:continue
   for row in source.get('own_objects',[]):
    if not roles.point(row.get('xyz')) or math.dist(row['xyz'][:2],target[:2])>300 or not roles.positive_ground(row):continue
    point=dict(xyz=row['xyz'],own_source_path=str(path.resolve()),own_source_sha256=hashlib.sha256(raw).hexdigest(),own_source_object_id=row['object_id'],observed_frame=source['logic_frame_candidate'])
    proof.source_records([point],session,frame,owner,minimum_points=1)
    return dict(source_point=point,distance_to_visible_contact=math.dist(row['xyz'][:2],target[:2]),route_planning_performed=False,walkable_route_verified=False,mutations=False)
  except (ValueError,TypeError,KeyError):continue
 return None
