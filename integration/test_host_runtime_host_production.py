"""Real Host methods through durable gateway, with synthetic original executor."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from battle_host import Host, parser
from host_runtime.contracts import ContractError, SessionBinding
from host_runtime.evidence_adapter import EvidenceBundle
from host_runtime.host_production import HostProduction, from_host
from host_runtime.journal import CommandJournal
from host_runtime.limits import ExecutionLimits
import test_host_runtime_native_adapters as fixtures

Executor, Checks, uid = fixtures.Executor, fixtures.Checks, fixtures.uid


class HostProductionTests(unittest.TestCase):
    def test_host_waits_full_native_production_gap_before_a_new_task(self):
        asyncio.run(self.host.dispatch());self.executor.mode='completed';asyncio.run(self.host.receive_receipts())
        self.job['task_id']=uid();deadline=self.host.production_not_before_frame
        self.host.last_snapshot['game_time_seconds']=(deadline-1)/15
        asyncio.run(self.host.dispatch());self.assertEqual(len(self.executor.calls),1)
        self.host.last_snapshot['game_time_seconds']=deadline/15
        asyncio.run(self.host.dispatch());self.assertEqual(len(self.executor.calls),2)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.binding=SessionBinding(1,uid(),3,uid(),1234,'2026-10-26T00:00:00+00:00',uid(),'a'*64,'b'*64)
        fixture=fixtures.NativeAdapterTests();fixture.binding=self.binding
        self.catalog=fixture.catalog_for()
        self.evidence=EvidenceBundle(self.catalog,{}, {},None,True)
        self.journal=CommandJournal(self.root/'commands.sqlite');self.run_id=uid()
        self.runtime=HostProduction(self.journal,self.run_id,self.binding,self.evidence,ExecutionLimits(5000,1000,1000))
        path=self.root/'session.json';path.write_text('immutable-original',encoding='utf-8')
        self.executor=Executor(path,self.binding);self.checks=Checks();self.runtime.attach(self.executor,checks=self.checks)
        self.task=uid();self.feedback=[]
        self.job=dict(task_id=self.task,host_dispatch_candidate=True,module='build',focus='infantry',expires_at_game_seconds=30,budget={'fraction':.1})
        self.host=Host.__new__(Host);host=self.host
        host.runtime_production=self.runtime;host.executor=self.executor;host.executor_ready=True;host.reserve_controller=None
        host.engine=SimpleNamespace(current=None)
        host.output=self.root;host.args=SimpleNamespace(total_budget=5000,reserve=1000)
        host.binding=SimpleNamespace(session_id=self.binding.session_id,player_id=3,commander_id=self.binding.commander_id)
        host.agent=SimpleNamespace(jobs=lambda:{'jobs':[self.job]},record_feedback=self.feedback.append,goals=SimpleNamespace(tasks=[]))
        host.collector=SimpleNamespace(foci=());host.evidence={'supported_foci':self.runtime.supported_foci}
        host.last_snapshot=dict(snapshot_id=1,paused=False,game_time_seconds=100/15,production={'own_roles':{}},resources={'credits':1000})
        host.sent={};host.sequence=0;host.remaining_budget=5000;host.started=time.monotonic();host.journal=self.root/'events.jsonl'
        host.counters=dict(dispatches=0,started=0,completed=0,failed=0,blocked=0);host.phase='running';host.reason='ok'
    def tearDown(self):self.journal.close();self.tmp.cleanup()

    def test_host_exports_actual_id_and_sequence_before_external_submit(self):
        original=self.executor.submit
        def checked_submit(wire):
            entry=json.loads((self.root/'dispatch-ledger.json').read_text())[self.task]
            self.assertEqual((entry['command_id'],entry['seq']),(wire['command_id'],wire['seq']))
            record=self.journal.get_command(self.run_id,entry['request_id'])
            self.assertEqual(record['status'],'dispatching');self.assertEqual(record['command_id'],wire['command_id'])
            return original(wire)
        self.executor.submit=checked_submit
        asyncio.run(self.host.dispatch())
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.executor.calls[0]['seq'],21)
        self.assertEqual(self.feedback[-1]['status'],'started')
        self.executor.mode='completed';asyncio.run(self.host.receive_receipts())
        entry=self.host.sent[self.task]
        self.assertTrue(entry['terminal']);self.assertEqual(self.feedback[-1]['status'],'completed')
        self.assertEqual(self.journal.get_command(self.run_id,entry['request_id'])['status'],'completed')
        self.assertEqual(self.host.collector.foci,('native_baseline','infantry'))
        self.assertIn('task_feedback',[event['event_type'] for event in self.journal.events(self.run_id)])
        asyncio.run(self.host.dispatch());self.assertEqual(len(self.executor.calls),1)

    def test_real_battle_agent_task_passes_gateway_and_receipt_returns_to_same_task(self):
        from battle_agent import BattleAgent,BuildEvidence
        from engine import StrategyEngine,Binding
        import fixtures as strategy_fixtures
        agent=BattleAgent(StrategyEngine(Binding(self.binding.session_id,3,self.binding.commander_id,'test',uid())),
            build_evidence=BuildEvidence(uid(),self.binding.session_id,3,'game_bridge',supported_foci=('infantry',)))
        raw=strategy_fixtures.snapshot(at=100/15,session_id=self.binding.session_id,source='game_bridge',
            capabilities=dict(production_focus=['native_baseline','infantry'],regions=['home_base']),
            enemy_observations=[],events=[])
        async def model(context):return strategy_fixtures.policy(context,production_focus='infantry')
        decision=asyncio.run(agent.decide(raw,model))
        self.assertEqual('accepted',decision.status,decision)
        task=next(t for t in agent.jobs()['jobs'] if t['module']=='build')
        self.assertEqual(task['task_id'],str(uuid.UUID(task['task_id'])))
        self.host.agent=agent;self.host.engine=agent.engine;self.host.last_snapshot=raw
        asyncio.run(self.host.dispatch())
        self.assertEqual(1,len(self.executor.calls))
        self.assertEqual(task['task_id'],self.executor.calls[0]['task_id'])
        events=self.journal.events(self.run_id)
        proposal=next(e for e in events if e['event_type']=='task_proposed' and e['payload']['task_id']==task['task_id'])
        intent=next(e for e in events if e['event_type']=='dispatch_intent_committed')
        self.assertLess(proposal['seq'],intent['seq'])
        plan=next(e for e in events if e['event_type']=='plan_applied')
        self.assertEqual(plan['payload']['plan_id'],proposal['payload']['plan_id'])
        self.executor.mode='completed';asyncio.run(self.host.receive_receipts())
        self.assertEqual('completed',next(t.status for t in agent.goals.tasks if t.task_id==task['task_id']))

    def test_late_pause_rejection_uses_actual_outcome_without_pending_or_send(self):
        prepare=self.runtime.prepare
        def later_pause(*args,**kwargs):
            result=prepare(*args,**kwargs);self.checks.paused=True;return result
        self.runtime.prepare=later_pause
        asyncio.run(self.host.dispatch())
        entry=self.host.sent[self.task]
        self.assertTrue(entry['terminal']);self.assertEqual(self.executor.calls,[])
        self.assertEqual(self.feedback[-1]['status'],'failed')
        self.assertEqual(self.journal.get_command(self.run_id,entry['request_id'])['status'],'rejected')

    def test_unknown_delivery_blocks_retries_and_new_host_for_same_session(self):
        self.executor.mode='unknown'
        with self.assertRaisesRegex(RuntimeError,'dispatch_outcome_unknown'):asyncio.run(self.host.dispatch())
        asyncio.run(self.host.dispatch());self.assertEqual(len(self.executor.calls),1)
        other=SessionBinding(**{**self.binding.public(),'host_id':uid()})
        evidence=EvidenceBundle(self.catalog.__class__.verify(other,self.catalog._grants,lambda grant,binding:grant),{}, {},None,True)
        with self.assertRaisesRegex(ContractError,'prior_host_commands_require_recovery'):
            HostProduction(self.journal,uid(),other,evidence,self.runtime.limits)

    def test_tampered_raw_native_receipt_does_not_complete_or_relabel(self):
        asyncio.run(self.host.dispatch());self.executor.mode='completed'
        self.executor.ledger[0]['command_id']=uid()
        with self.assertRaisesRegex(RuntimeError,'dispatch_outcome_unknown'):asyncio.run(self.host.receive_receipts())
        entry=self.host.sent[self.task]
        self.assertEqual(self.journal.get_command(self.run_id,entry['request_id'])['status'],'uncertain')
        self.assertFalse(any(row['status']=='completed' for row in self.feedback))

    def test_changed_native_queue_is_uncertain_in_authoritative_ledger(self):
        asyncio.run(self.host.dispatch());self.executor.mode='completed';self.executor.ledger[0]['queue_id']=99
        with self.assertRaisesRegex(RuntimeError,'dispatch_outcome_unknown'):asyncio.run(self.host.receive_receipts())
        entry=self.host.sent[self.task];record=self.journal.get_command(self.run_id,entry['request_id'])
        self.assertEqual(record['status'],'uncertain');self.assertEqual(record['receipt']['reason_code'],'native_queue_identity_changed')

    def test_same_run_cannot_resume_unknown_work_via_new_host_object(self):
        self.executor.mode='unknown'
        with self.assertRaises(RuntimeError):asyncio.run(self.host.dispatch())
        with self.assertRaisesRegex(ContractError,'prior_host_commands_require_recovery'):
            HostProduction(self.journal,self.run_id,self.binding,self.evidence,self.runtime.limits)

    def test_prepare_refusal_is_persisted_before_export_and_stop_has_separate_outcome(self):
        self.checks.reason='production_process_start_changed'
        asyncio.run(self.host.dispatch());entry=self.host.sent[self.task]
        self.assertTrue(entry['terminal']);self.assertIsNone(entry['seq']);self.assertEqual(self.executor.calls,[])
        self.checks.reason=None
        outcome=self.runtime.stop();self.assertEqual(outcome['status'],'released')
        self.assertFalse(outcome['receipt']['facts']['mission_effect_verified'])

    def test_only_persistent_scope_exposed_and_cli_requires_explicit_switch(self):
        self.assertEqual(self.runtime.supported_units,('conscript',));self.assertEqual(self.runtime.supported_foci,('infantry',))
        args=parser().parse_args(['--session','session.json','--commander',uid()])
        self.assertIsNone(args.runtime_ledger);self.assertIsNone(args.runtime_run_id);self.assertIsNone(args.runtime_host_id)

    def test_readonly_check_and_legacy_tactics_rejected_before_profile_or_ledger_access(self):
        path=self.root/'host-session.json';path.write_text('{}')
        cases=[(['--execute','--check','--runtime-ledger',str(self.root/'new.sqlite')],'runtime_ledger_requires_execute_without_check'),
               (['--execute','--runtime-ledger',str(self.root/'new.sqlite'),'--tactical-evidence','old-pair.json'],'macro_mode_rejects_unit_control_evidence'),
               (['--runtime-run-id',uid()],'runtime_identity_requires_ledger')]
        for flags,reason in cases:
            args=parser().parse_args(['--session',str(path),'--commander',uid(),*flags])
            with patch('battle_host.load_profile',side_effect=AssertionError('must not be reached')):
                with self.assertRaisesRegex(ValueError,reason):Host(args)
        self.assertFalse((self.root/'new.sqlite').exists())

    def test_macro_host_rejects_first_home_evidence_even_when_legacy_pins_are_complete(self):
        path=self.root/'host-session.json';path.write_text('{}')
        base=['--session',str(path),'--commander',uid(),'--execute','--runtime-ledger',str(self.root/'new.sqlite')]
        basic=['--runtime-report','basic.json','--runtime-sha256','a'*64]
        cases=[basic+['--runtime-recovery-report','recovery.json'],
            ['--runtime-recovery-report','recovery.json','--runtime-recovery-sha256','b'*64],
            basic+['--runtime-recovery-sha256','b'*64],
            basic+['--runtime-recovery-report','recovery.json','--runtime-recovery-sha256','b'*64]]
        for flags in cases:
            args=parser().parse_args(base+flags)
            with self.subTest(flags=flags),patch('battle_host.load_profile',side_effect=AssertionError('No profile access')):
                with self.assertRaisesRegex(ValueError,'macro_mode_rejects_unit_control_evidence'):Host(args)
        self.assertFalse((self.root/'new.sqlite').exists())

    def test_trusted_desktop_ids_and_prejournaled_start_share_runtime_binding(self):
        game=self.root/'game.exe';game.write_bytes(b'fake-game')
        binding=SessionBinding(**{**self.binding.public(),'game_sha256':hashlib.sha256(game.read_bytes()).hexdigest()})
        run=uid();ledger=self.root/'desktop.sqlite'
        with CommandJournal(ledger) as journal:
            journal.register_run(run,binding.public())
            start=journal.reserve_command(run,uid(),'host_start',{'profile_id':'test'})
            journal.mark_dispatching(run,start['request_id'])
        def evidence_builder(actual,session,**kwargs):
            self.assertEqual(actual,binding)
            fixture=fixtures.NativeAdapterTests();fixture.binding=actual
            return EvidenceBundle(fixture.catalog_for(),{}, {},None,True)
        host=SimpleNamespace(args=SimpleNamespace(runtime_run_id=run,runtime_host_id=binding.host_id,player_id=3,player=3,commander=binding.commander_id,evidence=None,persistent_evidence=None,total_budget=5000,reserve=1000),
              session={'session_id':binding.session_id,'pid':1234,'start_time':binding.game_process_start,'game':str(game),'mod_sha256':binding.mod_sha256})
        runtime=from_host(host,ledger,evidence_builder=evidence_builder)
        try:self.assertEqual(runtime.run_id,run);self.assertEqual(runtime.binding,binding)
        finally:runtime.close()


if __name__=='__main__':unittest.main()
