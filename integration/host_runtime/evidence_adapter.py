"""Read-only bridge from existing raw-evidence verifiers to a scoped catalog.

Passing a filename/hash/`verified` flag cannot create a grant. Default verifiers
recompute the existing production and tactical proofs. Live process admission is
still performed by the actual native adapter immediately before execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path
import sys
from typing import Callable, Mapping

from .capabilities import CapabilityCatalog, VerifiedGrant
from .contracts import ContractError, SessionBinding, canonical_json, content_hash, identifier, sha256

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "integration"
PRODUCTION_EXECUTOR = ROOT / "production/persistent/bin-v2/ProductionPersistent.dll"
PRODUCTION_HOST = ROOT / "production/persistent/bin-v2/persistent_host.exe"
ONE_SHOT_EXECUTOR = ROOT / "production/bin/run_flak.exe"
PRODUCTION_SCOPE = ROOT / "production/persistent/capability-evidence.json"
TACTICAL_IDS = {("attack", "main_attack"): "tactics.attack",
                ("raid", "harass_economy"): "tactics.harass_economy",
                ("combined_arms", "coordinate_force"): "tactics.coordinate_force"}


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ContractError("invalid_evidence_object")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _existing_module(name: str):
    # Imports define existing verifier functions; no Host/Executor is constructed.
    if str(INTEGRATION) not in sys.path:
        sys.path.insert(0, str(INTEGRATION))
    value = importlib.import_module(name)
    if Path(value.__file__).resolve() != INTEGRATION / (name + ".py"):
        raise ContractError("evidence_verifier_module_mismatch")
    return value


def _production(path, session, *, root=None):
    return _existing_module("battle_host").capability_evidence(path, session, root=root)


def _persistent(path, session, *, root=None):
    return _existing_module("battle_host").conscript_evidence(path, session, root=root)


def _tactical(path, session, commander):
    return _existing_module("tactical_bridge").verify_manifest(path, session, commander)


def _session(binding: SessionBinding, session: Mapping):
    scenario = session.get("scenario", {})
    expected = {"session_id": binding.session_id, "pid": binding.game_process_id,
                "start_time": binding.game_process_start, "mod_sha256": binding.mod_sha256}
    if any(session.get(k) != v for k, v in expected.items()):
        raise ContractError("evidence_session_binding_mismatch")
    if scenario.get("commander_id") != binding.commander_id or scenario.get("computer_player_index") != binding.player_id:
        raise ContractError("evidence_commander_player_mismatch")
    # Existing proof executors currently hard-code player 3. Reject other players
    # rather than relabel that evidence as a generalized executor capability.
    if binding.player_id != 3:
        raise ContractError("legacy_executor_player_unsupported")
    game = Path(session["game"])
    if not game.is_absolute() or _digest(game) != binding.game_sha256:
        raise ContractError("evidence_game_binary_mismatch")
    production_path = ROOT / "production"
    if str(production_path) not in sys.path:
        sys.path.insert(0, str(production_path))
    module = importlib.import_module("session_package")
    if Path(module.__file__).resolve() != production_path / "session_package.py":
        raise ContractError("evidence_verifier_module_mismatch")
    module.verify_session_package(session)


def _production_integrity():
    """Check the repository's pinned executor inheritance, not a caller pin list."""
    value = _read(PRODUCTION_SCOPE)
    binaries = value.get("binaries", {})
    required = {"pause_guard_v2_dll": PRODUCTION_EXECUTOR, "pause_guard_v2_host": PRODUCTION_HOST}
    source_root = ROOT
    layout = ROOT / "companion-layout.json"
    if layout.exists():
        provenance = _read(layout)
        if set(provenance) != {"schema_version", "source_root"} or provenance["schema_version"] != 1:
            raise ContractError("production_executor_revision_mismatch")
        source_root = Path(provenance["source_root"])
        if not source_root.is_absolute() or str(source_root).startswith("\\\\"):
            raise ContractError("production_executor_revision_mismatch")
    for name, expected in required.items():
        row = binaries.get(name, {})
        recorded = source_root / expected.relative_to(ROOT)
        if Path(row.get("path", "")).resolve() != recorded or _digest(expected) != row.get("sha256"):
            raise ContractError("production_executor_revision_mismatch")
    return _digest(PRODUCTION_EXECUTOR), value


def _one_shot_executor():
    return _digest(ONE_SHOT_EXECUTOR)


@dataclass(frozen=True)
class EvidenceVerifiers:
    """Dependency injection for offline tests only; never exposed over IPC."""
    production: Callable = _production
    persistent: Callable = _persistent
    tactical: Callable = _tactical
    session: Callable = _session
    production_integrity: Callable = _production_integrity
    one_shot_executor: Callable = _one_shot_executor


@dataclass(frozen=True)
class EvidenceBundle:
    catalog: CapabilityCatalog
    production: dict | None
    persistent: dict | None
    tactical: dict | None
    test_only: bool
    runtime: dict | None = None
    first_home_recovery: dict | None = None

    @property
    def execution_constraints(self) -> dict:
        return {g["capability_id"]: g["execution_constraints"] for g in self.catalog.describe()["grants"]}

    @property
    def execution_constraints_hash(self) -> str:
        return content_hash(self.execution_constraints)

    def public(self) -> dict:
        return {"schema_version": 1, "catalog": self.catalog.describe(),
                "production_evidence_id": self.production.get("evidence_id") if self.production else None,
                "tactical_evidence_id": self.tactical.get("evidence_id") if self.tactical else None,
                "runtime_evidence_id": self.runtime.get("evidence_id") if self.runtime else None,
                "first_home_recovery_evidence_id": self.first_home_recovery.get('evidence_id') if self.first_home_recovery else None,
                "verification_mode": "injected_test_verifiers" if self.test_only else "existing_raw_verifiers",
                "execution_constraints": self.execution_constraints,
                "execution_constraints_hash": self.execution_constraints_hash,
                "live_process_admission_required": True, "capability_is_not_run_completion": True}


def build_catalog(binding: SessionBinding, session: Mapping, *, production_report: Path | None = None,
                  persistent_status: Path | None = None, tactical_manifest: Path | None = None,
                  runtime_report: Path | None = None, runtime_sha256: str | None = None,
                  runtime_recovery_report: Path | None = None, runtime_recovery_sha256: str | None = None,
                  verifiers: EvidenceVerifiers | None = None, acceptance_root: Path | None = None) -> EvidenceBundle:
    if not isinstance(binding, SessionBinding) or not isinstance(session, Mapping):
        raise ContractError("invalid_evidence_binding")
    verified = verifiers or EvidenceVerifiers(
        production=lambda path, session: _production(path, session, root=acceptance_root),
        persistent=lambda path, session: _persistent(path, session, root=acceptance_root))
    if not isinstance(verified, EvidenceVerifiers):
        raise ContractError("invalid_evidence_verifiers")
    # The immutable identity checks also run when a test replaces physical file checks.
    scenario = session.get("scenario", {})
    if (session.get("session_id") != binding.session_id or session.get("pid") != binding.game_process_id
            or session.get("start_time") != binding.game_process_start or session.get("mod_sha256") != binding.mod_sha256
            or scenario.get("commander_id") != binding.commander_id or scenario.get("computer_player_index") != binding.player_id):
        raise ContractError("evidence_session_binding_mismatch")
    if binding.player_id != 3:
        raise ContractError("legacy_executor_player_unsupported")
    try:
        verified.session(binding, session)
        grants = []; production = persistent = tactical = runtime = recovery = None
        if (runtime_report is None) != (runtime_sha256 is None):
            raise ContractError("runtime_evidence_pin_required")
        if (runtime_recovery_report is None)!=(runtime_recovery_sha256 is None):
            raise ContractError('first_home_evidence_pin_required')
        if runtime_recovery_report is not None and runtime_report is None:
            raise ContractError('first_home_requires_baseline_scope')
        if persistent_status is not None and production_report is None:
            raise ContractError("persistent_requires_base_production_evidence")
        if production_report is not None:
            path = Path(production_report).resolve()
            production = verified.production(path, session)
            if (not isinstance(production, dict) or production.get("source_report") != str(path)
                    or production.get("report_sha256") != _digest(path)
                    or production.get("assessment", {}).get("production_primitive_verified") is not True
                    or not production.get("assessment", {}).get("checks")
                    or not all(v is True for v in production["assessment"]["checks"].values())
                    or set(production.get("supported_foci", ())) != {"anti_air"}):
                raise ContractError("production_raw_evidence_unverified")
            report = _read(path)
            if report.get("mod_sha256") != binding.mod_sha256 or report.get("preflight", {}).get("player", {}).get("owner_index") != binding.player_id:
                raise ContractError("production_source_scope_mismatch")
            binary_hash, scope = verified.production_integrity()
            sha256(binary_hash)
            if scope.get("executable_sha256") != binding.game_sha256 or scope.get("package_sha256") != binding.mod_sha256:
                raise ContractError("production_executor_package_mismatch")
            one_shot_hash = sha256(verified.one_shot_executor())
            flak_constraints = dict(runtime_family="production_one_shot", executor_directory="production/bin",
                allowed_units=["flak"], persistent_units_verified=[], execution_ready=False,
                executor_sha256=one_shot_hash, evidence_id=production["evidence_id"],
                readiness_reason="historical_one_shot_executor_pin_missing")
            grants.append(VerifiedGrant("production.anti_air", production["evidence_id"], _digest(path), one_shot_hash,
                "Soviet Flak one-shot enqueue/payment/create primitive only; persistent Flak not established; "
                "historical executor binary pin missing; execution is unavailable until fresh validation",
                canonical_json(flak_constraints)))
            if persistent_status is not None:
                path = Path(persistent_status).resolve()
                persistent = verified.persistent(path, session)
                state = _read(path)
                if (not isinstance(persistent, dict) or persistent.get("status_sha256") != _digest(path)
                        or set(persistent.get("supported_foci", ())) != {"infantry", "balanced"}
                        or state.get("commander_id") != binding.commander_id or state.get("player_id") != binding.player_id):
                    raise ContractError("persistent_raw_evidence_unverified")
                audit = path.with_name("persistent-production.jsonl")
                if persistent.get("audit_sha256") != _digest(audit):
                    raise ContractError("persistent_audit_changed")
                audit_rows = [json.loads(line) for line in audit.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
                attaches = [row for row in audit_rows if row.get("event") == "attach_preflight"]
                if not attaches or any(row.get("commander_id") != binding.commander_id or row.get("session_id") != state.get("session_id") for row in attaches):
                    raise ContractError("persistent_source_commander_mismatch")
                evidence_id = content_hash({"status": _digest(path), "audit": _digest(audit)})
                constraints = dict(runtime_family="production_persistent_v2", executor_directory="production/persistent/bin-v2",
                    allowed_units=["conscript"], persistent_units_verified=["conscript"], execution_ready=True,
                    executor_sha256=binary_hash, evidence_id=evidence_id)
                grants.append(VerifiedGrant("production.infantry", evidence_id,
                    _digest(path), binary_hash, "Soviet Conscript persistent paid production only; no economy/technology/building authority; "
                    "pause-guard v2 inherits unchanged production path, no paused-dispatch field claim; current native admission required",
                    canonical_json(constraints)))
        if tactical_manifest is not None:
            tactical = verified.tactical(Path(tactical_manifest).resolve(), session, binding.commander_id)
            if not isinstance(tactical, dict) or not tactical.get("grants"):
                raise ContractError("tactical_raw_evidence_unverified")
            for raw in tactical["grants"]:
                key = (raw.get("module"), raw.get("purpose"))
                capability = TACTICAL_IDS.get(key)
                if capability is None:
                    raise ContractError("unsupported_tactical_scope")
                if (raw.get("session_id") != binding.session_id or raw.get("player_id") != binding.player_id
                        or raw.get("commander_id") != binding.commander_id or raw.get("source") != "game_bridge"
                        or raw.get("executable_sha256") != binding.game_sha256 or raw.get("package_sha256") != binding.mod_sha256):
                    raise ContractError("tactical_binding_mismatch")
                path = Path(raw["source_report"]).resolve()
                if _digest(path) != raw.get("source_sha256"):
                    raise ContractError("tactical_source_changed")
                identifier(raw["evidence_uuid"]); sha256(raw["native_binary_sha256"])
                role_scope = raw.get("stop_schema", {}).get("actor_roles")
                if not isinstance(role_scope, (tuple, list)) or not role_scope:
                    raise ContractError("tactical_role_scope_missing")
                description = canonical_json({"scope": raw.get("scope"), "executor": raw.get("executor_directory"),
                    "module": key[0], "purpose": key[1], "actor_roles": list(role_scope),
                    "limits": raw.get("limits"), "mission_protocol": raw.get("stop_schema", {}).get("mission_protocol")})
                constraints = dict(runtime_family="tactical", executor_directory="tactical/" + raw["executor_directory"],
                    module=key[0], purpose=key[1], actor_roles=list(role_scope), mission_protocol=raw.get("stop_schema", {}).get("mission_protocol"),
                    limits=raw.get("limits", {}), native_host_sha256=raw.get("native_host_sha256"), execution_ready=True,
                    executor_sha256=raw["native_binary_sha256"], evidence_id=raw["evidence_uuid"])
                grants.append(VerifiedGrant(capability, raw["evidence_uuid"], raw["source_sha256"], raw["native_binary_sha256"], description, canonical_json(constraints)))
                assessment = raw.get("raw_assessment", {})
                # Only an already verified continuous full movement/withdrawal
                # source can describe this subset. It keeps the identical scope.
                if (assessment.get("retreat_verified") is True and assessment.get("restoration_verified") is True
                        and assessment.get("approach_verified") is True):
                    if not any(g.capability_id == "tactics.move_hold_return" for g in grants):
                        subset_constraints = {**constraints, "execution_ready": False,
                                              "readiness_reason": "standalone_move_dispatch_not_verified"}
                        grants.append(VerifiedGrant("tactics.move_hold_return", raw["evidence_uuid"], raw["source_sha256"],
                            raw["native_binary_sha256"], "Movement/return subset only of " + description, canonical_json(subset_constraints)))
        if runtime_report is not None:
            from .runtime_evidence import verify_pinned_runtime
            grant = verify_pinned_runtime(Path(runtime_report).resolve(), runtime_sha256, binding)
            # A separately qualified current single-actor executor supersedes
            # only the non-executable movement subset of a legacy controller.
            if any(g.capability_id == grant.capability_id and g.public()["executable_ready"] for g in grants):
                raise ContractError("duplicate_executable_runtime_scope")
            grants = [g for g in grants if g.capability_id != grant.capability_id]
            grants.append(grant)
            runtime = dict(evidence_id=grant.evidence_id, source_report=str(Path(runtime_report).resolve()),
                           report_sha256=runtime_sha256, combat_effect_verified=False)
        if runtime_recovery_report is not None:
            from .runtime_first_home_evidence import verify_pinned_first_home
            grant=verify_pinned_first_home(Path(runtime_recovery_report).resolve(),runtime_recovery_sha256,binding,
                baseline_report=runtime_report,baseline_sha256=runtime_sha256)
            grants.append(grant)
            recovery=dict(evidence_id=grant.evidence_id,source_report=str(Path(runtime_recovery_report).resolve()),
                report_sha256=runtime_recovery_sha256,goal_effect_verified=False,natural_interference_verified=False)
        catalog = CapabilityCatalog.verify(binding, grants, lambda grant, _: grant)
        return EvidenceBundle(catalog, production, persistent, tactical, verifiers is not None, runtime,recovery)
    except ContractError:
        raise
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError):
        raise ContractError("existing_evidence_verification_failed") from None
