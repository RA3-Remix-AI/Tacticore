"""Held overlays over synthetic own rosters; no game/native/model operations."""
import copy
import json
import unittest
from unittest.mock import patch

import formations
import held_formations
import live_state
import test_held_formations as fixture

SESSION=fixture.SESSION
COMMANDER=fixture.COMMANDER
CTRL=fixture.CTRL

def registry(session=SESSION,commander=COMMANDER,front=800,support=801,start=100,ready_frame=130):
    held=held_formations.HeldFormationRegistry(session,commander)
    initial=fixture.prearm();initial.update(session_id=session,commander_id=commander)
    held.prearm_controller(initial)
    clock=fixture.clock(start);clock['session_id']=session;held.bind_lease_clock(CTRL,clock)
    for name,actor,frame in (("front",front,start+10),("support",support,start+20)):
        claim=fixture.claim(name);claim.update(session_id=session,object_id=actor,observed_frame=frame);held.claim_slot(CTRL,claim)
        ready=fixture.ready(name,ready_frame);ready.update(session_id=session,object_id=actor);held.mark_slot_ready(CTRL,ready)
    return held

def unit(actor,kind='0x19ab11af',hp=100,xyz=None):
    return dict(object_id=actor,type_hash=kind,hp=hp,xyz=[25,35,0] if xyz is None else xyz)

def state(held=None):
    result=live_state.LiveBattleState.__new__(live_state.LiveBattleState)
    result.session=dict(session_id=SESSION);result.commander_id=COMMANDER;result.player_id=3
    result.formations=formations.FormationRegistry(SESSION);result.private_formations={};result.private_held_formations={}
    result.held_formations=held
    return result

class Overlay(unittest.TestCase):
    def setUp(self):
        self.held=registry();self.state=state(self.held)
        self.units=[unit(800),unit(801,'0x2c358c61'),unit(10),unit(11),unit(12,'0x2c358c61')]
        self.eligible={u['object_id'] for u in self.units}
    def refresh(self,units=None,frame=140):
        return self.state.refresh_formations(self.units if units is None else units,self.eligible,frame)
    def held_form(self,public):
        return next(row for row in public if row['formation_id'] in self.state.private_held_formations)
    def test_default_none_preserves_original_free_schema_and_descriptors(self):
        source=state();expected=formations.FormationRegistry(SESSION)
        before=expected.refresh(self.units,self.eligible,source.region_of)
        current=source.refresh_formations(self.units,self.eligible,140)
        self.assertEqual(before,current);self.assertEqual(source.private_formations,expected.private)
        self.assertEqual(source.private_held_formations,{})
        self.assertTrue(all(set(value)=={'version','object_ids','role'} for value in source.private_formations.values()))
    def test_claims_excluded_from_free_and_held_public_strict_five_fields(self):
        public=self.refresh();held_public=self.held_form(public)
        free_ids={actor for row in self.state.private_formations.values() for actor in row['object_ids']}
        self.assertEqual(free_ids,{10,11,12});self.assertTrue(held_public['available'])
        self.assertEqual(held_public['roles'],{'infantry':1,'anti_air':1})
        self.assertEqual(set(held_public),{'formation_id','version','roles','region_id','available'})
        self.assertEqual(held_public['region_id'],self.state.region_of([25,35,0]))
        text=json.dumps(public)
        for name in ('object_id','object_ids','xyz','proof','lease','controller','hp'):self.assertNotIn(name,text)
        private=next(iter(self.state.private_held_formations.values()))
        self.assertEqual(private['object_ids'],[800,801]);self.assertFalse(private['physical_capability_verified'])
    def test_missing_actor_unavailable_with_current_remaining_roles_claims_retained(self):
        original=self.held.claimed_actor_ids();public=self.refresh([u for u in self.units if u['object_id']!=800])
        descriptor=self.held_form(public);self.assertFalse(descriptor['available']);self.assertEqual(descriptor['roles'],{'anti_air':1})
        self.assertEqual(self.held.claimed_actor_ids(),original)
        private=next(iter(self.state.private_held_formations.values()))
        self.assertEqual(private['object_ids'],[800,801]);self.assertEqual(private['own_roster_observation']['missing_or_unavailable_ids'],[800])
        self.assertFalse(private['own_roster_observation']['disposal_verified']);self.assertFalse(private['own_roster_observation']['control_release_verified'])
    def test_zero_hp_or_wrong_type_cannot_reuse_stale_ready_to_be_available(self):
        for field,value in (('hp',0),('hp',float('nan')),('hp',True),('type_hash','0x33026fa1')):
            units=copy.deepcopy(self.units);units[0][field]=value
            with self.subTest(field=field,value=value):
                descriptor=self.held_form(self.refresh(units));self.assertFalse(descriptor['available']);self.assertEqual(descriptor['roles'],{'anti_air':1})
                self.assertEqual(self.held.claimed_actor_ids(),{800,801})
    def test_no_current_pair_rows_omits_empty_public_but_retains_private_claims(self):
        public=self.refresh([u for u in self.units if u['object_id'] not in {800,801}])
        self.assertFalse(set(self.state.private_held_formations)&{row['formation_id'] for row in public})
        self.assertEqual(next(iter(self.state.private_held_formations.values()))['object_ids'],[800,801]);self.assertEqual(self.held.claimed_actor_ids(),{800,801})
    def test_stale_ready_expiry_is_unavailable_without_releasing(self):
        descriptor=self.held_form(self.refresh(frame=161));self.assertFalse(descriptor['available']);self.assertEqual(self.held.claimed_actor_ids(),{800,801})
    def test_partial_claim_excludes_free_even_before_pair_can_be_public(self):
        held=held_formations.HeldFormationRegistry(SESSION,COMMANDER);held.prearm_controller(fixture.prearm());held.bind_lease_clock(CTRL,fixture.clock());held.claim_slot(CTRL,fixture.claim())
        self.state.held_formations=held;public=self.refresh()
        ids={actor for row in self.state.private_formations.values() for actor in row['object_ids']}
        self.assertNotIn(800,ids);self.assertIn(801,ids);self.assertEqual(self.state.private_held_formations,{})
    def test_wrong_session_commander_player_fails_before_using_cached_overlay(self):
        self.refresh()
        for key,value in (('session_id',fixture.OTHER),('commander_id',fixture.OTHER),('player_id',4)):
            previous=getattr(self.held,key);setattr(self.held,key,value)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'binding'):self.refresh()
            setattr(self.held,key,previous);self.assertEqual(self.state.private_held_formations,{})
        self.assertEqual(self.held.claimed_actor_ids(),{800,801})
    def test_old_inflight_free_roster_cannot_also_be_claimed_by_controller(self):
        old=state();initial=old.refresh_formations(self.units,self.eligible,140)
        fid=next(row['formation_id'] for row in initial if 800 in old.private_formations[row['formation_id']]['object_ids'])
        old.formations.reserve([fid]);old.held_formations=self.held
        with self.assertRaisesRegex(ValueError,'already allocated'):old.refresh_formations(self.units,self.eligible,140)
        self.assertEqual(old.private_held_formations,{})
    def test_duplicate_current_owned_claimed_identity_is_rejected(self):
        with self.assertRaises(ValueError):self.refresh(self.units+[unit(800)])
        self.assertEqual(self.held.claimed_actor_ids(),{800,801})
    def test_release_is_only_by_independent_verifier_not_roster_overlay(self):
        self.refresh([u for u in self.units if u['object_id'] not in {800,801}]);self.assertEqual(self.held.claimed_actor_ids(),{800,801})
        self.held.record_terminal(CTRL,fixture.terminal());self.held.record_verified_release(CTRL,fixture.release())
        self.refresh(frame=182);self.assertEqual(self.state.private_held_formations,{})
        self.assertEqual({actor for row in self.state.private_formations.values() for actor in row['object_ids']},self.eligible)
    def test_snapshot_getters_do_not_mutate_registry_proof_records(self):
        self.refresh();record=next(iter(self.state.private_held_formations.values()));record['object_ids'][0]=1
        self.assertEqual(next(iter(self.held.private_formations().values()))['object_ids'],[800,801])
    def test_public_descriptor_alias_to_free_roster_is_rejected(self):
        original=self.held.private_formations
        free=state();public=free.refresh_formations(self.units,self.eligible,140);collision=public[0]['formation_id']
        def bad():
            copied=original();value=copied.pop(next(iter(copied)));copied[collision]=value;return copied
        with patch.object(self.held,'private_formations',side_effect=bad),self.assertRaisesRegex(ValueError,'collision'):self.refresh()
    def test_real_collect_path_skips_claimed_ids_in_legacy_admission(self):
        # Reuse only existing synthetic-memory setup; every Memory/reader/game
        # dependency is mocked by that fixture's collect method.
        import test_live_visibility as visibility_fixture
        case=visibility_fixture.LiveVisibility('test_garrison_immobile_and_script_holder_troops_are_not_mobile_cohorts')
        case.setUp()
        try:
            current=case.state;current.held_formations=registry(current.session['session_id'],current.commander_id,front=1,support=7,start=1480,ready_frame=1500)
            current.mission_history=True;current.session['run_directory']=str(case.root);current.session_raw=json.dumps(current.session).encode();current.session_path.write_bytes(current.session_raw)
            with patch.object(live_state,'mission_actor_eligible',return_value=True) as admission:raw=case.collect()
            self.assertEqual(admission.call_count,5)
            self.assertFalse({1,7}&{actor for row in current.private_formations.values() for actor in row['object_ids']})
            held_public=next(row for row in raw['battlefield']['formations'] if row['formation_id'] in current.private_held_formations)
            self.assertTrue(held_public['available']);self.assertEqual(held_public['roles'],{'infantry':1,'anti_air':1})
        finally:case.tearDown()

if __name__=='__main__':unittest.main()
