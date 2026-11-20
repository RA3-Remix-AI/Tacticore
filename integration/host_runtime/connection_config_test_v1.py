"""connections.test: one minimal model request with a saved connection's key.

The key is read only inside this process and handed to the agent_runtime
factory; it is never logged, returned or put into an error code.
"""

import asyncio
import json
from pathlib import Path
import sys
import time

from .contracts import ContractError

TEST_TIMEOUT_S = 12
PROBE_PROMPT = 'Connection test. Reply with exactly this JSON object: {"ok": true}'
# A completed HTTP 200 exchange that is merely not a usable game policy still proves the connection works.
ANSWERED_CODES = frozenset(
    {
        "invalid_policy_json",
        "incomplete_model_response",
        "completion_token_limit",
        "incomplete_or_refused_completion",
        "invalid_completion",
    }
)
TIMEOUT_CODES = frozenset(
    {
        "deadline_exceeded",
        "transport_timeout",
        "transport_connect_timeout",
        "transport_read_timeout",
        "transport_write_timeout",
        "transport_pool_timeout",
    }
)
# 400 is how several OpenAI-compatible providers answer an unknown model name; 402 is DeepSeek's "no balance".
HTTP_REASONS = {
    400: "model_not_found",
    401: "authentication_failed",
    402: "rate_limited",
    403: "authentication_failed",
    404: "model_not_found",
    429: "rate_limited",
}


def failure_reason(code):
    """Map a fixed agent_runtime error code to one of the UI's test reasons."""
    if code in TIMEOUT_CODES:
        return "timeout"
    if code == "credential_unavailable":
        return "credentials_unavailable"
    if type(code) is str and code.startswith("http_status_") and code[12:].isdigit():
        return HTTP_REASONS.get(int(code[12:]), "endpoint_unreachable")
    return "endpoint_unreachable"


def model_runtime():
    """The repository's model bootstrap (strategy/model_backend.py), which puts agent_runtime on the path."""
    folder = str(Path(__file__).resolve().parents[2] / "strategy")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import model_backend

    return model_backend


def default_backend_module():
    """The agent_runtime network backend module, or a fixed error when its dependencies are missing."""
    bootstrap = model_runtime()
    try:
        return bootstrap.check_backend_available()
    except bootstrap.RuntimeAdapterError:
        raise ContractError("connection_test_runtime_unavailable") from None


async def _probe(module, profile, transport, timeout):
    from http_adapter import decode_json
    from tacticore_agent_runtime.protocol import PolicyRequest

    async with module.openai_compatible_backend(
        profile,
        parse_json=json.loads,
        system_prompt=lambda _context: PROBE_PROMPT,
        decode_completion=decode_json,
        allow_network=True,
        timeout=timeout,
        max_tokens=256,
        transport=transport,
    ) as backend:
        await backend.run(PolicyRequest({"commander_id": profile.commander_id}))


def _result(reachable, latency_ms, reason_code):
    return dict(reachable=reachable, latency_ms=latency_ms, reason_code=reason_code)


def run_connection_test(connection, key, *, module=None, transport=None, timeout=TEST_TIMEOUT_S, clock=time.monotonic):
    """Return {reachable, latency_ms, reason_code} for one saved connection row of the library."""
    bootstrap = model_runtime()
    from http_adapter import AdapterError, Endpoint, Profile

    try:
        endpoint = Endpoint.parse(connection["base_url"])
    except AdapterError:
        return _result(False, None, "endpoint_unreachable")
    if not key and not endpoint.loopback:
        return _result(False, None, "credentials_unavailable")
    model = connection["default_model"].strip()
    if not model:
        return _result(False, None, "model_not_found")
    module = module if module is not None else default_backend_module()
    ident = connection["id"]
    profile = Profile(ident, "connection-test", ident, connection["provider"], model, 0, "", endpoint, key)
    started = clock()
    code = None
    try:
        asyncio.run(asyncio.wait_for(_probe(module, profile, transport, timeout), timeout + 1))
    except bootstrap.RuntimeAdapterError as error:
        code = error.args[0] if len(error.args) == 1 else "framework_request_failed"
    except TimeoutError:
        code = "deadline_exceeded"
    except Exception:
        code = "framework_request_failed"
    latency = max(0, round((clock() - started) * 1000))
    if code is None or code in ANSWERED_CODES:
        return _result(True, latency, None)
    reason = failure_reason(code)
    return _result(False, None if reason == "timeout" else latency, reason)
