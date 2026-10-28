"""Injected wall clock and synthetic native IO across real Host/SQLite tasks."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from host_runtime.capabilities import CapabilityCatalog
from host_runtime.contracts import ContractError
from host_runtime.host_tactical import HostTactical
from test_host_runtime_tactical_adapter import Transport,uid
import test_host_runtime_model_tasks as model_fixtures

class ModelLifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f=model_fixtures.ModelRuntimeComposition();self.f.setUp()
        self.host=self.f.host;self.scheduler=self.f.scheduler;self.runtime=self.f.runtime
        self.now=0;self.scheduler.clock_ms=lambda:self.now
        self.closed=[];self.resumed=[]
        def suspend():
            old=self.host.runtime_tactical;old.shutdown();self.closed.append(old.run_id)
            self.host.runtime_tactical_retirement=SimpleNamespace(run_id=old.run_id)
            self.host.runtime_tactical_rotation_attempted=True
            return dict(state='retired_waiting_successor')
        self.host.suspend_runtime_tactical=suspend

    def tearDown(self):self.f.tearDown();self.f.doCleanups()

    async def idle_retire(self):
        self.f.planning_mock.return_value=[]
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertIsNotNone(self.host.runtime_tactical)
        self.now=30000;await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual(len(self.closed),1);self.assertTrue(self.f.transport.closed)
        self.assertEqual(self.f.transport.calls,[])

    def fresh_paid(self):
        task=uid();request=uid()
        row=self.runtime.journal.reserve_command(self.runtime.run_id,request,'produce',dict(task_id=task,unit='conscript'))
        self.runtime.journal.mark_dispatching(self.runtime.run_id,request)
        self.runtime.journal.reserve_native_sequence(self.runtime.run_id,row['command_id'],0)
        self.runtime.journal.record_outcome(self.runtime.run_id,request,'completed',dict(facts=dict(object_id=802,paid=85)))
        self.host.sent[task]=dict(kind='runtime_production',request_id=request,command_id=row['command_id'],terminal=True)
        return task,row

    def resume_fake(self,task):
        self.resumed.append(task);entry=self.host.sent[task]
        binding=replace(self.runtime.binding,host_id=uid());transport=Transport(binding)
        transport.actor=replace(transport.actor,producer_command_id=entry['command_id'],identity=replace(transport.actor.identity,object_id=802))
        submit=transport.submit
        def correlated(wire):
            row=submit(wire);row['object_id']=802;return row
        transport.submit=correlated;transport.poll=lambda:transport.raw[-1]
        transport.started_ms=self.now;transport.closed=False;transport.close=lambda:setattr(transport,'closed',True)
        transport.targets=lambda:{transport.point:(60,0,0)}
        transport.observe_actor=lambda b:dict(xyz=[0,0,0],settled=True,stance=2,team=20,script_team=20)
        transport.reserved_home=lambda task,lease:dict(xyz=[0,0,0])
        catalog=CapabilityCatalog.verify(binding,self.runtime.evidence.catalog._grants,lambda grant,b:grant)
        owner=HostTactical(self.runtime.journal,uid(),binding,catalog,test_transport=transport)
        owner.actor=transport.actor;owner.producer_command_id=entry['command_id']
        self.host.runtime_tactical=owner;self.host.runtime_tactical_retirement=None;self.host.runtime_tactical_rotation_attempted=False
        self.f.planning_mock.return_value=[dict(target_point_id=transport.point,bearing_degrees=0,distance_units=60)]
        return owner

    async def test_thirty_second_no_readiness_closes_once_and_waits_past180_without_native_io(self):
        await self.idle_retire()
        self.now=190000
        with patch.object(self.host.runtime_tactical,'poll',side_effect=AssertionError('Retired IO')):
            await self.host.receive_runtime_tactical();await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual(len(self.closed),1);self.assertEqual(self.f.transport.calls,[])
        self.assertEqual(self.host.last_snapshot['runtime_preparation']['state'],'retired_waiting_paid_unit')
        self.assertIsNone(self.host.last_snapshot['runtime_opportunity']);self.assertFalse(self.scheduler.blocks_production())

    async def test_later_new_paid_actor_runs_model_task_in_fresh_binding_and_keeps_global_sequences(self):
        await self.idle_retire();self.now=190000;task,row=self.fresh_paid()
        self.host.resume_runtime_tactical=self.resume_fake
        self.host.last_snapshot=dict(self.host.last_snapshot,snapshot_id=2)
        await self.f.decide();await self.scheduler.dispatch()
        owner=self.host.runtime_tactical
        self.assertEqual(self.resumed,[task]);self.assertNotEqual(owner.binding.host_id,self.runtime.binding.host_id)
        self.assertEqual(owner.actor.identity.object_id,802)
        self.assertEqual([r['operation']for r in owner.transport.calls],['reserve','commit'])
        self.assertEqual(self.f.transport.calls,[]);self.assertEqual(self.scheduler.history[-1]['status'],'completed')
        sequences=[self.runtime.journal.get_native_sequence(r['run_id'],r['command_id'])for run in (self.runtime.run_id,owner.run_id)
            for r in self.runtime.journal.commands_for_run(run)if r['operation']in ('produce','reserve','commit')]
        self.assertEqual(sequences,sorted(set(sequences)))

    async def test_production_barrier_pauses_new_builds_until_closed_then_unlocks(self):
        self.f.planning_mock.return_value=[];await self.scheduler.prepare(self.host.last_snapshot)
        suspend=self.host.suspend_runtime_tactical;calls=[]
        def barrier():
            calls.append(True)
            if len(calls)==1:raise ContractError('runtime_tactical_waiting_production_or_control_barrier')
            return suspend()
        self.host.suspend_runtime_tactical=barrier;self.now=30000
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertTrue(self.scheduler.blocks_production())
        count=len(self.f.fixture.fixture.executor.calls);await self.host.dispatch()
        self.assertEqual(len(self.f.fixture.fixture.executor.calls),count)
        self.now=31000;await self.scheduler.prepare(self.host.last_snapshot)
        self.assertFalse(self.scheduler.blocks_production());self.assertEqual(len(self.closed),1)

    async def test_ninety_second_channel_will_not_reserve_a_new_model_task(self):
        await self.f.decide();self.now=90000;await self.scheduler.dispatch()
        self.assertEqual(self.f.transport.calls,[]);self.assertTrue(self.scheduler.blocks_production())
        await self.scheduler.prepare(self.host.last_snapshot);self.assertEqual(len(self.closed),1)

    async def test_active_task_gets_one_stop_before_native_hard_limit(self):
        await self.f.decide();self.f.delayed_reserve();await self.scheduler.dispatch()
        self.now=120000;await self.scheduler.advance();await self.scheduler.advance()
        self.assertEqual([c['operation']for c in self.f.transport.calls],['reserve','stop'])
        self.assertEqual(self.scheduler.history[-1]['reason_code'],'native_channel_budget')
        self.assertFalse(self.host.agent.runtime_feedback[-1]['mission_effect_verified'])

    async def test_unavailable_paid_unit_does_not_install_native_channel(self):
        self.f.available_mock.return_value=False
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertIsNone(self.host.runtime_tactical);self.assertEqual(self.f.transport.calls,[])
        self.assertEqual(self.host.last_snapshot['runtime_preparation']['paid_units_available'],1)

    async def test_unavailable_paid_candidate_wait_is_bounded_without_installed_hooks(self):
        self.f.available_mock.return_value=False
        await self.scheduler.prepare(self.host.last_snapshot);self.now=30000
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertIsNone(self.host.runtime_tactical);self.assertEqual(self.closed,[])
        self.assertEqual(self.host.last_snapshot['runtime_preparation']['paid_units_available'],0)
        self.now=190000;await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual(self.f.transport.calls,[]);self.assertIsNone(self.host.runtime_tactical)

    async def test_regressed_wall_clock_cannot_extend_channel_lifetime(self):
        await self.scheduler.prepare(self.host.last_snapshot)
        self.now=1000;self.scheduler.channel_age();self.now=999
        with self.assertRaisesRegex(ContractError,'clock_regressed'):self.scheduler.channel_age()

    async def test_unused_older_paid_actor_cannot_follow_a_later_retired_producer(self):
        await self.idle_retire()
        older_task,older=self.fresh_paid();newest_task,newest=self.fresh_paid()
        self.host.runtime_tactical.producer_command_id=newest['command_id']
        self.scheduler.exhausted.add(newest['command_id'])
        self.host.resume_runtime_tactical=self.resume_fake
        self.f.available_mock.reset_mock();self.now=190000
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual(self.resumed,[]);self.f.available_mock.assert_not_called()
        self.assertEqual(self.host.last_snapshot['runtime_preparation']['state'],'retired_waiting_paid_unit')
        self.assertEqual(self.host.last_snapshot['runtime_preparation']['paid_units_available'],0)
        later_task,later=self.fresh_paid()
        await self.scheduler.prepare(self.host.last_snapshot)
        self.assertEqual(self.resumed,[later_task]);self.assertIsNotNone(self.scheduler.opportunity)

if __name__=='__main__':unittest.main()
