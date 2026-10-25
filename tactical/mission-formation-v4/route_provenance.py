"""Ground-positive owned-route provenance and occupancy. Local source files only; no game calls."""
import hashlib,importlib.util,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mfm4_rebase_role_geometry',HERE/'role_route_planner.py');roles=importlib.util.module_from_spec(spec);spec.loader.exec_module(roles)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.loads(json.dumps(value,allow_nan=False))
def source_records(points,session,frame,owner,minimum_points=2):
 if not isinstance(points,list) or not minimum_points<=len(points)<=16:raise ValueError('rebase_original_route_count')
 records=[];collector=sha(HERE.parent.parent/'integration/ground_history.py');reader=sha(HERE.parent/'grounded_status_v2.py')
 for index,node in enumerate(points):
  path=Path(node['own_source_path']).resolve();raw=path.read_bytes();source=json.loads(raw.decode('utf-8-sig'));digest=hashlib.sha256(raw).hexdigest()
  if digest!=node['own_source_sha256'] or source.get('session_id')!=session['session_id'] or source.get('pid')!=session['pid'] or source.get('player_id')!=3 or type(source.get('logic_frame_candidate')) is not int or not 0<source['logic_frame_candidate']<=frame:raise ValueError('rebase_route_source_binding')
  if source.get('method')!='same_frame_owned_position_with_verified_native_surface' or source.get('source_collector_sha256')!=collector or source.get('ground_reader_sha256')!=reader or source.get('mutations') is not False or source.get('walkable_route_verified') is not False:raise ValueError('rebase_route_source_method')
  rows=[x for x in source.get('own_objects',[]) if x.get('object_id')==node['own_source_object_id']]
  if len(rows)!=1 or not roles.positive_ground(rows[0]) or not roles.point(node.get('xyz')) or math.dist(rows[0]['xyz'],node['xyz'])>.01 or node.get('observed_frame')!=source['logic_frame_candidate']:raise ValueError('rebase_route_positive_source_position')
  g=rows[0]['grounded_status']
  if g.get('owner')!=owner or g.get('object_id')!=rows[0]['object_id'] or g.get('type_hash')!=rows[0]['type_hash'] or g.get('frame')!=source['logic_frame_candidate']:raise ValueError('rebase_route_owner_or_frame')
  records.append(dict(index=index,path=str(path),sha256=digest,object_id=rows[0]['object_id'],observed_frame=source['logic_frame_candidate'],xyz=list(rows[0]['xyz'])))
 return records
def occupancy(points,owned,actor_ids):
 for node in points:
  if any(x['object_id'] not in actor_ids and roles.xy(x['xyz'],node['xyz'])<20 and abs(x['xyz'][2]-node['xyz'][2])<10 for x in owned):raise ValueError('rebase_route_current_own_occupant')
 return True
