"""Contingent wait-anchor protocol only; no SDK, field source or new position input."""
import copy,importlib.util,json,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mfm6_replan_tests',H/'wait_anchor_replan.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def fixture():
 r=dict(preflight=dict(owner='0x3000',selected=dict(address='0x2000',object_id=42,ai_address='0x4000'),support=dict(address='0x5000',object_id=43,ai_address='0x6000')),native=dict(safe_front=[140.,0.,210.],safe_support=[0.,0.,210.],mission_deadline_frame=4600),events=[])
 def add(kind,role,frame,pos,**v):
  e=dict(seq=len(r['events'])+1,kind=kind,role=role,frame=frame,tick=frame*60,unit_id=42+role,owner=0x3000,x=pos[0],y=pos[1],z=pos[2],own_hp=100.,mission_stage=1,mission_deadline_frame=4600,leader_role=0,motion_state=3,leader_hold_xyz=[300.,0.,210.],tag=0,arg=0,source=1,state_id=16,path=0,holder=0,sm_flags=0);e.update(v);r['events'].append(e);return e
 add(71,0,100,[140.,0.,210.]);add(71,1,100,[0.,0.,210.]);add(82,0,150,[300.,0.,210.])
 for kind in (30,32,33,31):add(kind,0,150,[300.,0.,210.],tag=4,arg=1,caller=0x787791)
 for frame in (151,152,153):add(3,0,frame,[300.,0.,210.])
 add(83,0,153,[300.,0.,210.]);add(96,0,200,[320.,0.,210.],arg=1)
 for kind in (30,32,33,31):add(kind,0,200,[320.,0.,210.],tag=4,arg=1,caller=0x787791,motion_state=11)
 for frame in (201,203,205):add(3,0,frame,[320.,0.,210.],motion_state=11)
 c=dict(index=0,role=0,frame=205,published_seq=0,thing=0x2000,object_id=42,type_hash=0x19ab11af,owner=0x3000,update=0x4000,holder=0,status_words=[0]*7,height_flags=4,height=0.,hp=100.,xyz=[320.,0.,210.],path_distance=0.,mission_stage=1,surface_verified=1)
 add(97,0,205,[320.,0.,210.],arg=1,motion_state=11,leader_hold_xyz=[320.,0.,210.],breadcrumb=c)
 return r
class Replan(unittest.TestCase):
 def test_old_anchor_explicitly_abandoned_real_stop_new_surface(self):
  a=m.audit(fixture());self.assertTrue(a['verified'],a);self.assertTrue(a['observed']);self.assertFalse(a['old_goal_arrival_claim']);self.assertFalse(a['attempts'][0]['old_anchor_arrival_claim'])
 def test_new_point_is_snapshot_not_mutated_published_trail(self):
  for key,value in [('published_seq',13),('index',1),('frame',204),('holder',1),('height_flags',0),('height',1.),('hp',0.),('owner',9),('object_id',44),('type_hash',0x33026fa1),('xyz',[999.,0.,210.])]:
   r=fixture();r['events'][-1]['breadcrumb'][key]=value;self.assertFalse(m.audit(r)['verified'],key)
 def test_cannot_reanchor_endpoint_or_combat_hold(self):
  for key,value in [('motion_state',7),('mission_stage',2),('role',1),('leader_role',1)]:
   r=fixture();next(e for e in r['events'] if e['kind']==96)[key]=value;self.assertFalse(m.audit(r)['verified'],key)
  r=fixture();r['events']=[e for e in r['events'] if e['kind']!=82];self.assertFalse(m.audit(r)['verified'])
 def test_no_drift_no_replan_and_never_silently_change_old_anchor(self):
  for key,value in [('x',310.),('leader_hold_xyz',[320.,0.,210.])]:
   r=fixture();next(e for e in r['events'] if e['kind']==96)[key]=value;self.assertFalse(m.audit(r)['verified'])
 def test_stop_must_be_normal_source1_real_three_distinct_and_stable(self):
  for key,value in [('path',1),('state_id',1),('source',0),('sm_flags',1),('x',350.)]:
   r=fixture();next(e for e in r['events'] if e['kind']==3 and e['frame']==203)[key]=value;self.assertFalse(m.audit(r)['verified'],key)
  r=fixture()
  for e in r['events']:
   if e['kind']==3 and e['frame']>=200:e['frame']=205
  self.assertFalse(m.audit(r)['verified'])
 def test_no_extra_leader_move_attack_during_stop_replan(self):
  for kind in (10,12,34,50):
   r=fixture();e=copy.deepcopy(r['events'][-2]);e.update(kind=kind,seq=r['events'][-1]['seq']-.5);r['events'].insert(-1,e);self.assertFalse(m.audit(r)['verified'],kind)
 def test_unmatched_replan_or_extra_gate_rejected(self):
  r=fixture();r['events'].pop();self.assertFalse(m.audit(r)['verified'])
  r=fixture();r['events']=[e for e in r['events'] if e['kind']!=96];self.assertFalse(m.audit(r)['verified'])
 def test_second_budget_uses_new_wait_anchor_not_abandoned_old_one(self):
  r=fixture();template=copy.deepcopy(r['events'][-1]);start=copy.deepcopy(next(e for e in r['events'] if e['kind']==96));start.update(seq=len(r['events'])+1,frame=210,tick=12600,arg=2,x=340.,leader_hold_xyz=[320.,0.,210.]);r['events'].append(start)
  for kind in (30,32,33,31):
   e=copy.deepcopy(start);e.update(seq=len(r['events'])+1,kind=kind,arg=1,tag=4,caller=0x787791,motion_state=11);r['events'].append(e)
  for frame in (211,213,215):
   e=copy.deepcopy(start);e.update(seq=len(r['events'])+1,kind=3,frame=frame,tick=frame*60,motion_state=11);r['events'].append(e)
  template.update(seq=len(r['events'])+1,frame=215,tick=12900,arg=2,x=340.,leader_hold_xyz=[340.,0.,210.]);template['breadcrumb'].update(frame=215,xyz=[340.,0.,210.]);r['events'].append(template)
  self.assertTrue(m.audit(r)['verified']);start['leader_hold_xyz']=[300.,0.,210.];self.assertFalse(m.audit(r)['verified'])
 def test_budget_deadline_and_frozen_original_origins(self):
  for key,value in [('arg',3),('mission_deadline_frame',4601),('frame',261),('leader_hold_xyz',[999.,0.,210.])]:
   r=fixture();r['events'][-1][key]=value;self.assertFalse(m.audit(r)['verified'],key)
  r=fixture();r['native']['safe_front']=[150.,0.,210.];self.assertFalse(m.audit(r)['verified'])
 def test_unobserved_not_forced_or_field_claimed(self):
  r=fixture();r['events']=r['events'][:2];a=m.audit(r);self.assertTrue(a['verified']);self.assertFalse(a['observed']);self.assertFalse(a['field_verified']);json.dumps(a,allow_nan=False)
if __name__=='__main__':unittest.main()
