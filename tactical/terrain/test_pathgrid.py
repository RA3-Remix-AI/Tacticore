import struct
import unittest
from test_heightmap import Memory
from pathgrid import PathGridReader,PREFIX_COORD,PREFIX_CELL,SCALE_BITS


class Cells(unittest.TestCase):
    def memory(self):
        m=Memory()
        for address,value in ((0xce3e30,0x20000),(0x20000,0xc18e20),(0x20028,0x30000),
                (0x30008,1),(0x3000c,0),(0x30010,0),(0x30014,20),(0x30018,20),
                (0x30004,0x40000),(0x40004,0x50000),(0xcb11f4,SCALE_BITS)):
            m.put(address,struct.pack('<I',value))
        m.put(0x68d010,PREFIX_COORD);m.put(0x544720,PREFIX_CELL)
        m.put(0x50000+48*2,struct.pack('<12I',0,1,2,7,*([0]*8)))
        return m
    def test_native_column_major_stride_and_raw_code_are_not_permissions(self):
        result=PathGridReader(self.memory()).sample(30,50)
        self.assertEqual((1,2,'0x50060'),(result['column'],result['row'],result['cell']))
        self.assertEqual(7,result['raw_terrain_nibble']);self.assertEqual(1,result['layer'])
        self.assertFalse(result['walkability_verified']);self.assertFalse(result['ground_target_permission_granted'])
    def test_scene_layout_and_outside_coordinates_are_refused(self):
        for address,value in ((0x10050,0),(0x20000,0),(0x30008,0),(0x30014,8192),(0xcb11f4,1)):
            m=self.memory();m.put(address,struct.pack('<I',value))
            with self.assertRaises(ValueError):PathGridReader(m).sample(30,50)
        for xy in ((-1,0),(1000,0),(float('nan'),0)):
            with self.assertRaises(ValueError):PathGridReader(self.memory()).sample(*xy)
    def test_changed_cells_and_column_pointers_are_rejected(self):
        for mode in ('cell','column'):
            m=self.memory();reads=0
            def mutate(address,size):
                nonlocal reads
                if address==0x50060:
                    reads+=1
                    if reads==2:m.put(0x50060 if mode=='cell' else 0x40004,struct.pack('<I',123))
            m.mutate=mutate
            with self.assertRaisesRegex(ValueError,'snapshot_changed'):PathGridReader(m).sample(30,50)


if __name__=='__main__':unittest.main()
