"""Synthetic byte packets test the reviewer, never establish field capability."""
import copy
import ctypes as c
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch

from host_runtime.contracts import SessionBinding
from host_runtime import runtime_evidence as review


def fixture():
    l = review._layout()
    binding = SessionBinding(1, "11111111-1111-4111-8111-111111111111", 3,
        "22222222-2222-4222-8222-222222222222", 1234, "2026-10-26T05:00:00+00:00",
        "33333333-3333-4333-8333-333333333333", "a" * 64, "b" * 64)
    boot = l.Bootstrap()
    for key, value in (("session", binding.session_id), ("commander", binding.commander_id), ("host", binding.host_id)):
        getattr(boot.binding, key)[:] = l.uuid_words(value)
    boot.binding.binding_hash[:] = l.digest_words(binding.binding_hash)
    boot.binding.pid, boot.binding.player, boot.binding.thread = 1234, 3, 5678
    boot.binding.process_start = review._filetime(binding.game_process_start)
    for i, name in enumerate(("logic", "owner", "ai", "personality", "personality_id", "player_template", "default_team", "script_team")):
        setattr(boot.native, name, 100 + i)
    for name, value in dict(object_id=20, thing=200, template_ptr=300, update=400, owner=boot.native.owner, type_hash=0x19ab11af).items():
        setattr(boot.actor, name, value)
    actor = l.Actor.from_buffer_copy(bytes(boot.actor))
    actor.generation, actor.born_frame = 1, 100
    boot.producer.command[:] = (1, 2, 3, 4)
    boot.producer.task[:] = (5, 6, 7, 8)
    boot.producer.sequence = 1
    Receipt, Header = review._producer_types(l)
    paid, producer = Receipt(), Header()
    paid.version, paid.state, paid.debit_count = 2, 2, 1
    paid.paid = paid.cost = 85
    paid.quoted_cost = paid.command.budget = 85
    paid.attempted = paid.preserved = paid.queue_id = paid.node = 1
    paid.command.hash, paid.command.reserve, paid.cash = 0x19ab11af, 1000, 10000
    paid.created = paid.completed = paid.live_samples = 1
    paid.object_id, paid.object, paid.object_owner, paid.object_hash = actor.object_id, actor.thing, actor.owner, actor.type_hash
    paid.completion_frame = 99
    paid.command.id[:], paid.command.task[:] = boot.producer.command[:], boot.producer.task[:]
    paid.command.seq = 1
    paid.command.session[:], paid.command.commander[:] = boot.binding.session[:], boot.binding.commander[:]
    producer.magic, producer.version, producer.phase = 0x50434d44, 1, 1
    producer.pid, producer.thread, producer.owner = boot.binding.pid, boot.binding.thread, boot.native.owner
    producer.callback_thread = boot.binding.thread
    producer.session[:], producer.commander[:] = boot.binding.session[:], boot.binding.commander[:]
    for name in ("owner", "ai", "personality", "personality_id", "player_template"):
        setattr(producer, name, getattr(boot.native, name))
    producer.reserve_floor = 1000
    producer.start_low = boot.binding.process_start & 0xffffffff
    producer.start_high = boot.binding.process_start >> 32
    producer.count, producer.spent = 1, 85
    packets = []
    for i in range(2):
        p = l.Command()
        p.command[:], p.task[:], p.lease[:] = (i + 10, 0, 0, 0), (20, 0, 0, 0), (30, 0, 0, 0)
        p.sequence, p.operation, p.actor = i + 1, i + 1, actor
        p.expires_frame, p.lease_deadline_frame, p.expires_monotonic_ms = 800, 850, 100000
        p.hold_frames = 15 if i else 0
        p.target.x = 60 if i else 0
        packets.append(p)
    events, counters, frame, phase, x = [], [0] * 6, 100, 1, 0

    def emit(kind="observation", *, next_phase=None, action=None, extra=1):
        nonlocal frame, phase
        frame += extra
        if next_phase is not None:
            phase = next_phase
        if action is not None:
            counters[action - 1] += 1
        event = l.WireEvent()
        event.ticket, event.event_type = len(events) + 1, kind.encode()
        packet = packets[0 if phase <= 4 else 1]
        receipt, sample = event.receipt, event.observation
        receipt.command[:], receipt.task[:], receipt.lease[:] = packet.command[:], packet.task[:], packet.lease[:]
        receipt.sequence, receipt.phase, receipt.frame, receipt.monotonic_ms, receipt.accepted = packet.sequence, phase, frame, frame * 30, 1
        receipt.sdk_calls[:] = counters
        receipt.held = phase != 12
        if phase == 12:
            receipt.physical_home = receipt.control_released = receipt.stance_restored = 1
        sample.binding, sample.actor, sample.frame, sample.monotonic_ms = boot.binding, actor, frame, frame * 30
        sample.current_thread, sample.default_team, sample.script_team = boot.binding.thread, boot.native.default_team, boot.native.script_team
        sample.team, sample.stance = (sample.default_team, 0) if phase == 12 else (sample.script_team, 2)
        sample.xyz.x, sample.command_source = x, 1
        sample.identity = sample.actor_birth_verified = sample.live_list_member = sample.grounded = sample.settled = sample.interference_guard_ready = True
        sample.normal_move_owned = phase in (5, 8)
        events.append(event)

    def stopped(next_phase):
        emit("sdk_attempt", action=3)
        emit(); emit(); emit("phase", next_phase=next_phase)

    emit("phase", next_phase=1)
    emit("sdk_attempt", action=1)
    emit("phase", next_phase=2)
    emit("sdk_attempt", action=2)
    emit("phase", next_phase=3)
    stopped(4)
    emit("phase", next_phase=5)
    emit("sdk_attempt", action=4)
    x = 60
    emit()
    emit("phase", next_phase=6)
    stopped(7)
    emit("phase", next_phase=14, extra=15)
    stopped(8)
    emit("sdk_attempt", action=4)
    x = 0
    emit()
    emit("phase", next_phase=9)
    stopped(10)
    emit("sdk_attempt", action=5)
    emit("phase", next_phase=11)
    emit("sdk_attempt", action=6)
    emit("phase", next_phase=12)
    header = l.SharedChannel()
    header.magic_word, header.protocol, header.structure_size, header.token = l.MAGIC, l.VERSION, c.sizeof(l.SharedChannel), 5
    header.bootstrap, header.admitted_actor = boot, actor
    header.state, header.hooks_restored, header.callback_thread = 3, 8191, boot.binding.thread
    header.command_generation = header.command_acknowledged = 4
    header.receipt_generation, header.receipt, header.events_written = 100, events[-1].receipt, len(events)
    raw_header = bytes(header)[:l.SharedChannel.events.offset].hex()
    commands = []
    for i, p in enumerate(packets):
        ack = l.WireReceipt()
        ack.command[:], ack.task[:], ack.lease[:] = p.command[:], p.task[:], p.lease[:]
        ack.sequence, ack.accepted = p.sequence, 1
        commands.append(dict(wire_hex=bytes(p).hex(), acknowledged_hex=bytes(ack).hex(), published_generation=2 * (i + 1), acknowledgement_generation=2 * (i + 1)))
    signatures = review._entry_signatures()
    traces = []
    for kind, operation, self_pointer, target_pointer, caller, source, words in (
        (7, 1, boot.native.ai + 0x104, actor.thing, 0x838877, 0, 0),
        (3, 3, actor.update + 0x24, 0, 0, 1, 0),
        (4, 3, actor.update, 0, 0x787791, 1, 0),
        (1, 4, actor.update + 0x24, 1000, 0, 1, 3),
        (3, 3, actor.update + 0x24, 0, 0, 1, 0),
        (4, 3, actor.update, 0, 0x787791, 1, 0),
        (3, 3, actor.update + 0x24, 0, 0, 1, 0),
        (4, 3, actor.update, 0, 0x787791, 1, 0),
        (1, 4, actor.update + 0x24, 1000, 0, 1, 3),
        (3, 3, actor.update + 0x24, 0, 0, 1, 0),
        (4, 3, actor.update, 0, 0x787791, 1, 0),
        (6, 6, boot.native.ai + 0x104, actor.thing, 0x83885b, 0, 0)):
        t = l.WireHookTrace()
        t.ticket = len(traces) + 1
        for name, value in dict(frame=events[0].observation.frame + t.ticket, thread=boot.binding.thread,
            kind=kind, operation=operation, self=self_pointer, target=target_pointer, caller=caller,
            source=source, scope=1, word_count=words).items():
            setattr(t.trace, name, value)
        if kind == 1:
            goal = 60.0 if not any(review._decode(l.WireHookTrace, row["raw_hex"]).trace.kind == 1 for row in traces) else 0.0
            t.trace.words[:3] = struct.unpack("<3I", struct.pack("<3f", goal, 0.0, 0.0))
        traces.append(dict(ticket=t.ticket, raw_hex=bytes(t).hex()))
    trace_counters = struct.pack("<ii", len(traces), 0).hex()
    report = dict(schema_version=1, protocol="tactical_runtime_v1_diagnostic", diagnostic=True,
        ordinary_execution_granted=False, field_verified=False, binding=binding.public(),
        native_layout=l.inventory(), build_manifest={}, executor_sha256="d" * 64, native_host_sha256="e" * 64,
        bootstrap_hex=bytes(boot).hex(), admitted_actor_hex=bytes(actor).hex(),
        producer_receipt=dict(raw_hex=bytes(paid).hex(), native_header_hex=bytes(producer).hex()),
        terminal_headers=[raw_header, raw_header], header_before_hex=raw_header, header_after_hex=raw_header,
        host_exit=0, events_written=len(events), events_overwritten=0, commands=commands,
        events=[dict(ticket=e.ticket, event_type=review._reason(e.event_type), raw_hex=bytes(e).hex()) for e in events],
        hook_traces=traces, traces_written=len(traces), traces_overwritten=0,
        trace_counters_before_hex=trace_counters, trace_counters_after_hex=trace_counters,
        terminal_entries=[dict(address=k, expected=v, actual=v) for k, v in signatures.items()])
    return report, binding, l


class RuntimeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.report, self.binding, self.layout = fixture()
        self.build = patch.object(review, "verify_build_artifacts", return_value={"TacticoreRuntime1.dll": "d" * 64, "runtime_host.exe": "e" * 64})
        self.build.start()
        self.addCleanup(self.build.stop)

    def result(self):
        return review.qualify_runtime_report(self.report, self.binding)

    def mutate_event(self, index, change):
        event = review._decode(self.layout.WireEvent, self.report["events"][index]["raw_hex"])
        change(event)
        self.report["events"][index]["raw_hex"] = bytes(event).hex()

    def test_complete_raw_synthetic_fixture_only_qualifies_scoped_review(self):
        result = self.result()
        self.assertEqual("passed", result["status"], result)
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(result["ordinary_execution_granted"])
        self.assertFalse(result["combat_effect_verified"])

    def test_flags_without_raw_packets_fail(self):
        self.report = dict(schema_version=1, protocol="tactical_runtime_v1_diagnostic", diagnostic=True, ordinary_execution_granted=False, field_verified=False)
        self.assertEqual("not_passed", self.result()["status"])

    def test_new_land_build_needs_actual_endpoint_admission_tickets(self):
        self.report['build_manifest']={'inputs':[{'file':'land_geometry.h'}]}
        self.report['native_land_verified']=True
        self.assertEqual('native_endpoint_geometry',self.result()['reason_code'])

    def test_changed_binding_fails(self):
        self.report["binding"]["host_id"] = self.binding.commander_id
        self.assertEqual("exact_public_binding", self.result()["reason_code"])

    def test_current_home_gate_cannot_be_replaced_by_summary(self):
        self.report['build_manifest'] = {'inputs': [{'file': 'home_clearance.h'}]}
        self.report['current_home_vacancy'] = True
        self.assertEqual('current_home_vacancy', self.result()['reason_code'])

    def test_stale_build_fails(self):
        with patch.object(review, "verify_build_artifacts", side_effect=review.EvidenceError("built_source_changed")):
            self.assertEqual("built_source_changed", self.result()["reason_code"])

    def test_bootstrap_cannot_self_assign_generation(self):
        boot = review._decode(self.layout.Bootstrap, self.report["bootstrap_hex"])
        boot.actor.generation = 1
        self.report["bootstrap_hex"] = bytes(boot).hex()
        self.assertEqual("raw_bootstrap_binding", self.result()["reason_code"])

    def test_experimental_yield_cannot_grant_ordinary_scope(self):
        boot = review._decode(self.layout.Bootstrap, self.report["bootstrap_hex"])
        boot.experimental_flags = 1
        self.report["bootstrap_hex"] = bytes(boot).hex()
        self.assertEqual("raw_bootstrap_binding", self.result()["reason_code"])

    def test_controlled_fault_mode_is_explicit_readonly_only_not_ordinary_scope(self):
        boot=review._decode(self.layout.Bootstrap,self.report['bootstrap_hex'])
        boot.experimental_flags=2;self.report['bootstrap_hex']=bytes(boot).hex()
        checks={}
        review.verify_bootstrap_paid(self.report,self.binding,self.layout,lambda n,v:checks.update({n:v}),expected_experimental_flags=2)
        self.assertEqual({'raw_bootstrap_binding':True,'raw_paid_actor':True},checks)
        self.assertEqual('raw_bootstrap_binding',self.result()['reason_code'])
        boot.binding.pid+=1;self.report['bootstrap_hex']=bytes(boot).hex();checks.clear()
        review.verify_bootstrap_paid(self.report,self.binding,self.layout,lambda n,v:checks.update({n:v}),expected_experimental_flags=2)
        self.assertFalse(checks['raw_bootstrap_binding'])

    def test_mixed_or_unreviewed_diagnostic_flags_remain_refused(self):
        for flags in (True,3,4,-1,'2'):
            with self.subTest(flags=flags),self.assertRaisesRegex(review.EvidenceError,'experimental_review_mode_invalid'):
                review.verify_bootstrap_paid(self.report,self.binding,self.layout,lambda n,v:None,expected_experimental_flags=flags)

    def test_truncated_event_fails(self):
        self.report["events"][0]["raw_hex"] = "00"
        self.assertEqual("raw_packet_size_or_encoding", self.result()["reason_code"])

    def test_missing_event_fails(self):
        del self.report["events"][1]
        self.assertEqual("closed_event_stream", self.result()["reason_code"])

    def test_changed_actor_generation_fails(self):
        self.mutate_event(1, lambda e: setattr(e.observation.actor, "generation", 2))
        self.assertEqual("raw_event_identities", self.result()["reason_code"])

    def test_wrong_process_fails(self):
        self.mutate_event(1, lambda e: setattr(e.observation.binding, "pid", 999))
        self.assertEqual("raw_event_identities", self.result()["reason_code"])

    def test_clock_regression_fails(self):
        self.mutate_event(1, lambda e: setattr(e.observation, "frame", 100))
        self.assertEqual("monotonic_observations", self.result()["reason_code"])

    def test_external_control_fails(self):
        self.mutate_event(1, lambda e: setattr(e.observation, "foreign_epoch", 1))
        self.assertEqual("no_foreign_control", self.result()["reason_code"])

    def test_missing_stop_sample_fails(self):
        self.mutate_event(7, lambda e: setattr(e.observation, "settled", False))
        self.assertEqual("three_frame_stops", self.result()["reason_code"])

    def test_different_original_entry_bytes_fail(self):
        self.report["terminal_entries"][0]["actual"] = "00"
        self.assertEqual("independent_original_entry_bytes", self.result()["reason_code"])

    def test_unacknowledged_command_fails(self):
        self.report["commands"][0]["acknowledgement_generation"] = 3
        self.assertEqual("original_command_packets", self.result()["reason_code"])

    def test_nonterminal_headers_fail(self):
        self.report["terminal_headers"] = []
        self.assertEqual("terminal_headers_missing", self.result()["reason_code"])

    def test_incomplete_payment_fails(self):
        Receipt, _ = review._producer_types(self.layout)
        paid = review._decode(Receipt, self.report["producer_receipt"]["raw_hex"])
        paid.paid = 84
        self.report["producer_receipt"]["raw_hex"] = bytes(paid).hex()
        self.assertEqual("raw_paid_actor", self.result()["reason_code"])

    def pinned(self, binding=None, pin=None, raw=None):
        raw = json.dumps(self.report).encode() if raw is None else raw
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-reviewer-test.json"
            path.write_bytes(raw)
            return review.verify_pinned_runtime(path, pin or hashlib.sha256(raw).hexdigest(), binding or self.binding)

    def test_explicit_pinned_boundary_retains_exact_local_scope(self):
        # Artifact verifier remains mocked: this is never registered in a Host.
        grant = self.pinned()
        self.assertEqual("tactics.move_hold_return", grant.capability_id)
        constraints = grant.public()["execution_constraints"]
        self.assertEqual("move_hold_return", constraints["purpose"])
        self.assertEqual(["infantry"], constraints["actor_roles"])
        self.assertEqual("e" * 64, constraints["native_host_sha256"])

    def test_pin_mismatch_fails_before_review(self):
        with self.assertRaisesRegex(review.ContractError, "runtime_evidence_pin_mismatch"):
            self.pinned(pin="f" * 64)

    def test_scope_cannot_cross_to_another_package(self):
        with self.assertRaisesRegex(review.ContractError, "runtime_evidence_package_or_scope_mismatch"):
            self.pinned(binding=replace(self.binding, mod_sha256="c" * 64))

    def test_new_process_can_reuse_scope_but_still_needs_native_admission(self):
        grant = self.pinned(binding=replace(self.binding, game_process_id=9999,
            session_id="44444444-4444-4444-8444-444444444444"))
        self.assertEqual("tactics.move_hold_return", grant.capability_id)

    def test_duplicate_json_key_fails(self):
        with self.assertRaisesRegex(review.ContractError, "runtime_evidence_duplicate_key"):
            self.pinned(raw=b'{"binding":{},"binding":{}}')

    def test_false_raw_flags_cannot_create_registered_capability(self):
        self.report["field_verified"] = True
        with self.assertRaisesRegex(review.ContractError, "runtime_raw_evidence_unverified"):
            self.pinned()

    def test_missing_hook_trace_fails(self):
        self.report["hook_traces"].pop()
        self.assertEqual("closed_native_hook_trace", self.result()["reason_code"])

    def test_wrong_roster_caller_fails(self):
        row = self.report["hook_traces"][0]
        trace = review._decode(self.layout.WireHookTrace, row["raw_hex"])
        trace.trace.caller = 0x12345
        row["raw_hex"] = bytes(trace).hex()
        self.assertEqual("closed_native_hook_trace", self.result()["reason_code"])

    def test_foreign_hook_epoch_fails(self):
        row = self.report["hook_traces"][0]
        trace = review._decode(self.layout.WireHookTrace, row["raw_hex"])
        trace.trace.epoch_after = 1
        row["raw_hex"] = bytes(trace).hex()
        self.assertEqual("closed_native_hook_trace", self.result()["reason_code"])

    def test_unstable_trace_counters_fail(self):
        self.report["trace_counters_after_hex"] = "00" * 8
        self.assertEqual("native_hook_trace_counters_unstable", self.result()["reason_code"])

    def test_native_move_goal_must_match_requested_target(self):
        row = next(row for row in self.report["hook_traces"]
                   if review._decode(self.layout.WireHookTrace, row["raw_hex"]).trace.kind == 1)
        trace = review._decode(self.layout.WireHookTrace, row["raw_hex"])
        self.assertNotEqual(0, trace.trace.words[0])
        trace.trace.words[0] = 0
        row["raw_hex"] = bytes(trace).hex()
        self.assertEqual("physical_target_and_home", self.result()["reason_code"])


@unittest.skipUnless((review.RUNTIME / "bin/atomic_publish.dll").is_file(), "Build the Windows host atomic bridge to inspect its PE metadata")
class ActualHostBridgeMetadataTests(unittest.TestCase):
    """Read current local artifact metadata; never load modified executable data."""
    def setUp(self):
        self.raw = bytearray((review.RUNTIME / "bin/atomic_publish.dll").read_bytes())
        self.pe = struct.unpack_from("<I", self.raw, 0x3c)[0]

    def test_actual_bridge_is_x64_noentry_single_export_noimports(self):
        review.verify_pe(self.raw, 0x8664, host_atomic=True)

    def test_wrong_machine_is_rejected(self):
        struct.pack_into("<H", self.raw, self.pe + 4, 0x14c)
        with self.assertRaisesRegex(review.EvidenceError, "binary_machine_unverified"):
            review.verify_pe(self.raw, 0x8664, host_atomic=True)

    def test_entrypoint_is_rejected(self):
        struct.pack_into("<I", self.raw, self.pe + 24 + 16, 0x1000)
        with self.assertRaisesRegex(review.EvidenceError, "atomic_helper_entry_or_architecture"):
            review.verify_pe(self.raw, 0x8664, host_atomic=True)

    def test_import_table_is_rejected(self):
        struct.pack_into("<I", self.raw, self.pe + 24 + 112 + 8, 0x2000)
        with self.assertRaisesRegex(review.EvidenceError, "atomic_helper_has_imports_or_tls"):
            review.verify_pe(self.raw, 0x8664, host_atomic=True)

    def test_wrong_export_is_rejected(self):
        self.raw[self.raw.index(b"runtime_exchange")] = ord("x")
        with self.assertRaisesRegex(review.EvidenceError, "atomic_helper_export_inventory"):
            review.verify_pe(self.raw, 0x8664, host_atomic=True)


if __name__ == "__main__":
    unittest.main()
