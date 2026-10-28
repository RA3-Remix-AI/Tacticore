"""Read-only review of two actual HostTactical leases and their SQLite journal.

Never manufactures diagnostic headers or renumbers tickets to reuse a one-task
review. This review grants no new capability and never attaches to a game.
"""
from __future__ import annotations

from contextlib import closing
import ctypes as c
import json
from pathlib import Path
import sqlite3
import struct

from .contracts import SessionBinding
from .runtime_home_evidence import valid_row as _home_trace_valid,groups as _home_groups,has_return_proof
from .runtime_evidence import (EvidenceError, _decode, _distance, _entry_signatures,_catalogue_trace_valid,_land_trace_valid,_land_groups,has_move_proof,
    _layout, _point, _reason, _values, verify_bootstrap_paid, verify_build_artifacts,
    verify_pinned_runtime)


def qualify_repetition(report, trial, journal_path, scope_path, scope_sha256):
    checks, facts = {}, {}

    def check(name, condition):
        checks[name] = condition is True
        if not checks[name]:
            raise EvidenceError(name)

    try:
        binding = SessionBinding.from_dict(report['binding'])
        verify_pinned_runtime(Path(scope_path).resolve(strict=True), scope_sha256, binding)
        check('reviewed_current_scope', report.get('diagnostic') is False
            and report.get('protocol') == 'tactical_runtime_v1_diagnostic'
            and report.get('field_scope_admitted') is True
            and report.get('field_evidence_id') == scope_sha256)
        l = _layout()
        hashes = verify_build_artifacts(report['build_manifest'], l)
        check('current_build_and_abi', report['native_layout'] == l.inventory()
            and report['executor_sha256'] == hashes['TacticoreRuntime1.dll']
            and report['native_host_sha256'] == hashes['runtime_host.exe'])
        boot, actor = verify_bootstrap_paid(report, binding, l, check)
        headers = report['terminal_headers']
        check('two_stable_terminal_headers', len(headers) == 2 and headers[0] == headers[1]
            == report['header_before_hex'] == report['header_after_hex'])
        h = _decode(l.SharedChannel, headers[0], l.SharedChannel.events.offset)
        check('native_cleanup', h.state == 3 and h.hooks_restored == 8191
            and h.active_callbacks == 0 and h.callback_thread == boot.binding.thread
            and report['host_exit'] == 0 and bytes(h.bootstrap) == bytes(boot)
            and _values(h.admitted_actor) == _values(actor)
            and h.magic_word == l.MAGIC and h.protocol == l.VERSION
            and h.structure_size == c.sizeof(l.SharedChannel) and h.token > 0)
        rows = report['commands']
        packets = [_decode(l.Command, r['wire_hex']) for r in rows]
        acks = [_decode(l.WireReceipt, r['acknowledged_hex']) for r in rows]
        check('four_original_packets', len(rows) == 4
            and [p.operation for p in packets] == [1, 2, 1, 2]
            and [p.sequence for p in packets] == [1, 2, 3, 4]
            and len({tuple(p.command) for p in packets}) == 4
            and all(_values(p.actor) == _values(actor) and a.accepted == 1
                and tuple(p.command) == tuple(a.command) and tuple(p.task) == tuple(a.task)
                and tuple(p.lease) == tuple(a.lease) and p.sequence == a.sequence
                and r['published_generation'] == 2 * (i + 1)
                for i, (p, a, r) in enumerate(zip(packets, acks, rows))))
        check('four_native_acknowledgements', h.command_generation == h.command_acknowledged == 8
            and h.native_last_sequence == 4)
        check('separate_leases', tuple(packets[0].task) == tuple(packets[1].task)
            and tuple(packets[2].task) == tuple(packets[3].task)
            and tuple(packets[0].task) != tuple(packets[2].task)
            and tuple(packets[0].lease) == tuple(packets[1].lease)
            and tuple(packets[2].lease) == tuple(packets[3].lease)
            and tuple(packets[0].lease) != tuple(packets[2].lease))
        events = [_decode(l.WireEvent, r['raw_hex']) for r in report['events']]
        check('closed_event_stream', 0 < len(events) == h.events_written == report['events_written'] <= l.CAPACITY
            and h.events_overwritten == report['events_overwritten'] == 0
            and all(e.ticket == r['ticket'] == i + 1 and _reason(e.event_type) == r['event_type']
                for i, (e, r) in enumerate(zip(events, report['events']))))
        packet_by_id = {tuple(p.command): p for p in packets}
        check('all_native_identities', all(tuple(e.receipt.command) in packet_by_id
            and tuple(e.receipt.task) == tuple(packet_by_id[tuple(e.receipt.command)].task)
            and tuple(e.receipt.lease) == tuple(packet_by_id[tuple(e.receipt.command)].lease)
            and e.receipt.sequence == packet_by_id[tuple(e.receipt.command)].sequence
            and _values(e.observation.binding) == _values(boot.binding)
            and _values(e.observation.actor) == _values(actor)
            and e.observation.identity and e.observation.actor_birth_verified
            and e.observation.live_list_member and e.observation.grounded
            and not e.observation.paused and e.observation.current_thread == boot.binding.thread
            and e.receipt.frame == e.observation.frame
            and e.receipt.monotonic_ms == e.observation.monotonic_ms for e in events))
        check('no_foreign_or_unknown', len({e.observation.foreign_epoch for e in events}) == 1
            and all(_reason(e.event_type) not in ('uncertain', 'command_rejected') for e in events))
        check('dual_clock_order', all(a.observation.frame <= b.observation.frame
            and a.observation.monotonic_ms <= b.observation.monotonic_ms for a, b in zip(events, events[1:])))
        traces = [_decode(l.WireHookTrace, r['raw_hex']) for r in report['hook_traces']]
        counters = report['trace_counters_before_hex']
        check('closed_trace_stream', counters == report['trace_counters_after_hex']
            and struct.unpack('<ii', bytes.fromhex(counters)) == (len(traces), 0)
            and 0 < len(traces) == report['traces_written'] <= l.TRACE_CAPACITY
            and report['traces_overwritten'] == 0
            and all(t.ticket == r['ticket'] == i + 1 and t.trace.thread == boot.binding.thread
                and (1<=t.trace.kind<=17 or _catalogue_trace_valid(t.trace,actor) or _land_trace_valid(t.trace,actor) or _home_trace_valid(t.trace,actor))
                and t.trace.epoch_before == t.trace.epoch_after == events[0].observation.foreign_epoch
                for i, (t, r) in enumerate(zip(traces, report['hook_traces']))))
        check('trace_frame_order', all(a.trace.frame <= b.trace.frame for a, b in zip(traces,traces[1:])))
        check('no_native_attack', not any(t.trace.kind == 9 for t in traces))
        land=_land_groups([t.trace for t in traces],actor,boot.native.logic)
        check('complete_native_land_proofs',land is not None)
        home_proofs=_home_groups([t.trace for t in traces],actor,boot.native.logic,boot.native.script_team)
        home_required=any(x.get('file')=='home_clearance.h' for x in report['build_manifest'].get('inputs',[]))
        check('complete_native_home_proofs',home_proofs is not None)
        task_facts, previous_end = [], 0
        for n in range(2):
            reserve, commit = packets[2*n:2*n+2]
            selected = [e for e in events if tuple(e.receipt.task) == tuple(reserve.task)]
            phase_rows = [(i, e) for i, e in enumerate(selected) if _reason(e.event_type) == 'phase']
            check(f'task{n+1}_complete_phases', [e.receipt.phase for _, e in phase_rows]
                == [1, 2, 3, 4, 5, 6, 7, 14, 8, 9, 10, 11, 12])
            phase = {e.receipt.phase: e for _, e in phase_rows}
            home, target = _point(phase[1].observation.xyz), _point(commit.target)
            home_moves=[t.trace for t in traces if t.trace.kind==1 and t.trace.operation==4
                        and phase[8].observation.frame<=t.trace.frame<=phase[9].observation.frame]
            check(f'task{n+1}_current_home_vacancy',not home_required or (len(home_moves)==1
                  and has_return_proof(home_proofs,home,home_moves[0].frame,
                                       [e.observation for e in selected],boot.native.script_team)))
            required=any(x.get('file')=='land_geometry.h' for x in report['build_manifest'].get('inputs',[]))
            moves=[t.trace for t in traces if t.trace.kind==1 and t.trace.operation==4
                and phase[5].observation.frame<=t.trace.frame<=phase[6].observation.frame]
            check(f'task{n+1}_native_endpoint_geometry',not required or (len(moves)==1 and has_move_proof(land,commit.target,moves[0].frame)))
            last = phase[12]
            check(f'task{n+1}_ordered_ownership', previous_end < phase[1].observation.frame
                and last.observation.frame <= reserve.lease_deadline_frame == commit.lease_deadline_frame
                and last.observation.frame - phase[1].observation.frame <= 900)
            previous_end = last.observation.frame
            check(f'task{n+1}_physical_effect_and_home', 20 <= _distance(home, target) <= 120
                and _distance(_point(phase[7].observation.xyz), target) <= 15
                and _distance(_point(last.observation.xyz), home) <= 15
                and abs(last.observation.xyz.z-home[2]) <= 2
                and phase[14].observation.frame-phase[7].observation.frame >= commit.hold_frames > 0
                and last.receipt.physical_home == last.receipt.control_released == last.receipt.stance_restored == 1
                and not last.receipt.held and last.observation.team == last.observation.default_team
                and last.observation.stance == 0
                and _reason(last.receipt.reason) == 'native_control_release_observed')
            for end, event in phase_rows:
                if event.receipt.phase not in (4, 7, 8, 10):
                    continue
                start = max((i for i in range(end) if _reason(selected[i].event_type) == 'sdk_attempt'
                    and (i == 0 or selected[i].receipt.sdk_calls[2] > selected[i-1].receipt.sdk_calls[2])), default=-1)
                distinct = {e.observation.frame: e.observation for e in selected[start+1:end+1]}
                tail = list(distinct.values())[-3:]
                check(f'task{n+1}_stop{event.receipt.phase}', start >= 0 and len(tail) == 3
                    and all(s.settled and s.stance == 2 and s.team == s.script_team and s.path == 0
                        and s.command_source == 1 for s in tail)
                    and all(_distance(_point(a.xyz), _point(b.xyz)) <= 1 for a, b in zip(tail, tail[1:])))
            own_traces = [t.trace for t in traces if phase[1].observation.frame <= t.trace.frame <= last.observation.frame]
            moves = [t for t in own_traces if t.kind == 1]
            goals = [struct.unpack('<3f', struct.pack('<3I', *t.words[:3])) for t in moves]
            check(f'task{n+1}_original_move_goals', goals == [target, home]
                and all(t.self == actor.update+0x24 and t.source == t.scope == 1 for t in moves)
                and tuple(last.receipt.sdk_calls) == (1, 1, 4, 2, 1, 1))
            check(f'task{n+1}_bounded_native_calls', all(all(x <= y for x,y in zip(a.receipt.sdk_calls,b.receipt.sdk_calls))
                for a,b in zip(selected,selected[1:])))
            task_facts.append(dict(task_id=l.uuid_text(commit.task),command_id=l.uuid_text(commit.command),
                lease_id=l.uuid_text(commit.lease),released_frame=last.observation.frame,home=home,target=target))
        original = _entry_signatures()
        check('all_original_entries', len(report['terminal_entries']) == len(original)
            and len({r['address'] for r in report['terminal_entries']}) == len(original)
            and all(r['actual'] == r['expected'] == original[r['address']] for r in report['terminal_entries']))
        check('trial_terminal', trial['status'] == 'journaled_native_terminal_requires_independent_review'
            and trial['session_id'] == binding.session_id and trial['journal_unresolved'] == []
            and len(trial['journaled_tasks']) == 2)
        with closing(sqlite3.connect(Path(journal_path).resolve().as_uri()+'?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            rows = list(db.execute('SELECT * FROM commands WHERE run_id=?', (trial['journal_run_id'],)))
            sequences = list(db.execute('SELECT sequence FROM native_sequences WHERE run_id=? ORDER BY sequence', (trial['journal_run_id'],)))
        by_id = {r['command_id']: r for r in rows}
        check('exact_authoritative_journal', len(rows) == 4
            and set(by_id) == {l.uuid_text(p.command) for p in packets}
            and [r['sequence'] for r in sequences] == [1, 2, 3, 4])
        for n, t in enumerate(trial['journaled_tasks']):
            replay = t['idempotent_replay']
            check(f'task{n+1}_no_replay_dispatch', replay['before'] == replay['after']
                == dict(sequence=2*(n+1),native_commands=2*(n+1))
                and replay['same_commit'] is True and replay['same_reserve'] is True)
            row = by_id[task_facts[n]['command_id']]
            receipt = json.loads(row['receipt'])['facts']
            check(f'task{n+1}_journal_matches_raw', row['operation'] == 'commit' and row['status'] == 'released'
                and receipt['game_frame'] == task_facts[n]['released_frame']
                and receipt['task_id'] == task_facts[n]['task_id']
                and receipt['lease_id'] == task_facts[n]['lease_id']
                and all(receipt[k] is True for k in ('mission_effect_verified','physical_home','control_released','stance_restored')))
        facts = dict(tasks=task_facts,object_id=actor.object_id,generation=actor.generation)
    except (ValueError, KeyError, TypeError, OSError, AttributeError, IndexError, struct.error, sqlite3.Error) as error:
        return dict(status='not_passed',reason_code=str(error) if isinstance(error,EvidenceError) else type(error).__name__,checks=checks,facts=facts,capability_granted=False)
    return dict(status='passed',reason_code='ok',checks=checks,facts=facts,capability_granted=False,
        scope='Two sequential paid single-actor local Move/Hold/home/return tasks only; no combat or natural-result credit')
