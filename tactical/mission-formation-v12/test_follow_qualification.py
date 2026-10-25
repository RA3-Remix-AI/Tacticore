"""Raw temporal follow evidence only; not a complete mission or source grant."""
from test_stance_qualification import decorate
import copy,json,unittest
from test_common_qualification import fixture,q
def follow_fixture():
 r=fixture();r['preflight']['selected']['xyz']=[100.,0.,210.];r['preflight']['support']['xyz']=[0.,0.,210.]
 for e in r['events']:
  role=e['role'];pos=r['preflight']['support' if role else 'selected']['xyz'];e.update(x=pos[0],y=0.);e['breadcrumb']['xyz']=list(pos);r['native']['crumbs'][role][0]['xyz']=list(pos)
 def add(kind,role,frame,pos,**values):
  e=copy.deepcopy(r['events'][role]);e.update(seq=len(r['events'])+1,kind=kind,role=role,unit_id=q.actor(r,role)['object_id'],frame=frame,tick=frame*60,x=pos[0],y=pos[1],z=pos[2],mission_stage=1,source=1,state_id=1,sm_flags=0,path=1,holder=0,tag=0);e.update(values);decorate(e);r['events'].append(e);return e
 add(3,0,115,[140.,0.,210.]);add(3,0,120,[180.,0.,210.])
 e=add(80,0,120,[180.,0.,210.],arg=1);c=copy.deepcopy(r['events'][0]['breadcrumb']);c.update(index=1,frame=120,published_seq=e['seq'],xyz=[180.,0.,210.],path_distance=80.);e['breadcrumb']=c;r['native']['crumbs'][0].append(copy.deepcopy(c))
 add(3,0,125,[200.,0.,210.]);c=copy.deepcopy(r['events'][0]['breadcrumb']);add(81,1,125,[0.,0.,210.],leader_role=0,follower_role=1,follow_crumb_role=0,follow_crumb_index=0,follow_active=1,breadcrumb=copy.deepcopy(c))
 for kind in (50,10,11,51):add(kind,1,125,[0.,0.,210.],tag=6,arg=1,command_xyz=c['xyz'],argument_path=0,argument_limit=3.4028234663852886e38)
 for frame,pos in [(126,[90.,0.,210.]),(128,[100.,0.,210.]),(129,[100.,0.,210.])]:add(3,1,frame,pos)
 add(84,1,129,[100.,0.,210.],breadcrumb=copy.deepcopy(c))
 for kind in (30,32,33,31):add(kind,1,129,[100.,0.,210.],arg=1,caller=0x787791,state_id=94,path=0,tag=4)
 for frame in (130,132,133):add(3,1,frame,[100.,0.,210.],state_id=94,path=0)
 add(94,1,133,[100.,0.,210.],breadcrumb=copy.deepcopy(c),state_id=94,path=0)
 r['native'].update(move_calls=0);r['native']['support']['move_calls']=1
 return r
def audit(r):
 crumbs=q.breadcrumb_audit(r);moves=q.normal_move_audit(r);return q.follow_audit(r,crumbs,moves)
class FollowEvidence(unittest.TestCase):
 def test_one_actual_reference_arrival_and_stop_component(self):
  r=follow_fixture();a=audit(r);self.assertTrue(q.breadcrumb_motion_audit(r,q.breadcrumb_audit(r))['verified']);self.assertTrue(a['verified'],a);self.assertTrue(a['approach_follow_observed']);self.assertFalse(a['retreat_follow_observed']);json.dumps(a,allow_nan=False)
 def test_flagged_published_without_earlier_source_is_not_evidence(self):
  r=follow_fixture();e=next(e for e in r['events'] if e['kind']==81);e['breadcrumb']['published_seq']=e['seq']+1;self.assertFalse(audit(r)['checks']['prior_actual_crumb'])
 def test_reference_cannot_change_observed_xyz(self):
  r=follow_fixture();next(e for e in r['events'] if e['kind']==81)['breadcrumb']['xyz']=[999.,0.,210.];self.assertFalse(audit(r)['checks']['prior_actual_crumb'])
 def test_header_path_counter_cannot_create_one_hundred_ahead(self):
  r=follow_fixture();r['native']['front_travel']=10000.;request=next(e for e in r['events'] if e['kind']==81);request['breadcrumb']=copy.deepcopy(r['native']['crumbs'][0][1]);request['follow_crumb_index']=1;next(e for e in r['events'] if e['kind']==3 and e['frame']==125)['x']=190.;self.assertFalse(audit(r)['checks']['actual_leader_one_hundred_ahead'])
 def test_three_copies_of_one_logical_frame_not_arrival(self):
  r=follow_fixture()
  for e in r['events']:
   if e['kind']==3 and e['role']==1 and e['frame'] in (126,128,129):e['frame']=129
  self.assertFalse(audit(r)['checks']['three_distinct_arrival'])
 def test_claimed_94_without_actual_source1_idle_stop_three_fails(self):
  for key,value in [('state_id',1),('path',1),('source',0),('sm_flags',1)]:
   r=follow_fixture()
   for e in r['events']:
    if e['kind']==3 and e['role']==1 and e['frame']>=130:e[key]=value
   self.assertFalse(audit(r)['checks']['stop_before_next'],key)
 def test_follow_move_must_be_normal_source1_complete_input_chain(self):
  for key,value in [('argument_path',123),('argument_limit',0.),('arg',0)]:
   r=follow_fixture();next(e for e in r['events'] if e['kind']==10)[key]=value;self.assertFalse(audit(r)['verified'],key)
 def test_move_to_another_point_not_old_reference(self):
  r=follow_fixture()
  for e in r['events']:
   if e['kind'] in (50,10,11,51):e['command_xyz']=[300.,0.,210.]
  self.assertFalse(audit(r)['checks']['normal_follow_input'])
 def test_second_reference_replay_not_unique_progress(self):
  r=follow_fixture();e=copy.deepcopy(next(e for e in r['events'] if e['kind']==81));e.update(seq=len(r['events'])+1,frame=140,tick=8400);r['events'].append(e);self.assertFalse(audit(r)['checks']['strict_reference_order'])
 def test_raw_ground_and_eighty_spacing_required_even_if_flag_true(self):
  r=follow_fixture();e=next(e for e in r['events'] if e['kind']==80 and e['arg']==1);e['breadcrumb']['status_words'][0]=1<<7;self.assertFalse(audit(r)['verified'])
  r=follow_fixture();e=next(e for e in r['events'] if e['kind']==80 and e['arg']==1);e['breadcrumb']['xyz'][0]=170.;e['x']=170.;r['native']['crumbs'][0][1]['xyz'][0]=170.;self.assertFalse(q.breadcrumb_motion_audit(r,q.breadcrumb_audit(r))['verified'])
 def test_retreat_phase_cannot_reuse_old_approach_point(self):
  r=follow_fixture();e=next(e for e in r['events'] if e['kind']==81);e.update(mission_stage=3,leader_role=1,follower_role=0,role=0,follow_crumb_role=1);self.assertFalse(audit(r)['checks']['prior_actual_crumb'])
 def test_incomplete_stage_is_never_complete_mission(self):
  r=follow_fixture();self.assertTrue(audit(r)['verified']);self.assertEqual(q.qualify(r)['status'],'not_passed')
if __name__=='__main__':unittest.main()
