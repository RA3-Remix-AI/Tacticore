"""Prompt v2 stays inside the existing model input budgets (offline sizing only).

Uses the production capacity envelope and the exact SDK size estimator; no
provider, credential, game or network access.
"""
import os
import unittest
from unittest.mock import patch

# The capacity module puts strategy/ and agent_runtime/ on the import path.
from host_runtime import model_capacity as capacity
from host_runtime.macro_group_role_contract import group_role_catalog_overrides
from host_runtime.native_runtime import NativeScope
from host_runtime.native_runtime_contract import PACKAGE_SHA, FLAGS
from host_runtime.profiles import normalize_profile
from host_runtime.strategic_contract import FLAG_ACTIONS
from engine import Snapshot
from macro_policy import ACTIONS, public_descriptions
import prompt_versions

STYLE = '更早寻找施压窗口，同时保留基础防守。'


def effective(identity, traits=STYLE):
    return normalize_profile(dict(schema_version=1, profile_id=identity.commander_id, name='Offline',
        revision=1, connection_id=identity.connection_id, model='fixture-model', doctrine='assault',
        custom_traits=traits))


def grammar_cases():
    """The two qualified 16 KiB grammars and the 32 KiB Native7 independent grammar."""
    from fixtures import snapshot
    for name, actions in (('legacy', capacity.LEGACY_ACTIONS), ('native_target', capacity.NATIVE_TARGET_ACTIONS)):
        targets = {action: 'region_1_3' if action == 'deployattack' else 'region_8_3'
                   for action in actions if ACTIONS[action] == 'deployment'}
        raw = snapshot(capabilities=dict(production_focus=['native_baseline'], regions=['region_1_3', 'region_8_3']),
            macro_control=dict(mode='macro_native', available_actions=['budgetarmy'], production_counts={},
                               region_targets={}))
        catalog = public_descriptions(sorted(actions), region_targets=targets)
        catalog.update(group_role_catalog_overrides())
        yield name, raw, catalog
    scope = NativeScope(PACKAGE_SHA, tuple(zip(FLAG_ACTIONS, FLAGS)), (), (), required_origin_region='region_7_1',
                        opponent_player_ids=(4, 5))
    raw = snapshot()
    raw['capabilities']['regions'] = ['region_7_1']
    raw['macro_control'] = dict(mode='macro_native', available_actions=['budgetarmy'], region_targets={},
                                intent_contract=scope.intent_contract)
    targets = {action: 'region_7_1' for action in scope.available_actions if ACTIONS[action] == 'deployment'}
    catalog = public_descriptions(scope.available_actions, region_targets=targets)
    catalog.update(scope.model_catalog_overrides())
    yield 'native7_independent', raw, catalog


def measure(version, raw, catalog, traits=STYLE):
    from fixtures import binding
    with patch.dict(os.environ, {prompt_versions.ENVIRONMENT_VARIABLE: version}):
        return capacity.check_model_capacity(effective(binding(), traits), 'DeepSeek', raw, catalog)


class PromptV2BudgetTests(unittest.TestCase):
    def test_v2_fits_every_qualified_grammar_and_never_exceeds_v1_on_16_kib(self):
        for name, raw, catalog in grammar_cases():
            with self.subTest(grammar=name):
                old = measure('v1', raw, catalog)
                new = measure('v2', raw, catalog)
                self.assertTrue(new['fits'], new)
                self.assertLessEqual(new['sdk_estimate_bytes'], new['maximum_bytes'])
                if new['maximum_bytes'] == capacity.LIMIT:
                    self.assertLessEqual(new['sdk_estimate_bytes'], old['sdk_estimate_bytes'])

    def test_v2_prompt_names_every_offered_action_of_the_real_envelope(self):
        from types import SimpleNamespace
        from fixtures import binding
        from http_adapter import system_prompt
        for name, raw, catalog in grammar_cases():
            with self.subTest(grammar=name):
                profile = effective(binding())
                value = capacity._capacity_envelope(profile, Snapshot.from_dict(raw), dict(catalog))
                public = SimpleNamespace(personality=profile.personality, traits=profile.traits)
                with patch.dict(os.environ, {prompt_versions.ENVIRONMENT_VARIABLE: 'v2'}):
                    text = system_prompt(public, value)
                instructions = text.split('\nRegionMap: ')[0]
                for action in value['allowed_macro_actions']:
                    self.assertIn(action, instructions)


if __name__ == '__main__':
    unittest.main()
