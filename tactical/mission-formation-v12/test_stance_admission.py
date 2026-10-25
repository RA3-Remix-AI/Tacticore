"""Actual enum-list/back-reference parsing, including unsafe live transitions."""
import struct,unittest
import stance_admission as reader

class Memory:
 def __init__(self):
  self.values={0x10000+0x380:0x20000,0x20000:0xc37f90,0x20004:0x30000,0x20008:0x10000,0x20038:0,0x30008:0x40000,0x40000:0x50000,0x50004:4,0x50008:0x60000,0xc37f98:0x71d3f0};self.entries=[1,0,0,0,2,0,3,0]
 def u32(self,addr):return self.values[addr]
 def read(self,addr,size):
  if addr==0x71d3f0:return bytes.fromhex('b84c7ec000c3')[:size]
  if addr==0x60000:return struct.pack('<8I',*self.entries)[:size]
  raise ValueError('Unmapped read')

class ActualStanceAdmission(unittest.TestCase):
 def test_normal_definition_order_is_preserved_and_capture_is_read_only(self):
  r=reader.inspect_stance(Memory(),0x10000)
  self.assertEqual(r['definition_entries'],[1,0,0,0,2,0,3,0]);self.assertFalse(r['mutations'])
 def test_bad_module_owner_enum_and_definition_capacity_are_rejected(self):
  for address,value in ((0x20000,0xc37f94),(0x20008,0x10004),(0x20038,2),(0x50004,5)):
   memory=Memory();memory.values[address]=value
   with self.assertRaises(ValueError):reader.inspect_stance(memory,0x10000)
 def test_duplicate_enum_or_missing_hold_is_not_an_allowed_definition(self):
  for entries in ([1,0,0,0,1,0,3,0],[1,0,0,0,3,0,4,0]):
   memory=Memory();memory.entries=entries
   with self.assertRaises(ValueError):reader.inspect_stance(memory,0x10000)

if __name__=='__main__':unittest.main()
