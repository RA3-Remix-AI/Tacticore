import struct,unittest
from test_native_read import FakeMemory
from native_read import ShroudReader,object_footprint_status
class FootprintTests(unittest.TestCase):
 def setUp(self):
  self.m=FakeMemory();self.g=ShroudReader(self.m);self.thing=0x130000;self.record=0x140000;self.refs=0x150000
  for p,v in [(self.thing+0x9c,self.record),(self.record,self.g.impl),(self.record+0x1c,self.refs),(self.record+0x20,2),(self.refs,self.g.cells),(self.refs+16,self.g.cells+0x34)]:self.m.u(p,v)
  self.m.put(self.record+0xf8,b'\0\0');self.m.counter(0,0,3,1);self.m.counter(1,0,3,1)
 def status(self):return object_footprint_status(self.m,self.thing,3,self.g)
 def test_full_clear(self):self.assertEqual(self.status(),1)
 def test_center_clear_neighbor_fog_is_not_visible(self):self.m.counter(1,0,3,0);self.assertEqual(self.g.query(3,(105,205)),1);self.assertEqual(self.status(),2)
 def test_all_fog(self):self.m.counter(0,0,3,0);self.m.counter(1,0,3,0);self.assertEqual(self.status(),3)
 def test_all_shroud(self):self.m.counter(0,0,3,0xffff);self.m.counter(1,0,3,0xffff);self.assertEqual(self.status(),4)
 def test_all_unknown_cells(self):self.m.u(self.refs,0);self.m.u(self.refs+16,0);self.assertEqual(self.status(),4)
 def test_empty_footprint(self):self.m.u(self.record+0x20,0);self.assertEqual(self.status(),4)
 def test_f9_blocks_clear(self):self.m.put(self.record+0xf9,b'\1');self.assertEqual(self.status(),2)
 def test_pending_geometry_is_unknown(self):self.m.put(self.record+0xf8,b'\1');self.assertIsNone(self.status())
 def test_missing_record_does_not_unshroud(self):self.m.u(self.thing+0x9c,0);self.assertIsNone(self.status())
 def test_wrong_grid_rejected(self):
  self.m.u(self.record,0x999000)
  with self.assertRaises(ValueError):self.status()
 def test_outside_cell_rejected(self):
  self.m.u(self.refs,0x999000)
  with self.assertRaises(ValueError):self.status()
 def test_player_specific(self):self.assertEqual(object_footprint_status(self.m,self.thing,4,self.g),3)
 def test_border_cell_blocks_full_visibility(self):self.m.put(self.g.cells+0x32,b'\1');self.assertEqual(self.status(),2)
if __name__=='__main__':unittest.main()
