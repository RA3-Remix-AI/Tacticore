"""Diagnostic artifacts are real bounded files, not a blind raw-log bundle."""
import hashlib
import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import test_host_runtime_desktop_backend as fixture
from host_runtime.diagnostics import MAX_EXPORT_EVENTS, project_event


class DiagnosticsTests(unittest.TestCase):
    def test_regional_event_retains_bounded_public_feedback_without_private_or_completion_claims(self):
        row=dict(seq=1,event_type='macro_regional_feedback',created_at='2026-10-28T00:00:00Z',payload=dict(
            source='native_regional_group_observation',action='deployattack',target_region='region_1_3',
            observed_frame=1500,view_frame=1499,moved_native_groups=2,groups_progressing_toward_region=1,
            allocated_native_groups=999999,native_execution_observed=True,policy_released=False,
            arrival_verified=True,mission_success_verified=True,address='PRIVATE',unit_id=23456))
        value=project_event(row)['facts']
        self.assertEqual(value['target_region'],'region_1_3');self.assertEqual(value['moved_native_groups'],2)
        self.assertNotIn('allocated_native_groups',value);self.assertNotIn('PRIVATE',json.dumps(value))
        self.assertNotIn('unit_id',value);self.assertFalse(value['arrival_verified']);self.assertFalse(value['mission_success_verified'])
        row['payload']['target_region']='region_8_3'
        self.assertNotIn('target_region',project_event(row)['facts'])

    def test_local_task_and_preparation_project_only_safe_status_and_effect_facts(self):
        result,run_id,_=self.start()
        task_id=str(uuid.uuid4())
        self.status_file(result,jobs=[dict(task_id=task_id,module='local_maneuver',purpose='move_hold_return',status='failed',
            physical_home=False,control_released=True,mission_effect_verified=False,target_point_id='PRIVATE_POINT',xyz=[1,2,3],raw_hex='PRIVATE_RAW')],
            runtime_model_tasks=dict(preparation=dict(state='waiting_native_readiness',reason_code='native_readiness_required',paid_units_available=1,api_key='PRIVATE_SECRET')))
        status=self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))
        self.assertEqual(status['tasks'][0]['task_id'],task_id);self.assertTrue(status['tasks'][0]['control_released'])
        self.assertFalse(status['tasks'][0]['physical_home']);self.assertFalse(status['tasks'][0]['mission_effect_verified'])
        self.assertEqual(status['local_preparation']['paid_units_available'],1)
        self.assertNotIn('PRIVATE',json.dumps(status))

    setUp = fixture.DesktopBackendTests.setUp
    tearDown = fixture.DesktopBackendTests.tearDown
    new_backend = fixture.DesktopBackendTests.new_backend
    ready = fixture.DesktopBackendTests.ready
    start_args = fixture.DesktopBackendTests.start_args
    start = fixture.DesktopBackendTests.start
    status_file = fixture.DesktopBackendTests.status_file

    def export(self, run_id, request_id=None):
        result = self.backend.diagnostics_export(dict(run_id=run_id), request_id or str(uuid.uuid4()))
        path = self.store.state_dir / "exports" / (result["export_id"] + ".json")
        raw = path.read_bytes()
        self.assertEqual(result["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["bytes"], len(raw))
        return result, json.loads(raw), raw

    def test_status_recent_page_advances_after_more_than_thirty_events(self):
        result, run_id, _ = self.start()
        for index in range(45):self.backend.journal.append_event(run_id, "decision", dict(snapshot_id=index, status="accepted"))
        first = self.backend.run_status(dict(run_id=run_id), str(uuid.uuid4()))
        self.assertEqual(30, len(first["events"]))
        self.assertTrue(first["events_cursor"]["truncated"])
        self.assertEqual(first["events_cursor"]["total_count"] - 30, first["events_cursor"]["overflow"])
        newest = self.backend.journal.append_event(run_id, "host_fault", dict(reason_code="test_failure"))
        second = self.backend.run_status(dict(run_id=run_id), str(uuid.uuid4()))
        self.assertEqual(newest["seq"], second["events"][-1]["seq"])
        self.assertGreater(second["events_cursor"]["last_seq"], first["events_cursor"]["last_seq"])

    def test_export_reconstructs_exact_historical_profile_not_current_save(self):
        result, run_id, _ = self.start(); self.status_file(result)
        previous = self.profile["effective"]["effective_hash"]
        self.store.save_profile(str(uuid.uuid4()), {**self.profile["draft"], "model": "new-model", "custom_traits": "PRIVATE_CUSTOM"}, 1)
        exported, document, raw = self.export(run_id)
        self.assertEqual(previous, document["effective_profile"]["effective_hash"])
        self.assertEqual(1, document["effective_profile"]["revision"])
        self.assertEqual("model-default", document["effective_profile"]["model"])
        self.assertFalse(document["effective_profile"]["free_text_included"])
        self.assertNotIn("PRIVATE_CUSTOM", raw.decode())
        self.assertEqual(run_id, document["run_id"])
        self.assertEqual(document["binding_hash"], content_hash_for_binding(document["binding"]))
        self.assertFalse(document["native_release_verified"])
        self.assertIn("components", document["software"])

    def test_export_only_hashes_raw_logs_provider_text_and_private_addresses(self):
        result, run_id, _ = self.start(); self.status_file(result)
        run_dir = self.store.state_dir / "runs" / run_id
        raw_log = b"PRIVATE_PROVIDER_INPUT Authorization: sk-PRIVATE 0x12345678"
        (run_dir / "host.log").write_bytes(raw_log)
        output = self.run / "battle-host"
        (output / "host-events.jsonl").write_bytes(raw_log)
        self.backend.journal.append_event(run_id, "decision", dict(status="accepted", reason_code="ready", provider_input="PRIVATE_PROVIDER_INPUT", address="0x12345678"))
        self.backend.journal.append_event(run_id, "PRIVATE_UNKNOWN_EVENT", dict(payload="PRIVATE_PROVIDER_INPUT"))
        _, document, raw = self.export(run_id)
        serialized = raw.decode()
        for text in ("PRIVATE_PROVIDER_INPUT", "sk-PRIVATE", "0x12345678", str(self.root), "PRIVATE_UNKNOWN_EVENT"):
            self.assertNotIn(text, serialized)
        indexed = next(item for item in document["raw_file_index"] if item["label"] == "host_log")
        self.assertEqual(hashlib.sha256(raw_log).hexdigest(), indexed["sha256"])
        self.assertFalse(indexed["content_included"])
        self.assertEqual("unprojected_event", document["timeline"][-1]["event_type"])
        self.assertFalse(document["timeline"][-1]["payload_projected"])

    def test_explicit_truncation_counts_snapshot_hash_and_idempotent_export(self):
        _, run_id, _ = self.start()
        for index in range(45):self.backend.journal.append_event(run_id, "decision", dict(snapshot_id=index))
        request_id = str(uuid.uuid4())
        self.assertEqual(10000, MAX_EXPORT_EVENTS)
        with patch("host_runtime.diagnostics.MAX_EXPORT_EVENTS", 20):
            receipt, document, raw = self.export(run_id, request_id)
        self.assertTrue(receipt["truncated"])
        self.assertEqual(20, receipt["exported_event_count"])
        self.assertGreater(receipt["event_count"], 20)
        self.assertEqual(20, len(document["timeline"]))
        from host_runtime.contracts import content_hash
        self.assertEqual(content_hash(document["timeline"]), document["events"]["timeline_sha256"])
        self.backend.journal.append_event(run_id, "host_fault", {})
        repeated, _, repeated_raw = self.export(run_id, request_id)
        self.assertEqual(receipt, repeated)
        self.assertEqual(raw, repeated_raw)

    def test_long_macro_match_exports_more_than_old_recent_window_without_losing_early_events(self):
        _, run_id, _ = self.start()
        for index in range(2200):self.backend.journal.append_event(run_id,'macro_native_feedback',dict(observed_frame=index+1))
        receipt, document, raw = self.export(run_id)
        self.assertFalse(receipt['truncated'])
        self.assertGreater(receipt['exported_event_count'],2200)
        self.assertEqual(receipt['event_count'],len(document['timeline']))
        self.assertEqual(document['events']['exported_count'],document['events']['total_count'])
        self.assertLess(len(raw),8*1024*1024)

    def test_missing_or_tampered_historical_profile_is_unavailable_not_substituted(self):
        _, run_id, _ = self.start()
        path = self.store.state_dir / "runs" / run_id / "commander-draft.json"
        draft = json.loads(path.read_text(encoding="utf-8")); draft["model"] = "tampered-model"
        path.write_text(json.dumps(draft), encoding="utf-8")
        _, document, _ = self.export(run_id)
        self.assertIsNone(document["effective_profile"])
        self.assertFalse(document["effective_profile_available"])

    def test_tasks_counters_and_consumption_are_real_whitelisted_projections(self):
        result, run_id, _ = self.start()
        self.status_file(result, task_counters=dict(dispatches=2, started=1, completed=0, failed=0, blocked=1, provider_input="PRIVATE"),
            jobs=[dict(task_id=str(uuid.uuid4()), module="build", purpose="infantry", status="planned", reason_code="awaiting_host_dispatch",
                       budget=dict(unit="fraction_of_observed_credits", fraction=.1), provider_payload="PRIVATE", native_address="0x12345678")],
            metrics=dict(requests=2, accepted=1, provider_input="PRIVATE"))
        status = self.backend.run_status(dict(run_id=run_id), str(uuid.uuid4()))
        self.assertEqual(dict(dispatches=2, started=1, completed=0, failed=0, blocked=1), status["task_counters"])
        self.assertEqual("planned", status["tasks"][0]["stage"])
        self.assertFalse(status["consumption"]["model_response_received"])
        self.assertIn("profile_consumption", status)
        self.assertNotIn("PRIVATE", json.dumps(status))
        self.assertNotIn("0x12345678", json.dumps(status))

    def test_mismatched_profile_event_does_not_claim_current_model_consumption(self):
        result, run_id, _ = self.start()
        event = self.backend.journal.append_event(run_id, "commander_model_response_returned", dict(profile_id=fixture.PROFILE,
            profile_revision=0, effective_hash="0" * 64, model_response_received=True))
        status = self.backend.run_status(dict(run_id=run_id), str(uuid.uuid4()))
        projected = next(item for item in status["events"] if item["seq"] == event["seq"])
        self.assertFalse(projected["profile_binding_matches"])
        self.assertEqual({}, projected["facts"])

    def test_export_keeps_plan_proposal_command_links_without_private_nested_fields(self):
        _,run_id,_=self.start()
        plan_id,task_id=str(uuid.uuid4()),str(uuid.uuid4())
        context=dict(session_id=fixture.SESSION,commander_id=fixture.PROFILE,player_id=3)
        plan=dict(**context,plan_id=plan_id,snapshot_id=9,based_on_game_time_seconds=10.,expires_at_game_seconds=20.,
            stance='defend',production_focus='infantry',economy_policy='stabilize',tech_policy='hold_current_tier',
            origin='model',reason_code='balanced_default',budget=dict(army=.4,economy=.3,tech=.1,reserve=.2),
            tactical_tasks=[],provider_input='PRIVATE_PLAN',native_address='0x12345678')
        self.backend.journal.append_event(run_id,'plan_applied',dict(**context,plan_id=plan_id,snapshot_id=9,plan=plan))
        proposal=dict(task_id=task_id,plan_id=plan_id,generation=1,module='build',purpose='reinforce',focus='infantry',
            spend_fraction=.1,force_fraction=0.,status='planned',reason_code='awaiting_host_dispatch',provider_input='PRIVATE_TASK')
        self.backend.journal.append_event(run_id,'task_proposed',dict(**context,task_id=task_id,plan_id=plan_id,generation=1,
            snapshot_id=9,proposal=proposal,execution_authorized=False))
        _,document,raw=self.export(run_id)
        applied=next(x for x in document['timeline'] if x['event_type']=='plan_applied')
        proposed=next(x for x in document['timeline'] if x['event_type']=='task_proposed')
        self.assertTrue(applied['plan_binding_matches'])
        self.assertTrue(proposed['proposal_binding_matches'])
        self.assertEqual(plan['budget'],applied['facts']['plan']['budget'])
        self.assertEqual(plan_id,proposed['facts']['proposal']['plan_id'])
        self.assertEqual('infantry',proposed['facts']['proposal']['focus'])
        self.assertFalse(proposed['facts']['execution_authorized'])
        for private in ('PRIVATE_PLAN','PRIVATE_TASK','0x12345678'):
            self.assertNotIn(private,raw.decode())

    def test_mismatched_nested_plan_and_proposal_are_not_attributed_to_current_event(self):
        _,run_id,_=self.start()
        plan_id,task_id=str(uuid.uuid4()),str(uuid.uuid4())
        context=dict(session_id=fixture.SESSION,commander_id=fixture.PROFILE,player_id=3)
        self.backend.journal.append_event(run_id,'plan_applied',dict(**context,plan_id=plan_id,snapshot_id=9,
            plan=dict(plan_id=plan_id,session_id=str(uuid.uuid4()),commander_id=fixture.PROFILE,player_id=3,snapshot_id=9)))
        self.backend.journal.append_event(run_id,'task_proposed',dict(**context,task_id=task_id,plan_id=plan_id,generation=1,
            proposal=dict(task_id=task_id,plan_id=str(uuid.uuid4()),generation=1,module='build')))
        _,document,_=self.export(run_id)
        applied=next(x for x in document['timeline'] if x['event_type']=='plan_applied')
        proposed=next(x for x in document['timeline'] if x['event_type']=='task_proposed')
        self.assertFalse(applied['plan_binding_matches'])
        self.assertNotIn('plan',applied['facts'])
        self.assertFalse(proposed['proposal_binding_matches'])
        self.assertNotIn('proposal',proposed['facts'])
        event=dict(seq=1,event_type='task_proposed',created_at='offline',payload=dict(task_id=task_id,proposal=dict(task_id=task_id)))
        projected=project_event(event)
        self.assertFalse(projected['proposal_binding_matches'])
        self.assertNotIn('proposal',projected['facts'])


def content_hash_for_binding(value):
    from host_runtime.contracts import SessionBinding
    return SessionBinding.from_dict(value).binding_hash


if __name__ == "__main__":unittest.main()
