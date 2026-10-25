import asyncio
import copy
import json
import unittest
import uuid

from battle_agent import BattleAgent,TacticalEvidence,RestorationEvidence,TaskCoordinator
from engine import ContractError,Snapshot,StrategyEngine,validate_policy
from fixtures import binding,SESSION
from tactical_fixtures import tactical_snapshot,tactical_policy,intent,execution
from test_battle_agent import feedback


def evidence(purposes=None,player=3):
    return TacticalEvidence(str(uuid.uuid4()),SESSION,player,"simulated",purposes if purposes is not None else (("attack",("main_attack",)),))


class Observations(unittest.TestCase):
    def test_optional_extension_round_trips_without_native_addresses(self):
        raw=tactical_snapshot();parsed=Snapshot.from_dict(raw)
        self.assertEqual(parsed.to_dict(),raw)
        self.assertEqual(parsed.battlefield.contacts[0].contact_id,"contact_ore")
        self.assertNotIn("address",json.dumps(parsed.model_context(binding())))

    def test_unverified_collector_cannot_send_enemy_contacts_or_legacy_counts(self):
        raw=tactical_snapshot();raw["battlefield"]["visibility_verified"]=False
        with self.assertRaisesRegex(ContractError,"unverified_enemy_information"):Snapshot.from_dict(raw)

        raw["battlefield"]["contacts"]=[];raw["battlefield"]["regions"]=[]
        self.assertFalse(Snapshot.from_dict(raw).battlefield.visibility_verified)
        raw["enemy_observations"]=[{"role":"air","count":3,"observed_at_game_seconds":100,"currently_visible":True}]
        with self.assertRaisesRegex(ContractError,"unverified_enemy_information"):Snapshot.from_dict(raw)

    def test_observer_or_other_player_view_is_rejected_even_when_marked_verified(self):
        raw=tactical_snapshot();raw["battlefield"]["viewer_player_id"]=2
        with self.assertRaisesRegex(ContractError,"battlefield_viewer_mismatch"):Snapshot.from_dict(raw)

    def test_unknown_stealth_old_visibility_owner_mismatch_and_raw_fields_rejected(self):
        for change in [{"stealth_state":"unknown"},{"observed_at_game_seconds":96},{"owner_player_id":3},{"native_address":"0x123456"},{"contact_id":"0x123456"}]:
            raw=tactical_snapshot();raw["battlefield"]["contacts"][0].update(change)
            with self.subTest(change=change),self.assertRaises(ContractError):Snapshot.from_dict(raw)

    def test_roles_formations_and_regions_must_be_finite_bounded_and_unique(self):
        for change in [{"version":True},{"roles":{"infantry":float("nan")}},{"roles":{"secret_sniper":1}},{"roles":{}},{"region_id":"unknown"},{"available":"yes"},{"formation_id":"12345"}]:
            raw=tactical_snapshot();raw["battlefield"]["formations"][0].update(change)
            with self.subTest(change=change),self.assertRaises(ContractError):Snapshot.from_dict(raw)
        raw=tactical_snapshot();raw["battlefield"]["formations"].append(copy.deepcopy(raw["battlefield"]["formations"][0]))
        with self.assertRaisesRegex(ContractError,"duplicate_id"):Snapshot.from_dict(raw)


class Intents(unittest.TestCase):
    def validate(self,raw,latest=None):
        request=Snapshot.from_dict(tactical_snapshot());current=Snapshot.from_dict(latest) if latest else request
        return validate_policy(raw,request,current,binding(),20)

    def test_valid_attack_and_formation_version_are_captured_by_host_contract(self):
        request=Snapshot.from_dict(tactical_snapshot());plan=self.validate(tactical_policy(request.model_context(binding())))
        self.assertEqual(plan.tactical_tasks[0].formation_versions,(("formation_main",1),))
        self.assertNotIn("formation_versions",plan.public()["tactical_tasks"][0])

    def test_stale_formations_and_no_longer_visible_contacts_reject_late_response(self):
        context=Snapshot.from_dict(tactical_snapshot()).model_context(binding())
        for update in ["version","hidden","unavailable"]:
            latest=tactical_snapshot(2,102)
            if update=="version":latest["battlefield"]["formations"][0]["version"]=2
            elif update=="hidden":latest["battlefield"]["contacts"][0]["currently_visible"]=False
            else:latest["battlefield"]["formations"][0]["available"]=False
            with self.subTest(update=update),self.assertRaises(ContractError):self.validate(tactical_policy(context),latest)

    def test_enemy_target_formation_role_and_fraction_contracts(self):
        context=Snapshot.from_dict(tactical_snapshot()).model_context(binding())
        changes=[{"target_contact_id":None},{"target_contact_id":"invented"},{"target_region":"unknown"},{"formation_ids":["invented"]},{"required_roles":["naval"]},{"force_fraction":.9},{"force_fraction":True},{"native_order":"execute"}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ContractError):self.validate(tactical_policy(context,[intent(**change)]))

    def test_raid_scout_and_combined_arms_purposes_are_not_interchangeable(self):
        context=Snapshot.from_dict(tactical_snapshot()).model_context(binding())
        self.validate(tactical_policy(context,[intent("raid","harass_economy")]))
        self.validate(tactical_policy(context,[intent("raid","recon",target_contact_id=None)]))
        self.validate(tactical_policy(context,[intent("combined_arms","defend_base",target_region="home_base",target_contact_id=None,required_roles=["infantry","anti_air"])]))
        for task in [intent("raid","recon"),intent("combined_arms","coordinate_force"),intent("combined_arms","defend_base",required_roles=["infantry","anti_air"])]:
            with self.subTest(task=task),self.assertRaises(ContractError):self.validate(tactical_policy(context,[task]))
        raw=tactical_snapshot();raw["battlefield"]["contacts"][0]["role"]="armor";request=Snapshot.from_dict(raw)
        with self.assertRaisesRegex(ContractError,"raid_economy_target"):validate_policy(tactical_policy(request.model_context(binding()),[intent("raid","harass_economy")]),request,request,binding(),20)

    def test_formation_cannot_be_assigned_to_two_modules(self):
        context=Snapshot.from_dict(tactical_snapshot()).model_context(binding())
        tasks=[intent(force_fraction=.3),intent("raid","recon",target_contact_id=None,force_fraction=.3)]
        with self.assertRaisesRegex(ContractError,"formation_conflict"):self.validate(tactical_policy(context,tasks))


class TacticalSessions(unittest.IsolatedAsyncioTestCase):
    async def create(self,proof=True,tasks=None):
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=evidence() if proof else None)
        async def model(context):return tactical_policy(context,tasks)
        result=await agent.decide(tactical_snapshot(),model)
        self.assertEqual(result.status,"accepted")
        task=next(t for t in agent.goals.tasks if t.request.module=="attack")
        return agent,task

    async def test_default_lock_and_purpose_scoped_evidence(self):
        agent,task=await self.create(False);self.assertEqual(task.status,"unavailable")
        self.assertFalse(next(job for job in agent.jobs()["jobs"] if job["module"]=="attack")["host_dispatch_candidate"])
        with self.assertRaisesRegex(ContractError,"unverified_capability"):agent.record_feedback(feedback(agent,task))
        proof=evidence((("raid",("recon",)),));coordinator=TaskCoordinator(StrategyEngine(binding()),tactical_evidence=proof)
        self.assertTrue(coordinator.verified_tactical("raid","recon","simulated"));self.assertFalse(coordinator.verified_tactical("attack","main_attack","simulated"))
        with self.assertRaisesRegex(ContractError,"tactical_evidence_binding"):TaskCoordinator(StrategyEngine(binding()),tactical_evidence=evidence(player=4))

    async def test_raid_and_combined_arms_receive_real_lifecycle_feedback_only_with_evidence(self):
        for task_intent in [intent("raid","harass_economy"),intent("combined_arms","coordinate_force",required_roles=["infantry","anti_air"])]:
            proof=evidence(((task_intent["module"],(task_intent["purpose"],)),))
            agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=proof)
            async def model(c):return tactical_policy(c,[task_intent])
            await agent.decide(tactical_snapshot(),model)
            task=next(t for t in agent.goals.tasks if t.request.module==task_intent["module"])
            self.assertEqual(task.status,"planned")
            value=feedback(agent,task,"started");value["execution"]=execution(task);agent.record_feedback(value)
            value=feedback(agent,task);value["execution"]=execution(task,goal_observed=True,restoration_verified=True);agent.record_feedback(value)
            self.assertEqual(task.status,"completed");self.assertFalse(agent.jobs()["execution_authorized"])

    async def test_feedback_requires_started_goal_restoration_no_interference_and_same_command(self):
        agent,task=await self.create()
        value=feedback(agent,task);value["execution"]=execution(task,goal_observed=True,restoration_verified=True)
        with self.assertRaisesRegex(ContractError,"lifecycle"):agent.record_feedback(value)
        start=feedback(agent,task,"started");start["execution"]=execution(task);agent.record_feedback(start)
        for change in [{"goal_observed":False},{"restoration_verified":False},{"interference":"unknown"},{"interference":"native_ai_override"},{"formation_versions":{"formation_main":2}},{"issued_frame":1501},{"command_source":"observer"},{"raw_address":"0x1234"}]:
            value=feedback(agent,task);value["execution"]=execution(task,goal_observed=True,restoration_verified=True);value["execution"].update(change)
            with self.subTest(change=change),self.assertRaises(ContractError):agent.record_feedback(value)
        value=feedback(agent,task);value["execution"]=execution(task,goal_observed=True,restoration_verified=True);agent.record_feedback(value)
        self.assertEqual(task.status,"completed")

    async def test_target_loss_and_formation_change_block_without_rebinding_same_plan(self):
        for changed in ["target","formation"]:
            agent,task=await self.create();task_id=task.task_id
            update=tactical_snapshot(2,102)
            if changed=="target":
                update["battlefield"]["contacts"][0].update(currently_visible=False,observed_at_game_seconds=100)
            else:update["battlefield"]["formations"][0]["version"]=2
            agent.observe(update);jobs=agent.jobs()["jobs"];job=next(j for j in jobs if j["module"]=="attack")
            self.assertEqual(job["task_id"],task_id);self.assertFalse(job["host_dispatch_candidate"]);self.assertEqual(job["status"],"blocked")
            self.assertEqual(job["formation_versions"],(("formation_main",1),))

    async def test_last_seen_preserves_only_previously_verified_facts_and_expires(self):
        agent,_=await self.create();update=tactical_snapshot(2,104)
        update["battlefield"]["contacts"]=[];agent.observe(update)
        self.assertEqual(agent.contact_facts["contact_ore"]["region_id"],"east_ore")
        self.assertFalse(agent.contact_facts["contact_ore"]["currently_visible"])
        for field,value in [("region_id","north_expansion"),("observed_at_game_seconds",104)]:
            other,_=await self.create();raw=tactical_snapshot(2,104);raw["battlefield"]["contacts"][0].update(currently_visible=False,observed_at_game_seconds=100);raw["battlefield"]["contacts"][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ContractError,"hidden_contact_updated"):other.observe(raw)
        fresh=BattleAgent(StrategyEngine(binding()));raw=tactical_snapshot();raw["battlefield"]["contacts"][0]["currently_visible"]=False
        with self.assertRaisesRegex(ContractError,"unseen_contact_history"):fresh.observe(raw)
        raw=tactical_snapshot(3,162);raw["battlefield"]["contacts"]=[];agent.observe(raw);self.assertEqual(agent.contact_facts,{})

    async def test_failed_issued_task_keeps_quarantine_until_trusted_restoration(self):
        agent,task=await self.create();value=feedback(agent,task,"started");value["execution"]=execution(task);agent.record_feedback(value)
        with self.assertRaisesRegex(ContractError,"tactical_feedback_fields"):agent.record_feedback(feedback(agent,task,"failed","native_interference"))
        value=feedback(agent,task,"failed","native_interference");value["execution"]=execution(task,interference="native_ai_override");agent.record_feedback(value)
        self.assertEqual(agent.goals.quarantined_formations,{"formation_main":1})
        raw=tactical_snapshot(2,125)
        async def model(c):return tactical_policy(c)
        await agent.decide(raw,model)
        self.assertEqual(next(t for t in agent.goals.tasks if t.request.module=="attack").reason_code,"restoration_unverified")
        bad=RestorationEvidence(str(uuid.uuid4()),SESSION,4,"simulated",(("formation_main",1),))
        with self.assertRaises(ContractError):agent.confirm_restoration(bad)
        proof=RestorationEvidence(str(uuid.uuid4()),SESSION,3,"simulated",(("formation_main",1),));agent.confirm_restoration(proof)
        self.assertEqual(agent.goals.quarantined_formations,{})
        self.assertTrue(next(j for j in agent.jobs()["jobs"] if j["module"]=="attack")["host_dispatch_candidate"])

    async def test_preflight_failure_does_not_claim_native_issue_or_completion(self):
        agent,task=await self.create();agent.record_feedback(feedback(agent,task,"failed","no_route"))
        self.assertEqual(task.status,"failed");self.assertEqual(agent.goals.quarantined_formations,{})
        self.assertNotIn("execution",agent.public_memory()["recent_execution_feedback"][-1])

    async def test_many_visible_contacts_are_bounded_and_excluded_after_context_trimming(self):
        raw=tactical_snapshot()
        raw["battlefield"]["contacts"]=[dict(raw["battlefield"]["contacts"][0],contact_id="contact_"+str(i)) for i in range(64)]
        agent=BattleAgent(StrategyEngine(binding()),context_budget_bytes=4096,event_capacity=4)
        agent.observe(raw);context=agent.context(agent.latest.model_context(binding()))
        self.assertLessEqual(len(json.dumps(context,ensure_ascii=False,separators=(",",":")).encode()),4096)
        self.assertLessEqual(len(agent.contact_facts),64);self.assertTrue(context["context_limits"]["details_truncated"])
        self.assertNotIn("object_id",json.dumps(context));self.assertNotIn("address",json.dumps(context))

    async def test_pause_blocks_dispatch_candidates_without_spending_another_model_turn(self):
        agent,task=await self.create();before=agent.engine.metrics["requests"]
        raw=tactical_snapshot(2,100);raw["paused"]=True
        async def must_not_call(context):raise AssertionError("Paused session requested model")
        result=await agent.decide(raw,must_not_call)
        self.assertEqual(result.status,"paused");self.assertEqual(agent.engine.metrics["requests"],before)
        self.assertFalse(any(job["host_dispatch_candidate"] for job in agent.jobs()["jobs"]))

    async def test_sixty_tactical_turns_keep_three_module_results_and_memory_bounded(self):
        proof=evidence((("raid",("recon",)),("attack",("main_attack",)),("combined_arms",("defend_base",))))
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=proof,event_capacity=4,context_budget_bytes=8192)
        for index in range(60):
            selected=[intent("raid","recon",target_contact_id=None),intent(),intent("combined_arms","defend_base",target_region="home_base",target_contact_id=None,required_roles=["infantry","anti_air"])][index%3]
            async def model(context,task=selected):return tactical_policy(context,[task])
            at=100+index*16;result=await agent.decide(tactical_snapshot(index+1,at),model)
            self.assertEqual(result.status,"accepted")
            task=next(t for t in agent.goals.tasks if t.request.module==selected["module"])
            frames={"issued_frame":int(at*15),"expires_frame":int(at*15)+150}
            value=feedback(agent,task,"started");value["execution"]=execution(task,**frames);agent.record_feedback(value)
            value=feedback(agent,task);value["execution"]=execution(task,goal_observed=True,restoration_verified=True,**frames);agent.record_feedback(value)
        self.assertEqual(agent.engine.metrics["requests"],60)
        self.assertLessEqual(len(agent.goals.history),16);self.assertEqual(len(agent.dialogue),2);self.assertEqual(len(agent.events),4)
        self.assertGreater(sum(agent.summary["completed_tasks"].values()),50)
        self.assertLessEqual(agent.metrics["max_payload_bytes"],8192)

    async def test_contacts_and_formations_not_sent_cannot_be_selected_from_full_snapshot(self):
        for unknown in ["contact","formation"]:
            raw=tactical_snapshot();contact=raw["battlefield"]["contacts"][0];formation=raw["battlefield"]["formations"][0]
            raw["battlefield"]["contacts"]=[dict(contact,contact_id="contact_"+str(i).zfill(2)) for i in range(64)]
            raw["battlefield"]["formations"]=[dict(formation,formation_id="formation_"+str(i).zfill(2)) for i in range(32)]
            agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=evidence())
            async def model(context):
                seen=context["working_memory"]["battlefield"]
                contact_id="contact_63" if unknown=="contact" else seen["contacts"][0]["contact_id"]
                formation_id="formation_31" if unknown=="formation" else seen["formations"][0]["formation_id"]
                return tactical_policy(context,[intent(target_contact_id=contact_id,formation_ids=[formation_id])])
            with self.subTest(unknown=unknown):
                result=await agent.decide(raw,model)
                self.assertEqual(result.status,"local_fallback")
                self.assertEqual(agent.engine.metrics["accepted"],0)

    async def test_impossibly_small_transport_budget_continues_old_legal_plan(self):
        agent,task=await self.create();original=agent.engine.current.plan_id
        class Impossible:
            max_input_bytes=4096
            def input_size(self,context):return 100000
            async def __call__(self,context):raise AssertionError("Budget failure made a request")
        result=await agent.decide(tactical_snapshot(2,116),Impossible())
        self.assertEqual(result.status,"fallback_continuing");self.assertEqual(result.plan.plan_id,original)
        self.assertEqual(agent.metrics["context_rejections"],1)


if __name__=="__main__":unittest.main(verbosity=2)
