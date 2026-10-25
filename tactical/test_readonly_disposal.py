import copy,json,unittest
from pathlib import Path
from readonly_disposal import eligibility,verify,trusted_entries,LAYOUT,COMBO_LAYOUT,COMBO_DLL
HERE=Path(__file__).resolve().parent
class DisposalTests(unittest.TestCase):
 def fixture(self):
  r=json.loads((HERE/'../acceptance/runs/20261025-010403-commander/ordered-ak03-static.json').read_text(encoding='utf-8'));r['native'].update(phase=4,error=32,return_calls=0,return_verified=0);r['events']=[e for e in r['events'] if e.get('tag')!=3];f=r['native']['issued_frame']+200
  state=dict(timer=0,phase=4,error=32,restore_mask=2047,active=0,shared_pointer='0x10000',module_base='0x20000',token=r['request']['token'],seq=r['request']['seq'],entries=[dict(x,actual=x['expected']) for x in trusted_entries()])
  state.update(pid=r['preflight']['pid'],thread=r['preflight']['window_thread'],session_id=r['session_id'],commander_id=r['preflight']['commander_id'],command_id=r['request']['command_id'],task_id=r['request']['task_id'],object_id=r['preflight']['selected']['object_id'],type_hash=r['preflight']['selected']['type_hash'],owner=r['preflight']['owner'])
  e=dict(source_sha256='source',session_id=r['session_id'],pid=r['preflight']['pid'],layout=LAYOUT,completed=False,goal_observed=False,return_verified=False,inert_snapshots=[copy.deepcopy(state),copy.deepcopy(state)],scans=[dict(complete=True,logic=r['preflight']['logic'],frame=x,end_frame=x,ids=[1,2,3],count=3) for x in [f,f+2]])
  return r,e
 def check(self,r,e):return verify(e,r,'source')['restoration_verified']
 def test_failed_actor_can_release_but_never_return_or_complete(self):
  r,e=self.fixture();a=verify(e,r,'source');self.assertTrue(a['restoration_verified']);self.assertFalse(a['return_verified']);self.assertFalse(a['completion_claim'])
 def test_live_actor(self):
  r,e=self.fixture();e['scans'][1]['ids'][0]=r['preflight']['selected']['object_id'];self.assertFalse(self.check(r,e))
 def test_same_frame(self):
  r,e=self.fixture();e['scans'][1]=copy.deepcopy(e['scans'][0]);self.assertFalse(self.check(r,e))
 def test_scan_crosses_frame(self):
  r,e=self.fixture();e['scans'][0]['end_frame']+=1;self.assertFalse(self.check(r,e))
 def test_forged_entry_expected(self):
  r,e=self.fixture();e['inert_snapshots'][0]['entries'][0].update(expected='90',actual='90');self.assertFalse(self.check(r,e))
 def test_repeated_entry(self):
  r,e=self.fixture();e['inert_snapshots'][0]['entries']=[e['inert_snapshots'][0]['entries'][0]]*11;self.assertFalse(self.check(r,e))
 def test_live_timer(self):
  r,e=self.fixture();e['inert_snapshots'][1]['timer']=1;self.assertFalse(self.check(r,e))
 def test_source_drift(self):
  r,e=self.fixture();e['source_sha256']='other';self.assertFalse(self.check(r,e))
 def test_native_mapping_rearmed(self):
  r,e=self.fixture();e['inert_snapshots'][1]['token']+=1;self.assertFalse(self.check(r,e))
 def test_active_callback(self):
  r,e=self.fixture();r['native']['active']=1;self.assertFalse(self.check(r,e))
 def test_already_normal_return_not_disposed(self):
  r,e=self.fixture();r['native']['return_verified']=1;self.assertFalse(eligibility(r))
 def test_combo_requires_its_own_twelve_entry_layout(self):
  r,e=self.fixture();r['native_binary_sha256']=COMBO_DLL;r['native']['restore_mask']=4095;e['layout']=COMBO_LAYOUT
  for s in e['inert_snapshots']:s.update(restore_mask=4095,entries=[dict(x,actual=x['expected']) for x in trusted_entries(r)])
  self.assertTrue(self.check(r,e));self.assertEqual(len(e['inert_snapshots'][0]['entries']),12)
 def test_combo_cannot_reuse_legacy_eleven_entries(self):
  r,e=self.fixture();r['native_binary_sha256']=COMBO_DLL;r['native']['restore_mask']=4095;e['layout']=COMBO_LAYOUT
  for s in e['inert_snapshots']:s['restore_mask']=4095
  self.assertFalse(self.check(r,e))
if __name__=='__main__':unittest.main()
