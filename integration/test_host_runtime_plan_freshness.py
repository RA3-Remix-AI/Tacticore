"""Plan expiry gates new intents without hiding receipts or stop requests."""
import unittest

from host_runtime.orchestration import MissionOrchestrator, OrchestrationConfig
import test_host_runtime_orchestration as fixtures
import test_host_runtime_coordinator as coordinator_fixtures


class PlanFreshnessTests(unittest.TestCase):
    def producing(self):
        machine = MissionOrchestrator(fixtures.BINDING)
        first = machine.advance(fixtures.observation()).intents[0]
        later = fixtures.observation(250, 200,
            receipts=[fixtures.receipt(first, 'accepted', enqueue_frame=100)])
        return machine, first, later

    def test_invalid_plan_does_not_create_second_production(self):
        for kind in ('wall', 'frame', 'missing', 'task', 'generation', 'plan_id'):
            with self.subTest(kind=kind):
                machine, _, later = self.producing()
                if kind == 'wall': later['plan']['valid_until_monotonic_ms'] = 200
                elif kind == 'frame': later['plan']['expires_frame'] = 250
                elif kind == 'missing': del later['plan']
                elif kind == 'task': later['plan']['task_id'] = 'other-task'
                elif kind == 'generation': later['plan']['generation'] += 1
                else: later['plan']['plan_id'] = 'other-plan'
                result = machine.advance(later)
                self.assertEqual(result.intents, ())
                self.assertTrue(any(e['event_type'] == 'plan_wait' for e in result.events))

    def test_valid_plan_still_creates_second_production(self):
        machine, _, later = self.producing()
        result = machine.advance(later)
        self.assertEqual([i['payload']['unit'] for i in result.intents], ['flak'])

    def test_expired_plan_does_not_hide_rejected_receipt(self):
        machine, first, later = self.producing()
        later['plan']['valid_until_monotonic_ms'] = 0
        later['receipts'] = [fixtures.receipt(first, 'rejected')]
        result = machine.advance(later)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(result.reason_code, 'production_rejected')

    def test_expired_plan_does_not_hide_unknown_receipt(self):
        machine, first, later = self.producing()
        later['plan']['valid_until_monotonic_ms'] = 0
        later['receipts'] = [fixtures.receipt(first, 'uncertain')]
        result = machine.advance(later)
        self.assertEqual(result.state, 'uncertain')
        self.assertEqual([i['operation'] for i in result.intents], ['query_status'])

    def test_missing_plan_does_not_block_user_stop(self):
        machine, _, later = self.producing()
        del later['plan']
        later['stop_requested'] = True
        result = machine.advance(later)
        self.assertEqual(result.state, 'cancelled')
        self.assertEqual(result.intents, ())

    def test_waiting_for_plan_does_not_renew_preparation_timeout(self):
        machine, _, later = self.producing()
        later['plan']['valid_until_monotonic_ms'] = 0
        self.assertEqual(machine.advance(later).state, 'producing')
        later['game_frame'] += 1
        later['monotonic_ms'] = 60000
        later['contacts'][0]['observed_frame'] = later['game_frame']
        result = machine.advance(later)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(result.reason_code, 'preparation_timeout')

    def test_paid_ready_actors_need_current_plan_before_reserve(self):
        machine = MissionOrchestrator(fixtures.BINDING, OrchestrationConfig(production_gap_frames=0))
        first = machine.advance(fixtures.observation()).intents[0]
        actors = [dict(role=role, object_id=ident, generation=gen, owner_player_id=3,
                       alive=True, ground_ready=True, held=False)
                  for role, ident, gen in [('infantry', 801, 11), ('anti_air', 802, 12)]]
        paid_first = fixtures.receipt(first, 'completed', enqueue_frame=100,
            object_id=801, actor_generation=11, paid_verified=True, created=True, paid=85)
        second = machine.advance(fixtures.observation(101, 10,
            receipts=[paid_first], actors=actors)).intents[0]
        paid_second = fixtures.receipt(second, 'completed', enqueue_frame=101,
            object_id=802, actor_generation=12, paid_verified=True, created=True, paid=220)
        later = fixtures.observation(102, 20, receipts=[paid_second], actors=actors)
        later['plan']['valid_until_monotonic_ms'] = 20
        result = machine.advance(later)
        self.assertEqual(result.intents, ())
        self.assertEqual(result.state, 'producing')
        self.assertIsNone(machine.public()['lease_start_frame'])

    def test_coordinator_does_not_dispatch_expired_second_production(self):
        fixture = coordinator_fixtures.CoordinatorTests()
        fixture.setUp()
        try:
            fixture.coordinator.tick(fixture.obs())
            later = fixture.obs(250)
            later['plan']['valid_until_monotonic_ms'] = 0
            fixture.coordinator.tick(later)
            self.assertEqual([c['payload']['unit'] for c in fixture.adapter.commands], ['conscript'])
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
