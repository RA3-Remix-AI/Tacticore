import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from .contracts import ContractError
from .macro_policy_runtime import MacroRequestAudit
from .macro_production_public import compact_production_feedback
from .macro_production_feedback import ProductionFeedback
from .test_macro_production_feedback import sample


class ProductionPublicTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_producer_revocation_skips_plan_but_unknown_delivery_is_not_hidden(self):
        from macro_host import MacroHost
        from .test_macro_production_runtime import ProductionRuntimeTests
        test=ProductionRuntimeTests();test.setUp()
        host=MacroHost.__new__(MacroHost);host.controller=test.controller;host.expected_hash='b'*64
        host.latest=dict(game_time_seconds=100.,paused=False);events=[]
        host.event=lambda kind,**facts:events.append((kind,facts))
        test.refresh(1500,alive=False)
        self.assertFalse(host.dispatch_plan(test.plan));self.assertEqual(test.calls,[])
        self.assertEqual(events[-1][1]['reason_code'],'macro_production_not_currently_available')
        test.refresh(1500)
        def unknown(*args):raise RuntimeError('private transport diagnostic')
        test.native.apply=unknown
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):host.dispatch_plan(test.plan)
        self.assertTrue(test.controller.stopped)

    async def test_latest_production_feedback_survives_empty_history_without_private_fields(self):
        builder,census=sample(1500)
        tracker=ProductionFeedback('produceflak',2,builder,census)
        builder,census=sample(1510,[(18,150)])
        value=tracker.observe(builder,census);value.update(producer_id=765,pointer='private address',extra={'secret':'value'})
        seen=[];events=[]
        class Backend:
            def input_size(self,context):return len(json.dumps(context))
            async def __call__(self,context):seen.append(context);return {}
        backend=Backend()
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1510,native_effect_verified=False)
        audit=MacroRequestAudit(backend,lambda kind,**facts:events.append(facts),
            feedback_supplier=lambda:budget,production_supplier=lambda:value)
        context=dict(control_mode='macro_native',game_time_seconds=1510/15,working_memory={'recent_execution_feedback':[]})
        expected=audit.prepare(context)
        self.assertEqual(audit.input_size(context),backend.input_size(expected))
        await audit(context)
        self.assertEqual(seen[0],expected);self.assertEqual(events[0]['context'],expected)
        feedback=seen[0]['macro_production_feedback']
        self.assertEqual(feedback['observed_new_queue_count'],1)
        self.assertEqual(feedback['fully_paid_queue_observations'],0)
        self.assertFalse(feedback['completed_units_verified']);self.assertFalse(feedback['exclusive_macro_attribution_verified'])
        self.assertNotIn('private',json.dumps(seen));self.assertNotIn('producer_id',json.dumps(seen))
        self.assertNotIn('macro_production_feedback',context)

    async def test_stale_or_noninteger_observations_cannot_be_sent_as_current(self):
        builder,census=sample(1500);value=ProductionFeedback('produceflak',2,builder,census).public()
        with self.assertRaisesRegex(ContractError,'invalid_or_stale'):compact_production_feedback(value,105.)
        for key,bad in [('observed_new_queue_count',True),('builder_frame',-1),('release_reason','unverified'),('additional_count_requested',4)]:
            with self.subTest(key=key),self.assertRaises(ContractError):compact_production_feedback(dict(value,**{key:bad}),100.)

    async def test_slow_native_sample_rejects_one_agent_context_and_fresh_tick_recovers(self):
        from engine import StrategyEngine
        from battle_agent import BattleAgent
        from fixtures import binding,policy,snapshot
        builder,census=sample(1519);production=ProductionFeedback('produceflak',2,builder,census).public()
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1500,native_effect_verified=False)
        calls=[]
        class Backend:
            max_input_bytes=16384
            def input_size(self,context):return len(json.dumps(context))
            async def __call__(self,context):
                calls.append(context);return policy(context,production_focus='native_baseline',macro_actions=[],macro_production=None)
        audit=MacroRequestAudit(Backend(),lambda *a,**k:None,feedback_supplier=lambda:budget,production_supplier=lambda:production)
        agent=BattleAgent(StrategyEngine(binding(),min_hold_game_seconds=0))
        raw=snapshot();raw['macro_control']=dict(mode='macro_native',available_actions=['budgeteconomy','budgetarmy'],production_counts={})
        rejected=await agent.decide(raw,audit)
        self.assertNotEqual(rejected.status,'accepted');self.assertEqual(calls,[])
        self.assertFalse(agent.engine.stopped)
        builder,census=sample(1531);production=ProductionFeedback('produceflak',2,builder,census).public()
        budget.update(observed_frame=1530)
        raw=snapshot(2,102);raw['macro_control']=dict(mode='macro_native',available_actions=['budgeteconomy','budgetarmy'],production_counts={})
        accepted=await agent.decide(raw,audit)
        self.assertEqual(accepted.status,'accepted');self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['macro_production_feedback']['builder_frame'],1531)

    async def test_host_busy_tick_revokes_actions_then_releases_at_observed_count(self):
        from .test_macro_production_runtime import ProductionRuntimeTests
        from macro_host import MacroHost
        test=ProductionRuntimeTests();test.setUp();events=[]
        host=MacroHost.__new__(MacroHost)
        host.controller=test.controller;host.sampler=SimpleNamespace(scope=test.scope)
        host.latest={'game_time_seconds':120.};host.event=lambda kind,**facts:events.append((kind,facts))
        builder,census=sample(1800)
        host.production_tick(dict(build_observation=builder,observation={'construction_feedback':census}))
        self.assertEqual(host.latest['macro_control']['production_counts'],{'produceflak':[2]})
        test.plan.based_on_game_time_seconds=120.;test.plan.expires_at_game_seconds=160.
        test.controller.dispatch(test.plan,120.,effective_hash='b'*64)
        host.production_tick(dict(build_observation=builder,observation={'construction_feedback':census}))
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
        builder,census=sample(1810,[(18,220),(19,10)])
        host.latest['game_time_seconds']=1810/15
        host.production_tick(dict(build_observation=builder,observation={'construction_feedback':census}))
        self.assertFalse(test.controller.busy)
        self.assertEqual(test.calls[1][0],[])
        self.assertNotIn('produceflak',host.latest['macro_control']['available_actions'])
        self.assertTrue(host.last_production_feedback['policy_released'])

    async def test_host_primes_lawful_contact_memory_before_followup_hidden_sample(self):
        from macro_host import MacroHost,BattleAgent,StrategyEngine
        from tactical_fixtures import tactical_snapshot
        from fixtures import binding
        with tempfile.TemporaryDirectory() as temp:
            host=MacroHost.__new__(MacroHost);host.output=Path(temp)
            host.agent=BattleAgent(StrategyEngine(binding()))
            host.latest=tactical_snapshot();host.latest['battlefield']['formations']=[]
            host.latest['macro_control']=dict(mode='macro_native',available_actions=[])
            host.observe_current()
            host.latest=tactical_snapshot(2,104);host.latest['battlefield']['formations']=[]
            host.latest['macro_control']=dict(mode='macro_native',available_actions=[],production_counts={})
            host.latest['battlefield']['contacts'][0].update(currently_visible=False,observed_at_game_seconds=100)
            host.observe_current()
            self.assertFalse(host.agent.contact_facts['contact_ore']['currently_visible'])
            rows=[json.loads(line) for line in (host.output/'macro-snapshots.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),2)
            self.assertTrue(rows[0]['battlefield']['contacts'][0]['currently_visible'])
            self.assertFalse(rows[1]['battlefield']['contacts'][0]['currently_visible'])
            host.agent=BattleAgent(StrategyEngine(binding()))
            with self.assertRaisesRegex(ValueError,'unseen_contact_history'):host.observe_current()


if __name__=='__main__':unittest.main()
