import copy
import unittest
from unittest.mock import patch
import assess_macro_complete_match as audit

ROOT=audit.ROOT
ARGS=(ROOT/'acceptance/runs/20261028-120251-macro-probe',
    ROOT/'reports/macro-natural-forces-77280-20261028-v2/assessment.json',
    ROOT/'reports/macro-outcome-77280-20261028-v1/assessment.json',
    ROOT/'reports/macro-timeline-77280-20261028-v2',ROOT/'delivery/commander-macro-20261028-progress-v1')


class CompleteMatchTests(unittest.TestCase):
    def test_actual_natural_match_passes_without_claiming_a_win_or_all_goals(self):
        result=audit.evaluate(*ARGS)
        self.assertTrue(result['full_G7_verified'])
        self.assertEqual(result['model_side_outcome'],'defeat')
        self.assertFalse(result['formal_goal_complete'])
        self.assertFalse(result['native_replay_fidelity_verified'])

    def test_missing_cross_round_memory_does_not_pass(self):
        rows=copy.deepcopy(audit.records(ARGS[0]/'battle-host/host-events.jsonl'))
        for row in rows:
            if row['kind']=='model_macro_request_context':row['context']['working_memory']['current_strategy']=None
        with patch.object(audit,'records',return_value=rows):result=audit.evaluate(*ARGS)
        self.assertFalse(result['full_G7_verified'])
        self.assertFalse(result['checks']['prior_model_strategy_reaches_later_round'])

    def test_absent_natural_verification_cannot_be_replaced_by_a_timeline(self):
        original=audit.bound_report
        def changed(path):
            value=original(path)
            if path==ARGS[1]:value['bounded_natural_result_and_release_verified']=False
            return value
        with patch.object(audit,'bound_report',side_effect=changed):result=audit.evaluate(*ARGS)
        self.assertFalse(result['full_G7_verified'])


if __name__=='__main__':unittest.main()
