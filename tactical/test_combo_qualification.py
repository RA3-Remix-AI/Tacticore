"""Synthetic protocol tests joined to an archived real damage packet, never field evidence."""
import copy,json,unittest
from pathlib import Path
import combo_qualification as q
HERE=Path(__file__).resolve().parent
class ComboQualificationTests(unittest.TestCase):
 def fixture(self):
  base=HERE/'../acceptance/runs/20261025-010403-commander';r=json.loads((base/'ordered-ak03-static.json').read_text(encoding='utf-8'));binding=json.loads((base/'ordered-ak03-template.json').read_text(encoding='utf-8'));g=copy.deepcopy(next(e for e in r['events'] if e['kind']==37));cut=g['seq'];first=[copy.deepcopy(e) for e in r['events'] if e['seq']<=cut];later=[copy.deepcopy(e) for e in r['events'] if e['seq']>cut]
  prep=[dict(g,kind=42,lease_stage=0,active_weapon_asset=q.AK)]
  for kind in [30,32,33,31,36]:prep.append(dict(g,kind=kind,tag=4,arg=1,caller=0x787791 if kind in [32,33] else 0,lease_stage=4))
  for frame in [2702,2703,2704]:prep.append(dict(g,kind=3,frame=frame,tag=0,lease_stage=4))
  prep.append(dict(g,kind=43,frame=2704,lease_stage=4))
  for e in later:e['frame']+=3
  r['events']=first+prep+later
  for i,e in enumerate(r['events']):e.update(seq=i+1,tick=e['frame']*60,active_weapon_asset=q.AK,active_weapon_entry=r['native']['weapon_entry'],active_weapon_ammo=3,status84=0)
  r['native'].update(stop_calls=3,private_stop_calls=3,total_private_stops=3,restore_mask=4095,attack_issued_frame=2704,returned_frame=2725,button=0xed06298,button_schema=0xed06340,toggle_calls=0,toggle_hook_calls=0,initial_weapon_asset=q.AK,prepare_gate_frame=2701,prepare_reconstituted_stops=0)
  r['request']['button']=dict(command_set_hash='0xb74cf71a',toggle=dict(entry='0xed06298',schema='0xed06340',asset_id='0x5977a798',asset_type='0x7d464170'));r.update(native_binary_sha256=q.DLL,native_host_sha256=q.HOST)
  return r,binding
 def test_direct_ak_prepare_protocol(self):
  r,b=self.fixture();a=q.qualify(r,b);self.assertEqual(a['status'],'bounded_ak_ordered_attack_verified',a['checks'])
 def test_old_binary_cannot_claim_new_scope(self):
  r,b=self.fixture();r['native_binary_sha256']='9c898e61651698fd04412c914b6a4c577dea941a20c6af31a88b38b9457af142';self.assertEqual(q.qualify(r,b)['status'],'not_passed')
 def test_post_prepare_stop_gate_required(self):
  r,b=self.fixture();next(e for e in r['events'] if e['kind']==43)['state_id']=96;self.assertEqual(q.qualify(r,b)['status'],'not_passed')
 def test_unbound_reconstituted_stop_after_prepare_is_rejected(self):
  r,b=self.fixture();e=copy.deepcopy(next(e for e in r['events'] if e['kind']==33 and e['lease_stage']==4));e['tag']=0;r['events'].insert(40,e)
  for i,row in enumerate(r['events']):row['seq']=i+1
  self.assertEqual(q.qualify(r,b)['status'],'not_passed')
if __name__=='__main__':unittest.main()
