"""Read-only desktop admission and terminal release checks for the native macro host."""

import hashlib
from pathlib import Path

from .contracts import ContractError, SessionBinding, content_hash
from .macro_live import MacroSampler, ROOT
from .macro_bundle import digest


def observe(registration, profile_id, state_dir):
    return _observed_session(registration, profile_id)[:4]


def _observed_session(registration, profile_id):
    from .macro_policy_runtime import COMMANDER

    if profile_id != COMMANDER:
        raise ContractError("session_mismatch")
    sampler = MacroSampler(registration.session_path, registration.macro_bundle)
    try:
        raw = sampler.collect()
        session = sampler.session
        summary = dict(
            id=session["session_id"], map=session["scenario"]["map_id"], player_name=profile_id, faction="Soviet"
        )
        return session, raw, sampler.footprint(), summary, sampler.bundle, sampler.scope
    finally:
        sampler.close()


def check_capacity(profile, raw, scope):
    """The commander style and this match's catalog fit the model context."""
    from .profiles import normalize_profile
    from .model_capacity import check_model_capacity
    from macro_policy import public_descriptions

    provider = profile.get("provider")
    if provider not in ("DeepSeek", "OpenAI", "自定义"):
        raise ContractError("model_context_capacity_provider_unavailable")
    effective = normalize_profile(dict(profile["draft"], model=profile["effective"]["model"]))
    if effective.effective_hash != profile["effective"]["effective_hash"]:
        raise ContractError("effective_profile_changed")
    catalog = public_descriptions(scope.available_actions, region_targets=scope.regional_action_regions.items())
    catalog.update(scope.model_catalog_overrides())
    try:
        capacity = check_model_capacity(effective, provider, raw, catalog)
    except ValueError:
        raise ContractError("model_context_capacity_contract_invalid") from None
    if not capacity["fits"]:
        raise ContractError(capacity["reason_code"])


def check(checks, registration, profile, host_id, state_dir, library_path, limits):
    from .desktop_backend import Admission, _module

    session, raw, footprint, summary, bundle, scope = _observed_session(registration, profile["profile_id"])
    if raw["paused"]:
        raise ContractError("session_not_ready")
    output = Path(session["run_directory"]) / "battle-host"
    if output.exists() and any(output.iterdir()):
        raise ContractError("run_state_conflict")
    # No protected loader at preflight: actual credentials are loaded only when
    # the bound host is ready to make provider requests.
    if hashlib.sha256(Path(library_path).read_bytes()).hexdigest() != profile["library_hash"]:
        raise ContractError("effective_profile_changed")
    check_capacity(profile, raw, scope)
    _module("model_backend", ROOT / "strategy").check_backend_available("pydantic")
    from .native_presence import require_unused_macro_process

    require_unused_macro_process(session["pid"])
    binding = SessionBinding(
        1,
        session["session_id"],
        3,
        profile["profile_id"],
        session["pid"],
        session["start_time"],
        host_id,
        digest(session["game"]),
        session["mod_sha256"],
    )
    summary["player_name"] = profile["name"]
    from .delegation_boundary import strategic_actions

    capabilities = dict(
        control_mode="macro_native",
        native_macro=True,
        available_macro_actions=list(strategic_actions(scope.available_actions)),
        supported_units=[],
        supported_foci=["native_baseline"],
        tactics_supported=False,
        runtime_tactical_supported=False,
        runtime_recovery_supported=False,
        runtime_purposes=[],
        model_response_received=False,
        native_transport_protocol=scope.native_transport_protocol,
        base_defense_granted=True,
        base_defense_goal="original_native_defense_of_own_infrastructure",
    )
    fingerprint = content_hash(
        dict(
            binding=binding.public(),
            footprint=footprint,
            profile_revision=profile["revision"],
            effective_hash=profile["effective"]["effective_hash"],
            library_hash=profile["library_hash"],
            scope=scope.public(),
            limits=limits.public(),
        )
    )
    return Admission(binding, fingerprint, summary, capabilities, False)


def released(backend, run_id, binding, host_receipt):
    """Whether the Host recorded a verified native return for this run."""
    from .native_lifecycle import verified_return

    return verified_return(backend, backend._launch(run_id), binding, host_receipt)
