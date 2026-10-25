"""Private own-position history and bounded routes; never reads hidden enemies.

Record from the host's own snapshot. End-point scoring receives one separately
verified visible contact position, never enumerates adversary objects.
"""
import collections,hashlib,json,math,struct,time
from pathlib import Path
ALLOWED={'0x19ab11af','0x2c358c61','0x33026fa1'}
LAST={}
def point(value):return isinstance(value,(list,tuple)) and len(value)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in value)
def record_history(memory,session,own_snapshot,frame,history_dir):
 path=Path(history_dir);logic=memory.u32(0xcd8ce4);start=memory.u32(logic+0x50)
 if memory.u32(logic)!=0xbeb630 or not 0<frame<=start<=frame+2:raise ValueError('own_history_clock')
 saved=[]
 for item in own_snapshot.get('candidates',[]):
  kind=item.get('type_hash');oid=item.get('object_id')
  if kind not in ALLOWED or item.get('owner_index_candidate')!=3:continue
  t=int(item['address'],0);owner=int(item['owner_address'],0);flags=memory.u32(t+0x84)
  if flags&0x20080000:continue
  xyz=list(struct.unpack('<fff',memory.read(t+0x38,12)));hp=memory.f32(memory.u32(t+0x33c)+4)
  if not point(xyz) or not math.isfinite(hp) or hp<=0 or memory.u32(t)!=0xc4db60 or memory.u32(t+0xdc)!=oid or memory.u32(t+0x418)!=owner or memory.u32(owner+0x20)!=3 or memory.u32(memory.u32(t+4)+8)!=int(kind,0):continue
  key=(session['session_id'],oid);old=LAST.get(key)
  if old and math.dist(xyz,old)<20:continue
  if memory.u32(t+0x84)!=flags:continue
  saved.append(dict(object_id=oid,type_hash=kind,xyz=xyz,hp=hp,status84=hex(flags)))
 end=memory.u32(logic+0x50)
 if memory.u32(0xcd8ce4)!=logic or not start<=end<=start+2:raise ValueError('own_history_non_atomic')
 if not saved:return 0
 path.mkdir(parents=True,exist_ok=True);source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 for row in saved:
  target=path/(str(start).zfill(8)+'-'+str(row['object_id'])+'.json')
  if target.exists():continue
  data=dict(schema_version=1,session_id=session['session_id'],pid=session['pid'],player_id=3,logic_frame_candidate=start,own_objects=[row],source_collector_sha256=source_sha,method='same_frame_owned_ground_actual_position',mutations=False,model_eligible=False)
  temp=target.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')
  for attempt in range(25):
   try:temp.replace(target);break
   except PermissionError:
    if attempt==24:raise
    time.sleep(.02)
  LAST[(session['session_id'],row['object_id'])]=row['xyz']
 return len(saved)

def plan_from_history(history_dir,pre,session,front,support,current_visible_xyz,own_candidates):
 if not point(current_visible_xyz):raise ValueError('current_visible_contact_point_required')
 nodes={};selected={front['object_id'],support['object_id']}
 for source in sorted(Path(history_dir).glob('*.json')):
  raw=source.read_bytes();record=json.loads(raw.decode('utf-8-sig'))
  if record.get('session_id')!=session['session_id'] or record.get('pid')!=session['pid'] or record.get('player_id')!=3 or not 0<record.get('logic_frame_candidate',0)<=pre['frame']:continue
  for row in record.get('own_objects',[]):
   p=row.get('xyz');kind=row.get('type_hash')
   if kind not in ALLOWED or not point(p) or row.get('hp',0)<=0 or 'status84' not in row or int(row['status84'],0)&0x20080000:continue
   if any(item['object_id'] not in selected and math.dist(item['xyz'][:2],p[:2])<20 and abs(item['xyz'][2]-p[2])<10 for item in own_candidates):continue
   key=(int(p[0]//40),int(p[1]//40),int(p[2]//40))
   nodes[key]=dict(xyz=list(p),own_source_path=str(source.resolve()),own_source_sha256=hashlib.sha256(raw).hexdigest(),own_source_object_id=row['object_id'])
 data=list(nodes.values())
 if not data:raise ValueError('no_private_owned_ground_route_history')
 goals=[i for i,n in enumerate(data) if math.dist(n['xyz'][:2],current_visible_xyz[:2])<=300]
 if not goals:raise ValueError('no_known_own_route_near_explicit_visible_contact')
 start=len(data);positions=[n['xyz'] for n in data]+[front['xyz']];buckets=collections.defaultdict(list)
 for i,p in enumerate(positions[:-1]):buckets[(int(p[0]//160),int(p[1]//160))].append(i)
 previous={start:None};depth={start:0};queue=collections.deque([start]);goal_set=set(goals);reached=[]
 while queue:
  at=queue.popleft()
  if at in goal_set and depth[at]>=2:reached.append(at)
  if depth[at]>=16:continue
  p=positions[at];cell=(int(p[0]//160),int(p[1]//160));near=[]
  for x in range(cell[0]-2,cell[0]+3):
   for y in range(cell[1]-2,cell[1]+3):near.extend(buckets.get((x,y),[]))
  near.sort(key=lambda i:math.dist(positions[i][:2],current_visible_xyz[:2]))
  for i in near:
   if i in previous:continue
   q=positions[i];d=math.dist(p[:2],q[:2])
   if not 40<=d<=170 or abs(p[2]-q[2])>100:continue
   previous[i]=at;depth[i]=depth[at]+1;queue.append(i)
 if not reached:raise ValueError('no_bounded_two_role_route_to_visible_contact')
 best=min(reached,key=lambda i:(math.dist(positions[i][:2],current_visible_xyz[:2]),depth[i]));route=[]
 while best!=start:route.append(data[best]);best=previous[best]
 route.reverse()
 if sum(math.dist(a[:2],z['xyz'][:2]) for a,z in zip([front['xyz']]+[n['xyz'] for n in route[:-1]],route))<=120:raise ValueError('route_does_not_establish_far_approach')
 return dict(schema_version=1,session_id=session['session_id'],pid=session['pid'],player_id=3,front_id=front['object_id'],support_id=support['object_id'],route=route,model_eligible=False,source='actual_private_own_position_history',target_selection='only_high_level_explicit_current_visible_contact')
