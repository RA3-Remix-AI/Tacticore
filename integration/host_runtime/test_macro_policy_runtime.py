"""Macro dispatch lifecycle checks; no game process or provider is opened."""
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
import uuid

from .contracts import ContractError
from .macro_policy_runtime import (BudgetController,BudgetScope,MacroRequestAudit,COMMANDER,PRESETS,
                                   ratios_match,verify_budget_scope)

ROOT=Path(__file__).resolve().parents[2]


class MacroBudgetTests(unittest.TestCase):
    def setUp(self):
        self.session=str(uuid.uuid4());self.calls=[];self.events=[]
        self.scope=BudgetScope('a'*64,{},('private flag',),
            {'budgeteconomy':'private economy','budgetarmy':'private army'},{})
        def apply(actions,duration,ident):
            self.calls.append((actions,duration,ident));return {'seq':len(self.calls)}
        self.transport=SimpleNamespace(session={'session_id':self.session,'mod_sha256':'a'*64},
            apply=apply,close=lambda:self.calls.append('closed'))
        self.controller=BudgetController(self.transport,self.scope,self.session,'b'*64,
            lambda kind,**facts:self.events.append(dict(kind=kind,**facts)))
        self.plan=SimpleNamespace(origin='model',session_id=self.session,commander_id=COMMANDER,
            player_id=3,based_on_game_time_seconds=100.,expires_at_game_seconds=140.,
            tactical_tasks=(),runtime_task=None,macro_actions=('budgeteconomy',),plan_id='plan1')

    def dispatch(self,**kwargs):
        return self.controller.dispatch(self.plan,110.,effective_hash='b'*64,**kwargs)

    def test_duplicate_plan_does_not_renew_native_deadline(self):
        first=self.dispatch();second=self.dispatch()
        self.assertEqual(first,second);self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0][1],450)
        self.assertFalse(first['native_effect_verified'])
        self.assertNotIn('private',json.dumps(self.events))

    def test_plan_id_conflict_refused(self):
        self.dispatch();self.plan.macro_actions=('budgetarmy',)
        with self.assertRaisesRegex(ContractError,'macro_plan_id_conflict'):self.dispatch()
        self.assertEqual(len(self.calls),1)

    def test_revised_profile_pause_and_expired_plans_refused(self):
        with self.assertRaisesRegex(ContractError,'revision_changed'):
            self.controller.dispatch(self.plan,110.,effective_hash='c'*64)
        with self.assertRaisesRegex(ContractError,'paused'):self.dispatch(paused=True)
        for at in (99.,140.,float('nan')):
            with self.assertRaisesRegex(ContractError,'binding_or_expiry'):
                self.controller.dispatch(self.plan,at,effective_hash='b'*64)
        self.assertEqual(self.calls,[])

    def test_wrong_binding_or_local_fallback_cannot_dispatch(self):
        for field,value in [('session_id',str(uuid.uuid4())),('commander_id','other'),
                            ('player_id',4),('origin','local_fallback')]:
            old=getattr(self.plan,field);setattr(self.plan,field,value)
            with self.subTest(field=field),self.assertRaises(ContractError):self.dispatch()
            setattr(self.plan,field,old)
        self.assertEqual(self.calls,[])

    def test_unqualified_actions_or_unit_tasks_refused(self):
        for actions in [('buildreactor',),('budgeteconomy','budgetarmy')]:
            self.plan.macro_actions=actions
            with self.assertRaisesRegex(ContractError,'not_qualified'):self.dispatch()
        self.plan.macro_actions=();self.plan.runtime_task=object()
        with self.assertRaisesRegex(ContractError,'unit_tasks'):self.dispatch()
        self.assertEqual(self.calls,[])

    def test_unknown_command_is_terminal_and_not_blindly_retried(self):
        def fail(*args):self.calls.append('uncertain');raise RuntimeError('private detail')
        self.transport.apply=fail
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
        with self.assertRaisesRegex(ContractError,'stopped'):self.dispatch()
        self.assertEqual(self.calls,['uncertain'])
        self.assertNotIn('private detail',json.dumps(self.events))

    def test_quantity_payload_cannot_bypass_budget_only_scope(self):
        self.plan.macro_production={'action':'produceflak','additional_count':2}
        with self.assertRaisesRegex(ContractError,'not_qualified'):self.dispatch()
        self.assertEqual(self.calls,[])

    def test_gate_ack_does_not_mean_native_effect(self):
        self.dispatch()
        sample={'frame':1700,'budget_feedback':{'selected_macro_flag':None,
            'account_shares':dict(PRESETS['budgetarmy'])}}
        self.assertEqual(self.controller.feedback(sample)['status'],'native_budget_pending')
        sample['budget_feedback']['selected_macro_flag']='private economy'
        self.assertFalse(self.controller.feedback(sample)['native_effect_verified'])
        sample['budget_feedback']['account_shares']=dict(PRESETS['budgeteconomy'])
        result=self.controller.feedback(sample)
        self.assertTrue(result['native_effect_verified']);self.assertFalse(result['payment_verified'])
        self.assertNotIn('private',json.dumps(result))

    def test_empty_plan_delegation_and_stop(self):
        self.plan.macro_actions=();self.dispatch()
        result=self.controller.feedback({'frame':1700,'budget_feedback':{
            'selected_macro_flag':None,'account_shares':dict(PRESETS['budgetarmy'])}})
        self.assertEqual(result['status'],'native_delegation_observed')
        self.assertEqual(self.calls[0][0],[])
        self.controller.stop()
        with self.assertRaisesRegex(ContractError,'stopped'):self.dispatch()
        self.assertEqual(self.calls[-1],'closed')

    def test_nonfinite_and_incomplete_native_shares_do_not_pass(self):
        value=dict(PRESETS['budgeteconomy']);value['investment']=float('nan')
        self.assertFalse(ratios_match(value,PRESETS['budgeteconomy']))
        value.pop('investment');self.assertFalse(ratios_match(value,PRESETS['budgeteconomy']))

    def test_frozen_field_evidence_qualifies_only_two_budget_actions(self):
        scope=verify_budget_scope(ROOT/'reports/macro-policy-budget-73924-20261028-v3',
            ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',
            ROOT/'reports/macro-policy-expiry-71320-20261028-v1',
            ROOT/'native-ai/macro-policy-runtime/bin/policy-v8-model-20261028')
        self.assertEqual(set(scope.available_actions),{'budgeteconomy','budgetarmy'})
        self.assertNotIn('budgettech',scope.available_actions)
        self.assertEqual(len(scope.evidence),9)
        self.assertFalse(scope.public()['production_and_construction_granted'])


class MacroRequestAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_latest_feedback_survives_compacted_memory_and_exact_audit(self):
        events=[];seen=[]
        class Backend:
            def input_size(self,value):return len(json.dumps(value))
            async def __call__(self,value):seen.append(value);return {}
        feedback=dict(status='native_budget_adopted',selected_policy='budgetarmy',actions=['budgetarmy'],
            observed_frame=1501,native_effect_verified=True,address='private pointer',production_id=765)
        backend=Backend();audit=MacroRequestAudit(backend,lambda kind,**facts:events.append(facts),feedback_supplier=lambda:feedback)
        context=dict(control_mode='macro_native',game_time_seconds=100.,working_memory=dict(recent_execution_feedback=[]))
        expected=audit.prepare(context)
        self.assertEqual(audit.input_size(context),backend.input_size(expected))
        await audit(context)
        self.assertEqual(seen[0],events[0]['context']);self.assertEqual(seen[0],expected)
        self.assertNotIn('macro_execution_feedback',context)
        self.assertEqual(seen[0]['macro_execution_feedback']['status'],'native_budget_adopted')
        self.assertNotIn('private pointer',json.dumps(seen));self.assertNotIn('765',json.dumps(seen))

    async def test_stale_feedback_cannot_be_substituted_into_new_request(self):
        calls=[]
        async def backend(context):calls.append(context)
        feedback=dict(status='native_budget_adopted',selected_policy='budgetarmy',actions=['budgetarmy'],
            observed_frame=1400,native_effect_verified=True)
        audit=MacroRequestAudit(backend,lambda *a,**k:None,feedback_supplier=lambda:feedback)
        with self.assertRaisesRegex(ContractError,'invalid_or_stale'):
            await audit(dict(control_mode='macro_native',game_time_seconds=100.))
        self.assertEqual(calls,[])

    async def test_exact_context_and_backend_sizing_preserved(self):
        events=[];seen=[]
        class Backend:
            max_input_bytes=8192
            def input_size(self,value):return len(json.dumps(value))
            async def __call__(self,value):seen.append(value);return {'policy':'synthetic'}
        backend=Backend();audit=MacroRequestAudit(backend,lambda kind,**facts:events.append(facts))
        context={'control_mode':'macro_native','working_memory':{'recent_execution_feedback':[
            {'status':'native_budget_adopted','selected_policy':'budgetarmy'}]}}
        self.assertEqual(await audit(context),{'policy':'synthetic'})
        self.assertIs(seen[0],context);self.assertEqual(events[0]['context'],context)
        self.assertEqual(len(events[0]['context_sha256']),64)
        self.assertEqual(audit.input_size(context),backend.input_size(context))
        self.assertEqual(audit.max_input_bytes,8192)
        self.assertNotIn('real_network_verified',events[0])

    async def test_non_macro_context_cannot_be_sent(self):
        calls=[]
        async def backend(context):calls.append(context)
        audit=MacroRequestAudit(backend,lambda *a,**k:None)
        with self.assertRaisesRegex(ContractError,'audit_mode'):await audit({'control_mode':'micro'})
        self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
