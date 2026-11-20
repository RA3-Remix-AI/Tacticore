"""Failure telemetry/probe tests; no protected profile loads or networking."""

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "strategy"), str(ROOT / "agent_runtime/src")]
from host_runtime.application import safe_backend_diagnostics, observe_applied_backend, apply_commander_draft
from test_host_runtime_application import profile, draft, context

SECRET = "PRIVATE-ENDPOINT-RAW-RESPONSE-KEY"


class Diagnostics(unittest.IsolatedAsyncioTestCase):
    async def test_success_recomputes_safe_shapes_instead_of_backend_raw_diagnostics(self):
        from fixtures import binding
        from test_macro_policy import macro_snapshot

        ctx = macro_snapshot(["budgeteconomy"]).model_context(binding())

        class Backend:
            last_diagnostics = {"untrusted": SECRET}

            async def __call__(self, _):
                return {"macro_actions": [{"action": "budgeteconomy", SECRET: SECRET}], "macro_production": None}

        events = []
        b = observe_applied_backend(
            Backend(), apply_commander_draft(profile(), draft()), event_sink=lambda k, p: events.append((k, p))
        )
        await b(ctx)
        diag = events[-1][1]["response_diagnostics"]
        self.assertEqual(diag["macro_actions"]["validation_code"], "macro_policy_actions")
        self.assertEqual(diag["macro_actions"]["item_type_counts"], {"object": 1})
        self.assertNotIn(SECRET, json.dumps(events))
        self.assertNotIn("untrusted", diag)

    async def test_failure_projects_only_fixed_codes_and_numeric_counters(self):
        class Failing:
            last_error_code = "input_budget_exceeded"
            metrics = {
                "attempts": 1,
                "timeouts": 0,
                "responses": False,
                "max_request_bytes": 16385,
                "key": SECRET,
                "retries": -1,
            }

            async def __call__(self, _):
                raise ValueError(SECRET)

        events = []
        b = observe_applied_backend(
            Failing(), apply_commander_draft(profile(), draft()), event_sink=lambda k, p: events.append((k, p))
        )
        with self.assertRaises(ValueError):
            await b(context())
        expected = {
            "error_code": "input_budget_exceeded",
            "transport_metrics": {"attempts": 1, "timeouts": 0, "max_request_bytes": 16385},
        }
        self.assertEqual(events[-1][1]["backend_diagnostics"], expected)
        self.assertEqual(b.observation()["failure_diagnostics"], expected)
        self.assertNotIn(SECRET, json.dumps(events))
        self.assertFalse(b.observation()["model_response_received"])

    async def test_unknown_and_malicious_codes_and_metric_values_are_not_exported(self):
        for code in [SECRET, "http_status_999", "http_status_200\n" + SECRET, [], None]:
            d = safe_backend_diagnostics(
                SimpleNamespace(
                    last_error_code=code, metrics={"attempts": True, "responses": 2**60, "max_request_bytes": SECRET}
                )
            )
            self.assertEqual(d, {"error_code": None, "transport_metrics": {}})
        for code in ["http_status_401", "http_status_503", "framework_request_failed"]:
            self.assertEqual(safe_backend_diagnostics(SimpleNamespace(last_error_code=code))["error_code"], code)

    async def test_cancel_keeps_cancellation_semantics_and_no_failure_claim(self):
        class Cancel:
            async def __call__(self, _):
                raise asyncio.CancelledError()

        b = observe_applied_backend(Cancel(), apply_commander_draft(profile(), draft()))
        with self.assertRaises(asyncio.CancelledError):
            await b(context())
        self.assertIsNone(b.observation()["failure_diagnostics"])
        self.assertEqual(b.observation()["stage"], "call_cancelled")


if __name__ == "__main__":
    unittest.main()
