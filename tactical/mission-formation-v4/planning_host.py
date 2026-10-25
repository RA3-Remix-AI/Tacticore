"""Bounded local planning while the native lease holds both actors stopped.

The only writes are to our shared controller mapping. A route is published once
with a naturally aligned32-bit generation word, after FlushProcessWriteBuffers;
the game callback then acquire-loads and validates/copies it privately. No raw
process writes, unit commands, UI input or model/API calls occur here.
"""
import ctypes as c,hashlib,json,math,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def refresh_guard(w,memory,pre,reader,front,support,contact_id,expected,shared):
 frame=memory.u32(int(pre['logic'],0)+0x50)
 if memory.u32(int(pre['logic'],0)+0x15c):raise ValueError('planning_game_paused')
 reader.collect(frame/15);target=reader.private_targets.get(contact_id)
 if not target or len(reader.private_targets)>=64 or any(target.get(k)!=expected.get(k) for k in ('object_id','address','owner','type_hash')):
  shared.planning_threat_clear=0;raise ValueError('planning_target_visibility_or_identity')
 for actor in (front,support):
  if any(math.dist(actor['xyz'][:2],t['xyz'][:2])<350 for t in reader.private_targets.values()):
   shared.planning_threat_clear=0;raise ValueError('planning_observed_origin_threat')
 shared.planning_threat_frame=target['observed_frame'];shared.planning_threat_clear=1
 return target

def stopped_records(w,memory,pre,front,support,shared):
 admission=w.module('mfm4_held_admission',HERE.parent/'mission_actor_admission_v2.py');rows=[]
 for actor,stop in [(front,list(shared.planning_front)),(support,list(shared.planning_support))]:
  r=admission.actor_admission(memory,int(actor['address'],0));g=r.get('grounded_status',{});state=r.get('state_snapshot',{})
  if not admission.verify_evidence(r)['verified'] or g.get('object_id')!=actor['object_id'] or g.get('owner')!=pre['owner'] or g.get('type_hash')!=actor['type_hash'] or g.get('hp',0)<50 or state.get('state_id')!=16 or state.get('command_source')!=1 or int(state.get('path','0'),0) or math.dist(g['xyz'][:2],stop[:2])>1:raise ValueError('planning_actor_not_same_stopped_lease')
  rows.append(r)
 frame=memory.u32(int(pre['logic'],0)+0x50)
 if any(x['frame']!=frame for x in rows):raise ValueError('planning_actor_pair_not_same_frame')
 return rows,frame

def publish_route(shared,route,front_xyz,support_xyz,target,flush):
 if shared.route_ready or shared.route_generation or not shared.planning_ready or shared.mission_stage!=9 or shared.phase!=1:raise ValueError('planning_submission_already_closed')
 if not 2<=len(route)<=16:raise ValueError('planning_submission_count')
 # Both publication words are aligned Windows32-bit scalars in a page-aligned
 # mapping. Native uses InterlockedCompareExchange acquire loads and a stable
 # generation+byte-copy check. No subsequent route mutation is permitted.
 for field in ('route_generation','route_ready'):
  if (c.addressof(shared)+getattr(type(shared),field).offset)%4:raise ValueError('unaligned_publication_word')
 shared.route_generation=1
 shared.route_count=len(route)
 for i in range(16):shared.route[i][:]=route[i]['xyz'] if i<len(route) else [0.,0.,0.]
 shared.submitted_front[:]=front_xyz;shared.submitted_support[:]=support_xyz
 shared.target[:]=target['xyz'];shared.target_observed_frame=target['observed_frame']
 flush();shared.route_generation=2;flush();shared.route_ready=1

def make_and_publish(w,memory,session,pre,report,shared,reader,front,support,contact_id,expected,history,output):
 started=time.monotonic();deadline=started+2
 if shared.phase!=1 or shared.mission_stage!=9 or not shared.planning_ready or shared.route_ready:raise ValueError('planning_ready_not_current')
 ready_frame=shared.planning_ready_frame;ready=[e for e in report['events'] if e.get('kind')==72]
 if {e.get('role') for e in ready}!={0,1} or len(ready)!=2 or any(e['frame']!=ready_frame for e in ready):raise ValueError('planning_ready_unpublished')
 first,frame=stopped_records(w,memory,pre,front,support,shared)
 target=refresh_guard(w,memory,pre,reader,front,support,contact_id,expected,shared)
 planner=w.module('mfm4_private_route_planner',HERE/'role_route_planner.py');validator=w.module('mfm4_route_provenance',HERE/'route_provenance.py')
 f=dict(front,xyz=first[0]['grounded_status']['xyz'],hp=first[0]['grounded_status']['hp']);s=dict(support,xyz=first[1]['grounded_status']['xyz'],hp=first[1]['grounded_status']['hp'])
 owned=w.b.own_candidates(memory,3,w.b.load_catalog())['candidates'];planning_pre=dict(pre,frame=frame)
 planner_started=time.monotonic();plan=planner.plan_from_history(history,planning_pre,session,f,s,target['xyz'],owned,planning_deadline=deadline);planner_elapsed=time.monotonic()-planner_started
 points=plan['route'];source_frame=memory.u32(int(pre['logic'],0)+0x50);sources=validator.source_records(points,session,source_frame,pre['owner'])
 occupancy_start=memory.u32(int(pre['logic'],0)+0x50);owned=w.b.own_candidates(memory,3,w.b.load_catalog())['candidates'];validator.occupancy(points,owned,{front['object_id'],support['object_id']});occupancy_end=memory.u32(int(pre['logic'],0)+0x50)
 final,frame=stopped_records(w,memory,pre,front,support,shared)
 target=refresh_guard(w,memory,pre,reader,front,support,contact_id,expected,shared)
 if any(math.dist(x['grounded_status']['xyz'][:2],y['grounded_status']['xyz'][:2])>1 for x,y in zip(first,final)):raise ValueError('planning_stopped_positions_changed')
 fxyz,sxyz=[r['grounded_status']['xyz'] for r in final]
 if not planner.route_geometry(fxyz,sxyz,points) or math.dist(points[-1]['xyz'][:2],target['xyz'][:2])>300:raise ValueError('planning_final_geometry_or_target')
 validated=memory.u32(int(pre['logic'],0)+0x50)
 if not frame<=target['observed_frame']<=validated<=frame+4 or not occupancy_start<=occupancy_end<=validated<=occupancy_end+4:raise ValueError('planning_final_snapshot_expired')
 if planner_elapsed>2 or ((int(w.b.k.GetTickCount())-int(shared.planning_ready_tick))&0xffffffff)>=6000:raise ValueError('planning_budget_exceeded')
 if shared.mission_deadline_frame!=report['request']['expires_frame'] or shared.phase!=1 or shared.mission_stage!=9 or shared.planning_ready_frame!=ready_frame:raise ValueError('planning_deadline_or_lease_changed')
 front.update(xyz=fxyz,hp=final[0]['grounded_status']['hp'],mission_admission=final[0]);support.update(xyz=sxyz,hp=final[1]['grounded_status']['hp'],mission_admission=final[1]);pre['frame']=frame
 origin=w.mission_safety(pre,memory,reader,front,support)
 path=Path(output).with_name(Path(output).stem+'-stopped-plan.json');w.b.durable(path,plan)
 commit=dict(protocol='mfm4_stopped_route_commit_v1',generation=2,planning_ready_frame=ready_frame,ready_event_seq=[e['seq'] for e in ready],source_plan=plan,source_plan_path=str(path.resolve()),source_plan_sha256=sha(path),history_directory=str(Path(history).resolve()),source_validation=sources,source_validation_frame=source_frame,occupancy=dict(frame_start=occupancy_start,frame_end=occupancy_end,owned_positions=[dict(object_id=x['object_id'],xyz=x['xyz']) for x in owned]),front_admission=final[0],support_admission=final[1],target=target,origin_safety=origin,planner_sha256=sha(HERE/'role_route_planner.py'),planner_wall_elapsed=planner_elapsed,planning_wall_elapsed=time.monotonic()-started,submitted_frame=validated,route_count=len(points),expires_frame=report['request']['expires_frame'],mutations=False)
 report['planning_commit']=commit;report['request']['route']=points;report['request']['safe_origin']=origin;report['request']['target']=target['xyz'];report['private_target']=dict(target,template=expected['template'])
 # Persist the validated intended plan before the one-way publication boundary.
 w.b.durable(output,report)
 flush=w.b.k.FlushProcessWriteBuffers;flush.argtypes=[];flush.restype=None
 publish_route(shared,points,fxyz,sxyz,target,flush)
