"""Offline protocol admission, borrowed-memory telemetry, and model projection."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import tempfile
from dataclasses import replace

from macro_host import native_transport_config,MacroHost
from host_runtime.contracts import ContractError
from host_runtime.macro_live import MacroSampler
from host_runtime.macro_policy_runtime import MacroRequestAudit
from host_runtime.macro_expansion_scope import EXTRA_ACTIONS,expansion_catalog_overrides
from host_runtime.macro_expansion_feedback import ExpansionFeedback
from host_runtime.test_macro_expansion_runtime import expansion_scope,legacy_scope
from host_runtime import test_macro_expansion_runtime as runtime_fixture
from host_runtime.test_macro_expansion_feedback import sample


def manifest(protocol):
    return dict(kind='native_macro_policy_transport_v2_candidate' if protocol==2 else 'native_macro_policy_transport_candidate',
        package_sha256='a'*64,protocol_version=protocol,flags=['f'+str(i) for i in range(20 if protocol==2 else 13)],
        maximum_host_wall_seconds=3540 if protocol==2 else 1500,absolute_native_wall_ms=3600000,
        heartbeat_loss_ms=5000,same_process_reattach_supported=False)


class HostProtocolTests(unittest.TestCase):
    def test_v1_default_and_max_1500_v2_default_and_max_3540(self):
        v1=native_transport_config(legacy_scope(),manifest(1));v2=native_transport_config(expansion_scope(),manifest(2))
        self.assertEqual(v1['max_wall_seconds'],1500);self.assertEqual(v2['max_wall_seconds'],3540)
        self.assertIn('macro-policy-runtime-v2',v2['client_path']);self.assertTrue(v2['client_path'].endswith('client.py'))
        self.assertNotIn('runtime-v2',v1['client_path']);self.assertEqual(v2['absolute_native_wall_ms'],3600000)
        self.assertTrue(v2['native_wall_guard_is_backup_only']);self.assertEqual(v2['heartbeat_loss_ms'],5000)
        for scope,version,wall in ((legacy_scope(),1,1501),(expansion_scope(),2,3541),(expansion_scope(),2,3600),
                (legacy_scope(),1,True),(expansion_scope(),2,9)):
            with self.subTest(version=version,wall=wall),self.assertRaisesRegex(ContractError,'wall_bound'):
                native_transport_config(scope,manifest(version),wall)

    def test_wrong_protocol_kind_native_limit_or_heartbeat_rejected_before_attach(self):
        for scope,value in ((expansion_scope(),manifest(1)),(legacy_scope(),manifest(2))):
            with self.assertRaisesRegex(ContractError,'protocol_mismatch'):native_transport_config(scope,value)
        for change in (dict(protocol_version=True),dict(protocol_version=1),dict(maximum_host_wall_seconds=3600),
                dict(maximum_host_wall_seconds=3540.),dict(absolute_native_wall_ms=3540000),dict(heartbeat_loss_ms=10000),dict(flags=['duplicate']*20)):
            with self.subTest(change=change),self.assertRaises(ContractError):native_transport_config(expansion_scope(),dict(manifest(2),**change))


class BorrowedExpansionSamplingTests(unittest.TestCase):
    def sampler(self,frame=1500):
        sampler=MacroSampler.__new__(MacroSampler);sampler.scope=expansion_scope();sampler.session={'session_id':'session'}
        data=sample(frame=frame);sampler.memory=Mock();sampler.expansion_templates={0xc16ff13f,0xcf8d9f20}
        sampler.expansion_readiness=Mock(sample=Mock(return_value=data['readiness']))
        sampler.expansion_dependency=Mock(sample=Mock(return_value=data['dependency']))
        sampler.expansion_lifecycle=Mock(observe=Mock(return_value=dict(frame=frame,objects=[])))
        return sampler,data

    def test_fresh_each_time_and_borrows_existing_observers_without_new_memory(self):
        sampler,data=self.sampler();result=sampler.collect_expansion(data)
        self.assertTrue(result['expansion_sample_coherent']);self.assertEqual(result['lifecycle']['frame'],1500)
        sampler.expansion_readiness.sample.assert_called_once_with([765])
        sampler.expansion_dependency.sample.assert_called_once_with(list(EXTRA_ACTIONS))
        sampler.expansion_lifecycle.observe.assert_called_once_with(data['dependency'],session_token='session')
        sampler.memory.close.assert_not_called()
        sampler.collect_expansion(data);self.assertEqual(sampler.expansion_readiness.sample.call_count,2)
        self.assertIn('original_frame',result['expansion_component_timings']['readiness'])

    def test_slow_original_frames_unchanged_and_no_lifecycle_or_new_grant(self):
        sampler,data=self.sampler();data['observation']['frame']=1441
        result=sampler.collect_expansion(data)
        self.assertFalse(result['expansion_sample_coherent']);self.assertEqual(result['observation']['frame'],1441)
        self.assertEqual(result['readiness']['frame'],1500);sampler.expansion_lifecycle.observe.assert_not_called()
        fixture=runtime_fixture.ExpansionRuntimeTests();fixture.setUp();fixture.controller.refresh(result)
        self.assertNotIn('buildpower',fixture.controller.available_actions(100.))
        self.assertIn('budgetarmy',fixture.controller.available_actions(100.))

    def test_read_failure_or_missing_new_observers_only_disables_new_domain(self):
        sampler,data=self.sampler();sampler.expansion_readiness.sample.side_effect=ValueError('private native error')
        result=sampler.collect_expansion(data);self.assertFalse(result['expansion_sample_coherent'])
        self.assertNotIn('private native',json.dumps(result));self.assertIs(result['build_observation'],data['build_observation'])
        sampler.scope=legacy_scope();self.assertIs(sampler.collect_expansion(data),data)

    def test_static_component_error_code_is_retained_without_private_prose(self):
        sampler,data=self.sampler();sampler.expansion_dependency.sample.side_effect=ValueError('dependency_frame_span')
        result=sampler.collect_expansion(data)
        self.assertFalse(result['expansion_sample_coherent'])
        self.assertEqual(result['expansion_sample_error_details']['dependency'],
            dict(error_type='ValueError',reason_code='dependency_frame_span'))
        sampler.expansion_dependency.sample.side_effect=RuntimeError('private address 0x1234')
        result=sampler.collect_expansion(data)
        self.assertNotIn('private address',json.dumps(result))

    def test_product_missing_cost_is_still_explicitly_blocked_with_good_telemetry(self):
        fixture=runtime_fixture.ExpansionRuntimeTests();fixture.setUp();fixture.controller.cost_supplier=None
        host=MacroHost.__new__(MacroHost);host.controller=fixture.controller
        host.sampler=SimpleNamespace(scope=fixture.controller.expansion_scope)
        host.latest=dict(game_time_seconds=100.,battlefield=dict(visibility_verified=True,viewer_player_id=3,contacts=[]));host.event=Mock()
        data=sample();data['expansion_sample_coherent']=True
        self.assertTrue(host.production_tick(data));self.assertNotIn('buildpower',host.latest['macro_control']['available_actions'])
        self.assertEqual(fixture.controller.expansion_blocked['buildpower'],'blocked_native_cost_reservation_unverified')


class ExpansionAuditTests(unittest.IsolatedAsyncioTestCase):
    def feedback(self):return ExpansionFeedback('buildpower',sample(),100.).public()

    async def test_strict_projection_survives_context_and_refuses_private_or_oversized_wire(self):
        feedback=dict(self.feedback(),private_address='private')
        calls=[]
        class Backend:
            def input_size(self,value):return 17000
            async def __call__(self,value):calls.append(value);return {}
        audit=MacroRequestAudit(Backend(),Mock(),expansion_supplier=lambda:feedback)
        context=dict(control_mode='macro_native',game_time_seconds=100.)
        self.assertNotIn('private',json.dumps(audit.prepare(context)))
        with self.assertRaisesRegex(ContractError,'wire_bounds'):await audit(context)
        self.assertEqual(calls,[])
        feedback['builder_frame']=1441;self.assertFalse(audit.fresh_for_game_seconds(100.))
        with self.assertRaisesRegex(ContractError,'invalid_or_stale'):audit.prepare(context)

    async def test_expanded_catalog_only_exact_host_definitions_and_allowed_actions(self):
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1500,native_effect_verified=False)
        overrides=expansion_catalog_overrides(('buildpower','producesickle'))
        audit=MacroRequestAudit(None,Mock(),feedback_supplier=lambda:budget,catalog_supplier=lambda:overrides)
        context=dict(control_mode='macro_native',game_time_seconds=100.,allowed_macro_actions=['buildpower'],
            macro_policy_catalog=dict(buildpower=dict(domain='construction')))
        result=audit.prepare(context);self.assertEqual(result['macro_policy_catalog']['buildpower']['maximum_duration_seconds'],40)
        self.assertNotIn('producesickle',result['macro_policy_catalog'])
        overrides['buildpower']['maximum_duration_seconds']=3600
        with self.assertRaisesRegex(ContractError,'catalog_invalid'):audit.prepare(context)

    async def test_twenty_action_context_and_resource_facts_fit_sixteen_kib_wire(self):
        from engine import Snapshot,Binding,StrategyEngine
        from battle_agent import BattleAgent
        from http_adapter import macro_system_prompt
        from macro_strategy import MacroStrategyMemory
        from host_runtime.test_resource_reservations import queue_cost
        from host_runtime.macro_policy_runtime import ROOT,COMMANDER
        fixture=runtime_fixture.ExpansionRuntimeTests();fixture.setUp()
        fixture.controller.cost_supplier=lambda action,data,seconds:replace(queue_cost(fixture.sid),frame=data['build_observation']['frame'])
        fixture.dispatch()
        expansion=fixture.controller.expansion_feedback();resources=fixture.controller.resource_feedback()
        path=ROOT/'acceptance/runs/20261028-075720-macro-probe/battle-host/macro-snapshots.jsonl'
        raw=json.loads(path.read_text().splitlines()[0]);frame=round(raw['game_time_seconds']*15)
        for key in ('builder_frame','own_census_frame'):expansion[key]=frame
        actions=['budgeteconomy','budgetarmy','budgettech','produceconscript','produceflak','producetank',
            'buildreactor','scout','deployattack','deploydefense','regroup','withdraw','reinforce',*EXTRA_ACTIONS]
        raw['capabilities']['regions']=sorted(set(raw['capabilities']['regions'])|{'region_1_3','region_8_3'})
        raw['macro_control']=dict(mode='macro_native',available_actions=actions,
            production_counts={action:[1] for action in actions if action.startswith('produce')},
            region_targets={action:('region_1_3' if action=='deployattack' else 'region_8_3') for action in
                ('deployattack','deploydefense','regroup','withdraw','reinforce')})
        request=Snapshot.from_dict(raw);binding=Binding(request.session_id,3,COMMANDER,'commander','23968c8e-25d3-47bd-8c84-5f0d5bbfd43b')
        agent=BattleAgent(StrategyEngine(binding),context_budget_bytes=16384);agent.observe(raw)
        prose='优先观察经济和供电再决定扩张。保持生产设施运转，遇到明确威胁时调整资源分配。侦察只参考已知公开信息，不能把失联目标当作当前事实。保存长期战略但随实际局势修订，队伍和建筑的完成状态分别判断。'
        profile=SimpleNamespace(traits=(prose*20)[:1200],personality=1)
        def wire(context):
            return len(json.dumps({'messages':[dict(role='system',content=macro_system_prompt(profile,context)),
                dict(role='user',content=json.dumps(context,ensure_ascii=False,separators=(',',':')))]},ensure_ascii=False).encode())+1024
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=frame,native_effect_verified=False)
        memory=MacroStrategyMemory(session_id=binding.session_id,commander_id=COMMANDER,player_id=3,profile_revision=1,effective_hash='b'*64)
        def strategy(context):
            value=memory.context(context)
            value['fact_catalog']['wire_pressure_fixture']=''
            size=lambda:len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
            remaining=1536-size()
            self.assertGreaterEqual(remaining,0)
            value['fact_catalog']['wire_pressure_fixture']='测'*(remaining//3)+'x'*(remaining%3)
            self.assertEqual(size(),1536)
            return value
        audit=MacroRequestAudit(SimpleNamespace(input_size=wire),Mock(),feedback_supplier=lambda:budget,
            expansion_supplier=lambda:expansion,resource_supplier=lambda:resources,
            catalog_supplier=lambda:expansion_catalog_overrides(EXTRA_ACTIONS),strategy_supplier=strategy)
        context=agent.context(request.model_context(binding),wire_size=audit.input_size,wire_limit=16384)
        self.assertLessEqual(audit.input_size(context),16384)
        self.assertEqual(set(context['allowed_macro_actions']),set(actions))
        prepared=audit.prepare(context)
        self.assertIn('macro_expansion_feedback',prepared);self.assertIn('macro_resource_feedback',prepared)
        self.assertEqual(prepared['macro_resource_feedback']['funding_scope'],'current_owned_production_upgrade_queues')
        from macro_policy import restore_public_defaults
        self.assertEqual(restore_public_defaults(prepared)['macro_strategy'],strategy(context))

    async def test_invalid_host_limit_rejected_before_sampler_transport_or_backend(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'build-manifest.json').write_text(json.dumps(manifest(2)),encoding='utf8')
            host=MacroHost.__new__(MacroHost);host.args=SimpleNamespace(macro_bundle=root/'absent-no-real-grant',max_wall_seconds=3541)
            host.session={};host.output=root;host.pending=None;host.agent=None;host.sampler=None;host.transport=None;host.controller=None
            host.strategy_runtime=None;host.event=Mock();host.publish=Mock();host.store=Mock();host.journal=Mock()
            with patch('macro_host.load_bundle',return_value=({'build':str(root)},expansion_scope())), \
                    patch('macro_host.MacroSampler') as sampler,patch('macro_host.importlib.util.spec_from_file_location') as transport, \
                    patch('macro_host.create_applied_backend') as backend:
                result=await host.run()
            self.assertEqual(result['reason_code'],'macro_host_wall_bound')
            sampler.assert_not_called();transport.assert_not_called();backend.assert_not_called()
            self.assertFalse((root/'native-transport-preflight.json').exists())

    async def test_resource_facts_are_not_duplicated_or_allowed_to_conflict(self):
        fixture=runtime_fixture.ExpansionRuntimeTests();fixture.setUp();fixture.dispatch()
        expansion=fixture.controller.expansion_feedback();resource=fixture.controller.resource_feedback()
        audit=MacroRequestAudit(None,Mock(),expansion_supplier=lambda:expansion,resource_supplier=lambda:resource)
        context=audit.prepare(dict(control_mode='macro_native',game_time_seconds=100.))
        self.assertNotIn('resource_reservation',context['macro_expansion_feedback'])
        self.assertEqual(context['macro_resource_feedback'],resource)
        resource['status']='unknown'
        with self.assertRaisesRegex(ContractError,'context_binding_mismatch'):
            audit.prepare(dict(control_mode='macro_native',game_time_seconds=100.))

