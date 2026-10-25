"""Sole-runner calibration selector: one explicit visible static ground target.
No requests, GUI actions, target replacement after dispatch, or retry loop.
"""
import argparse,hashlib,importlib.util,json,math,subprocess,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--natural',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--object-id',type=int);p.add_argument('--target-id',type=int);p.add_argument('--economy',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--backend',choices=['mission-combat','mission-combat-v2','mission-combat-v3'],default='mission-combat');p.add_argument('--min-distance',type=float,default=400);p.add_argument('--max-distance',type=float,default=2600);a=p.parse_args()
 b=load('continuous_field_combat',HERE.parent/a.backend/'lease.py');pre,s,raw,*rest=b.readiness(a.session);m=rest[-1]
 try:
  sys.path[:0]=[str(BRIDGE/'visibility'),str(HERE.parent)]
  from capability import bind_session
  from projection import VisibilityProjection
  from collector import VisibilityCollector
  from mobility_guard import mobility_status
  proof,safety=bind_session(m,s,3);projection=VisibilityProjection(s['session_id'],3,s['mod_sha256'],proof,safety);reader=VisibilityCollector(m,s,3,projection);fresh_frame=m.u32(int(pre['logic'],0)+0x50);reader.collect(fresh_frame/15);pairs=[]
  for cid,target in reader.private_targets.items():
   if a.target_id is not None and target['object_id']!=a.target_id:continue
   if a.economy and target['type_hash']!='0xc45aaeab':continue
   if safety['templates'][target['type_hash']]['role'] not in ('structure','economy'):continue
   for u in pre['units']:
    if u['type_hash']!='0x19ab11af' or not u['eligible'] or u['hp']<75 or a.object_id is not None and u['object_id']!=a.object_id:continue
    if not mobility_status(m,int(u['address'],0))['independently_movable']:continue
    if m.u32(int(u['address'],0)+0x238)!=0:continue
    d=math.dist(u['xyz'][:2],target['xyz'][:2])
    if a.min_distance<=d<=a.max_distance:pairs.append((d,cid,u,target))
  if not pairs:
   diagnostic=dict(status='no_dispatch_no_actor_in_requested_distance_window',session_id=s['session_id'],frame=pre['frame'],requested_min_distance=a.min_distance,requested_max_distance=a.max_distance,sdk_calls=0)
   a.output.parent.mkdir(parents=True,exist_ok=True);a.output.with_name(a.output.stem+'-no-dispatch.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf-8');raise ValueError('no_healthy_free_conscript_and_visible_static_target_with_real_approach_window')
  d,cid,u,t=min(pairs,key=lambda x:x[0]);selection=dict(session_id=s['session_id'],pid=s['pid'],frame=pre['frame'],paused=pre['paused'],actor=u,target=t,target_contact_id=cid,initial_distance=d,model_requests=0,selection_policy='fresh_player3_full_footprint_static_ground_400_to2600_no_hidden_fallback')
  a.output.parent.mkdir(parents=True,exist_ok=True);selection_path=a.output.with_name(a.output.stem+'-selection.json');selection_path.write_text(json.dumps(selection,indent=2),encoding='utf-8');proof_path=a.output.with_name(a.output.stem+'-proof.json');proof_path.write_text(json.dumps(proof,indent=2),encoding='utf-8');mission_path=a.output.with_name(a.output.stem+'-mission.json');mission_path.write_text(json.dumps(dict(schema_version=1)),encoding='utf-8')
  if not a.execute:print(json.dumps(dict(selection=str(selection_path),actor=u['object_id'],target=t['object_id'],contact=cid,distance=d,frame=pre['frame'],paused=pre['paused'])));return
  if pre['paused']:raise ValueError('resume_and_observe_native_frame_before_execute')
  frame=m.u32(int(pre['logic'],0)+0x50);deadline=frame+4500
 finally:m.close()
 args=[sys.executable,str(HERE.parent/a.backend/'lease.py'),'--session',str(a.session),'--natural',str(a.natural),'--mission-file',str(mission_path),'--proof-file',str(proof_path),'--contact-id',cid,'--object-id',str(u['object_id']),'--expires-frame',str(deadline),'--command-id',str(uuid.uuid4()),'--task-id',str(uuid.uuid4()),'--seq',str(int(time.monotonic()*1000)&0x7fffffff),'--post-frames','30','--execute','--output',str(a.output)]
 print(json.dumps(dict(dispatching=True,actor=u['object_id'],target=t['object_id'],initial_distance=d,original_deadline_frame=deadline)),flush=True)
 raise SystemExit(subprocess.run(args).returncode)
if __name__=='__main__':main()
