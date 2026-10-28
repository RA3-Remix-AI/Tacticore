"""Apply a bounded commander draft to the existing protected model Profile.

This module does not discover credentials, send a request, or grant execution.
Only personality, traits and model are changed; credential/endpoint identity is
preserved. A constructed backend is not reported as a provider response.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, fields, is_dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Mapping

from .capabilities import CapabilityCatalog
from .contracts import ContractError, integer
from .profiles import EffectiveProfile, normalize_profile

MAX_DRAFT_BYTES = 65536


def load_commander_draft(path: Path, *, max_bytes: int = MAX_DRAFT_BYTES) -> dict:
    integer(max_bytes, 1, MAX_DRAFT_BYTES, "invalid_draft_byte_limit")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ContractError("duplicate_draft_key")
            value[key] = item
        return value
    def constant(_):
        raise ContractError("invalid_draft_number")
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ContractError("commander_draft_too_large")
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
        if not isinstance(value, dict):
            raise ContractError("invalid_commander_draft")
        return value
    except ContractError:
        raise
    except (OSError, ValueError, UnicodeError, RecursionError, TypeError):
        raise ContractError("commander_draft_unavailable_or_invalid") from None


@dataclass(frozen=True)
class AppliedProfile:
    effective: EffectiveProfile
    profile: object = field(repr=False)

    def public(self) -> dict:
        effective = self.effective
        return {"schema_version": 1, "profile_id": effective.profile_id,
                "connection_id": effective.connection_id, "profile_revision": effective.revision,
                "effective_hash": effective.effective_hash, "model": effective.model,
                "personality": effective.personality, "traits_bytes": effective.traits_bytes,
                "traits_sha256": hashlib.sha256(effective.traits.encode("utf-8")).hexdigest(),
                "traits_truncated": False, "axis_support": effective.public()["axis_support"],
                "state": "host_profile_applied", "model_response_received": False,
                "application_scope": "current_host_instance", "behavior_verified": False}


def apply_commander_draft(base_profile, draft: Mapping, *,
                          capability_catalog: CapabilityCatalog | None = None) -> AppliedProfile:
    expected = {"commander_id", "commander_name", "connection_id", "provider", "model", "personality", "traits", "endpoint", "key"}
    if not is_dataclass(base_profile) or {f.name for f in fields(base_profile)} != expected:
        raise ContractError("protected_profile_required")
    if not isinstance(draft, Mapping):
        raise ContractError("invalid_commander_draft")
    if draft.get("profile_id") != base_profile.commander_id:
        raise ContractError("profile_commander_mismatch")
    if draft.get("connection_id") != base_profile.connection_id:
        raise ContractError("profile_connection_mismatch")
    if draft.get("name") != base_profile.commander_name:
        raise ContractError("profile_name_mismatch")
    resolved = dict(draft)
    if not isinstance(resolved.get("model"), str):
        raise ContractError("invalid_model")
    resolved["model"] = resolved["model"].strip() or base_profile.model
    if not isinstance(resolved["model"], str) or not resolved["model"].strip():
        raise ContractError("model_not_resolved")
    effective = normalize_profile(resolved, capability_catalog=capability_catalog)
    profile = replace(base_profile, model=effective.model, personality=effective.personality,
                      traits=effective.traits)
    # These are references from the trusted base Profile, never fields supplied
    # by the client draft or reconstructed from its JSON.
    if profile.endpoint is not base_profile.endpoint or profile.key is not base_profile.key:
        raise ContractError("protected_profile_changed")
    return AppliedProfile(effective, profile)


class AppliedBackend:
    """Transparent accounting wrapper around the existing backend interface."""
    def __init__(self, backend, application: AppliedProfile, *, event_sink: Callable | None = None,
                 transport_mode: str = "provider_transport"):
        if transport_mode not in ("provider_transport", "injected_transport"):
            raise ContractError("invalid_transport_mode")
        self._backend = backend
        self.application = application
        self._event_sink = event_sink
        self.transport_mode = transport_mode
        self._call_sequence = 0
        self._responses_returned = 0
        self._last_stage = "backend_constructed"
        self._network_verified = False
        self._transport_receipt = None
        self._emit("commander_model_backend_constructed", "backend_constructed")

    def _emit(self, event_type, stage, **facts):
        self._last_stage = stage
        payload = {**self.application.public(), "stage": stage, "transport_mode": self.transport_mode,
                   "real_network_verified": self._network_verified, **facts}
        if self._event_sink is not None:
            self._event_sink(event_type, payload)

    def observation(self) -> dict:
        return {**self.application.public(), "stage": self._last_stage,
                "transport_mode": self.transport_mode, "real_network_verified": self._network_verified,
                "transport_receipt": self._transport_receipt,
                "calls_started": self._call_sequence, "responses_returned": self._responses_returned,
                "model_response_received": self._responses_returned > 0}

    @staticmethod
    def _context_fields(context):
        if not isinstance(context, dict):
            return {}
        fields = {}
        if type(context.get("snapshot_id")) is int and context["snapshot_id"] >= 0:
            fields["snapshot_id"] = context["snapshot_id"]
        at = context.get("game_time_seconds")
        if type(at) in (int, float) and math.isfinite(at) and at >= 0:
            fields["based_on_game_time_seconds"] = at
        return fields

    async def _call(self, operation, context):
        self._call_sequence += 1
        sequence = self._call_sequence
        context_fields = self._context_fields(context)
        self._emit("commander_model_call_started", "call_started", call_sequence=sequence, **context_fields)
        try:
            result = await operation()
        except asyncio.CancelledError:
            self._emit("commander_model_call_cancelled", "call_cancelled", call_sequence=sequence, **context_fields)
            raise
        except Exception:
            # No exception string or response body: provider failures can contain
            # request/credential data and must not escape via telemetry.
            self._emit("commander_model_call_failed", "call_failed", call_sequence=sequence, **context_fields)
            raise
        self._responses_returned += 1
        if self.transport_mode == 'provider_transport':
            from tacticore_agent_runtime.factory import NetworkBackend
            if type(self._backend) is NetworkBackend and self._backend._transport is None:
                receipt = self._backend.last_transport_receipt
                if (isinstance(receipt, dict) and receipt.get('source') == 'bounded_provider_transport'
                    and receipt.get('real_network_verified') is True and receipt.get('injected_transport') is False
                    and receipt.get('expected_origin') is True and receipt.get('https') is True
                    and receipt.get('loopback') is False and receipt.get('http_status') == 200
                    and receipt.get('response_complete') is True):
                    self._transport_receipt = dict(receipt)
                    self._network_verified = True
        self._emit("commander_model_response_returned", "response_returned", call_sequence=sequence,
                   model_response_received=True, transport_receipt=self._transport_receipt, **context_fields)
        return result

    async def __call__(self, context):
        return await self._call(lambda: self._backend(context), context)

    async def run(self, request):
        return await self._call(lambda: self._backend.run(request), request.context)

    def __getattr__(self, name):
        # Preserve the original metrics, wire budget, diagnostics and sizing hook.
        return getattr(self._backend, name)


def observe_applied_backend(backend, application: AppliedProfile, *, event_sink=None,
                            transport_mode="provider_transport") -> AppliedBackend:
    return AppliedBackend(backend, application, event_sink=event_sink, transport_mode=transport_mode)


def create_applied_backend(application: AppliedProfile, *, event_sink=None, **factory_options) -> AppliedBackend:
    # model_backend is the repository's normal bootstrap to the unique factory.
    from model_backend import create_backend
    backend = create_backend(application.profile, **factory_options)
    mode = "injected_transport" if factory_options.get("transport") is not None else "provider_transport"
    return observe_applied_backend(backend, application, event_sink=event_sink, transport_mode=mode)
