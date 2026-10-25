"""Calibration-only static-ground selection; frozen MF10 still performs all admission.
No writes, native host, model calls or new game capability.
"""
import argparse,hashlib,importlib.util,json,math,sys,time
from pathlib import Path
BRIDGE=Path(__file__).resolve().parents[2];HERE=BRIDGE/'tactical/mission-formation-v10'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def ahead_pairs(pairs,target,preferred_front=None,preferred_support=None):
 def priority(pair):
  f,s=pair;v=[target[i]-f['xyz'][i] for i in (0,1)];w=[f['xyz'][i]-s['xyz'][i] for i in (0,1)];dot=sum(a*b for a,b in zip(v,w))
  preferred=(preferred_front is not None and f['object_id']!=preferred_front)+(preferred_support is not None and s['object_id']!=preferred_support)
  return dot,(preferred,math.hypot(*v))
 return sorted([pair for pair in pairs if priority(pair)[0]>=0],key=lambda pair:priority(pair)[1])

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--front-id',type=int);p.add_argument('--support-id',type=int);p.add_argument('--contact-id');p.add_argument('--preferred-front-id',type=int);p.add_argument('--preferred-support-id',type=int);p.add_argument('--minimum-selection-gap',type=float,default=60);a=p.parse_args();b=load('formation_field_backend',HERE/'lease.py');pre,s,raw,*rest=b.b.readiness(a.session);m=rest[-1]
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
  contacts=[(cid,t) for cid,t in reader.private_targets.items() if (a.contact_id is None or cid==a.contact_id) and safety['templates'][t['type_hash']]['role'] in ('structure','economy')]
  def target_priority(ct):
   target=ct[1];near=sum(u['type_hash']=='0x19ab11af' and u['hp']>0 and math.dist(u['xyz'][:2],target['xyz'][:2])<250 for u in pre['units'])
   distance=min((math.dist(actor['xyz'][:2],target['xyz'][:2]) for actor in front),default=float('inf'))
   return (not 600<=distance<=1300,near,0 if safety['templates'][target['type_hash']]['role'] in ('structure','economy') else 1,0 if target['type_hash']=='0x2c358c61' else 1,-target['hp'])
  contacts.sort(key=target_priority)
  def admitted(units):
   result=[]
   for u in units:
    admission=actor_admission(m,int(u['address'],0))
    g=admission.get('grounded_status',{})
    if verify_admission(admission)['verified'] and b.actor_health_eligible(g.get('hp')) and all(g.get(k)==u.get(k) for k in ('object_id','address','type_hash')) and g.get('owner')==pre['owner'] and admission['state_snapshot']['update']==u['ai_address']:
     result.append(dict(u,xyz=g['xyz'],hp=g['hp'],mission_admission=admission))
   return result
  front=admitted(front);support=admitted(support);pre['frame']=m.u32(int(pre['logic'],0)+0x50)
  errors=[];pairs=[(f,sup) for f in front for sup in support if b.initial_pair_eligible(math.dist(f['xyz'][:2],sup['xyz'][:2])) and max(60,a.minimum_selection_gap)<=math.dist(f['xyz'][:2],sup['xyz'][:2])<=120]
  match=None;until=time.monotonic()+2
  for cid,t in contacts:
   if time.monotonic()>=until:break
   for f,sup in ahead_pairs(pairs,t['xyz'],a.preferred_front_id,a.preferred_support_id):
    if time.monotonic()>=until:break
    try:
     if len(reader.private_targets)>=64:raise ValueError('current_visibility_capacity_unknown')
     distance=math.dist(f['xyz'][:2],t['xyz'][:2])
     if not 600<=distance<=2600:raise ValueError('calibration_target_distance_window')
     b.mission_safety(pre,m,reader,f,sup)
     clearance=min(math.dist(actor['xyz'][:2],enemy['xyz'][:2]) for actor in (f,sup) for enemy in reader.private_targets.values())
     if clearance<450:raise ValueError('calibration_origin_margin_not_ready')
     match=(cid,t,f,sup);break
    except ValueError as error:errors.append(str(error))
   if match:break
  if not match:
   report=dict(status='no_dispatch_current_pair_or_contact_not_ready',session_id=s['session_id'],frame=pre['frame'],paused=pre['paused'],own_fronts=[dict(object_id=x['object_id'],xyz=x['xyz']) for x in front],own_supports=[dict(object_id=x['object_id'],xyz=x['xyz']) for x in support],visible_contacts=len(contacts),errors=sorted(set(errors)),route_planning_performed=False,sdk_calls=0);b.b.durable(a.output,report);print(json.dumps(report));return
  cid,t,f,sup=match;expires=pre['frame']+4500
  plan=dict(schema_version=1,session_id=s['session_id'],pid=s['pid'],player_id=3,front_id=f['object_id'],support_id=sup['object_id'],navigation_mode='native_leader_actual_breadcrumbs',target_contact_id=cid,expires_frame=expires)
  b.b.durable(a.output,plan);proof_path=a.output.with_name(a.output.stem+'-proof.json');b.b.durable(proof_path,proof);choice=dict(status='read_only_pair_contact_ready',session_id=s['session_id'],frame=pre['frame'],paused=pre['paused'],front_id=f['object_id'],support_id=sup['object_id'],contact_id=cid,target_object_id=t['object_id'],target_type_hash=t['type_hash'],target_currently_visible_hp=t['hp'],initial_distance=math.dist(f['xyz'][:2],t['xyz'][:2]),expires_frame=expires,selection_origin_margin=clearance,selection_pair_gap=math.dist(f['xyz'][:2],sup['xyz'][:2]),selection_policy='calibration_static_ground_gap60_120_margin450_prefer600_1300_allow2600',route_planning_performed=False,mission_file=str(a.output.resolve()),proof_file=str(proof_path.resolve()),sdk_calls=0);b.b.durable(a.output.with_name(a.output.stem+'-selection.json'),choice);print(json.dumps(choice))
 finally:m.close()
if __name__=='__main__':main()
