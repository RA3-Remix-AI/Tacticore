"""MF5 parent allocation stays identity-only; all native boundaries are fake."""
import importlib.util,tempfile,unittest
from pathlib import Path
import test_mission4_planning_client as boundary

class BreadcrumbClient(unittest.TestCase):
 family="mission-formation-v5"
 def test_formation_dispatch_has_no_prior_route_or_ground_history_requirement(self):
  helper=boundary.HeldPlanningClient()
  with tempfile.TemporaryDirectory() as folder:
   e,task,pre,captured=helper.setup_case(folder);e.session['pid']=123
   e.capability_grants[('combined_arms','coordinate_force')]['executor_directory']=self.family
   e.mission_context=dict(schema_version=1,route=[{'xyz':[999,999,999]}],retreat_point=dict(xyz=[1,2,3]),unknown_private_data='not_forwarded')
   result=helper.submit(e,task,pre)
  self.assertTrue(result['accepted'],result);self.assertEqual(result['object_ids'],[1,2]);self.assertFalse(result['started'])
  payload=captured[0]['mission_input']
  self.assertEqual(set(payload),{'schema_version','session_id','pid','player_id','front_id','support_id','target_contact_id','navigation_mode','expires_frame'})
  self.assertEqual(payload['navigation_mode'],'native_leader_actual_breadcrumbs');self.assertEqual(payload['expires_frame'],5500)
  e._role_route_pair.assert_not_called();self.assertEqual(e._surface_ground_candidates.call_args.args[-1],'mission_actor_admission_v2.py')
  spec=importlib.util.spec_from_file_location('mf5_parent_contract',Path(__file__).parent/self.family/'mission_contract.py');contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
  validated=contract.validate_mission(payload,e.session,1,2,target_contact_id='contact_c',now_frame=1000,expires_frame=5500)
  self.assertEqual(validated['lease_frames'],4500)

 def test_missing_verified_mobile_actors_cannot_start_breadcrumb_control(self):
  helper=boundary.HeldPlanningClient()
  with tempfile.TemporaryDirectory() as folder:
   e,task,pre,captured=helper.setup_case(folder);e.session['pid']=123
   e.capability_grants[('combined_arms','coordinate_force')]['executor_directory']=self.family
   e._surface_ground_candidates.side_effect=None;e._surface_ground_candidates.return_value=[]
   result=helper.submit(e,task,pre)
  self.assertFalse(result['accepted']);self.assertFalse(captured)

if __name__=='__main__':unittest.main()
