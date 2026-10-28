"""A native autonomous build or rejected combined model plan cannot pass G6."""
import unittest
import copy
from unittest.mock import patch
import assess_macro_desktop_construction as audit


class ConstructionEvidenceTests(unittest.TestCase):
    def test_real_directed_build_expiry_then_queue_feedback_and_stop_are_distinct(self):
        value=audit.assess(audit.ROOT/'acceptance/runs/20261028-060454-macro-probe',
            'ff9fcc7a-dfe8-419a-ac1e-c551a3cefcf1')
        self.assertEqual(value['construction_commands'],2);self.assertEqual(value['real_model_responses'],12)
        self.assertTrue(value['durable_construction_loop_verified']);self.assertTrue(value['user_stop_completed'])
        self.assertTrue(value['some_model_construction_effect_verified'])
        self.assertFalse(value['native_construction_subset_verified'])
        first,second=value['construction_results']
        self.assertEqual(first['release_reason'],'expired');self.assertEqual(first['final_observations']['observed_new_queue_count'],0)
        self.assertEqual(second['release_reason'],'queue_observed');self.assertEqual(second['final_observations']['observed_new_queue_count'],1)
        self.assertFalse(second['final_observations']['construction_completed_verified'])
        self.assertTrue(value['directed_acceptance_scenario']);self.assertFalse(value['autonomous_build_choice_verified'])

    def test_no_positive_consumer_cannot_turn_autonomous_construction_into_model_effect(self):
        ident='ff9fcc7a-dfe8-419a-ac1e-c551a3cefcf1'
        changed=copy.deepcopy(audit.trial(audit.ROOT/'reports'/('macro-desktop-'+ident)))
        for row in changed[3]:
            if row['kind']=='native_builder_observation' and 'observation' in row:
                for item in row['observation']['macro_entries']:item['state_score']=0
        with patch.object(audit,'trial',return_value=changed):
            value=audit.assess(audit.ROOT/'acceptance/runs/20261028-060454-macro-probe',ident)
        self.assertFalse(value['some_model_construction_effect_verified'])
        self.assertFalse(value['durable_construction_loop_verified'])

    def test_early_clear_is_not_relabelled_a_valid_build_expiry(self):
        ident='ff9fcc7a-dfe8-419a-ac1e-c551a3cefcf1'
        changed=copy.deepcopy(audit.trial(audit.ROOT/'reports'/('macro-desktop-'+ident)))
        commands={r['seq']:r for r in changed[3] if r['kind']=='command_acknowledged'}
        commands[5]['native']['last_frame']=commands[4]['native']['last_frame']+1
        with patch.object(audit,'trial',return_value=changed):
            value=audit.assess(audit.ROOT/'acceptance/runs/20261028-060454-macro-probe',ident)
        self.assertFalse(value['bounded_construction_lifecycle_verified'])
        self.assertFalse(value['durable_construction_loop_verified'])

    def test_no_model_build_dispatch_does_not_claim_native_construction_effect(self):
        value=audit.assess(audit.ROOT/'acceptance/runs/20261028-053118-macro-probe',
            'dc61806b-7255-4b20-b7a4-fdd3f5949b11')
        self.assertTrue(value['checks']['genuine_provider']);self.assertTrue(value['user_stop_completed'])
        self.assertEqual(value['construction_commands'],0)
        self.assertFalse(value['native_construction_subset_verified'])
        self.assertFalse(value['construction_completed_verified'])

    def test_model_requested_build_but_controller_refused_it_is_not_an_executed_build(self):
        value=audit.assess(audit.ROOT/'acceptance/runs/20261028-053916-macro-probe',
            '92c1fa98-2189-45ad-bd26-65d63958f2c4')
        self.assertEqual(value['terminal_state'],'fault');self.assertEqual(value['real_model_responses'],5)
        self.assertEqual(value['construction_commands'],0);self.assertFalse(value['user_stop_completed'])
        self.assertFalse(value['checks']['model_build_choice_native_effect'])
        self.assertTrue(value['checks']['native_cleanup_verified']);self.assertFalse(value['formal_goal_complete'])


if __name__=='__main__':unittest.main()
