import struct
import unittest
from heightmap import HeightMapReader
from compare_native import native_reference
from test_heightmap import Memory

class References(unittest.TestCase):
    def fixture(self,z=210):
        m=Memory()
        for address,value in ((0x50000,0xc4db60),(0x500dc,55),(0x50004,0x80000),(0x80008,0x19ab11af),
            (0x50418,0x60000),(0x50374,0x70000),(0x70000,0xc48670),(0x70024,0xc48528),
            (0x70008,0x50000),(0x50414,0xa0000),(0xa0004,0xa1000),(0xa1008,0x60000),
            (0x5033c,0x90000),(0x50238,0),(0x50048,4)):
            m.put(address,struct.pack('<I',value))
        m.put(0x50038,struct.pack('<3f',2.5,7.5,z));m.put(0x5005c,struct.pack('<f',0))
        m.put(0x90004,struct.pack('<f',100));m.put(0x50080,bytes(28))
        row=dict(address='0x50000',owner_address='0x60000',ai_address='0x70000',object_id=55,type_hash='0x19ab11af',xyz=(2.5,7.5,float(z)))
        return m,row
    def test_same_frame_owned_native_reference_agrees_but_never_grants_walkability(self):
        m,row=self.fixture();value=native_reference(m,row,100,HeightMapReader(m))
        self.assertTrue(value['height_agrees']);self.assertEqual(0,value['base_height_delta'])
        self.assertFalse(value['walkability_verified']);self.assertFalse(value['ground_target_permission_granted'])
    def test_different_surface_is_retained_as_a_mismatch(self):
        m,row=self.fixture(220);value=native_reference(m,row,100,HeightMapReader(m))
        self.assertFalse(value['height_agrees']);self.assertEqual(-10,value['base_height_delta'])
    def test_wrong_identity_cache_and_cross_frame_are_rejected(self):
        for address,value in ((0x50418,0x99999),(0x50048,1),(0x10050,101)):
            m,row=self.fixture();m.put(address,struct.pack('<I',value))
            with self.assertRaises(ValueError):native_reference(m,row,100,HeightMapReader(m))

if __name__=='__main__':unittest.main()
