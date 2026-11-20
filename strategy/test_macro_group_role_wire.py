"""Wire encoding helpers and synthetic catalog/prompt checks."""
import copy
from types import SimpleNamespace
import unittest

import http_adapter
from http_adapter import ChatAdapter
from macro_policy import model_catalog

def offline_adapter(profile, provider='DeepSeek', traits=None):
    # The pure encoder needs no adapter initialization, endpoint or credentials.
    adapter = ChatAdapter.__new__(ChatAdapter)
    adapter.profile = SimpleNamespace(personality=profile['personality'],
        traits=profile['effective']['traits'] if traits is None else traits,
        provider=provider, model='deepseek-flash' if provider=='DeepSeek' else 'gpt-example')
    adapter.max_tokens = 2048
    return adapter


SYNTHETIC_PROFILE = dict(personality=1, effective=dict(traits=''))


class MacroGroupRoleWireTests(unittest.TestCase):
    def test_catalog_projection_preserves_unknown_or_changed_contract_values(self):
        catalog={'withdraw':dict(target_region='region_8_3',goal='home',
            arbitrary_unit_selection_supported=True,native_unit_operations_unchanged=False,
            future_constraint={'limit':3},arrival_and_mission_success_guaranteed=False)}
        before=copy.deepcopy(catalog);projected=model_catalog(catalog)
        self.assertEqual(catalog,before)
        self.assertTrue(projected['withdraw']['arbitrary_unit_selection_supported'])
        self.assertFalse(projected['withdraw']['native_unit_operations_unchanged'])
        self.assertEqual(projected['withdraw']['future_constraint'],{'limit':3})
        self.assertNotIn('arrival_and_mission_success_guaranteed',projected['withdraw'])

    def test_prompt_explicitly_requires_string_actions_and_rejects_object_items(self):
        from fixtures import policy,binding
        from test_macro_policy import macro_snapshot
        from engine import validate_policy,ContractError
        observed=macro_snapshot(['budgetarmy'])
        context=observed.model_context(binding())
        prompt=http_adapter.system_prompt(offline_adapter(SYNTHETIC_PROFILE).profile,context)
        self.assertIn('flat array of exact allowed strings',prompt)
        answer=policy(context,macro_actions=[dict(action='budgetarmy')])
        with self.assertRaisesRegex(ContractError,'macro_policy_actions'):
            validate_policy(answer,observed,observed,binding(),20)
        answer['macro_actions']=['budgetarmy']
        self.assertEqual(validate_policy(answer,observed,observed,binding(),20).macro_actions,('budgetarmy',))

if __name__=='__main__':unittest.main()
