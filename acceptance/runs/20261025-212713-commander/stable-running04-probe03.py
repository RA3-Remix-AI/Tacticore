"""Private calibration hint only; current p3 FOV, zero SDK or game mutations."""
import importlib.util,json,math,sys
from pathlib import Path
BRIDGE=Path(__file__).resolve().parents[3]
HERE=BRIDGE/'tactical/mission-formation-v8'
spec=importlib.util.spec_from_file_location('margin8_backend',HERE/'lease.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
session=BRIDGE/'acceptance/active-session.json'
pre,s,raw,*rest=b.b.readiness(session);m=rest[-1]
try:
 sys.path[:0]=[str(BRIDGE/'visibility'),str(BRIDGE/'tactical')]
 from capability import bind_session
 from projection import VisibilityProjection
 from collector import VisibilityCollector
 from mission_actor_admission_v2 import actor_admission,verify_evidence
 proof,safety=bind_session(m,s,3)
 reader=VisibilityCollector(m,s,3,VisibilityProjection(s['session_id'],3,s['mod_sha256'],proof,safety))
 reader.collect(m.u32(int(pre['logic'],0)+0x50)/15)
 units=[];rejections=[]
 for u in pre['units']:
  if u['type_hash'] not in ('0x19ab11af','0x2c358c61') or not u.get('eligible'):continue
  a=actor_admission(m,int(u['address'],0));g=a.get('grounded_status',{})
  if verify_evidence(a)['verified'] and b.actor_health_eligible(g.get('hp')) and all(g.get(k)==u.get(k) for k in ('object_id','address','type_hash')) and g.get('owner')==pre['owner'] and a['state_snapshot']['update']==u['ai_address']:
   units.append(dict(u,xyz=g['xyz'],hp=g['hp'],mission_admission=a))
  else:rejections.append(dict(object_id=u['object_id'],type_hash=u['type_hash'],status=a.get('status'),reason=a.get('reason')))
 targets=list(reader.private_targets.items());rows=[]
 for f in units:
  if f['type_hash']!='0x19ab11af':continue
  for r in units:
   if r['type_hash']!='0x2c358c61':continue
   gap=math.dist(f['xyz'][:2],r['xyz'][:2])
   if not b.initial_pair_eligible(gap):continue
   for cid,t in targets:
    if safety['templates'][t['type_hash']]['role'] not in ('infantry','armor','structure','economy'):continue
    dot=sum((t['xyz'][i]-f['xyz'][i])*(f['xyz'][i]-r['xyz'][i]) for i in (0,1))
    if dot<0:continue
    margin=min(math.dist(a['xyz'][:2],e['xyz'][:2]) for a in (f,r) for _,e in targets)
    try:b.mission_safety(pre,m,reader,f,r);reason=None
    except ValueError as error:reason=str(error)
    rows.append(dict(front_id=f['object_id'],support_id=r['object_id'],front_hp=f['hp'],support_hp=r['hp'],front_state=f['mission_admission']['state_snapshot']['state_id'],support_state=r['mission_admission']['state_snapshot']['state_id'],gap=gap,minimum_current_visible_enemy_distance=margin,target_contact_id=cid,target_object_id=t['object_id'],target_type_hash=t['type_hash'],target_hp=t['hp'],target_role=safety['templates'][t['type_hash']]['role'],target_distance=math.dist(f['xyz'][:2],t['xyz'][:2]),original_safety_rejection=reason,extra_margin400_hint=margin>=400,extra_margin450_hint=margin>=450))
 rows.sort(key=lambda x:(x['original_safety_rejection'] is not None,not x['extra_margin450_hint'],not 600<=x['target_distance']<=1300,x['target_distance']))
 report=dict(pid=s['pid'],session_id=s['session_id'],frame=m.u32(int(pre['logic'],0)+0x50),paused=m.u32(int(pre['logic'],0)+0x15c),admitted_fronts=sum(u['type_hash']=='0x19ab11af' for u in units),admitted_supports=sum(u['type_hash']=='0x2c358c61' for u in units),visible_contacts=len(targets),candidates=rows,admitted_actor_states=[dict(id=u['object_id'],type=u['type_hash'],hp=u['hp'],xyz=u['xyz'],state=u['mission_admission']['state_snapshot']['state_id']) for u in units],rejections=rejections,hard_guard_unchanged=350,sdk_calls=0,mutations=False,paused_hint_only=False)
 out=Path(__file__).with_name('stable-running04-probe03.json');b.b.durable(out,report)
 print(json.dumps(dict(report=str(out),frame=report['frame'],paused=report['paused'],fronts=report['admitted_fronts'],supports=report['admitted_supports'],contacts=len(targets),candidates=rows[:8])))
finally:m.close()
