"""Pure two-phase evidence checks. Never starts or attaches to the game."""
import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
H=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
q=load('mfm4_q_tests',H/'formation_mission_qualification.py');old=load('mfm3_boundary_fixture',H.parent/'mission-formation-v3/test_admission_wrapper_v3.py')
def fixture():
 r=old.Admission().fixture();last=r['last_admission'];f,s=last['front']['grounded_status']['xyz'],last['support']['grounded_status']['xyz'];at=last['frame'];route=r['request']['route'];ev=[]
 def emit(kind,role,frame,**kwargs):
  pos=s if role else f;e=dict(seq=len(ev)+1,kind=kind,role=role,frame=frame,tick=frame*100,tag=0,arg=0,x=pos[0],y=pos[1],z=pos[2],state_id=16,source=1,path=0,holder=0,sm_flags=65536,planning_front=f,planning_support=s,planning_ready_frame=at,route_commit_frame=at+2,mission_stage=8,target_visible=1,mission_deadline_frame=4500);e.update(kwargs);ev.append(e);return e
 for role in (0,1):emit(1,role,at-5,tag=1);emit(33,role,at-5,arg=1,caller=0x787791)
 for frame in (at-3,at-2,at):
  for role in (0,1):emit(3,role,frame)
 for role in (0,1):emit(72,role,at,mission_stage=9,planning_ready=1,route_ready=0,route_generation=0)
 for role in (0,1):emit(3,role,at+1,mission_stage=9)
 for role in (0,1):emit(73,role,at+2,mission_stage=9,planning_ready=1,route_ready=1,route_generation=2,committed_route_count=2)
 for i,node in enumerate(route):emit(74,0,at+2,arg=i,mission_stage=9,route_generation=2,committed_route_count=2,committed_route_xyz=node['xyz'])
 emit(50,0,at+3,tag=6,mission_stage=1)
 n=dict(issued_frame=at-5,planning_timeout_ms=6000,planning_ready_frame=at,planning_front=f,planning_support=s,safe_front=f,safe_support=s,route_generation=2,route_committed_generation=2,route_ready=1,route_commit_frame=at+2,route_count=2,planning_failed=0,mission_deadline_frame=4500)
 r.update(native=n,events=ev,planning_commit=dict(protocol='mfm4_stopped_route_commit_v1',generation=2,planning_ready_frame=at,route_count=2,expires_frame=4500,submitted_frame=at+1,planning_wall_elapsed=.5,planner_wall_elapsed=.2,front_admission=last['front'],support_admission=last['support']));r['request']['expires_frame']=4500
 return r
class PlanningQualificationTests(unittest.TestCase):
 def audit(self,r):
  with patch.object(q,'planned_source_audit',return_value=True),patch.object(q,'load_local',return_value=old.planner):return q.planning_commit_audit(r)
 def test_raw_two_stops_then_atomic_commit_then_move(self):
  a=self.audit(fixture());self.assertTrue(a['verified'],a)
 def test_one_role_or_one_frame_stop_is_not_three(self):
  for mode in ('missingrole','oneframe'):
   r=fixture()
   if mode=='missingrole':r['events']=[e for e in r['events'] if not(e['kind']==33 and e['role']==1)]
   else:
    for e in r['events']:
     if e['kind']==3 and e['mission_stage']==8:e['frame']=r['native']['planning_ready_frame']
   self.assertFalse(self.audit(r)['verified'],mode)
 def test_cannot_move_before_commit_even_same_tick(self):
  r=fixture();move=r['events'].pop();idx=next(i for i,e in enumerate(r['events']) if e['kind']==73);r['events'].insert(idx,move)
  for i,e in enumerate(r['events']):e['seq']=i+1
  self.assertFalse(self.audit(r)['checks']['no_move_before_atomic_commit'])
 def test_generation_1_3_and_shared_count_scalar_do_not_commit(self):
  for generation in [0,1,3]:
   r=fixture();r['native']['route_committed_generation']=generation;self.assertFalse(self.audit(r)['verified'])
  r=fixture();r['events']=[e for e in r['events'] if e['kind']!=74];self.assertFalse(self.audit(r)['verified'])
 def test_each_frozen_point_must_match_request(self):
  r=fixture();next(e for e in r['events'] if e['kind']==74)['committed_route_xyz']=[999,999,0];self.assertFalse(self.audit(r)['checks']['atomic_frozen_route_echo'])
  r=fixture();points=[e for e in r['events'] if e['kind']==74];points[1]['arg']=0;self.assertFalse(self.audit(r)['checks']['atomic_frozen_route_echo'])
 def test_idle_hold_cannot_drift_or_resume_attack(self):
  for key,value in [('x',99999),('state_id',10),('path',123),('source',0),('sm_flags',1)]:
   r=fixture();next(e for e in r['events'] if e['kind']==3 and e['mission_stage']==9)[key]=value;self.assertFalse(self.audit(r)['checks']['stopped_while_planning'],key)
 def test_full_fov_is_required_at_both_ready_and_accept(self):
  for kind in (72,73):
   r=fixture();next(e for e in r['events'] if e['kind']==kind)['target_visible']=0;self.assertFalse(self.audit(r)['verified'])
 def test_6_second_native_and_2_second_pure_planner_limits(self):
  r=fixture();r['planning_commit']['planner_wall_elapsed']=2.001;self.assertFalse(self.audit(r)['checks']['planning_time_bound'])
  r=fixture();ready=next(e for e in r['events'] if e['kind']==72)
  for e in r['events']:
   if e['kind']==73:e['tick']=ready['tick']+6001
  self.assertFalse(self.audit(r)['checks']['single_generation_commit'])
 def test_wrong_source_or_actor_readiness_cannot_be_true(self):
  r=fixture();r['planning_commit']['support_admission']['state_snapshot']['state_id']=10;self.assertFalse(self.audit(r)['checks']['same_stopped_actor_admission'])
  r=fixture()
  with patch.object(q,'planned_source_audit',return_value=False),patch.object(q,'load_local',return_value=old.planner):self.assertFalse(q.planning_commit_audit(r)['verified'])
 def test_declared_planning_failure_is_not_valid_success(self):
  r=fixture();r['native']['planning_failed']=2;self.assertFalse(self.audit(r)['checks']['no_planning_failure'])
 def test_late_header_deadline_cannot_change_raw_ready_deadline(self):
  r=fixture();r['planning_commit']['expires_frame']=4600;r['request']['expires_frame']=4600;r['native']['mission_deadline_frame']=4600;self.assertFalse(self.audit(r)['checks']['frozen_deadline_across_planning'])
 def test_new_planning_stages_publish_approach_without_regression(self):
  r=fixture()
  for kind in (72,73):
   e=next(x for x in r['events'] if x['kind']==kind);e.update(own_hp=100.,native_error=0,mission_reason=0,mission_deadline_frame=4500)
   a=q.progress(dict(r,events=r['events'][:e['seq']]),'mission');self.assertEqual(a['stage'],'approach');self.assertEqual(len(a),9)
 def test_failure_before_plan_can_release_but_never_completes(self):
  r=dict(native=dict(planning_failed=1,error=55,move_calls=0,support=dict(move_calls=0)),events=[dict(kind=75,role=role,arg=1,frame=20,tick=2000) for role in (0,1)])
  with patch.object(q,'control_release',return_value=dict(control_release_verified=True,return_verified=True)):
   a=q.planning_failure_audit(r);self.assertTrue(a['control_release_verified']);self.assertFalse(a['completion_claim']);self.assertFalse(a['effect_verified'])
  r['native']['move_calls']=1
  with patch.object(q,'control_release',return_value=dict(control_release_verified=True,return_verified=True)):self.assertFalse(q.planning_failure_audit(r)['control_release_verified'])
 def test_actual_source_nodes_and_persisted_plan_are_independently_rechecked(self):
  old4=load('mf4_real_late_source_fixture',H.parent/'mission-formation-v3/test_admission_wrapper_v4.py');r=old4.fixture();route=r['request']['route'];pre=r['preflight'];frame=r['last_admission']['frame'];plan=dict(schema_version=1,session_id=r['session_id'],pid=pre['pid'],player_id=3,front_id=r['request']['front_id'],support_id=r['request']['support_id'],route=route,source='positive_ground_own_positions_role_aware',walkable_route_verified=False)
  origin=dict(origin_method='current_verified_owned_movable_positions',viewer_player_id=3,front_id=r['request']['front_id'],support_id=r['request']['support_id'],observed_frame=pre['frame'],front_initial=pre['selected']['xyz'],support_initial=pre['support']['xyz'],currently_visible_enemy_threats_within350=[]);r['request']['safe_origin']=origin
  validator=q.load_local('mf4_positive_source_test','route_provenance.py');sources=validator.source_records(route,dict(session_id=r['session_id'],pid=pre['pid']),frame,pre['owner'])
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'planned.json';path.write_text(json.dumps(plan),encoding='utf-8');r['planning_commit']=dict(source_plan=plan,source_plan_path=str(path),source_plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_validation=sources,submitted_frame=frame,planner_sha256=hashlib.sha256((H/'role_route_planner.py').read_bytes()).hexdigest(),origin_safety=origin,target=r['private_target'],occupancy=r['route_rebase']['occupancy'])
   self.assertTrue(q.planned_source_audit(r))
   for mode in ['wrongsha','newpoint','occupied','threat','lateframe']:
    broken=copy.deepcopy(r)
    if mode=='wrongsha':broken['planning_commit']['source_validation'][0]['sha256']='0'*64
    elif mode=='newpoint':broken['planning_commit']['source_plan']['route'][0]['xyz'][0]+=1
    elif mode=='occupied':broken['planning_commit']['occupancy']['owned_positions'].append(dict(object_id=999999,xyz=route[0]['xyz']))
    elif mode=='threat':broken['planning_commit']['origin_safety']['currently_visible_enemy_threats_within350']=[123]
    else:broken['planning_commit']['submitted_frame']+=31
    self.assertFalse(q.planned_source_audit(broken),mode)
 def test_old_geometry_and_release_remain_conservative(self):
  oldtests=load('mf4_legacy_geometry_release',H.parent/'mission-formation-v3/test_mission.py')
  for stage in (1,3):self.assertTrue(all(x['verified'] for x in q.stage_audit(oldtests.staged(),[[80,0,0],[160,0,0]],[0,0,0],[-80,0,0],stage)))
  fixture=oldtests.ReleaseTests();r=fixture.rec();r['native'].update(planning_failed=1,error=55,move_calls=0);r['native']['support']['move_calls']=0;r['events']+=[dict(kind=75,role=role,arg=1,frame=110,tick=11000) for role in (0,1)]
  with patch.object(q,'source_pins',return_value=True):
   a=q.planning_failure_audit(r);self.assertTrue(a['control_release_verified']);self.assertFalse(a['completion_claim']);r['terminal_readonly']['timer']=1;self.assertFalse(q.planning_failure_audit(r)['control_release_verified'])
 def test_timeout_label_requires_real_six_second_wait(self):
  r=dict(native=dict(planning_failed=2,error=55,move_calls=0,support=dict(move_calls=0)),events=[dict(kind=72,tick=0)]+[dict(kind=75,role=role,arg=2,frame=20,tick=5999) for role in (0,1)])
  with patch.object(q,'control_release',return_value=dict(control_release_verified=True,return_verified=True)):self.assertFalse(q.planning_failure_audit(r)['planning_failed'])
if __name__=='__main__':unittest.main()
