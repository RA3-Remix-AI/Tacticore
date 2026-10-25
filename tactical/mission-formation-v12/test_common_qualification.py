"""MFM6 common/ground evidence tests; no Native launch or capability grant."""
import copy,ctypes as c,importlib.util,json,math,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mfm6_common_q',HERE/'formation_mission_qualification.py');q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
def fixture():
 pre=dict(player_id=3,owner='0x3000',ai='0x8000',window_thread=9,session_id='s',commander_id='c',frame=100,selected=dict(address='0x2000',object_id=42,type_hash='0x19ab11af',ai_address='0x4000'),support=dict(address='0x5000',object_id=43,type_hash='0x2c358c61',ai_address='0x6000'))
 report=dict(preflight=pre,session_id='s',request=dict(front_id=42,support_id=43,seq=1,command_id='cmd',task_id='task',expires_frame=4600),events=[],native=dict(session_id='s',commander_id='c',command_id='cmd',task_id='task',seq=1,object_id=42,support={'id':43},phase=1,active=1,issued_frame=110,mission_deadline_frame=4600,memory_ttl_frames=900,approach_limit=2100,retreat_limit=1800,hold_timeout_frames=60,combat_frames=180,route_count=0,route_ready=0,route_generation=0,crumbs=[[],[]]))
 for role in (0,1):
  u=q.actor(report,role);crumb=dict(index=0,role=role,frame=110,published_seq=role+1,thing=int(u['address'],0),object_id=u['object_id'],type_hash=q.ROLE_TYPES[role],owner=0x3000,update=int(u['ai_address'],0),holder=0,status_words=[0]*7,height_flags=4,height=0.,hp=100.,xyz=[100.+role*50,100.,210.],path_distance=0.,mission_stage=1,surface_verified=1)
  event=dict(seq=role+1,kind=80,tag=0,role=role,unit_id=u['object_id'],frame=110,tick=1000,thread=9,owner=0x3000,x=crumb['xyz'][0],y=100.,z=210.,own_hp=100.,arg=0,mission_stage=1,mission_deadline_frame=4600,damage_before=0.,damage_after=0.,damage_reported=0.,breadcrumb=copy.deepcopy(crumb));report['events'].append(event);report['native']['crumbs'][role].append(copy.deepcopy(crumb))
 return report
class CommonGround(unittest.TestCase):
 def test_actual_fixed_abi_from_native_shared_h(self):
  spec=importlib.util.spec_from_file_location('mfm6_common_layout',HERE/'native_layout.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  self.assertEqual(c.sizeof(m.Breadcrumb),104);self.assertEqual(c.sizeof(m.Event),1616);self.assertEqual(c.sizeof(m.Tactical),13266404);self.assertEqual(m.Tactical.events.offset,28132);self.assertEqual(q.sha(HERE/'shared.h'),m.SHARED_SHA256)
 def test_initial_positive_surface_needs_no_ground160(self):
  r=fixture()
  for e in r['events']:
   self.assertFalse(e['breadcrumb']['status_words'][5]&1);self.assertTrue(q.surface_sample(e['breadcrumb'],r,e)['verified'])
  self.assertTrue(q.breadcrumb_audit(r)['verified'])
 def test_positive_surface_claim_cannot_override_raw_exclusions(self):
  for index in (0,7,8,51,61,161,207,211):
   r=fixture();e=r['events'][0];e['breadcrumb']['status_words'][index//32]|=1<<(index%32);self.assertFalse(q.surface_sample(e['breadcrumb'],r,e)['verified'],index)
 def test_cache_holder_hp_finite_and_identity_independent(self):
  for key,value in [('height_flags',0),('height',1.),('height',float('nan')),('hp',0),('hp',float('inf')),('holder',9),('owner',1),('thing',2),('update',3),('type_hash',4),('object_id',55)]:
   r=fixture();e=r['events'][0];e['breadcrumb'][key]=value;self.assertFalse(q.surface_sample(e['breadcrumb'],r,e)['verified'],key)
 def test_source_event_cannot_echo_another_position_frame_role_or_seq(self):
  for key,value in [('frame',111),('published_seq',2),('role',1),('xyz',[999.,100.,210.])]:
   r=fixture();e=r['events'][0];e['breadcrumb'][key]=value;self.assertFalse(q.surface_sample(e['breadcrumb'],r,e)['verified'],key)
 def test_unknown_or_boolean_status_words_rejected(self):
  for value in [None,[0]*6,[False]+[0]*6,['0']+[0]*6]:
   r=fixture();e=r['events'][0];e['breadcrumb']['status_words']=value;self.assertFalse(q.surface_sample(e['breadcrumb'],r,e)['verified'])
 def test_header_cannot_replace_missing_or_mutated_publication(self):
  r=fixture();r['native']['crumbs'][0][0]['xyz'][0]=111.;self.assertFalse(q.breadcrumb_audit(r)['verified'])
  r=fixture();r['events'].pop();self.assertFalse(q.breadcrumb_audit(r)['verified'])
 def test_duplicate_out_of_order_or_rewritten_crumb_rejected(self):
  for index in [0,2]:
   r=fixture();e=copy.deepcopy(r['events'][0]);e.update(seq=3,arg=index);e['breadcrumb'].update(index=index,published_seq=3);r['events'].append(e);r['native']['crumbs'][0].append(copy.deepcopy(e['breadcrumb']));self.assertFalse(q.breadcrumb_audit(r)['verified'])
 def test_common_deadline_and_publication_guards_fail_closed(self):
  for field,value in [('memory_ttl_frames',901),('approach_limit',9999),('route_ready',1),('mission_deadline_frame',4601)]:
   r=fixture();r['native'][field]=value;self.assertFalse(q.common_audit(r)['verified'],field)
 def test_incomplete_algorithm_and_unbuilt_source_never_qualify(self):
  r=fixture();result=q.qualify(r);self.assertEqual(result['status'],'not_passed');self.assertFalse(result['effect_verified']);self.assertFalse(result['restoration_verified']);json.dumps(result,allow_nan=False)
if __name__=='__main__':unittest.main()
