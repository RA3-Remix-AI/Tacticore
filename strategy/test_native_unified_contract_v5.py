import unittest
from native_unified_contract_v5 import split_intents,additional_catalog
from macro_policy import validate_actions,public_descriptions

class HighLevelDomains(unittest.TestCase):
    def test_legal_combined_domains(self):
        actions=['scout','budgetarmy','pauseconstruction','advanceproduction']
        self.assertEqual(split_intents(actions),(('scout','budgetarmy'),{0:False,1:True}))
        self.assertEqual(validate_actions(actions,actions,actions),tuple(actions))
    def test_conflicts_and_precise_names_refused(self):
        for actions in (['expand','scout'],['budgetarmy','budgettech'],['pauseproduction','advanceproduction'],['buildfactory'],['producebullfrog']):
            with self.subTest(actions=actions),self.assertRaises(ValueError):split_intents(actions)
    def test_catalogue_does_not_claim_queue_or_global_stop(self):
        catalog=public_descriptions(['expand','pauseconstruction','advanceproduction'])
        self.assertTrue(catalog['expand']['stock_conditions_preserved'])
        self.assertFalse(catalog['expand']['release_blocks_autonomous_expansion'])
        self.assertTrue(catalog['pauseconstruction']['opening_and_committed_work_not_globally_stopped'])
        self.assertEqual(catalog['advanceproduction']['native_manager'],'unit_and_prerequisite_builder_family')
        self.assertTrue(all('quantity' not in value and 'building' not in value for value in catalog.values()))

if __name__=='__main__':unittest.main()
