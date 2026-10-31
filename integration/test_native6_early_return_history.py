"""Missing-status routing only; full proof verification has separate tests."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from host_runtime import native6_early_return_history as h,native6_history,native6_orphan_return
from host_runtime.native6_release import KIND as NORMAL
from host_runtime.native6_no_attachment import KIND as NO_ATTACH
from host_runtime import beta_history
from host_runtime.contracts import ContractError
from integration import test_native6_return_routing as route_fixture


class MissingStatus(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.output=Path(temp.name)
        self.context=self.output/'native6-context.json';self.context.write_text('{}')
        self.row=dict(run_id=str(uuid.uuid4()),output_path=str(self.output))
        self.binding=SimpleNamespace(session_id=str(uuid.uuid4()))
        self.start=dict(operation='host_start',status='completed',payload=dict(capabilities=dict(native_macro=True,native_transport_protocol=6)),
            receipt=dict(reason_code='host_process_lost_control_returned',host_pid=123,host_start_time='bound-original-start'))
        self.stop=dict(status='released',receipt=dict(native_release_contract=native6_orphan_return.KIND))
        self.backend=SimpleNamespace(journal=SimpleNamespace(get_command=lambda *_:self.stop))

    def project(self):return h.missing_status_projection(self.backend,self.row,self.binding,self.start)

    def test_verified_committed_orphan_projects_fault_without_creating_status_or_capture(self):
        with patch.object(native6_history,'verified_return',return_value=True) as verify,\
                patch.object(native6_orphan_return,'capture',side_effect=AssertionError('no capture')):
            result=self.project();verify.assert_called_once_with(self.backend,self.row,self.binding,self.start['receipt'])
        self.assertEqual(result,dict(run_id=self.row['run_id'],session_id=self.binding.session_id,state='fault',native_release_verified=True))
        self.assertFalse((self.output/'host-status.json').exists());self.assertEqual(self.context.read_text(),'{}')

    def test_bad_full_proof_cannot_become_a_projection(self):
        with patch.object(native6_history,'verified_return',return_value=False) as verify:
            self.assertIsNone(self.project());verify.assert_called_once()

    def test_normal_no_attachment_and_unknown_contracts_cannot_borrow_missing_status_path(self):
        for contract in (NORMAL,NO_ATTACH,'unknown'):
            self.stop['receipt']['native_release_contract']=contract
            with patch.object(native6_history,'verified_return',side_effect=AssertionError('wrong contract')):
                self.assertIsNone(self.project())

    def test_unfinished_or_rejected_stop_never_projects_return(self):
        for status in ('reserved','dispatching','uncertain','rejected','cancelled'):
            self.stop['status']=status
            with patch.object(native6_history,'verified_return',side_effect=AssertionError('not committed')):
                self.assertIsNone(self.project())

    def test_missing_context_does_not_call_verifier(self):
        self.context.unlink()
        with patch.object(native6_history,'verified_return',side_effect=AssertionError('no original context')):
            self.assertIsNone(self.project())

    def test_existing_corrupt_status_is_left_for_original_strict_reader(self):
        path=self.output/'host-status.json';path.write_bytes(b'not-json')
        with patch.object(native6_history,'verified_return',side_effect=AssertionError('must read original status')):
            self.assertIsNone(self.project())
        self.assertEqual(path.read_bytes(),b'not-json')

    def test_existing_status_directory_is_not_treated_as_absence(self):
        (self.output/'host-status.json').mkdir()
        with patch.object(native6_history,'verified_return',side_effect=AssertionError('not absent')):
            self.assertIsNone(self.project())

    def test_access_error_is_not_absence_or_permission_to_review_another_proof(self):
        with patch.object(Path,'lstat',side_effect=PermissionError('denied')),\
                patch.object(native6_history,'verified_return',side_effect=AssertionError('not absent')):
            with self.assertRaises(PermissionError):self.project()

    def test_wrong_epoch_type_or_macro_scope_is_refused(self):
        original=deepcopy(self.start)
        for protocol in (5,'6',True,None):
            self.start=deepcopy(original);self.start['payload']['capabilities']['native_transport_protocol']=protocol
            with patch.object(native6_history,'verified_return',side_effect=AssertionError('wrong epoch')):
                self.assertIsNone(self.project())
        self.start=deepcopy(original);self.start['payload']['capabilities']['native_macro']=False
        self.assertIsNone(self.project())

    def test_wrong_host_start_status_or_reason_is_refused(self):
        original=deepcopy(self.start)
        for status in ('started','uncertain','failed'):
            self.start=deepcopy(original);self.start['status']=status;self.assertIsNone(self.project())
        self.start=deepcopy(original);self.start['receipt']['reason_code']='host_stopped'
        self.assertIsNone(self.project())


class ReaderIntegration(unittest.TestCase):
    setUp=route_fixture.OfflineProjection.setUp
    write=staticmethod(route_fixture.OfflineProjection.write)
    fixture=route_fixture.OfflineProjection.fixture

    def backend(self,contract=native6_orphan_return.KIND):
        value=self.fixture(contract)
        start=value.journal.get_command(self.row['run_id'],self.row['request_id'])
        start['payload']['capabilities']['native_transport_protocol']=6
        return value

    def test_absent_status_reaches_complete_orphan_review_after_host_ended_check(self):
        backend=self.backend();(self.output/'host-status.json').unlink()
        with patch.object(beta_history,'host_ended') as ended,patch.object(native6_history,'verified_return',return_value=True) as verify:
            result=beta_history.closed_status(backend,self.row)
        ended.assert_called_once();verify.assert_called_once()
        self.assertEqual(result['state'],'fault');self.assertTrue(result['native_release_verified'])
        self.assertFalse((self.output/'host-status.json').exists())

    def test_invalid_orphan_proof_and_missing_status_stay_unverifiable(self):
        backend=self.backend();(self.output/'host-status.json').unlink()
        with patch.object(beta_history,'host_ended'),patch.object(native6_history,'verified_return',return_value=False):
            with self.assertRaises(ContractError):beta_history.closed_status(backend,self.row)

    def test_normal_or_no_attachment_proof_cannot_substitute_for_missing_status(self):
        for contract in (NORMAL,NO_ATTACH):
            backend=self.backend(contract);(self.output/'host-status.json').unlink()
            with patch.object(beta_history,'host_ended'),patch.object(native6_history,'verified_return',side_effect=AssertionError('wrong contract')):
                with self.assertRaises(ContractError):beta_history.closed_status(backend,self.row)

    def test_live_or_unknown_host_prevents_all_projection(self):
        backend=self.backend();(self.output/'host-status.json').unlink()
        with patch.object(beta_history,'host_ended',side_effect=ContractError('beta_existing_run_unreleased')),\
                patch.object(native6_history,'verified_return',side_effect=AssertionError('host not ended')):
            with self.assertRaises(ContractError):beta_history.closed_status(backend,self.row)

    def test_present_wrong_binding_still_uses_original_identity_checks(self):
        backend=self.backend();path=self.output/'host-status.json'
        import json
        status=json.loads(path.read_bytes());status['session_id']=str(uuid.uuid4());self.write(path,status)
        with patch.object(beta_history,'host_ended'),patch.object(native6_history,'verified_return',side_effect=AssertionError('bad original status')):
            with self.assertRaises(ContractError):beta_history.closed_status(backend,self.row)


if __name__=='__main__':unittest.main()
