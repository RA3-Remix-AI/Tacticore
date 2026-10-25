"""Offline boundary tests. Synthetic records are not live capability evidence."""
import copy,ctypes,hashlib,importlib.util,json,math,re,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
q=load('formation_mission_tests_qualifier',HERE/'formation_mission_qualification.py')
b=load('formation_mission_tests_wrapper',HERE/'lease.py')
r=load('formation_mission_tests_routes',HERE/'mission_route.py')

def staged():
 ev=[];frame=100
 def emit(kind,role,stage,index,step,xy,**extra):
  row=dict(seq=len(ev)+1,kind=kind,tag=6 if kind==50 else 0,role=role,mission_stage=stage,route_index=index,nav_step=step,frame=frame,tick=frame*100,x=xy[0],y=xy[1],z=0,unit_id=10+role,source=1,path=0,sm_flags=0);row.update(extra);ev.append(row)
 def pairs(stage,index,step,fp,sp):
  nonlocal frame
  for _ in range(3):frame+=1;emit(3,0,stage,index,step,fp);emit(3,1,stage,index,step,sp)
 for stage,indices in ((1,[0,1]),(3,[1,0])):
  for i in indices:
   fg=[80*(i+1),0,0] if stage==1 else [80*i,0,0]
   sg=[80*i,0,0] if stage==1 else [80*(i-1),0,0]
   before_f=[80*i,0,0] if stage==1 else [80*(i+1),0,0]
   before_s=[80*(i-1),0,0] if stage==1 else [80*i,0,0]
   frame+=1;emit(58,0,stage,i,1,before_f);emit(58,1,stage,i,1,before_s)
   lead=0 if stage==1 else 1;emit(50,lead,stage,i,1,before_f if lead==0 else before_s)
   pairs(stage,i,1,fg if lead==0 else before_f,sg if lead==1 else before_s)
   emit(50,1-lead,stage,i,2,before_s if lead==0 else before_f)
   pairs(stage,i,2,fg,sg);emit(60,0,stage,i,2,fg);emit(60,1,stage,i,2,sg)
 return ev

class HealthThresholdTests(unittest.TestCase):
 def test_explicit_half_health_boundary(self):
  for hp,allowed in [(49.999,False),(50,True),(100,True),(float('nan'),False),(float('inf'),False),(None,False)]:self.assertEqual(b.actor_health_eligible(hp),allowed)
 def test_field_planner_uses_identical_guard(self):self.assertEqual((HERE/'field_plan.py').read_text().count("b.actor_health_eligible(u['hp'])"),2)

class PairBoundaryTests(unittest.TestCase):
 def test_native_supported_initial_gap_boundary(self):
  for gap,allowed in [(24.999,False),(25,True),(180,True),(180.001,False),(float('nan'),False)]:self.assertEqual(b.initial_pair_eligible(gap),allowed)
 def test_field_planner_uses_same_pair_guard(self):self.assertIn("b.initial_pair_eligible(math.dist",(HERE/'field_plan.py').read_text())

class OriginEvidenceTests(unittest.TestCase):
 def record(self):
  f=dict(object_id=10,xyz=[0,0,0]);s=dict(object_id=11,xyz=[60,0,0]);o=dict(origin_method='current_verified_owned_movable_positions',viewer_player_id=3,front_id=10,support_id=11,observed_frame=100,front_initial=f['xyz'],support_initial=s['xyz'],anchor_distances_diagnostic=[],currently_visible_enemy_threats_within350=[])
  return dict(preflight=dict(player_id=3,frame=100,selected=f,support=s),request=dict(safe_origin=o))
 def test_real_origin_requires_no_arbitrary_base_radius(self):self.assertTrue(q.origin_verified(self.record()))
 def test_visible_threat_rejected(self):
  r=self.record();r['request']['safe_origin']['currently_visible_enemy_threats_within350']=[99];self.assertFalse(q.origin_verified(r))
 def test_wrong_actor_or_frame_rejected(self):
  for key,value in [('front_id',99),('observed_frame',99),('viewer_player_id',2)]:
   r=self.record();r['request']['safe_origin'][key]=value;self.assertFalse(q.origin_verified(r))
 def test_origin_cannot_be_unobserved_point(self):
  r=self.record();r['request']['safe_origin']['front_initial']=[40,0,0];self.assertFalse(q.origin_verified(r))

class GeometryTests(unittest.TestCase):
 def audit(self,ev,stage):return q.stage_audit(ev,[[80,0,0],[160,0,0]],[0,0,0],[-80,0,0],stage)
 def test_multiple_advance_and_reverse_retreat(self):
  for stage in (1,3):self.assertTrue(all(x['verified'] for x in self.audit(staged(),stage)))
 def test_reject_same_frame_count_inflation(self):
  ev=staged()
  for e in ev:
   if e['kind']==3 and e['mission_stage']==1 and e['route_index']==0 and e['nav_step']==2:e['frame']=500;e['tick']=50000
  self.assertFalse(self.audit(ev,1)[0]['verified'])
 def test_reject_support_moves_before_front(self):
  ev=staged();moves=[e for e in ev if e['kind']==50 and e['mission_stage']==1 and e['route_index']==0]
  moves[0]['role'],moves[1]['role']=1,0
  self.assertFalse(self.audit(ev,1)[0]['verified'])
 def test_reject_front_leaves_hold_during_rear_withdrawal(self):
  ev=staged()
  for e in ev:
   if e['kind']==3 and e['mission_stage']==3 and e['route_index']==1 and e['nav_step']==1 and e['role']==0:e['y']=16
  self.assertFalse(self.audit(ev,3)[0]['verified'])
 def test_arrival_radius_not_relaxed(self):
  for offset,expected in ((15,True),(15.001,False)):
   ev=staged()
   for e in ev:
    if e['kind']==3 and e['mission_stage']==1 and e['route_index']==0 and e['nav_step']==2 and e['role']==1:e['y']=offset
   self.assertEqual(self.audit(ev,1)[0]['verified'],expected)
 def test_reject_nonmatching_sample_ticks(self):
  ev=staged()
  for e in ev:
   if e['role']==1 and e['kind']==3:e['tick']+=1
  self.assertFalse(any(x['verified'] for x in self.audit(ev,1)))

class ProgressTests(unittest.TestCase):
 def record(self):
  events=[]
  for i,(x,visible,target) in enumerate([(0,1,[500,0,0]),(100,1,[500,0,0]),(999,0,[99999,0,0])]):events.append(dict(seq=i+1,kind=3,tag=0,role=0,mission_stage=1,lease_stage=5,frame=100+i,tick=1000+i,x=x,y=0,z=0,own_hp=100,target_visible=visible,visible_target_xyz=target,mission_deadline_frame=4500,mission_reason=0,native_error=0))
  return dict(native={'issued_frame':100,'target':[99999,99999,0]},events=events)
 def test_remaining_distance_and_hidden_freeze(self):self.assertEqual(q.progress(self.record(),'task')['approach_distance'],400)
 def test_mutable_header_never_changes_same_revision(self):
  a=self.record();v=q.progress(a,'task');a['native'].update(target=[0,0,0],mission_stage=4,damage_total=100);self.assertEqual(v,q.progress(a,'task'))
 def test_revision_last_published_event_not_stage(self):
  value=q.progress(self.record(),'task');self.assertEqual(value['revision'],3);self.assertEqual(value['observed_frame'],102)
 def test_exact_nine_fields(self):self.assertEqual(set(q.progress(self.record(),'task')),{'mission_id','stage','revision','observed_frame','deadline_frame','approach_distance','own_hp','damage','reason'})
 def test_no_native_issue_no_telemetry(self):
  rec=self.record();rec['native']['issued_frame']=0;self.assertIsNone(q.progress(rec,'task'))
 def test_two_actual_returns_required_for_restored(self):
  rec=self.record();rec['events'].append(dict(rec['events'][-1],seq=4,kind=5,tag=3,mission_stage=4));self.assertEqual(q.progress(rec,'task')['stage'],'retreat');rec['events'].append(dict(rec['events'][-1],seq=5,role=1));self.assertEqual(q.progress(rec,'task')['stage'],'restored')
 def test_wrapper_uses_same_pure_progress(self):self.assertEqual(q.progress(self.record(),'task'),b.progress(self.record(),'task'))
 def test_never_visible_does_not_invent_distance(self):
  rec=self.record()
  for e in rec['events']:e['target_visible']=0
  self.assertIsNone(q.progress(rec,'task')['approach_distance'])

class ReleaseTests(unittest.TestCase):
 def entries(self):
  block=(HERE/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
  return [dict(address=a,expected=e.replace('\\x',''),actual=e.replace('\\x',''),restored=True) for a,e,n in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block)]
 def disposal(self,x):
  x['preflight'].update(pid=1,commander_id='commander',owner='0x2',logic='0x3');x['request']=dict(command_id='cmd',task_id='task',seq=1,token=7);x['native_binary_sha256']='bin';pre=x['preflight'];rq=x['request'];bound=dict(pid=1,session_id='session',commander_id='commander',owner='0x2',logic='0x3',native_binary_sha256='bin',**rq);terminal=dict(x['terminal_readonly'],**bound,module_base='0x4',shared_pointer='0x5',mutations=False)
  return dict(bound,object_id=10,role=0,source_session_id='session',source_request_sha256=hashlib.sha256(json.dumps(rq,sort_keys=True,separators=(',',':')).encode()).hexdigest(),source_preflight_sha256=hashlib.sha256(json.dumps(pre,sort_keys=True,separators=(',',':')).encode()).hexdigest(),terminal_before=terminal,terminal_after=copy.deepcopy(terminal),scans=[dict(complete=True,logic='0x3',frame=f,end_frame=f,count=2,ids=[11,12]) for f in (200,201)],mutations=False)
 def rec(self,death=False):
  ev=[]
  for role in (0,1):
   if death and role==0:continue
   ev.append(dict(seq=len(ev)+1,kind=33,arg=1,caller=0x787791,role=role,frame=100,x=0,y=0,z=0))
   for frame in (101,102,103):ev.append(dict(seq=len(ev)+1,kind=3,role=role,frame=frame,x=0,y=0,z=0,path=0,sm_flags=0,source=1))
   ev.append(dict(seq=len(ev)+1,kind=66,role=role,frame=103,x=0,y=0,z=0))
   for kind,arg,caller in [(16,0x1104,0x83885b),(15,1,0),(5,0,0)]:ev.append(dict(seq=len(ev)+1,kind=kind,tag=3,role=role,arg=arg,caller=caller))
  return dict(native={'phase':4,'error':32 if death else 48,'restore_mask':8191,'active':0,'detach_calls':1,'return_calls':0 if death else 1,'return_verified':0 if death else 1,'support':{'detach_calls':1,'return_calls':1,'returned':1}},preflight={'ai':'0x1000','selected':{'object_id':10},'support':{'object_id':11}},session_id='session',events=ev,terminal_readonly={'timer':0,'phase':4,'restore_mask':8191,'active':0,'binding_verified':True,'entries':self.entries()})
 def verify(self,x):
  with patch.object(q,'source_pins',return_value=True):return q.control_release(x)
 def test_failed_goal_two_real_returns_still_release(self):self.assertTrue(self.verify(self.rec())['restoration_verified'])
 def test_alive_companion_cannot_be_abandoned_on_front_death(self):
  x=self.rec(True);self.assertFalse(self.verify(x)['restoration_verified'])
 def test_two_distinct_absent_scans_plus_survivor_return_release(self):
  x=self.rec(True);x['disposal_readonly']={'0':self.disposal(x)};v=self.verify(x);self.assertTrue(v['restoration_verified']);self.assertTrue(v['disposed_verified']);self.assertFalse(v['return_verified']);self.assertFalse(v['completion_claim'])
 def test_dead_id_still_live_rejects(self):
  x=self.rec(True);x['disposal_readonly']={'0':{'object_id':10,'source_session_id':'session','scans':[{'complete':True,'frame':f,'end_frame':f,'count':2,'ids':[10,11]} for f in (200,201)]}};self.assertFalse(self.verify(x)['restoration_verified'])
 def test_one_frame_scan_twice_rejects(self):
  x=self.rec(True);x['disposal_readonly']={'0':{'object_id':10,'source_session_id':'session','scans':[{'complete':True,'frame':200,'end_frame':200,'count':2,'ids':[11,12]}]*2}};self.assertFalse(self.verify(x)['restoration_verified'])
 def test_active_timer_blocks_release(self):
  x=self.rec();x['terminal_readonly']['timer']=1;self.assertFalse(self.verify(x)['restoration_verified'])
 def test_same_actor_return_duplicated_cannot_cover_other(self):
  x=self.rec()
  for e in x['events']:e['role']=0
  self.assertFalse(self.verify(x)['restoration_verified'])

 def test_terminal_boolean_cannot_replace_bytes(self):
  x=self.rec();x['terminal_readonly']['entries']=[dict(restored=True)]*13;self.assertFalse(self.verify(x)['restoration_verified'])
 def test_disposal_wrong_child_identity_rejected(self):
  x=self.rec(True);d=self.disposal(x);d['task_id']='wrong';x['disposal_readonly']={'0':d};self.assertFalse(self.verify(x)['restoration_verified'])
 def test_disposal_wrong_logic_rejected(self):
  x=self.rec(True);d=self.disposal(x);d['scans'][0]['logic']='wrong';x['disposal_readonly']={'0':d};self.assertFalse(self.verify(x)['restoration_verified'])

class V2RegressionTests(unittest.TestCase):
 def test_forced_return_not_settled_release(self):
  fixture=ReleaseTests();r=fixture.rec()
  for e in r['events']:
   if e['kind']==66:e['kind']=69
  self.assertFalse(fixture.verify(r)['restoration_verified'])
 def test_canonical_assessment_matches_persisted_raw(self):
  path=HERE.parent.parent/'acceptance/runs/20261025-105617-commander/coord-mission03.json';r=json.loads(path.read_text(encoding='utf-8-sig'));expected=q.qualify(r)
  for key in ['front_initial','support_initial']:r['request']['safe_origin'][key]=tuple(r['request']['safe_origin'][key])
  for key in ['selected','support']:r['preflight'][key]['xyz']=tuple(r['preflight'][key]['xyz'])
  self.assertEqual(b.assess_canonical(r),expected)

class RouteTests(unittest.TestCase):
 def test_no_enemy_fallback_when_own_history_empty(self):
  with tempfile.TemporaryDirectory() as path:
   with self.assertRaisesRegex(ValueError,'no_private_owned'):r.plan_from_history(path,{'frame':100},{'session_id':'s','pid':1},{'object_id':10,'xyz':[0,0,0]},{'object_id':11},[500,500,0],[])
 def test_old_primitive_report_is_not_a_mission(self):
  result=q.qualify({'native':{'phase':3,'restore_mask':127,'active':0},'preflight':{},'request':{},'events':[]})
  self.assertFalse(result['combined_arms_verified'])

if __name__=='__main__':unittest.main()
