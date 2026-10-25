"""Standard-library strategy contract and dry-run coordinator.

No game-memory calls, model credentials, HTTP client, code execution, or live
production actuator are present here. Adapters receive a sanitized model context.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import tempfile
from typing import Any, Awaitable, Callable, Mapping
import uuid
from battlefield import Battlefield,TacticalIntent,validate_intents

SCHEMA_VERSION = 1
FOCI = frozenset({"native_baseline", "balanced", "anti_air", "anti_armor", "infantry", "naval", "economy"})
STANCES = frozenset({"defend", "scout", "pressure", "raid", "expand"})
ECONOMY = frozenset({"stabilize", "expand_if_defensible", "save"})
TECH = frozenset({"hold_current_tier", "advance_if_affordable"})
REASONS = frozenset({"air_threat", "armor_threat", "economy_window", "defensive_emergency", "balanced_default", "tech_window"})
EVENTS = frozenset({"base_under_attack", "enemy_air_seen", "major_loss", "phase_changed"})
CRITICAL_EVENTS = frozenset({"base_under_attack", "major_loss"})
ROLES = frozenset({"anti_air", "anti_armor", "infantry", "naval", "air", "armor", "economy","structure"})
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_REGION = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")


class ContractError(ValueError):
    """Stable error code only; never embeds model output or adapter exceptions."""


def _keys(value: Any, expected: set[str], code: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ContractError(code)
    return value


def _number(value: Any, low: float, high: float, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ContractError(code)
    return float(value)


def _integer(value: Any, low: int, high: int, code: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ContractError(code)
    return value


def _enum(value: Any, allowed: frozenset[str], code: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ContractError(code)
    return value


def _identifier(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ContractError(code)
    return value


def _session(value: Any) -> str:
    if not isinstance(value, str):
        raise ContractError("session_id")
    try:
        parsed = str(uuid.UUID(value))
    except (ValueError, AttributeError):
        raise ContractError("session_id") from None
    if parsed != value:
        raise ContractError("session_id")
    return value


def parse_model_json(raw: str | bytes) -> dict:
    """Bounded JSON, rejecting duplicate keys and NaN/Infinity before validation."""
    if isinstance(raw, bytes):
        if len(raw) > 16384:
            raise ContractError("model_size")
        try:
            raw = raw.decode("utf-8")
        except UnicodeError:
            raise ContractError("model_json") from None
    if not isinstance(raw, str):
        raise ContractError("model_size")
    try:
        if len(raw.encode("utf-8")) > 16384:
            raise ContractError("model_size")
    except UnicodeError:
        raise ContractError("model_json") from None

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate_key")
            result[key] = value
        return result

    def reject_constant(_):
        raise ContractError("nonfinite_json")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError, UnicodeError):
        raise ContractError("model_json") from None
    if not isinstance(value, dict):
        raise ContractError("model_object")
    return value


@dataclass(frozen=True)
class Binding:
    session_id: str
    player_id: int
    commander_id: str
    commander_name: str
    connection_id: str

    def __post_init__(self):
        _session(self.session_id)
        _integer(self.player_id, 0, 15, "player_id")
        _identifier(self.commander_id, "commander_id")
        _identifier(self.connection_id, "connection_id")
        if not isinstance(self.commander_name, str) or not 1 <= len(self.commander_name) <= 64 or any(ord(c) < 32 for c in self.commander_name):
            raise ContractError("commander_name")


@dataclass(frozen=True)
class Snapshot:
    session_id: str
    player_id: int
    snapshot_id: int
    game_time_seconds: float
    source: str
    paused: bool
    credits: float
    power_balance: float | None
    available_foci: tuple[str, ...]
    regions: tuple[str, ...]
    queued_count: int
    idle_producers: int
    own_roles: tuple[tuple[str, int], ...]
    enemy_observations: tuple[tuple[str, int, float, bool], ...]
    events: tuple[str, ...]
    battlefield: Battlefield | None = None

    @classmethod
    def from_dict(cls, raw: Any) -> "Snapshot":
        expected={"schema_version", "session_id", "player_id", "snapshot_id", "game_time_seconds", "source", "paused", "resources", "capabilities", "production", "enemy_observations", "events"}
        if isinstance(raw,dict) and "battlefield" in raw:expected.add("battlefield")
        d = _keys(raw,expected,"snapshot_fields")
        if d["schema_version"] != 1 or type(d["schema_version"]) is not int:
            raise ContractError("schema_version")
        session_id = _session(d["session_id"])
        player_id = _integer(d["player_id"], 0, 15, "player_id")
        snapshot_id = _integer(d["snapshot_id"], 0, 2**53 - 1, "snapshot_id")
        game_time = _number(d["game_time_seconds"], 0, 86400, "game_time")
        source = _enum(d["source"], frozenset({"simulated", "game_bridge"}), "source")
        if type(d["paused"]) is not bool:
            raise ContractError("paused")
        resources = _keys(d["resources"], {"credits", "power_balance"}, "resource_fields")
        credits = _number(resources["credits"], 0, 10**9, "credits")
        power = None if resources["power_balance"] is None else _number(resources["power_balance"], -10**7, 10**7, "power_balance")
        capabilities = _keys(d["capabilities"], {"production_focus", "regions"}, "capability_fields")
        foci, regions = capabilities["production_focus"], capabilities["regions"]
        if not isinstance(foci, list) or not 1 <= len(foci) <= len(FOCI) or len(set(x for x in foci if isinstance(x, str))) != len(foci):
            raise ContractError("available_foci")
        foci = tuple(_enum(x, FOCI, "available_foci") for x in foci)
        if "native_baseline" not in foci:
            raise ContractError("native_baseline_required")
        if not isinstance(regions, list) or len(regions) > 256 or any(not isinstance(x, str) or not _REGION.fullmatch(x) for x in regions) or len(set(regions)) != len(regions):
            raise ContractError("regions")
        production = _keys(d["production"], {"queued_count", "idle_producers", "own_roles"}, "production_fields")
        queued = _integer(production["queued_count"], 0, 10000, "queued_count")
        idle = _integer(production["idle_producers"], 0, 10000, "idle_producers")
        own = production["own_roles"]
        if not isinstance(own, dict) or set(own) - ROLES:
            raise ContractError("own_roles")
        own_roles = tuple(sorted((role, _integer(count, 0, 100000, "own_role_count")) for role, count in own.items()))
        observed = d["enemy_observations"]
        if not isinstance(observed, list) or len(observed) > 128:
            raise ContractError("enemy_observations")
        observations = []
        for item in observed:
            o = _keys(item, {"role", "count", "observed_at_game_seconds", "currently_visible"}, "enemy_observation_fields")
            if type(o["currently_visible"]) is not bool:
                raise ContractError("observation_visibility")
            observations.append((_enum(o["role"], ROLES, "enemy_role"), _integer(o["count"], 0, 100000, "enemy_count"), _number(o["observed_at_game_seconds"], 0, game_time, "observation_time"), o["currently_visible"]))
        events = d["events"]
        if not isinstance(events, list) or len(events) > len(EVENTS) or any(not isinstance(x, str) for x in events) or len(set(events)) != len(events):
            raise ContractError("events")
        events = tuple(_enum(x, EVENTS, "events") for x in events)
        battlefield=Battlefield.from_dict(d["battlefield"],game_time,set(regions),player_id) if "battlefield" in d else None
        if battlefield is not None and not battlefield.visibility_verified and observations:raise ContractError("unverified_enemy_information")
        return cls(session_id, player_id, snapshot_id, game_time, source, d["paused"], credits, power, foci, tuple(regions), queued, idle, own_roles, tuple(observations), events,battlefield)

    def model_context(self, binding: Binding) -> dict:
        """Only game observations and commander ID; no connection or credentials."""
        return {
            "schema_version": 1, "session_id": self.session_id, "player_id": self.player_id,
            "commander_id": binding.commander_id, "snapshot_id": self.snapshot_id,
            "game_time_seconds": self.game_time_seconds, "paused": self.paused,
            "resources": {"credits": self.credits, "power_balance": self.power_balance},
            "allowed_production_focus": list(self.available_foci), "allowed_regions": list(self.regions),
            "production": {"queued_count": self.queued_count, "idle_producers": self.idle_producers, "own_roles": dict(self.own_roles)},
            "enemy_observations": [{"role": role, "count": count, "observed_at_game_seconds": at, "currently_visible": visible} for role, count, at, visible in self.enemy_observations],
            "events": list(self.events),
            **({"battlefield":self.battlefield.public()} if self.battlefield is not None else {}),
        }

    def to_dict(self) -> dict:
        return {
            "schema_version": 1, "session_id": self.session_id, "player_id": self.player_id,
            "snapshot_id": self.snapshot_id, "game_time_seconds": self.game_time_seconds,
            "source": self.source, "paused": self.paused,
            "resources": {"credits": self.credits, "power_balance": self.power_balance},
            "capabilities": {"production_focus": list(self.available_foci), "regions": list(self.regions)},
            "production": {"queued_count": self.queued_count, "idle_producers": self.idle_producers, "own_roles": dict(self.own_roles)},
            "enemy_observations": [{"role": role, "count": count, "observed_at_game_seconds": at, "currently_visible": visible} for role, count, at, visible in self.enemy_observations],
            "events": list(self.events),
            **({"battlefield":self.battlefield.public()} if self.battlefield is not None else {}),
        }


@dataclass(frozen=True)
class Plan:
    plan_id: str
    commander_id: str
    session_id: str
    player_id: int
    snapshot_id: int
    based_on_game_time_seconds: float
    expires_at_game_seconds: float
    stance: str
    production_focus: str
    economy_policy: str
    tech_policy: str
    budget: tuple[tuple[str, float], ...]
    objective_region: str | None
    reason_code: str
    origin: str
    tactical_tasks: tuple[TacticalIntent,...] = ()

    def public(self) -> dict:
        result = asdict(self)
        result["budget"] = dict(self.budget)
        result["tactical_tasks"]=[task.public() for task in self.tactical_tasks]
        return result


def validate_policy(raw: Any, request: Snapshot, latest: Snapshot, binding: Binding, max_response_age: float) -> Plan:
    expected={"schema_version", "commander_id", "session_id", "player_id", "snapshot_id", "based_on_game_time_seconds", "valid_for_game_seconds", "stance", "production_focus", "economy_policy", "tech_policy", "budget", "objective_region", "reason_code"}
    if isinstance(raw,dict) and "tactical_tasks" in raw:expected.add("tactical_tasks")
    d = _keys(raw,expected,"policy_fields")
    if type(d["schema_version"]) is not int or d["schema_version"] != 1:
        raise ContractError("schema_version")
    if d["commander_id"] != binding.commander_id or d["session_id"] != binding.session_id or type(d["player_id"]) is not int or d["player_id"] != binding.player_id:
        raise ContractError("policy_binding")
    if type(d["snapshot_id"]) is not int or d["snapshot_id"] != request.snapshot_id:
        raise ContractError("policy_snapshot")
    based = _number(d["based_on_game_time_seconds"], 0, 86400, "policy_time")
    if abs(based - request.game_time_seconds) > 1e-6:
        raise ContractError("policy_time")
    if latest.game_time_seconds - based > max_response_age or latest.game_time_seconds < based:
        raise ContractError("stale_response")
    if set(latest.events) & CRITICAL_EVENTS and not set(request.events) & CRITICAL_EVENTS:
        raise ContractError("critical_event_after_request")
    duration = _number(d["valid_for_game_seconds"], 5, 60, "policy_duration")
    if latest.game_time_seconds >= based + duration:
        raise ContractError("expired_response")
    stance = _enum(d["stance"], STANCES, "stance")
    focus = _enum(d["production_focus"], FOCI, "production_focus")
    if focus not in request.available_foci or focus not in latest.available_foci:
        raise ContractError("unsupported_production_focus")
    economy = _enum(d["economy_policy"], ECONOMY, "economy_policy")
    tech = _enum(d["tech_policy"], TECH, "tech_policy")
    budget = _keys(d["budget"], {"economy", "army", "tech", "reserve"}, "budget_fields")
    values = tuple((key, _number(budget[key], 0, 1, "budget_range")) for key in sorted(budget))
    if abs(sum(value for _, value in values) - 1.0) > 1e-6 or not .05 <= budget["reserve"] <= .6:
        raise ContractError("budget_total_or_reserve")
    target = d["objective_region"]
    if target is not None and (not isinstance(target, str) or target not in request.regions or target not in latest.regions):
        raise ContractError("objective_region")
    if stance != "defend" and target is None:
        raise ContractError("objective_required")
    reason = _enum(d["reason_code"], REASONS, "reason_code")
    tactical=validate_intents(d.get("tactical_tasks",[]),request,latest)
    if sum(task.force_fraction for task in tactical)>1-budget["reserve"]+1e-6:raise ContractError("tactical_force_total")
    return Plan(uuid.uuid4().hex, binding.commander_id, binding.session_id, binding.player_id, request.snapshot_id, based, based + duration, stance, focus, economy, tech, values, target, reason, "model",tactical)


class Audit:
    """Only coordinator-generated fields; callers cannot append arbitrary text."""
    FIELDS = frozenset({"event", "reason_code", "request_id", "plan_id", "snapshot_id", "game_time_seconds", "production_focus", "stance", "status"})

    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None

    def emit(self, binding: Binding, **fields):
        if set(fields) - self.FIELDS:
            raise ContractError("audit_fields")
        entry = {"schema_version": 1, "at_utc": datetime.now(timezone.utc).isoformat(), "session_id": binding.session_id, "player_id": binding.player_id, "commander_id": binding.commander_id, **fields}
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + "\n")


@dataclass(frozen=True)
class Decision:
    status: str
    reason_code: str
    plan: Plan | None


Adapter = Callable[[dict], Awaitable[dict | str | bytes]]


class StrategyEngine:
    """One immutable commander/session/player binding per independent instance."""
    def __init__(self, binding: Binding, *, timeout_seconds=2.0, max_response_age_seconds=10.0, min_hold_game_seconds=15.0, audit_path: Path | None = None, status_path: Path | None = None, provenance_description: str | None = None):
        self.binding = binding
        self.timeout = _number(timeout_seconds, .001, 120, "timeout")
        self.max_response_age = _number(max_response_age_seconds, 0, 60, "max_response_age")
        self.min_hold = _number(min_hold_game_seconds, 0, 60, "min_hold")
        self.audit = Audit(audit_path)
        self.status_path = Path(status_path) if status_path else None
        self.provenance_description = provenance_description
        self.latest: Snapshot | None = None
        self.current: Plan | None = None
        self.last_result = {"status": "idle", "reason_code": "not_started"}
        self.metrics = dict(requests=0, accepted=0, rejected=0, timeouts=0, adapter_errors=0, plan_changes=0)
        self.stopped = False
        self._lock = asyncio.Lock()
        self._pending: asyncio.Task | None = None
        self._generation = 0
        self._accepted_at = float("-inf")
        self._state = "idle"
        self._reassessment_requested = False
        self._write_status("idle")

    def observe(self, raw: Mapping | Snapshot) -> Snapshot:
        snapshot = Snapshot.from_dict(raw.to_dict() if isinstance(raw, Snapshot) else raw)
        if snapshot.session_id != self.binding.session_id or snapshot.player_id != self.binding.player_id:
            raise ContractError("snapshot_binding")
        if self.latest:
            if snapshot.source != self.latest.source:
                raise ContractError("snapshot_source_changed")
            if snapshot.snapshot_id < self.latest.snapshot_id or snapshot.game_time_seconds < self.latest.game_time_seconds:
                raise ContractError("snapshot_regression")
            if snapshot.snapshot_id == self.latest.snapshot_id and snapshot != self.latest:
                raise ContractError("snapshot_conflict")
        self.latest = snapshot
        return snapshot

    def _usable(self, plan: Plan | None, snapshot: Snapshot) -> bool:
        return bool(plan and plan.commander_id == self.binding.commander_id and plan.session_id == snapshot.session_id and plan.player_id == snapshot.player_id and plan.based_on_game_time_seconds <= snapshot.game_time_seconds < plan.expires_at_game_seconds and plan.production_focus in snapshot.available_foci and (plan.objective_region is None or plan.objective_region in snapshot.regions))

    def _fallback_plan(self, snapshot: Snapshot) -> Plan:
        return Plan(uuid.uuid4().hex, self.binding.commander_id, self.binding.session_id, self.binding.player_id, snapshot.snapshot_id, snapshot.game_time_seconds, snapshot.game_time_seconds + 10, "defend", "native_baseline", "stabilize", "hold_current_tier", (("army", .4), ("economy", .35), ("reserve", .25), ("tech", 0.0)), None, "balanced_default", "local_fallback")

    @staticmethod
    def _intent(plan: Plan | None):
        if plan is None:
            return None
        return (plan.stance, plan.production_focus, plan.economy_policy, plan.tech_policy, plan.budget, plan.objective_region,plan.tactical_tasks)

    def _set_plan(self, plan: Plan):
        if self._intent(self.current) != self._intent(plan):
            self.metrics["plan_changes"] += 1
        self.current = plan

    def _finish(self, status: str, reason: str, state: str) -> Decision:
        self._state = state
        self.last_result = {"status": status, "reason_code": reason}
        self.audit.emit(self.binding, event="decision", status=status, reason_code=reason, snapshot_id=self.latest.snapshot_id if self.latest else None, game_time_seconds=self.latest.game_time_seconds if self.latest else None, plan_id=self.current.plan_id if self.current else None)
        self._write_status(state)
        return Decision(status, reason, self.current)

    def _local(self, reason: str) -> Decision:
        if self.stopped:
            self.current = None
            return self._finish("stopped", "stopped", "stopped")
        assert self.latest is not None
        emergency_override = "base_under_attack" in self.latest.events and self.current is not None and self.current.stance != "defend"
        if self._usable(self.current, self.latest) and not emergency_override:
            return self._finish("fallback_continuing", reason, "fallback")
        self._set_plan(self._fallback_plan(self.latest))
        return self._finish("local_fallback", reason, "fallback")

    async def decide(self, raw: Mapping | Snapshot, adapter: Adapter) -> Decision:
        async with self._lock:
            request = self.observe(raw)
            if self.stopped:
                self.current = None
                return self._finish("stopped", "stopped", "stopped")
            if request.paused:
                if not self._usable(self.current, request):
                    self.current = None
                return self._finish("paused", "game_paused", "holding")
            age = request.game_time_seconds - self._accepted_at
            interrupt = bool(set(request.events) & CRITICAL_EVENTS) or self._reassessment_requested
            if self._usable(self.current, request) and self.current.origin == "model" and age < self.min_hold and (not interrupt or age < min(2.0, self.min_hold)):
                return self._finish("held", "minimum_hold", "holding")
            if self._pending is not None and not self._pending.done():
                return self._local("adapter_still_cancelling")
            request_id = uuid.uuid4().hex
            self._reassessment_requested = False
            self.metrics["requests"] += 1
            self.audit.emit(self.binding, event="request", request_id=request_id, snapshot_id=request.snapshot_id, game_time_seconds=request.game_time_seconds)
            self.last_result = {"status": "planning", "reason_code": "awaiting_model"}
            self._state = "planning"
            self._write_status("planning")
            generation = self._generation
            try:
                task = asyncio.ensure_future(adapter(request.model_context(self.binding)))
            except Exception:
                self.metrics["adapter_errors"] += 1
                return self._local("adapter_error")
            self._pending = task
            # Consume eventual failures after timeout without ever logging exception text.
            def consume(t):
                if not t.cancelled():
                    t.exception()
            task.add_done_callback(consume)
            try:
                done, _ = await asyncio.wait({task}, timeout=self.timeout)
                if not done:
                    task.cancel()
                    self.metrics["timeouts"] += 1
                    return self._local("model_timeout")
                if generation != self._generation or self.stopped:
                    return self._local("request_cancelled")
                try:
                    response = task.result()
                except asyncio.CancelledError:
                    self.metrics["adapter_errors"] += 1
                    return self._local("adapter_cancelled")
                except Exception:
                    self.metrics["adapter_errors"] += 1
                    return self._local("adapter_error")
                if isinstance(response, (str, bytes)):
                    response = parse_model_json(response)
                if self._reassessment_requested:
                    raise ContractError("reassessment_after_request")
                assert self.latest is not None
                plan = validate_policy(response, request, self.latest, self.binding, self.max_response_age)
                if self.latest.paused:
                    if not self._usable(self.current, self.latest):
                        self.current = None
                    return self._finish("paused", "paused_during_request", "holding")
                self._set_plan(plan)
                self._accepted_at = self.latest.game_time_seconds
                self.metrics["accepted"] += 1
                self.audit.emit(self.binding, event="plan_accepted", request_id=request_id, plan_id=plan.plan_id, snapshot_id=request.snapshot_id, production_focus=plan.production_focus, stance=plan.stance)
                return self._finish("accepted", "valid_policy", "holding")
            except ContractError as error:
                self.metrics["rejected"] += 1
                self.audit.emit(self.binding, event="policy_rejected", request_id=request_id, reason_code=str(error), snapshot_id=request.snapshot_id)
                return self._local(str(error))
            except asyncio.CancelledError:
                task.cancel()
                if self.stopped or generation != self._generation:
                    return self._local("request_cancelled")
                raise
            except Exception:
                self.metrics["adapter_errors"] += 1
                return self._local("adapter_error")

    def stop(self):
        self.stopped = True
        self._generation += 1
        self.current = None
        if self._pending is not None and not self._pending.done():
            self._pending.cancel()
        self._finish("stopped", "user_stopped", "stopped")

    def request_reassessment(self, reason_code: str):
        """Trusted local feedback can request review without inventing game events."""
        if reason_code not in {"execution_failure", "capability_changed"}:
            raise ContractError("reassessment_reason")
        self._reassessment_requested = True
        self.audit.emit(self.binding, event="reassessment_requested", reason_code=reason_code)

    def public_status(self, state: str | None = None) -> dict:
        snapshot = self.latest
        provenance = {"kind": snapshot.source if snapshot else "simulated", "description": "Synthetic local adapter fixture; no real model or game is connected." if snapshot is None or snapshot.source == "simulated" else "Read-only bridge observations; no game actuator is connected."}
        if self.provenance_description is not None:
            provenance["description"] = self.provenance_description
        return {
            "schema_version": 1, "service_state": state or self._state,
            "mode": "simulation" if snapshot is None or snapshot.source == "simulated" else "read_only",
            "source": dict(provenance), "provenance": dict(provenance),
            "binding": {**asdict(self.binding), "computer_verified": False},
            "latest_snapshot": {"snapshot_id": snapshot.snapshot_id, "game_time_seconds": snapshot.game_time_seconds, "paused": snapshot.paused} if snapshot else None,
            "current_plan": self.current.public() if self.current else None,
            "last_result": dict(self.last_result),
            "execution": {"enabled": False, "dry_run": True, "reason_code": "production_control_not_verified"},
            "metrics": dict(self.metrics),
        }

    def _write_status(self, state: str):
        if not self.status_path:
            return
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.public_status(state), ensure_ascii=False, indent=2, allow_nan=False)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.status_path.parent, prefix=".status-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            temporary.replace(self.status_path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
