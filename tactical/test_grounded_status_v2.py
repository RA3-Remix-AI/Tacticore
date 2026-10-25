"""Surface-positive admission boundaries; no SDK, process or GUI operations."""
import copy,math,struct,unittest
import grounded_status_v2 as g

class Memory:
 def __init__(self):
  self.words=[0]*7;self.cache=4;self.height=0.;self.hp=100.;self.xyz=[100.,200.,210.];self.holder=0;self.kind=0x19ab11af;self.frame=[100,100];self.ids=[77,77];self.reads=[]
 def u32(self,a):
  if a==0x1050:return self.frame.pop(0) if len(self.frame)>1 else self.frame[0]
  if a==0x20dc:return self.ids.pop(0) if len(self.ids)>1 else self.ids[0]
  return {0xcd8ce4:0x1000,0x1000:0xbeb630,0x2000:0xc4db60,0x2418:0x3000,0x2004:0x4000,0x4008:self.kind,0x3000:0xc5bce0,0x3020:3,0x233c:0x5000,0x2048:self.cache,0x2238:self.holder}.get(a,0)
 def read(self,a,n):
  self.reads.append((a,n));return {(0x2080,28):struct.pack('<7I',*self.words),(0x2038,12):struct.pack('<3f',*self.xyz),(0x205c,4):struct.pack('<f',self.height),(0x5004,4):struct.pack('<f',self.hp)}[(a,n)]

class GroundedSurface2Tests(unittest.TestCase):
 def test_pure_record_verifier_rechecks_raw_fields_and_source(self):
  r=g.grounded_status(Memory(),0x2000);self.assertTrue(g.verify_evidence(r)['verified'])
  for key,value in [('height_cache_flags','0x0'),('cached_height_distance',10.),('cached_height_distance',math.nan),('type_hash','0x33026fa1'),('helper_sha256','0'*64),('frame',101),('holder','0x6000'),('grounded_verified',False),('walkable_route_verified',True)]:
   changed=copy.deepcopy(r);changed[key]=value;self.assertFalse(g.verify_evidence(changed)['verified'],key)
  changed=copy.deepcopy(r);changed['status_words'][0]='0x80';self.assertFalse(g.verify_evidence(changed)['verified'])
 def test_zero_valid_height_is_positive_without_flag160(self):
  m=Memory();r=g.grounded_status(m,0x2000);self.assertTrue(r['grounded_verified']);self.assertTrue(r['ground_positive']);self.assertFalse(r['ground160_diagnostic']);self.assertFalse(r['walkable_route_verified'])
 def test_both_ground_only_templates_have_same_positive_rule(self):
  for kind in g.FOOT:
   m=Memory();m.kind=kind;self.assertTrue(g.grounded_status(m,0x2000)['grounded_verified'])
 def test_invalid_cache_zero_or_stale_negative_is_not_positive(self):
  for height in [0.,-3.35997]:
   m=Memory();m.cache=0;m.height=height;r=g.grounded_status(m,0x2000);self.assertFalse(r['height_cache_valid']);self.assertFalse(r['grounded_verified'])
 def test_nonzero_or_nonfinite_height_not_positive(self):
  for height in [.501,-.501,10.,30.,math.nan,math.inf]:
   m=Memory();m.height=height;self.assertFalse(g.grounded_status(m,0x2000)['grounded_verified'])
 def test_every_known_air_or_mobility_flag_blocks_positive_surface(self):
  for name,(record,index) in g.native_status.FLAGS.items():
   if name=='GROUND_LOCOMOTOR_ACTIVE':continue
   m=Memory();m.words[index>>5]|=1<<(index&31);self.assertFalse(g.grounded_status(m,0x2000)['grounded_verified'],name)
 def test_holder_dead_and_amphibious_or_unknown_template_rejected(self):
  for attr,value in [('holder',0x6000),('hp',0.),('hp',math.nan),('kind',0x33026fa1),('kind',1234)]:
   m=Memory();setattr(m,attr,value);self.assertFalse(g.grounded_status(m,0x2000)['grounded_verified'],attr)
 def test_same_frame_identity_and_xyz_stability_required(self):
  for attr,value in [('frame',[100,101]),('ids',[77,78])]:
   m=Memory();setattr(m,attr,value);self.assertEqual(g.grounded_status(m,0x2000)['status'],'unknown_or_ineligible')
  m=Memory();original=m.read;count=[0]
  def changed(a,n):
   if a==0x2038:count[0]+=1;return struct.pack('<3f',100.+count[0],200.,210.)
   return original(a,n)
  m.read=changed;self.assertFalse(g.grounded_status(m,0x2000)['grounded_verified'])
 def test_foreign_owner_never_reads_coordinates_or_health(self):
  m=Memory();original=m.u32;m.u32=lambda a:4 if a==0x3020 else original(a);self.assertFalse(g.grounded_status(m,0x2000)['grounded_verified']);self.assertFalse(m.reads)
 def test_static_cached_height_and_coordinate_invalidation_pins(self):
  proof=g.static_proof('E:/RedRar3/Data/RA3_1.12.game');self.assertFalse(proof['ground160_required']);self.assertEqual(len(proof['surface_cache_proof']),4)

if __name__=='__main__':unittest.main()
