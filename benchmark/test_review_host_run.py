"""Pure offline contract tests, not live match outcomes."""
import copy
import unittest
from review_host_run import review

class ReviewTests(unittest.TestCase):
    def fixture(self):
        binding = dict(session_id='test-session', player_id=3, commander_id='test-commander')
        return {'session.json': dict(session_id='test-session', mod_sha256='package'),
                'battle-host/host-status.json': dict(session_id='test-session', binding=binding,
                    metrics=dict(requests=2, accepted=2, rejected=0, timeouts=0, adapter_errors=0, plan_changes=1)),
                'battle-host/agent-state.json': dict(binding=binding, active_goals=[dict(task_id='a', status='planned')]),
                'battle-host/plans.jsonl': [], 'battle-host/host-events.jsonl': []}

    def test_initial_plan_is_not_change(self):
        result = review(self.fixture())
        self.assertEqual(result['strategy']['intent_transitions_excluding_initial'], 0)

    def test_missing_production_and_no_terminal_tasks_remain_unknown(self):
        result = review(self.fixture())
        self.assertIsNone(result['production'])
        self.assertIsNone(result['tasks']['completion_rate_known_started_outcomes'])
        self.assertEqual(result['tasks']['unique_retained_tasks_by_status']['planned'], 1)

    def test_prestart_failure_not_task_failure(self):
        sources = self.fixture()
        binding = sources['battle-host/host-status.json']['binding']
        sources['battle-host/host-events.jsonl'] = [dict(binding, kind='task_feedback', task_id='a', status='failed')]
        result = review(sources)
        self.assertEqual(result['tasks']['prestart_rejections_not_failed_tasks'], 1)
        self.assertEqual(result['tasks']['observed_started_failed'], 0)
        self.assertIsNone(result['tasks']['completion_rate_known_started_outcomes'])

    def test_wrong_session_rejected(self):
        sources = self.fixture()
        sources['battle-host/host-events.jsonl'] = [dict(session_id='other')]
        with self.assertRaises(ValueError): review(sources)

    def feedback(self, *rows):
        sources = self.fixture()
        binding = sources['battle-host/host-status.json']['binding']
        sources['battle-host/host-events.jsonl'] = [dict(binding, kind='task_feedback', task_id=task, status=status)
                                                   for task, status in rows]
        return review(sources)

    def test_orphan_completion_is_raw_report_only(self):
        result = self.feedback(('a', 'completed'))
        self.assertEqual(result['tasks']['host_reported_completed'], 1)
        self.assertEqual(result['tasks']['observed_started_completed'], 0)
        self.assertEqual(result['tasks']['prestart_completions_not_completed_tasks'], 1)
        self.assertIsNone(result['tasks']['completion_rate_known_started_outcomes'])
        self.assertFalse(result['whole_match_acceptance_passed'])

    def test_late_start_cannot_retroactively_certify_completion(self):
        result = self.feedback(('a', 'completed'), ('a', 'started'), ('a', 'completed'))
        self.assertEqual(result['tasks']['observed_started'], 1)
        self.assertEqual(result['tasks']['observed_started_completed'], 0)
        self.assertIsNone(result['tasks']['completion_rate_known_started_outcomes'])

    def test_repeated_ordered_completion_is_one_outcome(self):
        result = self.feedback(('a', 'started'), ('a', 'started'), ('a', 'completed'), ('a', 'completed'),
                               ('b', 'started'), ('b', 'failed'), ('c', 'started'))
        self.assertEqual(result['tasks']['observed_started_completed'], 1)
        self.assertEqual(result['tasks']['observed_started_failed'], 1)
        self.assertEqual(result['tasks']['started_without_terminal_feedback'], 1)
        self.assertEqual(result['tasks']['completion_rate_known_started_outcomes'], .5)

    def test_conflicting_terminals_never_double_count(self):
        for states in [('completed', 'failed'), ('failed', 'completed'), ('completed', 'cancelled')]:
            result = self.feedback(('a', 'started'), *(('a', state) for state in states))
            self.assertEqual(result['tasks']['started_with_conflicting_terminal_feedback'], 1)
            self.assertEqual(result['tasks']['observed_started_completed'], 0)
            self.assertEqual(result['tasks']['observed_started_failed'], 0)
            self.assertEqual(result['tasks']['started_without_terminal_feedback'], 0)
            self.assertIsNone(result['tasks']['completion_rate_known_started_outcomes'])

    def test_prestart_rejection_does_not_poison_later_valid_start(self):
        result = self.feedback(('a', 'failed'), ('a', 'started'), ('a', 'completed'))
        self.assertEqual(result['tasks']['prestart_rejections_not_failed_tasks'], 1)
        self.assertEqual(result['tasks']['observed_started_completed'], 1)
        self.assertEqual(result['tasks']['completion_rate_known_started_outcomes'], 1.)

    def test_cost_without_created_unit_not_complete(self):
        sources = self.fixture()
        row = dict(status='completed', command_id='c', seq=1, accepted=True, started=True,
                   completed=True, paid_verified=True, cost=85, paid=85,
                   created=False, completion_observed=True, queue_preserved=True,
                   queue_id=1, object_id=5, live_samples=1, payment_error=0)
        sources['persistent-production.jsonl'] = [dict(event='attach_preflight', session_id='test-session', commander_id='test-commander', package_sha256='package'),dict(row,event='execution_feedback')]
        self.assertEqual(review(sources)['production']['fully_verified_units'], 0)

    def test_repeated_completion_rows_count_once_and_bind_package(self):
        sources = self.fixture()
        row = dict(status='completed', command_id='c', seq=1, task_id='a', unit='conscript', accepted=True, started=True,
                   completed=True, paid_verified=True, cost=85, paid=85, created=True,
                   completion_observed=True, queue_preserved=True, queue_id=1, object_id=5,
                   live_samples=1, payment_error=0)
        command=dict(sources['battle-host/host-status.json']['binding'], command_id='c',seq=1,task_id='a',unit='conscript')
        sources['persistent-production.jsonl'] = [dict(event='attach_preflight', session_id='test-session', commander_id='test-commander', package_sha256='package'), dict(event='command_dispatch_pending',command=command),dict(row,event='execution_feedback'),dict(row,event='execution_feedback')]
        result=review(sources)
        self.assertEqual(result['production']['fully_verified_units'], 1)
        self.assertEqual(result['production']['verified_paid_credits'], 85)
        altered=copy.deepcopy(sources)
        altered['persistent-production.jsonl'][0]['package_sha256']='wrong'
        self.assertEqual(review(altered)['production']['fully_verified_units'], 0)

    def test_result_candidate_not_finalized(self):
        sources = self.fixture()
        sources['battle-host/match-state.json'] = dict(match_ended_verified=True, result_records=[dict(victory_frame=100)])
        result = review(sources)
        self.assertFalse(result['result_finalized'])
        self.assertFalse(result['whole_match_acceptance_passed'])

    def test_prearmed_early_request_is_candidate_only(self):
        sources=self.fixture()
        sources['session.json']['scenario']={'host_prearmed':True}
        binding=sources['battle-host/host-status.json']['binding']
        sources['battle-host/plans.jsonl']=[dict(binding,event='request',game_time_seconds=.9)]
        sources['battle-host/host-events.jsonl']=[dict(binding,kind='entered_match',first_game_time_seconds=.9)]
        result=review(sources)
        self.assertEqual(result['trial_kind'],'prearmed_whole_match_integration_candidate')
        self.assertFalse(result['whole_match_acceptance_passed'])

if __name__ == '__main__': unittest.main()
