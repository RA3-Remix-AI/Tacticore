import copy,struct,json,tempfile,unittest
from pathlib import Path
from ordered_qualification import qualify,qualify_path
BASE=Path(__file__).resolve().parent.parent/'acceptance/runs/20261025-010403-commander'
class OrderedQualificationTests(unittest.TestCase):
 def raw(self):return json.loads((BASE/'ordered-ak03-static.json').read_text(encoding='utf-8'))
 def binding(self):return json.loads((BASE/'ordered-ak03-template.json').read_text(encoding='utf-8'))
 def check(self,r):return qualify(r,self.binding())
 def hit(self,r):return next(e for e in r['events'] if e['kind']==20)
 def test_real_direct_ground_order(self):
  q=qualify_path(BASE/'ordered-ak03-static.json');self.assertEqual(q['status'],'bounded_ak_ordered_attack_verified');self.assertTrue(q['new_order_fire_association_verified']);self.assertFalse(q['harass_economy_verified']);self.assertFalse(q['single_shot_claim']);self.assertEqual(len(q['supplemental_sources']),1)
 def test_different_source_actor_packet_rejected(self):
  r=self.raw();self.hit(r)['stack_words'][34]=999;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_molotov_packet_not_direct_ak(self):
  r=self.raw();h=self.hit(r);h['stack_words'][36]=0x41872ecc;h['stack_words'][37]=0x41872ecc;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_other_damage_type_rejected(self):
  r=self.raw();self.hit(r)['stack_words'][39]=4;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_packet_is_bound_by_actual_argument_pointer(self):
  r=self.raw();self.hit(r)['stack_words'][23]+=4;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_packet_nonfinite_amount_rejected(self):
  r=self.raw();self.hit(r)['stack_words'][68]=0x7fc00000;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_amount_not_hardcoded_to_five(self):
  r=self.raw();h=self.hit(r);commit=next(e for e in r['events'] if e['kind']==24)
  for e in [h,commit]:e['damage_after']=e['damage_before']-7.5;e['damage_reported']=7.5
  h['stack_words'][67]=h['stack_words'][68]=struct.unpack('<I',struct.pack('<f',7.5))[0];r['native']['damage_total']=7.5;self.assertEqual(self.check(r)['status'],'bounded_ak_ordered_attack_verified')
 def test_late_ammo_observation_rejected(self):
  r=self.raw();next(e for e in r['events'] if e['kind']==22)['frame']+=10;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_old_order_damage_rejected(self):
  r=self.raw();self.hit(r)['lease_stage']=0;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_real_override_rejected_post_return_reacquisition_allowed(self):
  r=self.raw();e=next(e for e in r['events'] if e['kind']==12 and e['tag']==0);e['frame']=2710;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_missing_return_rejected(self):
  r=self.raw();r['native']['return_verified']=0;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_air_target_rejected(self):
  r=self.raw();r['request']['target_role']='air';self.assertEqual(self.check(r)['status'],'not_passed')
 def test_critical_float_null_rejected_without_crash(self):
  r=self.raw();self.hit(r)['x']=None;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_unstable_stop_rejected(self):
  r=self.raw();next(e for e in r['events'] if e['kind']==3 and e['lease_stage']==0)['x']+=50;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_wrong_template_source_binding_rejected(self):
  b=self.binding();b['asset_id']='0x41872ecc';self.assertEqual(qualify(self.raw(),b)['status'],'not_passed')
 def test_damage_event_before_order_rejected_even_with_later_frame(self):
  r=self.raw();hits=[e for e in r['events'] if e['kind'] in [24,20]];r['events']=[e for e in r['events'] if e not in hits];at=next(i for i,e in enumerate(r['events']) if e['kind']==34 and e['tag']==2);r['events'][at:at]=hits
  for i,e in enumerate(r['events']):e['seq']=i+1
  self.assertEqual(self.check(r)['status'],'not_passed')
 def test_sample_frame_reverse_rejected(self):
  r=self.raw();next(e for e in r['events'] if e['kind']==3 and e['lease_stage']==1)['frame']=2600;self.assertEqual(self.check(r)['status'],'not_passed')
 def test_war_factory_cannot_be_relabelled_economy(self):
  r=self.raw();r['request']['target_role']='economy';a=self.check(r);self.assertEqual(a['status'],'not_passed');self.assertFalse(a['harass_economy_verified'])
 def test_partial_clip_same_ak_entry_is_allowed(self):
  r=self.raw();r['native'].update(weapon_ammo=2,last_ammo=1);next(e for e in r['events'] if e['kind']==22).update(damage_before=2.,damage_after=1.);self.assertEqual(self.check(r)['status'],'bounded_ak_ordered_attack_verified')
 def test_partial_clip_cannot_increase(self):
  r=self.raw();r['native'].update(weapon_ammo=1,last_ammo=2);self.assertEqual(self.check(r)['status'],'not_passed')
 def test_partial_clip_native_totals_must_match_raw_drop(self):
  r=self.raw();r['native'].update(weapon_ammo=1,last_ammo=0);self.assertEqual(self.check(r)['status'],'not_passed')
if __name__=='__main__':unittest.main()
