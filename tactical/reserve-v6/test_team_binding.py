"""Current owned team must be fresh, stable, and proven through its owner chain."""
import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('rsv6_team_preflight',Path(__file__).with_name('preflight.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Memory:
 def __init__(self):self.words={0x1050:70,0x20dc:781,0x2418:0x3000,0x2374:0x4000,0x2414:0x5000,0x5000:0x9000,0x5004:0x6000,0x6000:0x9010,0x6008:0x3000}
 def u32(self,a):return self.words[a]
 def read(self,a,n):assert n==4;return self.u32(a).to_bytes(4,'little')
class Binding(unittest.TestCase):
 def sample(self,memory):return m.current_team_binding(memory,0x2000,0x3000,0x1000,781,0x4000,0x7000)
 def test_actual_fresh_team_replaces_no_descriptor_assertion(self):
  x=self.sample(Memory());self.assertEqual(x['team'],'0x5000');self.assertEqual(x['frame'],70);self.assertEqual(x['raw_before'],x['raw_after']);self.assertFalse(x['mutations'])
 def test_foreign_definition_owner_is_hard_failure(self):
  memory=Memory();memory.words[0x6008]=0x8000
  with self.assertRaisesRegex(ValueError,'team_owner_binding'):self.sample(memory)
 def test_actor_identity_is_hard_failure(self):
  for address in (0x20dc,0x2418,0x2374):
   with self.subTest(address=address):
    memory=Memory();memory.words[address]=1
    with self.assertRaisesRegex(ValueError,'team_owner_binding'):self.sample(memory)
 def test_script_null_unaligned_team_are_hard_failure(self):
  for team in (0,0x7000,0x5001):
   with self.subTest(team=team):
    memory=Memory();memory.words[0x2414]=team
    with self.assertRaisesRegex(ValueError,'team_not_native_owned'):self.sample(memory)
 def test_between_reads_change_is_transient_refusal(self):
  memory=Memory();original=memory.read;calls=0
  def read(a,n):
   nonlocal calls
   calls+=1
   if calls==10:memory.words[0x1050]=71
   return original(a,n)
  memory.read=read
  with self.assertRaisesRegex(ValueError,'team_snapshot_changed'):self.sample(memory)
if __name__=='__main__':unittest.main()
