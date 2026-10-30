"""Real Agent/Audit/Host boundary with artificial observations, no native IO."""
import asyncio
import copy
from dataclasses import replace
import json
from pathlib import Path
import unittest
import uuid

import test_macro_host_dispatch_revalidation as fixture
from host_runtime.contracts import ContractError
from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1,decide_prepared_macro_request_v1,encoded


class PreparedRequestTests(unittest.TestCase):
    collect=fixture.RevalidationTests.collect
    events=fixture.RevalidationTests.events
    archived=fixture.RevalidationTests.archived
    def setUp(self):
        fixture.RevalidationTests.setUp(self)
        self.sent=[];original=self.host.strategy_audit.backend
        class Backend:
            max_input_bytes=16384
            def input_size(inner,context):return len(encoded(context))
            async def __call__(inner,context):
                self.sent.append(copy.deepcopy(context));return await original(context)
        self.host.strategy_audit.backend=Backend()

    def dispatch_memory(self,at=100):
        context=self.host.agent.context(self.host.agent.latest.model_context(self.host.agent.engine.binding),commit=False)
        review=self.host.strategy_runtime.review(self.plan,self.host.strategy_audit,self.host.strategy_audit.prepare(context))
        self.memory.record_dispatch(review,command_id='offline_command',game_seconds=at)

    def advance_memory(self,at):
        self.memory.record_outcome(command_id='offline_command',plan_id=self.plan.plan_id,outcome='no_effect',
            game_seconds=at,release_verified=True,reason_code='independent_empty_native_gates')

    def test_host_new_true_post_view_resolves_before_memory_without_retiming(self):
        self.dispatch_memory();self.advance_memory(1502/15)
        context=self.host.agent.context(self.host.agent.latest.model_context(self.host.agent.engine.binding),commit=False)
        with self.assertRaisesRegex(ContractError,'strategy_context_before_memory'):self.host.strategy_audit.prepare(context)
        self.host.capability_sample_frames=(1502,1502);self.views=[self.post]
        prepared=self.host.prepare_model_request(self.host.strategy_audit)
        self.assertIsNotNone(prepared);self.assertEqual(self.host.agent.latest.game_time_seconds,1503/15)
        self.assertIn('produceconscript',self.host.agent.latest.macro_control)
        result=asyncio.run(decide_prepared_macro_request_v1(self.host.agent,self.host.agent.latest,prepared))
        self.assertNotEqual(result.reason_code,'adapter_error')
        self.assertEqual(len(self.sent),1);self.assertEqual(self.sent[0]['game_time_seconds'],1503/15)
        self.assertEqual([r['snapshot_id'] for r in self.archived()],[3]);self.assertEqual(self.native.calls,[])

    def test_async_gap_preserves_captured_memory_not_future_outcome(self):
        self.dispatch_memory()
        snap=self.host.agent.latest;audit=self.host.strategy_audit
        prepared=prepare_macro_request_v1(self.host.agent,audit,snap)
        expected=prepared.measure.prepare(self.host.agent.context(snap.model_context(self.host.agent.engine.binding),commit=False))
        # The inner Engine task runs after this queued mutation. The snapshot
        # stays real and unchanged; only the live trusted memory moves on.
        async def exercise():
            task=asyncio.create_task(decide_prepared_macro_request_v1(self.host.agent,snap,prepared))
            asyncio.get_running_loop().call_soon(self.advance_memory,101)
            return await task
        result=asyncio.run(exercise())
        self.assertNotEqual(result.reason_code,'adapter_error');self.assertEqual(self.sent,[expected])
        with self.assertRaisesRegex(ContractError,'strategy_context_before_memory'):
            audit.prepare(self.host.agent.context(snap.model_context(self.host.agent.engine.binding),commit=False))
        self.assertEqual(audit._last_request_context,expected);self.assertEqual(audit.sequence,2)
        self.assertEqual(self.host.agent.latest,snap)

    def test_superseded_before_task_start_defers_without_engine_or_provider(self):
        snap=self.host.agent.latest;prepared=prepare_macro_request_v1(self.host.agent,self.host.strategy_audit,snap)
        self.host.agent.observe(self.pre);requests=self.host.agent.engine.metrics['requests']
        result=asyncio.run(decide_prepared_macro_request_v1(self.host.agent,snap,prepared))
        self.assertEqual(result.status,'deferred');self.assertEqual(self.sent,[])
        self.assertEqual(self.host.agent.engine.metrics['requests'],requests);self.assertEqual(self.host.agent.latest.snapshot_id,2)

    def test_capture_is_detached_and_read_once_and_tamper_never_calls_provider(self):
        calls=[];value=None
        def supplier():calls.append(1);return value
        audit=self.host.strategy_audit;audit.production_supplier=supplier
        snap=self.host.agent.latest;prepared=prepare_macro_request_v1(self.host.agent,audit,snap)
        self.assertEqual(len(calls),1)
        base=self.host.agent.context(snap.model_context(self.host.agent.engine.binding),commit=False)
        base['snapshot_id']=999
        with self.assertRaisesRegex(ContractError,'captured_context_changed'):asyncio.run(prepared(base))
        with self.assertRaisesRegex(ContractError,'already_consumed'):asyncio.run(prepared(base))
        self.assertEqual(self.sent,[]);self.assertEqual(len(calls),1)

    def test_stale_pair_observes_real_post_history_but_sends_nothing(self):
        self.host.capability_sample_frames=(1502,1502);self.views=[fixture.view(3,1520)]
        self.assertIsNone(self.host.prepare_model_request(self.host.strategy_audit))
        self.assertEqual([r['snapshot_id'] for r in self.archived()],[3]);self.assertEqual(self.sent,[])
        self.assertEqual(self.events()[-1]['reason_code'],'macro_request_native_pair_stale')

    def test_missing_declaration_remains_rejected_by_original_audit(self):
        audit=self.host.strategy_audit
        class Missing:
            def input_size(inner,c):return 0
            async def __call__(inner,c):self.sent.append(c);return {}
        audit.backend=Missing();snap=self.host.agent.latest
        prepared=prepare_macro_request_v1(self.host.agent,audit,snap)
        result=asyncio.run(decide_prepared_macro_request_v1(self.host.agent,snap,prepared))
        self.assertEqual(result.reason_code,'adapter_error');self.assertEqual(len(self.sent),1)
        self.assertTrue(any(e.get('kind')=='macro_strategy_response_rejected' for e in self.events()))

    def test_mutating_live_supplier_after_capture_cannot_change_sent_input(self):
        value=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1500,native_effect_verified=False)
        audit=self.host.strategy_audit;audit.feedback_supplier=lambda:value
        snap=self.host.agent.latest;prepared=prepare_macro_request_v1(self.host.agent,audit,snap)
        value['observed_frame']=9999;value['actions'].append('budgetarmy')
        result=asyncio.run(decide_prepared_macro_request_v1(self.host.agent,snap,prepared))
        self.assertNotEqual(result.reason_code,'adapter_error')
        self.assertEqual(self.sent[0]['macro_execution_feedback']['observed_frame'],1500)
        self.assertEqual(self.sent[0]['macro_execution_feedback']['actions'],[])

    def test_wire_bounds_fail_before_provider(self):
        audit=self.host.strategy_audit;audit.backend.input_size=lambda c:17000
        with self.assertRaises(Exception):prepare_macro_request_v1(self.host.agent,audit,self.host.agent.latest)
        self.assertEqual(self.sent,[])

    def test_parent_sequence_change_refuses_queued_request(self):
        audit=self.host.strategy_audit;snap=self.host.agent.latest
        prepared=prepare_macro_request_v1(self.host.agent,audit,snap);audit.sequence+=1
        result=asyncio.run(decide_prepared_macro_request_v1(self.host.agent,snap,prepared))
        self.assertEqual(result.reason_code,'adapter_error');self.assertEqual(self.sent,[])

    def test_v4_audit_uses_frozen_suppliers_but_live_dispatch_review(self):
        from host_runtime.macro_admission_feedback_v4 import MacroRequestAuditV4
        old=self.host.strategy_audit
        audit=MacroRequestAuditV4(old.backend,self.host.event,strategy_supplier=self.memory.context,resource_supplier=lambda:None)
        snap=self.host.agent.latest;prepared=prepare_macro_request_v1(self.host.agent,audit,snap)
        result=asyncio.run(decide_prepared_macro_request_v1(self.host.agent,snap,prepared))
        self.assertEqual(result.status,'accepted');self.assertEqual(audit.request_context_for(result.plan),self.sent[0])
        context=self.host.agent.context(snap.model_context(self.host.agent.engine.binding),commit=False)
        review=self.host.strategy_runtime.review(result.plan,audit,audit.prepare(context))
        self.assertTrue(review.allowed)
        self.memory.record_dispatch(review,command_id='offline_unknown',game_seconds=100,outcome='unknown')
        live=audit.prepare(context)
        refused=self.host.strategy_runtime.review(replace(result.plan,plan_id=str(uuid.uuid4())),audit,live)
        self.assertFalse(refused.allowed);self.assertEqual(refused.reason_code,'strategy_unknown_outcome')
        self.assertEqual(audit._last_request_context,self.sent[0])

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'reports/macro-request-memory-order-dfeb8c37-20261029-v1/finding.json').is_file(),
                         'requires the local historical timing archive; not distributed with source')
    def test_original_three_recorded_time_boundaries_remain_strict(self):
        finding=Path(__file__).resolve().parents[1]/'reports/macro-request-memory-order-dfeb8c37-20261029-v1/finding.json'
        anchors=json.loads(finding.read_text(encoding='utf8'))['results']
        # Use a separate actual Agent fixture for each original time boundary;
        # source replay and original prefix hashes are in the immutable finding.
        for row in anchors:
            with self.subTest(snapshot_id=row['snapshot_id']):
                case=PreparedRequestTests();case.setUp()
                try:
                    case.dispatch_memory();case.advance_memory(row['recorded_memory_game_seconds'])
                    old=fixture.view(row['snapshot_id'],row['request_game_seconds']*15)
                    case.host.latest=old;case.host.observe_current()
                    context=case.host.agent.context(case.host.agent.latest.model_context(case.host.agent.engine.binding),commit=False)
                    with self.assertRaisesRegex(ContractError,'strategy_context_before_memory'):case.host.strategy_audit.prepare(context)
                    fresh=fixture.view(row['fresh_original_snapshot_id'],row['fresh_original_game_seconds']*15)
                    frame=round(row['fresh_original_game_seconds']*15)-1
                    builder,census=fixture.sample(frame)
                    case.host.controller.refresh(dict(build_observation=builder,observation=dict(frame=frame,construction_feedback=census)))
                    case.host.capability_sample_frames=(frame,frame);case.views=[fresh]
                    prepared=case.host.prepare_model_request(case.host.strategy_audit)
                    self.assertIsNotNone(prepared)
                    result=asyncio.run(decide_prepared_macro_request_v1(case.host.agent,case.host.agent.latest,prepared))
                    self.assertNotEqual(result.reason_code,'adapter_error');self.assertEqual(len(case.sent),1)
                    self.assertEqual(case.sent[0]['game_time_seconds'],row['fresh_original_game_seconds'])
                finally:case.doCleanups()

if __name__=='__main__':unittest.main()
