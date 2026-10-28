import unittest

from host_runtime.arbitration import ActorIdentity, ArbitrationError, ControlArbiter


class ArbitrationTests(unittest.TestCase):
    def setUp(self):
        self.front = ActorIdentity("session", 3, 101, 10)
        self.support = ActorIdentity("session", 3, 102, 11)
        self.arbiter = ControlArbiter("session", 3, reviewed_micro_actions=("self_defense",))
        self.arbiter.claim("lease-a", "task-a", (self.front, self.support), issued_frame=20, deadline_frame=100)

    def test_actor_cannot_have_two_owners_or_reused_identity(self):
        for actor in (self.front, ActorIdentity("session", 3, 101, 90)):
            with self.assertRaisesRegex(ArbitrationError, "actor_already_owned"):
                self.arbiter.claim("lease-b", "task-b", (actor,), issued_frame=30, deadline_frame=120)

    def test_only_exact_current_task_command_is_allowed(self):
        no_source = self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=30, task_id="task-a")
        wrong_task = self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=31, task_id="task-b", source_verified=True)
        right = self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=32, task_id="task-a", source_verified=True)
        self.assertEqual((no_source.outcome, wrong_task.outcome, right.outcome), ("reject", "reject", "allow"))

    def test_reviewed_self_defense_differs_from_unreviewed_action(self):
        allowed = self.arbiter.decide("lease-a", self.support, action="native_micro:self_defense", game_frame=30, source_verified=True)
        denied = self.arbiter.decide("lease-a", self.support, action="native_micro:unknown_yield", game_frame=31, source_verified=True)
        self.assertEqual(allowed.outcome, "allow")
        self.assertEqual(denied.outcome, "stop")
        self.assertTrue(denied.release_requested)
        # A later task command cannot revive the stopped ownership projection.
        late = self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=32, task_id="task-a", source_verified=True)
        self.assertEqual(late.reason_code, "lease_return_pending")

    def test_deadline_is_immutable_and_request_does_not_release(self):
        decision = self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=100, task_id="task-a", source_verified=True)
        self.assertEqual(decision.reason_code, "lease_deadline_reached")
        with self.assertRaisesRegex(ArbitrationError, "actor_already_owned"):
            self.arbiter.claim("lease-b", "task-b", (self.front,), issued_frame=101, deadline_frame=200)
        with self.assertRaisesRegex(ArbitrationError, "lease_reused"):
            self.arbiter.claim("lease-a", "task-a", (self.front, self.support), issued_frame=20, deadline_frame=200)

    def test_verified_release_allows_second_mission_but_not_old_lease_reuse(self):
        self.arbiter.confirm_release("lease-a", (self.front, self.support), game_frame=80,
                                    source_reference="native-proof", independently_verified=True)
        second = self.arbiter.claim("lease-b", "task-b", (self.front,), issued_frame=81, deadline_frame=180)
        self.assertEqual(second['state'], 'held')
        self.assertFalse(second['execution_authority_granted'])
        self.assertEqual(self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=90,
                                             task_id="task-a", source_verified=True).outcome, "reject")
        with self.assertRaisesRegex(ArbitrationError, "lease_reused"):
            self.arbiter.claim("lease-a", "task-a", (self.front, self.support), issued_frame=20, deadline_frame=100)

    def test_unverified_release_cannot_unlock_actor(self):
        with self.assertRaisesRegex(ArbitrationError, "release_identity_or_proof"):
            self.arbiter.confirm_release("lease-a", (self.front, self.support), game_frame=80,
                                        source_reference="untrusted", independently_verified=False)
        with self.assertRaisesRegex(ArbitrationError, "actor_already_owned"):
            self.arbiter.claim("lease-b", "task-b", (self.front,), issued_frame=81, deadline_frame=180)

    def test_actor_generation_mismatch_cannot_issue(self):
        changed = ActorIdentity("session", 3, 101, 12)
        result = self.arbiter.decide("lease-a", changed, action="task_command", game_frame=40,
                                     task_id="task-a", source_verified=True)
        self.assertEqual(result.reason_code, "actor_identity_mismatch")

    def test_old_observation_cannot_authorize_or_release(self):
        self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=50,
                            task_id="task-a", source_verified=True)
        old = self.arbiter.decide("lease-a", self.front, action="task_command", game_frame=30,
                                   task_id="task-a", source_verified=True)
        self.assertEqual(old.reason_code, "observation_clock_regressed")
        with self.assertRaisesRegex(ArbitrationError, "release_clock_regressed"):
            self.arbiter.confirm_release("lease-a", (self.front, self.support), game_frame=40,
                                        source_reference="stale-proof", independently_verified=True)


if __name__ == "__main__":
    unittest.main()
