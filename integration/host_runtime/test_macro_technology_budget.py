"""Replay native account adoption and keep unsupported technology claims gated."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .contracts import ContractError
from .macro_policy_runtime import PRESETS,BudgetController,MacroRequestAudit
from .macro_technology_budget_scope import extend_technology_budget_scope
from . import macro_technology_budget_scope as qualification
from . import test_macro_policy_runtime as fixtures
from .test_macro_production_choices import base_scope
from .macro_bundle import create_bundle,load_bundle

ROOT=Path(__file__).resolve().parents[2]
FIELD=ROOT/'reports/macro-budget-tech-77436-20261028-v3'


class TechnologyBudgetTests(unittest.TestCase):
    def test_native_field_extends_only_budget_and_baseline_keeps_tech_ungranted(self):
        original=base_scope().budget
        scope=extend_technology_budget_scope(original,FIELD)
        self.assertEqual(scope.available_actions,('budgeteconomy','budgetarmy','budgettech'))
        self.assertNotIn('budgettech',original.available_actions)
        self.assertNotIn('buildtech',scope.available_actions)
        self.assertFalse(scope.public()['production_and_construction_granted'])

    def test_ratios_without_selected_native_consumer_cannot_qualify(self):
        field=copy.deepcopy(qualification.trial(FIELD/'transport'))
        for row in field[3]:
            if row['kind']=='macro_observation' and row.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag'):
                row['observation']['budget_feedback']['selected_macro_flag']=None
        with patch.object(qualification,'trial',return_value=field),self.assertRaisesRegex(ContractError,'native_adoption_missing'):
            extend_technology_budget_scope(base_scope().budget,FIELD)

    def test_selected_flag_without_correct_ratios_cannot_qualify(self):
        field=copy.deepcopy(qualification.trial(FIELD/'transport'))
        for row in field[3]:
            if row['kind']=='macro_observation' and row.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag'):
                row['observation']['budget_feedback']['account_shares']=PRESETS['budgetarmy']
        with patch.object(qualification,'trial',return_value=field),self.assertRaisesRegex(ContractError,'native_adoption_missing'):
            extend_technology_budget_scope(base_scope().budget,FIELD)

    def test_native_release_not_observed_prevents_grant(self):
        field=copy.deepcopy(qualification.trial(FIELD/'transport'))
        for row in field[3]:
            if row.get('label')=='after_technology_budget_release':
                row['observation']['budget_feedback']['selected_macro_flag']='still_selected'
        with patch.object(qualification,'trial',return_value=field),self.assertRaisesRegex(ContractError,'delegation_missing'):
            extend_technology_budget_scope(base_scope().budget,FIELD)

    def test_unqualified_technology_dispatch_refused_then_qualified_feedback_is_only_accounts(self):
        fixture=fixtures.MacroBudgetTests();fixture.setUp();fixture.plan.macro_actions=('budgettech',)
        with self.assertRaisesRegex(ContractError,'action_not_qualified'):fixture.dispatch()
        scope=extend_technology_budget_scope(base_scope().budget,FIELD)
        # Synthetic transport has a separate fixture identity; retain that identity
        # while using the actually qualified action menu and observed preset.
        scope=replace(scope,package_sha256='a'*64)
        controller=BudgetController(fixture.transport,scope,fixture.session,'b'*64,lambda *a,**k:None)
        controller.dispatch(fixture.plan,110.,effective_hash='b'*64)
        feedback=controller.feedback(dict(frame=1650,budget_feedback=dict(
            selected_macro_flag=scope.action_flags['budgettech'],account_shares=PRESETS['budgettech'])))
        self.assertTrue(feedback['native_effect_verified']);self.assertFalse(feedback['payment_verified'])
        audit=MacroRequestAudit(None,lambda *a,**k:None,feedback_supplier=lambda:feedback)
        public=audit.prepare(dict(game_time_seconds=110.))['macro_execution_feedback']
        self.assertEqual(public['selected_policy'],'budgettech')
        self.assertNotIn('0x',json.dumps(public));self.assertNotIn('technology_upgrade_verified',public)

    def test_version5_bundle_requires_and_pins_independent_technology_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bundle.json'
            args=dict(build=ROOT/'native-ai/macro-policy-runtime/bin/policy-v24-technology-budget-20261028',
                visibility=ROOT/'reports/macro-visibility-2bb7bb23-derived-20261028-v1',
                normal=ROOT/'reports/macro-policy-budget-73924-20261028-v3',
                host_loss=ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',
                expiry=ROOT/'reports/macro-policy-expiry-71320-20261028-v1',technology_budget=FIELD)
            with self.assertRaisesRegex(ContractError,'technology_bundle_incomplete'):create_bundle(path,**args)
            create_bundle(path,**args,production=ROOT/'reports/macro-production-count-69152-20261028-v1',
                production_static=ROOT/'reports/macro-builder-static-20261028-v2',
                construction=ROOT/'reports/macro-early-build-69152-20261028-v1')
            value,scope=load_bundle(path);self.assertEqual(value['schema_version'],5)
            self.assertIn('budgettech',scope.available_actions);self.assertIn('buildreactor',scope.available_actions)
            value['pins'][str((FIELD/'technology-driver.py').resolve())]='0'*64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)


if __name__=='__main__':unittest.main()
