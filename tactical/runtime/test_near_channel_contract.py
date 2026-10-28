"""Build the isolated actual channel and compare its executable ABI to ctypes."""
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from tactical.runtime import near_layout as n

ROOT=Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name=='nt'and shutil.which('pwsh'),'Windows native channel toolchain unavailable')
class NearChannelContract(unittest.TestCase):
    def test_frozen_channel_build_real_layout_and_transport_checks(self):
        sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='tacticore-near-channel2-')as temporary:
            output=Path(temporary)/'build'
            run=subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(ROOT/'tactical/runtime/build_near_channel.ps1'),
                                '-OutputDirectory',str(output)],capture_output=True,text=True,encoding='utf-8',timeout=120)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            m=json.loads((output/'manifest.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(m['layout'],n.inventory());self.assertEqual(m['transport_groups'],6)
            actual=subprocess.check_output([str(output/'near_runtime_host.exe'),'--layout'],text=True)
            self.assertEqual(json.loads(actual),n.inventory())
            self.assertEqual(c.sizeof(n.Shared),2228168);self.assertEqual(c.sizeof(n.Observation),672)
            self.assertEqual(c.sizeof(n.WireCombatEvent),1160);self.assertEqual(c.sizeof(n.Damage),328)
            self.assertEqual(m['native_host_hard_ms'],180000);self.assertEqual(m['expected_restore_mask'],32767)
            self.assertTrue(m['active_v1_unchanged']);self.assertTrue(m['native_wire_abi_defined'])
            for flag in ['game_process_opened','hooks_installed','field_verified','capability_granted','full_goal_complete']:
                self.assertFalse(m[flag])
            self.assertEqual(m['game_sdk_calls'],0)
            for row in m['sources']:
                self.assertEqual(sha(output/'source'/row['file']),row['sha256'])
                self.assertEqual(sha(ROOT/row['file']),row['sha256'])
            for row in m['outputs']:
                self.assertEqual(sha(output/row['file']),row['sha256'])


if __name__=='__main__':unittest.main()
