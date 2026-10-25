"""Static ABI and generated-structure checks; never attaches to a game."""
import ctypes as c,hashlib,importlib.util,json,re,subprocess,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('combo_test',HERE/'ordered-combo/lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ComboBuildTests(unittest.TestCase):
 def test_layout(self):
  actual=json.loads(subprocess.check_output([str(HERE/'ordered-combo/bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(actual,dict(event=c.sizeof(m.Event),tactical=c.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0))
 def test_message_change_did_not_change_thing_aiupdate_offset(self):
  source=(HERE/'ordered-combo/lease.cpp').read_text(encoding='utf-8');header=(HERE/'ordered-combo/shared.h').read_text(encoding='utf-8');self.assertIn('word(p->unit+0x374)==p->update',source);self.assertNotIn('p->unit+0x378',source);self.assertIn('(WM_APP+0x378)',header)
 def test_ordinary_button_and_attack_arguments(self):
  source=(HERE/'ordered-combo/lease.cpp').read_text(encoding='utf-8');self.assertIn('((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0)',source);self.assertIn('((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1)',source);self.assertIn('issue_stop(4)',source);self.assertIn('p->lease_stage==3',source);self.assertIn('now-p->toggle_frame>=15&&idle',source)
 def test_legacy_attack_binary_unchanged(self):self.assertEqual(hashlib.sha256((HERE/'ordered-attack/bin/TacticalOrderedAttack.dll').read_bytes()).hexdigest(),'9c898e61651698fd04412c914b6a4c577dea941a20c6af31a88b38b9457af142')
 def test_real_ctypes_event_capture_serializes_all_arrays(self):
  shared=m.Tactical();shared.count=1;shared.events[0].seq=1;shared.events[0].requested[:]=[float('nan'),0.,0.];r={};m.capture_shared(r,shared);json.dumps(r,allow_nan=False);self.assertIsNone(r['events'][0]['requested'][0]);self.assertIn('active_weapon_asset',r['events'][0]);self.assertIn('toggle_calls',r['native'])
 def test_exact_hook_signatures_match_pinned_executable(self):
  from readonly_disposal import pe_bytes,EXE
  exe=Path('E:/RedRar3/Data/RA3_1.12.game');self.assertEqual(hashlib.sha256(exe.read_bytes()).hexdigest(),EXE);source=(HERE/'ordered-combo/lease.cpp').read_text(encoding='utf-8');hooks=re.findall(r'\{(0x[0-9a-f]+),\(void\*\)[^,]+,\(void\*\*\)&[^,]+,"([^\"]+)",(\d+),',source);self.assertEqual(len(hooks),12)
  for address,literal,length in hooks:self.assertEqual(pe_bytes(exe,int(address,0),int(length)),bytes.fromhex(literal.replace('\\x','')))
if __name__=='__main__':unittest.main()
