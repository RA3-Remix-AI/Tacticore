"""Host acknowledgement is a reservation, never a native started receipt."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from battle_agent import BattleAgent,TacticalEvidence
from engine import ContractError,StrategyEngine
from fixtures import SESSION,binding
from tactical_fixtures import tactical_snapshot,tactical_policy,intent,execution
from test_battle_agent import feedback


class HostCommit(unittest.IsolatedAsyncioTestCase):
    async def create(self,*,proof=True,memory_path=None):
        evidence=TacticalEvidence(str(uuid.uuid4()),SESSION,3,"simulated",(("attack",("main_attack",)),("raid",("recon",)))) if proof else None
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=evidence,memory_path=memory_path)
        async def model(context):return tactical_policy(context)
        await agent.decide(tactical_snapshot(),model)
        task=next(task for task in agent.goals.tasks if task.request.module=="attack")
        return agent,task

    async def test_commit_persists_pending_without_native_started_or_repeated_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"memory.json";agent,task=await self.create(memory_path=path)
            result=agent.host_commit_task(task.task_id)
            self.assertEqual(result["status"],"dispatch_pending");self.assertIsNone(task.execution_start)
            self.assertEqual(agent.public_memory()["recent_execution_feedback"],[])
            self.assertFalse(next(job for job in agent.jobs()["jobs"] if job["task_id"]==task.task_id)["host_dispatch_candidate"])
            count=len([event for event in agent.events if event["kind"]=="host_commit"])
            agent.host_commit_task(task.task_id)
            self.assertEqual(len([event for event in agent.events if event["kind"]=="host_commit"]),count)
            state=json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(next(goal for goal in state["active_goals"] if goal["task_id"]==task.task_id)["status"],"dispatch_pending")

    async def test_reserved_unavailable_snapshot_and_new_plan_preserve_exact_original_job(self):
        agent,task=await self.create();agent.host_commit_task(task.task_id)
        plan_id=task.plan_id;version=task.request.formation_versions;expiry=task.expires_at_game_seconds
        update=tactical_snapshot(2,116);update["battlefield"]["formations"][0]["available"]=False
        async def new_plan(context):return tactical_policy(context,[],stance="expand",objective_region="north_expansion")
        result=await agent.decide(update,new_plan)
        self.assertEqual(result.status,"accepted");self.assertNotEqual(agent.engine.current.plan_id,plan_id)
        retained=next(goal for goal in agent.goals.tasks if goal.task_id==task.task_id)
        self.assertIs(retained,task);self.assertEqual(task.status,"dispatch_pending")
        self.assertEqual((task.plan_id,task.request.formation_versions,task.expires_at_game_seconds),(plan_id,version,expiry))
        started=feedback(agent,task,"started");started["execution"]=execution(task,issued_frame=1740,expires_frame=1890);agent.record_feedback(started)
        self.assertEqual(task.status,"active")
        completed=feedback(agent,task);completed["execution"]=execution(task,issued_frame=1740,expires_frame=1890,goal_observed=True,restoration_verified=True);agent.record_feedback(completed)
        self.assertEqual(task.status,"completed")

    async def test_expiry_keeps_pending_until_definitive_pre_dispatch_cancel(self):
        agent,task=await self.create();agent.host_commit_task(task.task_id)
        agent.observe(tactical_snapshot(2,200));jobs=agent.jobs()["jobs"]
        self.assertEqual(next(job for job in jobs if job["task_id"]==task.task_id)["status"],"dispatch_pending")
        agent.record_feedback(feedback(agent,task,"cancelled","expired"))
        self.assertEqual(task.status,"cancelled");self.assertFalse(any(job["task_id"]==task.task_id for job in agent.jobs()["jobs"]))

    async def test_pending_locks_and_force_budget_apply_to_new_plan(self):
        agent,task=await self.create();agent.host_commit_task(task.task_id)
        update=tactical_snapshot(2,116);update["battlefield"]["formations"][0]["available"]=False
        async def raid(context):return tactical_policy(context,[intent("raid","recon",target_contact_id=None,formation_ids=["formation_raid"],required_roles=["armor"],force_fraction=.4)])
        self.assertEqual((await agent.decide(update,raid)).status,"accepted")
        raid_task=next(goal for goal in agent.goals.tasks if goal.request.module=="raid")
        self.assertEqual(raid_task.status,"blocked");self.assertEqual(raid_task.reason_code,"budget_conflict")
        self.assertEqual(task.status,"dispatch_pending")

    async def test_unknown_outcome_cannot_be_reported_as_definitive_pre_dispatch_error(self):
        agent,task=await self.create();agent.host_commit_task(task.task_id)
        with self.assertRaisesRegex(ContractError,"pending_outcome_requires_native_evidence"):agent.record_feedback(feedback(agent,task,"failed","execution_error"))
        self.assertEqual(task.status,"dispatch_pending")
        # A confirmed preflight no-route refusal has never issued a native order.
        agent.record_feedback(feedback(agent,task,"failed","no_route"))
        self.assertEqual(task.status,"failed")

    async def test_commit_cannot_unlock_unverified_paused_expired_or_unknown_tasks(self):
        agent,task=await self.create(proof=False)
        with self.assertRaisesRegex(ContractError,"host_commit_not_dispatchable"):agent.host_commit_task(task.task_id)
        agent,task=await self.create();paused=tactical_snapshot(2,100);paused["paused"]=True;agent.observe(paused)
        with self.assertRaisesRegex(ContractError,"host_commit_not_dispatchable"):agent.host_commit_task(task.task_id)
        agent,task=await self.create();agent.observe(tactical_snapshot(2,200))
        with self.assertRaises(ContractError):agent.host_commit_task(task.task_id)
        with self.assertRaises(ContractError):agent.host_commit_task(str(uuid.uuid4()))

    async def test_pending_is_not_completed_without_real_started_evidence(self):
        agent,task=await self.create();agent.host_commit_task(task.task_id)
        value=feedback(agent,task);value["execution"]=execution(task,goal_observed=True,restoration_verified=True)
        with self.assertRaisesRegex(ContractError,"tactical_feedback_lifecycle"):agent.record_feedback(value)
        self.assertEqual(task.status,"dispatch_pending")


if __name__=="__main__":unittest.main(verbosity=2)
