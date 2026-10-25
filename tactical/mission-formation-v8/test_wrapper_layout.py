"""Actual ctypes and publication boundaries only; never attaches to a game."""
import ctypes as c
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import uuid

H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf8_wrapper_layout_test',H/'lease.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)


class Layout(unittest.TestCase):
    def report(self):return dict(request=dict(task_id=str(uuid.uuid4())),events=[])

    def test_actual_host_abi_and_old_prefix(self):
        actual=json.loads(subprocess.check_output([str(H/'bin/tactical_host.exe'),'--layout'],text=True))
        self.assertEqual(actual,w.layout_module.layout())
        self.assertEqual((c.sizeof(w.Breadcrumb),c.sizeof(w.Event),w.Tactical.events.offset,c.sizeof(w.Tactical)),(104,1616,27900,13266172))
        self.assertEqual((w.Tactical.phase.offset,w.Tactical.error.offset,w.Tactical.issued_frame.offset),(260,276,288))
        self.assertEqual(c.sizeof(w.Header),w.Tactical.events.offset)
        self.assertEqual(hashlib.sha256((H/'shared.h').read_bytes()).hexdigest(),w.layout_module.SHARED_SHA256)

    def test_nested_ground_record_retains_all_raw_words_and_identity(self):
        e=w.Event();e.seq=1;e.kind=80;e.breadcrumb.object_id=7;e.breadcrumb.type_hash=0x19ab11af;e.breadcrumb.status_words[:]=range(7);e.breadcrumb.height=.125;e.breadcrumb.published_seq=1
        record=w.event_record(e)
        self.assertEqual(record['breadcrumb']['status_words'],list(range(7)))
        self.assertEqual(record['breadcrumb']['object_id'],7)
        self.assertEqual(record['breadcrumb']['height'],.125)
        json.dumps(record,allow_nan=False)

    def test_nonfinite_diagnostics_are_explicit_unknown_not_zero(self):
        e=w.Event();e.requested[0]=float('nan');e.breadcrumb.height=float('inf')
        record=w.event_record(e)
        self.assertIsNone(record['requested'][0]);self.assertIsNone(record['breadcrumb']['height'])
        self.assertIn('event.requested[0]',record['invalid_float_fields'])
        self.assertIn('event.breadcrumb.height',record['invalid_float_fields'])
        json.dumps(record,allow_nan=False)

    def test_only_new_immutable_published_prefix_is_decoded(self):
        shared=w.Tactical();shared.count=2;shared.events[0].seq=1;shared.events[0].kind=3
        report=self.report()
        with patch.object(w,'progress',return_value=None),patch.object(w,'event_record',wraps=w.event_record) as decode:
            w.capture(report,shared);self.assertEqual(len(report['events']),1);self.assertEqual(decode.call_count,1)
            first=report['events'][0]
            shared.events[1].seq=2;shared.events[1].kind=80
            w.capture(report,shared);self.assertIs(report['events'][0],first);self.assertEqual(decode.call_count,2)
            w.capture(report,shared);self.assertEqual(decode.call_count,2)
        self.assertEqual(report['capture_metadata']['published_prefix_count'],2)

    def test_unpublished_gap_never_skipped_or_promoted_by_terminal_header(self):
        shared=w.Tactical();shared.phase=3;shared.count=3;shared.events[0].seq=1;shared.events[2].seq=3
        report=self.report()
        with patch.object(w,'progress',return_value=None):self.assertTrue(w.capture(report,shared))
        self.assertEqual(len(report['events']),1)
        self.assertEqual(report['capture_metadata']['header_count'],3)

    def test_counter_regression_refuses_reusing_a_previous_channel_prefix(self):
        shared=w.Tactical();shared.count=0
        with self.assertRaisesRegex(ValueError,'published_event_prefix_regressed'):w.capture(dict(events=[dict(seq=1)]),shared)

    def test_header_crumbs_are_bounded_by_actual_per_role_count(self):
        shared=w.Tactical();shared.crumb_count[:]=[1,0];shared.crumbs[0][0].object_id=9
        report=self.report()
        with patch.object(w,'progress',return_value=None):w.capture(report,shared)
        self.assertEqual([len(x) for x in report['native']['crumbs']],[1,0])
        self.assertEqual(report['native']['crumbs'][0][0]['object_id'],9)

    def test_no_python_planner_or_route_handshake_exists(self):
        text=(H/'lease.py').read_text(encoding='utf-8')
        for forbidden in ('make_and_publish','formation_history_dir','route_points','planning_host_traffic'):
            self.assertNotIn(forbidden,text)
        self.assertIn('s.route_count=s.route_ready=s.route_generation=0',text)
        self.assertIn('s.memory_ttl_frames=900',text)
        self.assertIn('shared.heartbeat_tick=',text)
        self.assertIn('now-written>=1',text)


if __name__=='__main__':unittest.main()
