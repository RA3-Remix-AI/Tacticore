"""connections.test with fake credentials and a fake model transport; no real endpoint is ever called."""

from contextlib import asynccontextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from host_runtime.connection_config_schema_v1 import OPERATIONS
from host_runtime.connection_config_service_v1 import ConnectionConfigServiceV1
from host_runtime.connection_config_test_v1 import failure_reason, model_runtime, run_connection_test
from host_runtime.profile_store import ProfileStore
from test_host_runtime_profile_store import CONNECTION, library

FAKE_KEY = "FAKE-ONLY-CONNECTION-TEST-KEY-12345"
HTTPS = dict(
    id=CONNECTION,
    name="Remote",
    provider="DeepSeek",
    base_url="https://api.invalid/v1",
    remember_key=True,
    default_model="fixture-model",
)
RuntimeAdapterError = model_runtime().RuntimeAdapterError


class FakeCredentials:
    def protect(self, value):
        return b"fake:" + value.encode()

    def unprotect(self, raw):
        return raw.decode()[len("fake:") :]


class FakeBackendModule:
    """Stands in for agent_runtime's pydantic backend module; records the profile it was given."""

    def __init__(self, error=None, answer=None):
        self.error, self.answer, self.profiles, self.timeouts = error, answer or {"ok": True}, [], []

    @asynccontextmanager
    async def openai_compatible_backend(self, profile, *, timeout, allow_network, max_tokens, transport, **_):
        self.profiles.append(profile)
        self.timeouts.append(timeout)
        assert allow_network is True and max_tokens == 256

        class Backend:
            async def run(inner, request):
                assert request.context == {"commander_id": profile.commander_id}
                if self.error:
                    raise RuntimeAdapterError(self.error)
                return self.answer

        yield Backend()


def ticking_clock():
    values = iter([10.0, 10.25])
    return lambda: next(values)


class ReasonMappingTests(unittest.TestCase):
    def test_runtime_codes_map_to_the_six_ui_reasons(self):
        expected = {
            "http_status_401": "authentication_failed",
            "http_status_403": "authentication_failed",
            "http_status_404": "model_not_found",
            "http_status_400": "model_not_found",
            "http_status_429": "rate_limited",
            "http_status_402": "rate_limited",
            "http_status_503": "endpoint_unreachable",
            "transport_connect_failed": "endpoint_unreachable",
            "endpoint_requires_tls": "endpoint_unreachable",
            "transport_read_timeout": "timeout",
            "deadline_exceeded": "timeout",
            "credential_unavailable": "credentials_unavailable",
            "framework_request_failed": "endpoint_unreachable",
        }
        for code, reason in expected.items():
            self.assertEqual(failure_reason(code), reason, code)


class RunConnectionTestTests(unittest.TestCase):
    def test_success_reports_latency_and_never_returns_the_key(self):
        module = FakeBackendModule()
        result = run_connection_test(HTTPS, FAKE_KEY, module=module, clock=ticking_clock())
        self.assertEqual(result, dict(reachable=True, latency_ms=250, reason_code=None))
        self.assertEqual(module.profiles[0].key, FAKE_KEY)
        self.assertEqual(module.profiles[0].model, "fixture-model")
        self.assertEqual(module.profiles[0].endpoint.path, "/v1/chat/completions")
        self.assertLessEqual(module.timeouts[0], 15)
        self.assertNotIn(FAKE_KEY, json.dumps(result))

    def test_a_completed_answer_that_is_not_a_policy_still_counts_as_reachable(self):
        result = run_connection_test(HTTPS, FAKE_KEY, module=FakeBackendModule("incomplete_model_response"))
        self.assertTrue(result["reachable"])

    def test_provider_failures_are_mapped(self):
        for code, reason in (("http_status_401", "authentication_failed"), ("transport_connect_timeout", "timeout")):
            result = run_connection_test(HTTPS, FAKE_KEY, module=FakeBackendModule(code), clock=ticking_clock())
            self.assertFalse(result["reachable"])
            self.assertEqual(result["reason_code"], reason)

    def test_missing_key_or_model_fails_before_any_request(self):
        unused = object()  # any attribute access would raise
        self.assertEqual(run_connection_test(HTTPS, "", module=unused)["reason_code"], "credentials_unavailable")
        empty_model = dict(HTTPS, default_model="  ")
        self.assertEqual(run_connection_test(empty_model, FAKE_KEY, module=unused)["reason_code"], "model_not_found")

    @unittest.skipUnless(
        importlib.util.find_spec("httpx2") and importlib.util.find_spec("pydantic_ai"), "agent runtime not installed"
    )
    def test_actual_runtime_with_a_mock_transport(self):
        import httpx2
        from host_runtime.connection_config_test_v1 import default_backend_module

        seen = []

        def reply(status, content='{"ok": true}'):
            def handler(request):
                seen.append(request.headers.get("authorization"))
                body = {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant"}}]}
                body["choices"][0]["message"]["content"] = content
                body.update(id="x", object="chat.completion", created=1, model="fixture-model")
                return httpx2.Response(status, json=body if status == 200 else {"error": "no"})

            return httpx2.MockTransport(handler)

        module = default_backend_module()
        ok = run_connection_test(HTTPS, FAKE_KEY, module=module, transport=reply(200))
        self.assertTrue(ok["reachable"], ok)
        denied = run_connection_test(HTTPS, FAKE_KEY, module=module, transport=reply(401))
        self.assertEqual(denied["reason_code"], "authentication_failed")
        self.assertEqual(seen, ["Bearer " + FAKE_KEY] * 2)


class ServiceEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="connection-test-v1-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        document = library()
        document["connections"][0].update(HTTPS)
        self.lib = root / "library.v2.json"
        self.lib.write_text(json.dumps(document), encoding="utf8")
        (root / "secrets").mkdir()
        (root / "secrets" / (CONNECTION + ".dpapi")).write_bytes(FakeCredentials().protect(FAKE_KEY))
        self.store = ProfileStore(self.lib, root / "state")
        self.addCleanup(self.store.close)
        self.calls = []

        def fake_test(connection, key):
            self.calls.append((connection["id"], key))
            return dict(reachable=False, latency_ms=None, reason_code="timeout")

        self.service = ConnectionConfigServiceV1(
            self.store, stopped_guard=lambda: True, credentials=FakeCredentials(), connection_test=fake_test
        )
        self.addCleanup(self.service.close)

    def invoke(self, args):
        request = dict(schema_version=1, request_id=str(uuid.uuid4()), operation="connections.test", args=args)
        return self.service.handle(request)

    def test_saved_key_is_used_but_not_returned(self):
        self.assertIn("connections.test", OPERATIONS)
        reply = self.invoke({"connection_id": CONNECTION})
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"], dict(reachable=False, latency_ms=None, reason_code="timeout"))
        self.assertEqual(self.calls, [(CONNECTION, FAKE_KEY)])
        self.assertNotIn(FAKE_KEY, json.dumps(reply))

    def test_unknown_connection_and_extra_fields_are_refused(self):
        missing = self.invoke({"connection_id": str(uuid.uuid4())})
        self.assertEqual(missing["error"]["code"], "connection_config_connection_missing")
        extra = self.invoke({"connection_id": CONNECTION, "api_key": FAKE_KEY})
        self.assertEqual(extra["error"]["code"], "unexpected_fields")
        self.assertNotIn(FAKE_KEY, json.dumps(extra))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
