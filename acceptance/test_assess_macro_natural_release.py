import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import assess_macro_natural_release as assessment

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'acceptance/runs/20261028-062801-macro-probe'
WATCH=ROOT/'reports/macro-native-tech-77436-match-watch-20261028-v1'
RUN_ID='b44dec19-b866-4399-add5-33e77a18aa0e'
DOWNLOAD=Path('C:/Users/Administrator/Downloads/tacticore-diagnostics-539f4221-9e38-558d-9c05-c6627e338ad6.json')
EXPORT=Path('C:/Users/Administrator/AppData/Local/Tacticore/desktop-runtime/exports/539f4221-9e38-558d-9c05-c6627e338ad6.json')


class NaturalReleaseAssessmentTests(unittest.TestCase):
    def evaluate(self):return assessment.evaluate(RUN,RUN_ID,DOWNLOAD,EXPORT,WATCH)

    def test_actual_natural_release_does_not_claim_full_match_or_technology_choice(self):
        value=self.evaluate()
        self.assertTrue(value['natural_result_release_subset_verified'])
        self.assertTrue(value['host_started_mid_match'])
        self.assertFalse(value['model_technology_budget_selected'])
        self.assertFalse(value['full_G7_verified']);self.assertFalse(value['formal_goal_complete'])

    def test_unadopted_opening_budget_remains_no_effect_but_can_expire_in_a_natural_session(self):
        old=assessment.load(ROOT/'reports/macro-natural-release-74296-20261028-v1/assessment.json')
        paths=[Path(p) for p in old['evidence']]
        download=next(p for p in paths if p.parent==Path('C:/Users/Administrator/Downloads'))
        export=next(p for p in paths if p.name==download.name.removeprefix('tacticore-diagnostics-') and p!=download)
        value=assessment.evaluate(ROOT/'acceptance/runs/20261028-065549-macro-probe',old['run_id'],download,export,
            ROOT/'reports/macro-desktop-74296-match-watch-20261028-v1',
            ROOT/'reports/macro-desktop-production-74296-20261028-v1/assessment.json')
        self.assertFalse(value['checks']['every_budget_or_delegation_effect'])
        self.assertGreater(value['budget_unadopted_intents'],0)
        self.assertTrue(value['bounded_natural_result_and_release_verified'])
        self.assertFalse(value['full_G7_verified']);self.assertFalse(value['formal_goal_complete'])

    def test_a_budget_deadline_beyond_scope_cannot_pass_bounded_natural_operation(self):
        original=assessment.trial
        def changed(path):
            value=copy.deepcopy(original(path))
            first=next(r for r in value[3] if r['kind']=='command_acknowledged' and r['native']['applied_mask'])
            first['native']['deadline_frame']=first['native']['last_frame']+901
            return value
        with patch.object(assessment,'trial',side_effect=changed):value=self.evaluate()
        self.assertFalse(value['bounded_natural_session_checks']['all_budget_intents_bound_and_time_limited'])
        self.assertFalse(value['bounded_natural_result_and_release_verified'])

    def test_result_screen_without_native_result_boundary_is_insufficient(self):
        original=assessment.records
        def changed(path):
            rows=original(path)
            if path==WATCH/'native-match-transitions.jsonl':
                for row in rows:row['result_records']=[]
            return rows
        with patch.object(assessment,'records',side_effect=changed):value=self.evaluate()
        self.assertFalse(value['checks']['independent_natural_lifecycle'])
        self.assertFalse(value['natural_result_release_subset_verified'])

    def mixed(self,scouting=True):
        run=ROOT/'acceptance/runs/20261028-075720-macro-probe'
        download=Path('C:/Users/Administrator/Downloads/tacticore-diagnostics-4fab86e9-c05a-5a87-90bd-b6622d1d0242.json')
        export=Path('C:/Users/Administrator/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Tacticore/desktop-runtime/exports/4fab86e9-c05a-5a87-90bd-b6622d1d0242.json')
        return assessment.evaluate(run,'246c5557-f3ae-48f6-bca5-a83f0bf6571f',download,export,
            ROOT/'reports/macro-scout-77356-match-watch-20261028-v1',
            ROOT/'reports/macro-desktop-production-77356-20261028-v1/assessment.json',
            ROOT/'reports/macro-desktop-scouting-77356-20261028-v1/assessment.json' if scouting else None)

    def test_mixed_scouting_match_counts_all_commands_without_claiming_every_attempt_effective(self):
        value=self.mixed()
        self.assertEqual(value['native_macro_plan_dispatches'],23)
        self.assertEqual(value['scouting_commands'],3)
        self.assertTrue(value['some_model_scouting_feedback_loop_verified'])
        self.assertTrue(value['natural_result_release_subset_verified'])
        self.assertFalse(value['full_G7_verified'])

    def test_scout_commands_require_independent_scouting_assessment(self):
        value=self.mixed(False)
        self.assertFalse(value['checks']['bounded_scouting_and_feedback_verified'])
        self.assertFalse(value['natural_result_release_subset_verified'])

    def test_late_scout_dispatch_breaks_natural_stop_boundary(self):
        original=assessment.records
        def changed(path):
            rows=original(path)
            if path.name=='host-events.jsonl':rows.append(dict(kind='model_macro_scout_prepared'))
            return rows
        with patch.object(assessment,'records',side_effect=changed):value=self.mixed()
        self.assertFalse(value['checks']['no_new_requests_or_commands_after_stop'])
        self.assertFalse(value['natural_result_release_subset_verified'])

    def test_late_regional_dispatch_breaks_natural_stop_boundary(self):
        original=assessment.records
        def changed(path):
            rows=original(path)
            if path.name=='host-events.jsonl':rows.append(dict(kind='model_macro_region_prepared'))
            return rows
        with patch.object(assessment,'records',side_effect=changed):value=self.mixed()
        self.assertFalse(value['checks']['no_new_requests_or_commands_after_stop'])
        self.assertFalse(value['natural_result_release_subset_verified'])

    def test_fault_is_never_counted_as_normal_natural_release(self):
        original=assessment.load
        def changed(path):
            value=original(path)
            if path==RUN/'battle-host/host-status.json':value['state']='fault'
            return value
        with patch.object(assessment,'load',side_effect=changed):value=self.evaluate()
        self.assertFalse(value['checks']['host_ended_on_native_result'])
        self.assertFalse(value['natural_result_release_subset_verified'])
        self.assertFalse(value['bounded_natural_result_and_release_verified'])

    def test_a_late_new_request_breaks_the_stop_boundary(self):
        original=assessment.records
        def changed(path):
            rows=original(path)
            if path==RUN/'battle-host/host-events.jsonl':rows.append(dict(kind='commander_model_call_started'))
            return rows
        with patch.object(assessment,'records',side_effect=changed):value=self.evaluate()
        self.assertFalse(value['checks']['no_new_requests_or_commands_after_stop'])
        self.assertFalse(value['natural_result_release_subset_verified'])


if __name__=='__main__':unittest.main()
