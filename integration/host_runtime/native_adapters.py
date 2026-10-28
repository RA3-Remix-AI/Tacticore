"""Scoped adapter to an already started persistent production executor.

Importing this module neither imports Win32 game readers nor attaches an executor.
The default checks lazily reuse the existing package, owner and command validators.
Injected checks are an explicit test boundary and are labelled in every receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
from typing import Mapping

from .capabilities import CapabilityCatalog
from .contracts import ContractError, SessionBinding, identifier, integer, object_fields
from .gateway import AdmissionRefused, NativeReceipt
from .limits import ExecutionLimits

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "production/persistent/client.py"
RUNTIME_FAMILY = "production_persistent_v2"


@dataclass(frozen=True)
class AdmissionSnapshot:
    game_frame: int
    paused: bool
    native_last_sequence: int
    executor_sha256: str


def _refuse(reason):
    raise AdmissionRefused(reason)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _legacy_module():
    name = "tacticore_host_runtime_persistent_native_adapter"
    module = sys.modules.get(name)
    if module is not None:
        if Path(module.__file__).resolve() != CLIENT:
            _refuse("production_module_identity_changed")
        return module
    spec = importlib.util.spec_from_file_location(name, CLIENT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


class ExistingProductionChecks:
    """Actual read-only admission, using the executor's existing game handle."""
    test_only = False

    def admit(self, executor, binding: SessionBinding, operation: str) -> AdmissionSnapshot:
        owner_module = sys.modules.get(type(executor).__module__)
        if (type(executor).__name__ != "ProductionExecutor" or owner_module is None
                or Path(owner_module.__file__).resolve() != CLIENT):
            _refuse("existing_production_executor_required")
        legacy = _legacy_module()
        if executor.shared is None or executor.memory is None or executor.host is None:
            _refuse("production_executor_not_attached")
        if executor.host.poll() is not None and operation != "stop":
            _refuse("production_host_not_running")
        memory = executor.memory
        if memory.pid != binding.game_process_id or _digest(memory.path) != binding.game_sha256:
            _refuse("production_game_binary_changed")
        # Memory construction checked the original PID/start. Re-read the process
        # start and exit state now rather than trusting its cached timestamp.
        c, w, k = legacy.c, legacy.w, legacy.k
        times = [w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(memory.handle, *[c.byref(t) for t in times]):
            _refuse("production_process_identity_unavailable")
        actual_ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        expected = datetime.fromisoformat(binding.game_process_start.replace("Z", "+00:00")).timestamp()
        if abs((actual_ticks - 116444736000000000) / 10000000 - expected) > .001:
            _refuse("production_process_start_changed")
        exit_code = w.DWORD()
        k.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
        k.GetExitCodeProcess.restype = w.BOOL
        if not k.GetExitCodeProcess(memory.handle, c.byref(exit_code)) or (operation == "produce" and exit_code.value != 259):
            _refuse("production_game_process_ended")
        if executor.shared.pid != binding.game_process_id:
            _refuse("production_shared_process_mismatch")
        if (tuple(executor.shared.session) != legacy.uuid_words(binding.session_id)
                or tuple(executor.shared.commander) != legacy.uuid_words(binding.commander_id)):
            _refuse("production_shared_session_mismatch")
        if ((executor.shared.start_high << 32) | executor.shared.start_low) != actual_ticks:
            _refuse("production_shared_start_mismatch")
        if Path(legacy.verify_session_package(executor.session)).resolve() != Path(executor.package).resolve():
            _refuse("production_package_binding_changed")
        if operation == "produce":
            player = executor._verify_binding()
            if player.get("owner_index") != binding.player_id:
                _refuse("production_owner_mismatch")
            if executor.shared.phase != 1 or executor.shared.stop_requested or executor.stopping.is_set():
                _refuse("production_executor_stopped")
            legacy.require_unpaused(memory)
            factory = legacy.read_factory(memory, executor.candidate, executor.owner)
            if factory.get("production_interface_available") is not True:
                _refuse("production_factory_unavailable")
        else:
            # Cleanup/read-only status use only this already attached original
            # mapping. Natural settlement may have destroyed the owner/logic;
            # do not reattach or dereference it just to release callbacks.
            original = getattr(executor, "binding", {})
            native = getattr(executor, "native", {})
            if (original.get("personality_binding_verified") is not True
                    or original.get("commander_id") != binding.commander_id
                    or executor.shared.owner != executor.owner
                    or executor.shared.personality != int(native.get("personality_wrapper", "0"), 0)
                    or executor.shared.personality_id != int(native.get("instance_id", "0"), 0)):
                _refuse("production_attached_identity_changed")
        logic = memory.u32(0xcd8ce4) if operation == "produce" else 0
        return AdmissionSnapshot(memory.u32(logic + 0x50) if logic else 0, memory.u32(logic + 0x15c) != 0 if logic else False,
                                 int(executor.shared.last_seq), _digest(legacy.NATIVE_BIN / "ProductionPersistent.dll"))

    def validate(self, wire, executor, snapshot):
        return _legacy_module().validate_command(wire, executor.session["session_id"],
                                                executor.commander_id, snapshot.game_frame,
                                                executor.reserve_floor)


class PersistentProductionAdapter:
    """Gateway adapter; starts no executor and enables no tactical capabilities.

    ``journal`` owns durable sequence reservation. ``checks`` is injectable only
    by the host/test harness; it is never decoded from UI or model dictionaries.
    """
    def __init__(self, executor, binding: SessionBinding, *, run_id: str, journal,
                 capabilities: CapabilityCatalog, execution_limits: ExecutionLimits,
                 checks=None):
        if not isinstance(binding, SessionBinding) or not isinstance(capabilities, CapabilityCatalog):
            raise ContractError("native_adapter_contract_required")
        self.executor, self.binding, self.run_id = executor, binding, identifier(run_id)
        if not isinstance(execution_limits, ExecutionLimits):
            raise ContractError("native_execution_limits_required")
        self.execution_limits = execution_limits
        self.journal, self.capabilities = journal, capabilities
        if not callable(getattr(journal, "reserve_native_sequence", None)):
            raise ContractError("persistent_native_sequence_store_required")
        self.checks = checks if checks is not None else ExistingProductionChecks()
        if not callable(getattr(self.checks, "admit", None)) or not callable(getattr(self.checks, "validate", None)):
            raise ContractError("native_adapter_checks_required")
        self.test_only = checks is not None
        self._sent = set()

    def _metadata(self, command, binding):
        if not isinstance(binding, SessionBinding) or binding != self.binding:
            _refuse("production_adapter_binding_mismatch")
        if not isinstance(command, Mapping):
            _refuse("production_command_envelope_invalid")
        for key, expected in (("run_id", self.run_id), ("session_id", binding.session_id),
                              ("player_id", binding.player_id), ("commander_id", binding.commander_id)):
            if command.get(key) != expected or key == "player_id" and type(command.get(key)) is not int:
                _refuse("production_command_binding_mismatch")
        identifier(command.get("command_id")); identifier(command.get("request_id"))
        if binding.player_id != 3:
            _refuse("legacy_executor_player_unsupported")
        if (self.executor.total_budget != self.execution_limits.production_total_budget
                or self.executor.reserve_floor != self.execution_limits.reserve_floor):
            _refuse("production_execution_limits_mismatch")
        if command.get("operation") not in ("produce", "query_status", "stop"):
            _refuse("persistent_adapter_operation_unsupported")
        original = self.journal.get_command(self.run_id, command["request_id"])
        if (original["command_id"] != command["command_id"] or original["operation"] != command["operation"]
                or original["payload"] != command.get("payload")):
            _refuse("production_journal_command_mismatch")
        raw = self.executor.session_path.read_bytes()
        if raw != self.executor.session_bytes:
            _refuse("production_session_original_changed")
        session = self.executor.session
        if (session.get("session_id") != binding.session_id or session.get("pid") != binding.game_process_id
                or session.get("start_time") != binding.game_process_start or session.get("mod_sha256") != binding.mod_sha256
                or self.executor.commander_id != binding.commander_id):
            _refuse("production_session_binding_mismatch")

    def _grant(self, command, snapshot):
        unit = command["payload"].get("unit")
        capability_id = {"conscript": "production.infantry", "flak": "production.anti_air"}.get(unit)
        if capability_id is None:
            _refuse("production_unit_unsupported")
        grant = self.capabilities.require(capability_id, self.binding)
        if command.get("capability") != grant.public():
            _refuse("production_grant_changed")
        constraints = grant.public().get("execution_constraints", {})
        if (constraints.get("runtime_family") != RUNTIME_FAMILY
                or constraints.get("executor_directory") != "production/persistent/bin-v2"
                or constraints.get("execution_ready") is not True
                or unit not in constraints.get("allowed_units", ())
                or unit not in constraints.get("persistent_units_verified", ())
                or constraints.get("executor_sha256") != grant.executor_sha256
                or grant.executor_sha256 != snapshot.executor_sha256
                or constraints.get("evidence_id") != grant.evidence_id):
            _refuse("persistent_unit_scope_unverified")
        payload = command["payload"]
        if "max_budget" in constraints and payload.get("budget", 0) > constraints["max_budget"]:
            _refuse("production_budget_exceeds_evidence_scope")
        if "reserve_floor" in constraints and payload.get("reserve", 0) < constraints["reserve_floor"]:
            _refuse("production_reserve_below_evidence_scope")

    def _wire(self, command, sequence):
        payload = object_fields(command["payload"], {"unit", "task_id", "budget", "reserve", "expires_frame"},
                                {"generation", "lease_id", "plan_id", "observed_frame", "monotonic_ms", "max_cost"})
        identifier(payload["task_id"])
        self._validate_metadata(payload)
        if "max_cost" in payload:
            integer(payload["max_cost"], 1, 1000, "production_max_cost_invalid")
            if payload["budget"] > payload["max_cost"]:
                _refuse("production_command_exceeds_task_cost")
        integer(payload["budget"], 1, self.execution_limits.max_command_budget, "production_budget_invalid")
        integer(payload["reserve"], self.executor.reserve_floor, 100000, "production_reserve_invalid")
        integer(payload["expires_frame"], 0, 0xffffffff, "production_expiry_invalid")
        return dict(session_id=self.binding.session_id, player_id=self.binding.player_id,
                    commander_id=self.binding.commander_id, command_id=command["command_id"],
                    task_id=payload["task_id"], seq=sequence, unit=payload["unit"],
                    budget=payload["budget"], reserve=payload["reserve"], expires_frame=payload["expires_frame"])

    @staticmethod
    def _validate_metadata(payload):
        if "generation" in payload:
            integer(payload["generation"], 1, 2**53-1, "production_generation_invalid")
        for key in ("lease_id", "plan_id"):
            if key in payload and payload[key] is not None:
                identifier(payload[key])
        for key in ("observed_frame", "monotonic_ms"):
            if key in payload:
                integer(payload[key], 0, 2**53-1, "production_observation_clock_invalid")

    def _admit(self, command, binding):
        self._metadata(command, binding)
        snapshot = self.checks.admit(self.executor, binding, command["operation"])
        if not isinstance(snapshot, AdmissionSnapshot):
            _refuse("production_admission_snapshot_invalid")
        integer(snapshot.game_frame, 0, 0xffffffff, "production_frame_invalid")
        integer(snapshot.native_last_sequence, 0, 0xffffffff, "production_sequence_invalid")
        if command["operation"] == "produce":
            if snapshot.paused is not False:
                _refuse("game_paused")
            self._grant(command, snapshot)
            if snapshot.native_last_sequence >= 0xffffffff:
                _refuse("production_sequence_exhausted")
            self.checks.validate(self._wire(command, snapshot.native_last_sequence + 1), self.executor, snapshot)
        else:
            optional = {"scope", "reason_code", "task_id", "generation", "lease_id", "plan_id", "observed_frame", "monotonic_ms"} | ({"production_request_id"} if command["operation"] == "query_status" else set())
            data = object_fields(command["payload"], set(), optional)
            self._validate_metadata(data)
            if "task_id" in data:
                identifier(data["task_id"])
            if data.get("scope", "production") != "production":
                _refuse("persistent_adapter_scope_unsupported")
            if "production_request_id" in data:
                identifier(data["production_request_id"])
        return snapshot

    def preflight(self, command, binding):
        try:
            self._admit(command, binding)
        except AdmissionRefused:
            raise
        except Exception:
            _refuse("production_preflight_failed")

    def prepare_wire(self, command, binding):
        """Persist a sequence after admission, without issuing a game command.

        The caller must persist its Host projection before resume_reserved;
        dispatch will re-admit the game state and use this same allocation.
        """
        snapshot = self._admit(command, binding)
        if command["operation"] != "produce":
            _refuse("production_prepare_operation_invalid")
        sequence = self.journal.reserve_native_sequence(self.run_id, command["command_id"], snapshot.native_last_sequence)
        return self.checks.validate(self._wire(command, sequence), self.executor, snapshot)

    def normalize_existing_receipt(self, command, binding, raw):
        """Correlate a later original executor receipt; never dispatch/relabel it."""
        self._metadata(command, binding)
        if command["operation"] != "produce":
            _refuse("production_receipt_operation_invalid")
        sequence = self.journal.get_native_sequence(self.run_id, command["command_id"])
        return self._normalize(command, self._wire(command, sequence), raw)

    def _receipt(self, command, status, facts):
        return NativeReceipt(command["command_id"], self.binding.binding_hash, status,
                             {"source": "injected_test_adapter" if self.test_only else "native_persistent_production",
                              "operation": command["operation"], **facts})

    @staticmethod
    def _reason(value):
        return value if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_]{1,100}", value) else "native_reason_unavailable"

    def _normalize(self, command, wire, raw):
        if not isinstance(raw, Mapping):
            return self._receipt(command, "uncertain", {"reason_code": "native_receipt_not_object"})
        state = raw.get("status")
        if state == "no_dispatch_rejected" and raw.get("task_id") == wire["task_id"] and all(raw.get(k) is False for k in ("accepted", "started", "completed")):
            return self._receipt(command, "rejected", {"reason_code": self._reason(raw.get("reason_code")), "native_dispatch_attempted": False,
                                                       "task_id": wire["task_id"], "seq": wire["seq"]})
        if state == "unknown":
            return self._receipt(command, "uncertain", {"reason_code": self._reason(raw.get("reason_code")), "task_id": wire["task_id"], "seq": wire["seq"]})
        if (raw.get("command_id") != wire["command_id"] or raw.get("task_id") != wire["task_id"]
                or type(raw.get("seq")) is not int or raw["seq"] != wire["seq"] or raw.get("unit") != wire["unit"]):
            return self._receipt(command, "uncertain", {"reason_code": "native_receipt_command_mismatch"})
        if state not in ("queued", "completed") or raw.get("accepted") is not True or raw.get("started") is not True:
            return self._receipt(command, "uncertain", {"reason_code": "native_receipt_status_inconsistent"})
        keys = ("command_id", "task_id", "seq", "unit", "queue_id", "object_id", "cost", "paid", "paid_verified", "created",
                "completion_observed", "live_samples", "payment_error", "enqueue_frame", "completion_frame", "queue_preserved")
        facts = {k: raw.get(k) for k in keys}
        facts["reason_code"] = self._reason(raw.get("reason_code"))
        # The original producer proves the created ID/payment but does not
        # publish an actor birth-generation contract. A trusted own observer
        # must supply that before any later reservation can consume this actor.
        facts["actor_generation_verified"] = False
        if state == "completed":
            complete = (raw.get("completed") is True and raw.get("paid_verified") is True and raw.get("created") is True
                        and type(raw.get("queue_id")) is int and raw["queue_id"] > 0 and raw.get("queue_preserved") is True
                        and raw.get("completion_observed") is True and type(raw.get("object_id")) is int and raw["object_id"] > 0
                        and type(raw.get("cost")) is int and 0 < raw["cost"] <= wire["budget"]
                        and type(raw.get("paid")) is int and raw["paid"] == raw["cost"]
                        and type(raw.get("payment_error")) is int and raw["payment_error"] == 0
                        and type(raw.get("live_samples")) is int and raw["live_samples"] > 0)
            return self._receipt(command, "completed" if complete else "uncertain", facts)
        if raw.get("completed") is not False or type(raw.get("queue_id")) is not int or raw["queue_id"] <= 0:
            return self._receipt(command, "uncertain", {"reason_code": "native_queue_receipt_invalid"})
        return self._receipt(command, "accepted", facts)

    def _status_facts(self, raw):
        if not isinstance(raw, Mapping) or (raw.get("session_id"), raw.get("player_id"), raw.get("commander_id")) != (self.binding.session_id, self.binding.player_id, self.binding.commander_id):
            raise ValueError("native_status_binding_mismatch")
        if raw.get("personality_binding_verified") is not True:
            raise ValueError("native_status_personality_unverified")
        return {k: raw.get(k) for k in ("state", "native_phase", "native_error", "restore_mask", "active_callbacks", "spent_committed", "total_budget", "last_seq")}

    def _query(self, command):
        raw = self.executor.status()
        facts = {"query_only": True, **self._status_facts(raw)}
        target_request = command["payload"].get("production_request_id")
        if target_request is not None:
            original = self.journal.get_command(self.run_id, target_request)
            if original["operation"] != "produce":
                raise ValueError("query_target_not_production")
            lookup = getattr(self.journal, "get_native_sequence", None)
            sequence = lookup(self.run_id, original["command_id"]) if callable(lookup) else None
            if sequence is None:
                facts["production_result"] = {"request_id": target_request, "command_id": original["command_id"],
                                               "status": "uncertain", "reason_code": "native_sequence_not_observed"}
            else:
                rows = [r for r in raw.get("ledger", ()) if isinstance(r, Mapping) and r.get("command_id") == original["command_id"]]
                if len(rows) > 1:
                    raise ValueError("native_query_duplicate_command")
                if not rows:
                    facts["production_result"] = {"request_id": target_request, "command_id": original["command_id"],
                                                   "status": "uncertain", "reason_code": "native_receipt_not_observed"}
                else:
                    envelope = {**command, "command_id": original["command_id"], "operation": "produce", "payload": original["payload"]}
                    wire = self._wire(envelope, sequence)
                    normalized = self._normalize(envelope, wire, rows[0])
                    facts["production_result"] = {"request_id": target_request, "command_id": normalized.command_id,
                                                   "session_binding_hash": normalized.session_binding_hash,
                                                   "status": normalized.status, "facts": dict(normalized.facts)}
        return self._receipt(command, "completed", facts)

    def dispatch(self, command, binding):
        try:
            snapshot = self._admit(command, binding)
        except AdmissionRefused:
            raise
        except Exception:
            _refuse("production_pre_dispatch_refused")
        if command["command_id"] in self._sent:
            return self._receipt(command, "uncertain", {"reason_code": "native_adapter_repeat_blocked"})
        self._sent.add(command["command_id"])
        operation = command["operation"]
        if operation == "produce":
            # Persistence occurs before submit. A crash here consumes a sequence,
            # never restarts from zero and never proves the external command ran.
            sequence = self.journal.reserve_native_sequence(self.run_id, command["command_id"], snapshot.native_last_sequence)
            wire = self.checks.validate(self._wire(command, sequence), self.executor, snapshot)
            raw = self.executor.submit(wire)
            return self._normalize(command, wire, raw)
        if operation == "query_status":
            return self._query(command)
        raw = self.executor.stop()
        facts = self._status_facts(raw)
        restored = (all(type(raw.get(k)) is int for k in ("native_phase", "native_error", "restore_mask", "active_callbacks"))
                    and raw.get("state") == "stopped" and raw.get("native_phase") == 2 and raw.get("native_error") == 0
                    and raw.get("restore_mask") == 31 and raw.get("active_callbacks") == 0 and raw.get("local_error") is None)
        return self._receipt(command, "released" if restored else "uncertain", {**facts, "production_release_verified": restored,
                             "mission_effect_verified": False, "native_ai_continues": True})
