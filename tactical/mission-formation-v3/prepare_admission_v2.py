"""Derive a last-admission Python revision without modifying frozen predecessors."""
from pathlib import Path
import hashlib
HERE=Path(__file__).resolve().parent;P=HERE.parent
def swap(text,old,new):
 if old not in text:raise ValueError('expected_frozen_marker_missing:'+old[:60])
 return text.replace(old,new)
def main():
 old=(HERE/'lease.py').read_bytes()
 if hashlib.sha256(old).hexdigest()!='fd52c92762214821594be8a2ee32a072facfa2a1f5d68d8c750e9e00b8288a2f':raise ValueError('frozen_wrapper_changed')
 wrapper=old.decode('utf-8').replace('\r\n','\n')
 wrapper=wrapper.replace('formation_mission_qualification.py','formation_mission_qualification_v2.py').replace('pre_dispatch_formation_v3_contract.py','pre_dispatch_formation_v3_admission_v2_contract.py')
 extras="HERE.parent/'mobility_guard.py',HERE/'role_route_planner.py',HERE.parent/'mission_actor_admission.py',HERE.parent/'grounded_status_v2.py',HERE.parent/'grounded_status.py',HERE.parent/'ordered-combo/lease.py',HERE.parent/'ordered_qualification.py',HERE.parent/'stop_sequence.py',HERE.parent/'readonly_disposal.py']"
 wrapper=swap(wrapper,"HERE.parent/'mobility_guard.py']",extras)
 wrapper=swap(wrapper,"report['native_launch_intent_persisted']=False","report['native_launch_intent_persisted']=False\n  report.update(wrapper_revision='mfm3_admission_v2',wrapper_filename='lease_admission_v2.py',pre_dispatch_helper='pre_dispatch_formation_v3_admission_v2_contract.py',initial_preflight=json.loads(json.dumps(pre)),initial_safe_origin=json.loads(json.dumps(req['safe_origin'])))")
 wrapper=swap(wrapper,"   NATIVE_LAUNCH_INTENT=True;", "   late=last_admission(memory,pre,front,support,points,reader,a.contact_id,contact)\n   report['last_admission']=late\n   front.update(xyz=late['front']['grounded_status']['xyz'],hp=late['front']['grounded_status']['hp'],mission_admission=late['front'])\n   support.update(xyz=late['support']['grounded_status']['xyz'],hp=late['support']['grounded_status']['hp'],mission_admission=late['support'])\n   pre['frame']=late['frame'];req['safe_origin']=mission_safety(pre,memory,reader,front,support)\n   req['target']=late['target']['xyz'];report['private_target']=dict(late['target'],template=contact['template'])\n   s.target[:]=late['target']['xyz'];s.target_observed_frame=late['target']['observed_frame']\n   NATIVE_LAUNCH_INTENT=True;")
 helper='''
def last_admission(memory,pre,front,support,points,reader,contact_id,expected_target):
 admission=module('formation_last_actor_admission',HERE.parent/'mission_actor_admission.py')
 planner=module('formation_last_role_geometry',HERE/'role_route_planner.py')
 records=[]
 for actor in (front,support):
  r=admission.actor_admission(memory,int(actor['address'],0));g=r.get('grounded_status',{})
  if not admission.verify_evidence(r)['verified'] or not actor_health_eligible(g.get('hp')) or g.get('object_id')!=actor['object_id'] or g.get('type_hash')!=actor['type_hash'] or int(g.get('address','0'),0)!=int(actor['address'],0) or int(g.get('owner','0'),0)!=int(pre['owner'],0) or int(r['state_snapshot']['update'],0)!=int(actor['ai_address'],0):raise ValueError('last_actor_admission_rejected')
  records.append(r)
 f,s=[r['grounded_status'] for r in records];frame=memory.u32(int(pre['logic'],0)+0x50)
 if f['frame']!=s['frame'] or f['frame']!=frame:raise ValueError('last_actor_pair_not_same_frame')
 if not planner.route_geometry(f['xyz'],s['xyz'],points):raise ValueError('last_role_route_geometry_rejected')
 reader.collect(frame/15);target=reader.private_targets.get(contact_id)
 if not target:raise ValueError('last_target_not_currently_visible')
 if any(target.get(k)!=expected_target.get(k) for k in ('object_id','address','owner','type_hash')):raise ValueError('last_target_identity_changed')
 if math.dist(points[-1]['xyz'][:2],target['xyz'][:2])>300:raise ValueError('last_target_outside_route_end')
 if memory.u32(int(pre['logic'],0)+0x15c):raise ValueError('last_game_paused')
 validated=memory.u32(int(pre['logic'],0)+0x50)
 if not frame<=target['observed_frame']<=validated<=frame+4:raise ValueError('last_admission_expired_during_visibility_read')
 return dict(protocol='mfm3_last_admission_v2',frame=frame,validated_frame=validated,front=records[0],support=records[1],target=target,route_geometry_verified=True,mutations=False)

'''
 wrapper=swap(wrapper,'def main():\n',helper+'def main():\n')
 (HERE/'lease_admission_v2.py').write_text(wrapper,encoding='utf-8')
 q=(HERE/'formation_mission_qualification.py').read_text(encoding='utf-8').replace("HERE/'lease.py'","HERE/'lease_admission_v2.py'").replace('pre_dispatch_formation_v3_contract.py','pre_dispatch_formation_v3_admission_v2_contract.py').replace("HERE/'formation_mission_qualification.py'","HERE/'formation_mission_qualification_v2.py'")
 q=swap(q,"HERE.parent/'mobility_guard.py']",extras)
 q=swap(q,'  return primary and ',"  return report.get('wrapper_revision')=='mfm3_admission_v2' and report.get('wrapper_filename')=='lease_admission_v2.py' and primary and ")
 q=swap(q," checks['finished_and_source_pinned']=", " checks['last_admission_before_native_launch']=last_admission_verified(report)\n checks['finished_and_source_pinned']=")
 qhelper='''
def last_admission_verified(report):
 try:
  from mission_actor_admission import verify_evidence
  import importlib.util
  spec=importlib.util.spec_from_file_location('formation_q_last_geometry',HERE/'role_route_planner.py');planner=importlib.util.module_from_spec(spec);spec.loader.exec_module(planner)
  last=report['last_admission'];front=last['front'];support=last['support'];f=front['grounded_status'];s=support['grounded_status'];pre=report['preflight'];rq=report['request']
  if last.get('protocol')!='mfm3_last_admission_v2' or last.get('mutations') is not False or last.get('route_geometry_verified') is not True:return False
  if not verify_evidence(front)['verified'] or not verify_evidence(support)['verified']:return False
  for g,selected in [(f,pre['selected']),(s,pre['support'])]:
   if g['object_id']!=selected['object_id'] or int(g['address'],0)!=int(selected['address'],0) or g['type_hash']!=selected['type_hash'] or int(g['owner'],0)!=int(pre['owner'],0):return False
   if not finite(g['hp']) or g['hp']<50 or g['xyz']!=selected['xyz'] or g['hp']!=selected['hp']:return False
  if f['frame']!=s['frame'] or f['frame']!=last['frame'] or not 0<=report['native']['issued_frame']-last['validated_frame']<=60:return False
  target=last['target']
  if not last['frame']<=target['observed_frame']<=last['validated_frame']<=last['frame']+4:return False
  if any(target.get(k)!=report['private_target'].get(k) for k in ('object_id','address','owner','type_hash')) or target['object_id']!=rq['target_object_id'] or target['xyz']!=rq['target'] or distance(rq['route'][-1]['xyz'],target['xyz'])>300:return False
  return planner.route_geometry(f['xyz'],s['xyz'],rq['route'])
 except (KeyError,TypeError,ValueError,OSError):return False

'''
 q=swap(q,'def qualify(report):\n',qhelper+'def qualify(report):\n');(HERE/'formation_mission_qualification_v2.py').write_text(q,encoding='utf-8')
 pre=(P/'pre_dispatch_formation_v3_contract.py').read_text(encoding='utf-8').replace("directory/'lease.py'","directory/'lease_admission_v2.py'").replace("path/'lease.py'","path/'lease_admission_v2.py'")
 pre=swap(pre,"record.update(status='no_dispatch_rejected'","record.update(wrapper_revision='mfm3_admission_v2',wrapper_filename='lease_admission_v2.py',pre_dispatch_helper='pre_dispatch_formation_v3_admission_v2_contract.py',status='no_dispatch_rejected'")
 pre=swap(pre,"  checks['target_binding']=", "  checks['wrapper_revision']=report.get('wrapper_revision')=='mfm3_admission_v2' and report.get('wrapper_filename')=='lease_admission_v2.py' and report.get('pre_dispatch_helper')=='pre_dispatch_formation_v3_admission_v2_contract.py'\n  checks['target_binding']=")
 (P/'pre_dispatch_formation_v3_admission_v2_contract.py').write_text(pre,encoding='utf-8')
 gate=(P/'mission_formation_v3_gate_no_lease.py').read_text(encoding='utf-8').replace("[('mission-formation-v2',2),('mission-formation-v3',3)]","[('mission-formation-v3',3)]").replace("'formation_mission_qualification.py'","'formation_mission_qualification_v2.py'").replace("'lease.py'","'lease_admission_v2.py'")
 (P/'mission_formation_v3_admission_v2_gate_no_lease.py').write_text(gate,encoding='utf-8')
if __name__=='__main__':main()
