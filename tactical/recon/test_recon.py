import copy,math,unittest
from logic import choose,assessment,idle_report,digest_json
class ReconTests(unittest.TestCase):
 def setUp(self):
  self.u={'object_id':7,'type_hash':'0x19ab11af','eligible':True,'hp':100,'xyz':[0,0,10]}
  self.r={'session_id':'s','plan':{'session_id':'s','target':{'grid_cell':5,'region_id':'r','xyz':[300,0,10]}},'native':{'session_id':'s','issued_frame':100,'returned_frame':140,'phase':3,'error':0,'restore_mask':31,'active':0,'return_verified':1,'detach_calls':1,'move_calls':1,'return_calls':1},'native_report':{'session_id':'s','host_exit':0,'request':{'target':[300,0,10]},'assessment':{'status':'move_and_return_primitive_verified','checks':{'arrival_independent':True}}},'baseline':{'target_terrain_status':0,'clear_cells':[1,2]},'samples':[{'frame':110,'own_identity_verified':True,'new_clear_cells_in_target_region':2,'target_cell_newly_clear':True}],'error':None}
 def test_recon_all_criteria_pass(self):self.assertEqual(assessment(self.r)['status'],'recon_arrival_new_vision_and_return_verified')
 def test_arrival_only_does_not_pass(self):self.r['samples'][0].update(new_clear_cells_in_target_region=0,target_cell_newly_clear=False);self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_vision_without_arrival_does_not_pass(self):self.r['native_report']['assessment']['checks']['arrival_independent']=False;self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_gain_after_lease_not_counted(self):self.r['samples'][0]['frame']=160;self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_gain_before_lease_not_counted(self):self.r['samples'][0]['frame']=99;self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_region_gain_without_target_cell_rejects(self):self.r['samples'][0]['target_cell_newly_clear']=False;self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_restore_incomplete_rejects(self):self.r['native']['restore_mask']=15;self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_active_callback_rejects(self):self.r['native']['active']=1;self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_preknown_target_rejects(self):self.r['baseline']['clear_cells'].append(5);self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_wrong_native_target_rejects(self):self.r['native_report']['request']['target']=[310,0,10];self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_other_session_rejects(self):self.r['native_report']['session_id']='other';self.assertEqual(assessment(self.r)['status'],'not_passed')
 def test_hidden_enemy_not_needed_for_selection(self):u,r,p,d=choose([self.u],[('r',[500,0,0])]);self.assertEqual(u['object_id'],7);self.assertEqual(p,[500,0,10])
 def test_outside_bound_rejects(self):
  with self.assertRaises(ValueError):choose([self.u],[('r',[601,0,0])])
 def test_ineligible_own_rejects(self):
  self.u['eligible']=False
  with self.assertRaises(ValueError):choose([self.u],[('r',[300,0,0])])
 def test_all_same_region_candidates_considered(self):self.assertEqual(choose([self.u],[('r',[900,0,0]),('r',[300,0,0])])[3],300)
 def test_idle_report_checks_actual_restore(self):
  a={'session_id':'s','host_exit':0,'native':dict(phase=3,error=0,restore_mask=63,active=0)};self.assertTrue(idle_report(a,'s'));a['native']['active']=1
  with self.assertRaises(ValueError):idle_report(a,'s')
 def test_digest_rejects_mutation(self):a=digest_json(self.r);self.r['plan']['target']['xyz'][0]=100;self.assertNotEqual(a,digest_json(self.r))
 def test_only_one_move_per_lease(self):self.r['native']['move_calls']=2;self.assertEqual(assessment(self.r)['status'],'not_passed')
if __name__=='__main__':unittest.main()
