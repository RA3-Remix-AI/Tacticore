"""Read-only sole-runner pair/route preparation. Never launches a native host."""
import argparse,hashlib,importlib.util,json,math,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--routes',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--front-id',type=int);p.add_argument('--support-id',type=int);p.add_argument('--contact-id');p.add_argument('--preferred-front-id',type=int);p.add_argument('--preferred-support-id',type=int);p.add_argument('--minimum-selection-gap',type=float,default=25);a=p.parse_args();b=load('formation_field_backend',HERE/'lease.py');pre,s,raw,*rest=b.b.readiness(a.session);m=rest[-1]
 try:
  sys.path[:0]=[str(BRIDGE/'visibility'),str(HERE.parent)]
  from capability import bind_session
  from projection import VisibilityProjection
  from collector import VisibilityCollector
  from mobility_guard import mobility_status
  from mission_actor_admission_v2 import actor_admission,verify_evidence as verify_admission
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
  coverage=load('mfm4_goal_coverage',HERE/'coverage.py');errors=[];pairs=[(f,sup) for f in front for sup in support if b.initial_pair_eligible(math.dist(f['xyz'][:2],sup['xyz'][:2])) and math.dist(f['xyz'][:2],sup['xyz'][:2])>=a.minimum_selection_gap]
  if contacts:pairs.sort(key=lambda pair:((a.preferred_front_id is not None and pair[0]['object_id']!=a.preferred_front_id)+(a.preferred_support_id is not None and pair[1]['object_id']!=a.preferred_support_id),)+coverage.roles.pair_priority(*pair,contacts[0][1]['xyz']))
  match=None;until=time.monotonic()+2
  for cid,t in contacts:
   if time.monotonic()>=until:break
   try:goal=coverage.covered_goal(a.routes,s,pre['frame'],pre['owner'],t['xyz'],until)
   except ValueError as error:errors.append(str(error));continue
   if not goal:errors.append('no_positive_ground_history_near_explicit_visible_contact');continue
   for f,sup in pairs:
    try:
     if len(reader.private_targets)>=64:raise ValueError('current_visibility_capacity_unknown')
     b.mission_safety(pre,m,reader,f,sup);match=(cid,t,f,sup,goal);break
    except ValueError as error:errors.append(str(error))
   if match:break
  if not match:
   report=dict(status='no_dispatch_pair_or_goal_coverage_not_ready',session_id=s['session_id'],frame=pre['frame'],paused=pre['paused'],own_fronts=[dict(object_id=x['object_id'],xyz=x['xyz']) for x in front],own_supports=[dict(object_id=x['object_id'],xyz=x['xyz']) for x in support],visible_contacts=len(contacts),errors=sorted(set(errors)),route_planning_performed=False,sdk_calls=0);b.b.durable(a.output,report);print(json.dumps(report));return
  cid,t,f,sup,goal=match;plan=dict(schema_version=1,session_id=s['session_id'],pid=s['pid'],player_id=3,front_id=f['object_id'],support_id=sup['object_id'],formation_history_dir=str(a.routes.resolve()),goal_coverage=goal,route_planning_performed=False)
  b.b.durable(a.output,plan);proof_path=a.output.with_name(a.output.stem+'-proof.json');b.b.durable(proof_path,proof);choice=dict(status='read_only_pair_goal_coverage_ready',session_id=s['session_id'],frame=pre['frame'],paused=pre['paused'],front_id=f['object_id'],support_id=sup['object_id'],contact_id=cid,target_object_id=t['object_id'],target_type_hash=t['type_hash'],target_currently_visible_hp=t['hp'],initial_distance=math.dist(f['xyz'][:2],t['xyz'][:2]),goal_coverage=goal,route_planning_performed=False,mission_file=str(a.output.resolve()),proof_file=str(proof_path.resolve()),sdk_calls=0);b.b.durable(a.output.with_name(a.output.stem+'-selection.json'),choice);print(json.dumps(choice))
 finally:m.close()
if __name__=='__main__':main()
