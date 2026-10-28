import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import assess_macro_desktop_production as audit

RUN=audit.ROOT/'acceptance/runs/20261028-044027-macro-probe'
RUN_ID='a43492c2-6cf4-40e5-a196-d02f26fbb143'


class ProductionEvidenceTests(unittest.TestCase):
    def test_queue_observed_after_native_expiry_cannot_pass_as_model_production_effect(self):
        run=audit.ROOT/'acceptance/runs/20261028-110543-macro-probe';ident='f12886bd-6242-497a-9fdd-87a4862102e7'
        value=audit.assess(run,ident)
        tank=next(r for r in value['production_results'] if r['action']=='producetank')
        self.assertFalse(tank['release_after_observed_queue_target'])
        self.assertTrue(tank['bounded_release_verified'])
        self.assertEqual(tank['final_observations']['observed_new_queue_count'],0)
        self.assertGreater(tank['final_observations']['additional_queue_observations_after_release'],0)
        self.assertTrue(any(not r['observed_counts_match'] for r in tank['production_feedback_in_followup_requests']))
        self.assertFalse(value['bounded_production_lifecycle_verified'])
        self.assertFalse(value['native_production_subset_verified'])

    def test_native_expiry_is_replayed_before_observing_a_later_autonomous_queue(self):
        run=audit.ROOT/'acceptance/runs/20261028-120251-macro-probe';ident='b724b078-474e-429c-ba00-894780a2f844'
        value=audit.assess(run,ident)
        result=next(r for r in value['production_results'] if r['native_seq']==31)
        self.assertTrue(result['bounded_release_verified'])
        self.assertFalse(result['observed_queue_goal_met'])
        self.assertEqual(result['release_reason'],'expired')
        self.assertEqual(result['final_observations']['observed_new_queue_count'],0)
        self.assertTrue(all(r['observed_counts_match'] for r in result['production_feedback_in_followup_requests']))
        self.assertTrue(value['bounded_production_lifecycle_verified'])
        self.assertFalse(value['native_production_subset_verified'])

    def test_choice_loop_handles_partial_expiry_and_user_stop_without_claiming_all_targets_met(self):
        run=audit.ROOT/'acceptance/runs/20261028-050458-macro-probe';ident='a0240fae-67f6-4bd8-a88e-dbfc746d99a0'
        value=audit.assess(run,ident)
        self.assertTrue(value['durable_production_loop_verified']);self.assertTrue(value['user_stop_completed'])
        self.assertFalse(value['native_production_subset_verified']);self.assertFalse(value['full_G6_verified'])
        tank=next(r for r in value['production_results'] if r['action']=='producetank')
        self.assertEqual(tank['final_observations']['observed_new_queue_count'],0)
        self.assertEqual(tank['release_reason'],'expired');self.assertFalse(tank['observed_queue_goal_met'])
        last=value['production_results'][-1]
        self.assertEqual(last['release_reason'],'stopped')
        self.assertEqual(last['production_feedback_in_followup_requests'],[])
        self.assertEqual(value['native_plan_dispatches'],7);self.assertEqual(value['engine_accepted_plans'],8)

    def test_early_clear_of_unfulfilled_goal_cannot_pass_as_valid_expiry(self):
        run=audit.ROOT/'acceptance/runs/20261028-050458-macro-probe';ident='a0240fae-67f6-4bd8-a88e-dbfc746d99a0'
        changed=copy.deepcopy(audit.trial(audit.ROOT/'reports'/('macro-desktop-'+ident)))
        commands={r['seq']:r for r in changed[3] if r['kind']=='command_acknowledged'}
        commands[6]['native']['last_frame']=commands[5]['native']['last_frame']+1
        with patch.object(audit,'trial',return_value=changed):value=audit.assess(run,ident)
        self.assertFalse(value['bounded_production_lifecycle_verified'])
        self.assertFalse(value['durable_production_loop_verified'])

    def test_actual_production_field_preserves_queue_evidence_and_terminal_fault(self):
        value=audit.assess(RUN,RUN_ID)
        self.assertTrue(value['native_production_subset_verified'])
        self.assertEqual(value['real_model_responses'],7)
        self.assertEqual(value['production_commands'],1)
        result=value['production_results'][0]
        self.assertEqual(result['final_observations']['observed_new_queue_count'],2)
        self.assertEqual(result['final_observations']['additional_queue_observations_after_release'],1)
        self.assertEqual(len(result['production_feedback_in_followup_requests']),3)
        self.assertEqual(value['terminal_reason'],'macro_production_feedback_invalid_or_stale')
        self.assertFalse(value['user_stop_completed']);self.assertFalse(value['durable_production_loop_verified'])
        self.assertFalse(value['formal_goal_complete'])

    def test_gate_ack_and_autonomous_queues_without_positive_native_consumer_are_insufficient(self):
        original=audit.trial(audit.ROOT/'reports'/('macro-desktop-'+RUN_ID))
        changed=copy.deepcopy(original)
        for row in changed[3]:
            if row['kind']=='native_builder_observation' and 'observation' in row:
                for entry in row['observation']['macro_entries']:entry['state_score']=0
        with patch.object(audit,'trial',return_value=changed):value=audit.assess(RUN,RUN_ID)
        self.assertFalse(value['checks']['model_intent_native_queue_effect'])
        self.assertFalse(value['native_production_subset_verified'])


if __name__=='__main__':unittest.main()
