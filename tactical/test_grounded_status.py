"""Status bit provenance and atomic read boundaries; no SDK or game access."""
import struct,unittest
from grounded_status import grounded_status,decode,FLAGS,static_proof

class Memory:
 def __init__(self,words=None):
  self.words=words or [0,0,0,0,0,1,0];self.calls=[];self.frames=[100,100];self.ids=[77,77]
 def u32(self,address):
  if address==0x1050:return self.frames.pop(0) if len(self.frames)>1 else self.frames[0]
  if address==0x20dc:return self.ids.pop(0) if len(self.ids)>1 else self.ids[0]
  return {0xcd8ce4:0x1000,0x1000:0xbeb630,0x2000:0xc4db60,0x2418:0x3000,0x2004:0x4000,0x4008:0x19ab11af,0x3000:0xc5bce0,0x3020:3}.get(address,0)
 def read(self,address,size):
  self.calls.append((address,size));assert (address,size)==(0x2080,28);return struct.pack('<7I',*self.words)

class GroundStatusTests(unittest.TestCase):
 def test_positive_ground_and_all_air_clear(self):
  r=grounded_status(Memory(),0x2000);self.assertTrue(r['ground_positive']);self.assertTrue(r['grounded_verified']);self.assertFalse(r['walkable_route_verified']);self.assertEqual(r['frame'],r['end_frame'])
 def test_absence_of_air_is_not_positive_ground(self):
  self.assertFalse(grounded_status(Memory([0]*7),0x2000)['grounded_verified'])
 def test_every_known_air_or_mobility_exclusion_blocks(self):
  for name,(record,index) in FLAGS.items():
   if name=='GROUND_LOCOMOTOR_ACTIVE':continue
   words=[0,0,0,0,0,1,0];words[index>>5]|=1<<(index&31);r=grounded_status(Memory(words),0x2000);self.assertFalse(r['grounded_verified'],name)
 def test_frame_or_identity_change_is_unknown_not_eligible(self):
  for attr,values in [('frames',[100,101]),('ids',[77,78])]:
   memory=Memory();setattr(memory,attr,values);r=grounded_status(memory,0x2000);self.assertEqual(r['status'],'unknown');self.assertFalse(r['grounded_verified'])
 def test_foreign_owner_never_reads_status_or_coordinates(self):
  memory=Memory();original=memory.u32;memory.u32=lambda a:4 if a==0x3020 else original(a);r=grounded_status(memory,0x2000);self.assertFalse(r['grounded_verified']);self.assertFalse(memory.calls)
 def test_actual_file_name_records_and_native_setter(self):
  proof=static_proof('E:/RedRar3/Data/RA3_1.12.game');self.assertEqual(len(proof['records']),8);self.assertEqual(next(e for e in proof['records'] if e['name']=='GROUND_LOCOMOTOR_ACTIVE')['native_enum'],160);self.assertEqual(proof['generic_setter']['address'],'0x7274c0')

if __name__=='__main__':unittest.main()
