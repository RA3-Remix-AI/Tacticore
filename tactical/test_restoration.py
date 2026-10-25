import copy,importlib.util,json,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('restore_module',Path(__file__).parent/'restoration.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
ROOT=Path(__file__).resolve().parent.parent
class RestorationTests(unittest.TestCase):
 def live(self):return json.loads((ROOT/'acceptance/runs/20261024-233225-commander/formation03.json').read_text(encoding='utf-8'))
 def test_real_failed_goal_both_returned_is_settled(self):
  r=self.live();self.assertEqual(r['assessment']['status'],'not_passed');self.assertTrue(m.formation_restoration(r)['restoration_verified'])
 def test_missing_member_is_unknown(self):
  r=self.live();r['units'].pop();self.assertFalse(m.formation_restoration(r)['restoration_verified'])
 def test_claim_without_add_trace_is_not_return(self):
  r=self.live();r['events']=[e for e in r['events'] if e['kind']!=17];self.assertFalse(m.formation_restoration(r)['restoration_verified'])
 def disposed(self):
  r=self.live();u=r['units'][0];u.update(returned=0,return_calls=0,disposed_verified=1,disposed_reason=1,disposed_frame=r['native']['returned_frame'],disposed_list_count=0,disposed_hp=0.);r['native'].update(error=32,phase=4);r['events']=[e for e in r['events'] if not(e['unit_id']==u['id'] and e['tag']==3)];r['events'].append(dict(unit_id=u['id'],kind=30,arg=1,frame=u['disposed_frame']));return r
 def test_verified_disposal_plus_live_return_is_settled(self):self.assertTrue(m.formation_restoration(self.disposed())['restoration_verified'])
 def test_hp_positive_does_not_dispose(self):
  r=self.disposed();r['units'][0]['disposed_hp']=20.;self.assertFalse(m.formation_restoration(r)['restoration_verified'])
 def test_disposal_without_event_is_unknown(self):
  r=self.disposed();r['events']=[e for e in r['events'] if e['kind']!=30];self.assertFalse(m.formation_restoration(r)['restoration_verified'])
 def test_cleanup_failure_never_settled(self):
  r=self.disposed();r['native']['restore_mask']=30;self.assertFalse(m.formation_restoration(r)['restoration_verified'])
if __name__=='__main__':unittest.main()
