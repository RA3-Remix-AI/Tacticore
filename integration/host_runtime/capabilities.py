"""Capability descriptions use host-verified evidence, never UI authority flags."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import math
from pathlib import PurePosixPath, PureWindowsPath
from typing import Callable, Iterable, Mapping

from .contracts import ContractError, SessionBinding, canonical_json, content_hash, sha256, text

AXIS_REQUIREMENTS = {
    "attack": ("tactics.attack",),
    "risk": ("tactics.retreat",),
    "economy": ("economy.expand",),
    "scouting": ("recon.scout",),
    "pursuit": ("tactics.pursuit",),
}
CAPABILITY_IDS = frozenset({"production.infantry", "production.anti_air", "technology.advance",
                            "tactics.coordinate_force", "tactics.harass_economy", "tactics.move_hold_return", "tactics.reconcile_return_home",
                            *(c for rows in AXIS_REQUIREMENTS.values() for c in rows)})


@dataclass(frozen=True)
class VerifiedGrant:
    """Constructed by the host's evidence verifier, not decoded from UI JSON.

    This catalog still does not replace native per-command admission checks.
    """
    capability_id: str
    evidence_id: str
    source_sha256: str
    executor_sha256: str
    scope: str
    execution_constraints_json: str = "{}"

    def __post_init__(self):
        if self.capability_id not in CAPABILITY_IDS:
            raise ContractError("unknown_capability")
        text(self.evidence_id, 128); text(self.scope, 500)
        sha256(self.source_sha256); sha256(self.executor_sha256)
        self._constraints()

    def _constraints(self) -> dict:
        try:
            value = json.loads(self.execution_constraints_json)
        except (TypeError, ValueError):
            raise ContractError("invalid_execution_constraints") from None
        keys = {"runtime_family", "executor_directory", "allowed_units", "persistent_units_verified", "max_budget", "reserve_floor",
                "module", "purpose", "actor_roles", "mission_protocol", "limits", "native_host_sha256",
                "execution_ready", "executor_sha256", "evidence_id", "readiness_reason"}
        if not isinstance(value, dict) or set(value) - keys or canonical_json(value) != self.execution_constraints_json:
            raise ContractError("invalid_execution_constraints")
        if not value:
            return value
        required = {"runtime_family", "executor_directory", "execution_ready", "executor_sha256", "evidence_id"}
        if not required <= set(value) or type(value["execution_ready"]) is not bool:
            raise ContractError("invalid_execution_constraints")
        if value["runtime_family"] not in ("production_persistent_v2", "production_one_shot", "tactical"):
            raise ContractError("invalid_execution_constraints")
        directory = value["executor_directory"]
        if (not isinstance(directory, str) or not directory or "\\" in directory or ":" in directory
                or PurePosixPath(directory).is_absolute() or PureWindowsPath(directory).is_absolute()
                or any(p in (".", "..") for p in directory.split("/"))):
            raise ContractError("invalid_execution_constraints")
        if value["executor_sha256"] != self.executor_sha256 or value["evidence_id"] != self.evidence_id:
            raise ContractError("execution_constraint_identity_mismatch")
        for field in ("allowed_units", "persistent_units_verified", "actor_roles"):
            if field in value:
                allowed = {"infantry", "anti_air", "air"} if field == "actor_roles" else {"conscript", "flak"}
                items = value[field]
                if (not isinstance(items, list) or any(not isinstance(x, str) or x not in allowed for x in items)
                        or len(items) != len(set(items))):
                    raise ContractError("invalid_execution_constraints")
        for field in ("max_budget", "reserve_floor"):
            if field in value and (type(value[field]) is not int or not 0 <= value[field] <= 20000):
                raise ContractError("invalid_execution_constraints")
        if "limits" in value:
            limits = value["limits"]
            allowed = {"request_force_fraction_min", "request_force_fraction_max", "allocation_fraction_cap", "min_remaining_frames", "max_remaining_frames", "lease_frames"}
            if not isinstance(limits, dict) or set(limits) - allowed:
                raise ContractError("invalid_execution_constraints")
            if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in limits.values()):
                raise ContractError("invalid_execution_constraints")
        if "native_host_sha256" in value:
            sha256(value["native_host_sha256"])
        for field in ("module", "purpose", "mission_protocol", "readiness_reason"):
            if field in value and value[field] is not None:
                text(value[field], 128)
        return value

    def public(self) -> dict:
        return {"capability_id": self.capability_id, "evidence_id": self.evidence_id,
                "source_sha256": self.source_sha256, "executor_sha256": self.executor_sha256,
                "scope": self.scope, "execution_constraints": self._constraints(),
                "executable_ready": self._constraints().get("execution_ready") is True}


class CapabilityCatalog:
    """Empty by default. Verification callback is an in-process trusted boundary."""
    def __init__(self):
        self._binding: SessionBinding | None = None
        self._grants: tuple[VerifiedGrant, ...] = ()

    @classmethod
    def verify(cls, binding: SessionBinding, candidates: Iterable,
               verifier: Callable[[object, SessionBinding], VerifiedGrant]) -> "CapabilityCatalog":
        if not isinstance(binding, SessionBinding) or not callable(verifier):
            raise ContractError("capability_verifier_required")
        catalog = cls(); grants = []
        for candidate in candidates:
            grant = verifier(candidate, binding)
            if not isinstance(grant, VerifiedGrant):
                raise ContractError("invalid_verified_grant")
            if any(g.capability_id == grant.capability_id for g in grants):
                raise ContractError("duplicate_capability")
            grants.append(grant)
        catalog._binding = binding
        catalog._grants = tuple(sorted(grants, key=lambda g: g.capability_id))
        return catalog

    @property
    def binding_hash(self) -> str | None:
        return self._binding.binding_hash if self._binding else None

    @property
    def binding(self) -> SessionBinding | None:
        return self._binding

    def require(self, capability_id: str, binding: SessionBinding | None = None) -> VerifiedGrant:
        if capability_id not in CAPABILITY_IDS:
            raise ContractError("unknown_capability")
        if self._binding is None:
            raise ContractError("capability_unsupported")
        if not isinstance(binding, SessionBinding) or binding != self._binding:
            raise ContractError("capability_binding_mismatch")
        for grant in self._grants:
            if grant.capability_id == capability_id:
                return grant
        raise ContractError("capability_unsupported")

    def describe_axes(self) -> dict:
        present = {g.capability_id for g in self._grants if g.public()["executable_ready"]}
        return {axis: {
            "mode": "executable" if set(required) <= present else "advisory",
            "model_advice": True,
            "execution_status": "verified_scope" if set(required) <= present else "unsupported",
            "missing_capabilities": sorted(set(required) - present),
            "required_capabilities": list(required),
            "verified_scopes": [{"capability_id": g.capability_id, "scope": g.scope,
                                 "evidence_id": g.evidence_id} for g in self._grants if g.capability_id in required],
        } for axis, required in AXIS_REQUIREMENTS.items()}

    def describe(self) -> dict:
        return {"schema_version": 1, "binding_hash": self.binding_hash,
                "grants": [g.public() for g in self._grants], "axes": self.describe_axes(),
                "per_command_admission_required": True}

    @property
    def catalog_hash(self) -> str:
        return content_hash(self.describe())


def policy_execution_support(policy: Mapping, catalog: CapabilityCatalog,
                             binding: SessionBinding | None = None) -> dict:
    """Explicitly reports policy fields that lack executors; never silently merges budgets."""
    if not isinstance(policy, Mapping) or not isinstance(catalog, CapabilityCatalog):
        raise ContractError("invalid_policy_support_request")
    policies = (("economy_policy", "expand_if_defensible", "economy.expand"),
                ("tech_policy", "advance_if_affordable", "technology.advance"))
    enums = {"economy_policy": {"stabilize", "expand_if_defensible", "save"},
             "tech_policy": {"hold_current_tier", "advance_if_affordable"}}
    result = {}
    for field, requires_value, capability in policies:
        value = policy.get(field)
        if not isinstance(value, str) or value not in enums[field]:
            raise ContractError("invalid_policy_field")
        if value != requires_value:
            result[field] = {"requested": value, "status": "advisory", "reason_code": "no_native_policy_executor"}
            continue
        try:
            grant = catalog.require(capability, binding)
        except ContractError as error:
            result[field] = {"requested": value, "status": "unsupported", "reason_code": error.code}
        else:
            if grant.public()["executable_ready"]:
                result[field] = {"requested": value, "status": "executable", "capability_id": grant.capability_id,
                                 "scope": grant.scope, "per_command_admission_required": True}
            else:
                result[field] = {"requested": value, "status": "unsupported", "reason_code": "capability_not_execution_ready"}
    return result
