import copy,json,unittest
from projection import VisibilityProjection
class ProjectionTests(unittest.TestCase):
 def setUp(self):
  self.proof=dict(schema_version=2,object_visibility_method='native_footprint_reconstruction',footprint_live_verified=True,session_id='s',target_player_id=3,package_sha256='sha',terrain_view_live_verified=True,object_view_live_verified=True,conservative_stealth_exclusion_reviewed=True,no_observer_fallback=True)
  self.safety={'package_sha256':'sha','templates':{'0x123':{'role':'infantry','source_audited_no_intrinsic_stealth':True}}}
  self.ob={'relation':'enemy','terrain_shroud':1,'object_shroud_cached':1,'object_shroud_reconstructed':1,'object_visibility_method':'native_footprint_reconstruction','runtime_stealth_safe':True,'type_hash':'0x123','object_id':10,'owner_player_id':4,'region_id':'region_1','identity_stable':True,'observer_fallback':False,'alive':True,'xyz':[1,2,3],'address':'0x123abc','hp':100}
 def make(self):return VisibilityProjection('s',3,'sha',self.proof,self.safety,90)
 def test_clear_contact(self):self.assertEqual(len(self.make().project([self.ob],1)['contacts']),1)
 def test_no_addresses_or_precise_coords(self):
  text=json.dumps(self.make().project([self.ob],1))
  for word in ['0x123','xyz','address','object_id','type_hash','hp']:self.assertNotIn(word,text)
 def test_terrain_fog_closed(self):self.ob['terrain_shroud']=0;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_unknown_cache_closed(self):self.ob['object_shroud_reconstructed']=None;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_mixed_object_closed(self):self.ob['object_shroud_reconstructed']=2;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_cached_clear_does_not_override_partial_footprint(self):self.ob['object_shroud_cached']=1;self.ob['object_shroud_reconstructed']=2;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_lazy_zero_reconstructed_clear(self):self.ob['object_shroud_cached']=0;self.assertEqual(len(self.make().project([self.ob],1)['contacts']),1)
 def test_unknown_template_closed(self):self.ob['type_hash']='0x444';self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_stealthed_closed(self):self.ob['runtime_stealth_safe']=False;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_observer_closed(self):self.ob['observer_fallback']=True;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_wrong_proof_player_closed(self):self.proof['target_player_id']=2;self.assertFalse(self.make().project([self.ob],1)['visibility_verified'])
 def test_wrong_package_closed(self):self.safety['package_sha256']='other';self.assertFalse(self.make().project([self.ob],1)['visibility_verified'])
 def test_fog_memory_freezes_fact(self):
  p=self.make();a=p.project([self.ob],1)['contacts'][0];self.ob.update(terrain_shroud=0,region_id='hidden_new_region');b=p.project([self.ob],10)['contacts'][0]
  self.assertFalse(b['currently_visible']);self.assertEqual(b['region_id'],a['region_id']);self.assertEqual(b['observed_at_game_seconds'],1)
 def test_hidden_death_not_exported(self):
  p=self.make();p.project([self.ob],1);self.ob.update(alive=False,terrain_shroud=0);r=p.project([self.ob],10);self.assertEqual(len(r['contacts']),1);self.assertNotIn('destroyed',json.dumps(r))
 def test_memory_expires(self):p=self.make();p.project([self.ob],1);self.assertEqual(p.project([],92)['contacts'],[])
 def test_hidden_first_seen_never_created(self):self.ob['terrain_shroud']=0;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_region_counts_only_current(self):p=self.make();p.project([self.ob],1);self.assertFalse(p.project([],2)['regions'][0]['currently_visible']);self.assertEqual(p.project([],2)['regions'][0]['role_counts'],{})
 def test_clock_rollback_invalidates(self):
  p=self.make();p.project([self.ob],10)
  with self.assertRaises(ValueError):p.project([self.ob],5)
  self.assertEqual(p.seen,{})
 def test_identity_change_closed(self):self.ob['identity_stable']=False;self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
 def test_ally_not_enemy(self):self.ob['relation']='ally';self.assertEqual(self.make().project([self.ob],1)['contacts'],[])
if __name__=='__main__':unittest.main()
