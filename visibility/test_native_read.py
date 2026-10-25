import struct,unittest
from native_read import ShroudReader
class FakeMemory:
 def __init__(self):
  self.data={};self.u(0xce2fa0,0x100000);self.u(0x100000,0xc6aefc);self.u(0x100028,0x110000)
  self.put(0x110004,bytes(0x44));self.put(0x110004,struct.pack('<ff',100.,200.));self.put(0x110038,struct.pack('<fIII',.1,4,3,0x120000));self.u(0xd074a4,3);self.put(0x120000,bytes(12*0x34))
 def put(self,p,b):self.data.update({p+i:x for i,x in enumerate(b)})
 def read(self,p,n):return bytes(self.data[p+i] for i in range(n))
 def u(self,p,x):self.put(p,struct.pack('<I',x))
 def f32(self,p):return struct.unpack('<f',self.read(p,4))[0]
 def u32(self,p):return struct.unpack('<I',self.read(p,4))[0]
 def counter(self,x,y,player,value):self.put(0x120000+(y*4+x)*0x34+4+2*player,struct.pack('<H',value))
class ShroudTests(unittest.TestCase):
 def setUp(self):self.m=FakeMemory();self.g=ShroudReader(self.m)
 def test_fog(self):self.assertEqual(self.g.query(3,(105,205)),0)
 def test_clear(self):self.m.counter(0,0,3,2);self.assertEqual(self.g.query(3,(105,205)),1)
 def test_player_specific(self):self.m.counter(0,0,2,5);self.assertEqual(self.g.query(3,(105,205)),0);self.assertEqual(self.g.query(2,(105,205)),1)
 def test_shrouded_sentinel(self):self.m.counter(0,0,3,0xffff);self.assertEqual(self.g.query(3,(105,205)),3)
 def test_fogged_sentinel(self):self.m.u(0xd074a4,0);self.g=ShroudReader(self.m);self.m.counter(0,0,3,0xffff);self.assertEqual(self.g.query(3,(105,205)),0)
 def test_border_blocks_clear(self):self.m.counter(0,0,3,9);self.m.put(0x120032,b'\1');self.assertEqual(self.g.query(3,(105,205)),3)
 def test_xy_row_major(self):self.m.counter(2,1,3,1);self.assertEqual(self.g.query(3,(125,215)),1);self.assertEqual(self.g.query(3,(115,225)),0)
 def test_out_of_bounds(self):self.assertEqual(self.g.query(3,(150,250)),3)
 def test_native_truncation(self):self.m.counter(0,0,3,1);self.assertEqual(self.g.query(3,(99,205)),1) # native truncates -0.1 -> 0
 def test_nonfinite(self):
  with self.assertRaises(ValueError):self.g.query(3,(float('nan'),205))
 def test_invalid_player(self):
  with self.assertRaises(ValueError):self.g.query(20,(105,205))
 def test_reject_wrong_vtable(self):
  self.m.u(0x100000,0)
  with self.assertRaises(ValueError):ShroudReader(self.m)
 def test_lifecycle_changed(self):self.m.u(0x100028,0x180000);self.assertFalse(self.g.stable())
 def test_dynamic_list_not_grid_metadata(self):self.m.u(0x110048,0x888888);self.assertTrue(self.g.stable())
if __name__=='__main__':unittest.main()
