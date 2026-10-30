import json
import unittest
from macro_policy_diagnostics import action_shape,production_shape

SECRET='PRIVATE_UNKNOWN_VALUE_OR_KEY_123'
def context():return {'allowed_macro_actions':['budgeteconomy','produceconscript'],
    'macro_policy_catalog':{'produceconscript':{'quantity':{'allowed_additional_counts':[1,2,3]}}}}


class ShapeTests(unittest.TestCase):
    def test_flat_known_actions_report_exact_static_contract(self):
        value=action_shape({'macro_actions':['budgeteconomy','produceconscript']},context())
        self.assertIsNone(value['validation_code']);self.assertEqual(value['known_string_count'],2)
        self.assertEqual(value['request_allowed_string_count'],2);self.assertEqual(value['unique_count'],2)
    def test_object_array_failure_reports_only_known_selectors(self):
        value=action_shape({'macro_actions':[{'action':'budgeteconomy',SECRET:SECRET}]},context())
        self.assertEqual(value['validation_code'],'macro_policy_actions')
        self.assertEqual(value['item_type_counts'],{'object':1})
        self.assertEqual(value['items'][0]['known_selector_fields'][0]['known_action'],'budgeteconomy')
        self.assertNotIn(SECRET,json.dumps(value));self.assertEqual(len(value['items'][0]['sha256']),64)
    def test_unknown_strings_and_keys_never_export_raw(self):
        for item in (SECRET,{'action':SECRET,SECRET:SECRET},[SECRET],True,None):
            value=action_shape({'macro_actions':[item]},context())
            self.assertEqual(value['validation_code'],'macro_policy_actions')
            self.assertNotIn(SECRET,json.dumps(value))
    def test_known_normalized_enum_is_diagnostic_not_a_repair(self):
        value=action_shape({'macro_actions':[' BUDGET_ECONOMY ']},context())
        self.assertEqual(value['items'][0]['normalized_known_action'],'budgeteconomy')
        self.assertEqual(value['validation_code'],'macro_policy_actions')
        self.assertEqual(value['known_string_count'],0)
    def test_duplicates_over_limit_and_unsupported_are_distinct(self):
        for actions,code in [(['budgeteconomy']*2,'macro_policy_actions'),
            (['budgeteconomy']*6,'macro_policy_actions'),(['producesickle'],'unsupported_macro_action')]:
            self.assertEqual(action_shape({'macro_actions':actions},context())['validation_code'],code)
    def test_inspection_bounded_and_missing_not_treated_as_empty(self):
        value=action_shape({'macro_actions':[SECRET]*100},context())
        self.assertEqual(len(value['items']),8);self.assertTrue(value['items_truncated'])
        self.assertEqual(value['unique_count'],1)
        self.assertEqual(action_shape({},context())['validation_code'],'macro_policy_actions')
    def test_production_null_and_exact_object_follow_actions(self):
        for actions,prod,code in [(['budgeteconomy'],None,None),
            (['produceconscript'],None,'macro_production_quantity'),
            (['produceconscript'],{'action':'produceconscript','additional_count':1},None),
            (['produceconscript'],{'action':'produceconscript','additional_count':True},'macro_production_quantity'),
            (['budgeteconomy'],{'action':'produceconscript','additional_count':1},'macro_production_without_action')]:
            d=production_shape({'macro_actions':actions,'macro_production':prod},context())
            self.assertEqual(d['validation_code'],code)
    def test_production_unknown_values_and_extra_keys_are_hidden(self):
        value=production_shape({'macro_actions':['produceconscript'],'macro_production':{
            'action':SECRET,'additional_count':SECRET,SECRET:SECRET}},context())
        self.assertNotIn(SECRET,json.dumps(value));self.assertEqual(value['extra_field_count'],1)


if __name__=='__main__':unittest.main()
