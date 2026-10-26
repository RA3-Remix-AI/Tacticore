"""Pure trusted-metadata fixtures; no Native, SDK, game or physical claims."""
import copy
import json
import unittest
import uuid
import held_formations as m

SESSION="11111111-1111-4111-8111-111111111111"
COMMANDER="22222222-2222-4222-8222-222222222222"
CTRL="33333333-3333-4333-8333-333333333333"
LEASE="44444444-4444-4444-8444-444444444444"
OTHER="55555555-5555-4555-8555-555555555555"
TASK="66666666-6666-4666-8666-666666666666"
COMMAND="77777777-7777-4777-8777-777777777777"
def binding(): return dict(session_id=SESSION,controller_id=CTRL,lease_id=LEASE)
def begin(): return dict(binding(),commander_id=COMMANDER,player_id=3,reserve_start_frame=100,reserve_deadline_frame=400,hard_deadline_frame=4600,allocation_scope=m.SCOPE,max_paid=305,reserve_floor=1000)
def prearm():
    return dict(binding(),commander_id=COMMANDER,player_id=3,allocation_scope=m.SCOPE,max_paid=305,reserve_floor=1000,reserve_offset_frames=300,hard_offset_frames=4500)
def clock(start=100):
    return dict(binding(),reserve_start_frame=start,reserve_deadline_frame=start+300,hard_deadline_frame=start+4500,observed_frame=start,proof_sha256="a"*64,validated_before_first_borrow=True)

def claim(name="front"):
    front=name=="front"
    return dict(binding(),slot=name,object_id=800 if front else 801,type_hash="0x19ab11af" if front else "0x2c358c61",paid=85 if front else 220,producer_reserve=1000,production_command_id=str(uuid.uuid5(uuid.UUID(CTRL),name+"command")),production_task_id=str(uuid.uuid5(uuid.UUID(CTRL),name+"task")),receipt_sha256=("a" if front else "b")*64,proof_sha256=("c" if front else "d")*64,observed_frame=110 if front else 120)
def ready(name="front",frame=130): return dict(binding(),slot=name,object_id=800 if name=="front" else 801,observed_frame=frame,proof_sha256="e"*64,validated_ready=True,region_id="home_base")
def commit(reg):
    state=reg.controller(CTRL)
    return dict(binding(),task_id=TASK,command_id=COMMAND,seq=1,formation_id=state["formation_id"],formation_version=1,object_ids=[800,801],module="combined_arms",purpose="coordinate_force",request_force_fraction=1,allocation_scope=m.SCOPE,hard_deadline_frame=4600,reserve_deadline_frame=400,commit_frame=140,target=dict(contact_id="contact_visible",object_id=999,type_hash="0xc45aaeab",owner_player_id=4,role="economy",observed_frame=138,proof_sha256="f"*64,currently_visible_verified=True))
def terminal(status="cancelled",frame=180): return dict(binding(),status=status,reason_code="host_stop",observed_frame=frame,proof_sha256="e"*64)
def release(actors=None,verified=True): return dict(binding(),object_ids=[800,801] if actors is None else actors,observed_frame=181,proof_sha256="f"*64,independently_verified=verified,channel_release_verified=True)

class Held(unittest.TestCase):
    def setUp(self): self.reg=m.HeldFormationRegistry(SESSION,COMMANDER);self.reg.begin_controller(begin())
    def pair(self):
        for name in ("front","support"): self.reg.claim_slot(CTRL,claim(name));self.reg.mark_slot_ready(CTRL,ready(name))
    def test_trusted_sixteen_policy_450_is_family_scoped_and_never_renews(self):
        reg=m.HeldFormationRegistry(SESSION,COMMANDER,executor_directory="mission-formation-v16",reserve_duration_frames=450)
        data=dict(prearm(),reserve_offset_frames=450);reg.prearm_controller(data)
        original=dict(clock(900),reserve_deadline_frame=1350)
        reg.bind_lease_clock(CTRL,original)
        self.assertEqual(reg.controller(CTRL)["hard_deadline_frame"],5400)
        reg.bind_lease_clock(CTRL,original)
        for changed in (clock(900),dict(original,reserve_deadline_frame=1351),dict(original,reserve_start_frame=901,reserve_deadline_frame=1351,hard_deadline_frame=5401,observed_frame=901)):
            with self.subTest(changed=changed),self.assertRaises(ValueError):reg.bind_lease_clock(CTRL,changed)
        late=dict(claim(),observed_frame=1350)
        with self.assertRaisesRegex(ValueError,"deadline"):reg.claim_slot(CTRL,late)
        self.assertEqual(reg.controller(CTRL)["reserve_deadline_frame"],1350)
        fixture=dict(begin(),reserve_deadline_frame=550)
        fixed=m.HeldFormationRegistry(SESSION,COMMANDER,executor_directory="mission-formation-v16",reserve_duration_frames=450)
        fixed.begin_controller(fixture)
        self.assertEqual(fixed.controller(CTRL)["reserve_deadline_frame"],550)
    def test_clock_policy_cannot_be_upgraded_by_records_or_wrong_family(self):
        for family in ("mission-formation-v13","mission-formation-v14","mission-formation-v15"):
            old=m.HeldFormationRegistry(SESSION,COMMANDER,executor_directory=family)
            with self.subTest(family=family),self.assertRaisesRegex(ValueError,"policy"):old.prearm_controller(dict(prearm(),reserve_offset_frames=450))
        for family,duration in (("mission-formation-v13",450),("mission-formation-v14",450),("mission-formation-v15",450),("mission-formation-v16",300),("mission-formation-v17",450),("mission-formation-v16",True),("mission-formation-v16",451)):
            with self.subTest(family=family,duration=duration),self.assertRaisesRegex(ValueError,"policy"):m.HeldFormationRegistry(SESSION,COMMANDER,executor_directory=family,reserve_duration_frames=duration)
        new=m.HeldFormationRegistry(SESSION,COMMANDER,executor_directory="mission-formation-v16",reserve_duration_frames=450)
        with self.assertRaisesRegex(ValueError,"policy"):new.prearm_controller(prearm())
    def test_prearm_claims_channel_without_inventing_clock(self):
        reg=m.HeldFormationRegistry(SESSION,COMMANDER);state=reg.prearm_controller(prearm())
        self.assertEqual(reg.channel_owner,CTRL);self.assertFalse(state["lease_clock_bound"])
        for key in ("reserve_start_frame","reserve_deadline_frame","hard_deadline_frame"):self.assertIsNone(state[key])
        self.assertFalse(reg.claimed_actor_ids());self.assertEqual(reg.public_formations(999),[])
        other=prearm();other.update(controller_id=OTHER,lease_id=TASK)
        with self.assertRaisesRegex(ValueError,"channel_occupied"):reg.prearm_controller(other)
    def test_unbound_prearm_cannot_claim_slot_or_change_offset_policy(self):
        reg=m.HeldFormationRegistry(SESSION,COMMANDER);reg.prearm_controller(prearm())
        with self.assertRaisesRegex(ValueError,"clock_unbound"):reg.claim_slot(CTRL,claim())
        self.assertFalse(reg.claimed_actor_ids())
        for key in ("reserve_offset_frames","hard_offset_frames"):
            changed=prearm();changed[key]+=1
            with self.assertRaisesRegex(ValueError,"policy"):m.HeldFormationRegistry(SESSION,COMMANDER).prearm_controller(changed)
    def test_clock_binds_actual_first_borrow_time_not_arm_or_production(self):
        reg=m.HeldFormationRegistry(SESSION,COMMANDER);reg.prearm_controller(prearm())
        # Arbitrary queue waiting does not bind/consume the lease clock.
        self.assertIsNone(reg.controller(CTRL)["reserve_start_frame"])
        reg.bind_lease_clock(CTRL,clock(900));state=reg.controller(CTRL)
        self.assertTrue(state["lease_clock_bound"]);self.assertEqual((state["reserve_deadline_frame"],state["hard_deadline_frame"]),(1200,5400))
        data=claim();data["observed_frame"]=900;reg.claim_slot(CTRL,data)
        self.assertEqual(reg.claimed_actor_ids(),{800})
    def test_clock_same_proof_replay_idempotent_but_rebind_forbidden(self):
        reg=m.HeldFormationRegistry(SESSION,COMMANDER);reg.prearm_controller(prearm());reg.bind_lease_clock(CTRL,clock())
        before=json.dumps(reg.audit(),sort_keys=True);reg.bind_lease_clock(CTRL,clock());self.assertEqual(before,json.dumps(reg.audit(),sort_keys=True))
        for record in (clock(101),dict(clock(),proof_sha256="b"*64),dict(clock(),hard_deadline_frame=4601),dict(clock(),observed_frame=99),dict(clock(),validated_before_first_borrow=False),dict(clock(),session_id=OTHER)):
            with self.subTest(record=record),self.assertRaises(ValueError):reg.bind_lease_clock(CTRL,record)
        reg.claim_slot(CTRL,claim())
        with self.assertRaisesRegex(ValueError,"rebind"):reg.bind_lease_clock(CTRL,clock(102))
    def test_unbound_failure_keeps_channel_until_zero_slot_verified_release(self):
        reg=m.HeldFormationRegistry(SESSION,COMMANDER);reg.prearm_controller(prearm());reg.record_terminal(CTRL,terminal(frame=0))
        self.assertEqual(reg.channel_owner,CTRL)
        with self.assertRaisesRegex(ValueError,"terminal"):reg.bind_lease_clock(CTRL,clock())
        with self.assertRaisesRegex(ValueError,"independently"):reg.record_verified_release(CTRL,dict(release([],False),observed_frame=0))
        reg.record_verified_release(CTRL,dict(release([]),observed_frame=0));self.assertIsNone(reg.channel_owner)
        saved=reg.audit()["controllers"][0];self.assertFalse(saved["lease_clock_bound"]);self.assertIsNotNone(saved["terminal"]);self.assertIsNotNone(saved["release"])
    def test_channel_claim_precedes_first_borrow(self):
        self.assertEqual(self.reg.channel_owner,CTRL);self.assertFalse(self.reg.claimed_actor_ids());self.assertEqual(self.reg.public_formations(110),[])
        self.reg.claim_slot(CTRL,claim());self.assertEqual(self.reg.claimed_actor_ids(),{800});self.assertEqual(self.reg.exclude_from_free([1,800,2]),[1,2])
        with self.assertRaisesRegex(ValueError,"not_free"):self.reg.assert_free([800])
    def test_single_controller_channel_cannot_double_book(self):
        other=begin();other.update(controller_id=OTHER,lease_id=TASK)
        with self.assertRaisesRegex(ValueError,"channel_occupied"):self.reg.begin_controller(other)
    def test_slot_actor_and_source_cannot_duplicate_or_change(self):
        self.reg.claim_slot(CTRL,claim())
        for change in ({},{"object_id":802},{"slot":"support","type_hash":"0x2c358c61"},{"slot":"support","object_id":801,"type_hash":"0x2c358c61"}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.reg.claim_slot(CTRL,dict(claim(),**change))
        self.assertEqual(self.reg.claimed_actor_ids(),{800})
    def test_wrong_session_or_lease_never_claims(self):
        for field in ("session_id","controller_id","lease_id"):
            data=claim();data[field]=OTHER
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"binding"):self.reg.claim_slot(CTRL,data)
        self.assertFalse(self.reg.claimed_actor_ids())
    def test_exact_frozen_global_deadlines_cannot_extend_or_restart_per_slot(self):
        self.reg.claim_slot(CTRL,claim())
        late=claim("support");late["observed_frame"]=400
        with self.assertRaisesRegex(ValueError,"deadline"):self.reg.claim_slot(CTRL,late)
        self.assertEqual(self.reg.controller(CTRL)["reserve_deadline_frame"],400)
        for field in ("reserve_deadline_frame","hard_deadline_frame"):
            reg=m.HeldFormationRegistry(SESSION,COMMANDER);data=begin();data[field]+=1
            with self.assertRaisesRegex(ValueError,"deadline"):reg.begin_controller(data)
    def test_paid_scope_305_and_reserve_1000_are_enforced(self):
        for change in ({"allocation_scope":"free"},{"max_paid":306},{"reserve_floor":999}):
            with self.subTest(change=change),self.assertRaises(ValueError):m.HeldFormationRegistry(SESSION,COMMANDER).begin_controller(dict(begin(),**change))
        self.reg.claim_slot(CTRL,claim());expensive=claim("support");expensive["paid"]=221
        with self.assertRaisesRegex(ValueError,"budget"):self.reg.claim_slot(CTRL,expensive)
        low=claim("support");low["producer_reserve"]=999
        with self.assertRaises(ValueError):self.reg.claim_slot(CTRL,low)
        self.reg.claim_slot(CTRL,claim("support"));self.assertEqual(sum(s["paid"] for s in self.reg.controller(CTRL)["slots"].values()),305)
    def test_pair_only_available_after_both_trusted_ready(self):
        self.reg.claim_slot(CTRL,claim());self.reg.mark_slot_ready(CTRL,ready());self.assertEqual(self.reg.public_formations(140),[])
        self.reg.claim_slot(CTRL,claim("support"));self.assertEqual(self.reg.public_formations(140),[])
        self.reg.mark_slot_ready(CTRL,ready("support"));public=self.reg.public_formations(140)[0]
        self.assertTrue(public["available"]);self.assertEqual(set(public),{"formation_id","version","roles","region_id","available"});self.assertEqual(public["roles"],{"infantry":1,"anti_air":1})
        self.assertFalse(self.reg.public_formations(161)[0]["available"]);self.assertFalse(self.reg.public_formations(400)[0]["available"])
    def test_ready_cannot_change_actor_or_unvalidated_or_regress(self):
        self.reg.claim_slot(CTRL,claim());self.reg.mark_slot_ready(CTRL,ready())
        for change in ({"object_id":802},{"validated_ready":False},{"observed_frame":129},{"proof_sha256":"f"*64},{"observed_frame":400}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.reg.mark_slot_ready(CTRL,dict(ready(),**change))
        self.reg.mark_slot_ready(CTRL,ready(frame=135));self.assertEqual(self.reg.controller(CTRL)["slots"]["front"]["ready"]["observed_frame"],135)
    def test_mission_mapping_write_once_idempotent_and_no_new_claim(self):
        self.pair();data=commit(self.reg);result=self.reg.commit_mission(CTRL,data)
        self.assertEqual(result,self.reg.commit_mission(CTRL,copy.deepcopy(data)));self.assertEqual(result["child_task_id"],str(uuid.uuid5(uuid.UUID(TASK),"formation")))
        self.assertEqual(result["mission_id"],TASK);self.assertFalse(result["native_acceptance_verified"]);self.assertFalse(result["physical_effect_verified"])
        self.assertFalse(self.reg.public_formations(140)[0]["available"]);self.assertEqual(self.reg.claimed_actor_ids(),{800,801})
        self.assertEqual(self.reg.controller(CTRL)["hard_deadline_frame"],4600)
    def test_same_commit_numeric_one_normalizes_to_same_digest(self):
        self.pair();data=commit(self.reg);first=self.reg.commit_mission(CTRL,data);data["request_force_fraction"]=1.0
        self.assertEqual(self.reg.commit_mission(CTRL,data)["commit_sha256"],first["commit_sha256"])
    def test_second_target_or_model_task_or_command_never_replaces_commit(self):
        self.pair();data=commit(self.reg);self.reg.commit_mission(CTRL,data)
        for field,value in (("task_id",OTHER),("command_id",OTHER),("seq",2),("commit_frame",141)):
            mutated=copy.deepcopy(data);mutated[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"conflict"):self.reg.commit_mission(CTRL,mutated)
        changed=copy.deepcopy(data);changed["target"]["object_id"]=1000
        with self.assertRaisesRegex(ValueError,"conflict"):self.reg.commit_mission(CTRL,changed)
    def test_commit_deadline_scope_fraction_pair_rejected(self):
        self.pair()
        for change in ({"hard_deadline_frame":4700},{"reserve_deadline_frame":500},{"allocation_scope":"free"},{"request_force_fraction":.5},{"request_force_fraction":True},{"object_ids":[801,800]},{"object_ids":[800,801,802]},{"formation_version":2}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.reg.commit_mission(CTRL,dict(commit(self.reg),**change))
        self.assertIsNone(self.reg.controller(CTRL)["mission_commit"])
    def test_commit_requires_fresh_real_pair_and_verified_visible_target(self):
        with self.assertRaises(ValueError):self.reg.commit_mission(CTRL,commit(self.reg))
        self.pair()
        for change in ({"currently_visible_verified":False},{"owner_player_id":3},{"observed_frame":94},{"object_id":800},{"role":"air"}):
            data=commit(self.reg);data["target"].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.reg.commit_mission(CTRL,data)
        data=commit(self.reg);data["commit_frame"]=170;data["target"]["observed_frame"]=169
        with self.assertRaisesRegex(ValueError,"not_ready"):self.reg.commit_mission(CTRL,data)
    def test_terminal_untasked_retains_claims_and_audit_until_verified_release(self):
        self.reg.claim_slot(CTRL,claim());self.reg.record_terminal(CTRL,terminal())
        self.assertEqual(self.reg.claimed_actor_ids(),{800});self.assertEqual(self.reg.channel_owner,CTRL)
        saved=self.reg.audit();self.assertIsNone(saved["controllers"][0]["mission_commit"]);self.assertIsNotNone(saved["controllers"][0]["terminal"]);self.assertFalse(saved["physical_capability_verified"])
        with self.assertRaisesRegex(ValueError,"independently"):self.reg.record_verified_release(CTRL,release([800],False))
        self.assertEqual(self.reg.claimed_actor_ids(),{800})
        self.reg.record_verified_release(CTRL,release([800]));self.assertFalse(self.reg.claimed_actor_ids());self.assertIsNone(self.reg.channel_owner)
    def test_release_must_cover_exact_pair_and_channel_after_terminal(self):
        self.pair()
        with self.assertRaisesRegex(ValueError,"requires_terminal"):self.reg.record_verified_release(CTRL,release())
        self.reg.record_terminal(CTRL,terminal())
        for data in (release([800]),release([800,800]),release([800,801,802]),dict(release(),channel_release_verified=False),dict(release(),session_id=OTHER)):
            with self.subTest(data=data),self.assertRaises(ValueError):self.reg.record_verified_release(CTRL,data)
        self.assertEqual(self.reg.claimed_actor_ids(),{800,801});self.reg.record_verified_release(CTRL,release());self.assertEqual(self.reg.audit()["claimed_actor_ids"],[])
    def test_new_controller_only_after_release_old_ids_cannot_be_reused(self):
        self.reg.record_terminal(CTRL,terminal());self.reg.record_verified_release(CTRL,release([]))
        with self.assertRaisesRegex(ValueError,"identity_reused"):self.reg.begin_controller(begin())
        data=begin();data.update(controller_id=OTHER,lease_id=TASK);self.reg.begin_controller(data);self.assertEqual(self.reg.channel_owner,OTHER)
    def test_terminal_cannot_be_rewritten_and_untasked_not_completed(self):
        with self.assertRaisesRegex(ValueError,"untasked"):self.reg.record_terminal(CTRL,terminal("completed"))
        self.reg.record_terminal(CTRL,terminal())
        with self.assertRaisesRegex(ValueError,"changed"):self.reg.record_terminal(CTRL,terminal("failed"))
        with self.assertRaisesRegex(ValueError,"terminal"):self.reg.claim_slot(CTRL,claim())
    def test_release_and_commit_replays_do_not_mutate_state(self):
        self.pair();data=commit(self.reg);self.reg.commit_mission(CTRL,data);self.reg.record_terminal(CTRL,terminal("completed"));self.reg.record_verified_release(CTRL,release())
        before=json.dumps(self.reg.audit(),sort_keys=True);self.reg.commit_mission(CTRL,data);self.reg.record_verified_release(CTRL,release());self.assertEqual(json.dumps(self.reg.audit(),sort_keys=True),before)
    def test_getters_and_inputs_are_isolated_copies(self):
        data=claim();self.reg.claim_slot(CTRL,data);data["object_id"]=1
        state=self.reg.controller(CTRL);state["slots"]["front"]["object_id"]=2
        audit=self.reg.audit();audit["controllers"].clear();self.assertEqual(self.reg.claimed_actor_ids(),{800});self.assertEqual(self.reg.controller(CTRL)["slots"]["front"]["object_id"],800)
    def test_scope_metadata_private_not_public_physical_claim(self):
        self.pair();private=next(iter(self.reg.private_formations().values()))
        self.assertEqual((private["allocation_scope"],private["request_force_fraction"]),(m.SCOPE,1));self.assertFalse(private["physical_capability_verified"])
        self.assertNotIn("proof",json.dumps(self.reg.public_formations(140)));self.assertNotIn("object_id",json.dumps(self.reg.public_formations(140)))
    def test_malformed_normalized_records_rejected(self):
        for data in (dict(claim(),extra=1),dict(claim(),proof_sha256="fake"),dict(claim(),paid=True),dict(claim(),slot=[])):
            with self.subTest(data=data),self.assertRaises(ValueError):self.reg.claim_slot(CTRL,data)
        self.assertFalse(self.reg.claimed_actor_ids())

if __name__=="__main__":unittest.main()
