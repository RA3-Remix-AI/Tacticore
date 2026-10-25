import copy,hashlib,json,tempfile,random,math
import importlib.util
import unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('roles',Path(__file__).with_name('role_route_planner.py'));p=importlib.util.module_from_spec(s);s.loader.exec_module(p)

class Geometry(unittest.TestCase):
 def surface(self):
  hashes={k:hashlib.sha256((Path(__file__).parent.parent/n).read_bytes()).hexdigest() for k,n in [('helper_sha256','grounded_status_v2.py'),('native_status_helper_sha256','grounded_status.py')]}
  flags={k:False for k in ['AIRBORNE_TARGET','PARACHUTING','GROUND_LOCOMOTOR_ACTIVE','AIR_LOCOMOTOR_ACTIVE','LANDING_IN_PROGRESS','LIFTED_INTO_AIR','INSIDE_GARRISON','IMMOBILE']}
  return dict(grounded_verified=True,type_hash='0x19ab11af',xyz=[100,0,210],hp=100,grounded_status=dict(**hashes,flags=flags,known_air_state=False,ground160_diagnostic=False,ground_positive=True,owner='0x1234',address='0x5678',object_id=99,frame=10,end_frame=10,atomic_sample_verified=True,schema_version=2,status='verified_native_surface_sample',grounded_verified=True,template='SovietAntiInfantryInfantry',source='ground_only_template_plus_valid_native_surface_cache_and_air_exclusions_v2',status_words=['0x0']*7,height_cache_flags='0x4',holder='0x0',height_cache_valid=True,cached_height_distance=0.,height_tolerance=.5,hp=100,xyz=[100,0,210],mutations=False,walkable_route_verified=False))
 def test_forward_and_reverse_safe(self):
  self.assertTrue(p.route_geometry([0,0,0],[-60,0,0],[{'xyz':[100,0,0]},{'xyz':[200,0,0]},{'xyz':[300,0,0]}]))
 def test_actual_failed_front_goal_crosses_support(self):
  self.assertFalse(p.leg_geometry([2160,2420,210],[1967.768,2487.768,210],[1963.462,2488.442,210],True))
 def test_reverse_direction_rejected(self):
  self.assertFalse(p.leg_geometry([0,0,0],[-60,0,0],[-100,0,0],True))
 def test_holder_crossing_rejected(self):
  self.assertLess(p.segment_clearance([0,0,0],[-100,0,0],[-60,0,0]),25)
 def test_first_leg_headroom(self):
  self.assertFalse(p.leg_geometry([0,0,0],[-60,0,0],[170,0,0],True))
 def test_turn_can_keep_both_roles_clear(self):
  self.assertTrue(p.route_geometry([0,0,0],[-60,0,0],[{'xyz':[100,0,0]},{'xyz':[100,100,0]}]))
 def test_old_unqualified_history_unknown(self):
  self.assertFalse(p.positive_ground({'grounded_verified':True,'status84':'0x0'}))
 def test_copied_boolean_cannot_certify_ground(self):
  self.assertFalse(p.positive_ground({'grounded_verified':True,'grounded_status':{'grounded_verified':True,'status_words':['0x0']*7}}))
 def test_native_surface_positive_without_flag160(self):
  self.assertTrue(p.positive_ground(self.surface()))
 def test_seven_words_air_garrison_dead_negative(self):
  for i in (0,7,8,51,61,161,207,211):
   r=self.surface();r['grounded_status']['status_words'][i>>5]=hex(1<<(i&31));self.assertFalse(p.positive_ground(r))
 def test_cache_holder_height_and_amphibious_negative(self):
  for k,v in [('height_cache_flags','0x0'),('holder','0x1000'),('cached_height_distance',.501),('cached_height_distance',float('nan')),('height_tolerance',10),('template','SovietScoutInfantry'),('xyz',[1,2,3]),('hp',0)]:
   r=self.surface();r['grounded_status'][k]=v;self.assertFalse(p.positive_ground(r),k)
 def fixture(self,folder,wrong_sha=False,old_method=False):
  reader=Path(__file__).parent.parent/'grounded_status_v2.py'
  for i,x in enumerate((-100,100,200,300)):
   r=self.surface();r.update(object_id=99,xyz=[x,0,210]);r['grounded_status'].update(object_id=99,type_hash=r['type_hash'],xyz=r['xyz'],frame=10,end_frame=10)
   record=dict(session_id='s',pid=1,player_id=3,logic_frame_candidate=10,method='same_frame_owned_position_with_positive_ground_locomotor' if old_method else 'same_frame_owned_position_with_verified_native_surface',ground_reader_sha256='bad' if wrong_sha else hashlib.sha256(reader.read_bytes()).hexdigest(),own_objects=[r])
   (Path(folder)/f'{i}.json').write_text(json.dumps(record),encoding='utf-8')
 def run_plan(self,folder,own=None):
  return p.plan_from_history(folder,{'frame':20},{'session_id':'s','pid':1},{'object_id':77,'xyz':[0,0,210]},{'object_id':88,'xyz':[-60,0,210]},[500,0,210],own or [])
 def test_explicit_route_uses_forward_real_sources(self):
  with tempfile.TemporaryDirectory() as d:
   self.fixture(d);r=self.run_plan(d);self.assertTrue(p.route_geometry([0,0,210],[-60,0,210],r['route']));self.assertGreater(r['route'][0]['xyz'][0],0);self.assertFalse(r['walkable_route_verified']);self.assertTrue(all(Path(x['own_source_path']).exists() for x in r['route']))
 def test_wrong_reader_fingerprint_and_old_history_rejected(self):
  for opts in ({'wrong_sha':True},{'old_method':True}):
   with tempfile.TemporaryDirectory() as d:
    self.fixture(d,**opts)
    with self.assertRaisesRegex(ValueError,'no_positive_native_ground_history'):self.run_plan(d)
 def test_current_third_actor_occupancy_blocks_only_first_leg(self):
  with tempfile.TemporaryDirectory() as d:
   self.fixture(d)
   with self.assertRaisesRegex(ValueError,'no_role_safe_first_leg_from_current_pair'):self.run_plan(d,[{'object_id':555,'xyz':[100,0,210]}])
 def test_fast_local_geometry_equivalent_to_original_segments(self):
  rng=random.Random(47)
  for _ in range(10000):
   f=[rng.uniform(-200,200),rng.uniform(-200,200),0];s=[rng.uniform(-200,200),rng.uniform(-200,200),0];q=[rng.uniform(-200,200),rng.uniform(-200,200),0]
   dot=(f[0]-s[0])*(q[0]-f[0])+(f[1]-s[1])*(q[1]-f[1]);d=p.xy(f,q)
   reference=40<=d<=160 and dot>=0 and p.segment_clearance(f,q,s)>=25 and p.segment_clearance(s,f,q)>=25
   self.assertEqual(p.leg_geometry(f,s,q),reference)

if __name__=='__main__':unittest.main()
