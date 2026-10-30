"""Strategic protocol integration with offline models and frozen public inputs."""
import asyncio
import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from battle_agent import BattleAgent
from engine import ContractError, Snapshot, StrategyEngine, validate_policy
from fixtures import binding, policy, snapshot
from http_adapter import ChatAdapter, system_prompt
from macro_policy import (ACTIONS, CONSTRUCTION_BUILDINGS, INITIAL_PRODUCTION_COUNTS,
                          model_catalog, project_strategy_defaults, restore_public_defaults,
                          public_descriptions)
from macro_strategy import MacroStrategyMemory
from test_macro_strategy import declaration


def macro_snapshot(actions=None, *, counts=None):
    control=dict(mode='macro_native',available_actions=actions or ['budgeteconomy','budgetarmy'])
    if counts is not None:control['production_counts']=counts
    return Snapshot.from_dict(snapshot(macro_control=control))


def memory_for(context):
    return MacroStrategyMemory(session_id=context['session_id'], commander_id=context['commander_id'],
        player_id=context['player_id'],profile_revision=21,effective_hash='a'*64)


def encoder():
    value=ChatAdapter.__new__(ChatAdapter)
    value.profile=SimpleNamespace(personality=1,traits='风格偏好'*100,provider='DeepSeek',model='offline-test')
    value.max_tokens=2048
    return value


class StrategyPlanTests(unittest.TestCase):
    def test_optional_declaration_roundtrip_and_old_public_shape(self):
        observed=macro_snapshot()
        context=observed.model_context(binding())
        old=validate_policy(policy(context,macro_actions=['budgetarmy']),observed,observed,binding(),20)
        self.assertIsNone(old.macro_strategy)
        self.assertNotIn('macro_strategy',old.public())
        raw=policy(context,macro_actions=['budgetarmy'],macro_strategy=declaration())
        current=validate_policy(raw,observed,observed,binding(),20)
        self.assertEqual(current.public()['macro_strategy'],declaration())
        raw['macro_strategy']['public_fact_refs'].append('PRIVATE')
        self.assertEqual(current.macro_strategy['public_fact_refs'],['own.credits'])
        engine=StrategyEngine(binding());engine.current=current
        agent=BattleAgent(engine);agent.observe(observed.to_dict())
        self.assertEqual(agent.public_memory()['current_strategy']['macro_strategy'],declaration())
        self.assertNotEqual(StrategyEngine._intent(old),StrategyEngine._intent(current))

    def test_declaration_cannot_enable_macro_mode_or_bypass_strict_shape(self):
        observed=Snapshot.from_dict(snapshot());context=observed.model_context(binding())
        with self.assertRaisesRegex(ContractError,'requires_macro_mode'):
            validate_policy(policy(context,macro_strategy=declaration()),observed,observed,binding(),20)
        observed=macro_snapshot();context=observed.model_context(binding())
        for value in (None,{},dict(declaration(),phase='arbitrary'),dict(declaration(),secret='PRIVATE')):
            with self.subTest(value=value),self.assertRaises(ContractError):
                validate_policy(policy(context,macro_strategy=value),observed,observed,binding(),20)

    def test_candidates_are_recognized_but_not_implicitly_authorized(self):
        candidates=['buildpower','buildbarracks','buildfactory','buildrefinery','buildbattlelab',
                    'producesickle','producebullfrog']
        self.assertTrue(set(candidates)<=set(ACTIONS))
        existing=macro_snapshot()
        for action in candidates:
            with self.subTest(action=action),self.assertRaisesRegex(ContractError,'unsupported_macro_action'):
                validate_policy(policy(existing.model_context(binding()),macro_actions=[action]),
                    existing,existing,binding(),20)
        for action in INITIAL_PRODUCTION_COUNTS:
            observed=macro_snapshot([action],counts={action:[1]})
            context=observed.model_context(binding())
            raw=policy(context,macro_actions=[action],macro_production={'action':action,'additional_count':1})
            self.assertEqual(validate_policy(raw,observed,observed,binding(),20).macro_production.additional_count,1)
            self.assertEqual(context['macro_policy_catalog'][action]['quantity']['allowed_additional_counts'],[1])
            for count in (2,3):
                raw['macro_production']['additional_count']=count
                with self.assertRaisesRegex(ContractError,'quantity_not_qualified'):
                    validate_policy(raw,observed,observed,binding(),20)
        for action,building in CONSTRUCTION_BUILDINGS.items():
            self.assertEqual(public_descriptions([action])[action]['building'],building)

    def test_unknown_power_is_kept_unknown(self):
        observed=macro_snapshot();raw=observed.to_dict();raw['resources']['power_balance']=None
        observed=Snapshot.from_dict(raw);agent=BattleAgent(StrategyEngine(binding()));agent.observe(raw)
        context=agent.context(observed.model_context(binding()))
        self.assertIsNone(memory_for(context).context(context)['fact_catalog']['own.power_balance'])


class ProjectionTests(unittest.TestCase):
    def test_default_projection_is_exactly_reversible_without_mutating_input(self):
        original=dict(macro_policy_catalog=model_catalog(public_descriptions(
            ['produceconscript','buildreactor'],counts=[('produceconscript',(1,))])),
            macro_production_feedback=dict(payment_verified=False,automatic_retry_allowed=False,
                unit_operation_policy='native_ai',observed_new_queue_count=1,own_census_frame=1500,
                status='native_production_queue_target_observed',policy_released=True,release_reason='queue_target_observed'),
            own_forces=dict(recruitability_verified=False,ready_for_combat_verified=False,
                named_unit_counts={'conscript':2},observed_frame=1500),unknown_data={'arbitrary':False})
        frozen=copy.deepcopy(original);packed=project_strategy_defaults(original)
        self.assertEqual(original,frozen)
        self.assertEqual(restore_public_defaults(packed),original)
        self.assertEqual(project_strategy_defaults(packed),packed)
        self.assertLess(len(json.dumps(packed['macro_production_feedback'])),len(json.dumps(original['macro_production_feedback'])))
        self.assertEqual(packed['unknown_data'],{'arbitrary':False})

    def test_changed_or_unknown_values_are_kept_and_contract_tampering_rejected(self):
        raw=dict(macro_policy_catalog={'buildreactor':dict(domain='construction',control_basis='future_control',
            release_on='first_new_matching_queue_or_expiry',maximum_duration_seconds=31,unknown=False)},
            macro_production_feedback=dict(payment_verified=True,automatic_retry_allowed=True,
                unit_operation_policy='changed_policy',secret_not_a_default=False))
        packed=project_strategy_defaults(raw)
        self.assertEqual(packed['macro_production_feedback'],raw['macro_production_feedback'])
        self.assertEqual(packed['macro_policy_catalog']['buildreactor']['control_basis'],'future_control')
        self.assertEqual(restore_public_defaults(packed),raw)
        broken=copy.deepcopy(packed);broken['macro_default_contract']['definitions']='unknown_schema'
        with self.assertRaisesRegex(ValueError,'contract_invalid'):restore_public_defaults(broken)
        broken=copy.deepcopy(packed);broken['macro_default_contract']['catalog'][0]=True
        with self.assertRaisesRegex(ValueError,'contract_mask'):restore_public_defaults(broken)
        broken=copy.deepcopy(packed);broken['macro_policy_catalog']['buildreactor']['release_on']='changed'
        with self.assertRaisesRegex(ValueError,'contract_conflict'):restore_public_defaults(broken)

    def test_aliases_conflicts_unknown_map_and_duplicate_raw_json_are_rejected(self):
        raw=dict(macro_policy_catalog={str(i):{'domain':'budget','target_policy':'native','observed_frame':1500}
            for i in range(8)})
        packed=project_strategy_defaults(raw)
        self.assertTrue(packed['macro_default_contract']['aliases'])
        self.assertEqual(restore_public_defaults(packed),raw)
        alias,field=next(iter(packed['macro_default_contract']['aliases'].items()))
        broken=copy.deepcopy(packed);broken['macro_policy_catalog']['0'][field]='conflict'
        with self.assertRaisesRegex(ValueError,'alias_conflict'):restore_public_defaults(broken)
        broken=copy.deepcopy(packed);broken['macro_default_contract']['aliases']['unknown']='observed_frame'
        with self.assertRaisesRegex(ValueError,'unknown_alias'):restore_public_defaults(broken)
        with self.assertRaisesRegex(ValueError,'duplicate_key'):
            restore_public_defaults('{"x":1,"x":2}')


class StrategyRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_request_shape_matches_plan_binding_and_supplied_facts(self):
        from integration.host_runtime.macro_policy_runtime import MacroRequestAudit
        observed=macro_snapshot();agent=BattleAgent(StrategyEngine(binding()))
        memory=memory_for(observed.model_context(binding()));enc=encoder()
        class Backend:
            max_input_bytes=16384
            def input_size(self,value):return enc.input_size(value)
            async def __call__(self,value):
                self.sent=copy.deepcopy(value)
                return policy(value,macro_actions=['budgetarmy'],macro_strategy=declaration())
        backend=Backend();events=[]
        audited=MacroRequestAudit(backend,lambda kind,**facts:events.append((kind,facts)),strategy_supplier=memory.context)
        result=await agent.decide(observed.to_dict(),audited)
        self.assertEqual(result.status,'accepted')
        request=audited.request_context_for(result.plan)
        self.assertEqual(request,backend.sent)
        self.assertEqual(request['macro_strategy']['fact_catalog']['own.credits'],4000)
        self.assertTrue(memory.review(result.plan,result.plan.macro_strategy,request).allowed)
        request['macro_strategy']['fact_catalog']['own.credits']=999
        self.assertEqual(audited.request_context_for(result.plan)['macro_strategy']['fact_catalog']['own.credits'],4000)
        # Measuring another candidate does not replace the actual sent request.
        audited.input_size(dict(backend.sent,snapshot_id=999))
        self.assertEqual(audited.request_context_for(result.plan)['snapshot_id'],1)
        with self.assertRaisesRegex(ValueError,'request_binding'):
            audited.request_context_for(replace(result.plan,snapshot_id=999))

    async def test_enabled_strategy_refuses_missing_declaration_before_dispatch(self):
        from integration.host_runtime.macro_policy_runtime import MacroRequestAudit
        observed=macro_snapshot();context=observed.model_context(binding());memory=memory_for(context);enc=encoder()
        class Backend:
            def input_size(self,value):return enc.input_size(value)
            async def __call__(self,value):return policy(value,macro_actions=['budgetarmy'])
        audit=MacroRequestAudit(Backend(),lambda *a,**k:None,strategy_supplier=memory.context)
        with self.assertRaisesRegex(ValueError,'declaration_missing'):await audit(context)

    async def test_wire_limit_is_enforced_before_provider_invocation(self):
        from integration.host_runtime.macro_policy_runtime import MacroRequestAudit
        observed=macro_snapshot();context=observed.model_context(binding());memory=memory_for(context)
        calls=[]
        class Backend:
            def input_size(self,value):return 16385
            async def __call__(self,value):calls.append(value);return {}
        audit=MacroRequestAudit(Backend(),lambda *a,**k:None,strategy_supplier=memory.context)
        with self.assertRaisesRegex(ValueError,'wire_bounds'):await audit(context)
        self.assertEqual(calls,[])

    async def test_heavily_escaped_style_retains_data_and_is_refused_if_wire_overflows(self):
        from integration.host_runtime.macro_policy_runtime import MacroRequestAudit
        from test_macro_strategy_wire import pressure_context
        from test_macro_group_role_wire import offline_adapter
        from tacticore_agent_runtime.factory import NetworkBackend
        context,profile,memory=pressure_context();calls=[]
        traits='正常风格'*32+'"'*800
        self.assertLessEqual(len(traits.encode('utf8')),1200)
        enc=offline_adapter(profile,traits=traits)
        measured=NetworkBackend.__new__(NetworkBackend)
        measured._prompt=lambda value:system_prompt(enc.profile,value)
        class Backend:
            def input_size(self,value):return measured.input_size(value)
            async def __call__(self,value):calls.append(value);return {}
        audit=MacroRequestAudit(Backend(),lambda *a,**k:None,strategy_supplier=memory.context)
        with self.assertRaisesRegex(ValueError,'wire_bounds'):await audit(context)
        self.assertEqual(calls,[])
        self.assertIsNone(audit._last_request_context)


if __name__=='__main__':unittest.main()
