import unittest,json
from pathlib import Path
from restoration import single_control_release
ROOT=Path(__file__).resolve().parent
class SingleReleaseTests(unittest.TestCase):
 def raw(self):return json.loads((ROOT/'../acceptance/runs/20261024-234355-commander/stop-move01.json').read_text(encoding='utf-8'))
 def disposed(self):
  r=self.raw();n=r['native'];f=n['returned_frame']+2;n.update(phase=4,error=32,return_calls=0,return_verified=0,disposed_verified=1,disposed_frame=f);r['events']=[e for e in r['events'] if e['tag']!=3];r['events'].append(dict(kind=39,arg=2,frame=f,thread=r['preflight']['window_thread']));r['disposal_scans']=[dict(complete=True,frame=frame,end_frame=frame,thread=r['preflight']['window_thread'],logic=r['preflight']['logic'],ids=[1,2,3],count=3) for frame in [f-1,f]];return r
 def test_real_normal_return(self):self.assertTrue(single_control_release(self.raw(),127)['return_verified'])
 def test_missing_body_id_twice_releases_without_false_return(self):
  a=single_control_release(self.disposed(),127);self.assertTrue(a['control_release_verified']);self.assertTrue(a['disposed_verified']);self.assertFalse(a['return_verified']);self.assertFalse(a['completion_claim'])
 def test_still_live_id_rejected(self):
  r=self.disposed();r['disposal_scans'][1]['ids'][-1]=r['preflight']['selected']['object_id'];self.assertFalse(single_control_release(r,127)['control_release_verified'])
 def test_one_frame_repeated_not_lifetime_evidence(self):
  r=self.disposed();r['disposal_scans'][0]=dict(r['disposal_scans'][1]);self.assertFalse(single_control_release(r,127)['control_release_verified'])
 def test_incomplete_scan_rejected(self):
  r=self.disposed();r['disposal_scans'][0]['complete']=False;self.assertFalse(single_control_release(r,127)['control_release_verified'])
 def test_duplicate_ids_rejected(self):
  r=self.disposed();r['disposal_scans'][0]['ids']=[1,1,2];self.assertFalse(single_control_release(r,127)['control_release_verified'])
 def test_unknown_callbacks_rejected(self):
  r=self.disposed();r['native']['active']=1;self.assertFalse(single_control_release(r,127)['control_release_verified'])
 def test_session_drift_rejected(self):
  r=self.disposed();r['native']['session_id']='other';self.assertFalse(single_control_release(r,127)['control_release_verified'])
if __name__=='__main__':unittest.main()
