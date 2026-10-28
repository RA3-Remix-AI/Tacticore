"""Compose pure orchestration with durable events and the native gateway.

Callers supply host-verified observation/receipt projections. The coordinator is
not exposed directly to a WebView or model and is not a source of game evidence.
"""
from __future__ import annotations

from dataclasses import asdict
import copy
from typing import Mapping

from .contracts import ContractError, SessionBinding, content_hash, identifier
from .gateway import ExecutionGateway
from .limits import ExecutionLimits
from .orchestration import MissionOrchestrator, OrchestrationConfig


class HostCoordinator:
    def __init__(self, gateway: ExecutionGateway, *, config: OrchestrationConfig | None = None,
                 execution_limits: ExecutionLimits | None = None):
        self.gateway = gateway
        self.config = config or OrchestrationConfig()
        self.execution_limits = execution_limits or ExecutionLimits()
        self._tasks: dict[str, MissionOrchestrator] = {}
        self._active: str | None = None
        self._receipts: dict[str, list[dict]] = {}
        self._issued_metadata: dict[str, dict] = {}
        self._last_clock: tuple[int, int] | None = None

    def create_task(self, task_id: str, generation: int = 1):
        identifier(task_id)
        if task_id in self._tasks:
            if self._tasks[task_id].generation != generation:
                raise ContractError("task_identity_conflict")
            return self._tasks[task_id].public()
        if self._active is not None:
            active = self._tasks[self._active]
            if active.state not in active.TERMINAL:
                raise ContractError("active_task_not_released")
            if any(command['payload'].get('task_id') == self._active
                   for command in self.gateway.journal.unresolved(self.gateway.run_id)):
                raise ContractError("prior_task_command_unresolved")
        binding = {"run_id": self.gateway.run_id, **self.gateway.binding.public()}
        machine = MissionOrchestrator(binding, self.config, task_id=task_id, generation=generation)
        self.gateway.journal.append_event(self.gateway.run_id, "task_created",
            dict(task_id=task_id, generation=generation, config=asdict(self.config)))
        self._tasks[task_id] = machine
        self._receipts[task_id] = []
        self._active = task_id
        return machine.public()

    def _validate_observation(self, observation: Mapping):
        if not isinstance(observation, Mapping):
            raise ContractError("observation_required")
        if observation.get('session_binding_hash') != self.gateway.binding.binding_hash:
            raise ContractError("observation_binding_mismatch")
        if observation.get('session_id') != self.gateway.binding.session_id:
            raise ContractError("observation_session_mismatch")
        if observation.get('source') != 'game_bridge' and getattr(self.gateway.adapter, 'test_only', False) is not True:
            raise ContractError("simulated_observation_cannot_reach_live_adapter")
        frame, wall = observation.get('game_frame'), observation.get('monotonic_ms')
        if type(frame) is not int or type(wall) is not int or frame < 0 or wall < 0:
            raise ContractError("observation_clock_invalid")
        if self._last_clock and (frame < self._last_clock[0] or wall < self._last_clock[1]):
            raise ContractError("observation_clock_regressed")

    def tick(self, observation: Mapping):
        if self._active is None:
            raise ContractError("no_active_task")
        self._validate_observation(observation)
        task_id = self._active
        normalized = copy.deepcopy(dict(observation))
        normalized['receipts'] = [*normalized.get('receipts', ()), *self._receipts[task_id]]
        # Advance a disposable projection. Failed event persistence cannot leave
        # in-memory commands marked sent while their durable intent is absent.
        candidate = copy.deepcopy(self._tasks[task_id])
        step = candidate.advance(normalized)
        payload = dict(task_id=task_id, generation=candidate.generation,
                       observation=normalized, result=step.public(), result_hash=content_hash(step.public()))
        self.gateway.journal.append_event(self.gateway.run_id, "orchestration_step", payload,
            game_frame=normalized['game_frame'], monotonic_ns=normalized['monotonic_ms'] * 1_000_000)
        self._tasks[task_id] = candidate
        self._receipts[task_id] = []
        self._last_clock = normalized['game_frame'], normalized['monotonic_ms']
        results = []
        for intent in step.intents:
            self._issued_metadata[intent['request_id']] = dict(intent)
            body = dict(intent['payload'], task_id=task_id, generation=candidate.generation,
                        lease_id=intent['lease_id'], plan_id=intent['plan_id'],
                        observed_frame=normalized['game_frame'], monotonic_ms=normalized['monotonic_ms'])
            if intent['operation'] == 'commit':
                body['purpose'] = 'coordinate_force'
            if intent['operation'] == 'produce':
                plan = normalized.get('plan', {})
                expiry = plan.get('expires_frame', normalized['game_frame'] + 900)
                body['expires_frame'] = min(expiry, normalized['game_frame'] + 900)
                body['budget'] = min(body['max_cost'], self.execution_limits.max_command_budget)
                body['reserve'] = self.execution_limits.reserve_floor
            record = self.gateway.submit(intent['request_id'], intent['operation'], body)
            self._queue_receipt(intent, record)
            results.append(record)
        return dict(task=candidate.public(), step=step.public(), command_results=results,
                    observation_source=observation.get('source'), physical_evidence_granted=False)

    def _queue_receipt(self, intent, record):
        if record['status'] == 'reserved':
            return
        facts = record.get('receipt') or {}
        native = facts.get('facts', {})
        if not isinstance(native, Mapping):
            native = {}
        result = dict(native)
        # Native facts cannot override host-owned request/task binding.
        result.update(request_id=intent['request_id'], session_id=self.gateway.binding.session_id,
                      task_id=intent['task_id'], generation=intent['generation'], status=record['status'])
        self._receipts[intent['task_id']].append(result)

    def observe_command(self, request_id: str, *, status: str, facts: Mapping):
        """Persist a trusted adapter's later receipt, not an untrusted UI report."""
        identifier(request_id)
        if request_id not in self._issued_metadata:
            raise ContractError("unknown_task_request")
        record = self.gateway.journal.record_outcome(self.gateway.run_id, request_id, status,
            {"reason_code": "native_receipt_verified", "facts": dict(facts)})
        self._queue_receipt(self._issued_metadata[request_id], record)
        return record

    def snapshot(self):
        return dict(run_id=self.gateway.run_id, binding=self.gateway.binding.public(),
                    active_task_id=self._active,
                    tasks=[self._tasks[key].public() for key in sorted(self._tasks)],
                    unresolved_commands=self.gateway.journal.unresolved(self.gateway.run_id),
                    execution_authority_granted=False)
