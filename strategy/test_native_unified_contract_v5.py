import unittest
from native_unified_contract_v5 import (split_intents,split_native7_intents,additional_catalog,
    INDEPENDENT_DEVELOPMENT_CONTRACT,focus_action,focus_actions_for)
from macro_policy import validate_actions,public_descriptions

class HighLevelDomains(unittest.TestCase):
    def test_raid_is_a_native_military_intent_with_separate_expansion(self):
        self.assertEqual(split_native7_intents(['raideconomy','focusenemy5','expand']),
            (('expand','raideconomy'),{},5))
        with self.assertRaisesRegex(ValueError,'requires_native7'):split_intents(['raideconomy'])
        for actions in (['raideconomy','attackenemy'],['raideconomy','deploydefense']):
            with self.subTest(actions=actions),self.assertRaises(ValueError):split_native7_intents(actions)
        raid=additional_catalog(['raideconomy'])['raideconomy']
        self.assertEqual(raid['target_policy'],'original_native_safest_ground_harvester')
        self.assertTrue(raid['native_task_readiness_preserved'])
        self.assertNotIn('unit_template',raid)

    def test_native7_expansion_and_military_have_independent_replacement_domains(self):
        actions=['deploydefense','expand','budgeteconomy','focusenemy4','advanceconstruction','advanceproduction']
        flags,gates,focus=split_native7_intents(actions)
        self.assertEqual(flags,('deploydefense','budgeteconomy','expand'))
        self.assertEqual(gates,{0:True,1:True})
        self.assertEqual(focus,4)
        kwargs=dict(request_intent_contract=INDEPENDENT_DEVELOPMENT_CONTRACT,
            latest_intent_contract=INDEPENDENT_DEVELOPMENT_CONTRACT)
        self.assertEqual(validate_actions(actions,actions,actions,**kwargs),tuple(actions))
        for invalid in (['scout','deploydefense'],['attackenemy','deploydefense'],['expand','expand']):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):split_native7_intents(invalid)
        with self.assertRaises(ValueError):split_intents(['scout','expand'])
        for request,latest in ((None,None),(INDEPENDENT_DEVELOPMENT_CONTRACT,None),
                               (None,INDEPENDENT_DEVELOPMENT_CONTRACT)):
            with self.subTest(request=request,latest=latest),self.assertRaises(ValueError):
                validate_actions(['scout','expand'],['scout','expand'],['scout','expand'],
                    request_intent_contract=request,latest_intent_contract=latest)

    def test_focus_intents_follow_the_actual_enemy_ids(self):
        self.assertEqual(focus_actions_for((2,6)),{'focusenemy2':2,'focusenemy6':6})
        self.assertEqual(split_native7_intents(['attackenemy','focusenemy2'])[2],2)
        self.assertEqual(additional_catalog(['focusenemy6'])['focusenemy6']['target_player_id'],6)
        for invalid in (-1,16,True,'4'):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):focus_action(invalid)
        with self.assertRaises(ValueError):split_native7_intents(['focusenemy16'])

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
