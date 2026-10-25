"""Reviewer protocol regression only, never a real field certificate."""
import copy,importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'mission-formation-v6'))
from test_complete_qualification import full_fixture
s=importlib.util.spec_from_file_location('independent_mf6_tests',Path(__file__).with_name('mfm6_field_independent.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Review(unittest.TestCase):
 def test_complete_synthetic_protocol_positive(self):self.assertEqual(m.review(full_fixture())['status'],'independent_mfm6_field_chain_verified')
 def test_counter_without_body_and_ammo_cannot_be_effect(self):
  for kind in (20,24,22):
   r=full_fixture();r['events']=[e for e in r['events'] if e['kind']!=kind];self.assertFalse(m.review(r)['checks']['real_nonlethal_source_damage_and_support'])
 def test_false_ground_and_future_reference(self):
  r=full_fixture();next(e for e in r['events'] if e['kind']==80)['breadcrumb']['height_flags']=0;self.assertFalse(m.review(r)['checks']['actual_ground_publications_and_immutable_header'])
  r=full_fixture();next(e for e in r['events'] if e['kind']==81)['breadcrumb']['published_seq']=99999;self.assertFalse(m.review(r)['checks']['every_prior_reference_arrival_and_stop'])
 def test_same_frame_arrival_duplicates_cannot_fake_three(self):
  r=full_fixture()
  for e in r['events']:
   if e['kind']==3 and e['frame'] in (151,153,155):e['frame']=155
  self.assertFalse(m.review(r)['checks']['every_prior_reference_arrival_and_stop'])
 def test_death_or_cleanup_without_actual_home_cannot_complete(self):
  for kind in (91,66,5):
   r=full_fixture();r['events']=[e for e in r['events'] if e['kind']!=kind];self.assertFalse(m.review(r)['checks']['both_actual_long_retreat_and_live_pool_returns'])
 def test_duplicate_pristine_entries_and_wrong_token_rejected(self):
  r=full_fixture();r['terminal_readonly']['entries']=[r['terminal_readonly']['entries'][0]]*13;self.assertFalse(m.review(r)['checks']['actual_bound_timer_and_thirteen_pristine_bytes'])
  r=full_fixture();r['terminal_readonly']['token']+=1;self.assertFalse(m.review(r)['checks']['actual_bound_timer_and_thirteen_pristine_bytes'])
 def test_running_or_native_error_is_not_completion(self):
  for key,value in [('status','running'),('host_exit',9)]:
   r=full_fixture();r[key]=value;self.assertEqual(m.review(r)['status'],'not_passed')
if __name__=='__main__':unittest.main()
