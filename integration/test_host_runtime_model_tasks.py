"""Real model parser -> Host owner -> durable SQLite; explicit synthetic IO."""
import asyncio
from dataclasses import replace
import unittest
from unittest.mock import patch
from battle_host import Host
from battle_agent import BattleAgent
from engine import Binding,StrategyEngine
import fixtures
from host_runtime.capabilities import CapabilityCatalog
from host_runtime.contracts import ContractError
from host_runtime.model_tasks import ModelRuntimeTasks,native_choices
from types import SimpleNamespace
import test_host_runtime_host_tactical as tactical_fixtures
from test_host_runtime_tactical_adapter import uid


class ModelRuntimeComposition(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture=tactical_fixtures.HostTacticalCompositionTests();self.fixture.setUp();self.fixture.paid()
        self.host=self.fixture.host;self.runtime=self.fixture.runtime;self.transport=self.fixture.transport
        self.host.stop_requested=lambda:False
        b=self.runtime.binding
        self.host.engine=StrategyEngine(Binding(b.session_id,b.player_id,b.commander_id,'test',uid()))
        self.host.agent=BattleAgent(self.host.engine)
        self.scheduler=ModelRuntimeTasks(self.host);self.host.runtime_model_tasks=self.scheduler
        self.host.last_snapshot=fixtures.snapshot(at=100/15,session_id=b.session_id,player_id=b.player_id)
        self.transport.targets=lambda:{self.transport.point:(60,0,0)}
        self.transport.observe_actor=lambda b:dict(xyz=[0,0,0],settled=True,stance=2,team=20,script_team=20)
        self.transport.reserved_home=lambda task,lease:dict(xyz=[0,0,0])
        self.choices=[dict(target_point_id=self.transport.point,bearing_degrees=0,distance_units=60)]
        self.attach=patch('host_runtime.host_tactical.from_host',side_effect=self.fixture.factory);self.attach.start();self.addCleanup(self.attach.stop)
        self.planning=patch('host_runtime.model_tasks.native_choices',return_value=self.choices);self.planning_mock=self.planning.start();self.addCleanup(self.planning.stop)
        self.available=patch('host_runtime.model_tasks.paid_actor_available',return_value=True);self.available_mock=self.available.start();self.addCleanup(self.available.stop)

    def tearDown(self):self.fixture.tearDown()

    async def decide(self,*,duration=30):
        await self.scheduler.prepare(self.host.last_snapshot)
        async def model(context):
            o=context['runtime_opportunity']
            return fixtures.policy(context,valid_for_game_seconds=duration,runtime_task=dict(opportunity_id=o['opportunity_id'],purpose='move_hold_return',target_point_id=o['targets'][0]['target_point_id'],hold_frames=15))
        result=await self.host.agent.decide(self.host.last_snapshot,model)
        self.assertEqual(result.status,'accepted')
        return result

    async def test_model_exact_intent_reaches_real_owner_journal_and_feedback_without_repeat(self):
        result=await self.decide()
        self.assertEqual(self.transport.calls,[]) # opportunity attaches, never borrows
        await self.scheduler.dispatch()
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve','commit'])
        self.assertEqual(self.transport.calls[1]['payload']['target_point_id'],result.plan.runtime_task.target_point_id)
        self.assertEqual(self.transport.calls[1]['payload']['hold_frames'],15)
        rows=self.runtime.journal.commands_for_run(self.runtime.run_id)
        self.assertEqual([r['operation']for r in rows],['produce','reserve','commit'])
        sequences=[self.runtime.journal.get_native_sequence(self.runtime.run_id,r['command_id'])for r in rows]
        self.assertEqual(sequences,sorted(set(sequences)))
        self.assertEqual(self.runtime.journal.unresolved(self.runtime.run_id),[])
        self.assertEqual(self.scheduler.history[-1]['status'],'completed')
        feedback=self.host.agent.runtime_feedback[-1]
        self.assertTrue(feedback['physical_home']);self.assertTrue(feedback['control_released'])
        self.assertEqual(sum(self.host.agent.summary['completed_tasks'].values()),0)
        await self.scheduler.dispatch()
        self.host.last_snapshot=dict(self.host.last_snapshot,snapshot_id=2,game_time_seconds=8)
        await self.scheduler.prepare(self.host.last_snapshot);await self.scheduler.dispatch()
        self.assertEqual(len(self.transport.calls),2)

    async def test_stopped_agent_still_exposes_completed_local_task_history_without_coordinates(self):
        await self.decide();await self.scheduler.dispatch();self.host.agent.stop()
        jobs=self.host.public_jobs();local=[r for r in jobs if r['module']=='local_maneuver']
        self.assertEqual(len(local),1);self.assertEqual(local[0]['status'],'completed')
        self.assertTrue(local[0]['physical_home']);self.assertTrue(local[0]['control_released'])
        self.assertNotIn('target_point_id',local[0]);self.assertNotIn('opportunity_id',local[0])

    async def test_stale_exact_model_endpoint_stops_after_reserve_never_substitutes(self):
        await self.decide();self.transport.targets=lambda:{uid():(60,0,0)}
        await self.scheduler.dispatch()
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve','stop'])
        self.assertEqual(self.scheduler.history[-1]['reason_code'],'model_endpoint_no_longer_approved')
        self.assertFalse(self.host.agent.runtime_feedback[-1]['mission_effect_verified'])
        self.assertEqual(self.runtime.journal.unresolved(self.runtime.run_id),[])

    async def test_unknown_reserve_is_not_retried_by_dispatch_refresh_or_stop(self):
        await self.decide();self.transport.mode='error'
        with self.assertRaisesRegex(ContractError,'requires_reconciliation'):await self.scheduler.dispatch()
        command=self.runtime.journal.unresolved(self.runtime.run_id)[0]
        self.transport.poll=lambda:dict(command_id=command['command_id'])
        await self.scheduler.dispatch()
        with self.assertRaisesRegex(ContractError,'requires_reconciliation'):await self.scheduler.prepare(self.host.last_snapshot)
        with self.assertRaisesRegex(ContractError,'requires_reconciliation'):await self.host.stop_runtime_tactical()
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve'])
        self.assertEqual(self.runtime.journal.unresolved(self.runtime.run_id)[0]['status'],'uncertain')

    async def test_pause_or_stop_between_model_and_dispatch_cannot_borrow(self):
        await self.decide();self.host.last_snapshot['paused']=True
        await self.scheduler.dispatch();self.assertEqual(self.transport.calls,[])
        self.host.last_snapshot['paused']=False;self.host.stop_requested=lambda:True
        await self.scheduler.dispatch();self.assertEqual(self.transport.calls,[])

    async def test_no_move_grant_does_not_attach_or_expose_opportunity(self):
        grants=[g for g in self.runtime.evidence.catalog._grants if g.capability_id!='tactics.move_hold_return']
        self.runtime.evidence=replace(self.runtime.evidence,catalog=CapabilityCatalog.verify(self.runtime.binding,grants,lambda g,b:g))
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertIsNone(self.host.last_snapshot['runtime_opportunity']);self.assertIsNone(self.host.runtime_tactical)
        self.planning_mock.assert_not_called();self.assertEqual(self.transport.calls,[])

    async def test_no_fresh_native_home_window_never_reserves(self):
        self.planning_mock.return_value=[]
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertIsNone(self.host.last_snapshot['runtime_opportunity']);self.assertEqual(self.transport.calls,[])

    def delayed_reserve(self):
        submit=self.transport.submit
        def delayed(wire):
            row=submit(wire)
            if wire['operation']=='reserve':row.update(status='started',phase='braking')
            return row
        self.transport.submit=delayed

    async def test_pending_ready_waits_without_resending_then_commits_same_choice(self):
        await self.decide();self.delayed_reserve();await self.scheduler.dispatch()
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve'])
        await self.scheduler.prepare(self.host.last_snapshot);await self.scheduler.dispatch()
        self.assertEqual(len(self.transport.calls),1)
        self.transport.raw[-1].update(status='completed',phase='ready')
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve','commit'])
        self.assertEqual(self.scheduler.history[-1]['status'],'completed')

    async def test_sampling_wait_cannot_commit_when_ready_then_resumes_once_running(self):
        await self.decide();self.delayed_reserve();await self.scheduler.dispatch()
        self.transport.raw[-1].update(status='completed',phase='ready')
        self.host.phase='sampling_wait'
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve'])
        self.host.phase='running';await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve','commit'])

    async def test_ungrounded_idle_actor_refuses_planning_without_game_action_or_host_fault(self):
        self.host.session=dict(pid=self.runtime.binding.game_process_id)
        owner=self.host.attach_runtime_actor(self.fixture.fixture.task)
        self.transport.planning_actor=lambda:object()
        self.transport.observe_planning_actor=lambda b:dict(frame=2142,identity=True,birth_verified=True,
            live=True,grounded=False,paused=False,state_id=77,command_source=0)
        self.transport.targets=lambda:(_ for _ in ()).throw(AssertionError('No endpoint admission when unavailable'))
        window=SimpleNamespace(begin=lambda *a,**kw:None)
        with patch('battle_host.Memory') as memory,patch('tactical_bridge.module',return_value=SimpleNamespace(HomeWindow=lambda *a:window)):
            self.assertEqual(native_choices(self.host,owner),[])
            memory.return_value.close.assert_called_once()
        self.assertEqual(self.transport.calls,[])

    async def test_expired_plan_after_ready_stops_without_commit(self):
        result=await self.decide();self.delayed_reserve();await self.scheduler.dispatch()
        self.host.last_snapshot['game_time_seconds']=result.plan.expires_at_game_seconds
        self.transport.raw[-1].update(status='completed',phase='ready')
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve','stop'])
        self.assertEqual(self.scheduler.history[-1]['reason_code'],'plan_expired_before_commit')

    async def test_late_native_ready_cannot_use_a_stale_host_snapshot_to_commit(self):
        await self.decide(duration=5);self.delayed_reserve();await self.scheduler.dispatch()
        # Native Ready happened before the plan expired. The Host's strategic
        # snapshot is old, while the fresh native clock is now past its expiry.
        self.transport.snapshot=replace(self.transport.snapshot,game_frame=200,monotonic_ms=7000)
        self.transport.raw[-1].update(status='completed',phase='ready',game_frame=160,monotonic_ms=5000)
        submit=self.transport.submit
        def current_clock(wire):
            raw=submit(wire);raw.update(game_frame=201,monotonic_ms=7000);return raw
        self.transport.submit=current_clock
        try:await self.scheduler.prepare(self.host.last_snapshot)
        except ContractError:
            self.fail(str([(r['operation'],r['status'],r.get('receipt'))for r in self.runtime.journal.commands_for_run(self.runtime.run_id)]))
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve','stop'])
        self.assertEqual(self.scheduler.history[-1]['reason_code'],'plan_expired_before_commit')

    async def test_current_native_pause_or_expiry_prevents_reserve_even_with_old_unpaused_host_snapshot(self):
        await self.decide();self.transport.snapshot=replace(self.transport.snapshot,paused=True)
        await self.scheduler.dispatch();self.assertEqual(self.transport.calls,[])
        self.transport.snapshot=replace(self.transport.snapshot,paused=False,game_frame=1000)
        await self.scheduler.dispatch();self.assertEqual(self.transport.calls,[])

    async def test_actual_host_stop_projects_release_to_local_feedback_without_goal_credit(self):
        await self.decide();self.delayed_reserve();await self.scheduler.dispatch()
        await self.host.stop_runtime_tactical()
        self.assertEqual([c['operation']for c in self.transport.calls],['reserve','stop'])
        self.assertEqual(self.scheduler.history[-1]['reason_code'],'host_stopped')
        self.assertTrue(self.host.agent.runtime_feedback[-1]['control_released'])
        self.assertFalse(self.host.agent.runtime_feedback[-1]['mission_effect_verified'])

if __name__=='__main__':unittest.main()
