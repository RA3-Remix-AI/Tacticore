"""Strategic model -> real Host/journal/controller, artificial native transport.

These tests prove routing and refusal, never live-game or model qualification.
"""
import asyncio
import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
import uuid

from battle_agent import BattleAgent
from engine import Binding, StrategyEngine, Snapshot
from fixtures import SESSION, CONNECTION, policy, snapshot
from http_adapter import macro_system_prompt
from macro_host import MacroHost
from host_runtime.contracts import ContractError, SessionBinding
from host_runtime.journal import CommandJournal
from host_runtime.macro_durable import DurableMacroTransport
from host_runtime.macro_policy_runtime import BudgetController, BudgetScope, MacroRequestAudit, COMMANDER
from host_runtime.macro_delegation_boundary_v1 import (
    KIND, STRATEGIC_ACTIONS, restrict_snapshot, restrict_context, validate_policy,
)


def raw_view():
    return snapshot(macro_control=dict(mode='macro_native',
        available_actions=['budgetarmy', 'budgeteconomy', 'producebullfrog', 'buildrefinery'],
        production_counts={'producebullfrog': [1]}))


def model_policy(context, **changes):
    return policy(context, production_focus='native_baseline', objective_region=None,
                  macro_actions=['budgetarmy'], macro_production=None,
                  tactical_tasks=[], runtime_task=None, **changes)


class BoundaryTests(unittest.TestCase):
    def test_snapshot_removes_specific_authority_and_keeps_original_observation(self):
        before=raw_view(); after=restrict_snapshot(before)
        self.assertEqual(after['macro_control']['available_actions'], ['budgetarmy','budgeteconomy'])
        self.assertEqual(after['macro_control']['production_counts'], {})
        self.assertEqual(after['capabilities']['production_focus'], ['native_baseline'])
        self.assertEqual(after['resources'], before['resources'])
        self.assertEqual(after['enemy_observations'], before['enemy_observations'])
        self.assertIn('producebullfrog', before['macro_control']['available_actions'])
        Snapshot.from_dict(after)

    def test_context_does_not_grant_absent_high_level_routes(self):
        result=restrict_context(dict(allowed_macro_actions=['producebullfrog','buildrefinery'],
            macro_policy_catalog={'producebullfrog':{}, 'buildrefinery':{}},
            macro_resource_feedback={'unnecessary':'exact ledger'}))
        self.assertEqual(result['allowed_macro_actions'], [])
        self.assertEqual(result['macro_policy_catalog'], {})
        self.assertNotIn('macro_resource_feedback',result)
        self.assertIn('not_global_native_stop',result['native_delegation']['empty_actions'])
        self.assertIn('not_construction_or_expansion_permission',result['native_delegation']['budget_actions'])

    def test_rejects_each_existing_specific_action(self):
        from macro_policy import ACTIONS
        for action in set(ACTIONS)-STRATEGIC_ACTIONS:
            with self.subTest(action=action), self.assertRaises(ContractError):
                validate_policy(dict(macro_actions=[action],production_focus='native_baseline'))

    def test_quantity_cannot_be_smuggled_with_budget(self):
        with self.assertRaisesRegex(ContractError,'quantity_refused'):
            validate_policy(dict(macro_actions=['budgetarmy'],production_focus='native_baseline',
                                 macro_production={'action':'producebullfrog','additional_count':1}))

    def test_contact_projection_is_idempotent_and_does_not_refresh_hidden_facts(self):
        contacts=[dict(contact_id=str(i),region_id='east_ore',role='armor',relation='enemy',
                       currently_visible=visible,observed_at_game_seconds=at)
                  for i,visible,at in ((1,True,99),(2,True,98),(3,False,70))]
        before=dict(working_memory=dict(battlefield=dict(contacts=contacts)),allowed_macro_actions=['scout'])
        after=restrict_context(before)
        self.assertEqual(restrict_context(after),after)
        groups=after['working_memory']['battlefield']['contact_groups']
        self.assertEqual(len(groups),2)
        self.assertEqual((groups[0]['oldest_game_seconds'],groups[0]['newest_game_seconds'],groups[0]['observations']),(98,99,2))
        self.assertFalse(groups[1]['currently_visible'])
        self.assertEqual(groups[1]['newest_game_seconds'],70)
        self.assertEqual(before['working_memory']['battlefield']['contacts'],contacts)

    def test_composition_and_unit_orders_are_refused(self):
        for extra in ({'production_focus':'anti_air'}, {'tactical_tasks':[{'unit_id':1}]},
                      {'runtime_task':{'unit_id':1}}):
            value=dict(macro_actions=['budgetarmy'],production_focus='native_baseline');value.update(extra)
            with self.subTest(extra=extra),self.assertRaises(ContractError):validate_policy(value)

    def test_prompt_preserves_native_ownership_without_quantity_contract(self):
        context=Snapshot.from_dict(restrict_snapshot(raw_view())).model_context(Binding(SESSION,3,COMMANDER,'Test',CONNECTION))
        context=restrict_context(context)
        profile=SimpleNamespace(traits='normal',personality=0)
        text=macro_system_prompt(profile,context)
        self.assertIn('native AI owns ALL building',text)
        self.assertIn('does NOT stop all native',text)
        self.assertNotIn('additional_count',text)
        self.assertNotIn('producebullfrog',text)

    def test_prompt_exposes_only_offered_regional_targets_after_alias_packing(self):
        from macro_policy import project_strategy_defaults,public_descriptions
        context=Snapshot.from_dict(restrict_snapshot(raw_view())).model_context(Binding(SESSION,3,COMMANDER,'Test',CONNECTION))
        context=restrict_context(context)
        context['allowed_macro_actions']=['regroup','deployattack','advanceproduction']
        context['allowed_regions']=['region_8_3','region_1_3']
        context['macro_policy_catalog']=public_descriptions(['regroup','deployattack','advanceproduction','deploydefense'],
            region_targets={'regroup':'region_8_3','deployattack':'region_1_3','deploydefense':'region_8_3'})
        packed=project_strategy_defaults(context);before=copy.deepcopy(packed)
        text=macro_system_prompt(SimpleNamespace(traits='normal',personality=0),packed)
        targets=json.loads(next(line.removeprefix('RegionMap: ') for line in text.splitlines() if line.startswith('RegionMap: ')))
        self.assertEqual(targets,{'regroup':'region_8_3','deployattack':'region_1_3'})
        self.assertEqual(packed,before)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.events=[]
        self.view=restrict_snapshot(raw_view())
        self.binding=Binding(SESSION,3,COMMANDER,'Test',CONNECTION)
        self.agent=BattleAgent(StrategyEngine(self.binding,min_hold_game_seconds=0))
        self.calls=[]

    def decide(self,changes=None):
        outer=self
        class Model:
            def input_size(self,context):return len(json.dumps(context).encode())
            async def __call__(self,context):
                outer.calls.append(copy.deepcopy(context))
                result=model_policy(context)
                result.update(changes or {})
                return result
        audit=MacroRequestAudit(Model(),lambda kind,**v:self.events.append((kind,v)),strategic_only=True)
        return asyncio.run(self.agent.decide(self.view,audit))

    def host(self):
        host=MacroHost.__new__(MacroHost);host.strategic_only=True
        host.binding=SessionBinding(1,SESSION,3,COMMANDER,101,'2026-10-29T00:00:00+00:00',CONNECTION,'c'*64,'a'*64)
        host.output=self.folder;host.started=time.monotonic();host.latest=copy.deepcopy(self.view)
        host.expected_hash='b'*64;host.run_id=str(uuid.uuid4());host.prepared_macro_commands={}
        host.strategy_runtime=None;host.agent=self.agent
        host.journal=CommandJournal(self.folder/'journal.sqlite3');self.addCleanup(host.journal.close)
        host.journal.register_run(host.run_id,host.binding.public())
        class Native:
            session=dict(session_id=SESSION,mod_sha256='a'*64)
            def __init__(self):self.calls=[]
            def apply(self,actions,duration,command):
                self.calls.append((actions,duration,command))
                return dict(seq=len(self.calls),native=dict(last_frame=1501,deadline_frame=1501+duration))
            def close(self):pass
        host.transport=Native()
        scope=BudgetScope('a'*64,{},('private',),{'budgetarmy':'private-army','budgeteconomy':'private-economy'},{})
        host.controller=BudgetController(DurableMacroTransport(host.transport,host.journal,host.run_id),
                                         scope,SESSION,host.expected_hash,host.event)
        return host

    def test_real_model_contract_host_journal_controller_route_budget_intent(self):
        decision=self.decide();self.assertEqual(decision.status,'accepted',decision.reason_code)
        self.assertEqual(self.calls[0]['native_delegation']['kind'],KIND)
        self.assertEqual(self.calls[0]['allowed_macro_actions'],['budgetarmy','budgeteconomy'])
        host=self.host();self.assertTrue(host.dispatch_plan(decision.plan))
        self.assertEqual(host.transport.calls[0][0],['budgetarmy'])
        self.assertEqual(host.journal.commands_for_run(host.run_id)[0]['status'],'completed')
        # An ACK is deliberately not represented as a strategic effect.
        self.assertFalse(host.controller.sent[decision.plan.plan_id]['native_effect_verified'])

    def test_host_gate_refuses_old_specific_plan_even_if_model_audit_is_bypassed(self):
        plan=self.decide().plan;host=self.host()
        detailed=replace(plan,macro_actions=('producebullfrog',))
        self.assertFalse(host.dispatch_plan(detailed))
        self.assertEqual(host.transport.calls,[])
        self.assertEqual(host.journal.commands_for_run(host.run_id),[])

    def test_model_detailed_response_is_rejected_before_host(self):
        result=self.decide({'macro_actions':['producebullfrog']})
        self.assertEqual(result.status,'local_fallback')
        self.assertEqual(result.reason_code,'strategic_boundary_detailed_action_refused')
        self.assertEqual(self.agent.engine.metrics['adapter_errors'],0)

    def test_dynamic_host_availability_cannot_reoffer_precise_actions(self):
        host=self.host()
        host.controller=SimpleNamespace(available_actions=lambda at: ['budgetarmy','producebullfrog','buildpower'])
        host.sampler=SimpleNamespace(scope=SimpleNamespace(production_counts={'producebullfrog':(1,)}))
        host.update_macro_control(100)
        self.assertEqual(host.latest['macro_control']['available_actions'],['budgetarmy'])
        self.assertEqual(host.latest['macro_control']['production_counts'],{})

    def test_async_prepared_request_preserves_boundary_and_validates_response(self):
        from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1,decide_prepared_macro_request_v1
        self.agent.observe(self.view)
        outer=self
        class Model:
            def input_size(self,context):return len(json.dumps(context).encode())
            async def __call__(self,context):
                outer.calls.append(context)
                result=model_policy(context);result['macro_actions']=['producebullfrog'];return result
        audit=MacroRequestAudit(Model(),lambda *a,**v:None,strategic_only=True)
        prepared=prepare_macro_request_v1(self.agent,audit,self.agent.latest)
        self.assertTrue(prepared.measure.strategic_only)
        self.assertTrue(prepared.sender.strategic_only)
        result=asyncio.run(decide_prepared_macro_request_v1(self.agent,self.agent.latest,prepared))
        self.assertEqual(self.calls[0]['native_delegation']['kind'],KIND)
        self.assertEqual(result.reason_code,'strategic_boundary_detailed_action_refused')
        self.assertEqual(self.agent.engine.metrics['adapter_errors'],0)


if __name__=='__main__':unittest.main()
