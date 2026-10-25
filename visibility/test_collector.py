import copy,struct,unittest
from native_read import read_player_relation
from collector import VisibilityCollector
from projection import VisibilityProjection
from test_native_read import FakeMemory
class CollectorTests(unittest.TestCase):
 def setUp(self):
  m=self.m=FakeMemory();self.session={'session_id':'s','mod_sha256':'sha'}
  for p,n in [(0xcd8ce4,0x150000),(0x150000,0xbeb630),(0x150050,100),(0xce8c9c,0x200000),(0x20003c,0x130000),(0x130000,0xc5bce0),(0x130020,3),(0x130090,0x210000),(0x210000,0xc60f60),(0x140000,0xc5bce0),(0x140020,4),(0x1500b4,0x160000)]:m.u(p,n)
  for ob,owner,template,body,record,oid,xyz,nxt in [(0x160000,0x140000,0x180000,0x190000,0x1a0000,17,(105.,205.,0.),0x170000),(0x170000,0x130000,0x181000,0x191000,0x1a1000,18,(115.,205.,0.),0)]:
   for off,value in [(0,0xc4db60),(4,template),(0x33c,body),(0x9c,record),(0xdc,oid),(0x418,owner),(0x7c,nxt),(0xc8,0)]:m.u(ob+off,value)
   m.u(template+8,0x123);m.put(body+4,struct.pack('<f',100));m.put(ob+0x38,struct.pack('<fff',*xyz));m.u(record+0x30,1);m.u(record,0x110000);m.u(record+0x1c,0x1b0000+(0 if oid==17 else 0x1000));m.u(record+0x20,1);m.u(0x1b0000+(0 if oid==17 else 0x1000),0x120000+(0 if oid==17 else 0x34));m.put(record+0xf8,b'\0\0')
  m.counter(0,0,3,1);m.counter(1,0,3,1)
  for p,n in [(0x1300fc,0x1d0000),(0x1d0010,1),(0x1d0008,0x1e0000),(0x1d000c,4),(0x1e0000,0x1f0000),(0x1f0000,4),(0x1f0004,0),(0x1f0008,0)]:m.u(p,n)
  m.put(0x992130,bytes.fromhex('8b4928e9b8f1ffff'));m.put(0x990379,bytes.fromhex('8b448124c20400'));m.put(0x6fda40,bytes.fromhex('8b81c8000000'))
  self.proof=dict(schema_version=2,object_visibility_method='native_footprint_reconstruction',footprint_live_verified=True,session_id='s',target_player_id=3,package_sha256='sha',terrain_view_live_verified=True,object_view_live_verified=True,conservative_stealth_exclusion_reviewed=True,no_observer_fallback=True)
  self.safety={'package_sha256':'sha','templates':{'0x123':{'role':'infantry','source_audited_no_intrinsic_stealth':True}}}
  self.projection=VisibilityProjection('s',3,'sha',self.proof,self.safety)
  self.c=VisibilityCollector(m,self.session,3,self.projection)
 def sample(self,t):
  self.m.u(0x150050,int(t*15));return self.c.collect(t)
 def test_clock_parameter_rejects_stale_sample(self):
  with self.assertRaises(ValueError):self.c.collect(0)
 def test_public_private_boundary(self):
  r=self.sample(1);self.assertEqual(len(r['contacts']),1);cid=r['contacts'][0]['contact_id'];self.assertEqual(self.c.private_targets[cid]['address'],0x160000);self.assertEqual(r['viewer_player_id'],3);self.assertNotIn('xyz',str(r));self.assertNotIn('object_id',str(r))
 def test_hidden_target_removed_private_and_memory_frozen(self):
  self.sample(1);self.m.u(0x1a0030,4);self.m.counter(0,0,3,0);r=self.sample(2);self.assertEqual(self.c.private_targets,{});self.assertFalse(r['contacts'][0]['currently_visible']);self.assertEqual(r['contacts'][0]['observed_at_game_seconds'],1)
 def test_active_invisible_excluded(self):self.m.u(0x1600c8,1<<11);self.assertEqual(self.sample(1)['contacts'],[])
 def test_camo_excluded(self):self.m.u(0x1600c8,1<<12);self.assertEqual(self.sample(1)['contacts'],[])
 def test_template_unknown_excluded(self):self.safety['templates']={};self.assertEqual(self.sample(1)['contacts'],[])
 def test_false_proof_own_points_only(self):self.proof['object_view_live_verified']=False;r=self.sample(1);self.assertFalse(r['visibility_verified']);self.assertEqual(r['contacts'],[]);self.assertTrue(self.c.region_points);self.assertFalse(self.c.private_targets)
 def test_ally_excluded(self):self.m.u(0x1f0004,2);self.assertEqual(self.sample(1)['contacts'],[])
 def test_unknown_relation_excluded(self):self.m.u(0x1f0004,7);self.assertEqual(self.sample(1)['contacts'],[])
 def test_invalidated_cache_reconstructed(self):self.m.u(0x1a0030,0);self.assertEqual(len(self.sample(1)['contacts']),1)
 def test_grid_fog_blocks_cached_clear(self):self.m.counter(0,0,3,0);self.assertEqual(self.sample(1)['contacts'],[])
 def test_own_region_points_no_hidden_truth(self):self.m.u(0x1a0030,4);self.m.counter(0,0,3,0);self.sample(1);self.assertEqual(list(self.c.region_points.values()),[[115.,205.,0.]])
 def test_failure_discards_old_private_targets(self):
  self.sample(1);self.m.u(0x150000,0)
  with self.assertRaises(ValueError):self.sample(2)
  self.assertEqual(self.c.private_targets,{})
 def test_list_cycle_fails_closed(self):
  self.m.u(0x17007c,0x160000)
  with self.assertRaises(ValueError):self.sample(1)
  self.assertEqual(self.c.private_targets,{})
 def test_relation_enemy(self):self.assertEqual(read_player_relation(self.m,0x130000,4),'enemy')
 def test_relation_missing_is_neutral(self):self.m.u(0x1d0010,0);self.assertEqual(read_player_relation(self.m,0x130000,4),'neutral')
 def test_relation_self(self):self.assertEqual(read_player_relation(self.m,0x130000,3),'self')
 def test_relation_cycle_rejects(self):
  self.m.u(0x1f0000,8);self.m.u(0x1f0008,0x1f0000)
  with self.assertRaises(ValueError):read_player_relation(self.m,0x130000,4)
if __name__=='__main__':unittest.main()
