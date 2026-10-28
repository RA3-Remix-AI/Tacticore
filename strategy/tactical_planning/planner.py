"""Advisory G6 planning over existing Snapshot/TacticalIntent/MissionProgress.

This is an immutable advice cache, not another MissionBoard or lease owner.
No observation, caller capability manifest or successful replay grants native IO.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import uuid

from battlefield import TacticalIntent, validate_intents
from engine import Binding, ContractError, Snapshot, _identifier, _session
from missions import Mission, MissionObservations, MissionProgress, PHASES

MODULES = {"main_attack": "attack", "harass_economy": "raid", "coordinate_force": "combined_arms"}
DEFAULT_ROLES = {"main_attack": ("infantry",), "harass_economy": ("infantry",),
                 "coordinate_force": ("infantry", "anti_air")}
ADVICE_PHASES = {"approach", "prepare", "engage", "retreat", "await_host_release", "closed_reported"}


def _number(value, low, high, code):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ContractError(code)
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Limits:
    max_contact_age_seconds: float = 3
    duration_game_seconds: float = 180
    max_wall_duration_ms: float = 240000
    max_engage_game_seconds: float = 30
    force_fraction: float = .5

    def __post_init__(self):
        _number(self.max_contact_age_seconds, 0, 3, "planning_contact_age")
        _number(self.duration_game_seconds, 15, 300, "planning_duration")
        _number(self.max_wall_duration_ms, 1000, 3600000, "planning_wall_duration")
        _number(self.max_engage_game_seconds, 1, 120, "planning_engage_duration")
        _number(self.force_fraction, .01, 1, "planning_force_fraction")


@dataclass(frozen=True)
class Memory:
    session_id: str
    commander_id: str
    player_id: int
    source: str
    purpose: str
    generation: int
    task_id: str
    target_contact_id: str
    target_region: str
    retreat_region: str
    formation_versions: tuple
    required_roles: tuple
    force_fraction: float
    created_game_seconds: float
    deadline_game_seconds: float
    created_monotonic_ms: float
    wall_deadline_ms: float
    last_game_seconds: float
    last_monotonic_ms: float
    last_frame: int
    stage: str = "approach"
    retreat_reason: str | None = None
    engage_started_game_seconds: float | None = None
    feedback_sequence: int = 0
    feedback_digest: str | None = None
    host_phase: str | None = None
    engage_duration_game_seconds: float = 30

    def __post_init__(self):
        _session(self.session_id)
        _identifier(self.commander_id, "planning_memory_binding")
        if type(self.player_id) is not int or not 0 <= self.player_id <= 15 or self.source not in {"simulated", "game_bridge"}:
            raise ContractError("planning_memory_binding")
        try:
            valid_id = isinstance(self.task_id, str) and str(uuid.UUID(self.task_id)) == self.task_id
        except (ValueError, AttributeError):valid_id = False
        if not valid_id or self.purpose not in MODULES or type(self.generation) is not int or not 1 <= self.generation <= 2**31-1:
            raise ContractError("planning_memory_identity")
        _identifier(self.target_contact_id, "planning_memory_target")
        _identifier(self.target_region, "planning_memory_target")
        _identifier(self.retreat_region, "planning_memory_home")
        if (not isinstance(self.formation_versions, tuple) or not 1 <= len(self.formation_versions) <= 4
                or any(not isinstance(pair, tuple) or len(pair) != 2 for pair in self.formation_versions)):
            raise ContractError("planning_memory_formations")
        for key, version in self.formation_versions:
            _identifier(key, "planning_memory_formations")
            if type(version) is not int or not 1 <= version <= 2**31-1:raise ContractError("planning_memory_formations")
        if len(set(k for k, _ in self.formation_versions)) != len(self.formation_versions):
            raise ContractError("planning_memory_formations")
        if not isinstance(self.required_roles, tuple) or set(self.required_roles) != set(DEFAULT_ROLES[self.purpose]) or len(self.required_roles) != len(set(self.required_roles)):
            raise ContractError("planning_memory_roles")
        _number(self.force_fraction, .01, 1, "planning_memory_force")
        _number(self.created_game_seconds, 0, 86400, "planning_memory_clock")
        _number(self.deadline_game_seconds, self.created_game_seconds + 15,
                self.created_game_seconds + 300, "planning_memory_deadline")
        _number(self.last_game_seconds, self.created_game_seconds, 86400, "planning_memory_clock")
        _number(self.created_monotonic_ms, 0, 1e15, "planning_memory_clock")
        _number(self.wall_deadline_ms, self.created_monotonic_ms + 1000,
                self.created_monotonic_ms + 3600000, "planning_memory_deadline")
        _number(self.last_monotonic_ms, self.created_monotonic_ms, 1e15, "planning_memory_clock")
        if type(self.last_frame) is not int or self.last_frame < 0 or self.stage not in ADVICE_PHASES:
            raise ContractError("planning_memory_phase")
        _number(self.engage_duration_game_seconds, 1, 120, "planning_engage_duration")
        if self.engage_started_game_seconds is not None:
            _number(self.engage_started_game_seconds, self.created_game_seconds,
                    self.last_game_seconds, "planning_memory_engage")
        if type(self.feedback_sequence) is not int or self.feedback_sequence < 0:
            raise ContractError("planning_memory_feedback")
        if self.host_phase is not None and self.host_phase not in PHASES:
            raise ContractError("planning_memory_feedback")

    def public(self):
        return asdict(self)


@dataclass(frozen=True)
class Recommendation:
    action: str
    reason_code: str
    memory: Memory | None = None
    intent: TacticalIntent | None = None

    def public(self):
        return {"schema_version": 1, "action": self.action, "reason_code": self.reason_code,
                "suggested_stage": self.memory.stage if self.memory else None,
                "task_id": self.memory.task_id if self.memory else None,
                "memory": self.memory.public() if self.memory else None,
                "tactical_intent": self.intent.public() if self.intent else None,
                "execution_authorized": False, "field_verified": False,
                "mission_completed": False, "control_release_verified": False}


def _current_target(snapshot, ident, limits):
    for item in snapshot.battlefield.contacts:
        if (item.contact_id == ident and item.relation == "enemy" and item.currently_visible
                and item.stealth_state in {"visible", "detected"}
                and 0 <= snapshot.game_time_seconds - item.observed_at_game_seconds <= limits.max_contact_age_seconds):
            return item
    return None


def _select_target(snapshot, purpose, limits):
    ranks = ({"economy": 0} if purpose == "harass_economy" else
             {"structure": 0, "armor": 1, "anti_armor": 2, "anti_air": 3, "infantry": 4, "economy": 5})
    candidates = [item for item in snapshot.battlefield.contacts
                  if item.role in ranks and _current_target(snapshot, item.contact_id, limits) is not None]
    return min(candidates, key=lambda item: (ranks[item.role], item.contact_id), default=None)


def _select_formations(snapshot, roles, unavailable, purpose):
    # Greedy bounded coverage with stable tie breaks, at most four formations.
    candidates = [item for item in snapshot.battlefield.formations if item.available and item.formation_id not in unavailable
                  and (purpose != "coordinate_force" or {r for r, n in item.roles if n}.issubset(roles))]
    selected = []
    needed = set(roles)
    while needed and len(selected) < 4:
        ranked = sorted(candidates, key=lambda item: (-len(needed & {r for r, n in item.roles if n}), item.formation_id))
        if not ranked or not (needed & {r for r, n in ranked[0].roles if n}):
            return ()
        item = ranked[0]
        selected.append(item)
        candidates.remove(item)
        needed -= {r for r, n in item.roles if n}
    return tuple(sorted((item.formation_id, item.version) for item in selected)) if not needed else ()


def _feedback(memory, feedback, snapshot):
    if feedback is None:
        return memory, None
    if not isinstance(feedback, MissionProgress) or not isinstance(feedback.observations, MissionObservations):
        raise ContractError("planning_feedback_type")
    expected = (memory.session_id, memory.player_id, memory.commander_id, memory.task_id,
                memory.task_id, memory.source, memory.target_contact_id, memory.formation_versions)
    observed = (feedback.session_id, feedback.player_id, feedback.commander_id, feedback.task_id,
                feedback.mission_id, feedback.source, feedback.target_contact_id, feedback.formation_versions)
    if observed != expected or type(feedback.player_id) is not int:
        raise ContractError("planning_feedback_binding")
    _number(feedback.at_game_seconds, memory.created_game_seconds, snapshot.game_time_seconds, "planning_feedback_time")
    if type(feedback.progress_seq) is not int or feedback.progress_seq < 1:
        raise ContractError("planning_feedback_sequence")
    if feedback.phase not in PHASES or (memory.host_phase is not None and PHASES.index(feedback.phase) < PHASES.index(memory.host_phase)):
        raise ContractError("planning_feedback_phase")
    if (not isinstance(feedback.evidence_sha256, str) or len(feedback.evidence_sha256) != 64
            or any(c not in "0123456789abcdef" for c in feedback.evidence_sha256)):
        raise ContractError("planning_feedback_evidence")
    obs = feedback.observations
    for name in ("target_currently_visible", "approach_verified", "coordination_verified", "retreat_verified",
                 "restoration_verified", "no_dispatch_verified", "disposed_verified", "scene_closed_verified"):
        if type(getattr(obs, name)) is not bool:
            raise ContractError("planning_feedback_boolean")
    _number(obs.source_damage_amount, 0, 1e8, "planning_feedback_damage")
    if obs.distance_to_goal is not None:
        _number(obs.distance_to_goal, 0, 1e7, "planning_feedback_distance")
    if obs.interference not in {"none", "native_ai_override", "unknown"}:
        raise ContractError("planning_feedback_interference")
    digest = _digest(asdict(feedback))
    if feedback.progress_seq < memory.feedback_sequence:
        raise ContractError("planning_feedback_sequence")
    if feedback.progress_seq == memory.feedback_sequence:
        if digest != memory.feedback_digest:
            raise ContractError("planning_feedback_duplicate_changed")
        return memory, feedback
    return replace(memory, feedback_sequence=feedback.progress_seq, feedback_digest=digest, host_phase=feedback.phase), feedback


def _intent(memory):
    return TacticalIntent(MODULES[memory.purpose], memory.purpose, memory.target_region,
                          memory.target_contact_id, tuple(k for k, _ in memory.formation_versions),
                          memory.required_roles, memory.force_fraction, memory.formation_versions)


def plan_for_snapshot(binding, snapshot, purpose, *, game_frame, monotonic_ms,
                      capability_purposes=(), allowed_roles=None, memory=None, feedback=None,
                      generation=1, unavailable_formations=(), stop_requested=False, limits=None):
    """Recommend one task slot, preserving target/identity until host-reported release.

    capability_purposes/allowed_roles are caller projections for early rejection;
    the authoritative host must independently authorize every actual command.
    Existing tasks retain their identity/total deadline when strategic TTL refreshes.
    """
    limits = limits or Limits()
    if not isinstance(binding, Binding) or not isinstance(snapshot, Snapshot) or not isinstance(limits, Limits):
        raise ContractError("planning_input_type")
    if purpose not in MODULES or type(generation) is not int or not 1 <= generation <= 2**31 - 1:
        raise ContractError("planning_task_identity")
    if type(game_frame) is not int or game_frame < 0 or type(stop_requested) is not bool:
        raise ContractError("planning_clock_or_stop")
    _number(monotonic_ms, 0, 1e15, "planning_clock")
    # Revalidate directly constructed dataclasses through the existing wire contract.
    snapshot = Snapshot.from_dict(snapshot.to_dict())
    if (snapshot.session_id, snapshot.player_id) != (binding.session_id, binding.player_id):
        raise ContractError("planning_snapshot_binding")
    if memory is not None:
        if not isinstance(memory, Memory):
            raise ContractError("planning_memory_type")
        if (memory.session_id, memory.player_id, memory.commander_id, memory.source) != (
                binding.session_id, binding.player_id, binding.commander_id, snapshot.source):
            return Recommendation("discard", "binding_changed")
        if (memory.purpose, memory.generation) != (purpose, generation):
            raise ContractError("planning_memory_identity")
        if snapshot.game_time_seconds < memory.last_game_seconds or monotonic_ms < memory.last_monotonic_ms or game_frame < memory.last_frame:
            raise ContractError("planning_clock_regressed")
    unavailable = set(unavailable_formations)
    if any(not isinstance(item, str) for item in unavailable):
        raise ContractError("planning_unavailable_formations")
    permitted = purpose in capability_purposes
    expected_roles = DEFAULT_ROLES[purpose]
    roles = tuple(sorted(allowed_roles)) if allowed_roles is not None else ()
    if (len(roles) != len(set(roles)) or any(role not in {r for r in expected_roles} for role in roles)
            or set(expected_roles) - set(roles)):
        permitted = False
    if memory is None:
        if feedback is not None:
            raise ContractError("planning_feedback_without_task")
        if stop_requested:
            return Recommendation("wait", "stopped_without_task")
        if not permitted:
            return Recommendation("wait", "capability_unavailable")
        if snapshot.paused:
            return Recommendation("wait", "game_paused")
        if snapshot.battlefield is None or not snapshot.battlefield.visibility_verified:
            return Recommendation("wait", "visibility_unavailable")
        target = _select_target(snapshot, purpose, limits)
        if target is None:
            return Recommendation("wait", "no_current_target")
        formations = _select_formations(snapshot, roles, unavailable, purpose)
        if not formations:
            return Recommendation("wait", "roles_unavailable")
        home = min((r.region_id for r in snapshot.battlefield.regions if r.relation in {"self", "ally"}), default=None)
        if home is None:
            return Recommendation("wait", "retreat_region_unavailable")
        task_id = str(uuid.uuid5(uuid.UUID(binding.session_id), f"tactical-planning:{binding.commander_id}:{binding.player_id}:{purpose}:{generation}"))
        memory = Memory(binding.session_id, binding.commander_id, binding.player_id, snapshot.source,
                        purpose, generation, task_id, target.contact_id, target.region_id, home,
                        formations, roles, limits.force_fraction, snapshot.game_time_seconds,
                        snapshot.game_time_seconds + limits.duration_game_seconds, monotonic_ms,
                        monotonic_ms + limits.max_wall_duration_ms, snapshot.game_time_seconds,
                        monotonic_ms, game_frame, engage_duration_game_seconds=limits.max_engage_game_seconds)
        intent = _intent(memory)
        validate_intents([intent.public()], snapshot, snapshot)
        return Recommendation("propose", "current_target_and_roles", memory, intent)
    memory, telemetry = _feedback(memory, feedback, snapshot)
    memory = replace(memory, last_game_seconds=snapshot.game_time_seconds, last_monotonic_ms=monotonic_ms, last_frame=game_frame)
    if memory.stage == "closed_reported":
        return Recommendation("closed", "host_reported_release_requires_certification", memory)
    reason = memory.retreat_reason
    if stop_requested:
        reason = reason or "host_stop"
    elif snapshot.game_time_seconds >= memory.deadline_game_seconds or monotonic_ms >= memory.wall_deadline_ms:
        reason = reason or "deadline"
    elif not permitted:
        reason = reason or "capability_lost"
    elif snapshot.battlefield is None or not snapshot.battlefield.visibility_verified:
        reason = reason or "target_lost"
    else:
        current = _current_target(snapshot, memory.target_contact_id, limits)
        if current is None or current.region_id != memory.target_region:
            reason = reason or "target_lost"
        forms = {f.formation_id: f for f in snapshot.battlefield.formations}
        if any(key in unavailable or key not in forms or forms[key].version != version
               for key, version in memory.formation_versions):
            reason = reason or "formation_changed"
        else:
            present = {role for key, _ in memory.formation_versions for role, count in forms[key].roles if count}
            if set(memory.required_roles) - present:
                reason = reason or "roles_lost"
    if telemetry and telemetry.observations.interference != "none":
        reason = reason or "native_interference"
    if reason:
        memory = replace(memory, stage="retreat", retreat_reason=reason)
    if telemetry is not None:
        obs = telemetry.observations
        if telemetry.phase == "restored" and obs.restoration_verified:
            memory = replace(memory, stage="closed_reported")
            return Recommendation("closed", "host_reported_release_requires_certification", memory)
        if memory.retreat_reason:
            if telemetry.phase in {"retreat", "restored"} and obs.retreat_verified:
                memory = replace(memory, stage="await_host_release")
        elif telemetry.phase == "engage":
            started = memory.engage_started_game_seconds
            memory = replace(memory, stage="engage", engage_started_game_seconds=telemetry.at_game_seconds if started is None else started)
            if obs.source_damage_amount > 0:
                memory = replace(memory, stage="retreat", retreat_reason="reported_effect")
        elif telemetry.phase in {"prepare", "approach"} and obs.approach_verified:
            ready = purpose != "coordinate_force" or obs.coordination_verified
            memory = replace(memory, stage="engage" if ready else "prepare")
        elif telemetry.phase == "reserved":
            memory = replace(memory, stage="approach")
    if memory.engage_started_game_seconds is not None and snapshot.game_time_seconds >= memory.engage_started_game_seconds + memory.engage_duration_game_seconds:
        memory = replace(memory, stage="retreat", retreat_reason=memory.retreat_reason or "engage_limit")
    if memory.stage in {"retreat", "await_host_release"}:
        return Recommendation("request_retreat" if memory.stage == "retreat" else "await_release",
                              memory.retreat_reason or "host_retreat_reported", memory)
    if snapshot.paused:
        return Recommendation("wait", "game_paused", memory)
    return Recommendation("continue", "same_task_and_target", memory)


def memory_for_mission(binding, snapshot, mission, *, game_frame, monotonic_ms,
                       issued_monotonic_ms, generation=1, limits=None):
    """Adopt an actual MissionBoard mission without renewing its game/wall limit.

    issued_monotonic_ms must come from the host's original task event. A caller
    that did not retain it must recover the event rather than substitute now.
    This function reads mission state; it never writes or certifies that state.
    """
    limits = limits or Limits()
    if not isinstance(mission, Mission) or not isinstance(binding, Binding) or not isinstance(snapshot, Snapshot):
        raise ContractError("planning_mission_type")
    snapshot = Snapshot.from_dict(snapshot.to_dict())
    if (snapshot.session_id, snapshot.player_id) != (binding.session_id, binding.player_id):
        raise ContractError("planning_snapshot_binding")
    try:
        valid_id = isinstance(mission.task_id, str) and str(uuid.UUID(mission.task_id)) == mission.task_id
    except (ValueError, AttributeError):valid_id = False
    if (mission.purpose not in MODULES or mission.module != MODULES[mission.purpose]
            or mission.mission_id != mission.task_id or not valid_id
            or type(generation) is not int or generation < 1):
        raise ContractError("planning_mission_identity")
    _number(issued_monotonic_ms, 0, monotonic_ms, "planning_mission_clock")
    _number(monotonic_ms, 0, 1e15, "planning_mission_clock")
    _number(mission.created_at_game_seconds, 0, snapshot.game_time_seconds, "planning_mission_time")
    _number(mission.deadline_game_seconds, mission.created_at_game_seconds + 15,
            mission.created_at_game_seconds + 300, "planning_mission_deadline")
    if type(game_frame) is not int or game_frame < 0 or not isinstance(mission.formation_versions, tuple):
        raise ContractError("planning_mission_identity")
    if mission.phase not in PHASES or not isinstance(mission.target_contact_id, str):
        raise ContractError("planning_mission_phase")
    if mission.retreat_region not in snapshot.regions:
        raise ContractError("planning_mission_home")
    stage = "await_host_release" if mission.phase == "restored" else mission.phase
    if stage == "reserved":stage = "approach"
    memory = Memory(binding.session_id, binding.commander_id, binding.player_id, snapshot.source,
                    mission.purpose, generation, mission.task_id, mission.target_contact_id,
                    mission.target_region, mission.retreat_region, mission.formation_versions,
                    mission.required_roles, mission.force_fraction, mission.created_at_game_seconds,
                    mission.deadline_game_seconds, issued_monotonic_ms,
                    issued_monotonic_ms + limits.max_wall_duration_ms, snapshot.game_time_seconds,
                    monotonic_ms, game_frame, stage=stage,
                    retreat_reason=mission.retreat_requested_reason,
                    engage_started_game_seconds=mission.updated_at_game_seconds if stage == "engage" else None,
                    engage_duration_game_seconds=limits.max_engage_game_seconds)
    if mission.last_progress is not None:
        memory, _ = _feedback(memory, mission.last_progress, snapshot)
    return memory


def plan_for_agent(agent, purpose, *, unavailable_formations=(), **kwargs):
    """Read-only BattleAgent adapter; caller retains memory and submits proposals.

    Uses the real agent's latest Snapshot, capability manifest and quarantined /
    in-flight formation projections. Does not alter its goals, context or model.
    A proposed TacticalIntent can enter an existing model policy, then must pass
    validate_policy, TaskCoordinator and MissionBoard / host checks as usual.
    """
    snapshot = agent.latest
    if snapshot is None:
        return Recommendation("wait", "snapshot_unavailable")
    module = MODULES.get(purpose)
    if module is None:
        raise ContractError("planning_task_identity")
    manifest = agent.capability_manifest().get(module, {})
    purposes = manifest.get("verified_purposes", ()) if manifest.get("state") == "planned_only" else ()
    roles = manifest.get("purpose_actor_roles", {}).get(purpose, ())
    unavailable = set(agent.goals.quarantined_formations) | set(unavailable_formations)
    current = kwargs.get("memory")
    if current is None and any(mission.purpose == purpose for mission in agent.missions.active.values()):
        return Recommendation("wait", "active_mission_requires_original_memory")
    for task in agent.goals.tasks:
        if task.status in {"dispatch_pending", "active"} and (current is None or task.task_id != current.task_id):
            unavailable.update(task.request.formation_ids)
    result = plan_for_snapshot(agent.engine.binding, snapshot, purpose, capability_purposes=purposes,
                              allowed_roles=roles, unavailable_formations=unavailable, **kwargs)
    if result.intent is not None:
        target = next(c for c in snapshot.battlefield.contacts if c.contact_id == result.intent.target_contact_id)
        try:
            agent.goals.validate_actor_roles(module, purpose, result.intent.formation_ids,
                result.intent.required_roles, snapshot.battlefield, snapshot.source, target.role)
            agent.missions.validate_intent(module, purpose, result.intent.target_contact_id, snapshot)
        except ContractError:
            return Recommendation("wait", "agent_contract_rejected")
    return result


def plan_batch_for_agent(agent, purposes, *, memories=None, feedback=None, **kwargs):
    """Plan at most three purpose slots without sharing proposed formations.

    Existing mission/TaskCoordinator state is still authoritative. Priority is
    the caller's explicit purpose order; an unavailable slot does not borrow it.
    """
    if not isinstance(purposes, (tuple, list)) or len(purposes) > 3 or len(set(purposes)) != len(purposes):
        raise ContractError("planning_batch_purposes")
    memories, feedback = memories or {}, feedback or {}
    results, claimed = {}, set()
    for purpose in purposes:
        result = plan_for_agent(agent, purpose, memory=memories.get(purpose), feedback=feedback.get(purpose),
                                unavailable_formations=claimed, **kwargs)
        results[purpose] = result
        if result.memory is not None and result.action not in {"closed", "discard"}:
            claimed.update(key for key, _ in result.memory.formation_versions)
    return results


def context_hints(results, *, context, max_bytes=8192):
    """Bounded, model-safe projection; advice memory remains private to its owner.

    The caller may add this as `tactical_planning_advice` before the existing
    BattleAgent context-size/trimming pass. Model output remains independently
    validated against the exact context it received, latest Snapshot and host.
    """
    if not isinstance(results, dict) or len(results) > 3 or set(results) - set(MODULES):
        raise ContractError("planning_hint_results")
    if not isinstance(context, dict) or not isinstance(context.get("working_memory"), dict):
        raise ContractError("planning_hint_context")
    field = context["working_memory"].get("battlefield", {})
    contacts = {item["contact_id"] for item in field.get("contacts", ())}
    formations = {item["formation_id"] for item in field.get("formations", ())}
    regions = set(context.get("allowed_regions", ()))
    if type(max_bytes) is not int or not 256 <= max_bytes <= 16384:
        raise ContractError("planning_hint_budget")
    rows = []
    for purpose, item in results.items():
        if not isinstance(item, Recommendation):raise ContractError("planning_hint_results")
        row = {"purpose": purpose, "action": item.action, "reason_code": item.reason_code,
                     "suggested_stage": item.memory.stage if item.memory else None,
                     "tactical_intent": item.intent.public() if item.intent else None}
        if item.intent is not None and (item.intent.target_contact_id not in contacts
                or not set(item.intent.formation_ids).issubset(formations) or item.intent.target_region not in regions):
            row.update(action="wait", reason_code="omitted_from_model_context", tactical_intent=None)
        rows.append(row)
    value = {"advisory_only": True, "execution_authorized": False, "recommendations": rows}
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")) > max_bytes:
        raise ContractError("planning_hint_budget_exceeded")
    return value
