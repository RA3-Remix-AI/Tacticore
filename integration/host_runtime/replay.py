"""Deterministic orchestration replay from recorded or explicitly synthetic input."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping

from .orchestration import MissionOrchestrator, OrchestrationConfig


@dataclass(frozen=True)
class ReplayResult:
    source: str
    steps: tuple[dict, ...]
    intents: tuple[dict, ...]
    events: tuple[dict, ...]
    final_state: dict
    digest: str


def replay(binding: Mapping, observations: Iterable[Mapping], config: OrchestrationConfig | None = None, *, task_id="task", generation=1, source="synthetic") -> ReplayResult:
    if source not in ("synthetic", "recorded"):
        raise ValueError("invalid_replay_source")
    machine = MissionOrchestrator(binding, config, task_id=task_id, generation=generation)
    steps, intents, events = [], [], []
    for observation in observations:
        result = machine.advance(observation)
        steps.append(result.public())
        intents.extend(result.intents)
        events.extend(result.events)
    final = machine.public()
    body = dict(source=source, steps=steps, final_state=final)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return ReplayResult(source, tuple(steps), tuple(intents), tuple(events), final, digest)
