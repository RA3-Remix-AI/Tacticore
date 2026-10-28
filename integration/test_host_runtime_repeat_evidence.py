"""Synthetic reviewer tests only; these never create field evidence or authority."""
from contextlib import closing
import ctypes as c
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
from unittest.mock import patch

from host_runtime import runtime_repeat_evidence as review
from host_runtime.runtime_evidence import _decode, _reason
from test_host_runtime_runtime_evidence import fixture


class RepetitionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name)/'synthetic.sqlite3'
        self.scope = Path(self.temp.name)/'synthetic-scope.json'
        self.scope.write_text('{}')
        self.report, binding, self.l = fixture()
        r, l = self.report, self.l
        first = {key:list(r[key]) for key in ('commands','events','hook_traces')}
        for key in first:
            r[key] = []
        self.trial = dict(session_id=binding.session_id,journal_run_id='synthetic-run',
            status='journaled_native_terminal_requires_independent_review',journal_unresolved=[],journaled_tasks=[])
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('CREATE TABLE commands(command_id TEXT,run_id TEXT,operation TEXT,status TEXT,receipt TEXT)')
            db.execute('CREATE TABLE native_sequences(run_id TEXT,sequence INTEGER)')
            for n in range(2):
                for row in first['commands']:
                    p = _decode(l.Command,row['wire_hex'])
                    p.command[0] += 100*n; p.task[0] += n; p.lease[0] += n; p.sequence += 2*n
                    a = _decode(l.WireReceipt,row['acknowledged_hex'])
                    a.command[:],a.task[:],a.lease[:],a.sequence = p.command[:],p.task[:],p.lease[:],p.sequence
                    r['commands'].append(dict(wire_hex=bytes(p).hex(),acknowledged_hex=bytes(a).hex(),published_generation=2*p.sequence))
                    db.execute('INSERT INTO native_sequences VALUES(?,?)',('synthetic-run',p.sequence))
                    receipt = dict(game_frame=0,task_id=l.uuid_text(p.task),lease_id=l.uuid_text(p.lease),
                        mission_effect_verified=True,physical_home=True,control_released=True,stance_restored=True)
                    if p.operation == 2:
                        final = _decode(l.WireEvent,first['events'][-1]['raw_hex'])
                        receipt['game_frame'] = final.observation.frame+200*n
                    db.execute('INSERT INTO commands VALUES(?,?,?,?,?)',(l.uuid_text(p.command),'synthetic-run',
                        'reserve' if p.operation==1 else 'commit','completed' if p.operation==1 else 'released',
                        json.dumps(dict(facts=receipt))))
                for row in first['events']:
                    e = _decode(l.WireEvent,row['raw_hex'])
                    e.ticket = len(r['events'])+1
                    e.receipt.command[0] += 100*n; e.receipt.task[0] += n; e.receipt.lease[0] += n; e.receipt.sequence += 2*n
                    e.receipt.frame += 200*n; e.observation.frame += 200*n
                    e.receipt.monotonic_ms += 6000*n; e.observation.monotonic_ms += 6000*n
                    if e.receipt.phase == 12:
                        e.receipt.reason = b'native_control_release_observed'
                    r['events'].append(dict(ticket=e.ticket,event_type=_reason(e.event_type),raw_hex=bytes(e).hex()))
                for row in first['hook_traces']:
                    t = _decode(l.WireHookTrace,row['raw_hex'])
                    t.ticket = len(r['hook_traces'])+1; t.trace.frame += 200*n
                    r['hook_traces'].append(dict(ticket=t.ticket,raw_hex=bytes(t).hex()))
                count = 2*(n+1)
                self.trial['journaled_tasks'].append(dict(idempotent_replay=dict(
                    before=dict(sequence=count,native_commands=count),after=dict(sequence=count,native_commands=count),
                    same_commit=True,same_reserve=True)))
        h = _decode(l.SharedChannel,r['terminal_headers'][0],l.SharedChannel.events.offset)
        h.command_generation = h.command_acknowledged = 8; h.native_last_sequence = 4
        h.events_written = r['events_written'] = len(r['events'])
        header = bytes(h)[:l.SharedChannel.events.offset].hex()
        r.update(diagnostic=False,field_scope_admitted=True,field_evidence_id='f'*64,
            terminal_headers=[header,header],header_before_hex=header,header_after_hex=header,
            traces_written=len(r['hook_traces']))
        r['trace_counters_before_hex'] = r['trace_counters_after_hex'] = struct.pack('<ii',r['traces_written'],0).hex()
        for name, value in [('verify_pinned_runtime',None),('verify_build_artifacts',
                {'TacticoreRuntime1.dll':'d'*64,'runtime_host.exe':'e'*64})]:
            p = patch.object(review,name,return_value=value);p.start();self.addCleanup(p.stop)

    def result(self):
        return review.qualify_repetition(self.report,self.trial,self.db,self.scope,'f'*64)

    def test_two_synthetic_leases_qualify_review_without_grant(self):
        result = self.result()
        self.assertEqual('passed',result['status'],result)
        self.assertFalse(result['capability_granted'])
        self.assertEqual(2,len(result['facts']['tasks']))

    def test_missing_native_packet_cannot_be_replaced_by_journal_summary(self):
        self.report['commands'].pop()
        self.assertEqual('four_original_packets',self.result()['reason_code'])

    def test_current_home_gate_requires_original_proofs_for_each_task(self):
        self.report['build_manifest'] = {'inputs': [{'file': 'home_clearance.h'}]}
        self.trial['current_home_vacancy'] = True
        self.assertEqual('task1_current_home_vacancy', self.result()['reason_code'])

    def test_journal_release_must_match_native_frame(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE commands SET receipt=? WHERE operation='commit'",(json.dumps(dict(facts=dict(game_frame=999))),))
        self.assertEqual('task1_journal_matches_raw',self.result()['reason_code'])

    def test_duplicate_dispatch_cannot_be_called_idempotent(self):
        self.trial['journaled_tasks'][0]['idempotent_replay']['after']['native_commands'] = 3
        self.assertEqual('task1_no_replay_dispatch',self.result()['reason_code'])

    def test_return_without_goal_effect_fails(self):
        for row in self.report['events']:
            e = _decode(self.l.WireEvent,row['raw_hex'])
            if e.receipt.phase == 12:
                e.receipt.reason = b'native_control_release_without_goal_effect'
                row['raw_hex'] = bytes(e).hex()
        self.assertEqual('task1_physical_effect_and_home',self.result()['reason_code'])

    def test_stale_stop_witness_does_not_pass(self):
        for row in self.report['events']:
            e = _decode(self.l.WireEvent,row['raw_hex'])
            if e.receipt.phase == 3:
                e.observation.settled = False;row['raw_hex'] = bytes(e).hex()
        self.assertEqual('task1_stop4',self.result()['reason_code'])

    def test_scope_does_not_hide_foreign_native_command(self):
        row = self.report['events'][-1]
        e = _decode(self.l.WireEvent,row['raw_hex']);e.observation.foreign_epoch = 1
        row['raw_hex'] = bytes(e).hex()
        self.assertEqual('no_foreign_or_unknown',self.result()['reason_code'])


if __name__ == '__main__':
    unittest.main()
