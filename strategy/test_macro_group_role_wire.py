"""Replay the schema9 overflow with real wire encoding and public inputs only."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import http_adapter
from http_adapter import ChatAdapter
from macro_policy import public_descriptions,model_catalog
from integration.host_runtime.macro_group_role_contract import group_role_catalog_overrides

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT/'reports/macro-group-role-wire-repair-20261028-v1/http_adapter.before.py'


def historical_context():
    path = ROOT/'acceptance/runs/20261028-133800-macro-probe/battle-host/host-events.jsonl'
    if not path.is_file():
        raise unittest.SkipTest('requires local archived wire contexts; not distributed with source')
    rows = [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]
    context = copy.deepcopy([r['context'] for r in rows if r['kind']=='model_macro_request_context'][-1])
    scope = json.loads((ROOT/'reports/macro-group-role-desktop-bootstrap-20261028-v1/qualification.json').read_text(encoding='utf8'))['scope']
    context['allowed_macro_actions'] = scope['available_actions']
    context['macro_policy_catalog'] = public_descriptions(scope['available_actions'], scope['production_counts'].items(), scope['regional_action_regions'].items())
    context['macro_policy_catalog'].update(group_role_catalog_overrides())
    profile = json.loads((ROOT/'reports/macro-group-role-directed-profile-20261028.json').read_text(encoding='utf8'))
    return context, profile


def offline_adapter(profile, provider='DeepSeek', traits=None):
    # The pure encoder needs no adapter initialization, endpoint or credentials.
    adapter = ChatAdapter.__new__(ChatAdapter)
    adapter.profile = SimpleNamespace(personality=profile['personality'],
        traits=profile['effective']['traits'] if traits is None else traits,
        provider=provider, model='deepseek-flash' if provider=='DeepSeek' else 'gpt-example')
    adapter.max_tokens = 2048
    return adapter


def accumulated_feedback_context():
    """Explicit stress fixture combining public requests from separate runs."""
    context,profile=historical_context()
    for name in ('20261028-060454-macro-probe','20261028-075720-macro-probe',
                 '20261028-133800-macro-probe','20261028-160009-macro-probe'):
        rows=(ROOT/'acceptance/runs'/name/'battle-host/host-events.jsonl').read_text(encoding='utf8').splitlines()
        for line in rows:
            row=json.loads(line)
            if row['kind']!='model_macro_request_context':continue
            context.update({k:v for k,v in row['context'].items()
                if k.startswith('macro_') and k.endswith('_feedback') and isinstance(v,dict)})
    return context,profile


@unittest.skipUnless((ROOT/'acceptance/runs/20261028-133800-macro-probe/battle-host/host-events.jsonl').is_file() and BEFORE.is_file(),
                     'requires local archived wire contexts and pre-fix source')
class MacroGroupRoleWireTests(unittest.TestCase):
    def test_accumulated_domain_feedback_with_full_scope_and_maximum_style_fits(self):
        context,profile=accumulated_feedback_context()
        original=copy.deepcopy(context)
        self.assertTrue({'macro_execution_feedback','macro_production_feedback',
            'macro_construction_feedback','macro_scouting_feedback','macro_regional_feedback'}<=set(context))
        adapter=offline_adapter(profile,traits='风格偏好'*100)
        self.assertGreater(adapter.input_size(context),16384)
        context['macro_policy_catalog']=model_catalog(context['macro_policy_catalog'])
        self.assertLessEqual(adapter.input_size(context),16384)
        from tacticore_agent_runtime.factory import NetworkBackend
        runtime=NetworkBackend.__new__(NetworkBackend)
        runtime._prompt=lambda value:http_adapter.system_prompt(adapter.profile,value)
        self.assertLessEqual(runtime.input_size(context),16384)
        self.assertEqual({k:v for k,v in context.items() if k!='macro_policy_catalog'},
            {k:v for k,v in original.items() if k!='macro_policy_catalog'})
        for action,description in context['macro_policy_catalog'].items():
            for key in ('domain','target_region','goal','target_policy',
                        'native_account_shares','maximum_duration_seconds','requires_existing_forward_force'):
                if key in original['macro_policy_catalog'][action]:
                    self.assertEqual(description[key],original['macro_policy_catalog'][action][key])
            if 'quantity' in description:
                for key in ('field','allowed_additional_counts','additional_count_min','additional_count_max','control_basis'):
                    if key in original['macro_policy_catalog'][action]['quantity']:
                        self.assertEqual(description['quantity'][key],original['macro_policy_catalog'][action]['quantity'][key])

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
        _,profile=historical_context()
        prompt=http_adapter.system_prompt(offline_adapter(profile).profile,context)
        self.assertIn('flat array of exact allowed strings',prompt)
        answer=policy(context,macro_actions=[dict(action='budgetarmy')])
        with self.assertRaisesRegex(ContractError,'macro_policy_actions'):
            validate_policy(answer,observed,observed,binding(),20)
        answer['macro_actions']=['budgetarmy']
        self.assertEqual(validate_policy(answer,observed,observed,binding(),20).macro_actions,('budgetarmy',))

    def test_frozen_previous_prompt_reproduces_overflow(self):
        context, profile = historical_context()
        raw = BEFORE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '6a929841a709ed344d5e86f16f29c51924ea055edccf2eaaeabf28f901af4564')
        function = next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='macro_system_prompt')
        namespace = {name:getattr(http_adapter,name) for name in ('Profile','STANCES','ECONOMY','TECH','REASONS')}
        namespace['json'] = json
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(BEFORE),'exec'),namespace)
        adapter = offline_adapter(profile)
        body = json.loads(adapter.encoded_request(context))
        body['messages'][0]['content'] = namespace['macro_system_prompt'](adapter.profile,context)
        encoded = json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')
        self.assertGreater(len(encoded),16384)

    def test_full_catalog_feedback_and_maximum_style_fit_actual_wire_unchanged(self):
        context, profile = historical_context()
        original = copy.deepcopy(context)
        for provider in ('DeepSeek','OpenAI'):
            for traits in (None,'风格偏好'*100):
                with self.subTest(provider=provider,maximum_style=traits is not None):
                    adapter = offline_adapter(profile,provider,traits)
                    encoded = adapter.encoded_request(context)
                    self.assertLessEqual(len(encoded),16384)
                    self.assertEqual(adapter.input_size(context),len(encoded))
                    body = json.loads(encoded)
                    self.assertEqual(json.loads(body['messages'][1]['content']),original)
                    self.assertEqual(context,original)
                    self.assertTrue({'regroup','reinforce','withdraw'} <= set(context['macro_policy_catalog']))
                    self.assertEqual(context['macro_policy_catalog']['produceflak']['quantity']['allowed_additional_counts'],[2,3])
                    if traits is not None:
                        self.assertIn(traits,body['messages'][0]['content'])


if __name__=='__main__':unittest.main()
