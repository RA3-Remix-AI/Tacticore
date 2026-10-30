"""Synthetic maximum-pressure encoding, assembled from frozen public requests.

This deliberately combines separate runs and republishes known frame fields;
it is a software stress fixture, never a claim of one real game or new grants.
"""
import copy
import json
import unittest
import uuid

from http_adapter import system_prompt
from macro_policy import (model_catalog,project_strategy_defaults,restore_public_defaults,
                          public_descriptions)
from macro_strategy import MacroStrategyMemory
from test_macro_group_role_wire import accumulated_feedback_context,offline_adapter
from test_macro_strategy import declaration


def pressure_context():
    context,profile=accumulated_feedback_context()
    context['macro_policy_catalog']=model_catalog(context['macro_policy_catalog'])
    at=context['game_time_seconds'];frame=int(at*15)
    # Explicitly synthetic coeval copies, not edited historical source files.
    for section in ('own_forces','own_infrastructure','macro_production_feedback'):
        if section in context:
            for key in ('observed_frame','builder_frame','own_census_frame'):
                if key in context[section]:context[section][key]=frame
    memory=MacroStrategyMemory(session_id=context['session_id'],commander_id=context['commander_id'],
        player_id=context['player_id'],profile_revision=21,effective_hash='a'*64)
    refs=sorted(memory.context(context)['fact_catalog'],key=len,reverse=True)[:4]
    declared=declaration(public_fact_refs=refs,objective='develop_technology',phase='execute',
        expected_observation='building_operational',
        continue_conditions=['capability_available','resources_sufficient','prerequisite_met'],
        replan_conditions=['capability_available','resources_sufficient','prerequisite_met'])
    plan=dict(plan_id=str(uuid.uuid4()),session_id=context['session_id'],commander_id=context['commander_id'],
        player_id=context['player_id'],origin='model',based_on_game_time_seconds=at,
        expires_at_game_seconds=at+30,macro_actions=['budgetarmy'],macro_production=None,
        objective_region=None,tactical_tasks=[],runtime_task=None)
    reviewed=memory.review(plan,declared,context)
    memory.record_dispatch(reviewed,command_id='software-pressure-only',game_seconds=at)
    memory.record_outcome(command_id='software-pressure-only',plan_id=plan['plan_id'],
        outcome='effect_observed',game_seconds=at,observed_game_seconds=at,effect_verified=True,reason_code='r'*64)
    candidates=['buildpower','buildbarracks','buildfactory','buildrefinery','buildbattlelab','producesickle','producebullfrog']
    context['allowed_macro_actions']+=candidates
    context['macro_policy_catalog'].update(model_catalog(public_descriptions(candidates,
        counts=[('producesickle',(1,)),('producebullfrog',(1,))])))
    context['macro_strategy']=memory.context(context)
    return context,profile,memory


class StrategyWirePressureTests(unittest.TestCase):
    def test_one_new_profitable_alias_restores_each_changed_value_exactly(self):
        context,_,_=pressure_context();catalog=context['macro_policy_catalog']
        field='requires_fresh_native_readiness_and_dependency'
        for action in ('buildpower','buildbarracks','buildfactory','buildrefinery','buildbattlelab','producesickle','producebullfrog'):
            catalog[action][field]=action!='buildpower'
        original=copy.deepcopy(context);packed=project_strategy_defaults(context)
        self.assertEqual(restore_public_defaults(packed),original)
        self.assertIs(restore_public_defaults(packed)['macro_policy_catalog']['buildpower'][field],False)
    def test_native_location_alias_retains_mixed_values_and_previous_alias_ids(self):
        from macro_policy import _STRATEGY_ALIASES
        context,_,_=pressure_context();catalog=context['macro_policy_catalog']
        field='native_ai_selects_location_and_operates_units'
        for i,action in enumerate(('buildpower','buildbarracks','buildfactory','buildrefinery','buildbattlelab','producesickle','producebullfrog')):
            catalog[action][field]=i%2==0
        original=copy.deepcopy(context);packed=project_strategy_defaults(context)
        self.assertEqual(restore_public_defaults(packed),original)
        self.assertEqual(_STRATEGY_ALIASES['U'],'requires_fresh_native_readiness_and_dependency')
        self.assertEqual(_STRATEGY_ALIASES['V'],field)
    def test_twenty_candidates_full_feedback_maximum_style_and_state_fit_both_encoders(self):
        from tacticore_agent_runtime.factory import NetworkBackend
        context,profile,memory=pressure_context();original=copy.deepcopy(context)
        self.assertEqual(len(context['allowed_macro_actions']),20)
        size=len(json.dumps(context['macro_strategy'],ensure_ascii=False,separators=(',',':')).encode('utf8'))
        self.assertGreaterEqual(size,1500)
        self.assertLessEqual(size,1536)
        packed=project_strategy_defaults(context)
        self.assertEqual(restore_public_defaults(packed),original)
        self.assertEqual(context,original)
        self.assertEqual(memory.context(packed),context['macro_strategy'])
        for provider in ('DeepSeek','OpenAI'):
            adapter=offline_adapter(profile,provider=provider,traits='风格偏好'*100)
            runtime=NetworkBackend.__new__(NetworkBackend)
            runtime._prompt=lambda value:system_prompt(adapter.profile,value)
            with self.subTest(provider=provider):
                self.assertLessEqual(adapter.input_size(packed),16384-256)
                # The SDK estimate includes a conservative 1024-byte reserve.
                # Its hard ceiling stays unchanged; require the 256-byte actual
                # body margin in the real SDK MockTransport pressure test.
                self.assertLessEqual(runtime.input_size(packed),16384)
            body=json.loads(adapter.encoded_request(packed))
            self.assertEqual(restore_public_defaults(json.loads(body['messages'][1]['content'])),original)
            self.assertNotIn('full_schema',body['messages'][0]['content'])


if __name__=='__main__':unittest.main()
