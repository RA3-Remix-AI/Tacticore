"""Offline second-round regression from retained public trial bytes.

The pressure case explicitly synthesizes four coeval domains. No game handle,
network request or new field qualification is created by these tests.
"""
import copy
import json
from pathlib import Path
import unittest

from battle_agent import BattleAgent
from engine import Binding,Plan,StrategyEngine
from macro_strategy import MacroStrategyMemory
from macro_policy import restore_public_defaults
from test_macro_group_role_wire import offline_adapter
from tacticore_agent_runtime.factory import NetworkBackend
from http_adapter import system_prompt
from host_runtime.strategic_unified_feedback_v5 import UnifiedRequestAuditV5
from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'acceptance/runs/desktop-bcd88e90-e31e-4f87-94c1-9f2ec32da025/battle-host'
# Local trial bytes are intentionally not distributed with the source checkout.
# A present but invalid archive must still run and fail its original checks.
WIRE_ARCHIVE_FILES=tuple(SOURCE/name for name in
    ('host-events.jsonl','profile.json','macro-snapshots.jsonl'))
WIRE_ARCHIVE_AVAILABLE=all(path.is_file() for path in WIRE_ARCHIVE_FILES)

@unittest.skipUnless(WIRE_ARCHIVE_AVAILABLE,
    'requires unpublished desktop-bcd88e90 trial events, profile and snapshots')
class Wire(unittest.TestCase):
    def fixture(self,pressure=False):
        events=[json.loads(line) for line in (SOURCE/'host-events.jsonl').read_text().splitlines()]
        request=restore_public_defaults(next(r['context'] for r in events if r['kind']=='model_macro_request_context'))
        profile=json.loads((SOURCE/'profile.json').read_bytes())
        binding=Binding(request['session_id'],3,request['commander_id'],profile['name'],profile['connection_id'])
        engine=StrategyEngine(binding);agent=BattleAgent(engine,context_budget_bytes=16384)
        for line in (SOURCE/'macro-snapshots.jsonl').read_text().splitlines():agent.observe(json.loads(line))
        value=copy.deepcopy(next(r['plan'] for r in events if r['kind']=='plan_applied'))
        value['budget']=tuple(sorted(value['budget'].items()));value['macro_actions']=tuple(value['macro_actions']);value['tactical_tasks']=()
        plan=Plan(**value);engine.current=plan
        memory=MacroStrategyMemory(session_id=binding.session_id,commander_id=binding.commander_id,player_id=3,
            profile_revision=profile['revision'],effective_hash=profile['effective']['effective_hash'])
        review=memory.review(plan,plan.macro_strategy,request)
        ack=next(r for r in events if r['kind']=='macro_policy_acknowledged')
        memory.record_dispatch(review,command_id=ack['command_id'],game_seconds=ack['native_start_frame']/15)
        observed=next(r for r in events if r['kind']=='macro_strategy_outcome' and r['outcome']=='effect_observed')
        memory.record_outcome(command_id=ack['command_id'],plan_id=plan.plan_id,outcome='effect_observed',
            game_seconds=observed['observed_game_seconds'],observed_game_seconds=observed['observed_game_seconds'],
            effect_verified=True,reason_code=observed['reason_code'])
        feedback=copy.deepcopy([r for r in events if r['kind']=='macro_native_feedback'][-1])
        unified=copy.deepcopy([r for r in events if r['kind']=='macro_unified_feedback'][-1])
        if pressure:
            # Artificial maximum simultaneous strategic domains, with each
            # source component frame explicit and no completion claim.
            template=unified['observations'][-1]
            unified['observations']=[dict(template,action=action) for action in
                ('expand','budgeteconomy','advanceconstruction','pauseproduction')]
            for row in unified['observations']:
                if row['action'] in ('advanceconstruction','pauseproduction'):
                    row.update(status='native_manager_state_observed',component_state_adopted=True,
                        active_native_task_observed=False,movement_observed=False)
                elif row['action'].startswith('budget'):
                    row.update(status='native_waiting_or_no_effect',active_native_task_observed=False,movement_observed=False)
        adapter=offline_adapter(profile,traits='风格偏好'*100 if pressure else profile['effective']['traits'])
        sdk=NetworkBackend.__new__(NetworkBackend);sdk._prompt=lambda context:system_prompt(adapter.profile,context)
        class Backend:
            max_input_bytes=16384
            def input_size(self,context):return max(adapter.input_size(context),sdk.input_size(context))
        audit=UnifiedRequestAuditV5(Backend(),lambda *a,**k:None,feedback_supplier=lambda:feedback,
            unified_supplier=lambda:unified,strategy_supplier=memory.context,strategic_only=True)
        return agent,audit,adapter,sdk,unified
    def test_second_round_and_four_domain_pressure_fit_both_real_encoders(self):
        for pressure in (False,True):
            with self.subTest(pressure=pressure):
                agent,audit,adapter,sdk,unified=self.fixture(pressure)
                prepared=prepare_macro_request_v1(agent,audit,agent.latest)
                base=agent.context(agent.latest.model_context(agent.engine.binding),commit=False,
                    wire_size=prepared.measure.input_size,wire_limit=16384)
                context=prepared.measure.prepare(base)
                self.assertLessEqual(adapter.input_size(context),16384-256);self.assertLessEqual(sdk.input_size(context),16384)
                public=restore_public_defaults(context)
                self.assertEqual([(r['action'],r['observed_frame']) for r in public['macro_unified_feedback']['observations']],
                    [(r['action'],r['observed_frame']) for r in unified['observations']])
                self.assertEqual(public['macro_unified_feedback']['completion_and_exclusive_causality_verified'],False)
                self.assertEqual(set(public['macro_policy_catalog']),set(public['allowed_macro_actions']))
                self.assertIn('native.scout',public['macro_strategy']['fact_catalog']) if not pressure else None
                self.assertEqual(agent.engine.metrics['requests'],0)
    def test_prepared_feedback_does_not_follow_later_live_mutation(self):
        agent,audit,_,_,unified=self.fixture()
        prepared=prepare_macro_request_v1(agent,audit,agent.latest)
        base=agent.context(agent.latest.model_context(agent.engine.binding),commit=False)
        before=prepared.measure.prepare(base);unified['observations'][0]['observed_frame']+=1000
        self.assertEqual(prepared.measure.prepare(base),before)
        with self.assertRaises(Exception):audit.prepare(base)

if __name__=='__main__':unittest.main()
