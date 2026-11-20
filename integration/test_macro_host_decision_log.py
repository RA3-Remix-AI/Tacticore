"""MacroHost -> decisions.jsonl wiring with the real audit, engine and controller.

Artificial native transport and model; no game, network or credentials.
"""

import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for folder in ("strategy", "integration"):
    if str(ROOT / folder) not in sys.path:
        sys.path.insert(0, str(ROOT / folder))

import test_delegation_boundary as base  # noqa: E402
from host_runtime.decision_log import read_decisions, read_run_log  # noqa: E402
from host_runtime.macro_policy_runtime import MacroRequestAudit  # noqa: E402
from macro_host import MacroHost  # noqa: E402
import prompt_versions  # noqa: E402


class HostDecisionLogTests(unittest.TestCase):
    def setUp(self):
        self.case = base.RoutingTests(methodName="runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def host_with_log(self):
        host = self.case.host()
        host.session = dict(scenario=dict(map_id="map_mp_2_feasel6", opponent_difficulty="brutal"))
        host.profile = dict(provider="DeepSeek", effective=dict(model="fixture-model"))
        host.backend = SimpleNamespace(last_response=None)
        with patch.dict(os.environ, {prompt_versions.ENVIRONMENT_VARIABLE: "v1"}):
            host.decision_log = host.open_decision_log()
        return host

    def decide_through(self, host, changes=None):
        class Model:
            def input_size(self, context):
                return 1000

            async def __call__(self, context):
                result = base.model_policy(context)
                result.update(changes or {})
                return result

        audit = MacroRequestAudit(Model(), host.event, strategic_only=True)
        decision = asyncio.run(self.case.agent.decide(self.case.view, audit))
        host.decision_log.decided(decision)
        return decision

    def test_accepted_plan_dispatched_by_the_host_is_logged_as_applied(self):
        host = self.host_with_log()
        decision = self.decide_through(host, {"reasoning": "Budget army before their attack lands."})
        self.assertEqual(decision.status, "accepted", decision.reason_code)
        self.assertTrue(host.dispatch_plan(decision.plan))
        log = read_run_log(host.output)
        self.assertEqual(log["run"]["prompt_version"], "v1")
        self.assertEqual(log["run"]["map_id"], "map_mp_2_feasel6")
        record = log["decisions"][0]
        self.assertEqual(record["outcome"]["status"], "applied")
        self.assertEqual(record["decision"]["intents"], ["budgetarmy"])
        self.assertEqual(record["decision"]["reasoning"], "Budget army before their attack lands.")
        self.assertEqual(record["situation"]["own"]["credits"], 4000)
        self.assertEqual(record["prompt_version"], "v1")
        self.assertEqual(record["model"]["provider"], "DeepSeek")

    def test_host_refusal_is_logged_with_its_reason(self):
        host = self.host_with_log()
        decision = self.decide_through(host, {"macro_actions": ["producebullfrog"]})
        self.assertEqual(decision.status, "local_fallback")
        record = read_decisions(host.output)[0]
        self.assertEqual(record["outcome"]["status"], "rejected")
        self.assertEqual(record["outcome"]["reason_code"], "strategic_boundary_detailed_action_refused")
        self.assertFalse(record["outcome"]["native_accepted"])

    def test_host_without_a_log_still_records_events(self):
        host = self.case.host()
        host.event("macro_startup_stage", stage="test")
        self.assertTrue((host.output / "host-events.jsonl").exists())
        self.assertFalse((host.output / "decisions.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
