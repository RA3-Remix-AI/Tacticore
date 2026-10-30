"""Independent high-level delegation regressions; artificial native endpoint."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,AsyncMock

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'strategy'),str(ROOT/'integration'),str(ROOT/'native-ai'),str(ROOT)]
import test_macro_delegation_boundary_v1 as base
from host_runtime.contracts import ContractError
from host_runtime.macro_policy_runtime import MacroRequestAudit,COMMANDER
from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1,decide_prepared_macro_request_v1
from host_runtime.macro_delegation_boundary_v1 import KIND,STRATEGIC_ACTIONS
from macro_policy import ACTIONS
from macro_strategy import MacroStrategyMemory
from http_adapter import macro_system_prompt,ChatAdapter,AdapterError
from fixtures import SESSION

SCRATCH=Path('D:/CodexScratch/ra3-independent-next/strategic-boundary-v1')


class StrategicDelegationIndependentTests(unittest.TestCase):
    def case(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        case=base.RoutingTests(methodName='runTest')
        original=tempfile.TemporaryDirectory
        with patch.object(tempfile,'TemporaryDirectory',side_effect=lambda **kwargs:original(dir=SCRATCH,**kwargs)):
            case.setUp()
        self.addCleanup(case.doCleanups)
        return case

    def audit(self,case,*,declared=False,oversized=False):
        class Backend:
            max_input_bytes=16384
            def input_size(self,context):return 16385 if oversized else len(json.dumps(context,ensure_ascii=False).encode('utf8'))
            async def __call__(self,context):
                case.calls.append(context)
                value=base.model_policy(context)
                if declared:
                    value['macro_strategy']=dict(strategy_id=None,objective='hold',phase='wait',
                        public_fact_refs=['capabilities.actions'],expected_observation='no_change',
                        continue_conditions=['capability_available'],replan_conditions=['facts_changed'],
                        resource_priorities=dict(value['budget']))
                return value
        memory=MacroStrategyMemory(session_id=SESSION,commander_id=COMMANDER,player_id=3,
            profile_revision=1,effective_hash='b'*64) if declared else None
        return MacroRequestAudit(Backend(),lambda kind,**facts:case.events.append((kind,facts)),
            strategic_only=True,strategy_supplier=memory.context if memory else None)

    def test_real_prepared_entry_preserves_strategic_boundary_on_measure_and_sender(self):
        case=self.case();case.agent.observe(case.view);audit=self.audit(case)
        prepared=prepare_macro_request_v1(case.agent,audit,case.agent.latest)
        self.assertTrue(prepared.measure.strategic_only,'prepared measurement clone lost strategic_only')
        self.assertTrue(prepared.sender.strategic_only,'prepared sender clone lost strategic_only')
        decision=asyncio.run(decide_prepared_macro_request_v1(case.agent,case.agent.latest,prepared))
        self.assertEqual(decision.status,'accepted',decision.reason_code)
        self.assertEqual(case.calls[0]['native_delegation']['kind'],KIND)
        self.assertTrue(set(case.calls[0]['allowed_macro_actions'])<=STRATEGIC_ACTIONS)

    def test_declared_prompt_does_not_reintroduce_precise_queue_contract(self):
        case=self.case();case.agent.observe(case.view);audit=self.audit(case,declared=True)
        context=case.agent.context(case.agent.latest.model_context(case.agent.engine.binding),commit=False)
        prepared=audit.prepare(context)
        text=macro_system_prompt(SimpleNamespace(personality=0,traits='normal'),prepared)
        self.assertIn('native AI owns ALL building',text)
        self.assertNotIn('production=macro_production/new queue acceptances',text)
        self.assertNotIn('first matching queue',text)

    def test_final_host_rejects_every_historical_specific_action_before_journal_or_native(self):
        case=self.case();plan=case.decide().plan;host=case.host()
        for action in set(ACTIONS)-STRATEGIC_ACTIONS:
            with self.subTest(action=action):self.assertFalse(host.dispatch_plan(replace(plan,macro_actions=(action,))))
        self.assertEqual(host.transport.calls,[]);self.assertEqual(host.journal.commands_for_run(host.run_id),[])

    def test_broad_intent_names_are_not_silently_translated_to_refinery_or_construction(self):
        for action in ('expand','expansion','expand_economy','construction','pauseconstruction','stopproduction','buildrefinery'):
            case=self.case();decision=case.decide({'macro_actions':[action]})
            with self.subTest(action=action):
                self.assertEqual(decision.status,'local_fallback')
                # Native5 recognizes these high-level names, but this fixture
                # does not grant their routes. They remain refused, never
                # translated into a detailed construction command.
                expected = ('unsupported_macro_action' if action in ('expand','pauseconstruction')
                            else 'strategic_boundary_detailed_action_refused')
                self.assertEqual(decision.reason_code,expected)

    def test_high_level_whitelist_does_not_grant_a_route_missing_from_current_scope(self):
        for action in ('scout','withdraw','reinforce','budgettech'):
            case=self.case();decision=case.decide({'macro_actions':[action]})
            with self.subTest(action=action):self.assertEqual(decision.status,'local_fallback')
            case=self.case();plan=case.decide().plan;host=case.host()
            with self.subTest(action=action),self.assertRaises(ContractError):
                host.dispatch_plan(replace(plan,macro_actions=(action,)))
            self.assertEqual(host.transport.calls,[])

    def test_precise_extra_fields_coordinates_quantities_and_unit_orders_never_become_a_plan(self):
        changes=({'building_template':'SovietRefinery'},{'coordinates':[1,2]},
            {'macro_production':{'action':'producebullfrog','additional_count':1}},
            {'production_focus':'anti_air'},{'tactical_tasks':[{'unit_id':1,'command':'move'}]},
            {'runtime_task':{'unit_id':1,'x':1,'y':2}})
        for change in changes:
            case=self.case();decision=case.decide(change)
            with self.subTest(change=change):self.assertEqual(decision.status,'local_fallback')

    def test_unknown_native_delivery_holds_uncertain_journal_and_cannot_be_resent(self):
        case=self.case();plan=case.decide().plan;host=case.host()
        def unknown(actions,duration,command):
            host.transport.calls.append((actions,duration,command));raise TimeoutError('artificial native outcome unknown')
        host.transport.apply=unknown
        with self.assertRaises(ContractError) as first:host.dispatch_plan(plan)
        self.assertEqual(first.exception.code,'macro_dispatch_outcome_unknown')
        with self.assertRaises(ContractError):host.dispatch_plan(plan)
        self.assertEqual(len(host.transport.calls),1)
        rows=host.journal.commands_for_run(host.run_id)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'uncertain')
        self.assertTrue(host.controller.stopped)

    def test_stop_prevents_new_model_requests_and_new_native_commands(self):
        case=self.case();case.agent.stop()
        decision=case.decide();self.assertEqual(decision.status,'stopped');self.assertEqual(case.calls,[])
        case=self.case();plan=case.decide().plan;host=case.host();host.controller.stop()
        with self.assertRaises(ContractError):host.dispatch_plan(plan)
        self.assertEqual(host.transport.calls,[])

    def test_old_session_and_old_snapshot_response_stays_unusable(self):
        for change in ({'session_id':'11111111-1111-4111-8111-111111111111'},{'snapshot_id':999}):
            case=self.case();decision=case.decide(change)
            with self.subTest(change=change):self.assertEqual(decision.status,'local_fallback')

    def test_prepared_wire_bound_refuses_before_backend_send(self):
        case=self.case();case.agent.observe(case.view);audit=self.audit(case,oversized=True)
        with self.assertRaises(Exception):prepare_macro_request_v1(case.agent,audit,case.agent.latest)
        self.assertEqual(case.calls,[])

    def test_actual_chat_wire_accounts_for_prompt_and_utf8_before_any_network_attempt(self):
        case=self.case();case.agent.observe(case.view);audit=self.audit(case,declared=True)
        context=case.agent.context(case.agent.latest.model_context(case.agent.engine.binding),commit=False)
        context=audit.prepare(context)
        profile=SimpleNamespace(commander_id=COMMANDER,model='artificial-wire-model',provider='artificial',
            personality=0,traits='宏观'*10000,key='ARTIFICIAL_ONLY_NOT_A_CREDENTIAL')
        adapter=ChatAdapter(profile,max_input_bytes=16384)
        body=adapter.encoded_request(context);envelope=json.loads(body)
        self.assertEqual(json.loads(envelope['messages'][1]['content'])['native_delegation']['kind'],KIND)
        self.assertNotIn(profile.key,body.decode('utf8'))
        self.assertLess(len(body),16384)
        data_size=len(json.dumps(context,ensure_ascii=False,separators=(',',':')).encode('utf8'))
        context=dict(context,padding='x'*(16384-data_size-20))
        self.assertLess(len(json.dumps(context,ensure_ascii=False,separators=(',',':')).encode('utf8')),16384)
        self.assertGreater(adapter.input_size(context),16384)
        adapter._http=AsyncMock(side_effect=AssertionError('network must remain unreachable'))
        with self.assertRaisesRegex(AdapterError,'input_budget_exceeded'):asyncio.run(adapter(context))
        adapter._http.assert_not_called();self.assertEqual(adapter.metrics['attempts'],0)

    def test_default_pydantic_prepared_route_and_actual_sdk_wire_guard(self):
        import model_backend  # repository bootstrap for the production factory
        import httpx2
        from tacticore_agent_runtime.factory import create_backend,NetworkBackend
        from tacticore_agent_runtime.protocol import RuntimeAdapterError
        from tacticore_agent_runtime.pydantic_backend import PydanticBackend
        case=self.case();case.agent.observe(case.view)
        calls=[]
        async def handler(request):
            calls.append(bytes(request.content))
            envelope=json.loads(request.content)
            context=json.loads(envelope['messages'][1]['content'])
            self.assertEqual(context['native_delegation']['kind'],KIND)
            self.assertIn('native AI owns ALL building',envelope['messages'][0]['content'])
            self.assertLessEqual(len(request.content),16384)
            return httpx2.Response(200,json={'id':'independent-artificial','object':'chat.completion',
                'created':1,'model':'fixture-model','choices':[{'index':0,'finish_reason':'stop',
                'message':{'role':'assistant','content':json.dumps(base.model_policy(context))}}]})
        profile=SimpleNamespace(commander_id=COMMANDER,model='fixture-model',provider='OpenAI',
            personality=0,traits='normal',key='ARTIFICIAL_ONLY_NOT_A_CREDENTIAL',
            endpoint=SimpleNamespace(tls=True,loopback=False,host='artificial.invalid',port=443,path='/v1/chat/completions'))
        backend=create_backend(profile,transport=httpx2.MockTransport(handler),max_input_bytes=16384)
        self.assertIsInstance(backend,NetworkBackend)
        audit=MacroRequestAudit(backend,lambda *args,**kwargs:None,strategic_only=True)
        prepared=prepare_macro_request_v1(case.agent,audit,case.agent.latest)
        decision=asyncio.run(decide_prepared_macro_request_v1(case.agent,case.agent.latest,prepared))
        self.assertEqual(decision.status,'accepted',decision.reason_code)
        self.assertEqual(len(calls),1);self.assertEqual(backend.metrics['retries'],0)
        self.assertEqual(backend.metrics['max_request_bytes'],len(calls[0]))
        self.assertFalse(backend.last_transport_receipt['real_network_verified'])
        self.assertTrue(backend.last_transport_receipt['injected_transport'])
        context=json.loads(json.loads(calls[0])['messages'][1]['content'])
        raw_size=len(json.dumps(context,ensure_ascii=False,separators=(',',':')).encode('utf8'))
        context=dict(context,padding='x'*(16384-raw_size-20))
        self.assertLess(len(json.dumps(context,ensure_ascii=False,separators=(',',':')).encode('utf8')),16384)
        with self.assertRaisesRegex(RuntimeAdapterError,'input_budget_exceeded'):asyncio.run(backend(context))
        self.assertEqual(len(calls),1);self.assertEqual(backend.metrics['attempts'],1)
        # Isolate the independent physical SDK-body guard; never change its bound.
        with patch.object(PydanticBackend,'input_size',return_value=0):
            with self.assertRaisesRegex(RuntimeAdapterError,'input_budget_exceeded'):asyncio.run(backend(context))
        self.assertEqual(len(calls),1);self.assertEqual(backend.metrics['attempts'],2)
        self.assertGreater(backend.metrics['max_request_bytes'],16384)
        self.assertEqual(backend.metrics['retries'],0)


if __name__=='__main__':unittest.main()
