"""Native high-level domains, including enemy focus, through the real ledger and controller.

The transport is artificial. This establishes no Game or native API effect.
"""

import copy
import unittest

from host_runtime.contracts import ContractError
from host_runtime.native_runtime import NativeScope
from host_runtime.native_runtime_contract import FLAG_ACTIONS, FLAGS, PACKAGE_SHA
from host_runtime.strategic_contract import split_intents, split_native7_intents
from host_runtime.strategic_controller import StrategicController
from host_runtime.strategic_feedback import project_unified_feedback
from macro_policy import validate_actions
import test_strategic_controller as existing_fixture


def selector(enemies, alive, target=None):
    """A bound native enemy-selector sample for own player 3."""
    enemy_mask = sum(1 << player for player in enemies)
    alive_mask = (1 << 3) | sum(1 << player for player in alive)
    priority = [int(bool(enemy_mask & alive_mask & (1 << player))) for player in range(16)]
    if target is not None:
        priority[target] = 10
    return dict(
        source="bound_native_enemy_selector_v2",
        manual=int(target is not None),
        isolated=0,
        enumeration_lock=0,
        own_player_id=3,
        enemy_mask=enemy_mask,
        alive_mask=alive_mask,
        priority=priority,
        automatic_scheme=2,
        selector=0x10000,
        public_opponent_ids=sorted(enemies),
    )


class NativeDispatch(unittest.TestCase):
    enemies = (4, 5)

    def setUp(self):
        self.fixture = existing_fixture.Dispatch()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        state = self.fixture.native
        self.fixture.flag_actions = FLAG_ACTIONS
        transport = self.fixture.controller.transport
        enemies = self.enemies

        def focus(player, frames, ident, *, not_after_frame):
            self.fixture.calls.append(dict(kind="focus", enemy_player_id=player, absolute=not_after_frame))
            if getattr(self, "fail_focus", False):
                raise RuntimeError("artificial unknown focus publication")
            state["last_frame"] += 1
            state["ack"] += 1
            state["request"] = state["ack"]
            state["result"] = 10 if player is None else 9
            sample = selector(enemies, enemies, player)
            state["focus"] = dict(
                phase=4 if player is None else 1,
                baseline_captured=1,
                selector=0x10000,
                baseline_scheme=2,
                target_player=player if player is not None else state["focus"].get("target_player", 0),
                request=state["ack"],
                manual=int(player is not None),
                isolated=0,
                own_player=3,
                enemy_mask=sample["enemy_mask"],
                alive_mask=sample["alive_mask"],
                priority=sample["priority"],
                frame=state["last_frame"],
                callback=state["ack"],
                deadline_frame=not_after_frame if player is not None else 0,
                call_reservations=1,
                reserved=0,
                ms=1000,
                deadline_ms=30000 if player is not None else 0,
            )
            return dict(
                seq=state["ack"],
                native=copy.deepcopy(state),
                native_gate_acknowledged=True,
                native_effect_verified=False,
            )

        transport.focus = focus
        scope = NativeScope(PACKAGE_SHA, tuple(zip(FLAG_ACTIONS, FLAGS)), (), (), opponent_player_ids=self.enemies)
        self.controller = StrategicController(
            transport,
            self.fixture.journal,
            self.fixture.run,
            scope,
            self.fixture.session,
            "a" * 64,
            lambda *args, **kwargs: None,
        )

    def observe(self, sample):
        state = self.fixture.native
        frame = state["last_frame"]
        self.controller.observe(
            dict(observation_complete=True, frame=frame, runtimes=[]),
            state,
            dict(frame=frame, components=[], enemy_focus=sample),
        )
        return frame

    def test_expansion_and_defense_share_one_bounded_flag_replacement(self):
        plan = self.fixture.plan(
            ["expand", "deploydefense", "budgeteconomy", "focusenemy4", "advanceconstruction", "advanceproduction"]
        )
        first = self.controller.dispatch(plan, 101, effective_hash="a" * 64)
        self.assertEqual(set(first["action_domain_windows"]), set(plan.macro_actions))
        self.assertEqual(self.fixture.native["applied_mask"], (1 << 9) | (1 << 8) | (1 << 4))
        self.assertEqual([row["kind"] for row in self.fixture.calls], ["manager", "manager", "focus", "flags"])
        self.controller.dispatch(self.fixture.plan(["deploydefense"]), 102, effective_hash="a" * 64)
        self.assertEqual(self.fixture.native["applied_mask"], 1 << 8)
        self.assertEqual(self.fixture.native["focus"]["phase"], 4)

    def test_five_domains_use_one_original_window_and_duplicate_has_no_new_delivery(self):
        plan = self.fixture.plan(["attackenemy", "budgetarmy", "pauseconstruction", "advanceproduction", "focusenemy5"])
        first = self.controller.dispatch(plan, 101, effective_hash="a" * 64)
        self.assertEqual([row["kind"] for row in self.fixture.calls], ["manager", "manager", "focus", "flags"])
        self.assertEqual([row["absolute"] for row in self.fixture.calls], [2100] * 4)
        self.assertEqual(first["action_domain_windows"]["focusenemy5"]["domain"], "enemy_focus")
        self.assertEqual(first["action_domain_windows"]["focusenemy5"]["end_frame"], 2100)
        self.assertEqual(first, self.controller.dispatch(plan, 102, effective_hash="a" * 64))
        self.assertEqual(len(self.fixture.calls), 4)
        self.assertEqual(self.fixture.journal.unresolved(self.fixture.run), [])

    def test_changed_target_and_omission_have_explicit_focus_children(self):
        for action in ("focusenemy4", "focusenemy5"):
            self.controller.dispatch(self.fixture.plan([action]), 101, effective_hash="a" * 64)
        self.controller.dispatch(self.fixture.plan([]), 102, effective_hash="a" * 64)
        self.assertEqual([row["enemy_player_id"] for row in self.fixture.calls if row["kind"] == "focus"], [4, 5, None])
        self.assertEqual(self.fixture.native["focus"]["phase"], 4)

    def test_partial_unknown_is_preserved_and_never_retried(self):
        self.fail_focus = True
        plan = self.fixture.plan(["attackenemy", "focusenemy4"])
        with self.assertRaisesRegex(ContractError, "outcome_unknown"):
            self.controller.dispatch(plan, 101, effective_hash="a" * 64)
        self.assertTrue(self.controller.delivery_unknown)
        self.assertFalse(any(row["kind"] == "flags" for row in self.fixture.calls))
        count = len(self.fixture.calls)
        with self.assertRaisesRegex(ContractError, "already_claimed"):
            self.controller.dispatch(plan, 102, effective_hash="a" * 64)
        self.assertEqual(len(self.fixture.calls), count)

    def test_priority_feedback_is_adoption_only_and_eliminated_target_is_unavailable(self):
        self.controller.dispatch(self.fixture.plan(["focusenemy4"]), 101, effective_hash="a" * 64)
        frame = self.observe(selector(self.enemies, self.enemies, 4))
        feedback = project_unified_feedback(self.controller.unified_feedback(), game_seconds=frame / 15)
        row = feedback["observations"][0]
        self.assertEqual(row["status"], "native_enemy_priority_observed")
        self.assertTrue(row["component_state_adopted"])
        self.assertFalse(row["mission_success_verified"])
        self.assertFalse(row["active_native_task_observed"])
        self.assertFalse(row["movement_observed"])
        self.controller.last_enemy_focus = selector(self.enemies, (5,))
        self.assertNotIn("focusenemy4", self.controller.available_actions(102))
        self.assertIn("focusenemy5", self.controller.available_actions(102))
        with self.assertRaisesRegex(ContractError, "not_currently_available"):
            self.controller.dispatch(self.fixture.plan(["focusenemy4"]), 102, effective_hash="a" * 64)

    def test_stopped_controller_refuses_new_intents_without_delivery(self):
        self.controller.transport.close = lambda: None
        self.controller.stop()
        with self.assertRaisesRegex(ContractError, "stopped_or_paused"):
            self.controller.dispatch(self.fixture.plan(["budgetarmy"]), 101, effective_hash="a" * 64)
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(self.fixture.journal.commands_for_run(self.fixture.run), [])

    def test_focus_is_separate_from_work_and_requires_native7(self):
        self.assertEqual(split_native7_intents(["attackenemy", "focusenemy5"]), (("attackenemy",), {}, 5))
        with self.assertRaisesRegex(ValueError, "requires_native7"):
            split_intents(["focusenemy4"])
        for actions in (["focusenemy4", "focusenemy5"], ["focusenemy99"], ["produceconscript"]):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                split_native7_intents(actions)
        with self.assertRaisesRegex(ValueError, "conflicting_macro_actions"):
            validate_actions(
                ["focusenemy4", "focusenemy5"], ["focusenemy4", "focusenemy5"], ["focusenemy4", "focusenemy5"]
            )


class AnyEnemyDispatch(NativeDispatch):
    """The same controller with enemies at arbitrary player ids (allies elsewhere)."""

    enemies = (1, 6, 12)

    def test_expansion_and_defense_share_one_bounded_flag_replacement(self):
        plan = self.fixture.plan(["expand", "budgeteconomy", "focusenemy12"])
        first = self.controller.dispatch(plan, 101, effective_hash="a" * 64)
        self.assertEqual(first["action_domain_windows"]["focusenemy12"]["domain"], "enemy_focus")
        self.assertEqual(self.fixture.native["focus"]["priority"][12], 10)

    def test_five_domains_use_one_original_window_and_duplicate_has_no_new_delivery(self):
        plan = self.fixture.plan(["attackenemy", "budgetarmy", "pauseconstruction", "advanceproduction", "focusenemy6"])
        first = self.controller.dispatch(plan, 101, effective_hash="a" * 64)
        self.assertEqual([row["absolute"] for row in self.fixture.calls], [2100] * 4)
        self.assertEqual(first["action_domain_windows"]["focusenemy6"]["end_frame"], 2100)
        self.assertEqual(first, self.controller.dispatch(plan, 102, effective_hash="a" * 64))
        self.assertEqual(len(self.fixture.calls), 4)

    def test_changed_target_and_omission_have_explicit_focus_children(self):
        for action in ("focusenemy1", "focusenemy12"):
            self.controller.dispatch(self.fixture.plan([action]), 101, effective_hash="a" * 64)
        self.controller.dispatch(self.fixture.plan([]), 102, effective_hash="a" * 64)
        self.assertEqual(
            [row["enemy_player_id"] for row in self.fixture.calls if row["kind"] == "focus"], [1, 12, None]
        )

    def test_partial_unknown_is_preserved_and_never_retried(self):
        self.fail_focus = True
        plan = self.fixture.plan(["attackenemy", "focusenemy6"])
        with self.assertRaisesRegex(ContractError, "outcome_unknown"):
            self.controller.dispatch(plan, 101, effective_hash="a" * 64)
        count = len(self.fixture.calls)
        with self.assertRaisesRegex(ContractError, "already_claimed"):
            self.controller.dispatch(plan, 102, effective_hash="a" * 64)
        self.assertEqual(len(self.fixture.calls), count)

    def test_priority_feedback_is_adoption_only_and_eliminated_target_is_unavailable(self):
        self.controller.dispatch(self.fixture.plan(["focusenemy6"]), 101, effective_hash="a" * 64)
        frame = self.observe(selector(self.enemies, self.enemies, 6))
        row = project_unified_feedback(self.controller.unified_feedback(), game_seconds=frame / 15)["observations"][0]
        self.assertEqual(row["status"], "native_enemy_priority_observed")
        self.controller.last_enemy_focus = selector(self.enemies, (1, 12))
        self.assertEqual(
            [a for a in self.controller.available_actions(102) if a.startswith("focus")],
            ["focusenemy1", "focusenemy12"],
        )
        with self.assertRaisesRegex(ContractError, "not_currently_available"):
            self.controller.dispatch(self.fixture.plan(["focusenemy6"]), 102, effective_hash="a" * 64)

    def test_offered_focus_follows_actual_enemies_only(self):
        self.assertEqual(
            [a for a in self.controller.scope.available_actions if a.startswith("focus")],
            ["focusenemy1", "focusenemy6", "focusenemy12"],
        )
        for action in ("focusenemy4", "focusenemy3"):
            with self.subTest(action=action), self.assertRaisesRegex(ContractError, "not_qualified"):
                self.controller.dispatch(self.fixture.plan([action]), 101, effective_hash="a" * 64)
        self.assertEqual(self.fixture.calls, [])

    def test_a_single_enemy_offers_no_focus(self):
        scope = NativeScope(PACKAGE_SHA, tuple(zip(FLAG_ACTIONS, FLAGS)), (), (), opponent_player_ids=(7,))
        self.assertFalse([a for a in scope.available_actions if a.startswith("focus")])


if __name__ == "__main__":
    unittest.main()
