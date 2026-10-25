"""Offline second-verifier counterexamples. No SDK or network."""
import copy,importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(P))
from test_mission_combat_v7 import fixture as base_fixture
s=importlib.util.spec_from_file_location('mct7_second_review',Path(__file__).with_name('mct7_effect_independent.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def fixture():
 r=base_fixture()
 # The old synthetic test's team label was constant through Transfer; an actual
 # successful native-pool return must display the frozen default-team pointer.
 for e in r['events']:
  if e['kind']==15 and e['tag']==3:e['team']=int(r['preflight']['default_team'],0)
 return r
class SecondReview(unittest.TestCase):
 def test_full_effect_trace_synthetic_is_not_a_grant(self):
  a=m.audit(fixture());self.assertEqual(a['status'],'independent_effect_chain_verified_not_a_grant',a['checks']);self.assertFalse(a['completion_claim']);self.assertEqual(a['source_damage_amount'],30);self.assertEqual(a['observed_reload_count'],1)
 def test_native_goal_headers_do_not_create_damage(self):
  r=fixture();r['events']=[e for e in r['events'] if e['kind'] not in [20,24]];self.assertFalse(m.audit(r)['checks']['packet_commit_ammo_all_source_hits'])
 def test_wrong_damage_argument_rejects_source_hit(self):
  r=fixture();e=next(e for e in r['events'] if e['kind']==20);e['stack_words']=[0]*len(e['stack_words']);self.assertFalse(m.audit(r)['checks']['packet_commit_ammo_all_source_hits'])
 def test_refill_counter_cannot_replace_transition(self):
  r=fixture();r['events']=[e for e in r['events'] if e['kind']!=67];self.assertFalse(m.audit(r)['checks']['source_six_and_natural_refill'])
 def test_true_return_requires_actual_default_team(self):
  r=fixture();next(e for e in r['events'] if e['kind']==15 and e['tag']==3)['team']=0;self.assertFalse(m.audit(r)['normal_return_verified'])
 def test_repeated_same_frame_arrival_does_not_complete(self):
  r=fixture();rows=[e for e in r['events'] if e['kind']==3 and e['mission_stage']==8][-3:]
  for e in rows:e['frame']=rows[0]['frame']
  self.assertFalse(m.audit(r)['checks']['physical_long_home_return'])
 def test_scene_disposal_is_not_normal_return(self):
  r=fixture();r['native'].update(phase=4,error=31,returned_frame=0,return_verified=0);r['events']=[e for e in r['events'] if not(e['kind']==15 and e['tag']==3)];a=m.audit(r);self.assertEqual(a['status'],'not_passed');self.assertFalse(a['normal_return_verified'])
if __name__=='__main__':unittest.main()
