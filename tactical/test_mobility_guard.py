import unittest
from mobility_guard import mobility_status
class Memory:
 def __init__(self,flags):self.flags=flags
 def u32(self,p):return {0x10000:0xc4db60,0x100dc:834,0x10418:0x20000,0x10084:self.flags}[p]
class MobilityTests(unittest.TestCase):
 def test_free(self):self.assertTrue(mobility_status(Memory(0),0x10000)['independently_movable'])
 def test_actual_garrison_word(self):
  a=mobility_status(Memory(0x20000000),0x10000);self.assertTrue(a['inside_garrison']);self.assertFalse(a['independently_movable'])
 def test_immobile(self):self.assertFalse(mobility_status(Memory(0x80000),0x10000)['independently_movable'])
 def test_unrelated_flags_do_not_make_immobile(self):self.assertTrue(mobility_status(Memory(0x8002000),0x10000)['independently_movable'])
if __name__=='__main__':unittest.main()
