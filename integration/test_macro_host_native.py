"""The macro Host on the one native runtime: admission, dispatch outcomes, results.

Artificial controller/transport; no Game, native call or provider request.
"""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid

from macro_host import MacroHost, native_transport_config
from host_runtime.contracts import ContractError
from host_runtime.native_runtime import NativeScope
from host_runtime.native_runtime_contract import FIELD_KIND, FLAG_ACTIONS, FLAGS, PACKAGE_SHA


def scope(**changes):
    return NativeScope(
        PACKAGE_SHA, tuple(zip(FLAG_ACTIONS, FLAGS)), (), (), runtime_manifest_sha256="a" * 64, **changes
    )


def manifest(**changes):
    return dict(
        dict(
            kind=FIELD_KIND,
            protocol_version=7,
            package_sha256=PACKAGE_SHA,
            admission_ready=True,
            compile_only=False,
            flags=list(FLAGS),
        ),
        **changes,
    )


class TransportConfig(unittest.TestCase):
    def test_only_the_attachable_native_build_for_this_scope_is_admitted(self):
        config = native_transport_config(scope(), manifest())
        self.assertEqual(config["protocol_version"], 7)
        self.assertTrue(config["client_path"].endswith("native_transport.py"))
        for change in (
            dict(kind="portable_strategic_native7_offline_candidate"),
            dict(protocol_version=6),
            dict(package_sha256="b" * 64),
            dict(admission_ready=False),
            dict(compile_only=True),
            dict(flags=list(FLAGS[:-1])),
        ):
            with self.subTest(change=change), self.assertRaisesRegex(ContractError, "protocol_mismatch"):
                native_transport_config(scope(), manifest(**change))
        with self.assertRaisesRegex(ContractError, "protocol_mismatch"):
            native_transport_config(SimpleNamespace(), manifest())
        with self.assertRaisesRegex(ContractError, "wall_bound"):
            native_transport_config(scope(), manifest(), 5)


class HostDispatch(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.host = host = MacroHost.__new__(MacroHost)
        host.output = Path(temporary.name)
        host.events = []
        host.event = lambda kind, **facts: host.events.append(dict(kind=kind, **facts))
        host.latest = dict(paused=False, game_time_seconds=100.0)
        host.expected_hash = "b" * 64
        host.strategy_runtime = None
        host.prepared_macro_commands = {}
        self.calls = []

    def plan(self, actions=("budgetarmy",), expires=140.0):
        value = SimpleNamespace(
            plan_id=str(uuid.uuid4()),
            macro_actions=tuple(actions),
            macro_production=None,
            production_focus="native_baseline",
            tactical_tasks=(),
            runtime_task=None,
            snapshot_id=1,
            expires_at_game_seconds=expires,
        )
        value.public = lambda: dict(
            macro_actions=list(value.macro_actions),
            plan_id=value.plan_id,
            production_focus="native_baseline",
            macro_production=None,
        )
        return value

    def controller(self, error=None):
        def dispatch(plan, at, *, effective_hash, paused=False):
            self.calls.append(plan.plan_id)
            if error:
                raise ContractError(error)
            return dict(command_id=plan.plan_id, seq=1)

        self.host.controller = SimpleNamespace(dispatch=dispatch)

    def test_accepted_plan_reaches_the_controller_once(self):
        self.controller()
        plan = self.plan()
        self.assertTrue(self.host.dispatch_plan(plan))
        self.assertEqual(self.calls, [plan.plan_id])
        self.assertEqual(self.host.events[-1]["kind"], "plan_applied")

    def test_expired_or_paused_plan_is_never_delivered(self):
        self.controller()
        self.assertFalse(self.host.dispatch_plan(self.plan(expires=90.0)))
        self.host.latest["paused"] = True
        self.assertFalse(self.host.dispatch_plan(self.plan()))
        self.assertEqual(self.calls, [])

    def test_refusals_before_delivery_are_reported_not_faulted(self):
        for code in ("macro_plan_expired_before_native_dispatch", "macro_action_not_currently_available"):
            self.controller(code)
            with self.subTest(code=code):
                self.assertFalse(self.host.dispatch_plan(self.plan()))
                self.assertEqual(self.host.events[-1]["reason_code"], code)

    def test_unknown_delivery_faults_the_host_instead_of_retrying(self):
        self.controller("macro_dispatch_outcome_unknown")
        with self.assertRaisesRegex(ContractError, "outcome_unknown"):
            self.host.dispatch_plan(self.plan())
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(self.host.pending_dispatch)


class HostResult(unittest.TestCase):
    def host(self, attached):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        host = MacroHost.__new__(MacroHost)
        host.output = Path(temporary.name)
        host.events = []
        host.event = lambda kind, **facts: host.events.append(dict(kind=kind, **facts))
        host.native_transport_attached = attached
        host.transport = object() if attached else None
        host.sampler = SimpleNamespace(state=dict(simulation_frame=0))
        host.stopping = lambda: False
        return host

    def test_native_result_is_a_candidate_only_with_an_attached_transport(self):
        host = self.host(True)
        host.record_run_exception(ContractError("macro_native_result_candidate"))
        self.assertEqual((host.phase, host.reason), ("result_candidate", "native_result_requires_visual_confirmation"))
        self.assertTrue((host.output / "result-native-state.json").is_file())
        host = self.host(False)
        host.record_run_exception(ContractError("macro_native_result_candidate"))
        self.assertEqual((host.phase, host.reason), ("fault", "macro_native_result_candidate"))

    def test_other_failures_fault_with_their_reason(self):
        host = self.host(True)
        host.record_run_exception(ContractError("macro_observation_unstable"))
        self.assertEqual((host.phase, host.reason), ("fault", "macro_observation_unstable"))
        host.record_run_exception(RuntimeError("private detail"))
        self.assertEqual(host.reason, "macro_host_failed")
        self.assertNotIn("private detail", json.dumps(host.events))


class HostControl(unittest.TestCase):
    def test_offered_actions_follow_the_scope_the_controller_and_pause(self):
        host = MacroHost.__new__(MacroHost)
        host.strategic_only = True
        current = scope(opponent_player_ids=(4, 6))
        host.sampler = SimpleNamespace(scope=current)
        host.controller = SimpleNamespace(available_actions=lambda at: current.available_actions)
        host.latest = dict(paused=False)
        host.update_macro_control(1.0)
        control = host.latest["macro_control"]
        self.assertIn("focusenemy6", control["available_actions"])
        self.assertEqual(control["intent_contract"], current.intent_contract)
        host.latest = dict(paused=True)
        host.update_macro_control(1.0)
        self.assertEqual(host.latest["macro_control"]["available_actions"], [])


if __name__ == "__main__":
    unittest.main()
