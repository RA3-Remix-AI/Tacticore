"""Independent offline semantic checks of declared-strategy Host integration.

No live process, provider, registry, protected library or game path is opened.
Several adversarial cases deliberately assert stricter evidence boundaries than
an ACK, an old cumulative tracker, or a model TTL alone can establish.
"""
import copy
from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
import uuid

from macro_host import MacroHost
from host_runtime.contracts import ContractError
from host_runtime.macro_policy_runtime import MacroRequestAudit, BudgetController, BudgetScope, COMMANDER
from host_runtime.macro_strategy_runtime import MacroStrategyRuntime
from battle_agent import BattleAgent
from engine import Binding, Snapshot, StrategyEngine, validate_policy
from fixtures import snapshot, policy, SESSION, CONNECTION
from macro_strategy import MacroStrategyMemory


def declaration(strategy_id=None):
    return dict(strategy_id=strategy_id,objective='build_force',phase='prepare',
        public_fact_refs=['own.credits'],expected_observation='production_queue',
        continue_conditions=['capability_available'],replan_conditions=['facts_changed'],
        resource_priorities=dict(economy=.2,army=.5,tech=.1,reserve=.2))


def native(seq=1, *, empty=False):
    return dict(active=0 if empty else 1,request=seq,ack=seq,error=0,phase=1,
                applied_mask=0 if empty else 512)


class RuntimeSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.binding=Binding(SESSION,3,COMMANDER,'offline',CONNECTION)
        self.events=[]
        self.memory=MacroStrategyMemory(session_id=SESSION,commander_id=COMMANDER,player_id=3,
            profile_revision=21,effective_hash='b'*64,min_hold_seconds=0)
        self.runtime=MacroStrategyRuntime(self.memory,self.event)
        self.requests={}
        self.sequence=0

    def event(self,kind,**facts):
        self.events.append(dict(kind=kind,**facts))

    def build(self,at=100,actions=('budgetarmy',),*,expires=30,strategy_id=None):
        raw=snapshot(at=at,ident=int(at))
        raw['macro_control']=dict(mode='macro_native',available_actions=[
            'budgetarmy','budgeteconomy','produceconscript','buildreactor','scout','regroup'],
            production_counts={'produceconscript':[1]},region_targets={'regroup':'home_base'})
        observed=Snapshot.from_dict(raw)
        agent=BattleAgent(StrategyEngine(self.binding));agent.observe(raw)
        context=agent.context(observed.model_context(self.binding))
        context['macro_strategy']=self.memory.context(context)
        answer=policy(context,macro_actions=list(actions),macro_strategy=declaration(strategy_id),
            production_focus='native_baseline',valid_for_game_seconds=expires)
        if 'produceconscript' in actions:answer['macro_production']=dict(action='produceconscript',additional_count=1)
        plan=validate_policy(answer,observed,observed,self.binding,20)
        self.requests[plan.plan_id]=copy.deepcopy(context)
        return plan,context,agent,raw

    def review(self,plan,context):
        audit=SimpleNamespace(request_context_for=lambda p:copy.deepcopy(self.requests[p.plan_id]))
        return self.runtime.review(plan,audit,context)

    def dispatch(self,at=100,actions=('budgetarmy',),*,unknown=False,receipt_changes=None,strategy_id=None):
        plan,context,agent,raw=self.build(at,actions,strategy_id=strategy_id)
        review=self.review(plan,context)
        self.assertTrue(review.allowed,review.reason_code)
        self.sequence+=1
        receipt=dict(command_id=str(uuid.uuid4()),seq=self.sequence,native_gate_acknowledged=True,
            plan_id=plan.plan_id,actions=list(plan.macro_actions),native_start_frame=int(at*15),
            native_deadline_frame=int(plan.expires_at_game_seconds*15))
        receipt.update(receipt_changes or {})
        self.runtime.dispatched(review,plan,None if unknown else receipt,at,
            unknown_command_id=receipt['command_id'] if unknown else None)
        return plan,receipt,review,agent,raw

    def effects(self):
        return [e for e in self.events if e['kind']=='macro_strategy_outcome' and e['outcome']=='effect_observed']

    @staticmethod
    def tracker(plan_id,**facts):
        return SimpleNamespace(active_plan=(plan_id,130),tracker=SimpleNamespace(public=lambda:dict(facts)))

    def test_gate_ack_and_zero_work_counts_do_not_establish_effect(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        self.assertEqual(self.effects(),[])
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=0,
            builder_frame=1515,own_census_frame=1515)
        self.runtime.observe(controller,native(r['seq']),102)
        self.assertEqual(self.effects(),[])

    def test_a_positive_queue_from_another_plan_is_not_borrowed(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        controller=self.tracker('unrelated-plan',action='produceconscript',observed_new_queue_count=2,
            builder_frame=1515,own_census_frame=1515)
        self.runtime.observe(controller,native(r['seq']),102)
        self.assertEqual(self.effects(),[])

    def test_matching_effect_in_window_reaches_real_long_term_memory(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=1,
            builder_frame=1515,own_census_frame=1515)
        self.runtime.observe(controller,native(r['seq']),102)
        self.assertEqual(len(self.effects()),1)
        self.assertTrue(self.memory._commands[r['command_id']]['had_effect'])
        self.assertEqual(self.memory._commands[r['command_id']]['plan_id'],p.plan_id)

    def test_expansion_tracker_is_bound_to_its_own_plan_and_window(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        value=dict(action='produceconscript',observed_new_queue_count=1,
            builder_frame=1515,own_census_frame=1515,policy_released=False)
        controller=SimpleNamespace(expansion_plan=('other-plan',130),
            expansion_tracker=SimpleNamespace(public=lambda:dict(value)))
        self.runtime.observe(controller,native(r['seq']),102)
        self.assertEqual(self.effects(),[])
        controller.expansion_plan=(p.plan_id,130)
        self.runtime.observe(controller,native(r['seq']),102)
        self.assertEqual(len(self.effects()),1)

    def test_model_expiry_boundary_cannot_be_reported_as_an_effect(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=1,
            builder_frame=1950,own_census_frame=1950)
        self.runtime.observe(controller,native(r['seq']),130)
        self.assertEqual(self.effects(),[])

    def test_cross_deadline_pair_cannot_be_sliced_to_the_earlier_builder_frame(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=1,
            builder_frame=1949,own_census_frame=1951)
        self.runtime.observe(controller,native(r['seq']),130.1)
        self.assertEqual(self.effects(),[], 'the census after expiry is part of the same claimed evidence')

    def test_native_window_cannot_be_expanded_to_the_longer_model_ttl(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',),receipt_changes={
            'native_start_frame':1515,'native_deadline_frame':1650})
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=1,
            builder_frame=1665,own_census_frame=1665)
        self.runtime.observe(controller,native(r['seq']),112)
        self.assertEqual(self.effects(),[], 'post-native-deadline queues are not this command effect')

    def test_prior_to_actual_native_start_is_not_counted(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',),receipt_changes={
            'native_start_frame':1530,'native_deadline_frame':1800})
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=1,
            builder_frame=1515,own_census_frame=1515)
        self.runtime.observe(controller,native(r['seq']),102)
        self.assertEqual(self.effects(),[])

    def test_released_tracker_cannot_first_establish_effect_from_cumulative_counts(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=1,
            builder_frame=1545,own_census_frame=1545,policy_released=True,release_reason='expired')
        self.runtime.observe(controller,native(r['seq']),104)
        self.assertEqual(self.effects(),[])

    def test_construction_without_positive_native_consumer_is_not_effect(self):
        p,r,_,_,_=self.dispatch(actions=('buildreactor',))
        controller=SimpleNamespace(construction_plan=(p.plan_id,130),construction_tracker=SimpleNamespace(public=lambda:dict(
            action='buildreactor',observed_new_queue_count=1,positive_native_build_state_observed=False,
            builder_frame=1515,own_census_frame=1515,policy_released=False)))
        self.runtime.observe(controller,native(r['seq']),102)
        self.assertEqual(self.effects(),[])

    def test_budget_adoption_does_not_mask_unfulfilled_work_in_combined_intent(self):
        p,r,_,_,_=self.dispatch(actions=('budgetarmy','produceconscript'))
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=0,
            builder_frame=1515,own_census_frame=1515)
        self.runtime.observe(controller,native(r['seq']),102,budget_feedback=dict(
            selected_policy='budgetarmy',native_effect_verified=True,observed_frame=1515))
        self.assertFalse(self.memory._commands[r['command_id']]['had_effect'],
            'work-success/retry guard cannot be satisfied solely by its budget companion')

    def test_known_replacement_requires_new_ack_and_ends_old_effect_window(self):
        first,r,review,_,_=self.dispatch()
        next_plan,context,_,_=self.build(102,('budgeteconomy',),strategy_id=review.strategy_id)
        next_review=self.review(next_plan,context)
        with self.assertRaisesRegex(ContractError,'receipt_required'):
            self.runtime.dispatched(next_review,next_plan,dict(command_id='unacked',seq=2,native_gate_acknowledged=False),102)
        self.assertFalse(self.runtime.commands[r['command_id']].released)
        self.runtime.dispatched(next_review,next_plan,dict(command_id='second',seq=2,native_gate_acknowledged=True,
            plan_id=next_plan.plan_id,actions=['budgeteconomy']),102)
        self.assertTrue(self.runtime.commands[r['command_id']].released)
        self.assertEqual(self.memory._commands[r['command_id']]['outcome'],'replaced')

    def test_receipt_for_a_different_plan_or_actions_is_refused(self):
        p,context,_,_=self.build()
        review=self.review(p,context)
        with self.assertRaises(ContractError):
            self.runtime.dispatched(review,p,dict(command_id='wrong-receipt',seq=1,native_gate_acknowledged=True,
                plan_id=str(uuid.uuid4()),actions=['budgeteconomy']),100)
        self.assertEqual(self.memory._commands,{})

    def test_reusing_an_old_ack_sequence_is_not_a_new_replacement_ack(self):
        _,r,first,_,_=self.dispatch()
        p,context,_,_=self.build(102,('budgeteconomy',),strategy_id=first.strategy_id)
        reviewed=self.review(p,context)
        with self.assertRaises(ContractError):
            self.runtime.dispatched(reviewed,p,dict(command_id='new-id-old-sequence',seq=r['seq'],
                native_gate_acknowledged=True,plan_id=p.plan_id,actions=list(p.macro_actions)),102)
        self.assertFalse(self.runtime.commands[r['command_id']].released)

    def test_unknown_replacement_does_not_release_and_blocks_every_new_intent(self):
        first,r,review,_,_=self.dispatch()
        p,context,_,_=self.build(102,('budgeteconomy',),strategy_id=review.strategy_id)
        waiting=self.review(p,context)
        self.runtime.dispatched(waiting,p,None,102,unknown_command_id='uncertain-second')
        self.assertFalse(self.runtime.commands[r['command_id']].released)
        p3,c3,_,_=self.build(200,('regroup',),strategy_id=review.strategy_id)
        self.assertEqual(self.review(p3,c3).reason_code,'strategy_unknown_outcome')

    def test_unknown_empty_gate_clear_cannot_disappear_from_the_global_barrier(self):
        _,r,review,_,_=self.dispatch()
        p,context,_,_=self.build(102,(),strategy_id=review.strategy_id)
        waiting=self.review(p,context)
        self.runtime.dispatched(waiting,p,None,102,unknown_command_id='uncertain-clear')
        self.assertFalse(self.runtime.commands[r['command_id']].released)
        p3,c3,_,_=self.build(200,('regroup',),strategy_id=review.strategy_id)
        self.assertEqual(self.review(p3,c3).reason_code,'strategy_unknown_outcome')

    def test_known_empty_actions_keep_strategy_and_clear_gates_through_the_real_host(self):
        _,_,review,_,_=self.dispatch()
        p,request,agent,raw=self.build(102,(),strategy_id=review.strategy_id)
        calls=[]
        scope=BudgetScope('a'*64,{},('x','y'),{'budgeteconomy':'x','budgetarmy':'y'},{})
        transport=SimpleNamespace(session={'session_id':SESSION,'mod_sha256':'a'*64},
            apply=lambda actions,duration,ident:(calls.append((list(actions),duration,ident)) or {'seq':2}),close=lambda:None)
        controller=BudgetController(transport,scope,SESSION,'b'*64,self.event)
        host=MacroHost.__new__(MacroHost)
        host.latest=raw;host.agent=agent;host.strategy_runtime=self.runtime;host.controller=controller
        host.expected_hash='b'*64;host.event=self.event
        host.strategy_audit=SimpleNamespace(prepare=lambda value:value,request_context_for=lambda plan:copy.deepcopy(request))
        self.assertTrue(host.dispatch_plan(p))
        self.assertEqual(calls[0][0],[])
        self.assertEqual(self.memory.context(request)['current_strategy']['strategy_id'],review.strategy_id)
        self.assertTrue(all(row.released for row in self.runtime.commands.values()))

    def test_malformed_native_boolean_cannot_prove_release(self):
        _,r,_,_,_=self.dispatch()
        state=native(r['seq'],empty=True);state['active']=False
        try:self.runtime.observe(SimpleNamespace(),state,102)
        except ContractError:pass  # Typed refusal or ignored invalid telemetry are both safe.
        self.assertFalse(self.runtime.commands[r['command_id']].released)

    def test_sample_time_regression_does_not_change_an_already_verified_outcome(self):
        p,r,_,_,_=self.dispatch(actions=('produceconscript',))
        controller=self.tracker(p.plan_id,action='produceconscript',observed_new_queue_count=1,
            builder_frame=1530,own_census_frame=1530)
        self.runtime.observe(controller,native(r['seq']),103)
        before=copy.deepcopy(self.memory._commands)
        try:self.runtime.observe(SimpleNamespace(),native(r['seq'],empty=True),101)
        except ContractError:pass
        self.assertEqual(self.memory._commands,before)

    def test_finish_with_unproven_release_stops_new_host_dispatch_without_inventing_release(self):
        _,r,review,_,_=self.dispatch()
        self.runtime.finish(102,release_verified=False)
        self.assertFalse(self.runtime.commands[r['command_id']].released)
        p,request,agent,raw=self.build(103,('budgeteconomy',),strategy_id=review.strategy_id)
        calls=[]
        host=MacroHost.__new__(MacroHost);host.latest=raw;host.agent=agent;host.strategy_runtime=self.runtime
        host.expected_hash='b'*64;host.event=self.event;host.controller=SimpleNamespace(dispatch=lambda *a,**k:calls.append(a))
        host.strategy_audit=SimpleNamespace(prepare=lambda value:value,request_context_for=lambda plan:copy.deepcopy(request))
        self.assertFalse(host.dispatch_plan(p))
        self.assertEqual(calls,[])

    def test_verified_finish_cancels_unknown_only_after_release_proof(self):
        _,r,_,_,_=self.dispatch(unknown=True)
        self.runtime.finish(105,release_verified=True)
        self.assertTrue(self.runtime.commands[r['command_id']].released)
        self.assertEqual(self.memory._commands[r['command_id']]['outcome'],'cancelled')


class QuoteBudgetBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_quote_overflow_is_rejected_before_provider_and_cannot_be_a_request_context(self):
        from test_macro_strategy_wire import pressure_context
        from test_macro_group_role_wire import offline_adapter
        from tacticore_agent_runtime.factory import NetworkBackend
        from http_adapter import system_prompt
        context,profile,memory=pressure_context();calls=[]
        encoder=offline_adapter(profile,traits='正常风格'*32+'"'*800)
        measured=NetworkBackend.__new__(NetworkBackend);measured._prompt=lambda value:system_prompt(encoder.profile,value)
        class Backend:
            def input_size(self,value):return measured.input_size(value)
            async def __call__(self,value):calls.append(value);return {}
        audit=MacroRequestAudit(Backend(),lambda *a,**k:None,strategy_supplier=memory.context)
        with self.assertRaisesRegex(ContractError,'wire_bounds'):await audit(context)
        self.assertEqual(calls,[])
        self.assertIsNone(audit._last_request_context)


if __name__=='__main__':unittest.main()
