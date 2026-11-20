"""Real Profile/factory/prompt composition, with exclusively fake transport."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "strategy"))
from http_adapter import Endpoint, Profile, system_prompt
from model_backend import check_backend_available
from engine import Snapshot
import fixtures
from host_runtime.application import (
    apply_commander_draft,
    create_applied_backend,
    load_commander_draft,
    observe_applied_backend,
)
from host_runtime.contracts import ContractError

SECRET = "FAKE-TEST-KEY-NEVER-LOG"


def profile(model="connection-default"):
    return Profile(
        fixtures.COMMANDER,
        "铁锤",
        fixtures.CONNECTION,
        "自定义",
        model,
        0,
        "old traits must disappear",
        Endpoint.parse("http://127.0.0.1:1/v1"),
        SECRET,
    )


def draft(**changes):
    value = dict(
        schema_version=1,
        profile_id=fixtures.COMMANDER,
        name="铁锤",
        revision=2,
        connection_id=fixtures.CONNECTION,
        model="",
        commander_id="custom",
        personality=dict(
            aggression=2,
            risk=1,
            persistence=2,
            punish=3,
            preserve=5,
            deception=1,
            grudge=2,
            adaptability=3,
            bait_awareness=3,
        ),
        voice_note="不要盲目追击。",
    )
    value.update(changes)
    return value


def context():
    return Snapshot.from_dict(fixtures.snapshot()).model_context(fixtures.binding())


class ApplicationContracts(unittest.TestCase):
    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_default_model_resolves_before_effective_hash_and_credentials_are_preserved(self):
        base = profile()
        applied = apply_commander_draft(base, draft())
        self.assertEqual(applied.effective.model, "connection-default")
        self.assertEqual(applied.profile.model, "connection-default")
        self.assertEqual(applied.profile.personality, 1)
        self.assertIn("不要盲目追击。", applied.profile.traits)
        self.assertNotIn("old traits", applied.profile.traits)
        self.assertIs(applied.profile.key, base.key)
        self.assertIs(applied.profile.endpoint, base.endpoint)
        self.assertEqual(applied.profile.commander_name, base.commander_name)
        changed = apply_commander_draft(profile("different-default"), draft())
        self.assertNotEqual(applied.effective.effective_hash, changed.effective.effective_hash)
        override = apply_commander_draft(base, draft(model="explicit-model"))
        self.assertEqual(override.profile.model, "explicit-model")
        self.assertNotIn(SECRET, repr(applied))
        self.assertNotIn(SECRET, json.dumps(applied.public()))

    def test_identity_secret_and_unresolved_model_inputs_are_rejected(self):
        self.assertCode(
            "profile_commander_mismatch",
            lambda: apply_commander_draft(profile(), draft(profile_id=fixtures.CONNECTION)),
        )
        self.assertCode(
            "profile_connection_mismatch",
            lambda: apply_commander_draft(profile(), draft(connection_id=fixtures.COMMANDER)),
        )
        self.assertCode("profile_name_mismatch", lambda: apply_commander_draft(profile(), draft(name="different")))
        self.assertCode("model_not_resolved", lambda: apply_commander_draft(profile(""), draft()))
        for field in ("api_key", "endpoint", "provider", "key", "appliedToHost"):
            self.assertCode(
                "unexpected_fields", lambda: apply_commander_draft(profile(), {**draft(), field: "untrusted"})
            )

    def test_bounded_strict_json_loading_and_original_prompt_contains_effective_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "draft.json"
            path.write_text(json.dumps(draft(), ensure_ascii=False), encoding="utf-8")
            applied = apply_commander_draft(profile(), load_commander_draft(path))
            prompt = system_prompt(applied.profile, context())
            self.assertIn("fortifier", prompt)
            self.assertIn("不要盲目追击。", prompt)
            self.assertNotIn("old traits", prompt)
            self.assertNotIn(SECRET, prompt)
            path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
            self.assertCode("duplicate_draft_key", lambda: load_commander_draft(path))
            path.write_text('{"n": NaN}', encoding="utf-8")
            self.assertCode("invalid_draft_number", lambda: load_commander_draft(path))
            path.write_bytes(b" " * 65537)
            self.assertCode("commander_draft_too_large", lambda: load_commander_draft(path))
            path.write_bytes(b"\xff")
            self.assertCode("commander_draft_unavailable_or_invalid", lambda: load_commander_draft(path))


class BackendApplication(unittest.IsolatedAsyncioTestCase):
    async def test_real_factory_and_sdk_fake_transport_receive_resolved_model_and_full_effective_traits(self):
        import httpx2

        check_backend_available("pydantic")
        calls, events = [], []
        applied = apply_commander_draft(profile(), draft())

        async def handler(request):
            wire = json.loads(request.content)
            calls.append(wire)
            self.assertEqual(wire["model"], applied.effective.model)
            self.assertIn(applied.effective.voice_note, wire["messages"][0]["content"])
            self.assertIn("fortifier", wire["messages"][0]["content"])
            self.assertEqual(request.headers["Authorization"], "Bearer " + SECRET)
            ctx = json.loads(wire["messages"][1]["content"])
            return httpx2.Response(
                200,
                json={
                    "id": "offline",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "connection-default",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": json.dumps(fixtures.policy(ctx))},
                        }
                    ],
                },
            )

        backend = create_applied_backend(
            applied,
            transport=httpx2.MockTransport(handler),
            event_sink=lambda kind, payload: events.append((kind, payload)),
        )
        self.assertEqual(len(calls), 0)
        self.assertFalse(backend.observation()["model_response_received"])
        self.assertEqual([p["stage"] for _, p in events], ["backend_constructed"])
        backend.input_size(context())
        self.assertEqual(len(events), 1)
        result = await backend(context())
        self.assertEqual(result["commander_id"], applied.profile.commander_id)
        self.assertEqual(len(calls), 1)
        self.assertEqual([p["stage"] for _, p in events], ["backend_constructed", "call_started", "response_returned"])
        self.assertTrue(all(p["effective_hash"] == applied.effective.effective_hash for _, p in events))
        self.assertTrue(
            all(p["transport_mode"] == "injected_transport" and not p["real_network_verified"] for _, p in events)
        )
        self.assertEqual(events[-1][1]["snapshot_id"], context()["snapshot_id"])
        self.assertTrue(events[-1][1]["model_response_received"])
        self.assertEqual(backend.metrics["responses"], 1)
        self.assertEqual(backend.observation()["responses_returned"], 1)
        self.assertTrue(backend.observation()["model_response_received"])
        self.assertFalse(backend.observation()["real_network_verified"])
        transport = backend._backend.last_transport_receipt
        self.assertIs(transport["injected_transport"], True)
        self.assertIs(transport["real_network_verified"], False)
        self.assertIs(transport["response_complete"], True)
        self.assertEqual(64, len(transport["request_sha256"]))
        self.assertEqual(64, len(transport["response_sha256"]))
        self.assertNotIn(SECRET, json.dumps(transport))
        self.assertNotIn(SECRET, json.dumps(events))

    async def test_custom_backend_cannot_self_attest_a_real_network_response(self):
        class Forged:
            last_transport_receipt = dict(
                real_network_verified=True,
                source="bounded_provider_transport",
                injected_transport=False,
                expected_origin=True,
                https=True,
                loopback=False,
                http_status=200,
                response_complete=True,
            )

            async def __call__(self, context):
                return fixtures.policy(context)

        backend = observe_applied_backend(Forged(), apply_commander_draft(profile(), draft()))
        await backend(context())
        self.assertTrue(backend.observation()["model_response_received"])
        self.assertFalse(backend.observation()["real_network_verified"])

    async def test_failure_and_cancellation_never_become_model_response_receipts(self):
        events = []

        class Failing:
            metrics = {}
            backend_name = "offline-failure"

            async def __call__(self, _):
                raise ValueError(SECRET)

        backend = observe_applied_backend(
            Failing(),
            apply_commander_draft(profile(), draft()),
            event_sink=lambda kind, payload: events.append((kind, payload)),
            transport_mode="injected_transport",
        )
        with self.assertRaises(ValueError):
            await backend(context())
        self.assertEqual(events[-1][1]["stage"], "call_failed")
        self.assertFalse(any(payload["model_response_received"] for _, payload in events))
        self.assertNotIn(SECRET, json.dumps(events))

        class Cancelled:
            async def __call__(self, _):
                raise asyncio.CancelledError()

        events.clear()
        backend = observe_applied_backend(
            Cancelled(),
            apply_commander_draft(profile(), draft()),
            event_sink=lambda kind, payload: events.append((kind, payload)),
        )
        with self.assertRaises(asyncio.CancelledError):
            await backend(context())
        self.assertEqual(events[-1][1]["stage"], "call_cancelled")
        self.assertFalse(any(payload["model_response_received"] for _, payload in events))


if __name__ == "__main__":
    unittest.main()
