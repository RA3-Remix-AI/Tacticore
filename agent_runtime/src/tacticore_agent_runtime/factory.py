"""Single production model assembly point. No silent backend substitution."""
from __future__ import annotations
import asyncio
import importlib
import json
import math
import os

from .legacy import LegacyBackend
from .protocol import CallableBackend, PolicyRequest, RuntimeAdapterError, encode_context, within_deadline

DEFAULT_BACKEND = "pydantic"
BACKENDS = ("pydantic", "legacy")


def check_backend_available(backend: str = DEFAULT_BACKEND):
    if backend not in BACKENDS:
        raise RuntimeAdapterError("unknown_model_backend")
    if backend == "pydantic":
        # Host CLIs emit machine-readable JSON, not SDK welcome banners.
        os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
        try:
            importlib.import_module("pydantic_ai.models.openai")
            importlib.import_module("pydantic_ai.providers.openai")
            return importlib.import_module("tacticore_agent_runtime.pydantic_backend")
        except ImportError:
            raise RuntimeAdapterError("pydantic_dependencies_missing_run_agent_runtime_install") from None
    return None


class NetworkBackend(CallableBackend):
    """One owned client per request; close it before returning or on cancellation."""
    backend_name = "pydantic"

    def __init__(self, profile, *, timeout, max_tokens, max_input_bytes, max_inflight, module, transport=None):
        from engine import parse_model_json
        from http_adapter import decode_json, structure_diagnostics, system_prompt
        self._profile = profile
        self._timeout = timeout
        self._max_tokens = max_tokens
        self.max_input_bytes = max_input_bytes
        self._semaphore = asyncio.Semaphore(max_inflight)
        self._module = module
        self._transport = transport
        self._parse = parse_model_json
        self._decode = decode_json
        self._diagnostics = structure_diagnostics
        self._prompt = lambda context: system_prompt(profile, context)
        self.metrics = {"attempts": 0, "retries": 0, "timeouts": 0, "responses": 0, "max_request_bytes": 0}
        self.last_error_code = None
        self.last_diagnostics = None

    def input_size(self, context):
        # Measure an oversized candidate so BattleAgent can compact it; reject
        # only the final request, not the host's pre-compaction estimate.
        encoded = encode_context(context, maximum=None)
        messages = [{"role": "system", "content": self._prompt(context)}, {"role": "user", "content": encoded}]
        return len(json.dumps({"messages": messages}, ensure_ascii=False).encode("utf-8")) + 1024

    async def run(self, request: PolicyRequest):
        self.last_error_code = None
        self.last_diagnostics = None
        before_timeouts = self.metrics["timeouts"]
        async def once():
            async with self._semaphore:
                async with self._module.openai_compatible_backend(self._profile,
                    parse_json=self._parse, system_prompt=self._prompt, decode_completion=self._decode,
                    diagnostics=self._diagnostics, allow_network=True, timeout=self._timeout,
                    max_tokens=self._max_tokens, max_input_bytes=self.max_input_bytes,
                    transport=self._transport) as backend:
                    backend.metrics = self.metrics
                    try:
                        return await backend.run(request)
                    finally:
                        self.last_error_code = backend.last_error_code
                        self.last_diagnostics = backend.last_diagnostics
        try:
            return await within_deadline(request, self._timeout, once)
        except asyncio.CancelledError:
            self.last_error_code = "transport_cancelled"
            raise
        except RuntimeAdapterError as error:
            self.last_error_code = str(error)
            if str(error) == "deadline_exceeded" and self.metrics["timeouts"] == before_timeouts:
                self.metrics["timeouts"] += 1
            raise


def create_backend(profile, *, backend: str = DEFAULT_BACKEND, timeout: float = 12,
                   max_tokens: int = 2048, max_input_bytes: int = 16384,
                   max_inflight: int = 2, http_retries: int = 0, transport=None):
    """Called only by explicit model-service startup, never by a UI render/import."""
    if (type(timeout) not in (int, float) or not math.isfinite(timeout) or not .01 <= timeout <= 120
            or type(max_tokens) is not int or not 256 <= max_tokens <= 4096
            or type(max_input_bytes) is not int or not 4096 <= max_input_bytes <= 32768
            or type(max_inflight) is not int or not 1 <= max_inflight <= 4
            or type(http_retries) is not int or http_retries not in (0, 1)):
        raise RuntimeAdapterError("invalid_model_options")
    module = check_backend_available(backend)
    if backend == "legacy":
        from http_adapter import ChatAdapter, TransportPool
        result = LegacyBackend(ChatAdapter(profile, pool=TransportPool(max_inflight),
            total_timeout=timeout, max_retries=http_retries, max_tokens=max_tokens,
            max_input_bytes=max_input_bytes), timeout=timeout)
        result.backend_name = "legacy"
        return result
    if http_retries:
        raise RuntimeAdapterError("pydantic_retry_must_be_zero")
    return NetworkBackend(profile, timeout=timeout, max_tokens=max_tokens,
        max_input_bytes=max_input_bytes, max_inflight=max_inflight, module=module, transport=transport)
