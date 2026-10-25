import copy,json,unittest
from test_common_qualification import fixture,q

def memory_fixture():
 r=fixture();r['events']=[]
 def add(kind,frame,visible,last,point):
  e=dict(seq=len(r['events'])+1,kind=kind,frame=frame,tick=frame*60,role=0,x=float(frame-100),y=0.,z=210.,mission_stage=1,target_visible=visible,target_last_seen_frame=last,last_seen_target=list(point),visible_target_xyz=list(point) if visible else [0.,0.,0.]);r['events'].append(e);return e
 point=[1000.,0.,210.];add(3,100,1,100,point);add(87,110,0,100,point);e=add(50,111,0,100,point);add(3,130,0,100,point);add(88,140,1,140,[1010.,0.,210.]);return r,dict(groups=[dict(role=0,mission_stage=1,seq=e['seq'],goal=point)])

def regroup_fixture():
 r=fixture();r['events']=[];r['native'].update(regroup_count=1,hold_repair_count=0)
 def add(k,role,f,pos,**v):
  e=dict(seq=len(r['events'])+1,kind=k,role=role,frame=f,tick=f*60,x=pos[0],y=pos[1],z=pos[2],mission_stage=1,leader_role=0,follower_role=1,tag=0,arg=0,source=1,state_id=16,sm_flags=0,path=0,holder=0);e.update(v);r['events'].append(e);return e
 f=[300.,0.,210.];s=[50.,0.,210.]
 for role,pos in ((0,f),(1,s)):add(3,role,150,pos)
 add(82,0,150,f)
 for kind in (30,32,33,31):add(kind,0,150,f,tag=4,arg=1,caller=0x787791)
 for frame in (151,152,153):add(3,0,frame,f)
 add(83,0,153,f,leader_hold_xyz=f)
 for role,pos in ((0,f),(1,[120.,0.,210.])):add(3,role,160,pos)
 e=add(85,0,160,f,actual_gap=180.)
 return r,dict(groups=[dict(role=0,mission_stage=1,seq=e['seq']+1,verified=True)])

class MemoryAndConditional(unittest.TestCase):
 def test_same_seen_point_hidden_and_real_reacquisition_component(self):
  r,m=memory_fixture();a=q.memory_audit(r,m);self.assertTrue(a['verified'],a);self.assertTrue(a['reacquisition_observed']);self.assertTrue(a['hidden_navigation_observed'])
 def test_hidden_update_no_actual_sighting_rejected(self):
  for key,value in [('last_seen_target',[2000.,0.,210.]),('target_last_seen_frame',110),('visible_target_xyz',[1000.,0.,210.])]:
   r,m=memory_fixture();r['events'][1][key]=value;self.assertFalse(q.memory_audit(r,m)['verified'],key)
 def test_memory_ttl_never_renewed_by_move(self):
  r,m=memory_fixture();r['events'][2]['frame']=1001;self.assertFalse(q.memory_audit(r,m)['verified'])
 def test_hidden_fire_is_forbidden_even_at_frozen_goal(self):
  r,m=memory_fixture();r['events'][3].update(kind=34,mission_stage=2);self.assertFalse(q.memory_audit(r,m)['checks']['attack_live_only'])
 def test_unobserved_branches_not_demanded_or_claimed(self):
  r=fixture();r['native'].update(regroup_count=0,hold_repair_count=0);a=q.conditional_audit(r,{'groups':[]});self.assertTrue(a['verified']);self.assertFalse(a['regroup']['observed']);self.assertFalse(a['hold_repair']['field_verified'])
 def test_actual_regroup_stop3_and_resume_at_one_eighty(self):
  r,m=regroup_fixture();a=q.conditional_audit(r,m);self.assertTrue(a['verified'],a)
 def test_no_fake_regroup_threshold_or_reanchoring(self):
  r,m=regroup_fixture();r['events'][0]['x']=280.;self.assertFalse(q.conditional_audit(r,m)['verified'])
  r,m=regroup_fixture();next(e for e in r['events'] if e['kind']==83)['leader_hold_xyz']=[999.,0.,210.];self.assertFalse(q.conditional_audit(r,m)['verified'])
 def test_resume_gap_requires_actual_pair_not_header(self):
  r,m=regroup_fixture();next(e for e in r['events'] if e['kind']==3 and e['role']==1 and e['frame']==160)['x']=0.;self.assertFalse(q.conditional_audit(r,m)['verified'])
 def test_duplicate_stop_samples_or_overlong_wait_rejected(self):
  r,m=regroup_fixture()
  for e in r['events']:
   if e['kind']==3 and e['frame'] in (151,152,153):e['frame']=153
  self.assertFalse(q.conditional_audit(r,m)['verified'])
  r,m=regroup_fixture();next(e for e in r['events'] if e['kind']==85)['frame']=451;self.assertFalse(q.conditional_audit(r,m)['verified'])
 def test_partial_branch_with_missing_actor_is_json_finite(self):
  r,m=regroup_fixture();r['events']=[e for e in r['events'] if not(e['kind']==3 and e['role']==1)];a=q.conditional_audit(r,m);self.assertFalse(a['verified']);json.dumps(a,allow_nan=False)
if __name__=='__main__':unittest.main()
