"""Independent byte-level review of the bounded single-actor diagnostic.

This module never attaches to a game or dispatches commands. Successful review
is local movement/hold/home evidence, never attack, scouting or combat credit.
The diagnostic's summary booleans cannot substitute for raw packets/samples.
"""
from __future__ import annotations

import ctypes as c
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import subprocess

from .contracts import SessionBinding
from .contracts import ContractError, canonical_json, sha256
from .capabilities import VerifiedGrant
from .runtime_land_evidence import valid_row as _land_trace_valid,groups as _land_groups,has_move_proof
from .runtime_home_evidence import valid_row as _home_trace_valid,groups as _home_groups,has_return_proof

RUNTIME = Path(__file__).resolve().parents[2] / "tactical/runtime"
CHECKS = (
    "diagnostic_schema", "exact_public_binding", "current_build_artifacts", "raw_bootstrap_binding",
    "raw_paid_actor", "stable_terminal_headers", "closed_event_stream", "original_command_packets",
    "raw_event_identities", "monotonic_observations", "no_foreign_control", "closed_native_hook_trace", "bounded_native_calls",
    "ordered_local_phases", "physical_target_and_home", "three_frame_stops", "actual_hold_interval",
    "live_native_pool_return", "independent_original_entry_bytes", "native_endpoint_geometry", "current_home_vacancy",
)


class EvidenceError(ValueError):
    pass


def _layout():
    spec = importlib.util.spec_from_file_location("_tacticore_independent_layout", RUNTIME / "layout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decode(cls, text, size=None):
    expected = c.sizeof(cls) if size is None else size
    if not isinstance(text, str) or len(text) != expected * 2 or not re.fullmatch("[0-9a-f]*", text):
        raise EvidenceError("raw_packet_size_or_encoding")
    raw = bytes.fromhex(text)
    return cls.from_buffer_copy(raw + bytes(c.sizeof(cls) - len(raw)))


def _values(value):
    return tuple((name, tuple(getattr(value, name)) if isinstance(getattr(value, name), c.Array) else getattr(value, name))
                 for name, *_ in value._fields_)


def _point(value):
    return value.x, value.y, value.z


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _reason(value):
    return bytes(value).split(b"\0", 1)[0].decode("ascii", errors="strict")


def _filetime(iso):
    value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    delta = value.astimezone(timezone.utc) - datetime(1601, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 10_000_000 + delta.microseconds * 10


def verify_pe(raw, machine, *, host_atomic=False):
    """Read PE metadata without loading a report-selected DLL."""
    def u16(offset):return struct.unpack_from("<H", raw, offset)[0]
    def u32(offset):return struct.unpack_from("<I", raw, offset)[0]
    try:
        pe = u32(0x3c)
        if raw[:2] != b"MZ" or raw[pe:pe + 4] != b"PE\0\0" or u16(pe + 4) != machine:
            raise EvidenceError("binary_machine_unverified")
        sections, optional_size = u16(pe + 6), u16(pe + 20)
        optional = pe + 24
        if not 0 < sections <= 96 or optional_size < 112 or optional + optional_size + sections * 40 > len(raw):
            raise EvidenceError("binary_pe_bounds_invalid")
        if u16(optional) != (0x20b if machine == 0x8664 else 0x10b):
            raise EvidenceError("binary_optional_header_unverified")
        if not host_atomic:
            return
        if machine != 0x8664 or not (u16(pe + 22) & 0x2000) or u32(optional + 16) != 0 or optional_size < 240:
            raise EvidenceError("atomic_helper_entry_or_architecture")
        directory = optional + 112
        if any(u32(directory + index * 8 + part) for index in (1, 9, 13) for part in (0, 4)):
            raise EvidenceError("atomic_helper_has_imports_or_tls")
        def offset(rva, size):
            for i in range(sections):
                section = optional + optional_size + i * 40
                virtual, count, disk = u32(section + 12), u32(section + 16), u32(section + 20)
                if virtual <= rva and rva + size <= virtual + count and disk + rva - virtual + size <= len(raw):
                    return disk + rva - virtual
            raise EvidenceError("atomic_helper_export_bounds")
        export_rva, export_size = u32(directory), u32(directory + 4)
        export = offset(export_rva, 40)
        if u32(export + 20) != 1 or u32(export + 24) != 1:
            raise EvidenceError("atomic_helper_export_inventory")
        name_rva = u32(offset(u32(export + 32), 4))
        name = offset(name_rva, len(b"runtime_exchange\0"))
        function = u32(offset(u32(export + 28), 4))
        if raw[name:name + 17] != b"runtime_exchange\0" or export_rva <= function < export_rva + export_size:
            raise EvidenceError("atomic_helper_export_inventory")
        offset(function, 1)
    except (struct.error, IndexError):
        raise EvidenceError("binary_pe_bounds_invalid") from None


def verify_build_artifacts(manifest, layout):
    """Current registered runtime paths only; no report-selected executable."""
    actual = json.loads((RUNTIME / "bin/build-manifest.json").read_text(encoding="utf-8-sig"))
    if manifest != actual or actual.get("architecture") != "x86" or actual.get("protocol") != "tactical_runtime_v1" or actual.get("layout") != layout.inventory():
        raise EvidenceError("build_manifest_changed")
    required = {"controller.cpp", "controller.h", "protocol.h", "shared_channel.h", "hooks.cpp", "hooks.h",
                "memory_io.h", "native_factory.cpp", "native_factory.h", "native_host.cpp", "channel_dll.cpp",
                "atomic_publish.cpp", "lineage.h", "membership.h", "incarnations.h", "endpoints.h", "geometry.h", "native_yield.h", "land_geometry.h", "home_clearance.h"}
    inputs = actual.get("inputs", [])
    if not required <= {row.get("file") for row in inputs} or len({row.get("file") for row in inputs}) != len(inputs):
        raise EvidenceError("build_inputs_incomplete")
    for row in inputs:
        name = row["file"]
        if not isinstance(name, str) or Path(name).name != name or "/" in name or "\\" in name:
            raise EvidenceError("build_input_path_invalid")
        if hashlib.sha256((RUNTIME / name).read_bytes()).hexdigest() != row.get("sha256"):
            raise EvidenceError("built_source_changed")
    outputs = actual.get("outputs", [])
    hashes = {row.get("file"): row.get("sha256") for row in outputs}
    if len(outputs) != 3 or set(hashes) != {"TacticoreRuntime1.dll", "runtime_host.exe", "atomic_publish.dll"}:
        raise EvidenceError("build_outputs_incomplete")
    for name, digest in hashes.items():
        raw = (RUNTIME / "bin" / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise EvidenceError("built_binary_changed")
        verify_pe(raw, 0x8664 if name == "atomic_publish.dll" else 0x14c, host_atomic=name == "atomic_publish.dll")
    executable_layout = json.loads(subprocess.check_output([str(RUNTIME / "bin/runtime_host.exe"), "--layout"], timeout=5, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
    if executable_layout != layout.inventory():
        raise EvidenceError("executable_abi_changed")
    return hashes


def _producer_types(layout):
    class Command(c.Structure):
        _fields_ = [("seq", layout.U)] + [(name, layout.ID) for name in ("id", "task", "session", "commander")] + [
            (name, layout.U) for name in "hash budget reserve expires queue_limit requested_tick factory factory_id iface".split()]
    class Receipt(c.Structure):
        _fields_ = [("updates", layout.I), ("version", layout.I), ("command", Command)] + [
            (name, layout.U) for name in "state error attempted frame queue_id node cost quoted_cost cash liability prior_count preserved paid debit_count payment_error created object object_id object_owner object_hash completed completion_frame live_samples object_hp_bits object_x_bits object_y_bits factory_x_bits factory_y_bits".split()]
    class Header(c.Structure):
        _fields_ = [(name, layout.U) for name in "magic version pid thread owner ai personality personality_id player_template start_low start_high".split()] + [
            ("session", layout.ID), ("commander", layout.ID)] + [(name, layout.U) for name in "total_budget reserve_floor min_interval start_frame".split()] + [
            (name, layout.I) for name in "phase stop_requested active heartbeat request_state".split()] + [("request", Command)] + [
            (name, layout.U) for name in "reply_index reply_error last_seq last_frame last_accepted_frame spent count restore_mask error callback_thread".split()]
    return Receipt, Header


def _entry_signatures():
    source = (RUNTIME / "hooks.cpp").read_text(encoding="utf-8")
    rows = re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2}|\\0)+)",(\d+),', source)
    expected = {}
    for address, encoded, count in rows:
        raw = encoded.encode("ascii").decode("unicode_escape").encode("latin1")
        if len(raw) != int(count):
            raise EvidenceError("original_signature_length")
        expected[address] = raw.hex()
    if len(expected) != 13:
        raise EvidenceError("original_signature_inventory")
    return expected


def _catalogue_trace_valid(trace,actor):
    """Non-action diagnostic rows only. Truncation never qualifies a grant."""
    if (trace.kind not in (26,27) or trace.word_count!=24 or trace.operation!=0
            or trace.scope!=0 or trace.source!=0 or trace.caller!=0
            or trace.self!=actor.update or trace.target!=actor.thing or trace.words[0]!=1):
        return False
    words=trace.words
    def scalar(i):return struct.unpack('<f',struct.pack('<I',words[i]))[0]
    if trace.kind==26:
        return (words[1]<=256 and words[2]<=words[1] and words[3] in (0,1) and words[4]<=40000
            and tuple(scalar(i) for i in (5,6,7,8))==(30,120,20,2) and words[9] in (0,1)
            and all(math.isfinite(scalar(i)) for i in (10,11,12)) and not any(words[13:]))
    if not (words[1]<words[2]<=256 and words[3] in (0,1) and words[4]<=31 and words[13]<=40000
            and tuple(scalar(i) for i in (14,15,16))==(30,120,20) and not any(words[19:])
            and all(math.isfinite(scalar(i)) for i in range(5,13)) and math.isfinite(scalar(17))):
        return False
    point=tuple(scalar(i) for i in (5,6,7));home=tuple(scalar(i) for i in (8,9,10))
    gap=scalar(11);nearest=scalar(12);height=scalar(17)
    if gap<0 or nearest<0 or height<0 or abs(gap-_distance(point,home))>.001 or abs(height-abs(point[2]-home[2]))>.001:
        return False
    flags=(0 if words[3] else 1)|(2 if gap<30 else 0)|(4 if gap>120 else 0)|(8 if words[3] and nearest<20 else 0)|(16 if height>2 else 0)
    return words[4]==flags and words[18]==int(30<=gap<=120 and words[3] and nearest>=20)


def verify_bootstrap_paid(report, expected_binding, layout, check, *, expected_experimental_flags=0):
    # Explicit diagnostics may inspect mode2 bytes. Ordinary qualification still
    # calls this with default0, so controlled-fault reports cannot grant scope.
    if type(expected_experimental_flags) is not int or expected_experimental_flags not in (0, 1, 2):
        raise EvidenceError('experimental_review_mode_invalid')
    boot = _decode(layout.Bootstrap, report.get("bootstrap_hex"))
    actor = _decode(layout.Actor, report.get("admitted_actor_hex"))
    stable_actor_fields = ("object_id", "thing", "template_ptr", "update", "owner", "type_hash")
    check("raw_bootstrap_binding", layout.uuid_text(boot.binding.session) == expected_binding.session_id
          and layout.uuid_text(boot.binding.commander) == expected_binding.commander_id
          and layout.uuid_text(boot.binding.host) == expected_binding.host_id
          and tuple(boot.binding.binding_hash) == layout.digest_words(expected_binding.binding_hash)
          and boot.binding.pid == expected_binding.game_process_id and boot.binding.player == expected_binding.player_id
          and abs(boot.binding.process_start - _filetime(expected_binding.game_process_start)) <= 9
          and boot.binding.thread > 0 and boot.experimental_flags == expected_experimental_flags and boot.actor.generation == boot.actor.born_frame == 0
          and actor.generation > 0 and actor.born_frame > 0
          and all(getattr(actor, name) == getattr(boot.actor, name) for name in stable_actor_fields)
          and boot.actor.type_hash == 0x19ab11af and boot.native.default_team != boot.native.script_team)
    producer = report.get("producer_receipt") or {}
    Receipt, Header = _producer_types(layout)
    paid = _decode(Receipt, producer.get("raw_hex"))
    production = _decode(Header, producer.get("native_header_hex"))
    check("raw_paid_actor", paid.updates == 0 and paid.version > 0 and paid.state == 2 and paid.error == 0
          and paid.payment_error == 0 and paid.debit_count > 0 and paid.paid == paid.cost == 85
          and paid.debit_count <= 85 and paid.quoted_cost == 85 and paid.attempted == paid.preserved == 1
          and paid.queue_id > 0 and paid.node > 0 and paid.command.hash == 0x19ab11af
          and 85 <= paid.command.budget <= 1000 and paid.command.reserve >= production.reserve_floor
          and paid.cash >= paid.cost + paid.liability + paid.command.reserve
          and paid.created == paid.completed == 1 and paid.live_samples > 0
          and paid.object_id == boot.actor.object_id and paid.object == boot.actor.thing
          and paid.object_owner == boot.actor.owner == boot.native.owner and paid.object_hash == boot.actor.type_hash
          and 0 < paid.completion_frame <= actor.born_frame
          and tuple(paid.command.id) == tuple(boot.producer.command)
          and tuple(paid.command.task) == tuple(boot.producer.task) and paid.command.seq == boot.producer.sequence
          and tuple(paid.command.session) == tuple(boot.binding.session)
          and tuple(paid.command.commander) == tuple(boot.binding.commander)
          and production.magic == 0x50434d44 and production.version == 1 and production.phase == 1 and production.error == 0
          and production.stop_requested == 0 and production.callback_thread == boot.binding.thread
          and production.pid == boot.binding.pid and production.thread == boot.binding.thread
          and tuple(production.session) == tuple(boot.binding.session) and tuple(production.commander) == tuple(boot.binding.commander)
          and all(getattr(production, name) == getattr(boot.native, name) for name in
                  ("owner", "ai", "personality", "personality_id", "player_template"))
          and production.owner == boot.native.owner and (production.start_low | (production.start_high << 32)) == boot.binding.process_start
          and boot.producer.receipt_index < production.count <= 1024 and production.spent >= 85)
    return boot, actor


def qualify_runtime_report(report, expected_binding: SessionBinding):
    checks = dict.fromkeys(CHECKS)
    facts = {}

    def check(name, condition):
        checks[name] = condition is True
        if not checks[name]:
            raise EvidenceError(name)

    try:
        check("diagnostic_schema", isinstance(report, dict) and report.get("schema_version") == 1
              and type(report.get("schema_version")) is int and report.get("protocol") == "tactical_runtime_v1_diagnostic"
              and report.get("diagnostic") is True and report.get("ordinary_execution_granted") is False
              and report.get("field_verified") is False)
        check("exact_public_binding", isinstance(expected_binding, SessionBinding) and report.get("binding") == expected_binding.public()
              and expected_binding.player_id == 3)
        layout = _layout()
        hashes = verify_build_artifacts(report.get("build_manifest"), layout)
        check("current_build_artifacts", report.get("native_layout") == layout.inventory()
              and hashes["TacticoreRuntime1.dll"] == report.get("executor_sha256")
              and hashes["runtime_host.exe"] == report.get("native_host_sha256"))
        boot, actor = verify_bootstrap_paid(report, expected_binding, layout, check)
        headers = report.get("terminal_headers", [])
        if len(headers) != 2:
            raise EvidenceError("terminal_headers_missing")
        before = _decode(layout.SharedChannel, headers[0], layout.SharedChannel.events.offset)
        after = _decode(layout.SharedChannel, headers[1], layout.SharedChannel.events.offset)
        check("stable_terminal_headers", headers[0] == headers[1] == report.get("header_before_hex") == report.get("header_after_hex")
              and before.magic_word == layout.MAGIC and before.protocol == layout.VERSION
              and before.structure_size == c.sizeof(layout.SharedChannel) and before.token > 0
              and bytes(before.bootstrap) == bytes(boot) and before.state == 3 and before.active_callbacks == 0
              and before.hooks_restored == 8191 and before.callback_thread == boot.binding.thread
              and before.command_generation == before.command_acknowledged and before.command_generation % 2 == 0
              and before.receipt_generation > 0 and before.receipt_generation % 2 == 0
              and _values(before.admitted_actor) == _values(actor)
              and report.get("host_exit") == 0 and type(report.get("host_exit")) is int)
        rows = report.get("events", [])
        check("closed_event_stream", isinstance(rows, list) and 0 < len(rows) == before.events_written <= layout.CAPACITY
              and before.events_overwritten == report.get("events_overwritten") == 0
              and report.get("events_written") == before.events_written)
        events = [_decode(layout.WireEvent, row.get("raw_hex")) for row in rows]
        check("closed_event_stream", all(event.ticket == row.get("ticket") == i + 1
              and _reason(event.event_type) == row.get("event_type") for i, (event, row) in enumerate(zip(events, rows))))
        commands = report.get("commands", [])
        packets = [_decode(layout.Command, row.get("wire_hex")) for row in commands]
        acknowledgements = [_decode(layout.WireReceipt, row.get("acknowledged_hex")) for row in commands]
        check("original_command_packets", len(packets) == 2 and [p.operation for p in packets] == [1, 2]
              and all(p.sequence > 0 and p.sequence <= 0xffffffff and p.expires_frame > 0
                      and p.expires_monotonic_ms > 0 and _values(p.actor) == _values(actor)
                      and tuple(p.task) == tuple(packets[0].task) and tuple(p.lease) == tuple(packets[0].lease)
                      and tuple(p.command) == tuple(a.command) and tuple(p.task) == tuple(a.task)
                      and tuple(p.lease) == tuple(a.lease) and p.sequence == a.sequence and a.accepted == 1
                      and row.get("published_generation") == 2 * (i + 1)
                      and type(row.get("acknowledgement_generation")) is int and row["acknowledgement_generation"] > 0
                      and row["acknowledgement_generation"] % 2 == 0
                      for i, (p, a, row) in enumerate(zip(packets, acknowledgements, commands)))
              and packets[0].sequence < packets[1].sequence and packets[0].hold_frames == 0
              and packets[0].lease_deadline_frame == packets[1].lease_deadline_frame
              and 0 < packets[1].hold_frames <= 900)
        command_ids = {tuple(p.command) for p in packets}
        samples = [event.observation for event in events]
        check("raw_event_identities", all(_values(s.binding) == _values(boot.binding) and _values(s.actor) == _values(actor)
              and s.frame >= actor.born_frame
              and s.identity and s.actor_birth_verified and s.live_list_member and s.grounded and not s.paused
              and s.current_thread == boot.binding.thread and s.interference_guard_ready
              and s.default_team == boot.native.default_team and s.script_team == boot.native.script_team
              and all(math.isfinite(v) for v in _point(s.xyz)) and tuple(e.receipt.command) in command_ids
              and tuple(e.receipt.task) == tuple(packets[0].task) and tuple(e.receipt.lease) == tuple(packets[0].lease)
              for e, s in zip(events, samples)))
        check("monotonic_observations", all(a.frame <= b.frame and a.monotonic_ms <= b.monotonic_ms for a, b in zip(samples, samples[1:]))
              and all(e.receipt.frame == s.frame and e.receipt.monotonic_ms == s.monotonic_ms for e, s in zip(events, samples)))
        check("no_foreign_control", len({s.foreign_epoch for s in samples}) == 1
              and not any(_reason(e.event_type) in ("uncertain", "command_rejected") or e.receipt.phase == 13 for e in events))
        trace_rows = report.get("hook_traces", [])
        trace_counters = report.get("trace_counters_before_hex")
        if (not isinstance(trace_counters, str) or not re.fullmatch("[0-9a-f]{16}", trace_counters)
                or trace_counters != report.get("trace_counters_after_hex")):
            raise EvidenceError("native_hook_trace_counters_unstable")
        written, overwritten = struct.unpack("<ii", bytes.fromhex(trace_counters))
        traces = [_decode(layout.WireHookTrace, row.get("raw_hex")) for row in trace_rows]
        check("closed_native_hook_trace", 0 < written == len(trace_rows) == report.get("traces_written") <= layout.TRACE_CAPACITY
              and overwritten == report.get("traces_overwritten") == 0
              and all(t.ticket == row.get("ticket") == i + 1 and t.trace.thread == boot.binding.thread
                      and (1 <= t.trace.kind <= 17 or _catalogue_trace_valid(t.trace,actor) or _land_trace_valid(t.trace,actor) or _home_trace_valid(t.trace,actor)) and t.trace.word_count <= 24
                      and (t.trace.kind not in (16, 17) or t.trace.word_count == 24)
                      and t.trace.epoch_before == t.trace.epoch_after == samples[0].foreign_epoch
                      and (actor.born_frame <= t.trace.frame <= before.current_observation.frame if t.trace.kind in (26,27,29,30,31)
                           else samples[0].frame <= t.trace.frame <= samples[-1].frame)
                      for i, (t, row) in enumerate(zip(traces, trace_rows)))
              and all(a.trace.frame <= b.trace.frame for a, b in zip(traces, traces[1:])))
        rows_by_kind = {kind: [t.trace for t in traces if t.trace.kind == kind] for kind in range(1, 18)}
        remove, add = rows_by_kind[7], rows_by_kind[6]
        facades = rows_by_kind[1]
        stops = [t for t in rows_by_kind[3] if t.operation == 3 and t.source == 1]
        private_stops = [t for t in rows_by_kind[4] if t.operation == 3 and t.source == 1]
        check("closed_native_hook_trace", len(remove) == len(add) == 1
              and remove[0].self == add[0].self == boot.native.ai + 0x104
              and remove[0].target == add[0].target == actor.thing
              and remove[0].caller == 0x838877 and remove[0].operation == 1 and remove[0].scope == 1
              and add[0].caller == 0x83885b and add[0].operation == 6 and add[0].scope == 1
              and len(facades) == 2 and all(t.self == actor.update + 0x24 and t.operation == 4 and t.scope == 1
                      and t.source == 1 and t.word_count == 3 for t in facades)
              and len(stops) == 4 and all(t.self == actor.update + 0x24 and t.scope == 1 for t in stops)
              and len(private_stops) == 4 and all(t.self == actor.update and t.caller == 0x787791 for t in private_stops)
              and all(a.frame <= b.frame <= a.frame + 40 for a, b in zip(stops, private_stops))
              and not rows_by_kind[9])
        land=_land_groups([t.trace for t in traces],actor,boot.native.logic)
        required=any(x.get('file')=='land_geometry.h' for x in report['build_manifest'].get('inputs',[]))
        check('native_endpoint_geometry', land is not None and (not required or has_move_proof(land,packets[1].target,facades[0].frame)))
        counters = [tuple(e.receipt.sdk_calls) for e in events]
        check("bounded_native_calls", all(all(a <= b for a, b in zip(x, y)) for x, y in zip(counters, counters[1:]))
              and counters[-1] == (1, 1, 4, 2, 1, 1) and tuple(before.receipt.sdk_calls) == counters[-1])
        phases = [(i, e.receipt.phase) for i, e in enumerate(events) if _reason(e.event_type) == "phase"]
        expected = [1, 2, 3, 4, 5, 6, 7, 14, 8, 9, 10, 11, 12]
        check("ordered_local_phases", [p for _, p in phases] == expected)
        phase_samples = {p: samples[i] for i, p in phases}
        home, target = _point(phase_samples[1].xyz), _point(packets[1].target)
        home_proofs=_home_groups([t.trace for t in traces],actor,boot.native.logic,boot.native.script_team)
        home_required=any(x.get('file')=='home_clearance.h' for x in report['build_manifest'].get('inputs',[]))
        check('current_home_vacancy',home_proofs is not None and (not home_required
              or has_return_proof(home_proofs,home,facades[-1].frame,samples,boot.native.script_team)))
        native_goals = [struct.unpack("<3f", struct.pack("<3I", *t.words[:3])) for t in facades]
        check("physical_target_and_home", 20 <= _distance(home, target) <= 300 and abs(home[2] - target[2]) <= 2
              and native_goals == [target, home]
              and _distance(_point(phase_samples[7].xyz), target) <= 15
              and _distance(_point(phase_samples[10].xyz), home) <= 15
              and all(_distance(home, _point(s.xyz)) <= 320 for s in samples)
              and any(s.normal_move_owned and _distance(home, _point(s.xyz)) >= 20 for s in samples))
        stable_proofs = []
        for end, phase in phases:
            if phase not in (4, 7, 8, 10):
                continue
            start = max((i for i in range(end) if _reason(events[i].event_type) == "sdk_attempt"
                         and (i == 0 or counters[i][2] > counters[i - 1][2])), default=-1)
            distinct = {}
            for s in samples[start + 1:end + 1]:
                distinct[s.frame] = s
            tail = list(distinct.values())[-3:]
            stable_proofs.append(start >= 0 and len(tail) == 3 and all(s.settled and s.stance == 2 and s.team == s.script_team
                and s.path == 0 and s.command_source == 1 for s in tail)
                and all(_distance(_point(a.xyz), _point(b.xyz)) <= 1 for a, b in zip(tail, tail[1:])))
        check("three_frame_stops", len(stable_proofs) == 4 and all(stable_proofs))
        check("actual_hold_interval", phase_samples[14].frame - phase_samples[7].frame >= packets[1].hold_frames
              and samples[-1].frame - phase_samples[1].frame <= 900
              and samples[-1].monotonic_ms - samples[0].monotonic_ms <= 120000)
        final, sample = before.receipt, phase_samples[12]
        check("live_native_pool_return", final.phase == 12 and final.physical_home == final.control_released == final.stance_restored == 1
              and final.held == 0 and sample.team == sample.default_team and sample.stance == 0
              and _distance(home, _point(sample.xyz)) <= 15 and _values(after.receipt) == _values(final)
              and tuple(final.command) == tuple(packets[-1].command) and final.sequence == packets[-1].sequence)
        original = _entry_signatures()
        proof = report.get("terminal_entries", [])
        check("independent_original_entry_bytes", isinstance(proof, list) and len(proof) == len(original)
              and len({row.get("address") for row in proof}) == len(original)
              and all(row.get("address") in original and row.get("expected") == row.get("actual") == original[row["address"]] for row in proof))
        facts = dict(object_id=actor.object_id, generation=actor.generation, first_stable_observation_frame=actor.born_frame, paid=85,
                     distance_xy=_distance(home, target), hold_frames=packets[1].hold_frames,
                     returned_frame=sample.frame, sdk_calls=list(final.sdk_calls), executor_sha256=hashes["TacticoreRuntime1.dll"],
                     native_host_sha256=hashes["runtime_host.exe"])
    except (EvidenceError, OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, subprocess.SubprocessError) as error:
        return dict(schema_version=1, status="not_passed", checks=checks,
                    reason_code=str(error) if isinstance(error, EvidenceError) else "raw_runtime_evidence_invalid",
                    facts=facts, ordinary_execution_granted=False, combat_effect_verified=False)
    return dict(schema_version=1, status="passed", checks=checks, reason_code="ok", facts=facts,
                ordinary_execution_granted=False, combat_effect_verified=False,
                scope="One paid Soviet Conscript, initial stance0, local native-ground Move/Hold/physical home/native return only")


def verify_pinned_runtime(path: Path, expected_sha256: str, binding: SessionBinding) -> VerifiedGrant:
    """Host-only registration boundary; never accepts a WebView capability flag.

    The caller owns the explicit reviewed file pin. Native admission still checks
    the new process, paid actor and every command. This does not authorize combat
    or turn diagnostic commands into an ordinary completed Host task.
    """
    sha256(expected_sha256)
    if not isinstance(binding, SessionBinding) or not isinstance(path, Path) or not path.is_absolute():
        raise ContractError("runtime_evidence_registration_required")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ContractError("runtime_evidence_duplicate_key")
            value[key] = item
        return value
    try:
        with path.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ContractError("runtime_evidence_pin_mismatch")
        report = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        source = SessionBinding.from_dict(report["binding"])
        if any(getattr(source, key) != getattr(binding, key) for key in
               ("player_id", "commander_id", "game_sha256", "mod_sha256")):
            raise ContractError("runtime_evidence_package_or_scope_mismatch")
        assessment = qualify_runtime_report(report, source)
        if assessment.get("status") != "passed" or not all(v is True for v in assessment.get("checks", {}).values()):
            raise ContractError("runtime_raw_evidence_unverified")
        facts = assessment["facts"]
        constraints = dict(runtime_family="tactical", executor_directory="tactical/runtime",
            purpose="move_hold_return", actor_roles=["infantry"], mission_protocol="tactical_runtime_v1",
            limits={"lease_frames": 900}, native_host_sha256=facts["native_host_sha256"],
            execution_ready=True, executor_sha256=facts["executor_sha256"], evidence_id=expected_sha256)
        return VerifiedGrant("tactics.move_hold_return", expected_sha256, expected_sha256,
            facts["executor_sha256"], assessment["scope"], canonical_json(constraints))
    except ContractError:
        raise
    except (OSError, ValueError, UnicodeError, TypeError, KeyError, AttributeError, RecursionError):
        raise ContractError("runtime_evidence_registration_invalid") from None
