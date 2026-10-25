"""Trusted client-only admission/planning tests; no SDK, kernel or child process."""
import types,unittest
from unittest.mock import MagicMock,patch
import test_client as boundary
import test_mission_client as mission_boundary
m=boundary.m

class SurfaceRouteClientTests(unittest.TestCase):
 def fake_loader(self,module):
  spec=types.SimpleNamespace(loader=MagicMock());return patch.object(m.importlib.util,'spec_from_file_location',return_value=spec),patch.object(m.importlib.util,'module_from_spec',return_value=module)
 def test_surface_eligibility_needs_verified_exact_actor_binding(self):
  e=boundary.ModelBoundary().executor();units=[dict(object_id=1,address='0x2000',type_hash='0x19ab11af',xyz=[0,0,0],hp=100)]
  record=dict(object_id=1,address='0x2000',owner='0x3000',type_hash='0x19ab11af',grounded_status=dict(xyz=[5,6,210],hp=75))
  for good in [True,False]:
   module=types.SimpleNamespace(actor_admission=lambda *args:record,verify_evidence=lambda x:dict(verified=good));p1,p2=self.fake_loader(module)
   with p1,p2:result=e._surface_ground_candidates(None,units,'0x3000')
   self.assertEqual(len(result),int(good))
   if good:self.assertEqual(result[0]['xyz'],[5,6,210]);self.assertEqual(result[0]['hp'],75)
  record['owner']='0x4000';module=types.SimpleNamespace(actor_admission=lambda *args:record,verify_evidence=lambda x:dict(verified=True));p1,p2=self.fake_loader(module)
  with p1,p2:self.assertFalse(e._surface_ground_candidates(None,units,'0x3000'))
 def test_public_unknown_surface_is_not_silently_no_army_or_enqueued(self):
  helper=mission_boundary.MissionClientTests();e,t,pre,captured=helper.setup_executor();e.capability_grants[('attack','main_attack')]['executor_directory']='mission-combat-v5';e._surface_ground_candidates=MagicMock(return_value=[])
  r=helper.submit(e,t,pre);self.assertFalse(r['accepted']);self.assertTrue(r['no_dispatch_verified']);self.assertIn('evidence_unavailable_not_no_army',r['reason_code']);self.assertFalse(captured);self.assertFalse(e.ledger)
 def test_route_pair_skips_no_route_without_reusing_first_pair(self):
  e=boundary.ModelBoundary().executor();e.session['pid']=1234;pre={'frame':100};f1={'object_id':1,'xyz':[0,0,0]};f2={'object_id':2,'xyz':[10,0,0]};support={'object_id':3,'xyz':[-60,0,0]};good=dict(front_id=2,support_id=3,session_id=e.session['session_id'],pid=e.session['pid'],route=[{'xyz':[1,2,3]},{'xyz':[4,5,6]}]);planner=MagicMock(side_effect=[ValueError('no route'),good]);p1,p2=self.fake_loader(types.SimpleNamespace(plan_from_history=planner))
  with p1,p2:result=e._role_route_pair({'formation_history_dir':'history'},pre,[100,0,0],[],[(2.,f2,support),(1.,f1,support)])
  self.assertEqual(result[1]['object_id'],2);self.assertEqual(planner.call_args_list[0].args[3]['object_id'],1);self.assertEqual(planner.call_args_list[1].args[3]['object_id'],2)
 def test_foreign_route_plan_fails_before_any_wrapper(self):
  e=boundary.ModelBoundary().executor();e.session['pid']=1234;planner=lambda *args,**kwargs:dict(front_id=99,support_id=2,session_id=e.session['session_id'],pid=e.session['pid'],route=[{},{}]);p1,p2=self.fake_loader(types.SimpleNamespace(plan_from_history=planner))
  with p1,p2,self.assertRaisesRegex(ValueError,'planner_binding'):e._role_route_pair({'formation_history_dir':'history'},{},[0,0,0],[],[(1.,{'object_id':1,'xyz':[0,0,0]},{'object_id':2,'xyz':[-60,0,0]})])
 def test_no_route_is_a_definitive_prequeue_error(self):
  e=boundary.ModelBoundary().executor();p1,p2=self.fake_loader(types.SimpleNamespace(plan_from_history=MagicMock(side_effect=ValueError('no route'))))
  with p1,p2,self.assertRaisesRegex(ValueError,'no_role_safe_verified_ground_route'):e._role_route_pair({'formation_history_dir':'history'},{},[0,0,0],[],[(1.,{'object_id':1,'xyz':[0,0,0]},{'object_id':2,'xyz':[-60,0,0]})])
 def test_all_pairs_share_a_two_second_budget(self):
  e=boundary.ModelBoundary().executor();planner=MagicMock(side_effect=ValueError('no route'));p1,p2=self.fake_loader(types.SimpleNamespace(plan_from_history=planner));pairs=[(i,{'object_id':i,'xyz':[i,0,0]},{'object_id':99,'xyz':[-60,0,0]}) for i in [1,2,3]]
  with p1,p2,patch.object(m.time,'monotonic',side_effect=[100.,100.1,102.1]),self.assertRaisesRegex(ValueError,'total_budget_exhausted'):e._role_route_pair({'formation_history_dir':'history'},{},[100,0,0],[],pairs)
  self.assertEqual(planner.call_count,1);self.assertEqual(planner.call_args.kwargs['planning_deadline'],102.)
 def test_front_already_ahead_of_support_is_tried_first(self):
  e=boundary.ModelBoundary().executor();e.session['pid']=1234;back={'object_id':1,'xyz':[0,0,0]};ahead={'object_id':2,'xyz':[70,0,0]};support={'object_id':3,'xyz':[60,0,0]};plan=dict(front_id=2,support_id=3,session_id=e.session['session_id'],pid=1234,route=[{},{}]);planner=MagicMock(return_value=plan);p1,p2=self.fake_loader(types.SimpleNamespace(plan_from_history=planner))
  with p1,p2:r=e._role_route_pair({'formation_history_dir':'history'},{},[100,0,0],[],[(1.,back,support),(2.,ahead,support)])
  self.assertEqual(r[1]['object_id'],2);self.assertEqual(planner.call_count,1)

if __name__=='__main__':unittest.main()
