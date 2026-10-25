import unittest
from inspect_own_weapons import active_weapon
class Memory:
 def __init__(self):self.d={0x1000:0xc4db60,0x10dc:77,0x1418:0x2000,0x137c:0x3000,0x3008:0x1000,0x3024:0x4000,0x3028:0x4004,0x4000:0x5000,0x5000:0xc3a6e0,0xc3a704:0x6dbe80,0xc3a708:0x6f88e0,0x5014:0,0x5094:0x6000,0x6000:0x7000,0x7000:0xc2e324,0x7008:0x5000,0x7004:0x8000,0x8004:0x9000,0x9000:0xa000,0xa000:0x94d4d96e,0xa004:0x447ea26e,0x701c:3}
 def u32(self,a):return self.d[a]
class WeaponReadTests(unittest.TestCase):
 def test_current_ak_read_no_calls(self):self.assertEqual(active_weapon(Memory(),0x1000)['selected']['template_id'],'0x447ea26e')
 def test_none_index_five(self):
  m=Memory();m.d[0x5014]=5;self.assertIsNone(active_weapon(m,0x1000)['selected'])
 def test_unknown_slot_getter(self):
  m=Memory();m.d[0xc3a704]=0
  with self.assertRaises(ValueError):active_weapon(m,0x1000)
 def test_entry_backpointer_mismatch(self):
  m=Memory();m.d[0x7008]=0x5004
  with self.assertRaises(ValueError):active_weapon(m,0x1000)
if __name__=='__main__':unittest.main()
