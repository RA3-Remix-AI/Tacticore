"""Real persistent strategy/bridge with fake transport; zero native/model calls."""
import unittest
import hashlib
from pathlib import Path
from unittest.mock import Mock,patch
import uuid

import battle_host  # Establish the same explicit strategy import boundary as the host.
from battle_agent import BattleAgent,TacticalEvidence,MissionEvidence
from engine import StrategyEngine
from tactical_fixtures import tactical_policy,tactical_snapshot
import tactical_bridge as bridge_module
import test_tactical_bridge as primitive_fixture
from continuous_contract import PROTOCOL


class ContinuousHostBoundaries(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=primitive_fixture.TacticalHostBoundaries()
        await self.fixture.asyncSetUp()
        f=self.fixture;self.host=f.host;self.bridge=f.bridge;self.executor=f.executor
        b=self.host.binding;purposes=(('attack',('main_attack',)),)
        proof=TacticalEvidence(str(uuid.uuid4()),b.session_id,3,'game_bridge',purposes,(('attack','main_attack',('infantry',)),))
        mission=MissionEvidence(str(uuid.uuid4()),b.session_id,3,b.commander_id,'game_bridge',purposes)
        self.host.engine=StrategyEngine(b);self.host.agent=BattleAgent(self.host.engine,tactical_evidence=proof,mission_evidence=mission)
        async def model(context):return tactical_policy(context)
        await self.host.agent.decide(self.host.last_snapshot,model)
        self.task=next(t for t in self.host.agent.goals.tasks if t.request.module=='attack');f.task=self.task
        self.bridge.evidence=dict(grants=[dict(module='attack',purpose='main_attack',executor_directory='mission-combat',stop_schema=dict(mission_protocol=PROTOCOL,mission_duration_frames=4500))])
        self.host.collector.private_targets={'contact_ore':dict(object_id=777,type_hash='0xc45aaeab',owner_player_id=4,xyz=[1000.,1000.,210.],observed_frame=1500)}
        original=self.executor.submit
        def submit(request):
            result=original(request)
            if result.get('status')=='no_dispatch_rejected':
                result.update({key:request[key] for key in ('command_id','task_id','seq','session_id','player_id','commander_id')})
                result.update(no_dispatch_verified=True,dispatch_attempted=False)
            return result
        self.executor.submit=submit

    async def asyncTearDown(self):await self.fixture.asyncTearDown()

    async def dispatch(self):await self.bridge.dispatch();return self.executor.commands[-1]

    async def test_commit_has_independent_deadline_and_context_not_model_coordinates(self):
        command=await self.dispatch();entry=self.bridge.sent[self.task.task_id]
        self.assertEqual(entry['expires_frame'],6000)
        self.assertEqual(command['mission_deadline_game_seconds'],400)
        self.assertEqual(self.host.agent.missions.active[self.task.task_id].deadline_game_seconds,400)
        self.assertEqual(len(self.executor.context),6)
        self.assertNotIn('target_xyz',command)

    async def test_plan_ttl_expiry_does_not_duplicate_or_release_active_mission(self):
        await self.dispatch();snapshot=tactical_snapshot(2,160);snapshot['source']='game_bridge'
        self.host.last_snapshot=snapshot;self.host.agent.observe(snapshot)
        await self.bridge.dispatch()
        self.assertEqual(len(self.executor.commands),1)
        self.assertEqual(self.task.status,'dispatch_pending')
        self.assertTrue(self.fixture.roster.reserved)
        self.assertEqual(self.host.agent.missions.active[self.task.task_id].deadline_game_seconds,400)

    async def test_actual_started_accepts_mission_window_but_rejects_changed_deadline(self):
        await self.dispatch();receipt=self.fixture.receipt()
        self.executor.ledger=[receipt];await self.bridge.receive()
        self.assertEqual(self.task.status,'active')
        receipt['execution']['expires_frame']+=1;self.executor.ledger=[receipt]
        with self.assertRaises(ValueError):await self.bridge.receive()

    async def test_no_dispatch_refusal_cancels_without_fake_native_stage(self):
        self.executor.reply='no_dispatch_rejected';await self.bridge.dispatch()
        self.assertEqual(self.task.status,'cancelled');self.assertFalse(self.fixture.roster.reserved)
        self.assertFalse(self.host.agent.missions.active)
        history=self.host.agent.missions.history[-1]
        self.assertEqual(history['phase'],'reserved');self.assertEqual(history['progress_seq'],0)
        self.assertTrue(history['observations']['no_dispatch_verified'])
        self.assertFalse(history['observations']['retreat_verified'])

    async def test_foreign_or_ambiguous_rejection_ack_preserves_control_lock(self):
        self.executor.submit=lambda request:dict(status='no_dispatch_rejected',accepted=False,started=False,completed=False)
        with self.assertRaisesRegex(ValueError,'rejection identity'):await self.bridge.dispatch()
        self.assertTrue(self.fixture.roster.reserved);self.assertEqual(self.task.status,'dispatch_pending')

    async def test_retreat_request_is_once_and_keeps_roster_until_native_return(self):
        await self.dispatch();self.executor.request_mission_retreat=Mock(return_value=dict(accepted=True))
        self.host.agent.request_mission_retreat(self.task.task_id,'replan')
        await self.bridge.receive();await self.bridge.receive()
        self.executor.request_mission_retreat.assert_called_once_with(self.task.task_id,'replan')
        self.assertTrue(self.fixture.roster.reserved);self.assertEqual(self.task.status,'dispatch_pending')

    async def test_queued_cancel_requires_bound_pre_wrapper_certificate(self):
        await self.dispatch();entry=self.bridge.sent[self.task.task_id]
        receipt=self.fixture.receipt('cancelled');receipt.update(started=False,issued_frame=0,dispatch_attempted=False,wrapper_attempted=False,no_dispatch_verified=True)
        receipt['pre_dispatch']={key:entry[key] for key in ('command_id','task_id','seq','object_ids')}
        receipt['pre_dispatch'].update(session_id=self.host.binding.session_id,commander_id=self.host.binding.commander_id,player_id=3,protocol='executor_queue_rejection_v1',stage='queued_before_wrapper',wrapper_attempted=False,dispatch_attempted=False,native_launch_intent_persisted=False,active_report=None,client_sha256=hashlib.sha256((Path(__file__).resolve().parents[1]/'tactical/client.py').read_bytes()).hexdigest(),reason_code='cancelled')
        receipt['pre_dispatch']['seq']+=1;self.executor.ledger=[receipt]
        with self.assertRaisesRegex(ValueError,'queue refusal identity'):await self.bridge.receive()
        self.assertTrue(self.fixture.roster.reserved)
        receipt['pre_dispatch']['seq']=entry['seq'];self.executor.ledger=[receipt]
        await self.bridge.receive()
        self.assertEqual(self.task.status,'cancelled');self.assertFalse(self.fixture.roster.reserved)
        self.assertEqual(self.bridge.counters['attack']['completed'],0)

    async def test_completed_status_without_raw_effect_cannot_unlock_or_count_success(self):
        await self.dispatch();self.executor.ledger=[self.fixture.receipt('completed')]
        with self.assertRaises(ValueError):await self.bridge.receive()
        self.assertEqual(self.bridge.counters['attack']['completed'],0)
        self.assertTrue(self.fixture.roster.reserved)

    async def test_failed_status_cannot_release_without_native_phase_or_disposal_proof(self):
        await self.dispatch();receipt=self.fixture.receipt('failed')
        receipt['execution']['restoration_verified']=True;receipt['restoration_verified']=True
        self.executor.ledger=[receipt]
        with self.assertRaisesRegex(ValueError,'terminal phase evidence'):await self.bridge.receive()
        self.assertTrue(self.fixture.roster.reserved)
        self.assertFalse(self.bridge.sent[self.task.task_id]['terminal'])

    async def test_progress_damage_stays_unverified_and_repeated_poll_is_idempotent(self):
        await self.dispatch();raw=tactical_snapshot(2,101);raw['source']='game_bridge';self.host.last_snapshot=raw;self.host.agent.observe(raw)
        receipt=self.fixture.receipt();receipt['mission']=dict(mission_id=str(uuid.UUID(self.task.task_id)),stage='engage',revision=12,observed_frame=1505,deadline_frame=6000,approach_distance=120.,own_hp=80.,damage=5.,reason='active')
        self.executor.ledger=[receipt]
        with patch.object(bridge_module,'progress_evidence',return_value=dict(sha256='a'*64)):
            await self.bridge.receive();await self.bridge.receive()
        mission=self.host.agent.missions.active[self.task.task_id]
        self.assertEqual(mission.progress_seq,12)
        self.assertEqual(mission.reported_damage,5)
        self.assertEqual(mission.observations.source_damage_amount,0)
        self.assertEqual(self.bridge.counters['attack']['completed'],0)
        self.assertEqual(len([e for e in self.host.agent.events if e['kind']=='mission_progress']),1)

    async def test_first_poll_disposal_records_actual_start_before_death_certificate(self):
        await self.dispatch();receipt=self.fixture.receipt('failed')
        proof=self.fixture.root/'disposed.json';proof.write_text('{}')
        receipt['restoration_verified']=receipt['execution']['restoration_verified']=True
        receipt['unit_results']=[dict(control_release=dict(disposed_verified=True,evidence_path=str(proof)))]
        self.executor.ledger=[receipt]
        with patch.object(self.bridge,'verify_disposals') as verify:await self.bridge.receive()
        self.assertTrue(verify.called);self.assertEqual(self.task.status,'failed')
        self.assertFalse(self.fixture.roster.reserved)
        self.assertTrue(self.host.agent.missions.history[-1]['observations']['disposed_verified'])
        self.assertEqual(self.bridge.counters['attack']['completed'],0)

    async def test_draining_can_record_verified_terminal_after_last_public_snapshot(self):
        await self.dispatch();receipt=self.fixture.receipt('completed')
        receipt['execution']['issued_frame']=1520
        receipt['mission']=dict(mission_id=str(uuid.UUID(self.task.task_id)),stage='restored',revision=80,observed_frame=1550,deadline_frame=6000,approach_distance=120.,own_hp=80.,damage=5.,reason='source_damage')
        self.executor.ledger=[receipt];self.bridge.draining=True
        facts=dict(sha256='a'*64,path=self.fixture.root/'raw.json',qualification=dict(checks=dict(no_native_override=True),effect_verified=True,approach_verified=True,retreat_verified=True,source_damage_amount=5.))
        with patch.object(bridge_module,'terminal_facts',return_value=facts),patch.object(bridge_module,'progress_evidence',return_value=dict(sha256='a'*64)),patch.object(self.bridge,'verify_completed'):
            await self.bridge.receive()
        self.assertEqual(self.task.status,'completed');self.assertFalse(self.fixture.roster.reserved)
        self.assertEqual(self.host.agent.latest.game_time_seconds,100)
        self.assertEqual(self.bridge.counters['attack']['completed'],1)


if __name__=='__main__':unittest.main()
