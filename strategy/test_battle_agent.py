import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from battle_agent import BattleAgent,BuildEvidence,TaskCoordinator,TaskRequest
from engine import ContractError,StrategyEngine
from fixtures import binding,policy,snapshot,SESSION,COMMANDER


def evidence(player=3):return BuildEvidence(str(uuid.uuid4()),SESSION,player,"simulated")


def feedback(agent,task,status="completed",reason="ok"):
    return {"session_id":SESSION,"player_id":agent.engine.binding.player_id,"commander_id":agent.engine.binding.commander_id,"task_id":task.task_id,"status":status,"reason_code":reason,"at_game_seconds":agent.latest.game_time_seconds,"source":"simulated"}


class Sessions(unittest.IsolatedAsyncioTestCase):
    async def test_strategy_is_held_and_only_summary_delta_is_sent(self):
        seen=[]
        async def model(context):seen.append(copy.deepcopy(context));return policy(context)
        agent=BattleAgent(StrategyEngine(binding()))
        await agent.decide(snapshot(),model)
        first_task=agent.jobs()["jobs"][0]["task_id"]
        for ident,at in [(2,101),(3,102),(4,104)]:await agent.decide(snapshot(ident,at,events=[]),model)
        self.assertEqual(len(seen),1);self.assertEqual(agent.jobs()["jobs"][0]["task_id"],first_task)
        await agent.decide(snapshot(5,116,events=[]),model)
        self.assertEqual(len(seen),2);self.assertEqual(seen[1]["working_memory"]["current_strategy"]["production_focus"],"anti_air")
        self.assertEqual(seen[1]["delta"]["since_snapshot_id"],1)
        self.assertEqual(seen[0]["agent_protocol"],"battle_agent_v1")
        self.assertNotIn("production",seen[0]);self.assertNotIn("resources",seen[0]);self.assertNotIn("units",seen[0])

    async def test_compaction_is_bounded_deterministic_and_unknown_power_preserved(self):
        a=BattleAgent(StrategyEngine(binding()),event_capacity=4,context_budget_bytes=4096)
        b=BattleAgent(StrategyEngine(binding()),event_capacity=4,context_budget_bytes=4096)
        for ident in range(1,101):
            raw=snapshot(ident,100+ident);raw["resources"]["power_balance"]=None
            for agent in [a,b]:agent.observe(raw)
        context=a.context(a.latest.model_context(binding()))
        self.assertLessEqual(len(json.dumps(context,ensure_ascii=False,separators=(",",":")).encode()),4096)
        self.assertEqual(len(a.events),4);self.assertGreater(a.metrics["compactions"],90)
        self.assertEqual(a.summary,b.summary);self.assertIsNone(context["working_memory"]["economy"]["power_balance"])
        self.assertNotIn("memory_address",json.dumps(context));self.assertLessEqual(len(a.dialogue),2)

    async def test_verified_enemy_facts_expire_without_model_invention(self):
        agent=BattleAgent(StrategyEngine(binding()),enemy_ttl_game_seconds=10)
        agent.observe(snapshot());agent.observe(snapshot(2,105,enemy_observations=[],events=[]))
        self.assertEqual(agent.enemy_facts["air"]["count"],3);self.assertFalse(agent.enemy_facts["air"]["currently_visible"])
        agent.observe(snapshot(3,111,enemy_observations=[],events=[]))
        self.assertEqual(agent.enemy_facts,{});self.assertEqual(agent.metrics["expired_enemy_facts"],1)

    async def test_completed_build_has_exactly_once_id_per_plan_and_new_plan_generation(self):
        agent=BattleAgent(StrategyEngine(binding()),build_evidence=evidence())
        async def model(c):return policy(c)
        await agent.decide(snapshot(),model)
        task=agent.goals.tasks[0];first=task.task_id;first_plan=task.plan_id
        agent.record_feedback(feedback(agent,task))
        for ident,at in [(2,101),(3,105),(4,110)]:await agent.decide(snapshot(ident,at,events=[]),model)
        self.assertEqual(agent.goals.tasks[0].task_id,first);self.assertEqual(agent.goals.tasks[0].status,"completed")
        await agent.decide(snapshot(5,116,events=[]),model)
        task=agent.goals.tasks[0]
        self.assertNotEqual(task.task_id,first);self.assertNotEqual(task.plan_id,first_plan)
        self.assertGreater(task.generation,1);self.assertEqual(len(agent.goals.history),2)
        job=agent.jobs()["jobs"][0];self.assertTrue(job["host_dispatch_candidate"]);self.assertFalse(agent.jobs()["execution_authorized"])
        self.assertEqual(job["budget"]["unit"],"fraction_of_observed_credits")

    async def test_active_task_survives_new_plan_and_expiry_for_feedback(self):
        agent=BattleAgent(StrategyEngine(binding()),build_evidence=evidence())
        async def model(c):return policy(c,budget={"economy":.1,"army":.5,"tech":.05,"reserve":.35}) if c["snapshot_id"]>1 else policy(c)
        await agent.decide(snapshot(),model);task=agent.goals.tasks[0]
        agent.record_feedback(feedback(agent,task,"started"));await agent.decide(snapshot(2,116,events=[]),model)
        self.assertIs(agent.goals.tasks[0],task)
        self.assertEqual(task.request.spend_fraction,.8)
        agent.observe(snapshot(3,200,events=[]));agent.jobs()
        self.assertIn(task,agent.goals.tasks);agent.record_feedback(feedback(agent,task))

    async def test_failure_memory_backoff_and_early_reassessment(self):
        contexts=[]
        async def model(c):contexts.append(copy.deepcopy(c));return policy(c)
        agent=BattleAgent(StrategyEngine(binding()),build_evidence=evidence(),event_capacity=4)
        await agent.decide(snapshot(),model);task=agent.goals.tasks[0]
        agent.record_feedback(feedback(agent,task,"failed","insufficient_funds"))
        await agent.decide(snapshot(2,103,events=[]),model)
        self.assertEqual(len(contexts),2);self.assertEqual(contexts[1]["working_memory"]["failure_memory"][0]["reason_code"],"insufficient_funds")
        self.assertEqual(agent.goals.tasks[0].reason_code,"failure_backoff")
        for ident in range(3,30):agent.observe(snapshot(ident,101+ident))
        self.assertEqual(agent.last_failures["build"]["reason_code"],"insufficient_funds")
        self.assertGreater(agent.summary["events_compacted"],0)

    async def test_unavailable_modules_and_unverified_feedback_never_claim_execution(self):
        agent=BattleAgent(StrategyEngine(binding()))
        async def model(c):return policy(c,stance="pressure")
        await agent.decide(snapshot(),model)
        self.assertTrue(all(task.status=="unavailable" for task in agent.goals.tasks))
        with self.assertRaisesRegex(ContractError,"feedback_unverified"):agent.record_feedback(feedback(agent,agent.goals.tasks[0]))
        self.assertFalse(agent.public_memory()["execution"]["enabled"])

    async def test_feedback_binding_future_stale_and_duplicate_are_rejected(self):
        agent=BattleAgent(StrategyEngine(binding()),build_evidence=evidence())
        async def model(c):return policy(c)
        await agent.decide(snapshot(),model);task=agent.goals.tasks[0]
        for change in [{"player_id":2},{"commander_id":str(uuid.uuid4())},{"at_game_seconds":101},{"at_game_seconds":99},{"extra":"bad"}]:
            value=feedback(agent,task);value.update(change)
            with self.subTest(change=change),self.assertRaises(ContractError):agent.record_feedback(value)
        agent.record_feedback(feedback(agent,task))
        with self.assertRaisesRegex(ContractError,"feedback_lifecycle"):agent.record_feedback(feedback(agent,task))

    async def test_instances_keep_memory_separate_even_with_shared_adapter(self):
        commander=str(uuid.uuid4());a=BattleAgent(StrategyEngine(binding()));b=BattleAgent(StrategyEngine(binding(4,commander)))
        async def model(c):return policy(c)
        await asyncio.gather(a.decide(snapshot(),model),b.decide(snapshot(player=4,enemy_observations=[]),model))
        self.assertTrue(a.enemy_facts);self.assertFalse(b.enemy_facts)
        self.assertNotIn(COMMANDER,json.dumps(b.public_memory()));self.assertNotIn(commander,json.dumps(a.public_memory()))

    async def test_inflight_snapshot_advance_does_not_mutate_sent_context(self):
        arrived=asyncio.Event();release=asyncio.Event();seen=[]
        async def model(c):seen.append(c);arrived.set();await release.wait();return policy(c)
        agent=BattleAgent(StrategyEngine(binding()))
        pending=asyncio.create_task(agent.decide(snapshot(),model));await arrived.wait()
        agent.observe(snapshot(2,103,enemy_observations=[],events=[]));release.set();await pending
        self.assertEqual(seen[0]["snapshot_id"],1);self.assertEqual(seen[0]["game_time_seconds"],100)
        self.assertEqual(seen[0]["working_memory"]["verified_enemy_facts"][0]["certainty"],"visible")

    async def test_context_rejects_objective_it_did_not_send(self):
        agent=BattleAgent(StrategyEngine(binding()))
        raw=snapshot();raw["capabilities"]["regions"]=["region_"+str(i) for i in range(20)]
        async def model(c):return policy(c,objective_region="region_19")
        result=await agent.decide(raw,model)
        self.assertEqual(result.status,"local_fallback")

    async def test_memory_and_jobs_files_are_explicit_proposals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);agent=BattleAgent(StrategyEngine(binding()),memory_path=root/"agent-state.json",jobs_path=root/"jobs.json")
            async def model(c):return policy(c)
            await agent.decide(snapshot(),model)
            self.assertTrue((root/"agent-state.json").is_file());self.assertFalse(json.loads((root/"jobs.json").read_text())["execution_authorized"])

    async def test_feedback_during_model_request_invalidates_obsolete_response(self):
        agent=BattleAgent(StrategyEngine(binding()),build_evidence=evidence())
        async def initial(c):return policy(c)
        await agent.decide(snapshot(),initial);task=agent.goals.tasks[0]
        arrived=asyncio.Event();release=asyncio.Event()
        async def slow(c):arrived.set();await release.wait();return policy(c)
        pending=asyncio.create_task(agent.decide(snapshot(2,116,events=[]),slow));await arrived.wait()
        agent.record_feedback(feedback(agent,task,"failed","prerequisite_missing"));release.set()
        result=await pending
        self.assertEqual(result.reason_code,"reassessment_after_request");self.assertNotEqual(result.status,"accepted")
        self.assertEqual(agent.last_failures["build"]["reason_code"],"prerequisite_missing")

    async def test_many_turns_keep_chat_ring_tasks_and_request_bytes_bounded(self):
        agent=BattleAgent(StrategyEngine(binding()),event_capacity=4,context_budget_bytes=4096,build_evidence=evidence())
        seen=[]
        async def model(c):seen.append(copy.deepcopy(c));return policy(c)
        for index in range(1,61):
            await agent.decide(snapshot(index,100+index*16,events=[]),model)
            task=agent.goals.tasks[0]
            if task.status=="planned":agent.record_feedback(feedback(agent,task))
        self.assertEqual(len(seen),60);self.assertEqual(len(agent.dialogue),2)
        self.assertLessEqual(len(agent.goals.history),16);self.assertEqual(len(agent.events),4)
        self.assertGreater(agent.summary["completed_tasks"]["build"],40)
        self.assertTrue(all(len(json.dumps(c,ensure_ascii=False,separators=(",",":")).encode())<=4096 for c in seen))


class Coordination(unittest.TestCase):
    def test_resource_and_budget_conflicts_are_explicit(self):
        coordinator=TaskCoordinator(StrategyEngine(binding()),evidence())
        requests=[TaskRequest("build","production_focus",None,"anti_air",.6,0,("production_queue",),90),TaskRequest("attack","main_attack","home_base",None,.3,.9,("main_force",),60),TaskRequest("raid","recon","home_base",None,0,.2,("main_force",),50)]
        tasks=coordinator.reconcile(requests,100,["home_base"],.8,1,"simulated")
        self.assertEqual(tasks[1].reason_code,"budget_conflict")
        requests[1]=TaskRequest("attack","main_attack","home_base",None,0,.5,("main_force",),60)
        tasks=coordinator.reconcile(requests,100,["home_base"],.8,1,"simulated")
        self.assertEqual(tasks[2].reason_code,"resource_conflict")

    def test_evidence_cannot_cross_player(self):
        with self.assertRaisesRegex(ContractError,"build_evidence_binding"):TaskCoordinator(StrategyEngine(binding()),evidence(4))

    def test_one_verified_primitive_does_not_enable_other_build_directions(self):
        coordinator=TaskCoordinator(StrategyEngine(binding()),evidence())
        request=TaskRequest("build","production_focus",None,"anti_armor",.5,0,("production_queue",),80)
        self.assertEqual(coordinator.reconcile([request],100,[],1,1,"simulated")[0].status,"unavailable")
        self.assertEqual(coordinator.capability_manifest("simulated")["build"]["verified_production_focus"],["anti_air"])


if __name__=="__main__":unittest.main(verbosity=2)
