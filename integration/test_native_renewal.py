"""Fresh high-level decisions can renew verified manager leases."""

import copy
from types import SimpleNamespace
import unittest

from host_runtime.native_runtime import NativeScope
from host_runtime.strategic_controller import StrategicController


class NativeRenewal(unittest.TestCase):
    def setUp(self):
        self.plan = SimpleNamespace(macro_actions=("budgetarmy", "advanceproduction"), macro_production=None)
        self.controller = StrategicController.__new__(StrategicController)
        self.controller.scope = NativeScope.__new__(NativeScope)
        self.controller.stopped = False
        self.controller.delivery_unknown = False
        self.controller.current_plan = "previous-plan"
        self.controller.current_actions = self.plan.macro_actions
        self.controller.current_seq = 2
        self.controller.flag_actions = ("budgetarmy",)
        self.controller.last_frame = 1650
        self.controller.last_native = dict(
            native_schema="unified_flags_and_managers_v7",
            phase=1,
            active=0,
            error=0,
            request=2,
            ack=2,
            applied_mask=1,
            flag_phase=1,
            flag_deadline=1950,
            gates=[dict(phase=0), dict(phase=1, requested_enabled=1, deadline_frame=1950)],
        )
        self.controller.action_domain_windows = {
            action: dict(start_frame=1500, end_frame=1950, native_deadline_frame=1950)
            for action in self.plan.macro_actions
        }
        self.controller.effects = {"advanceproduction": dict(component_state_adopted=True, observed_frame=1650)}

    def test_unchanged_observed_gate_can_be_reaffirmed_without_mutating_the_lease(self):
        before = copy.deepcopy(self.controller.last_native)
        self.assertEqual(self.controller.reaffirmable_plan(self.plan, 110), "previous-plan")
        self.assertEqual(self.controller.last_native, before)

    def test_unknown_stale_unobserved_changed_and_unowned_states_cannot_renew(self):
        for change in (
            "unknown",
            "stopped",
            "stale",
            "unobserved",
            "old_effect",
            "wrong_enabled",
            "wrong_mask",
            "expired",
            "foreign_gate",
        ):
            controller = copy.copy(self.controller)
            controller.last_native = copy.deepcopy(self.controller.last_native)
            controller.effects = copy.deepcopy(self.controller.effects)
            if change == "unknown":
                controller.delivery_unknown = True
            if change == "stopped":
                controller.stopped = True
            if change == "stale":
                controller.last_frame = 1600
            if change == "unobserved":
                controller.effects = {}
            if change == "old_effect":
                controller.effects["advanceproduction"]["observed_frame"] = 1647
            if change == "wrong_enabled":
                controller.last_native["gates"][1]["requested_enabled"] = 0
            if change == "wrong_mask":
                controller.last_native["applied_mask"] = 0
            if change == "expired":
                controller.last_native["gates"][1]["deadline_frame"] = 1649
            if change == "foreign_gate":
                controller.last_native["gates"][0] = dict(phase=1)
            with self.subTest(change=change):
                self.assertIsNone(controller.reaffirmable_plan(self.plan, 110))
        changed = SimpleNamespace(macro_actions=("budgetarmy", "pauseproduction"), macro_production=None)
        self.assertIsNone(self.controller.reaffirmable_plan(changed, 110))

    def test_both_observed_gate_domains_can_renew_together(self):
        actions = ("budgetarmy", "pauseconstruction", "advanceproduction")
        self.plan.macro_actions = actions
        self.controller.current_actions = actions
        self.controller.last_native["gates"][0] = dict(phase=1, requested_enabled=0, deadline_frame=1950)
        self.controller.action_domain_windows["pauseconstruction"] = dict(
            start_frame=1500, end_frame=1950, native_deadline_frame=1950
        )
        self.controller.effects["pauseconstruction"] = dict(component_state_adopted=True, observed_frame=1650)
        self.assertEqual(self.controller.reaffirmable_plan(self.plan, 110), "previous-plan")


if __name__ == "__main__":
    unittest.main()
