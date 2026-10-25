import copy
import struct
import unittest
from own_actor_timeline import sample

class Memory:
 def __init__(self):
  self.words={0xcd8ce4:0x80000,0x80050:100,0x10000:0xc4db60,0x100dc:7,0x10418:0x20000,0x10004:0x30000,0x30008:0x19ab11af,0x10374:0x40000,0x1033c:0x50000,0x40008:0x10000,0x4003c:0x60000,0x60004:0x70000,0x70004:77,0x70000:0xc54900,0x60078:0,0x10414:0x90000,0x10238:0xa0000,0x40150:0,0x40050:0}
  self.hp_reads=0;self.hp=100.
 def u32(self,address):return self.words[address]
 def f32(self,address):
  assert address==0x50004
  self.hp_reads+=1;return self.hp
 def read(self,address,size):
  if address==0x10038:return struct.pack('<3f',10.,20.,210.)
  if address==0x10080:return struct.pack('<7I',0,1<<29,0,0,0,0,0)
  raise ValueError('unmapped')

class OwnRoster(unittest.TestCase):
 def own(self):return dict(frame_start=100,frame_end=100,candidates=[dict(address='0x10000',owner_address='0x20000',object_id=7,type_hash='0x19ab11af')])
 def test_garrison_and_low_health_are_recorded_without_becoming_borrowable(self):
  memory=Memory();memory.hp=12.
  result=sample(memory,self.own());self.assertTrue(result['atomic']);row=result['rows'][0]
  self.assertTrue(row['garrison_flag']);self.assertEqual(row['hp'],12.)
  self.assertEqual(row['holder'],0xa0000);self.assertFalse(row['borrow_authorized'])
 def test_lost_ownership_never_reads_body_hp_or_classifies_death(self):
  memory=Memory();memory.words[0x10418]=0x22220
  result=sample(memory,self.own());self.assertEqual(memory.hp_reads,0)
  self.assertEqual(result['rows'][0]['sample_status'],'unknown');self.assertNotIn('hp',result['rows'][0])
 def test_absent_actor_does_not_follow_saved_pointer(self):
  memory=Memory();own=self.own();own['candidates']=[]
  result=sample(memory,own);self.assertEqual(result['rows'],[]);self.assertEqual(memory.hp_reads,0)
  self.assertIn('never_death_proof',result['missing_actor_means'])
 def test_mixed_frame_never_publishes_roster_facts(self):
  memory=Memory();memory.words[0x80050]=101
  result=sample(memory,self.own());self.assertFalse(result['atomic']);self.assertEqual(result['rows'],[])

if __name__=='__main__':unittest.main()
