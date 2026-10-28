"""Repeatable mission bookkeeping, independent from game execution and grants.

Only the host's trusted adapters may supply ReceiptEvidence. This module checks
identity, ordering and completion semantics; it does not verify raw game proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Callable, Mapping


class LifecycleError(ValueError):
    pass


def _id(value: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise LifecycleError("invalid_identifier")
    return value


def _integer(value: int) -> int:
    if type(value) is not int or value < 0:
        raise LifecycleError("invalid_clock_or_generation")
    return value


@dataclass(frozen=True)
class ReceiptEvidence:
    session_id: str
    task_id: str
    generation: int
    game_frame: int
    effect_verified: bool = False
    physical_return_verified: bool = False
    control_release_verified: bool = False
    source_reference: str = ""

    def __post_init__(self):
        _id(self.session_id); _id(self.task_id); _integer(self.game_frame)
        if type(self.generation) is not int or self.generation < 1:
            raise LifecycleError("invalid_generation")
        for key in ("effect_verified", "physical_return_verified", "control_release_verified"):
            if type(getattr(self, key)) is not bool:
                raise LifecycleError("invalid_evidence_flag")
        if not self.source_reference or type(self.source_reference) is not str or len(self.source_reference) > 512:
            raise LifecycleError("evidence_reference_required")


_TRANSITIONS = {
    "proposed": {"validating"},
    "validating": {"planning"},
    "planning": {"preparing"},
    "preparing": {"ready"},
    "ready": {"committing"},
    "committing": {"accepted", "uncertain"},
    "accepted": {"executing", "returning", "uncertain"},
    "executing": {"returning", "uncertain"},
    "returning": {"uncertain"},
    "uncertain": set(),
    "released": set(),
    "completed": set(), "failed": set(), "cancelled": set(),
}
_PRE_DISPATCH = {"proposed", "validating", "planning", "preparing", "ready"}
_TERMINAL = {"completed", "failed", "cancelled"}


class MissionLifecycle:
    """A mission's state, with completion distinct from release and safe failure.

    ``advance`` records host decisions, not authority to execute. A commit may
    have escaped once ``committing`` is entered; termination then needs a trusted
    release receipt even if its result was unknown or the caller was cancelled.
    """

    def __init__(self, session_id: str, task_id: str, generation: int, *,
                 game_frame: int = 0, monotonic_ms: int = 0,
                 event_sink: Callable[[dict], None] | None = None):
        self.session_id = _id(session_id); self.task_id = _id(task_id)
        if type(generation) is not int or generation < 1:
            raise LifecycleError("invalid_generation")
        self.generation = generation
        self.state = "proposed"
        self.last_frame = _integer(game_frame)
        self.last_monotonic_ms = _integer(monotonic_ms)
        self.reason_code = "proposed"
        self.evidence: ReceiptEvidence | None = None
        self._events: list[dict] = []
        self._sink = event_sink
        self._pending_result: str | None = None

    def _clock(self, game_frame: int, monotonic_ms: int):
        if _integer(game_frame) < self.last_frame or _integer(monotonic_ms) < self.last_monotonic_ms:
            raise LifecycleError("clock_regressed")

    def _change(self, state: str, reason_code: str, game_frame: int, monotonic_ms: int):
        self._clock(game_frame, monotonic_ms); _id(reason_code)
        event = dict(session_id=self.session_id, task_id=self.task_id,
                     generation=self.generation, event_type="mission_state_changed",
                     prior_state=self.state, state=state, reason_code=reason_code,
                     game_frame=game_frame, monotonic_ms=monotonic_ms)
        # A durable sink must accept the event before its projection changes.
        if self._sink is not None:
            self._sink(dict(event))
        self._events.append(event)
        self.state = state; self.reason_code = reason_code
        self.last_frame = game_frame; self.last_monotonic_ms = monotonic_ms

    def advance(self, state: str, *, reason_code: str, game_frame: int, monotonic_ms: int):
        if state not in _TRANSITIONS.get(self.state, set()):
            raise LifecycleError("invalid_state_transition")
        self._change(state, reason_code, game_frame, monotonic_ms)
        return self.public()

    def request_stop(self, *, reason_code: str, game_frame: int, monotonic_ms: int,
                     failed: bool = False):
        if type(failed) is not bool:
            raise LifecycleError("invalid_failure_flag")
        desired = "failed" if failed else "cancelled"
        if self.state in _TERMINAL:
            return self.public()
        if self.state == "released":
            self._change(desired, reason_code, game_frame, monotonic_ms)
        elif self.state in _PRE_DISPATCH:
            self._change(desired, reason_code, game_frame, monotonic_ms)
        elif self.state == "committing" or self.state == "uncertain":
            self._change("uncertain", reason_code, game_frame, monotonic_ms)
            self._pending_result = desired
        else:
            self._change("returning", reason_code, game_frame, monotonic_ms)
            self._pending_result = desired
        return self.public()

    def record_release(self, evidence: ReceiptEvidence, *, monotonic_ms: int):
        if not isinstance(evidence, ReceiptEvidence):
            raise LifecycleError("trusted_receipt_type_required")
        if (evidence.session_id, evidence.task_id, evidence.generation) != (
                self.session_id, self.task_id, self.generation):
            raise LifecycleError("receipt_identity_mismatch")
        if self.state not in {"accepted", "executing", "returning", "uncertain"}:
            raise LifecycleError("release_not_expected")
        if not evidence.control_release_verified:
            raise LifecycleError("release_unverified")
        self._change("released", "control_release_verified", evidence.game_frame, monotonic_ms)
        self.evidence = evidence
        if self._pending_result is not None:
            self._change(self._pending_result, "stop_reconciled", evidence.game_frame, monotonic_ms)
        return self.public()

    def finish(self, *, game_frame: int, monotonic_ms: int):
        if self.state != "released" or self.evidence is None:
            raise LifecycleError("completion_requires_release")
        success = (self.evidence.effect_verified and self.evidence.physical_return_verified
                   and self.evidence.control_release_verified)
        self._change("completed" if success else "failed",
                     "effect_return_release_verified" if success else "mission_effect_or_return_unverified",
                     game_frame, monotonic_ms)
        return self.public()

    def public(self):
        return dict(session_id=self.session_id, task_id=self.task_id, generation=self.generation,
                    state=self.state, reason_code=self.reason_code, game_frame=self.last_frame,
                    monotonic_ms=self.last_monotonic_ms, terminal=self.state in _TERMINAL,
                    effect_verified=bool(self.evidence and self.evidence.effect_verified),
                    physical_return_verified=bool(self.evidence and self.evidence.physical_return_verified),
                    control_release_verified=bool(self.evidence and self.evidence.control_release_verified))

    def events(self):
        return [dict(event) for event in self._events]


class MissionRegistry:
    """Multiple serial/concurrent task records without the old one-shot latch."""

    def __init__(self, session_id: str):
        self.session_id = _id(session_id)
        self._missions: dict[str, MissionLifecycle] = {}

    def create(self, task_id: str, generation: int, **kwargs) -> MissionLifecycle:
        _id(task_id)
        if task_id in self._missions:
            existing = self._missions[task_id]
            if existing.generation != generation:
                raise LifecycleError("task_id_reused_with_new_generation")
            return existing
        mission = MissionLifecycle(self.session_id, task_id, generation, **kwargs)
        self._missions[task_id] = mission
        return mission

    def snapshot(self):
        return [self._missions[key].public() for key in sorted(self._missions)]
