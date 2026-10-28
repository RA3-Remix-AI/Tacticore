"""Optional real Host production migration to the durable gateway.

The legacy JSON ledger is an export only on this path. This module does not
start executors, create calibration grants, or reinterpret one-shot Flak proof.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Mapping
import uuid

from .contracts import ContractError, SessionBinding, identifier
from .evidence_adapter import EvidenceBundle, build_catalog
from .gateway import AdmissionRefused, ExecutionGateway
from .journal import CommandJournal
from .limits import ExecutionLimits
from .native_adapters import PersistentProductionAdapter


@dataclass(frozen=True)
class PreparedProduction:
    request_id: str
    command_id: str
    task_id: str
    sequence: int | None
    record: Mapping

    def export_entry(self):
        return dict(kind="runtime_production", request_id=self.request_id,
                    command_id=self.command_id, seq=self.sequence, queue_id=None,
                    terminal=self.record["status"] != "reserved")


class HostProduction:
    def __init__(self, journal: CommandJournal, run_id: str, binding: SessionBinding,
                 evidence: EvidenceBundle, limits: ExecutionLimits):
        if not isinstance(evidence, EvidenceBundle) or evidence.catalog.binding != binding:
            raise ContractError("host_production_evidence_binding_mismatch")
        self.journal, self.run_id, self.binding = journal, identifier(run_id), binding
        self.evidence, self.limits = evidence, limits
        self.gateway = None
        if journal.unresolved_for_session(binding.public(), exclude_run_id=run_id):
            raise ContractError("prior_host_commands_require_recovery")
        journal.register_run(run_id, binding.public())
        if any(record['operation'] != 'host_start' for record in journal.unresolved(run_id)):
            raise ContractError("prior_host_commands_require_recovery")

    @property
    def supported_units(self):
        units = set()
        for grant in self.evidence.catalog.describe()["grants"]:
            c = grant.get("execution_constraints", {})
            if (c.get("runtime_family") == "production_persistent_v2" and c.get("execution_ready") is True
                    and c.get("executor_directory") == "production/persistent/bin-v2"):
                expected = {'production.infantry': 'conscript', 'production.anti_air': 'flak'}.get(grant['capability_id'])
                if expected in c.get('allowed_units', ()) and expected in c.get('persistent_units_verified', ()):
                    units.add(expected)
        return tuple(sorted(units))

    @property
    def supported_foci(self):
        units = set(self.supported_units)
        foci = []
        if "conscript" in units:foci.append("infantry")
        if "flak" in units:foci.append("anti_air")
        if {"conscript", "flak"} <= units:foci.append("balanced")
        return tuple(foci)

    def attach(self, executor, *, checks=None):
        if self.gateway is not None:
            raise ContractError("host_production_already_attached")
        if self.evidence.test_only and checks is None:
            raise ContractError("test_evidence_cannot_reach_native_executor")
        adapter = PersistentProductionAdapter(executor, self.binding, run_id=self.run_id,
                    journal=self.journal, capabilities=self.evidence.catalog,
                    execution_limits=self.limits, checks=checks)
        self.gateway = ExecutionGateway(self.run_id, self.binding, self.journal, self.evidence.catalog, adapter)

    def _envelope(self, record):
        unit = record["payload"].get("unit")
        capability = "production.infantry" if unit == "conscript" else "production.anti_air"
        grant = self.evidence.catalog.require(capability, self.binding)
        return dict(command_id=record["command_id"], request_id=record["request_id"], run_id=self.run_id,
                    session_id=self.binding.session_id, player_id=self.binding.player_id,
                    commander_id=self.binding.commander_id, operation="produce",
                    payload=dict(record["payload"]), capability=grant.public())

    def prepare(self, task_id, *, unit, budget, reserve, expires_frame):
        if self.gateway is None:
            raise ContractError("host_production_not_attached")
        identifier(task_id)
        request = str(uuid.uuid5(uuid.UUID(self.run_id), task_id + ":production"))
        payload = dict(task_id=task_id, unit=unit, budget=budget, reserve=reserve, expires_frame=expires_frame)
        record = self.journal.reserve_command(self.run_id, request, "produce", payload)
        if record["created"] is False:
            raise ContractError("production_request_requires_explicit_recovery")
        sequence = None
        try:
            if unit not in self.supported_units:
                raise AdmissionRefused("persistent_unit_scope_unverified")
            wire = self.gateway.adapter.prepare_wire(self._envelope(record), self.binding)
            sequence = wire["seq"]
        except (AdmissionRefused, ContractError) as error:
            reason = error.reason_code if isinstance(error, AdmissionRefused) else error.code
            record = self.journal.record_outcome(self.run_id, request, "rejected", {"reason_code": reason})
        except Exception:
            record = self.journal.record_outcome(self.run_id, request, "rejected", {"reason_code": "production_prepare_failed"})
        return PreparedProduction(request, record["command_id"], task_id, sequence, record)

    def dispatch(self, prepared: PreparedProduction):
        if self.gateway is None:
            raise ContractError("host_production_not_attached")
        record = self.journal.get_command(self.run_id, prepared.request_id)
        if record["command_id"] != prepared.command_id:
            raise ContractError("prepared_command_changed")
        return self.gateway.resume_reserved(prepared.request_id) if record["status"] == "reserved" else record

    def legacy_receipt(self, record):
        facts = dict((record.get("receipt") or {}).get("facts", {}))
        state = record["status"]
        if state in ("accepted", "started", "completed"):
            if facts.get("command_id") != record["command_id"] or facts.get("task_id") != record["payload"]["task_id"]:
                raise ContractError("production_normalized_receipt_binding_mismatch")
        return {**facts, "command_id": record["command_id"], "task_id": record["payload"]["task_id"],
                "status": "unknown" if state == "uncertain" else "queued" if state in ("accepted", "started") else state,
                "accepted": state in ("accepted", "started", "completed"),
                "started": state in ("accepted", "started", "completed"), "completed": state == "completed"}

    def observe(self, raw_receipt, entry):
        record = self.journal.get_command(self.run_id, entry["request_id"])
        if record["command_id"] != entry.get("command_id"):
            raise ContractError("host_export_command_changed")
        sequence = self.journal.get_native_sequence(self.run_id, record["command_id"])
        if entry.get("seq") != sequence:
            raise ContractError("host_export_sequence_changed")
        normalized = self.gateway.adapter.normalize_existing_receipt(self._envelope(record), self.binding, raw_receipt)
        prior_queue = (record.get('receipt') or {}).get('facts', {}).get('queue_id')
        if record['status'] in ('accepted', 'started') and normalized.status == 'completed' and normalized.facts.get('queue_id') != prior_queue:
            record = self.journal.record_outcome(self.run_id, entry['request_id'], 'uncertain',
                        {'reason_code': 'native_queue_identity_changed'})
            return self.legacy_receipt(record)
        if normalized.status != record["status"]:
            if record["status"] == "uncertain":
                # Only the separately reviewed recovery service may resolve an
                # uncertain action with explicit native evidence, never a retry.
                raise ContractError("production_unknown_requires_recovery")
            record = self.journal.record_outcome(self.run_id, entry["request_id"], normalized.status,
                       {"reason_code": "native_receipt_verified", "facts": dict(normalized.facts)})
        return self.legacy_receipt(record)

    def event(self, kind, payload, *, game_frame=None, monotonic_ns=None):
        return self.journal.append_event(self.run_id, kind, payload, game_frame=game_frame, monotonic_ns=monotonic_ns)

    def stop(self):
        if self.gateway is None:return None
        request = str(uuid.uuid5(uuid.UUID(self.run_id), "production-stop"))
        return self.gateway.submit(request, "stop", {"scope": "production"})

    def public(self):
        return dict(schema_version=1, run_id=self.run_id, binding_hash=self.binding.binding_hash,
                    supported_units=list(self.supported_units), supported_foci=list(self.supported_foci),
                    ledger_authoritative=True, gateway_attached=self.gateway is not None,
                    physical_evidence_granted=False)

    def close(self):self.journal.close()


def from_host(host, ledger_path, *, evidence_builder=build_catalog):
    """Build a fresh host instance; old runs with unresolved actions block it."""
    args, session = host.args, host.session
    host_id = identifier(getattr(args, "runtime_host_id", None) or str(uuid.uuid4()))
    run_id = identifier(getattr(args, "runtime_run_id", None) or str(uuid.uuid4()))
    binding = SessionBinding(1, session["session_id"], args.player, args.commander,
              session["pid"], session["start_time"], host_id,
              hashlib.sha256(Path(session["game"]).read_bytes()).hexdigest(), session["mod_sha256"])
    evidence_options=dict(production_report=args.evidence,persistent_status=args.persistent_evidence,
        tactical_manifest=getattr(args,'tactical_evidence',None),runtime_report=getattr(args,'runtime_report',None),
        runtime_sha256=getattr(args,'runtime_sha256',None),acceptance_root=getattr(args,'acceptance_root',None))
    if getattr(args,'runtime_recovery_report',None)is not None or getattr(args,'runtime_recovery_sha256',None)is not None:
        evidence_options.update(runtime_recovery_report=getattr(args,'runtime_recovery_report',None),
            runtime_recovery_sha256=getattr(args,'runtime_recovery_sha256',None))
    evidence=evidence_builder(binding,session,**evidence_options)
    limits = ExecutionLimits(args.total_budget, args.reserve, 1000)
    path = Path(ledger_path).resolve();path.parent.mkdir(parents=True, exist_ok=True)
    journal = CommandJournal(path)
    try:
        runtime = HostProduction(journal, run_id, binding, evidence, limits)
        if not runtime.supported_units:
            raise ContractError("runtime_no_persistent_production_scope")
        return runtime
    except BaseException:
        journal.close()
        raise
