"""Durable, capability-bound gateway to trusted native adapters.

The adapter is a host-owned boundary: it must verify current game identity,
command admission, and native receipt evidence. UI/model dictionaries never
serve as adapters or proof. This module issues no game calls by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .capabilities import CapabilityCatalog
from .contracts import ContractError, SessionBinding, identifier, object_fields, text
from .journal import CommandJournal, TransitionError


class AdmissionRefused(ValueError):
    """Definitive refusal before any command can have escaped."""
    def __init__(self, reason_code: str):
        self.reason_code = text(reason_code, 100)
        super().__init__(self.reason_code)


@dataclass(frozen=True)
class NativeReceipt:
    command_id: str
    session_binding_hash: str
    status: str
    facts: Mapping


class TrustedExecutor(Protocol):
    def preflight(self, command: Mapping, binding: SessionBinding) -> None:
        """Verify current binding and scope before side effects; otherwise refuse."""
    def dispatch(self, command: Mapping, binding: SessionBinding) -> NativeReceipt:
        """Send at most once and return an independently checked native receipt."""


def required_capability(operation: str, payload: Mapping) -> str | None:
    if operation == "produce":
        unit = payload.get("unit")
        if unit not in ("conscript", "flak"):
            raise ContractError("production_unit_unsupported")
        return "production.infantry" if unit == "conscript" else "production.anti_air"
    if operation == "reserve":
        purpose = payload.get("purpose", "coordinate_force")
        try:
            return {"coordinate_force": "tactics.coordinate_force", "main_attack": "tactics.attack",
                    "harass_economy": "tactics.harass_economy", "move_hold_return": "tactics.move_hold_return"}[purpose]
        except (KeyError, TypeError):
            raise ContractError("mission_purpose_unsupported") from None
    if operation == "commit":
        purpose = payload.get("purpose")
        try:
            return {"coordinate_force": "tactics.coordinate_force", "main_attack": "tactics.attack",
                    "harass_economy": "tactics.harass_economy", "move_hold_return": "tactics.move_hold_return"}[purpose]
        except (KeyError, TypeError):
            raise ContractError("mission_purpose_unsupported") from None
    if operation == "reconcile_return_home":
        return "tactics.reconcile_return_home"
    if operation in ("return", "stop", "query_status", "reconcile_release"):
        # Revoking a capability must not prevent release of existing ownership.
        # The trusted adapter still verifies the exact old lease/actors/binding.
        return None
    raise ContractError("operation_unsupported")


class ExecutionGateway:
    def __init__(self, run_id: str, binding: SessionBinding, journal: CommandJournal,
                 capabilities: CapabilityCatalog, adapter: TrustedExecutor):
        if not isinstance(binding, SessionBinding) or not isinstance(capabilities, CapabilityCatalog):
            raise ContractError("gateway_binding_or_catalog_invalid")
        if not callable(getattr(adapter, "preflight", None)) or not callable(getattr(adapter, "dispatch", None)):
            raise ContractError("trusted_executor_required")
        self.run_id = identifier(run_id)
        self.binding = binding
        self.journal = journal
        self.capabilities = capabilities
        self.adapter = adapter
        self.journal.register_run(self.run_id, self.binding.public())

    def submit(self, request_id: str, operation: str, payload: Mapping) -> dict:
        identifier(request_id)
        if not isinstance(payload, Mapping):
            raise ContractError("command_payload_required")
        if "session_id" in payload and payload["session_id"] != self.binding.session_id:
            raise ContractError("command_session_mismatch")
        if "player_id" in payload and (type(payload["player_id"]) is not int or payload["player_id"] != self.binding.player_id):
            raise ContractError("command_player_mismatch")
        if "commander_id" in payload and payload["commander_id"] != self.binding.commander_id:
            raise ContractError("command_commander_mismatch")
        # reserve_command also rejects credential-bearing payloads before I/O.
        record = self.journal.reserve_command(self.run_id, request_id, operation, payload)
        if record["created"] is False:
            return record
        return self._dispatch_reserved(record)

    def resume_reserved(self, request_id: str) -> dict:
        """Explicit recovery only for an intent provably never claimed to send.

        Unknown/in-flight commands cannot use this route. Admission and evidence
        are checked afresh; callers must separately reconcile prior host identity.
        """
        record = self.journal.get_command(self.run_id, request_id)
        if record["status"] != "reserved":
            raise TransitionError("only_unsent_reserved_command_can_resume")
        return self._dispatch_reserved(record)

    def _dispatch_reserved(self, record: Mapping) -> dict:
        request_id = record['request_id']
        operation = record['operation']
        payload = record['payload']
        capability = None
        try:
            capability = required_capability(operation, payload)
            grant = self.capabilities.require(capability, self.binding) if capability else None
        except ContractError as error:
            return self.journal.record_outcome(self.run_id, request_id, "rejected",
                                               {"reason_code": error.code, "capability_id": capability})
        command = dict(command_id=record["command_id"], request_id=request_id,
                       run_id=self.run_id, session_id=self.binding.session_id,
                       player_id=self.binding.player_id, commander_id=self.binding.commander_id,
                       operation=operation, payload=dict(payload),
                       capability=grant.public() if grant else None)
        try:
            self.adapter.preflight(command, self.binding)
        except AdmissionRefused as refusal:
            return self.journal.record_outcome(self.run_id, request_id, "rejected",
                                               {"reason_code": refusal.reason_code})
        except Exception:
            # preflight contract forbids side effects; do not log provider text.
            return self.journal.record_outcome(self.run_id, request_id, "rejected",
                                               {"reason_code": "executor_preflight_failed"})
        self.journal.mark_dispatching(self.run_id, request_id)
        try:
            receipt = self.adapter.dispatch(command, self.binding)
        except AdmissionRefused as refusal:
            return self.journal.record_outcome(self.run_id, request_id, "rejected",
                                               {"reason_code": refusal.reason_code})
        except BaseException as error:
            # Even cancellation can arrive after the command escaped. Persist
            # uncertainty first, then preserve cancellation/termination semantics.
            result = self.journal.record_outcome(self.run_id, request_id, "uncertain",
                                                 {"reason_code": "dispatch_delivery_unknown"})
            if not isinstance(error, Exception):
                raise
            return result
        if (not isinstance(receipt, NativeReceipt)
                or receipt.command_id != record["command_id"]
                or receipt.session_binding_hash != self.binding.binding_hash
                or receipt.status not in {"accepted", "started", "completed", "released", "rejected", "failed", "uncertain"}
                or not isinstance(receipt.facts, Mapping)):
            return self.journal.record_outcome(self.run_id, request_id, "uncertain",
                                               {"reason_code": "native_receipt_identity_or_status_invalid"})
        try:
            return self.journal.record_outcome(self.run_id, request_id, receipt.status,
                                               {"reason_code": "native_receipt_verified", "facts": dict(receipt.facts)})
        except (TypeError, ValueError):
            return self.journal.record_outcome(self.run_id, request_id, "uncertain",
                                               {"reason_code": "native_receipt_not_persistable"})
