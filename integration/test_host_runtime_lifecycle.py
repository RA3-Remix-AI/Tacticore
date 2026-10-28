import unittest

from host_runtime.lifecycle import LifecycleError, MissionLifecycle, MissionRegistry, ReceiptEvidence


class LifecycleTests(unittest.TestCase):
    def prepared(self, task="task-a"):
        mission = MissionLifecycle("session", task, 1)
        for frame, state in enumerate(("validating", "planning", "preparing", "ready", "committing", "accepted", "executing"), 1):
            mission.advance(state, reason_code="test_transition", game_frame=frame, monotonic_ms=frame * 20)
        return mission

    def receipt(self, task="task-a", **changes):
        values = dict(session_id="session", task_id=task, generation=1, game_frame=20,
                      effect_verified=True, physical_return_verified=True,
                      control_release_verified=True, source_reference="verified-native-receipt")
        values.update(changes)
        return ReceiptEvidence(**values)

    def test_release_is_not_completion(self):
        mission = self.prepared()
        mission.record_release(self.receipt(effect_verified=False), monotonic_ms=400)
        self.assertEqual(mission.state, "released")
        mission.finish(game_frame=20, monotonic_ms=400)
        self.assertEqual(mission.state, "failed")
        self.assertTrue(mission.public()["control_release_verified"])
        self.assertFalse(mission.public()["effect_verified"])

    def test_effect_without_physical_return_is_not_success(self):
        mission = self.prepared()
        mission.record_release(self.receipt(physical_return_verified=False), monotonic_ms=400)
        mission.finish(game_frame=20, monotonic_ms=400)
        self.assertEqual(mission.state, "failed")

    def test_completion_needs_bound_evidence(self):
        mission = self.prepared()
        with self.assertRaisesRegex(LifecycleError, "receipt_identity_mismatch"):
            mission.record_release(self.receipt(task="old-task"), monotonic_ms=400)
        with self.assertRaisesRegex(LifecycleError, "release_unverified"):
            mission.record_release(self.receipt(control_release_verified=False), monotonic_ms=400)
        self.assertEqual(mission.state, "executing")
        mission.record_release(self.receipt(), monotonic_ms=400)
        mission.finish(game_frame=21, monotonic_ms=420)
        self.assertEqual(mission.state, "completed")

    def test_cancellation_during_commit_is_uncertain_until_release(self):
        mission = MissionLifecycle("session", "task-a", 1)
        for frame, state in enumerate(("validating", "planning", "preparing", "ready", "committing"), 1):
            mission.advance(state, reason_code="test", game_frame=frame, monotonic_ms=frame)
        mission.request_stop(reason_code="user_stop", game_frame=6, monotonic_ms=6)
        self.assertEqual(mission.state, "uncertain")
        self.assertFalse(mission.public()["terminal"])
        with self.assertRaisesRegex(LifecycleError, "invalid_state_transition"):
            mission.advance("committing", reason_code="retry", game_frame=7, monotonic_ms=7)
        mission.record_release(self.receipt(), monotonic_ms=20)
        self.assertEqual(mission.state, "cancelled")

    def test_stop_while_executing_requires_release(self):
        mission = self.prepared()
        mission.request_stop(reason_code="user_stop", game_frame=8, monotonic_ms=160)
        self.assertEqual(mission.state, "returning")
        with self.assertRaisesRegex(LifecycleError, "completion_requires_release"):
            mission.finish(game_frame=9, monotonic_ms=180)
        mission.record_release(self.receipt(effect_verified=False), monotonic_ms=400)
        self.assertEqual(mission.state, "cancelled")

    def test_clock_regression_does_not_mutate_state(self):
        mission = self.prepared()
        before = mission.public()
        with self.assertRaisesRegex(LifecycleError, "clock_regressed"):
            mission.request_stop(reason_code="stop", game_frame=6, monotonic_ms=1000)
        with self.assertRaisesRegex(LifecycleError, "clock_regressed"):
            mission.request_stop(reason_code="stop", game_frame=100, monotonic_ms=5)
        self.assertEqual(before, mission.public())

    def test_sink_failure_does_not_advance_projection(self):
        def failed(_):
            raise OSError("database unavailable")
        mission = MissionLifecycle("session", "task-a", 1, event_sink=failed)
        with self.assertRaises(OSError):
            mission.advance("validating", reason_code="validate", game_frame=1, monotonic_ms=1)
        self.assertEqual(mission.state, "proposed")
        self.assertEqual(mission.events(), [])

    def test_second_task_in_same_session_is_independent(self):
        registry = MissionRegistry("session")
        first = registry.create("task-a", 1)
        first.request_stop(reason_code="no_target", game_frame=1, monotonic_ms=1, failed=True)
        second = registry.create("task-b", 1, game_frame=2, monotonic_ms=2)
        second.advance("validating", reason_code="new_task", game_frame=3, monotonic_ms=3)
        self.assertEqual(first.state, "failed")
        self.assertEqual(second.state, "validating")
        self.assertIs(first, registry.create("task-a", 1))
        with self.assertRaisesRegex(LifecycleError, "task_id_reused"):
            registry.create("task-a", 2)


if __name__ == "__main__":
    unittest.main()
