"""Clock-injected preparation/commit orchestration; emits intents, never SDK calls.

The owner validates actual capabilities and journals each intent before sending it.
Receipts passed here must already be normalized by that owner. These pure states
do not manufacture executable capabilities or claim physical game evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping
import uuid

from .selector import SelectionProfile, select_target


@dataclass(frozen=True)
class OrchestrationConfig:
    slots: tuple[tuple[str, str, int], ...] = (("infantry", "conscript", 85), ("anti_air", "flak", 220))
    selection: SelectionProfile = field(default_factory=SelectionProfile)
    opportunity_timeout_ms: int = 60000
    preparation_timeout_ms: int = 60000
    command_timeout_ms: int = 5000
    production_gap_frames: int = 150
    reserve_frames: int = 450
    hard_frames: int = 4500
    require_plan: bool = True

    def __post_init__(self):
        for key in ("opportunity_timeout_ms", "preparation_timeout_ms", "command_timeout_ms", "reserve_frames", "hard_frames"):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError("invalid_orchestration_config")
        if self.reserve_frames >= self.hard_frames or type(self.production_gap_frames) is not int or self.production_gap_frames < 0:
            raise ValueError("invalid_orchestration_config")
        if not self.slots or len({r for r, _, _ in self.slots}) != len(self.slots):
            raise ValueError("invalid_slots")
        for role, unit, cost in self.slots:
            if not role or not unit or type(cost) is not int or cost <= 0:
                raise ValueError("invalid_slots")


@dataclass(frozen=True)
class StepResult:
    state: str
    intents: tuple[dict, ...]
    events: tuple[dict, ...]
    reason_code: str | None

    def public(self):
        return {"state": self.state, "intents": list(self.intents),
                "events": list(self.events), "reason_code": self.reason_code}


class MissionOrchestrator:
    """One task instance; a host may create task B after task A is released.

    ``advance`` consumes JSON-like observations with explicit ``game_frame`` and
    ``monotonic_ms``. It does no sleeping, networking, game I/O or implicit retry.
    Each intent has deterministic task/request IDs and a frozen generation.
    """
    TERMINAL = frozenset(("completed", "failed", "cancelled"))

    def __init__(self, binding: Mapping, config: OrchestrationConfig | None = None, *, task_id: str = "task", generation: int = 1):
        self.binding = {k: binding.get(k) for k in ("run_id", "session_id", "commander_id", "player_id")}
        if any(not isinstance(self.binding[k], str) or not self.binding[k] for k in ("run_id", "session_id", "commander_id")) or type(self.binding["player_id"]) is not int or not 0 <= self.binding["player_id"] <= 15:
            raise ValueError("invalid_binding")
        if not isinstance(task_id, str) or not task_id or type(generation) is not int or generation < 1:
            raise ValueError("invalid_task_identity")
        self.config = config or OrchestrationConfig()
        self.task_id, self.generation = task_id, generation
        self.lease_id = self._id("lease", "")
        self.state = "waiting_opportunity"
        self.reason_code = None
        self._first_clock = self._last_clock = None
        self._phase_clock = None
        self._seq = 0
        self._issued: dict[str, dict] = {}
        self._receipts: dict[str, dict] = {}
        self._bound_actors: dict[str, tuple[int, int]] = {}
        self._lease_start = None
        self._plan_id = None
        self._stop_result = "cancelled"
        self._intents = []
        self._events = []

    def _id(self, operation, role):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join((self.binding["run_id"], self.task_id, str(self.generation), operation, role))))

    def _event(self, event_type, reason_code, **payload):
        self._seq += 1
        frame, wall = self._last_clock
        self._events.append(dict(self.binding, task_id=self.task_id, generation=self.generation,
                                 sequence=self._seq, game_frame=frame, monotonic_ms=wall,
                                 stage=self.state, event_type=event_type, reason_code=reason_code, **payload))

    def _transition(self, state, reason):
        self.state, self.reason_code = state, reason
        self._phase_clock = self._last_clock
        self._event("state_changed", reason)

    def _emit(self, operation, *, role="", **payload):
        ident = self._id(operation, role)
        if ident in self._issued:
            return
        value = dict(self.binding, request_id=ident, task_id=self.task_id,
                     generation=self.generation, operation=operation, role=role,
                     lease_id=self.lease_id, plan_id=self._plan_id, payload=payload, selection_only=True,
                     authority_granted=False)
        self._issued[ident] = {"intent": value, "at": self._last_clock}
        self._intents.append(value)
        self._event("intent_created", "pending_transport_validation", request_id=ident, operation=operation)

    def _receipt(self, operation, role=""):
        return self._receipts.get(self._id(operation, role))

    def _uncertain(self, reason):
        if self.state != "uncertain":
            self._transition("uncertain", reason)
        self._emit("query_status", issued_request_ids=sorted(self._issued))

    def _ingest_receipts(self, observation):
        for receipt in observation.get("receipts", ()):
            if not isinstance(receipt, Mapping) or receipt.get("request_id") not in self._issued:
                self._event("receipt_ignored", "unknown_request_id")
                continue
            ident = receipt["request_id"]
            if receipt.get("session_id") != self.binding["session_id"] or receipt.get("task_id") != self.task_id or receipt.get("generation") != self.generation:
                self._uncertain("receipt_binding_mismatch")
                return
            status = receipt.get("status")
            if status not in ("accepted", "started", "completed", "rejected", "failed", "released", "uncertain"):
                self._uncertain("invalid_receipt_status")
                return
            prior = self._receipts.get(ident)
            if prior == dict(receipt):
                continue
            if prior and prior.get("status") in ("completed", "rejected", "failed", "released"):
                self._uncertain("terminal_receipt_changed")
                return
            if prior and prior.get("status") == "started" and status == "accepted":
                self._uncertain("receipt_regressed")
                return
            if prior and any(key in prior and key in receipt and prior[key] != receipt[key]
                             for key in ("object_id", "actor_generation", "lease_issued_frame", "enqueue_frame")):
                self._uncertain("receipt_identity_changed")
                return
            self._receipts[ident] = dict(receipt)
            self._event("receipt_observed", status, request_id=ident)
            if status == "uncertain":
                self._uncertain("delivery_unknown")
                return

    def _plan_ok(self, observation):
        if not self.config.require_plan:
            return True
        plan = observation.get("plan")
        if not isinstance(plan, Mapping):
            self._event("plan_wait", "plan_missing")
            return False
        frame, wall = self._last_clock
        valid = (plan.get("session_id") == self.binding["session_id"]
                 and plan.get("task_id") == self.task_id and plan.get("generation") == self.generation
                 and isinstance(plan.get("plan_id"), str) and bool(plan["plan_id"])
                 and (self._plan_id is None or self._plan_id == plan["plan_id"])
                 and type(plan.get("expires_frame")) is int and frame < plan["expires_frame"]
                 and type(plan.get("valid_until_monotonic_ms")) in (int, float)
                 and math.isfinite(plan["valid_until_monotonic_ms"]) and wall < plan["valid_until_monotonic_ms"])
        if not valid:
            self._event("plan_wait", "plan_stale_or_wrong_binding")
        else:
            self._plan_id = plan["plan_id"]
        return valid

    def _actors(self, observation):
        result = {}
        for actor in observation.get("actors", ()):
            if not isinstance(actor, Mapping) or actor.get("role") in result:
                raise ValueError("invalid_actor_projection")
            identity = (actor.get("object_id"), actor.get("generation"))
            if any(type(n) is not int for n in identity) or identity[0] <= 0 or identity[1] < 0 or actor.get("owner_player_id") != self.binding["player_id"]:
                raise ValueError("invalid_actor_identity")
            if actor["role"] in self._bound_actors and self._bound_actors[actor["role"]] != identity:
                self._uncertain("actor_identity_reused")
            result[actor["role"]] = actor
        return result

    def _begin_return(self, observation, reason, outcome="failed"):
        self._stop_result = outcome
        held = [a for a in observation.get("actors", ()) if a.get("held") is True]
        if held or self._lease_start is not None:
            self._transition("returning", reason)
            self._emit("stop", reason_code=reason, actor_identities=dict(self._bound_actors))
        elif any(ident not in self._receipts for ident, item in self._issued.items() if item["intent"]["operation"] != "query_status"):
            self._uncertain("stop_with_pending_command")
        else:
            self._transition(outcome, reason)

    def _pending_timeout(self):
        frame, wall = self._last_clock
        for ident, item in self._issued.items():
            if item["intent"]["operation"] == "query_status" or ident in self._receipts:
                continue
            if wall - item["at"][1] >= self.config.command_timeout_ms:
                self._uncertain("command_ack_timeout")
                return True
        return False

    def advance(self, observation: Mapping) -> StepResult:
        if not isinstance(observation, Mapping):
            raise ValueError("invalid_observation")
        frame, wall = observation.get("game_frame"), observation.get("monotonic_ms")
        if type(frame) is not int or frame < 0 or type(wall) not in (int, float) or not math.isfinite(wall) or wall < 0:
            raise ValueError("invalid_clock")
        if self._last_clock and (frame < self._last_clock[0] or wall < self._last_clock[1]):
            raise ValueError("clock_moved_backwards")
        self._last_clock = frame, wall
        self._first_clock = self._first_clock or self._last_clock
        self._intents, self._events = [], []
        if self.state in self.TERMINAL:
            return self._result()
        if observation.get("session_id") != self.binding["session_id"]:
            self._uncertain("session_changed")
            return self._result()
        self._ingest_receipts(observation)
        if self.state == "uncertain":
            return self._result()
        actors = self._actors(observation)
        if self.state == "uncertain":
            return self._result()
        if observation.get("stop_requested") is True:
            if self.state != "returning":
                self._begin_return(observation, "user_stop", "cancelled")
        if self.state == "returning":
            terminal = observation.get("terminal", {})
            if terminal.get("release_verified") is True and terminal.get("session_id") == self.binding["session_id"] and terminal.get("lease_id") == self.lease_id and all(a.get("held") is not True for a in actors.values()):
                self._transition(self._stop_result, self.reason_code or "released")
            elif self._pending_timeout():
                pass
            elif self._phase_clock and wall - self._phase_clock[1] >= self.config.preparation_timeout_ms:
                self._uncertain("release_timeout")
            return self._result()
        if self._pending_timeout():
            return self._result()
        if observation.get("paused") is True:
            self._event("waiting", "game_paused")
            return self._result()
        if self._lease_start is not None and frame >= self._lease_start + self.config.hard_frames:
            self._begin_return(observation, "hard_deadline")
            return self._result()
        if self.state == "executing":
            terminal = observation.get("terminal", {})
            if terminal.get("session_id") == self.binding["session_id"] and terminal.get("lease_id") == self.lease_id and terminal.get("release_verified") is True:
                success = all(terminal.get(k) is True for k in ("effect_verified", "home_verified", "release_verified"))
                if any(a.get("held") is True for a in actors.values()):
                    self._uncertain("release_actor_still_held")
                else:
                    self._transition("completed" if success else "failed", "effect_home_release_verified" if success else "mission_effect_or_home_unverified")
            return self._result()
        if self.state == "committing":
            receipt = self._receipt("commit")
            if receipt:
                if receipt["status"] in ("accepted", "started", "completed"):
                    self._transition("executing", "commit_accepted")
                elif receipt["status"] in ("rejected", "failed"):
                    self._begin_return(observation, "commit_rejected")
            return self._result()
        selection = select_target(observation.get("contacts", []), observation.get("anchors", []), game_frame=frame, own_view_verified=observation.get("own_view_verified") is True, profile=self.config.selection)
        self._event("target_selection", selection.reason_code, selection=selection.public())
        if self.state == "waiting_opportunity":
            if wall - self._first_clock[1] >= self.config.opportunity_timeout_ms:
                self._transition("failed", "opportunity_timeout")
            elif selection.selected and self._plan_ok(observation):
                self._transition("producing", "opportunity_and_plan_ready")
                role, unit, cost = self.config.slots[0]
                self._emit("produce", role=role, unit=unit, max_cost=cost)
            return self._result()
        if not selection.selected:
            self._begin_return(observation, "opportunity_lost")
            return self._result()
        if self._phase_clock and wall - self._phase_clock[1] >= self.config.preparation_timeout_ms:
            self._begin_return(observation, "preparation_timeout")
            return self._result()
        if self.state == "producing":
            complete = []
            for index, (role, unit, cost) in enumerate(self.config.slots):
                receipt = self._receipt("produce", role)
                if receipt is None:
                    if index and self._receipt("produce", self.config.slots[index-1][0]):
                        prior = self._receipt("produce", self.config.slots[index-1][0])
                        enqueued = prior.get("enqueue_frame")
                        if (type(enqueued) is int and frame >= enqueued + self.config.production_gap_frames
                                and self._plan_ok(observation)):
                            self._emit("produce", role=role, unit=unit, max_cost=cost)
                    break
                if receipt["status"] in ("rejected", "failed"):
                    self._begin_return(observation, "production_rejected")
                    break
                if receipt["status"] == "completed":
                    actor = actors.get(role)
                    identity = (receipt.get("object_id"), receipt.get("actor_generation"))
                    if receipt.get("paid_verified") is not True or receipt.get("created") is not True or receipt.get("paid") != cost:
                        self._begin_return(observation, "production_payment_unverified")
                        break
                    if not actor or actor.get("ground_ready") is not True:
                        self._event("waiting", "spawn_transition", role=role)
                        continue
                    if identity != (actor["object_id"], actor["generation"]):
                        self._uncertain("production_actor_mismatch")
                        break
                    complete.append((role, identity))
            if len(complete) == len(self.config.slots) and self._plan_ok(observation):
                if len({identity for _, identity in complete}) != len(complete):
                    self._uncertain("duplicate_paid_actor")
                else:
                    self._bound_actors = dict(complete)
                    self._transition("preparing", "paid_actors_ready")
                    self._emit("reserve", actor_identities=dict(self._bound_actors))
        elif self.state == "preparing":
            receipt = self._receipt("reserve")
            if receipt and receipt["status"] in ("rejected", "failed"):
                self._begin_return(observation, "reserve_rejected")
            elif receipt and receipt["status"] in ("accepted", "started", "completed"):
                start = receipt.get("lease_issued_frame")
                if type(start) is not int or start < 0 or start > frame or self._lease_start is not None and start != self._lease_start:
                    self._uncertain("invalid_lease_clock")
                else:
                    self._lease_start = start
                    if frame >= start + self.config.reserve_frames:
                        self._begin_return(observation, "precommit_deadline")
                    elif all(role in actors and actors[role].get("alive") is True and actors[role].get("held") is True and actors[role].get("ready") is True and actors[role].get("lease_id") == self.lease_id for role in self._bound_actors) and self._plan_ok(observation):
                        self._transition("committing", "ready_and_current_target")
                        self._emit("commit", target=selection.selected, actor_identities=dict(self._bound_actors), reserve_deadline_frame=start+self.config.reserve_frames, hard_deadline_frame=start+self.config.hard_frames)
        return self._result()

    def _result(self):
        return StepResult(self.state, tuple(self._intents), tuple(self._events), self.reason_code)

    def public(self):
        return dict(self.binding, task_id=self.task_id, generation=self.generation,
                    lease_id=self.lease_id, state=self.state, reason_code=self.reason_code,
                    issued_request_ids=sorted(self._issued), actor_identities=dict(self._bound_actors),
                    lease_start_frame=self._lease_start, plan_id=self._plan_id, authority_granted=False)
