"""Compile/replay the actual C++ feature in x86/x64; never load a game DLL."""
import hashlib,json,os,shutil,struct,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=Path(__file__).resolve().parent

@unittest.skipUnless(os.name=='nt'and shutil.which('pwsh')and(ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe').is_file(),
                     'Windows fixed-toolchain replay is unavailable; no field authority')
class NearCombatNativeReplay(unittest.TestCase):
    def test_actual_win32_observer_links_and_denies_before_install(self):
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        manifest=json.loads((RUNTIME/'bin/build-manifest.json').read_text(encoding='utf-8-sig'))
        before={row['file']:sha(RUNTIME/'bin'/row['file'])for row in manifest['outputs']}
        tmp=tempfile.TemporaryDirectory(prefix='tacticore-near-native-');owned=Path(tmp.name).resolve()
        self.assertTrue(owned.is_relative_to(Path(tempfile.gettempdir()).resolve()));self.addCleanup(tmp.cleanup)
        output=owned/'native'
        process=subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(RUNTIME/'build_near_native_development.ps1'),'-OutputDirectory',str(output)],
                               capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(process.returncode,0,process.stdout+'\n'+process.stderr)
        report=json.loads((output/'manifest.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(report['offline_native_boundary_groups'],5);self.assertEqual(report['expected_hook_count'],15)
        self.assertEqual(report['regression_test_suites'],51)
        self.assertEqual(report['expected_restore_mask'],32767)
        for flag in ['game_process_opened','hooks_installed','published_wire_abi','field_verified','capability_granted','full_goal_complete']:self.assertFalse(report[flag])
        self.assertEqual(report['game_sdk_calls'],0);self.assertEqual(report['default_admission'],'deny')
        for row in report['sources']:
            self.assertEqual(sha(output/'source'/row['file']),row['sha256']);self.assertEqual(sha(ROOT/row['file']),row['sha256'])
        for row in report['outputs']:self.assertEqual(sha(output/row['file']),row['sha256'])
        executable=output/'test_near_native_boundary.exe';raw=executable.read_bytes();offset=struct.unpack_from('<I',raw,0x3c)[0]
        self.assertEqual(raw[offset:offset+4],b'PE\0\0');self.assertEqual(struct.unpack_from('<H',raw,offset+4)[0],0x14c)
        replay=subprocess.run([str(executable)],capture_output=True,text=True,timeout=30)
        self.assertEqual(replay.returncode,0,replay.stderr);self.assertEqual(replay.stdout.strip(),report['result'])
        replay=subprocess.run([str(output/'test_near_move_regression.exe')],capture_output=True,text=True,timeout=30)
        self.assertEqual(replay.returncode,0,replay.stderr);self.assertEqual(replay.stdout.strip(),report['regression_result'])
        self.assertTrue(json.loads(replay.stdout)['passed']);self.assertFalse(json.loads(replay.stdout)['game_access'])
        for row in manifest['inputs']:self.assertEqual(sha(RUNTIME/row['file']),row['sha256'])
        self.assertEqual(before,{row['file']:sha(RUNTIME/'bin'/row['file'])for row in manifest['outputs']})

    def test_frozen_actual_cpp_x86_x64_and_current_v1_build_are_separate(self):
        manifest=json.loads((RUNTIME/'bin/build-manifest.json').read_text(encoding='utf-8-sig'))
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        before={row['file']:sha(RUNTIME/'bin'/row['file'])for row in manifest['outputs']}
        tmp=tempfile.TemporaryDirectory(prefix='tacticore-near-combat-')
        owned=Path(tmp.name).resolve();self.assertTrue(owned.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.addCleanup(tmp.cleanup);output=owned/'replay'
        process=subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(RUNTIME/'build_near_combat_offline.ps1'),'-OutputDirectory',str(output)],
            capture_output=True,text=True,encoding='utf-8',timeout=90)
        self.assertEqual(process.returncode,0,process.stdout+'\n'+process.stderr)
        report=json.loads((output/'manifest.json').read_text(encoding='utf-8-sig'))
        self.assertEqual((report['unique_groups'],len(report['outputs'])),(64,10))
        self.assertFalse(report['field_verified']);self.assertFalse(report['capability_granted']);self.assertEqual(report['native_game_calls'],0)
        for row in report['sources']:
            path=output/'source'/row['file'];self.assertEqual(sha(path),row['sha256']);self.assertEqual(sha(ROOT/row['file']),row['sha256'])
        for row in report['outputs']:
            path=output/row['file'];self.assertEqual(sha(path),row['sha256'])
            raw=path.read_bytes();offset=struct.unpack_from('<I',raw,0x3c)[0]
            self.assertEqual(raw[offset:offset+4],b'PE\0\0')
            self.assertEqual(struct.unpack_from('<H',raw,offset+4)[0],0x14c if row['architecture']=='x86'else 0x8664)
            self.assertIn('fake',row['result'])
        for row in manifest['inputs']:self.assertEqual(sha(RUNTIME/row['file']),row['sha256'])
        self.assertEqual(before,{row['file']:sha(RUNTIME/'bin'/row['file'])for row in manifest['outputs']})

if __name__=='__main__':unittest.main()
