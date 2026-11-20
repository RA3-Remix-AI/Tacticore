"""Model request audit checks; no game process or provider is opened."""

import json
import unittest

from .contracts import ContractError
from .macro_policy_runtime import MacroRequestAudit


class MacroRequestAuditTests(unittest.IsolatedAsyncioTestCase):
    def test_own_budget_weights_reach_context_with_bounded_values_and_no_payment_claim(self):
        from .macro_policy_runtime import ACCOUNTS

        shares = dict(zip(ACCOUNTS, [0, 0, 0.849999964, 0.049999997, 0, 0.100000024]))
        feedback = dict(
            status="native_budget_pending",
            selected_policy="budgetarmy",
            actions=["budgetarmy"],
            observed_frame=1500,
            native_effect_verified=False,
            native_account_shares=shares,
            address="PRIVATE",
        )
        audit = MacroRequestAudit(None, lambda *a, **k: None, feedback_supplier=lambda: feedback)
        result = audit.prepare(dict(game_time_seconds=100.0, working_memory={}))["macro_execution_feedback"]
        self.assertEqual(result["native_account_shares"], dict(zip(ACCOUNTS, [0, 0, 0.85, 0.05, 0, 0.1])))
        self.assertFalse(result["payment_verified"])
        self.assertFalse(result["native_effect_verified"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        for field, value in [("investment", float("nan")), ("production", 1.1), ("technology", True)]:
            bad = dict(shares)
            bad[field] = value
            feedback["native_account_shares"] = bad
            with self.assertRaisesRegex(ContractError, "account_shares_invalid"):
                audit.prepare(dict(game_time_seconds=100.0, working_memory={}))
        feedback["native_account_shares"] = dict(shares, extra=0)
        with self.assertRaisesRegex(ContractError, "account_shares_invalid"):
            audit.prepare(dict(game_time_seconds=100.0, working_memory={}))

    async def test_latest_feedback_survives_compacted_memory_and_exact_audit(self):
        events = []
        seen = []

        class Backend:
            def input_size(self, value):
                return len(json.dumps(value))

            async def __call__(self, value):
                seen.append(value)
                return {}

        feedback = dict(
            status="native_budget_adopted",
            selected_policy="budgetarmy",
            actions=["budgetarmy"],
            observed_frame=1501,
            native_effect_verified=True,
            address="private pointer",
            production_id=765,
        )
        backend = Backend()
        audit = MacroRequestAudit(
            backend, lambda kind, **facts: events.append(facts), feedback_supplier=lambda: feedback
        )
        context = dict(
            control_mode="macro_native", game_time_seconds=100.0, working_memory=dict(recent_execution_feedback=[])
        )
        expected = audit.prepare(context)
        self.assertEqual(audit.input_size(context), backend.input_size(expected))
        await audit(context)
        self.assertEqual(seen[0], events[0]["context"])
        self.assertEqual(seen[0], expected)
        self.assertNotIn("macro_execution_feedback", context)
        self.assertEqual(seen[0]["macro_execution_feedback"]["status"], "native_budget_adopted")
        self.assertNotIn("private pointer", json.dumps(seen))
        self.assertNotIn("765", json.dumps(seen))

    async def test_stale_feedback_cannot_be_substituted_into_new_request(self):
        calls = []

        async def backend(context):
            calls.append(context)

        feedback = dict(
            status="native_budget_adopted",
            selected_policy="budgetarmy",
            actions=["budgetarmy"],
            observed_frame=1400,
            native_effect_verified=True,
        )
        audit = MacroRequestAudit(backend, lambda *a, **k: None, feedback_supplier=lambda: feedback)
        with self.assertRaisesRegex(ContractError, "invalid_or_stale"):
            await audit(dict(control_mode="macro_native", game_time_seconds=100.0))
        self.assertEqual(calls, [])

    async def test_exact_context_and_backend_sizing_preserved(self):
        events = []
        seen = []

        class Backend:
            max_input_bytes = 8192

            def input_size(self, value):
                return len(json.dumps(value))

            async def __call__(self, value):
                seen.append(value)
                return {"policy": "synthetic"}

        backend = Backend()
        audit = MacroRequestAudit(backend, lambda kind, **facts: events.append(facts))
        context = {
            "control_mode": "macro_native",
            "working_memory": {
                "recent_execution_feedback": [{"status": "native_budget_adopted", "selected_policy": "budgetarmy"}]
            },
        }
        self.assertEqual(await audit(context), {"policy": "synthetic"})
        self.assertIs(seen[0], context)
        self.assertEqual(events[0]["context"], context)
        self.assertEqual(len(events[0]["context_sha256"]), 64)
        self.assertEqual(audit.input_size(context), backend.input_size(context))
        self.assertEqual(audit.max_input_bytes, 8192)
        self.assertNotIn("real_network_verified", events[0])

    async def test_non_macro_context_cannot_be_sent(self):
        calls = []

        async def backend(context):
            calls.append(context)

        audit = MacroRequestAudit(backend, lambda *a, **k: None)
        with self.assertRaisesRegex(ContractError, "audit_mode"):
            await audit({"control_mode": "micro"})
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
