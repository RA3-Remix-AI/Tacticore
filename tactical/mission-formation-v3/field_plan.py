"""Read-only sole-runner pair/route preparation. Never launches a native host."""
import argparse,hashlib,importlib.util,json,math,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def prefix_actual_history(plan,history,front,pre,session):
 # Calibration planning only: a source-backed intermediate point, never linear interpolation.
 old=plan['route'][0];origin=front['xyz'];d=math.dist(origin[:2],old['xyz'][:2])
 if 60<=d<=140:return plan
 if len(plan['route'])>=16:raise ValueError('no_first_leg_margin_without_exceeding_route_count')
 rows=[]
 for source in Path(history).glob('*.json'):
  raw=source.read_bytes();record=json.loads(raw.decode('utf-8-sig'))
  if record.get('session_id')!=session['session_id'] or not 0<record.get('logic_frame_candidate',0)<=pre['frame']:continue
  for item in record.get('own_objects',[]):
   xyz=item['xyz'];a=math.dist(origin[:2],xyz[:2]);z=math.dist(xyz[:2],old['xyz'][:2])
   if 100<=a<=140 and 40<=z<=170 and z<d and abs(origin[2]-xyz[2])<=100 and abs(xyz[2]-old['xyz'][2])<=100:rows.append((abs(a-120),dict(xyz=xyz,own_source_path=str(source.resolve()),own_source_sha256=hashlib.sha256(raw).hexdigest(),own_source_object_id=item['object_id'])))
 if not rows:raise ValueError('no_actual_owned_first_leg_with_margin')
 out=dict(plan);out['route']=[min(rows,key=lambda x:x[0])[1]]+plan['route'];return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--routes',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--front-id',type=int);p.add_argument('--support-id',type=int);p.add_argument('--contact-id');p.add_argument('--preferred-front-id',type=int);p.add_argument('--preferred-support-id',type=int);p.add_argument('--minimum-selection-gap',type=float,default=25);a=p.parse_args();b=load('formation_field_backend',HERE/'lease.py');pre,s,raw,*rest=b.b.readiness(a.session);m=rest[-1]
 try:
  sys.path[:0]=[str(BRIDGE/'visibility'),str(HERE.parent)]
  from capability import bind_session
  from projection import VisibilityProjection
  from collector import VisibilityCollector
  from mobility_guard import mobility_status
  from mission_actor_admission import actor_admission,verify_evidence as verify_admission
  proof,safety=bind_session(m,s,3);reader=VisibilityCollector(m,s,3,VisibilityProjection(s['session_id'],3,s['mod_sha256'],proof,safety));reader.collect(m.u32(int(pre['logic'],0)+0x50)/15)
  front=[u for u in pre['units'] if u['type_hash']=='0x19ab11af' and u['eligible'] and b.actor_health_eligible(u['hp']) and (a.front_id is None or u['object_id']==a.front_id) and mobility_status(m,int(u['address'],0))['independently_movable']]
  support=[u for u in pre['units'] if u['type_hash']=='0x2c358c61' and u['eligible'] and b.actor_health_eligible(u['hp']) and (a.support_id is None or u['object_id']==a.support_id) and mobility_status(m,int(u['address'],0))['independently_movable']]
  contacts=[(cid,t) for cid,t in reader.private_targets.items() if (a.contact_id is None or cid==a.contact_id) and safety['templates'][t['type_hash']]['role'] in ('infantry','armor','structure','economy')]
  def target_priority(ct):
   target=ct[1];near=sum(u['type_hash']=='0x19ab11af' and u['hp']>0 and math.dist(u['xyz'][:2],target['xyz'][:2])<250 for u in pre['units'])
   return (near,0 if target['type_hash']=='0x2c358c61' else 1,-target['hp'])
  contacts.sort(key=target_priority)
  def admitted(units):
   result=[]
   for u in units:
    admission=actor_admission(m,int(u['address'],0))
    if verify_admission(admission)['verified']:
     g=admission['grounded_status'];result.append(dict(u,xyz=g['xyz'],hp=g['hp'],mission_admission=admission))
   return result
  front=admitted(front);support=admitted(support);pre['frame']=m.u32(int(pre['logic'],0)+0x50)
  candidates=[];errors=[];diagnostics=[];planner=load('formation_field_route',HERE/'role_route_planner.py');own=b.b.own_candidates(m,3,b.b.load_catalog())['candidates'];planning_deadline=time.monotonic()+2
  pairs=[(f,sup) for f in front for sup in support if b.initial_pair_eligible(math.dist(f['xyz'][:2],sup['xyz'][:2])) and math.dist(f['xyz'][:2],sup['xyz'][:2])>=a.minimum_selection_gap]
  if contacts:pairs.sort(key=lambda pair:((a.preferred_front_id is not None and pair[0]['object_id']!=a.preferred_front_id)+(a.preferred_support_id is not None and pair[1]['object_id']!=a.preferred_support_id),)+planner.pair_priority(*pair,contacts[0][1]['xyz']))
  for f,sup in pairs:
   if candidates or time.monotonic()>=planning_deadline:break
   try:b.mission_safety(pre,m,reader,f,sup)
   except ValueError as error:errors.append(str(error));continue
   for cid,t in contacts:
    if candidates or time.monotonic()>=planning_deadline:break
    try:
     plan=planner.plan_from_history(a.routes,pre,s,f,sup,t['xyz'],own,planning_deadline=min(planning_deadline,time.monotonic()+1));b.route_points(plan,pre,s,m,f,sup);candidates.append((sum(math.dist(x['xyz'][:2],z['xyz'][:2]) for x,z in zip([f]+plan['route'][:-1],plan['route'])),cid,t,f,sup,plan))
    except ValueError as error:
     errors.append(str(error))
     if getattr(error,'diagnostics',None):diagnostics.append(dict(front_id=f['object_id'],support_id=sup['object_id'],contact_id=cid,**error.diagnostics))
  if not candidates:
   report=dict(status='no_dispatch_route_or_pair_not_ready',session_id=s['session_id'],frame=pre['frame'],paused=pre['paused'],own_fronts=[dict(object_id=x['object_id'],xyz=x['xyz']) for x in front],own_supports=[dict(object_id=x['object_id'],xyz=x['xyz']) for x in support],visible_static_contacts=[dict(contact_id=cid,object_id=t['object_id'],xyz=t['xyz']) for cid,t in contacts],errors=sorted(set(errors)),planning_diagnostics=diagnostics,sdk_calls=0);b.b.durable(a.output,report);print(json.dumps(report));return
  length,cid,t,f,sup,plan=min(candidates,key=lambda x:x[0]);b.b.durable(a.output,plan);proof_path=a.output.with_name(a.output.stem+'-proof.json');b.b.durable(proof_path,proof);choice=dict(status='read_only_route_ready',session_id=s['session_id'],frame=pre['frame'],paused=pre['paused'],front_id=f['object_id'],support_id=sup['object_id'],contact_id=cid,target_object_id=t['object_id'],target_type_hash=t['type_hash'],target_currently_visible_hp=t['hp'],initial_distance=math.dist(f['xyz'][:2],t['xyz'][:2]),waypoints=len(plan['route']),route_length=length,mission_file=str(a.output.resolve()),proof_file=str(proof_path.resolve()),sdk_calls=0);b.b.durable(a.output.with_name(a.output.stem+'-selection.json'),choice);print(json.dumps(choice))
 finally:m.close()
if __name__=='__main__':main()
