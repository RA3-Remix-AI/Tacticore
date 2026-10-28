import copy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from .contracts import ContractError
from .macro_policy_runtime import verify_budget_scope
from .macro_production_runtime import verify_production_preference_scope
from .macro_production_choices import extend_production_scope
from .macro_production_public import compact_production_feedback
from . import test_macro_production_runtime as runtime_fixture
from .test_macro_production_feedback import sample
from . import macro_production_choices as qualification

ROOT=Path(__file__).resolve().parents[2]
CONSCRIPT=ROOT/'reports/macro-production-conscript1-60136-20261028-v1'
FLAK=ROOT/'reports/macro-production-flak3-60136-20261028-v1'
TANK=ROOT/'reports/macro-production-tank1-60136-20261028-v2'


def base_scope():
    budget=verify_budget_scope(ROOT/'reports/macro-policy-budget-73924-20261028-v3',
        ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',ROOT/'reports/macro-policy-expiry-71320-20261028-v1',
        ROOT/'native-ai/macro-policy-runtime/bin/policy-v19-production-count3-20261028')
    return verify_production_preference_scope(budget,ROOT/'reports/macro-production-count-69152-20261028-v1',
        ROOT/'reports/macro-builder-static-20261028-v2')


class ProductionChoiceTests(unittest.TestCase):
    def test_native_fields_extend_only_the_observed_action_count_pairs(self):
        original=base_scope();scope=extend_production_scope(original,[CONSCRIPT,FLAK])
        self.assertEqual(scope.production_counts,{'produceflak':(2,3),'produceconscript':(1,)})
        self.assertEqual(original.production_counts,{'produceflak':(2,)})
        self.assertNotIn('producetank',scope.available_actions)
        self.assertFalse(scope.public()['completed_units_guaranteed'])

    def test_tank_field_grants_only_one_queue_and_keeps_incomplete_payment_observation(self):
        scope=extend_production_scope(base_scope(),[CONSCRIPT,FLAK,TANK])
        self.assertEqual(scope.production_counts,{'produceflak':(2,3),'produceconscript':(1,),'producetank':(1,)})
        self.assertIn('producetank',scope.available_actions)
        self.assertFalse(scope.public()['completed_units_guaranteed'])
        review=qualification.load(TANK/'count-review.json')
        self.assertEqual(review['public_feedback']['fully_paid_queue_observations'],0)
        self.assertFalse(review['public_feedback']['exact_queue_to_unit_link_verified'])

    def test_tank_requires_current_vehicle_factory_and_uses_only_native_preference(self):
        test=runtime_fixture.ProductionRuntimeTests();test.setUp();controller=test.controller
        controller.scope=replace(test.scope,extra_choices=(('producetank',(1,),'private-tank'),))
        test.refresh(1500)
        self.assertNotIn('producetank',controller.available_actions(100.))
        builder,census=sample(1500)
        builder['builders'][0]['factory']['type_hash']='0xd50c222e';census['own_objects'][0]['type_hash']='0xd50c222e'
        controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)))
        self.assertNotIn('producetank',controller.available_actions(100.))
        census['own_objects'].append(dict(thing_id=800,type_hash='0x524bbd01'))
        controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)))
        self.assertIn('producetank',controller.available_actions(100.))
        test.plan.macro_actions=('producetank',);test.plan.macro_production=SimpleNamespace(action='producetank',additional_count=1)
        test.dispatch();self.assertEqual(test.calls[0][0],['producetank'])
        builder['frame']=1510;census['frame']=1510
        builder['builders'][0]['queue_candidate']['nodes']=[dict(kind_raw=1,template_hash='0x94b3590b',
            production_id_raw=20,native_cost_plus_30=1000,paid_accumulator_plus_68=50)]
        controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)));controller.tick(1510/15)
        self.assertEqual(test.calls[1][0],[])
        self.assertEqual(controller.production_feedback()['fully_paid_queue_observations'],0)
        self.assertEqual(controller.production_feedback()['observed_new_queue_count'],1)

    def test_duplicate_evidence_and_missing_positive_consumer_do_not_grant_a_choice(self):
        scope=base_scope()
        with self.assertRaisesRegex(ContractError,'choice_driver'):extend_production_scope(scope,[CONSCRIPT,CONSCRIPT])
        original=qualification.trial(CONSCRIPT/'transport');changed=copy.deepcopy(original)
        for row in changed[3]:
            if row['kind']=='native_builder_observation' and 'observation' in row:
                for entry in row['observation']['macro_entries']:entry['state_score']=0
        with patch.object(qualification,'trial',return_value=changed),self.assertRaisesRegex(ContractError,'choice_effect'):
            extend_production_scope(scope,[CONSCRIPT])

    def test_conscript_choice_remains_available_while_old_native_flak_queue_exists(self):
        test=runtime_fixture.ProductionRuntimeTests();test.setUp();controller=test.controller
        controller.scope=replace(test.scope,extra_choices=(('produceconscript',(1,),'private-conscript'),))
        builder,census=sample(1500,[(18,100)])
        controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)))
        self.assertNotIn('produceflak',controller.available_actions(100.))
        self.assertIn('produceconscript',controller.available_actions(100.))
        test.plan.macro_actions=('produceconscript','budgetarmy')
        test.plan.macro_production=SimpleNamespace(action='produceconscript',additional_count=1)
        test.dispatch();self.assertEqual(test.calls[0][0],['produceconscript','budgetarmy'])
        self.assertEqual(controller.available_actions(100.),())
        builder,census=sample(1510,[(18,100)])
        builder['builders'][0]['queue_candidate']['nodes'].append(dict(kind_raw=1,template_hash='0x19ab11af',
            production_id_raw=19,native_cost_plus_30=100,paid_accumulator_plus_68=1))
        controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)));controller.tick(1510/15)
        self.assertEqual(test.calls[1][0],[])
        feedback=controller.production_feedback()
        self.assertEqual(feedback['action'],'produceconscript');self.assertEqual(feedback['observed_new_queue_count'],1)
        self.assertEqual(compact_production_feedback(feedback,1510/15)['additional_count_requested'],1)

    def test_action_specific_quantity_cannot_use_another_units_count_grant(self):
        test=runtime_fixture.ProductionRuntimeTests();test.setUp();test.controller.scope=replace(test.scope,
            available_counts=(2,3),extra_choices=(('produceconscript',(1,),'private-conscript'),))
        test.refresh(1500);test.plan.macro_actions=('produceconscript',)
        test.plan.macro_production=SimpleNamespace(action='produceconscript',additional_count=3)
        with self.assertRaisesRegex(ContractError,'not_qualified'):test.dispatch()
        test.plan.macro_actions=('producetank',);test.plan.macro_production=SimpleNamespace(action='producetank',additional_count=1)
        with self.assertRaisesRegex(ContractError,'not_qualified'):test.dispatch()
        self.assertEqual(test.calls,[])


if __name__=='__main__':unittest.main()
