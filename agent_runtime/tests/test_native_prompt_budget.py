"""Order-invariant macro prompts through the real SDK and an offline transport.

All inputs are synthetic. No saved connection, game, or external HTTP is used.
"""
import copy
import json
import unittest

import httpx2

from http_adapter import Endpoint, Profile, system_prompt
from macro_policy import public_descriptions
from tacticore_agent_runtime import PolicyRequest, RuntimeAdapterError
from tacticore_agent_runtime import pydantic_backend
from tacticore_agent_runtime.factory import NetworkBackend


COMMANDER = "00000000-0000-4000-8000-000000000001"


def profile(provider="DeepSeek"):
    return Profile(COMMANDER, "Offline budget regression",
                   "00000000-0000-4000-8000-000000000002", provider,
                   "fixture-model", 0, "", Endpoint.parse("https://fixture.invalid/v1"),
                   "FAKE-LOCAL-TEST")


def context():
    return dict(
        commander_id=COMMANDER, session_id="00000000-0000-4000-8000-000000000003",
        player_id=3, snapshot_id=2, game_time_seconds=126.0,
        control_mode="macro_native", allowed_production_focus=["native_baseline"],
        allowed_macro_actions=["scout", "budgeteconomy"],
        macro_policy_catalog=public_descriptions(["scout", "budgeteconomy"]),
        native_delegation={"kind": "native_ai_details_v1"},
        macro_strategy={"fact_catalog": {
            "own.credits": 3000, "capabilities.actions": ["scout", "budgeteconomy"],
            "own.role.infantry": 4,
        }},
    )


def example(prompt):
    return json.loads(prompt.split("\nExample: ", 1)[1].split("\nStyle: ", 1)[0])


class NativePromptBudgetTests(unittest.IsolatedAsyncioTestCase):
    def test_existing_fact_reference_is_stable_under_json_key_sorting(self):
        cases = [
            ({"own.credits": 0, "capabilities.actions": []}, "own.credits"),
            ({"z.known": 1, "a.known": 2, "own.credits": None}, "a.known"),
            ({"z.unknown": None, "a.unknown": None}, "a.unknown"),
            ({}, None),  # Existing empty-catalog shape, not an admissible policy.
        ]
        for facts, ref in cases:
            with self.subTest(facts=facts):
                value = context()
                value["macro_strategy"]["fact_catalog"] = facts
                before = copy.deepcopy(value)
                ordered = json.loads(json.dumps(value, sort_keys=True))
                original_prompt = system_prompt(profile(), value)
                self.assertEqual(original_prompt, system_prompt(profile(), ordered))
                self.assertEqual(example(original_prompt)["macro_strategy"]["public_fact_refs"], [ref])
                self.assertEqual(value, before)

    async def test_near_limit_preparation_and_sdk_send_agree(self):
        for provider in ("DeepSeek", "OpenAI"):
            with self.subTest(provider=provider):
                calls = []

                async def transport(request):
                    calls.append(request.content)
                    self.assertLessEqual(len(request.content), 16384)
                    body = json.loads(request.content)
                    prompt = body["messages"][0]["content"]
                    sent_context = json.loads(body["messages"][1]["content"])
                    self.assertEqual(sent_context, value)
                    self.assertEqual(prompt, system_prompt(selected, value))
                    return httpx2.Response(200, json={
                        "id": "offline-budget", "object": "chat.completion", "created": 1,
                        "model": "fixture-model", "choices": [{"index": 0,
                            "finish_reason": "stop", "message": {"role": "assistant",
                            "content": json.dumps(example(prompt))}}],
                    })

                selected = profile(provider)
                backend = NetworkBackend(selected, timeout=4, max_tokens=2048,
                    max_input_bytes=16384, max_inflight=1, module=pydantic_backend,
                    transport=httpx2.MockTransport(transport))
                value = context()
                value["synthetic_padding"] = ""
                value["synthetic_padding"] = "x" * (16379 - backend.input_size(value))
                before = copy.deepcopy(value)
                self.assertEqual(backend.input_size(value), 16379)
                self.assertEqual(backend.input_size(json.loads(json.dumps(value, sort_keys=True))), 16379)
                result = await backend.run(PolicyRequest(value))
                self.assertEqual(result["macro_actions"], [])
                self.assertEqual(len(calls), 1)
                self.assertEqual(backend.metrics["attempts"], 1)
                self.assertEqual(backend.metrics["responses"], 1)
                self.assertEqual(value, before)

                # Keep the hard limit: an oversized input must never reach HTTP.
                value["synthetic_padding"] += "x" * 6
                self.assertEqual(backend.input_size(value), 16385)
                with self.assertRaisesRegex(RuntimeAdapterError, "input_budget_exceeded"):
                    await backend.run(PolicyRequest(value))
                self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
