"""Default model path migration and explicit rollback, entirely offline."""
import asyncio
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_backends import FRAMEWORK, context, profile
from engine import ContractError, StrategyEngine
from fixtures import COMMANDER, binding, policy, snapshot
from battle_agent import BattleAgent
from tacticore_agent_runtime import LegacyBackend, RuntimeAdapterError
from tacticore_agent_runtime.factory import DEFAULT_BACKEND, NetworkBackend, check_backend_available, create_backend


class SelectionTests(unittest.IsolatedAsyncioTestCase):
    def test_default_is_pydantic_and_legacy_is_explicit(self):
        from service import parser
        self.assertEqual(DEFAULT_BACKEND, "pydantic")
        self.assertEqual(inspect.signature(create_backend).parameters["backend"].default, "pydantic")
        self.assertEqual(parser().parse_args(["--commander", COMMANDER]).model_backend, "pydantic")
        with patch("tacticore_agent_runtime.factory.importlib.import_module", side_effect=ImportError("no sdk")):
            self.assertIsInstance(create_backend(profile(), backend="legacy"), LegacyBackend)
            with self.assertRaisesRegex(RuntimeAdapterError, "pydantic_dependencies_missing_run_agent_runtime_install"):
                create_backend(profile())

    async def test_missing_dependencies_cli_returns_clear_json_without_fallback(self):
        root = Path(__file__).resolve().parents[2]
        process = await asyncio.create_subprocess_exec(sys.executable, "-S", str(root / "strategy/service.py"),
            "--commander", COMMANDER, "--check-profile", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(process.communicate(), 5)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(stderr, b"")
        self.assertEqual(json.loads(stdout)["reason_code"], "pydantic_dependencies_missing_run_agent_runtime_install")


@unittest.skipUnless(FRAMEWORK, "install the pinned PydanticAI dependencies")
class DefaultBackendTests(unittest.IsolatedAsyncioTestCase):
    def response(self, request, *, content=None):
        import httpx2
        ctx = json.loads(json.loads(request.content)["messages"][1]["content"])
        return httpx2.Response(200, json={"id": "offline", "object": "chat.completion", "created": 1,
            "model": "fixture-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": content if content is not None else json.dumps(policy(ctx))}}]})

    async def test_default_factory_two_turns_preserves_host_memory_telemetry_and_close(self):
        import httpx2
        calls, closed = [], []
        async def handler(request):
            calls.append(request)
            self.assertEqual(request.headers["Accept-Encoding"], "identity")
            return self.response(request)
        class Transport(httpx2.MockTransport):
            async def aclose(self): closed.append(True)
        backend = create_backend(profile(), transport=Transport(handler))
        self.assertIsInstance(backend, NetworkBackend)
        battle = BattleAgent(StrategyEngine(binding()))
        self.assertEqual((await battle.decide(snapshot(), backend)).status, "accepted")
        await battle.decide(snapshot(2, 101), backend)
        self.assertEqual((await battle.decide(snapshot(3, 116), backend)).status, "accepted")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(closed), 2)
        self.assertEqual(backend.metrics["attempts"], 2)
        self.assertEqual(backend.metrics["responses"], 2)
        self.assertEqual(backend.metrics["retries"], 0)
        self.assertEqual(backend.metrics["max_request_bytes"], max(len(request.content) for request in calls))
        self.assertIsNone(backend.last_error_code)
        self.assertTrue(backend.last_diagnostics["json_object"])
        second = json.loads(json.loads(calls[1].content)["messages"][1]["content"])
        self.assertEqual(second["working_memory"]["current_strategy"]["production_focus"], "anti_air")
        self.assertFalse(battle.engine.public_status()["execution"]["enabled"])

    async def test_raw_envelope_finish_refusal_and_tools_rejected_before_sdk(self):
        import httpx2
        for mutation in ("missing", "null", "refusal", "tool_calls"):
            calls = []
            async def handler(request):
                calls.append(1)
                body = self.response(request).json()
                choice = body["choices"][0]
                if mutation == "missing": choice.pop("finish_reason")
                elif mutation == "null": choice["finish_reason"] = None
                elif mutation == "refusal": choice["message"]["refusal"] = "refused"
                else: choice["message"]["tool_calls"] = [{"id": "unexpected", "type": "function", "function": {"name": "move_unit", "arguments": "{}"}}]
                return httpx2.Response(200, json=body)
            backend = create_backend(profile(), transport=httpx2.MockTransport(handler))
            with self.subTest(mutation=mutation), self.assertRaisesRegex(RuntimeAdapterError, "framework_request_failed"):
                await backend(context())
            self.assertEqual(len(calls), 1)

    async def test_contract_error_identity_and_diagnostic_code_preserved(self):
        import httpx2
        async def handler(request): return self.response(request, content='{"x":1,"x":2}')
        backend = create_backend(profile(), transport=httpx2.MockTransport(handler))
        with self.assertRaisesRegex(ContractError, "duplicate_key"): await backend(context())
        self.assertEqual(backend.last_error_code, "invalid_policy_json")
        self.assertEqual(backend.metrics["responses"], 0)

    async def test_nonzero_retry_is_explicit_configuration_error(self):
        with self.assertRaisesRegex(RuntimeAdapterError, "pydantic_retry_must_be_zero"):
            create_backend(profile(), http_retries=1)
        self.assertIsInstance(create_backend(profile(), backend="legacy", http_retries=1), LegacyBackend)

    async def test_provider_token_fields_and_estimator_before_compaction(self):
        import httpx2
        for provider in ("OpenAI", "DeepSeek", "自定义"):
            calls = []
            async def handler(request):
                calls.append(json.loads(request.content))
                return self.response(request)
            backend = create_backend(profile(provider=provider), transport=httpx2.MockTransport(handler))
            self.assertGreater(backend.input_size(dict(context(), oversized="x" * 20000)), backend.max_input_bytes)
            await backend(context())
            field = "max_completion_tokens" if provider == "OpenAI" else "max_tokens"
            self.assertEqual(calls[0][field], 2048)


if __name__ == "__main__": unittest.main()
