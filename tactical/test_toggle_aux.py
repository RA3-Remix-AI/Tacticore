import copy,ctypes as c,importlib.util,json,subprocess,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('toggle_aux_test',HERE/'toggle-aux/lease.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
class ToggleTests(unittest.TestCase):
 def fixture(self):
  r=json.loads((HERE/'../acceptance/runs/20261024-234355-commander/stop-move01.json').read_text(encoding='utf-8'));gate=next(e for e in r['events'] if e['kind']==24);prefix=[e for e in r['events'] if e['seq']<=gate['seq']];toggle=gate['frame'];end=toggle+19;sample=copy.deepcopy(next(e for e in prefix if e['kind']==3));pointer=0xed06298
  for kind,arg in [(32,pointer),(33,1),(30,0)]:prefix.append(dict(sample,kind=kind,arg=arg,tag=5,frame=toggle))
  for frame in [toggle+15,toggle+17,end]:prefix.append(dict(sample,kind=3,tag=0,frame=frame,weapon_asset=0x447ea26e,weapon_entry=2,status84=0))
  prefix.append(dict(sample,kind=31,tag=0,frame=end))
  prefix.extend(dict(e,frame=end) for e in r['events'] if e['tag']==3)
  for i,e in enumerate(prefix):e.update(seq=i+1,tick=e['frame']*60)
  r['events']=prefix;r['request'].update(button=dict(toggle=dict(entry=hex(pointer))),lease_frames=90);r['native'].update(restore_mask=255,move_calls=0,toggle_calls=1,toggle_hook_calls=1,toggle_frame=toggle,ak_samples=3,initial_weapon_asset=0x41872ecc,initial_weapon_entry=1,observed_weapon_asset=0x447ea26e,observed_weapon_entry=2,returned_frame=end)
  return r
 def test_complete_synthetic_protocol(self):self.assertEqual(t.assessment(self.fixture())['status'],'ordinary_weapon_toggle_and_return_verified')
 def test_repeated_same_frame_cannot_complete(self):
  r=self.fixture();rows=[e for e in r['events'] if e.get('weapon_asset')==0x447ea26e]
  for e in rows:e['frame']=rows[0]['frame']
  self.assertEqual(t.assessment(r)['status'],'not_passed')
 def test_final_mode_change_cannot_use_early_ak_samples(self):
  r=self.fixture();[e for e in r['events'] if e.get('weapon_asset')==0x447ea26e][-1]['weapon_asset']=0x41872ecc;self.assertEqual(t.assessment(r)['status'],'not_passed')
 def test_native_layout(self):
  actual=json.loads(subprocess.check_output([str(HERE/'toggle-aux/bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(actual,dict(event=c.sizeof(t.Event),tactical=c.sizeof(t.Tactical),events=t.Tactical.events.offset,unused1=0,unused2=0))
 def test_real_ctypes_event_arrays_and_nonfinite_diagnostic_are_json_safe(self):
  shared=t.Tactical();shared.count=1;e=shared.events[0];e.seq=1;e.requested[:]=[float('nan'),0.,float('inf')];e.effective[:]=[1.,2.,3.];r={};t.capture(r,shared);json.dumps(r,allow_nan=False);self.assertEqual(r['events'][0]['requested'],[None,0.,None]);self.assertEqual(r['events'][0]['effective'],[1.,2.,3.])
 def test_current_real_readiness_is_not_a_capability(self):
  r=json.loads((HERE/'toggle-aux/readiness-live022351.json').read_text(encoding='utf-8'));self.assertFalse(r['model_eligible']);self.assertEqual(r['initial_weapon']['selected']['template_id'],'0x41872ecc');self.assertEqual(r['request']['button']['toggle']['asset_id'],'0x5977a798');self.assertEqual(r['status'],'read_only_ready')
 def test_no_direct_status_ammo_slot_writes(self):
  source=(HERE/'toggle-aux/lease.cpp').read_text(encoding='utf-8');self.assertIn('((Button)0x790990)',source);self.assertNotIn('WriteProcessMemory',source);self.assertNotIn('*(uint32_t*)',source);self.assertIn('now-p->toggle_frame>=15',source)
if __name__=='__main__':unittest.main()
