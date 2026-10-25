import ctypes as c,importlib.util,struct,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('rsv6_team_capture',Path(__file__).with_name('lease.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Capture(unittest.TestCase):
 def test_published_team_event_preserves_all_actual_tail_bytes(self):
  shared=m.Probe();shared.count=1;e=shared.events[0];e.seq=1;e.kind=73;e.frame=101
  words=(0x544d5034,0x5000,0x6000,0x3000,0x5000,0x6000,0x3000,101,0x4900,2);raw=struct.pack('<10I',*words)
  c.memmove(c.addressof(e.move),raw,40);r={};m.capture(r,shared);row=r['events'][0]
  self.assertEqual(row['team_proof_raw_hex'],raw.hex());self.assertEqual(row['team_proof']['previous_cohort_count'],2);self.assertEqual(row['team_proof']['actor_team_before'],0x5000)
 def test_normal_move_event_does_not_fabricate_team_evidence(self):
  shared=m.Probe();shared.count=1;e=shared.events[0];e.seq=1;e.kind=66;r={};m.capture(r,shared);self.assertNotIn('team_proof',r['events'][0])
if __name__=='__main__':unittest.main()
