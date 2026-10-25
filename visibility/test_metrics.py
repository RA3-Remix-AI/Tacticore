import unittest
from test_native_read import FakeMemory
from native_read import ShroudReader,vision_grid_snapshot
class VisionMetricTests(unittest.TestCase):
 def setUp(self):self.m=FakeMemory();self.g=ShroudReader(self.m)
 def test_no_enemy_object_memory_required(self):
  self.m.counter(1,1,3,1);metrics,bits,frontier=vision_grid_snapshot(self.m,self.g,3,20);self.assertEqual(metrics['clear_cell_count'],1);self.assertEqual(bits,frozenset({5}));self.assertTrue(frontier)
 def test_player_specific(self):self.m.counter(1,1,2,1);self.assertEqual(vision_grid_snapshot(self.m,self.g,3,20)[0]['clear_cell_count'],0)
 def test_border_blocks_metrics(self):self.m.counter(1,1,3,1);self.m.put(self.g.cells+5*0x34+0x32,b'\1');self.assertEqual(vision_grid_snapshot(self.m,self.g,3,20)[0]['clear_cell_count'],0)
 def test_frontiers_only_adjacent_fog(self):
  self.m.counter(1,1,3,1);_,bits,points=vision_grid_snapshot(self.m,self.g,3,20)
  for xyz in points.values():
   self.assertEqual(self.g.query(3,xyz),0)
   gx=int((xyz[0]-100)*.1);gy=int((xyz[1]-200)*.1);self.assertEqual(abs(gx-1)+abs(gy-1),1)
 def test_new_cells_set_difference(self):
  self.m.counter(1,1,3,1);old=vision_grid_snapshot(self.m,self.g,3,20)[1];self.m.counter(2,1,3,1);new=vision_grid_snapshot(self.m,self.g,3,21)[1];self.assertEqual(len(new-old),1)
 def test_unsupported_default_rejected(self):
  self.m.u(0xd074a4,2)
  with self.assertRaises(ValueError):ShroudReader(self.m)
if __name__=='__main__':unittest.main()
