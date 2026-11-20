"""Prompt v2 structure, version selection and the optional reasoning field.

Offline only: no model, network or game. Size against the real 16 KiB capacity
envelope is covered in integration/test_native_delegation_prompt_v2_budget.py.
"""
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from engine import ContractError, Snapshot, normalize_reasoning, validate_policy
from fixtures import COMMANDER, SESSION, binding, snapshot
from http_adapter import system_prompt
from macro_policy import public_descriptions
import native_delegation_prompt_v2 as v2
import prompt_versions

ACTIONS = ['attackenemy', 'scout', 'expand', 'budgeteconomy', 'budgetarmy', 'pauseconstruction',
           'advanceproduction']


def profile():
    return SimpleNamespace(personality=1, traits='Defend first, then counterattack.')


def delegation_context(actions=None, **changes):
    actions = list(ACTIONS if actions is None else actions)
    value = dict(
        commander_id=COMMANDER, session_id=SESSION, player_id=3, snapshot_id=1, game_time_seconds=100.0,
        control_mode='macro_native', allowed_production_focus=['native_baseline'],
        allowed_macro_actions=actions, macro_policy_catalog=public_descriptions(
            [action for action in actions if not action.startswith('focusenemy')]),
        native_delegation={'kind': 'native_ai_details_v1'},
        macro_strategy={'fact_catalog': {'own.credits': 3000, 'capabilities.actions': actions}},
    )
    value.update(changes)
    return value


def section(text, name):
    return text.split('\n' + name + ': ', 1)[1].split('\n', 1)[0]


class PromptVersionTests(unittest.TestCase):
    def test_v2_is_default_and_v1_stays_selectable(self):
        with patch.dict(os.environ, {prompt_versions.ENVIRONMENT_VARIABLE: ''}):
            self.assertEqual(prompt_versions.active_prompt_version(), 'v2')
            self.assertIn('# How to win', system_prompt(profile(), delegation_context()))
        with patch.dict(os.environ, {prompt_versions.ENVIRONMENT_VARIABLE: 'v1'}):
            self.assertEqual(prompt_versions.active_prompt_version(), 'v1')
            self.assertNotIn('# How to win', system_prompt(profile(), delegation_context()))

    def test_unknown_version_fails_closed(self):
        with patch.dict(os.environ, {prompt_versions.ENVIRONMENT_VARIABLE: 'v9'}):
            with self.assertRaises(prompt_versions.PromptVersionError):
                prompt_versions.active_prompt_version()
        with self.assertRaises(prompt_versions.PromptVersionError):
            prompt_versions.select_prompt_version('latest')


class PromptV2Tests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {prompt_versions.ENVIRONMENT_VARIABLE: 'v2'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_structured_sections_and_every_offered_action(self):
        text = system_prompt(profile(), delegation_context())
        for heading in ('# Role', '# Your intents', '# Situation', '# How to win', '# Output'):
            self.assertIn(heading, text)
        for action in ACTIONS:
            self.assertIn(action, text.split('\nRegionMap: ')[0])
        self.assertIn('natural match victory', text)
        self.assertIn('native AI owns ALL building', text)
        self.assertIn('[] restores native baseline execution', text)
        self.assertIn('including inference and dispatch time', text)

    def test_only_offered_actions_are_named(self):
        text = system_prompt(profile(), delegation_context(['budgeteconomy', 'scout']))
        instructions = text.split('\nRegionMap: ')[0]
        for absent in ('attackenemy', 'raideconomy', 'deploydefense', 'focusenemy', 'advanceproduction'):
            self.assertNotIn(absent, instructions)
        self.assertIn('macro_actions length<=2', instructions)

    def test_enemy_focus_is_built_from_offered_actions_not_fixed_players(self):
        actions = ['attackenemy', 'focusenemy6', 'focusenemy7', 'budgetarmy']
        context = delegation_context(actions)
        context['macro_policy_catalog'].update({
            'focusenemy6': dict(domain='enemy_focus', target_player_id=6),
            'focusenemy7': dict(domain='enemy_focus', target_player_id=7)})
        text = system_prompt(profile(), context)
        self.assertIn('focusenemy6=player 6|focusenemy7=player 7', text)
        self.assertNotIn('focusenemy4', text)
        self.assertNotIn('focusenemy5', text)

    def test_groups_follow_the_independent_development_contract(self):
        from native_unified_contract_v5 import INDEPENDENT_DEVELOPMENT_CONTRACT
        plain = v2.action_groups(ACTIONS, independent=False)
        self.assertIn('expand', plain['work'])
        independent = v2.action_groups(ACTIONS, independent=True)
        self.assertEqual(independent['development'], ['expand'])
        text = system_prompt(profile(), delegation_context(macro_intent_contract=INDEPENDENT_DEVELOPMENT_CONTRACT))
        self.assertIn('macro_actions length<=' + str(len(independent)), text)

    def test_example_parses_validates_and_keeps_reasoning_out_of_plan_identity(self):
        text = system_prompt(profile(), delegation_context())
        example = json.loads(section(text, 'Example'))
        self.assertLessEqual(len(example['reasoning']), v2.REASONING_MAX_CHARS)
        raw = snapshot(macro_control=dict(mode='macro_native', available_actions=['budgeteconomy']))
        request = Snapshot.from_dict(raw)
        plan = validate_policy(example, request, request, binding(), 20)
        self.assertEqual(plan.reasoning, example['reasoning'])
        self.assertNotIn('reasoning', plan.public())
        self.assertEqual(plan.macro_strategy['objective'], 'hold')
        json.loads(section(text, 'Enums'))
        json.loads(section(text, 'RegionMap'))

    def test_prompt_is_stable_under_context_key_order(self):
        context = delegation_context()
        ordered = json.loads(json.dumps(context, sort_keys=True))
        self.assertEqual(system_prompt(profile(), context), system_prompt(profile(), ordered))


class ReasoningFieldTests(unittest.TestCase):
    def test_optional_reasoning_is_trimmed_and_bounded(self):
        self.assertIsNone(normalize_reasoning(None))
        self.assertIsNone(normalize_reasoning('   '))
        self.assertEqual(normalize_reasoning(' enemy  far\naway '), 'enemy far away')
        long = normalize_reasoning('x' * 1000)
        self.assertEqual(len(long), 300)
        with self.assertRaises(ContractError):
            normalize_reasoning(['not', 'text'])
        with self.assertRaises(ContractError):
            normalize_reasoning('x' * 5000)

    def test_policy_without_reasoning_is_still_accepted(self):
        text = system_prompt(profile(), delegation_context())
        example = json.loads(section(text, 'Example'))
        example.pop('reasoning')
        request = Snapshot.from_dict(snapshot(macro_control=dict(mode='macro_native',
                                                                 available_actions=['budgeteconomy'])))
        self.assertIsNone(validate_policy(example, request, request, binding(), 20).reasoning)


if __name__ == '__main__':
    unittest.main()
