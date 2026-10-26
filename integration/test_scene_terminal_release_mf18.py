"""MF18 namespace-only scene adapter fixtures, no process/Source authority."""
import copy
import ctypes
import unittest
from unittest.mock import patch
import test_scene_terminal_release_mf17 as base

R=base.module('test_mf18_scene_reader',base.ROOT/'tactical/mission-formation-v18/scene_terminal_release.py')

class Scene18(unittest.TestCase):
 def fixture(self):
  record,report,profile=base.Scene17().fixture()
  # Same ABI is independently loaded from the actual new family file. Fixture
  # byte adaptation is synthetic and confers no Source18 or SDK capability.
  L=base.module('test_mf18_scene_actual_layout',base.ROOT/'tactical/mission-formation-v18/native_layout.py')
  self.assertEqual(ctypes.sizeof(profile['Header']),ctypes.sizeof(L.Header));profile['Header']=L.Header
  for sample in record['snapshots']:
   h=L.Header.from_buffer_copy(bytes.fromhex(sample['header_before_hex']));h.magic=0x4d463138;h.version=18
   sample['header_before_hex']=sample['header_after_hex']=bytes(h).hex()
  report['native']=R.plain(h);report['native']['crumbs']=[[],[]];record.update(protocol=R.PROTOCOL,reader_sha256=R.sha(R.__file__))
  return record,report,profile
 def verify(self,record,report,profile):
  with patch.object(R,'source_profile',return_value=profile),patch.object(ctypes,'WinDLL',side_effect=AssertionError('no SDK/process access')):return R.verify(record,report,'b'*64)
 def test_exact_eighteen_scene_only_certificate_keeps_all_failure_flags(self):
  record,report,profile=self.fixture();result=self.verify(record,report,profile)
  self.assertTrue(result['control_release_verified']);self.assertEqual(result['protocol'],'mf18_scene_terminal_release_v1');self.assertEqual([a['object_id'] for a in result['actors']],[800,801])
  for flag in R.FALSE_FLAGS:self.assertIs(result[flag],False)
 def test_old_family_and_success_or_unknown_exit_cannot_claim_eighteen_scene(self):
  for change in ('old_protocol','old_magic','old_reader','host0','host_unknown','cleanup52','live_scene'):
   record,report,profile=self.fixture()
   if change=='old_protocol':record['protocol']=base.R.PROTOCOL
   if change=='old_reader':record['reader_sha256']=base.R.sha(base.R.__file__)
   if change=='old_magic':report['native']['magic']=0x4d463137
   if change=='host0':report['host_exit']=0
   if change=='host_unknown':report['host_exit']=None
   if change=='cleanup52':report['native']['error']=52
   if change=='live_scene':record['snapshots'][0]['scene_before']['frame']=100
   with self.subTest(change=change):self.assertFalse(self.verify(record,report,profile)['control_release_verified'])
 def test_no_source_pins_never_promotes_cached_header_or_claims(self):
  record,report,profile=self.fixture()
  with patch.object(R,'source_profile',side_effect=ValueError('unqualified actual Source18')):self.assertFalse(R.verify(record,report,'b'*64)['control_release_verified'])

if __name__=='__main__':unittest.main()
