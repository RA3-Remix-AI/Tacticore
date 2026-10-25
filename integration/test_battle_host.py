"""Local host-boundary tests; no credentials, model endpoint or game process."""
import asyncio
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import uuid

import battle_host


class Agent:
    def __init__(self,jobs):self.proposals=jobs;self.feedback=[];self.goals=types.SimpleNamespace(tasks=[])
    def jobs(self):return {"jobs":copy.deepcopy(self.proposals)}
    def record_feedback(self,value):self.feedback.append(copy.deepcopy(value))
    def observe(self,value):return value
    def stop(self):self.stopped=True


class Executor:
    def __init__(self):self.commands=[];self.ledger=[];self.reply="queued"
    def submit(self,command):
        self.commands.append(copy.deepcopy(command))
        return dict(status=self.reply,accepted=self.reply=="queued",task_id=command["task_id"],command_id=command["command_id"],seq=command["seq"],queue_id=17)
    def status(self):return dict(native_phase=1,native_error=0,local_error=None,ledger=copy.deepcopy(self.ledger),spent_committed=0)
    def start(self):return dict(state="running",native_phase=1,native_error=0,personality_binding_verified=True)
    def stop(self):return dict(native_phase=2,restore_mask=31,active_callbacks=0)


class HostBoundaries(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        host=self.host=battle_host.Host.__new__(battle_host.Host)
        self.task=str(uuid.uuid4());host.binding=types.SimpleNamespace(session_id=str(uuid.uuid4()),player_id=3,commander_id=str(uuid.uuid4()))
        job=dict(task_id=self.task,plan_id=str(uuid.uuid4()),generation=1,host_dispatch_candidate=True,module="build",focus="anti_air",expires_at_game_seconds=130,budget={"fraction":.8})
        host.agent=Agent([job]);host.executor=Executor();host.executor_ready=True
        host.last_snapshot=dict(snapshot_id=1,game_time_seconds=100,paused=False,resources={"credits":5000,"power_balance":None},production={"own_roles":{"anti_air":0,"infantry":4}})
        host.evidence={"supported_foci":("anti_air",)};host.args=types.SimpleNamespace(execute=True,total_budget=2000,reserve=1500,session=self.root/"session.json")
        host.sent={};host.sequence=0;host.output=self.root;host.events=[];host.phase="running";host.reason="observing"
        host.counters=dict(dispatches=0,started=0,completed=0,failed=0,blocked=0)
        host.remaining_budget=2000;host.collector=types.SimpleNamespace(foci=("native_baseline","anti_air"))
        host.session={"pid":123,"scenario":{"participant_count":2}};host.engine=types.SimpleNamespace(metrics={})
        host.event=lambda kind,**fields:host.events.append({"kind":kind,**fields})

    async def asyncTearDown(self):self.temp.cleanup()

    async def test_paused_never_dispatches_or_records_started(self):
        self.host.last_snapshot["paused"]=True
        await self.host.dispatch()
        self.assertEqual(self.host.executor.commands,[]);self.assertEqual(self.host.sent,{})
        self.assertEqual(self.host.agent.feedback,[])

    async def test_same_job_is_dispatched_once_and_pending_is_persisted(self):
        original=self.host.executor.submit
        def submit(command):
            ledger=json.loads((self.root/"dispatch-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger[self.task]["command_id"],command["command_id"])
            return original(command)
        self.host.executor.submit=submit
        await self.host.dispatch();await self.host.dispatch()
        self.assertEqual(len(self.host.executor.commands),1)
        self.assertEqual([x["status"] for x in self.host.agent.feedback],["started"])

    async def test_unknown_outcome_faults_and_cannot_be_retried(self):
        self.host.executor.reply="unknown"
        with self.assertRaises(RuntimeError):await self.host.dispatch()
        self.assertEqual(self.host.phase,"fault");self.assertEqual(self.host.reason,"dispatch_outcome_unknown")
        await self.host.dispatch()
        self.assertEqual(len(self.host.executor.commands),1)
        self.assertFalse(any(x["status"]=="completed" for x in self.host.agent.feedback))

    async def test_expired_and_unverified_jobs_are_not_dispatched(self):
        self.host.agent.proposals[0]["expires_at_game_seconds"]=100
        await self.host.dispatch()
        self.host.agent.proposals[0]["expires_at_game_seconds"]=130;self.host.agent.proposals[0]["focus"]="anti_armor"
        await self.host.dispatch()
        self.assertEqual(self.host.executor.commands,[])

    async def test_insufficient_budget_is_blocked_before_native_submit(self):
        self.host.last_snapshot["resources"]["credits"]=100
        await self.host.dispatch()
        self.assertEqual(self.host.executor.commands,[])
        self.assertEqual(self.host.agent.feedback[0]["status"],"blocked")
        self.assertEqual(self.host.agent.feedback[0]["reason_code"],"insufficient_funds")

    async def accepted_command(self):
        await self.host.dispatch()
        self.host.agent.feedback.clear()
        return self.host.executor.commands[0]

    def completed_receipt(self,command):
        return dict(task_id=command["task_id"],command_id=command["command_id"],seq=command["seq"],queue_id=17,accepted=True,object_id=123,status="completed",completed=True,paid_verified=True,created=True,completion_observed=True,live_samples=1,payment_error=0,paid=220,cost=220,queue_preserved=True)

    async def test_complete_receipt_requires_all_correlation_checks_and_is_counted_once(self):
        command=await self.accepted_command();self.host.executor.ledger=[self.completed_receipt(command)]
        await self.host.receive_receipts();await self.host.receive_receipts()
        self.assertEqual([x["status"] for x in self.host.agent.feedback],["completed"])
        self.assertEqual(self.host.counters["completed"],1)

    async def test_spoofed_or_incomplete_completed_receipt_never_reports_success(self):
        command=await self.accepted_command();valid=self.completed_receipt(command)
        for change in [{"command_id":str(uuid.uuid4())},{"seq":command["seq"]+1},{"queue_id":18},{"queue_id":0},{"accepted":False},{"object_id":0},{"paid":219},{"cost":0},{"cost":True},{"queue_preserved":False},{"paid_verified":False},{"created":False},{"completion_observed":False},{"live_samples":0},{"payment_error":1},{"completed":False}]:
            self.host.sent[self.task]["terminal"]=False;self.host.agent.feedback.clear()
            receipt=copy.deepcopy(valid);receipt.update(change);self.host.executor.ledger=[receipt]
            with self.subTest(change=change):
                try:await self.host.receive_receipts()
                except RuntimeError:pass  # Faulting on corrupted correlation is safe.
                self.assertFalse(any(x["status"]=="completed" for x in self.host.agent.feedback))

    async def test_multiple_live_barracks_do_not_permanently_prevent_connection(self):
        self.host.executor=None;self.host.executor_ready=False
        self.host.collector=types.SimpleNamespace(latest_snapshot_path=self.root/"raw.json")
        factories=[dict(template="SovietBarracks",production_interface_available=True,address="0x100000",hp=100),dict(template="SovietBarracks",production_interface_available=True,address="0x200000",hp=100)]
        (self.root/"own-state.json").write_text(json.dumps({"factories":factories}),encoding="utf-8")
        self.host.natural_path=self.root/"natural.json";self.host.natural_path.write_text("{}",encoding="utf-8")
        self.host.observer=None;self.host.observer_output=None;created=[]
        def constructor(*args,**kwargs):
            created.append(args);return Executor()
        with patch.object(battle_host,'production_executor_type',return_value=constructor):await self.host.connect_executor()
        self.assertTrue(self.host.executor_ready);self.assertEqual(len(created),1)
        self.assertIn(created[0][2],{x["address"] for x in factories})

    async def test_executor_runtime_exception_is_published_as_fault_and_restores(self):
        host=self.host;host.started=time.monotonic();host.args.max_wall_seconds=1;host.args.interval=.01
        host.pending=None;host.observer=None;host.observer_output=None
        host.stop_requested=lambda:False
        host.collector=types.SimpleNamespace(collect=lambda:copy.deepcopy(host.last_snapshot),native={"result_records":[]})
        published=[];host.publish=lambda:published.append({"state":host.phase,"reason_code":host.reason})
        def failed_status():raise RuntimeError("executor_lost")
        host.executor.status=failed_status
        with patch.object(battle_host,"player_lease",return_value=nullcontext()):
            try:await host.run()
            except RuntimeError:pass
        self.assertTrue(host.agent.stopped);self.assertTrue(published)
        self.assertEqual(published[-1]["state"],"fault")
        self.assertNotEqual(published[-1]["reason_code"],"observing")

    async def test_budget_exhaustion_removes_foci_after_active_receipt_is_done(self):
        self.host.executor.status=lambda:dict(native_phase=1,native_error=0,local_error=None,spent_committed=2000,ledger=[])
        self.host.agent.goals.tasks=[types.SimpleNamespace(status="active")]
        await self.host.receive_receipts()
        self.assertEqual(self.host.remaining_budget,0);self.assertIn("anti_air",self.host.collector.foci)
        self.host.agent.goals.tasks=[];await self.host.receive_receipts()
        self.assertEqual(self.host.collector.foci,("native_baseline",))

    async def test_multiplayer_elimination_is_not_automatic_match_end(self):
        state={"result_records":[{"victory_frame":0,"defeat_frame":1500}]}
        self.host.session["scenario"]["participant_count"]=4
        self.assertFalse(self.host.has_result_candidate(state))
        self.host.session["scenario"]["participant_count"]=2
        self.assertTrue(self.host.has_result_candidate(state))
        self.host.session={};self.assertFalse(self.host.has_result_candidate(state))

    async def test_cleanup_result_reads_native_state_without_own_objects(self):
        state={"result_records":[{"victory_frame":1600,"defeat_frame":0}]};closed=[]
        memory=types.SimpleNamespace(read=lambda *args:None,close=lambda:closed.append(True))
        with patch.object(battle_host,"Memory",return_value=memory),patch.object(battle_host,"native_match_snapshot",return_value=state):
            self.assertTrue(await self.host.read_result_candidate())
        self.assertEqual(closed,[True]);self.assertEqual(self.host.collector.native,state)
        self.assertTrue((self.root/"result-native-state.json").is_file())

    async def test_sampling_cleanup_error_becomes_candidate_pending_visual_confirmation(self):
        host=self.host;host.started=time.monotonic();host.args.max_wall_seconds=1;host.args.interval=.01
        host.pending=None;host.observer=None;host.observer_output=None;host.stop_requested=lambda:False
        def collect():raise ValueError("No unique owned player in match")
        host.collector=types.SimpleNamespace(collect=collect)
        async def candidate():return True
        host.read_result_candidate=candidate;published=[];host.publish=lambda:published.append({"state":host.phase,"reason_code":host.reason})
        with patch.object(battle_host,"player_lease",return_value=nullcontext()):result=await host.run()
        self.assertEqual(result["state"],"result_candidate")
        self.assertEqual(published[-1]["reason_code"],"native_result_requires_visual_confirmation")
        self.assertEqual(host.executor.commands,[])

    async def test_real_agent_feedback_lifecycle_survives_refresh_and_can_build_next_job(self):
        # Exercise the actual finite-contract Agent with a fake native boundary.
        # This catches integration errors hidden by the simple feedback recorder.
        from fixtures import binding,snapshot,policy
        host=self.host;host.binding=binding()
        host.engine=battle_host.StrategyEngine(host.binding)
        evidence=battle_host.BuildEvidence(str(uuid.uuid4()),host.binding.session_id,3,"game_bridge")
        host.agent=battle_host.BattleAgent(host.engine,build_evidence=evidence)
        async def model(context):return policy(context)
        first=snapshot(source="game_bridge",events=[])
        host.last_snapshot=first;await host.agent.decide(first,model)
        await host.dispatch();first_command=host.executor.commands[0]
        await host.dispatch();self.assertEqual(len(host.executor.commands),1)
        update=snapshot(2,116,source="game_bridge",events=[])
        host.last_snapshot=update;await host.agent.decide(update,model)
        await host.dispatch();self.assertEqual(len(host.executor.commands),1)
        host.executor.ledger=[self.completed_receipt(first_command)]
        await host.receive_receipts();await host.dispatch()
        self.assertEqual(host.counters["completed"],1);self.assertEqual(len(host.executor.commands),2)
        self.assertNotEqual(host.executor.commands[0]["task_id"],host.executor.commands[1]["task_id"])
        await host.dispatch();self.assertEqual(len(host.executor.commands),2)

    async def test_result_branch_drains_last_completed_into_real_memory_before_stop(self):
        from fixtures import binding,snapshot,policy
        host=self.host;host.binding=binding();host.engine=battle_host.StrategyEngine(host.binding)
        evidence=battle_host.BuildEvidence(str(uuid.uuid4()),host.binding.session_id,3,"game_bridge")
        memory_path=self.root/"agent-state.json"
        host.agent=battle_host.BattleAgent(host.engine,build_evidence=evidence,memory_path=memory_path,jobs_path=self.root/"jobs.json")
        async def model(context):return policy(context)
        first=snapshot(source="game_bridge",events=[]);host.last_snapshot=first
        await host.agent.decide(first,model);await host.dispatch()
        command=host.executor.commands[0];task_id=command["task_id"]
        arrived=asyncio.Event()
        async def pending_model(context):arrived.set();await asyncio.Event().wait()
        second=snapshot(2,116,source="game_bridge",events=[]);host.last_snapshot=second
        host.pending=asyncio.create_task(host.agent.decide(second,pending_model));await arrived.wait()
        third=snapshot(3,117,source="game_bridge",events=[])
        host.collector=types.SimpleNamespace(collect=lambda:third,native={"result_records":[{"victory_frame":1755,"defeat_frame":0}]},foci=("native_baseline","anti_air"))
        receipt=self.completed_receipt(command)
        host.executor.status=lambda:dict(native_phase=2,restore_mask=31,active_callbacks=0,native_error=0,local_error=None,spent_committed=220,ledger=[receipt])
        host.started=time.monotonic();host.args.max_wall_seconds=1;host.args.interval=.01
        host.observer=None;host.observer_output=None;host.stop_requested=lambda:False;published=[]
        host.publish=lambda:published.append({"state":host.phase,"completed":host.counters["completed"]})
        actual_stop=host.agent.stop;stop_observations=[]
        def stop():
            # A stopped Agent cancels unfinished tasks. The final receipt must
            # already be persisted as completed before that transition occurs.
            persisted=json.loads(memory_path.read_text(encoding="utf-8"))
            stop_observations.append({"pending_cancelled":host.pending.cancelled(),"engine_stopped":host.engine.stopped,"completed":[record for record in persisted["recent_execution_feedback"] if record["status"]=="completed"]})
            actual_stop()
        host.agent.stop=stop
        with patch.object(battle_host,"player_lease",return_value=nullcontext()):result=await host.run()
        self.assertEqual(result["state"],"result_candidate");self.assertEqual(host.counters["completed"],1)
        self.assertEqual(len(stop_observations),1);self.assertTrue(stop_observations[0]["pending_cancelled"])
        self.assertFalse(stop_observations[0]["engine_stopped"])
        self.assertEqual(stop_observations[0]["completed"][0]["task_id"],task_id)
        persisted=json.loads(memory_path.read_text(encoding="utf-8"))
        self.assertTrue(host.engine.stopped);self.assertEqual(published[-1]["completed"],1)
        terminal=[task for task in persisted["task_history"]+persisted["active_goals"] if task["task_id"]==task_id]
        self.assertEqual(terminal[0]["status"],"completed")
        self.assertFalse(any(event["kind"]=="terminal_feedback_incomplete" for event in host.events))

    async def test_stopped_executor_without_verified_restoration_cannot_drain_success(self):
        command=await self.accepted_command();receipt=self.completed_receipt(command)
        restored=dict(native_phase=2,restore_mask=31,active_callbacks=0,native_error=0,local_error=None,spent_committed=220,ledger=[receipt])
        variants=[{"restore_mask":30},{"active_callbacks":1},{"native_error":1},{"native_phase":4}]
        for change in variants:
            status=copy.deepcopy(restored);status.update(change)
            self.host.executor.status=lambda value=status:value
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,"executor_lost"):
                await self.host.receive_receipts(allow_stopped=True)
            self.assertEqual(self.host.agent.feedback,[]);self.assertFalse(self.host.sent[self.task]["terminal"])
        self.host.executor.status=lambda:restored
        with self.assertRaisesRegex(RuntimeError,"executor_lost"):await self.host.receive_receipts()
        self.assertEqual(self.host.agent.feedback,[])


if __name__=="__main__":unittest.main(verbosity=2)
