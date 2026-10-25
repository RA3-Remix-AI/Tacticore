"""Bound-buffer software tests. Never attach to a game, host or live mapping."""
import copy
import ctypes as c
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import local_mission_risk_v1 as m

RAW = m.ROOT / 'acceptance/runs/20261026-012024-commander/continuous-paid-margin12-static01-formation.json'
SIDE = RAW.with_name('mf12-01-loss-absence-readonly.json')


def fill(value, source):
    for name, typ in value._fields_:
        if name not in source:
            continue
        item = getattr(value, name); data = source[name]
        if isinstance(item, c.Structure):
            fill(item, data)
        elif isinstance(item, c.Array):
            for i, x in enumerate(data):
                if isinstance(item[i], c.Structure):
                    fill(item[i], x)
                else:
                    item[i] = x
        else:
            setattr(value, name, data)


class Channel:
    def __init__(self, layout, events, header):
        self.layout = layout; self.events = events; self.h = header
        self.writes = []; self.live = True; self.closed = False; self.corrupt_seq = None
        self.mutate_before_request = None; self.header_reads = 0

    def header(self):
        self.header_reads += 1
        if self.mutate_before_request and self.header_reads == 4:
            self.mutate_before_request(self.h)
        return self.layout.Header.from_buffer_copy(bytes(self.h))

    def event(self, index):
        e = self.layout.Event.from_buffer_copy(bytes(self.events[index]))
        if e.seq != index+1 or index == self.corrupt_seq:
            raise m.NotReady('waiting_native_publication')
        return e

    def alive(self):return self.live
    def tick(self):return self.events[self.h.count-1].tick + 10
    def request(self):
        self.writes.append(('retreat_requested', 1)); self.h.retreat_requested = 1
    def close(self):self.closed = True


class Monitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(RAW.read_text(encoding='utf-8-sig'))
        cls.layout = m._load_layout()
        cls.events = []
        for row in cls.original['events']:
            e = cls.layout.Event(); fill(e, row); cls.events.append(e)
        cls.header = cls.layout.Header.from_buffer_copy(bytes.fromhex(json.loads(SIDE.read_text())['snapshots'][0]['header_hex']))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name)
        self.report = copy.deepcopy(self.original)
        self.report.update(status='running'); self.report.pop('host_exit', None)
        self.report['native'].update(phase=1, error=0)
        self.session = json.loads(RAW.with_name('session.json').read_text(encoding='utf-8-sig'))
        self.session['run_directory'] = str(self.path)
        registry = self.path/'registry.json'; registry.write_text('{}'); self.session['registry'] = str(registry); self.session['registry_revision'] = m.sha(registry)
        mission = self.path/'mission.json'; mission.write_bytes(Path(self.report['request']['mission_source_path']).read_bytes()); self.report['request']['mission_source_path'] = str(mission)
        self.rp = self.path/'active.json'; self.sp = self.path/'session.json'; self.out = self.path/'risk.jsonl'
        self.sp.write_text(json.dumps(self.session)); self.write_report()
        h = self.layout.Header.from_buffer_copy(bytes(self.header))
        h.phase=1; h.mission_stage=1; h.error=0; h.stop_requested=0; h.return_pending=0; h.retreat_requested=0
        h.return_calls=0; h.return_verified=0; h.support.return_calls=0; h.support.returned=0
        h.lifecycle_fail=0; h.owner_fail=0; h.overflow=0
        self.channel = Channel(self.layout, [self.layout.Event.from_buffer_copy(bytes(e)) for e in self.events], h)
        self.round(1856)
        self.enabled = patch.object(m, 'LIVE_MONITOR_ENABLED', True); self.enabled.start()
        self.opened = patch.object(m, '_open_channel', return_value=self.channel); self.factory = self.opened.start()
        self.mon = m.MissionRiskMonitor(self.rp, self.sp, self.out)

    def tearDown(self):
        self.mon.close(); self.opened.stop(); self.enabled.stop(); self.temp.cleanup()

    def write_report(self):self.rp.write_text(json.dumps(self.report), encoding='utf-8')

    def round(self, frame):
        pair = [e for e in self.channel.events if e.kind == 3 and e.frame == frame]
        self.channel.h.count = pair[-1].seq; self.channel.h.motion_last_tick=frame
        self.channel.h.pulse_acknowledged=pair[-1].tick
        return pair

    def polls(self, count=8):
        value = None
        for i in range(count):
            value=self.mon.poll()
            if value['request_written'] or self.mon.closed:break
        return value

    def test_actual_source_startup_issued71_before_set2_waits_then_observes(self):
        self.channel.h.phase=5;self.channel.h.mission_stage=0
        self.channel.h.count=max(e.seq for e in self.channel.events if e.kind==71)
        self.channel.h.motion_last_tick=0
        result=self.mon.poll();self.assertEqual(result['state'],'waiting_native',result)
        self.assertFalse(self.mon.closed);self.assertFalse(self.channel.writes)
        self.channel.h.phase=1;self.channel.h.mission_stage=1;self.round(1444)
        self.assertEqual(self.polls()['state'],'observing');self.assertFalse(self.channel.writes)

    def test_unpublished_sequence_waits_then_recovers_without_json_sample_credit(self):
        self.channel.corrupt_seq=self.channel.h.count-2
        self.assertEqual(self.polls()['state'],'waiting_native');self.assertFalse(self.channel.writes)
        self.channel.corrupt_seq=None;self.assertTrue(self.polls()['request_written'])

    def test_post_store_audit_failure_does_not_lie_about_flag_write(self):
        original=self.mon._record
        def record(event,**facts):
            if event=='retreat_flag_written':raise OSError('software_test_only')
            return original(event,**facts)
        with patch.object(self.mon,'_record',side_effect=record):result=self.polls()
        self.assertTrue(result['request_written']);self.assertTrue(result['audit_commit_failed']);self.assertEqual(len(self.channel.writes),1)
        self.assertFalse(self.mon.poll()['request_written'])

    def test_current_mapping_risk_requests_once_not_cached_report(self):
        # The cached report says healthy/currently visible; shared samples are
        # actual real-log1856 HP97.5/FOV0, copied into this isolated fake buffer.
        for e in self.report['events']:
            if e['kind']==3:e.update(own_hp=100.,target_visible=1)
        self.write_report();before=bytes(self.channel.h);result=self.polls()
        self.assertTrue(result['request_written'],result);self.assertEqual(result['reason'],'target_lost')
        self.assertEqual(result['request_frame'],1856);self.assertFalse(result['native_acknowledged']);self.assertFalse(result['completed'])
        self.assertEqual(self.channel.writes,[('retreat_requested',1)])
        after=bytes(self.channel.h);off=self.layout.Tactical.retreat_requested.offset
        self.assertEqual(before[:off]+before[off+4:],after[:off]+after[off+4:])
        self.assertFalse(self.mon.poll()['request_written']);self.assertEqual(len(self.channel.writes),1)
        rows=[json.loads(x) for x in self.out.read_text().splitlines()];request=next(x for x in rows if x['event']=='retreat_flag_written')
        self.assertEqual(request['issued_baseline_hp'],[100.,120.]);self.assertEqual(request['own_hp'],[97.5,120.]);self.assertEqual(len(request['raw_pair_hex']),2)

    def test_disabled_and_constructor_never_attach(self):
        self.factory.assert_not_called()
        with patch.object(m,'LIVE_MONITOR_ENABLED',False):self.assertEqual(self.mon.poll()['state'],'candidate_disabled')
        self.factory.assert_not_called();self.assertFalse(self.out.exists())

    def test_fov_true_or_no_health_loss_never_requests(self):
        for kind in ('visible','healthy'):
            self.mon.close();self.mon=m.MissionRiskMonitor(self.rp,self.sp,self.path/('risk-'+kind+'.jsonl'));self.channel.closed=False
            pair=self.round(1856)
            for e in pair:
                if kind=='visible':e.target_visible=1
                else:e.own_hp=100. if e.role==0 else 120.
            self.polls();self.assertEqual(self.channel.writes,[],kind)

    def test_same_frame_pause_duplicate_never_progresses_or_requests(self):
        self.round(1840);self.polls();self.assertFalse(self.channel.writes)
        frame=self.mon.last_frame
        for _ in range(3):self.mon.poll()
        self.assertEqual(self.mon.last_frame,frame);self.assertFalse(self.channel.writes)

    def test_foreign_header_uuid_pid_start_actor_or_token_blocks(self):
        mutations=[lambda h:setattr(h,'pid',123),lambda h:setattr(h,'token',1),lambda h:setattr(h,'seq',1),lambda h:setattr(h,'start_low',1),lambda h:setattr(h,'unit',1),lambda h:setattr(h.support,'update',1),lambda h:h.command.__setitem__(0,1)]
        for i,change in enumerate(mutations):
            with self.subTest(i=i):
                base=bytes(self.channel.h);self.mon.close();self.mon=m.MissionRiskMonitor(self.rp,self.sp,self.path/f'bad-{i}.jsonl');self.channel.h=self.layout.Header.from_buffer_copy(base);change(self.channel.h)
                self.assertEqual(self.mon.poll()['state'],'stopped');self.assertFalse(self.channel.writes)
                self.channel.h=self.layout.Header.from_buffer_copy(base)

    def test_terminal_stage_host_loss_deadline_or_other_request_never_writes(self):
        for i,change in enumerate([lambda h:setattr(h,'phase',4),lambda h:setattr(h,'mission_stage',3),lambda h:setattr(h,'retreat_requested',1),lambda h:setattr(h,'stop_requested',1),lambda h:setattr(h,'error',38)]):
            with self.subTest(i=i):
                base=bytes(self.channel.h);self.mon.close();self.mon=m.MissionRiskMonitor(self.rp,self.sp,self.path/f'term-{i}.jsonl');self.channel.h=self.layout.Header.from_buffer_copy(base);change(self.channel.h)
                self.assertEqual(self.mon.poll()['state'],'stopped');self.assertFalse(self.channel.writes);self.channel.h=self.layout.Header.from_buffer_copy(base)
        self.mon.close();self.mon=m.MissionRiskMonitor(self.rp,self.sp,self.path/'hostlost.jsonl');self.channel.live=False
        self.assertEqual(self.mon.poll()['state'],'stopped');self.assertFalse(self.channel.writes)

    def test_late_attach_retreat_without_real_baselines_is_refused(self):
        for e in self.channel.events:
            if e.kind==71:e.kind=70
        result=self.polls();self.assertEqual(result['state'],'waiting_native');self.assertFalse(self.channel.writes)

    def test_mixed_frames_partial_publication_and_bad_current_actor_refused(self):
        pair=self.round(1856);pair[-1].frame+=1;result=self.polls();self.assertEqual(result['state'],'waiting_native');self.assertFalse(self.channel.writes)
        pair[-1].frame-=1;pair[0].owner=1;self.mon.last_seq=0
        self.assertEqual(self.polls()['state'],'stopped');self.assertFalse(self.channel.writes)

    def test_report_identity_source_and_session_changes_stop(self):
        self.round(1840);self.polls();self.report['request']['token']+=1;self.write_report()
        self.assertEqual(self.mon.poll()['state'],'stopped');self.assertFalse(self.channel.writes)

    def test_source_mutation_before_write_cannot_use_cached_verification(self):
        self.round(1840);self.polls();mission=Path(self.report['request']['mission_source_path']);mission.write_text('{}')
        self.round(1856);self.assertEqual(self.mon.poll()['state'],'stopped');self.assertFalse(self.channel.writes)

    def test_200ms_cadence_bound_and_real_poll_metrics(self):
        self.round(1840);self.polls();self.mon.last_poll-=.201
        r=self.mon.poll();self.assertEqual(r['reason'],'poll_cadence_exceeded');self.assertGreater(r['poll_interval_seconds'],.2);self.assertFalse(self.channel.writes)

    def test_fresh_prefix_advance_retries_instead_of_disabling_guard(self):
        self.mon.last_seq=self.channel.h.count
        self.mon.baseline={e.role:e for e in self.channel.events if e.kind==71}
        self.mon.latest={e.role:e for e in self.channel.events if e.kind==3 and e.frame==1856}
        # Attach first, then exercise the final pre-write header changing.
        self.mon._attach(json.loads(self.rp.read_text()));self.channel.header_reads=1
        self.channel.mutate_before_request=lambda h:setattr(h,'count',h.count+1)
        r=self.mon.poll();self.assertEqual(r['state'],'waiting_native',r);self.assertFalse(self.mon.closed);self.assertFalse(self.channel.writes)


if __name__=='__main__':unittest.main()
