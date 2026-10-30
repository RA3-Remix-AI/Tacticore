"""Real Host/Agent/StrategyRuntime/controller path, artificial native inputs."""
import asyncio
import copy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
import uuid

from macro_host import MacroHost
from battle_agent import BattleAgent
from engine import Binding,Snapshot,StrategyEngine
from fixtures import SESSION,CONNECTION,policy
from tactical_fixtures import tactical_snapshot
from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.journal import CommandJournal
from host_runtime.macro_durable import DurableMacroTransport
from host_runtime.macro_policy_runtime import BudgetScope,COMMANDER,MacroRequestAudit
from host_runtime.macro_production_runtime import ProductionPreferenceScope,MacroProductionController
from host_runtime.macro_strategy_runtime import MacroStrategyRuntime
from macro_strategy import MacroStrategyMemory
from host_runtime.test_macro_production_feedback import sample


def view(ident,frame):
    raw=tactical_snapshot(ident,frame/15)
    raw['macro_control']=dict(mode='macro_native',available_actions=['budgetarmy','budgeteconomy'])
    return raw


class Native:
    def __init__(self):
        self.session=dict(session_id=SESSION,mod_sha256='a'*64);self.frame=1502;self.calls=[];self.samples=[];self.failed_delivery=False
        builder,census=sample(1502)
        self.pair=dict(build_observation=builder,observation=dict(frame=1502,construction_feedback=census))
    def observe(self,label):self.samples.append(label);return copy.deepcopy(self.pair)
    def native_status(self):return dict(active=0,request=len(self.calls),ack=len(self.calls),error=0,phase=1,applied_mask=0,last_frame=self.frame)
    def apply(self,actions,duration,command):
        self.calls.append((list(actions),duration,command))
        if self.failed_delivery:raise RuntimeError('artificial transport outcome unknown')
        self.frame+=1
        return dict(seq=len(self.calls),native=dict(last_frame=self.frame,deadline_frame=self.frame+duration))
    def close(self):pass


class RevalidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);folder=Path(self.temp.name)
        self.host=host=MacroHost.__new__(MacroHost);host.output=folder;host.started=time.monotonic()
        host.binding=SessionBinding(1,SESSION,3,COMMANDER,101,'2026-10-29T00:00:00+00:00',CONNECTION,'c'*64,'a'*64)
        host.run_id=str(uuid.uuid4());host.expected_hash='b'*64;host.expected_revision=21;host.prepared_macro_commands={}
        host.journal=CommandJournal(folder/'journal.sqlite3');self.addCleanup(host.journal.close)
        host.journal.register_run(host.run_id,host.binding.public())
        scope=ProductionPreferenceScope(BudgetScope('a'*64,{},('private',),dict(budgetarmy='private-army',budgeteconomy='private-economy'),{}),
            'private-flak',{},extra_choices=(('produceconscript',(1,),'private-conscript'),))
        # This pre-Native5 production fixture retains its original protocol 1.
        host.transport_config=dict(protocol_version=getattr(scope,'native_transport_protocol',1))
        self.native=host.transport=Native()
        host.controller=MacroProductionController(DurableMacroTransport(self.native,host.journal,host.run_id),scope,SESSION,'b'*64,host.event)
        host.controller.refresh(copy.deepcopy(self.native.pair))
        binding=Binding(SESSION,3,COMMANDER,'offline',CONNECTION)
        host.agent=BattleAgent(StrategyEngine(binding,min_hold_game_seconds=0))
        initial=view(1,1500)
        initial['macro_control']=dict(mode='macro_native',available_actions=list(scope.available_actions),
            production_counts={action:list(counts) for action,counts in scope.production_counts.items()})
        host.latest=initial;host.agent.observe(initial)
        self.memory=MacroStrategyMemory(session_id=SESSION,commander_id=COMMANDER,player_id=3,
            profile_revision=21,effective_hash='b'*64,min_hold_seconds=0)
        host.strategy_runtime=MacroStrategyRuntime(self.memory,host.event)
        class Backend:
            def input_size(self,context):return 0
            async def __call__(self,context):
                return policy(context,macro_actions=['produceconscript','budgetarmy'],
                    macro_production=dict(action='produceconscript',additional_count=1),production_focus='native_baseline',
                    macro_strategy=dict(strategy_id=None,objective='build_force',phase='prepare',public_fact_refs=['own.credits','capabilities.actions'],
                        expected_observation='production_queue',continue_conditions=['capability_available'],replan_conditions=['facts_changed'],
                        resource_priorities=dict(economy=.2,army=.5,tech=.1,reserve=.2)))
        host.strategy_audit=MacroRequestAudit(Backend(),host.event,strategy_supplier=self.memory.context)
        result=asyncio.run(host.agent.decide(initial,host.strategy_audit))
        self.assertEqual(result.status,'accepted',result.reason_code);self.plan=result.plan
        self.pre=view(2,1501);self.post=view(3,1503);self.views=[self.pre,self.post];self.collected=[]
        census=dict(frame=1500,enemy_details_read=False,own_objects=[])
        host.sampler=SimpleNamespace(scope=scope,latest_census=census,safety=dict(templates={}),collect=self.collect)
        self.output=folder

    def collect(self):
        raw=copy.deepcopy(self.views.pop(0));self.collected.append(copy.deepcopy(raw))
        self.host.sampler.latest_census=dict(frame=round(raw['game_time_seconds']*15),enemy_details_read=False,own_objects=[])
        self.native.frame=max(self.native.frame,round(raw['game_time_seconds']*15))
        return raw

    def events(self):
        import json
        return [json.loads(line) for line in (self.output/'host-events.jsonl').read_text(encoding='utf8').splitlines()]

    def archived(self):
        import json
        return [json.loads(line) for line in (self.output/'macro-snapshots.jsonl').read_text(encoding='utf8').splitlines()]

    def test_real_dispatch_restores_work_only_from_fresh_pair_and_new_post_view(self):
        self.assertTrue(self.host.dispatch_plan(self.plan))
        self.assertEqual(self.native.samples,['desktop_macro_dispatch_revalidation'])
        self.assertEqual(self.native.calls[0][0],['produceconscript','budgetarmy'])
        self.assertEqual(self.host.agent.latest.snapshot_id,3)
        self.assertIn('produceconscript',self.host.agent.latest.macro_control)
        archived=self.archived();self.assertEqual([row['snapshot_id'] for row in archived],[2,3])
        self.assertEqual(archived[0]['macro_control']['available_actions'],['budgetarmy','budgeteconomy'])
        self.assertIn('produceconscript',archived[1]['macro_control']['available_actions'])
        self.assertEqual([row['game_time_seconds'] for row in archived],[self.pre['game_time_seconds'],self.post['game_time_seconds']])
        self.assertEqual(self.memory.public_state()['current_strategy']['objective'],'build_force')
        self.assertEqual(len(self.host.strategy_runtime.commands),1)
        self.assertEqual(self.host.journal.commands_for_run(self.host.run_id)[0]['status'],'completed')

    def test_original_budget_only_pre_view_reproduces_the_actual_strategy_rejection(self):
        self.host.latest=self.collect();self.host.observe_current()
        context=self.host.agent.context(self.host.agent.latest.model_context(self.host.agent.engine.binding),commit=False)
        with self.assertRaisesRegex(ContractError,'strategy_plan_capabilities'):
            self.host.strategy_runtime.review(self.plan,self.host.strategy_audit,self.host.strategy_audit.prepare(context))
        self.assertEqual(self.native.calls,[])

    def test_current_producer_loss_cannot_reuse_request_capabilities(self):
        builder,census=sample(1502,alive=False)
        self.native.pair=dict(build_observation=builder,observation=dict(frame=1502,construction_feedback=census))
        self.assertFalse(self.host.dispatch_plan(self.plan));self.assertEqual(self.native.calls,[])
        self.assertNotIn('produceconscript',self.host.agent.latest.macro_control)
        self.assertEqual(self.events()[-1]['reason_code'],'strategy_plan_capabilities')

    def test_unqualified_action_cannot_become_available_from_revalidation(self):
        forged=replace(self.plan,macro_actions=('producetank','budgetarmy'),
            macro_production=replace(self.plan.macro_production,action='producetank'))
        self.assertFalse(self.host.dispatch_plan(forged));self.assertEqual(self.native.calls,[])
        self.assertEqual(self.events()[-1]['reason_code'],'strategy_plan_capabilities')

    def test_bad_pair_keeps_real_pre_view_history_and_never_dispatches(self):
        self.native.pair['build_observation']['frame']=1540
        self.assertFalse(self.host.dispatch_plan(self.plan));self.assertEqual(self.native.calls,[])
        self.assertEqual(len(self.collected),1);self.assertEqual(self.host.agent.latest.snapshot_id,2)
        self.assertEqual([row['snapshot_id'] for row in self.archived()],[2])
        self.assertEqual(self.events()[-1]['reason_code'],'macro_dispatch_native_pair_deferred')

    def test_stale_post_view_is_observed_once_and_its_new_contact_can_later_be_hidden(self):
        self.post=view(3,1520);new=dict(contact_id='only_post_contact',owner_player_id=4,relation='enemy',role='armor',
            region_id='east_ore',observed_at_game_seconds=1520/15,currently_visible=True,stealth_state='visible')
        self.post['battlefield']['contacts'].append(new);self.views=[self.pre,self.post]
        self.assertFalse(self.host.dispatch_plan(self.plan));self.assertEqual(self.native.calls,[])
        self.assertEqual([row['snapshot_id'] for row in self.archived()],[2,3])
        self.assertEqual(self.host.agent.latest.snapshot_id,3)
        hidden=view(4,1521);hidden['battlefield']['contacts'].append(dict(new,currently_visible=False))
        self.host.latest=hidden;self.host.observe_current()
        self.assertFalse(self.host.agent.contact_facts['only_post_contact']['currently_visible'])
        self.assertEqual(self.host.agent.contact_facts['only_post_contact']['observed_at_game_seconds'],1520/15)

    def test_expired_post_view_is_preserved_without_new_work(self):
        self.post=view(3,1950);self.views=[self.pre,self.post]
        self.assertFalse(self.host.dispatch_plan(self.plan));self.assertEqual(self.native.calls,[])
        self.assertEqual([row['snapshot_id'] for row in self.archived()],[2,3])
        self.assertEqual(self.events()[-1]['reason_code'],'expired_or_paused')

    def test_post_availability_failure_does_not_drop_new_visible_history(self):
        new=dict(contact_id='post_failure_contact',owner_player_id=4,relation='enemy',role='armor',
            region_id='east_ore',observed_at_game_seconds=self.post['game_time_seconds'],currently_visible=True,stealth_state='visible')
        self.post['battlefield']['contacts'].append(new);self.views=[self.pre,self.post]
        original=self.host.controller.available_actions
        def unavailable(at):
            if at==self.post['game_time_seconds']:raise ContractError('offline_availability_unverified')
            return original(at)
        self.host.controller.available_actions=unavailable
        with self.assertRaisesRegex(ContractError,'offline_availability_unverified'):self.host.dispatch_plan(self.plan)
        self.assertEqual(self.native.calls,[]);self.assertEqual([r['snapshot_id'] for r in self.archived()],[2,3])
        hidden=view(4,1504);hidden['battlefield']['contacts'].append(dict(new,currently_visible=False))
        self.host.latest=hidden;self.host.observe_current()
        self.assertFalse(self.host.agent.contact_facts['post_failure_contact']['currently_visible'])

    def test_paused_post_view_is_preserved_without_dispatch(self):
        self.post['paused']=True
        self.assertFalse(self.host.dispatch_plan(self.plan));self.assertEqual(self.native.calls,[])
        self.assertEqual([row['snapshot_id'] for row in self.archived()],[2,3])
        self.assertTrue(self.host.agent.latest.paused)

    def test_unknown_transport_stays_unknown_and_is_not_retried(self):
        self.native.failed_delivery=True
        with self.assertRaisesRegex(ContractError,'macro_dispatch_outcome_unknown'):self.host.dispatch_plan(self.plan)
        self.assertEqual(len(self.native.calls),1)
        self.assertEqual(self.host.journal.commands_for_run(self.host.run_id)[0]['status'],'uncertain')
        self.assertEqual(self.memory.public_state()['unknown_command_count'],1)


if __name__=='__main__':unittest.main()
