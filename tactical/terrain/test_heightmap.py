"""Synthetic memory only; no native queries, processes, SDK or movement."""
import struct
import unittest
from heightmap import HeightMapReader,interpolate,PREFIX,XY_SCALE_BITS,HEIGHT_SCALE_BITS

class Memory:
    def __init__(self):
        self.data={};self.mutate=None
        for address,value in ((0xcd8ce4,0x10000),(0x10000,0xbeb630),(0x10050,100),
            (0xce9c40,0x20000),(0x20000,0xc0a6f0),(0xc0a744,0x8ed070),
            (0x20014,0x30000),(0x30024,8),(0x30028,8),(0x3002c,2),(0x30044,0x40000),
            (0xbe6670,XY_SCALE_BITS),(0xc0930c,HEIGHT_SCALE_BITS)):
            self.put(address,struct.pack('<I',value))
        self.put(0x8ed070,PREFIX)
        self.put(0x40000,struct.pack('<64H',*([5376]*64)))
    def put(self,address,value):
        self.data.update({address+i:v for i,v in enumerate(value)})
    def read(self,address,size):
        if self.mutate:self.mutate(address,size)
        try:return bytes(self.data[address+i] for i in range(size))
        except KeyError:raise OSError('missing native byte')
    def u32(self,address):return struct.unpack('<I',self.read(address,4))[0]

class Heights(unittest.TestCase):
    def test_scalar_triangles_follow_native_diagonal_and_scale(self):
        self.assertAlmostEqual(20*.0390625,interpolate([0,10,20,40],.25,.75))
        self.assertAlmostEqual(15*.0390625,interpolate([0,10,20,40],.75,.25))
        self.assertEqual(210,interpolate([5376]*4,0,0))
    def test_flat_grid_retains_original_four_words_without_permission(self):
        result=HeightMapReader(Memory()).sample(2.5,7.5)
        self.assertEqual([18,19,26,27],result['vertex_indices'])
        self.assertEqual([5376]*4,result['vertices']);self.assertEqual(210,result['base_height'])
        self.assertFalse(result['walkability_verified']);self.assertFalse(result['ground_target_permission_granted'])
    def test_inactive_missing_map_or_changed_function_are_refused(self):
        for address,value in ((0x10050,0),(0x20014,0),(0x20000,123),(0x30024,0),(0x30044,0),(0xbe6670,1)):
            memory=Memory();memory.put(address,struct.pack('<I',value))
            with self.assertRaises(ValueError):HeightMapReader(memory).sample(2.5,7.5)
    def test_outside_bounds_or_unreadable_vertices_never_return_zero_height(self):
        for xy in ((-1,0),(10000,10),(float('nan'),10)):
            with self.assertRaises(ValueError):HeightMapReader(Memory()).sample(*xy)
        memory=Memory();del memory.data[0x40000+2*18]
        with self.assertRaises(OSError):HeightMapReader(memory).sample(2.5,7.5)
    def test_frame_and_grid_changes_are_not_accepted_as_a_snapshot(self):
        for mode in ('frame','vertex'):
            memory=Memory();seen=0
            def mutate(address,size):
                nonlocal seen
                if address==0x40000+2*18:
                    seen+=1
                    if seen==2:memory.put(0x10050 if mode=='frame' else address,struct.pack('<I',101) if mode=='frame' else struct.pack('<H',123))
            memory.mutate=mutate
            with self.assertRaisesRegex(ValueError,'snapshot_changed'):HeightMapReader(memory).sample(2.5,7.5)

if __name__=='__main__':unittest.main()
