"""Offline acceptance: real Agent.run, FunctionModel and mocked HTTP transport.

Run with PYTHONPATH=agent_runtime/src:strategy from the repository root.
Never load a real connection library or call an external endpoint.
"""
import asyncio
import json
import os
import unittest
from unittest.mock import patch

from engine import ContractError, Snapshot, StrategyEngine, parse_model_json
from fixtures import COMMANDER, CONNECTION, binding, policy, snapshot
from http_adapter import ChatAdapter, Endpoint, Profile, system_prompt
from tacticore_agent_runtime import LegacyBackend, PolicyRequest, ReplayBackend, ReplayEntry, RuntimeAdapterError, context_digest


def profile(endpoint="http://127.0.0.1:1/v1", provider="自定义"):
    return Profile(COMMANDER, "Offline only", CONNECTION, provider, "fixture-model", 0, "", Endpoint.parse(endpoint), "FAKE-LOCAL-TEST")


def context():
    return Snapshot.from_dict(snapshot()).model_context(binding())


class CoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_passes_exact_context_and_contract_error(self):
        value = context()
        expected = ContractError("fixture_contract")
        async def existing(received):
            self.assertIs(received, value)
            raise expected
        with self.assertRaises(ContractError) as result:
            await LegacyBackend(existing)(value)
        self.assertIs(result.exception, expected)

    async def test_legacy_preserves_host_wire_budget_hooks(self):
        original = ChatAdapter(profile())
        wrapped = LegacyBackend(original)
        self.assertEqual(wrapped.max_input_bytes, original.max_input_bytes)
        self.assertEqual(wrapped.input_size, getattr(original, "input_size", None))

    async def test_real_legacy_chat_adapter_with_local_http_and_engine(self):
        requests = []
        async def serve(reader, writer):
            header = await reader.readuntil(b"\r\n\r\n")
            headers = dict(line.split(":", 1) for line in header.decode().split("\r\n")[1:] if ":" in line)
            body = json.loads(await reader.readexactly(int(headers["Content-Length"])))
            requests.append(body)
            ctx = json.loads(body["messages"][1]["content"])
            response = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(policy(ctx))}}]}).encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + str(len(response)).encode() + b"\r\nConnection: close\r\n\r\n" + response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            original = ChatAdapter(profile(f"http://127.0.0.1:{port}/v1"), max_retries=0)
            result = await StrategyEngine(binding()).decide(snapshot(), LegacyBackend(original))
        self.assertEqual(result.status, "accepted")
        self.assertEqual(len(requests), 1)
        self.assertEqual(original.metrics["attempts"], 1)

    async def test_expired_deadline_and_version_do_not_call_provider(self):
        async def forbidden(_): raise AssertionError("must not run")
        backend = LegacyBackend(forbidden)
        for request, code in [(PolicyRequest(context(), deadline=0), "deadline_exceeded"),
                              (PolicyRequest(context(), protocol_version=2), "protocol_version")]:
            with self.assertRaisesRegex(RuntimeAdapterError, code): await backend.run(request)

    async def test_replay_exact_context_and_no_advance_on_mismatch(self):
        ctx = context()
        backend = ReplayBackend([ReplayEntry(context_digest(ctx), json.dumps(policy(ctx)))], parse_json=parse_model_json)
        wrong = dict(ctx, snapshot_id=999)
        with self.assertRaisesRegex(RuntimeAdapterError, "replay_context_mismatch"): await backend(wrong)
        self.assertEqual(await backend(ctx), policy(ctx))
        with self.assertRaisesRegex(RuntimeAdapterError, "replay_exhausted"): await backend(ctx)

    async def test_replay_preserves_strict_parser_error(self):
        ctx = context()
        backend = ReplayBackend([ReplayEntry(context_digest(ctx), '{"x":1,"x":2}')], parse_json=parse_model_json)
        with self.assertRaisesRegex(ContractError, "duplicate_key"): await backend(ctx)


try:
    import httpx2
    from pydantic_ai import Agent
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
    from tacticore_agent_runtime.pydantic_backend import PydanticBackend, openai_compatible_backend
    FRAMEWORK = True
except ImportError:
    if os.environ.get("TACTICORE_REQUIRE_FRAMEWORK") == "1": raise
    FRAMEWORK = False


@unittest.skipUnless(FRAMEWORK, "install the pinned experimental PydanticAI extra")
class FrameworkTests(unittest.IsolatedAsyncioTestCase):
    def backend(self, function, **kwargs):
        selected = profile()
        return PydanticBackend(FunctionModel(function), parse_json=parse_model_json,
            system_prompt=lambda ctx: system_prompt(selected, ctx), commander_id=COMMANDER, **kwargs)

    def response(self, messages):
        text = next(part.content for message in reversed(messages) for part in message.parts if isinstance(part, UserPromptPart))
        return ModelResponse(parts=[TextPart(json.dumps(policy(json.loads(text))))], finish_reason="stop")

    async def test_real_agent_run_no_tools_history_or_host_execution(self):
        calls = []
        async def fake(messages, info):
            calls.append(messages)
            self.assertEqual(info.function_tools, [])
            self.assertEqual(info.output_tools, [])
            return self.response(messages)
        backend = self.backend(fake)
        engine = StrategyEngine(binding())
        result = await engine.decide(snapshot(), backend)
        self.assertEqual(result.status, "accepted")
        self.assertFalse(engine.public_status()["execution"]["enabled"])
        await backend(context())
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(calls[0]), len(calls[1]))  # no framework conversation memory

    async def test_existing_battle_agent_retains_memory_hold_and_context(self):
        from battle_agent import BattleAgent
        seen = []
        async def fake(messages, info):
            payload = next(part.content for message in reversed(messages) for part in message.parts if isinstance(part, UserPromptPart))
            seen.append(json.loads(payload))
            return self.response(messages)
        backend = self.backend(fake)
        battle = BattleAgent(StrategyEngine(binding()))
        self.assertEqual((await battle.decide(snapshot(), backend)).status, "accepted")
        await battle.decide(snapshot(2, 101), backend)
        self.assertEqual(len(seen), 1)
        self.assertEqual((await battle.decide(snapshot(3, 116), backend)).status, "accepted")
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1]["agent_protocol"], "battle_agent_v1")
        self.assertEqual(seen[1]["working_memory"]["current_strategy"]["production_focus"], "anti_air")
        self.assertEqual(seen[1]["delta"]["since_snapshot_id"], 1)

    async def test_duplicate_json_still_raises_legacy_contract_error(self):
        calls = []
        async def fake(messages, info):
            calls.append(1)
            return ModelResponse(parts=[TextPart('{"stance":"defend","stance":"raid"}')], finish_reason="stop")
        with self.assertRaisesRegex(ContractError, "duplicate_key"): await self.backend(fake)(context())
        self.assertEqual(len(calls), 1)

    async def test_bad_policy_is_rejected_by_host_without_framework_repair(self):
        calls = []
        async def fake(messages, info):
            calls.append(1)
            return ModelResponse(parts=[TextPart(json.dumps(policy(context(), player_id=19)))], finish_reason="stop")
        engine = StrategyEngine(binding())
        result = await engine.decide(snapshot(), self.backend(fake))
        self.assertNotEqual(result.status, "accepted")
        self.assertEqual(engine.metrics["accepted"], 0)
        self.assertEqual(len(calls), 1)

    async def test_host_rejects_snapshot_that_ages_during_framework_call(self):
        engine = StrategyEngine(binding())
        async def fake(messages, info):
            engine.observe(snapshot(2, 112))
            return self.response(messages)
        result = await engine.decide(snapshot(), self.backend(fake))
        self.assertEqual(result.reason_code, "stale_response")
        self.assertEqual(engine.metrics["accepted"], 0)

    async def test_tool_proposal_never_executes_and_cannot_retry(self):
        calls = []
        async def fake(messages, info):
            calls.append(1)
            return ModelResponse(parts=[ToolCallPart("move_unit", {"address": 123})])
        with self.assertRaisesRegex(RuntimeAdapterError, "framework_request_failed"): await self.backend(fake)(context())
        self.assertEqual(len(calls), 1)

    async def test_valid_json_with_truncated_finish_is_not_accepted(self):
        async def fake(messages, info):
            return ModelResponse(parts=[TextPart(json.dumps(policy(context())))], finish_reason="length")
        with self.assertRaises(RuntimeAdapterError): await self.backend(fake)(context())

    async def test_deadline_cancels_actual_framework_run(self):
        cancelled = asyncio.Event()
        loop=asyncio.get_running_loop();origin=loop.time();elapsed=0
        async def fake(messages, info):
            nonlocal elapsed
            # Advance the test clock after the real framework enters its model
            # call. Cold SDK setup is not the behavior under test here.
            elapsed=1
            try: await asyncio.sleep(10)
            finally: cancelled.set()
        with patch.object(loop,'time',side_effect=lambda:origin+elapsed):
            with self.assertRaisesRegex(RuntimeAdapterError, "deadline_exceeded"):
                await self.backend(fake, timeout=.02)(context())
        self.assertTrue(cancelled.is_set())

    async def test_external_cancellation_propagates(self):
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def fake(messages, info):
            started.set()
            try: await asyncio.sleep(10)
            finally: cancelled.set()
        task = asyncio.create_task(self.backend(fake)(context()))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(cancelled.is_set())

    async def test_request_bound_and_commander_guard_before_model(self):
        async def forbidden(messages, info): raise AssertionError("must not run")
        backend = self.backend(forbidden)
        with self.assertRaisesRegex(RuntimeAdapterError, "input_budget_exceeded"):
            await backend(dict(context(), extra="x" * 17000))
        with self.assertRaisesRegex(RuntimeAdapterError, "adapter_commander_mismatch"):
            await backend(dict(context(), commander_id="other"))

    async def test_instrumentation_disabled_even_when_global_default_enabled(self):
        async def fake(messages, info): return self.response(messages)
        old = Agent._instrument_default
        try:
            Agent.instrument_all(True)
            # No instrumented run/model is constructed, even with a process-wide opt-in.
            from unittest.mock import patch
            from pydantic_ai.agent import InstrumentationCap
            with patch.object(InstrumentationCap, "__init__", side_effect=AssertionError("trace forbidden")):
                self.assertEqual(await self.backend(fake)(context()), policy(context()))
        finally: Agent.instrument_all(old)

    async def test_network_factory_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(RuntimeAdapterError, "network_not_enabled"):
            async with openai_compatible_backend(profile(), parse_json=parse_model_json, system_prompt=lambda _: "unused"):
                self.fail("must not yield")

    async def test_deepseek_compatible_wire_is_json_no_tools_no_retry(self):
        calls = []
        async def transport(request):
            calls.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/chat/completions")
            return httpx2.Response(200, json={"id": "fixture", "object": "chat.completion", "created": 1,
                "model": "fixture-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(policy(context()))}}]})
        selected = profile("https://fixture.invalid/v1", "DeepSeek")
        async with openai_compatible_backend(selected, parse_json=parse_model_json,
            system_prompt=lambda ctx: system_prompt(selected, ctx), allow_network=True,
            transport=httpx2.MockTransport(transport)) as backend:
            self.assertEqual(await backend(context()), policy(context()))
        self.assertEqual(len(calls), 1)
        self.assertNotIn("tools", calls[0])
        self.assertEqual(calls[0]["response_format"], {"type": "json_object"})
        self.assertEqual(calls[0]["thinking"], {"type": "disabled"})
        self.assertEqual(calls[0]["max_tokens"], 2048)
        self.assertNotIn("max_completion_tokens", calls[0])

    async def test_http_error_is_one_attempt_and_redacted(self):
        calls = []
        async def transport(request):
            calls.append(1)
            return httpx2.Response(429, json={"error": {"message": "SECRET-SHOULD-NOT-ESCAPE", "type": "rate_limit", "code": "rate_limit"}})
        selected = profile("https://fixture.invalid/v1")
        async with openai_compatible_backend(selected, parse_json=parse_model_json,
            system_prompt=lambda ctx: system_prompt(selected, ctx), allow_network=True,
            transport=httpx2.MockTransport(transport)) as backend:
            with self.assertRaises(RuntimeAdapterError) as caught: await backend(context())
        self.assertEqual(str(caught.exception), "framework_request_failed")
        self.assertEqual(len(calls), 1)

    async def test_redirect_and_oversized_response_do_not_follow_or_retry(self):
        for status, headers, content in [(302, {"location": "https://unexpected.invalid"}, b""),
                                         (200, {}, b"x" * 131073)]:
            calls = []
            async def transport(request):
                calls.append(1)
                return httpx2.Response(status, headers=headers, content=content)
            selected = profile("https://fixture.invalid/v1")
            async with openai_compatible_backend(selected, parse_json=parse_model_json,
                system_prompt=lambda ctx: system_prompt(selected, ctx), allow_network=True,
                transport=httpx2.MockTransport(transport)) as backend:
                with self.assertRaisesRegex(RuntimeAdapterError, "framework_request_failed"):
                    await backend(context())
            self.assertEqual(len(calls), 1)


if __name__ == "__main__": unittest.main()
