"""Single-request PydanticAI model backend. No tools, history or game access."""
from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
import json
from typing import Callable

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.instrumented import InstrumentedModel
from pydantic_ai.usage import UsageLimits

from .protocol import CallableBackend, PolicyRequest, RuntimeAdapterError, encode_context, within_deadline


class PydanticBackend(CallableBackend):
    max_input_bytes = 16384

    def __init__(self, model: Model, *, parse_json: Callable[[str], dict],
                 system_prompt: Callable[[dict], str], commander_id: str,
                 timeout: float = 12, max_tokens: int = 2048,
                 extra_body: dict | None = None, max_input_bytes: int = 16384,
                 diagnostics: Callable[[dict, dict], dict] | None = None):
        if isinstance(model, InstrumentedModel):
            raise RuntimeAdapterError("instrumented_model_forbidden")
        if type(max_tokens) is not int or not 256 <= max_tokens <= 4096:
            raise RuntimeAdapterError("token_configuration")
        if type(max_input_bytes) is not int or not 4096 <= max_input_bytes <= 32768:
            raise RuntimeAdapterError("input_budget_configuration")
        self.max_input_bytes = max_input_bytes
        self._model = model
        self._parse = parse_json
        self._prompt = system_prompt
        self._commander = commander_id
        self._timeout = timeout
        self._max_tokens = max_tokens
        # This argument is local adapter configuration, never model output.
        self._extra_body = extra_body or {}
        self._diagnostics = diagnostics
        self.metrics = {"attempts": 0, "retries": 0, "timeouts": 0, "responses": 0, "max_request_bytes": 0}
        self.last_error_code = None
        self.last_diagnostics = None
        self.last_transport_receipt = None

    def input_size(self, context: dict) -> int:
        # Existing BattleAgent can compact against this bound before committing
        # context. Reserve framing/model/settings overhead; transport checks the
        # final serialized SDK request independently.
        encoded = encode_context(context, maximum=None)
        prompt = self._prompt(context)
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": encoded}]
        return len(json.dumps({"messages": messages}, ensure_ascii=False).encode("utf-8")) + 1024

    async def run(self, request: PolicyRequest) -> dict:
        self.last_error_code = None
        self.last_diagnostics = None
        self.last_transport_receipt = None
        async def once():
            encoded = encode_context(request.context, self.max_input_bytes)
            context = json.loads(encoded)  # isolate the request from caller mutations
            if context.get("commander_id") != self._commander:
                raise RuntimeAdapterError("adapter_commander_mismatch")
            prompt = self._prompt(context)
            if self.input_size(context) > self.max_input_bytes:
                raise RuntimeAdapterError("input_budget_exceeded")
            # Text output is deliberate: legacy parsing rejects duplicate keys,
            # NaN and unknown shapes without Pydantic coercion or schema drift.
            agent = Agent(self._model, output_type=str, system_prompt=prompt,
                          name="tacticore_policy", retries=0, tools=(), toolsets=())
            # Explicitly overrides any process-wide instrument_all setting.
            agent.instrument = False
            self.metrics["attempts"] += 1
            try:
                result = await agent.run(encoded, infer_name=False,
                    model_settings={"max_tokens": self._max_tokens,
                                    "max_retries": 0, "timeout": self._timeout,
                                    "extra_body": self._extra_body},
                    usage_limits=UsageLimits(request_limit=1, tool_calls_limit=0))
            except Exception:
                # Cancellation (BaseException) propagates. Framework/provider
                # messages may contain a prompt or endpoint; do not expose them.
                raise RuntimeAdapterError("framework_request_failed") from None
            if result.response.finish_reason != "stop":
                raise RuntimeAdapterError("incomplete_model_response")
            try:
                parsed = self._parse(result.output)
            except Exception:
                self.last_error_code = "invalid_policy_json"
                raise
            self.last_diagnostics = self._diagnostics(parsed, context) if self._diagnostics else None
            self.metrics["responses"] += 1
            return parsed
        try:
            return await within_deadline(request, self._timeout, once)
        except asyncio.CancelledError:
            self.last_error_code = "transport_cancelled"
            raise
        except RuntimeAdapterError as error:
            self.last_error_code = str(error)
            if str(error) == "deadline_exceeded": self.metrics["timeouts"] += 1
            raise


@asynccontextmanager
async def openai_compatible_backend(profile, *, parse_json: Callable[[str], dict],
                                     system_prompt: Callable[[dict], str],
                                     allow_network: bool = False, timeout: float = 12,
                                     transport=None, max_tokens: int = 2048,
                                     max_input_bytes: int = 16384,
                                     decode_completion=None, diagnostics=None):
    """Explicit opt-in factory for an already validated legacy Profile.

    Credentials stay in the supplied Profile/client. No environment credential
    discovery, tracing exporter, tools or provider retry are enabled here.
    `transport` exists for trusted test injection, not a model/UI-controlled field.
    """
    if not allow_network:
        raise RuntimeAdapterError("network_not_enabled")
    import httpx2
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.profiles.openai import OpenAIModelProfile
    from pydantic_ai.providers.openai import OpenAIProvider
    if decode_completion is None:
        # The production factory injects this explicitly. Standalone callers
        # must run alongside the repository's existing contract modules.
        from http_adapter import decode_json as decode_completion

    endpoint = profile.endpoint
    if not profile.key and not endpoint.loopback:
        raise RuntimeAdapterError("credential_unavailable")
    if not endpoint.path.endswith("/chat/completions"):
        raise RuntimeAdapterError("endpoint_not_chat_completions")
    if not endpoint.tls and not endpoint.loopback:
        raise RuntimeAdapterError("endpoint_requires_tls")
    host = f"[{endpoint.host}]" if ":" in endpoint.host else endpoint.host
    base = f"{'https' if endpoint.tls else 'http'}://{host}:{endpoint.port}{endpoint.path[:-len('/chat/completions')]}"

    class BoundedStream(httpx2.AsyncByteStream):
        def __init__(self, stream): self.stream = stream
        async def __aiter__(self):
            total = 0
            async for chunk in self.stream:
                total += len(chunk)
                if total > 131072:
                    raise RuntimeAdapterError("provider_response_too_large")
                yield chunk
        async def aclose(self): await self.stream.aclose()

    class BoundedTransport(httpx2.AsyncBaseTransport):
        def __init__(self): self.inner = transport if transport is not None else httpx2.AsyncHTTPTransport(retries=0)
        async def handle_async_request(self, request):
            request_body = await request.aread()
            request_bytes = len(request_body)
            backend.metrics["max_request_bytes"] = max(backend.metrics["max_request_bytes"], request_bytes)
            if request_bytes > max_input_bytes:
                raise RuntimeAdapterError("input_budget_exceeded")
            response = await self.inner.handle_async_request(request)
            length = response.headers.get("content-length", "")
            if (response.headers.get("content-encoding", "identity").lower() != "identity"
                    or (length.isdigit() and int(length) > 131072)):
                await response.aclose()
                raise RuntimeAdapterError("provider_response_bounds")
            response.stream = BoundedStream(response.stream)
            try:
                raw = await response.aread()
                if len(raw) > 131072:
                    raise RuntimeAdapterError("provider_response_bounds")
                if response.status_code != 200:
                    raise RuntimeAdapterError("provider_http_status")
                body = decode_completion(raw, 131072)
                choices = body.get("choices") if isinstance(body, dict) else None
                if not isinstance(choices, list) or not 1 <= len(choices) <= 16 or not isinstance(choices[0], dict):
                    raise RuntimeAdapterError("invalid_completion")
                choice = choices[0]
                message = choice.get("message")
                # SDK normalization can turn absent/null finish_reason into stop;
                # preserve the previous raw-envelope gate before normalization.
                if choice.get("finish_reason") != "stop" or not isinstance(message, dict) or message.get("refusal") or message.get("tool_calls"):
                    raise RuntimeAdapterError("incomplete_or_refused_completion")
                if not isinstance(message.get("content"), str) or not message["content"].strip():
                    raise RuntimeAdapterError("invalid_completion")
                expected_origin = (request.url.scheme == ('https' if endpoint.tls else 'http')
                    and request.url.host.lower() == endpoint.host.lower()
                    and (request.url.port or (443 if endpoint.tls else 80)) == endpoint.port
                    and request.url.path == endpoint.path and not request.url.query)
                # Only the owned default network transport can attest HTTPS.
                # Hash body bytes; never persist bodies, headers or credentials.
                backend.last_transport_receipt = dict(schema_version=1,source='bounded_provider_transport',
                    injected_transport=transport is not None,expected_origin=expected_origin,
                    https=endpoint.tls,loopback=endpoint.loopback,http_status=response.status_code,
                    request_bytes=request_bytes,response_bytes=len(raw),
                    request_sha256=hashlib.sha256(request_body).hexdigest(),response_sha256=hashlib.sha256(raw).hexdigest(),
                    response_complete=True,real_network_verified=transport is None and expected_origin and endpoint.tls and not endpoint.loopback)
            except BaseException:
                await response.aclose()
                raise
            return response
        async def aclose(self): await self.inner.aclose()

    async with httpx2.AsyncClient(transport=BoundedTransport(), follow_redirects=False,
                                 trust_env=False, timeout=timeout,
                                 headers={"Accept-Encoding": "identity"}) as http:
        # The outer scope owns this HTTP client; avoid closing its transport twice.
        client = AsyncOpenAI(api_key=profile.key or "local-no-key", base_url=base,
                             max_retries=0, timeout=timeout, http_client=http)
        model = OpenAIChatModel(profile.model, provider=OpenAIProvider(openai_client=client),
            profile=OpenAIModelProfile(openai_chat_supports_max_completion_tokens=profile.provider == "OpenAI"))
        body = {"response_format": {"type": "json_object"}}
        if profile.provider == "DeepSeek": body["thinking"] = {"type": "disabled"}
        backend = PydanticBackend(model, parse_json=parse_json, system_prompt=system_prompt,
                              commander_id=profile.commander_id, timeout=timeout, extra_body=body,
                              max_tokens=max_tokens, max_input_bytes=max_input_bytes, diagnostics=diagnostics)
        yield backend
