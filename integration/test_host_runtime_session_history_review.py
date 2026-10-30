"""Fixed synthetic original records only; no credentials, process or game access."""
from dataclasses import replace
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

from host_runtime.contracts import ContractError,canonical_json
from host_runtime import session_history_review as history
from host_runtime import session_discovery_native as native
import test_host_runtime_desktop_backend as fixture


class HistoryReviewTests(unittest.TestCase):
    setUp=fixture.DesktopBackendTests.setUp
    tearDown=fixture.DesktopBackendTests.tearDown
    new_backend=fixture.DesktopBackendTests.new_backend
    ready=fixture.DesktopBackendTests.ready
    start_args=fixture.DesktopBackendTests.start_args
    start=fixture.DesktopBackendTests.start
    status_file=fixture.DesktopBackendTests.status_file

    def prepare_history(self):
        record=json.loads(self.session.read_text());record['mod_sha256']='b'*64;self.session.write_text(json.dumps(record))
        self.backend.register_session(self.session,self.report,self.persistent)
        check=self.checks.check
        def legacy(*args):
            admitted=check(*args)
            return replace(admitted,capabilities=dict(admitted.capabilities,control_mode='macro_native',runtime_tactical_supported=False))
        self.checks.check=legacy
        result,self.run_id,_=self.start();self.status_file(result,state='stopped');self.spawner.alive=False
        self.backend.run_status(dict(run_id=self.run_id),str(uuid.uuid4()))
        stop=str(uuid.uuid4());self.backend.journal.reserve_command(self.run_id,stop,'stop',{})
        self.backend.journal.mark_dispatching(self.run_id,stop)
        self.backend.journal.record_outcome(self.run_id,stop,'released',dict(reason_code='native_receipt_verified',facts=dict(
            source='native_persistent_production',production_release_verified=True,native_phase=2,native_error=0,restore_mask=31,active_callbacks=0)))
        return result

    def test_explicit_versioned_review_does_not_modify_original_commands_and_avoids_fake_epoch(self):
        self.prepare_history();before=canonical_json(self.backend.journal.commands_for_run(self.run_id))
        with self.assertRaises(ContractError):native.run_records(self.backend)
        result=history.review(self.backend,self.run_id)
        self.assertTrue(result['reviewed']);self.assertFalse(result['game_access'])
        self.assertEqual(before,canonical_json(self.backend.journal.commands_for_run(self.run_id)))
        rows=native.run_records(self.backend);self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0].native_epoch);self.assertIsNone(rows[0].creation_filetime)
        self.assertEqual(rows[0].history_protocol,history.PROTOCOL);self.assertEqual(len(rows[0].history_review_sha256),64)
        self.assertTrue(history.review(self.backend,self.run_id)['idempotent'])

    def test_offline_entry_opens_original_databases_read_only_and_never_queries_process(self):
        self.prepare_history();before=canonical_json(self.backend.journal.commands_for_run(self.run_id))
        with patch('host_runtime.desktop_backend.NativeHostSpawner.identity',side_effect=AssertionError('no process access')):
            offline=history.open_offline_backend(self.store.state_dir)
            try:
                self.assertTrue(history.review(offline,self.run_id)['reviewed'])
                with self.assertRaises(Exception):offline._db.execute('DELETE FROM launches')
                with self.assertRaises(Exception):offline.journal._db.execute('DELETE FROM commands')
            finally:offline.close()
        self.assertEqual(before,canonical_json(self.backend.journal.commands_for_run(self.run_id)))

    def test_unknown_or_missing_independent_release_keeps_history_blocked(self):
        self.prepare_history()
        with patch.object(self.backend,'_release_receipt',return_value=False),self.assertRaises(ContractError):
            history.review(self.backend,self.run_id)
        self.assertFalse(history.proof_path(self.backend,self.run_id).exists())
        unknown=str(uuid.uuid4());self.backend.journal.reserve_command(self.run_id,unknown,'produce',{})
        self.backend.journal.mark_dispatching(self.run_id,unknown)
        self.backend.journal.record_outcome(self.run_id,unknown,'uncertain',dict(reason_code='unknown'))
        with self.assertRaises(ContractError):history.review(self.backend,self.run_id)

    def test_original_session_status_inventory_or_sidecar_change_invalidates_review(self):
        self.prepare_history();history.review(self.backend,self.run_id)
        proof=history.proof_path(self.backend,self.run_id);original=proof.read_bytes()
        value=json.loads(original);value['existing_independent_release_recomputed']=1;proof.write_text(json.dumps(value))
        with self.assertRaises(ContractError):native.run_records(self.backend)
        proof.write_bytes(original)
        status=self.run/'battle-host/host-status.json';status.write_bytes(status.read_bytes()+b' ')
        with self.assertRaises(ContractError):native.run_records(self.backend)

    def test_macro_transport_cannot_be_classified_as_legacy_without_its_epoch(self):
        self.prepare_history();row=self.backend._launch(self.run_id)
        start=self.backend.journal.get_command(self.run_id,self.run_id)
        changed=copy.deepcopy(start);changed['payload']['capabilities']['native_macro']=True
        get=self.backend.journal.get_command
        with patch.object(self.backend.journal,'get_command',side_effect=lambda rid,cid:changed if cid==self.run_id else get(rid,cid)):
            with self.assertRaises(ContractError):history.review(self.backend,self.run_id)

    def test_verified_never_dispatched_start_does_not_require_nonexistent_source_freeze(self):
        value=json.loads(self.session.read_text());value['mod_sha256']='b'*64;self.session.write_text(json.dumps(value))
        self.backend.register_session(self.session,self.report,self.persistent)
        ready=self.ready();request=str(uuid.uuid4())
        with patch('host_runtime.desktop_backend._atomic',side_effect=OSError('before delivery')):
            result=self.backend.run_start(self.profile,self.start_args(ready),request)
        self.assertTrue(result['no_native_execution_started'])
        rows=native.run_records(self.backend)
        self.assertEqual(rows[0].history_protocol,'trusted_never_dispatched_host_v1')
        self.assertIsNone(rows[0].native_epoch);self.assertFalse(rows[0].native_delivery_attempted)
        self.assertEqual(self.spawner.commands,[])

    def test_missing_original_review_artifact_cannot_be_replaced_by_sidecar_assertion(self):
        self.prepare_history();command=str(uuid.uuid4())
        self.backend.journal.reserve_command(self.run_id,command,'review_host_release',{})
        self.backend.journal.mark_dispatching(self.run_id,command)
        self.backend.journal.record_outcome(self.run_id,command,'released',dict(review_sha256='a'*64))
        with self.assertRaises(ContractError):history.review(self.backend,self.run_id)

    def test_omitted_old_optional_mode_is_classified_by_original_release_protocol(self):
        self.prepare_history();get=self.backend.journal.get_command
        def old_record(run_id,command_id):
            value=get(run_id,command_id)
            if command_id==self.run_id:
                value['payload']['capabilities'].pop('control_mode')
                value['payload']['capabilities'].pop('runtime_tactical_supported')
            return value
        with patch.object(self.backend.journal,'get_command',side_effect=old_record):
            history.review(self.backend,self.run_id)
            proof=json.loads(history.proof_path(self.backend,self.run_id).read_text())
        self.assertIsNone(proof['original_declared_control_mode'])
        self.assertEqual(proof['control_family'],'legacy_persistent_production_v1')

