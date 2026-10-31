"""Committed proof protocols outrank stray files; no evidence is collected."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_native6_history as history_fixture
from host_runtime import native6_history as history,native6_lifecycle as original,native6_normal_return_v1 as normal
from host_runtime import native6_no_attachment as no_attach,native6_orphan_return as orphan,native6_release as release
from host_runtime import native6_recovery_route as recovery,beta_history
from host_runtime.journal import JournalError


class Routing(unittest.TestCase):
    setUp=history_fixture.Native6History.setUp
    write=staticmethod(history_fixture.Native6History.write)

    def complete_no_attachment(self):
        objects=dict(source='win32_read_only_macro_channel_and_semaphore_v1',
            mapping_name='Local\\RA3StrategicCommanderV6_123',semaphore_name='Local\\RA3MacroPolicyLease_123',
            mapping_status='absent',semaphore_status='absent',mapping_open_error=2,semaphore_open_error=2,
            native_writes=0,acquire_or_wait_calls=0)
        self.proof=dict(kind=no_attach.KIND,schema_version=1,run_id=self.row['run_id'],binding=self.binding.public(),
            actual_OS_before=dict(pid=123,process_creation_filetime=self.session['process_creation_filetime']),
            actual_OS_after=dict(pid=123,process_creation_filetime=self.session['process_creation_filetime']),
            policy_modules_before=[],policy_modules_after=[],objects_before=objects,objects_after=objects,
            started_monotonic_ns=1,ended_monotonic_ns=1000,image_before=str(Path(self.session['game']).resolve()),
            image_after=str(Path(self.session['game']).resolve()),image_sha256=self.binding.game_sha256,
            capture_code_sha256=history.sha(Path(no_attach.__file__)),no_control_acquired=True,
            manager_restoration_claimed=False,mission_effect_verified=False)
        self.write(self.output/'native-no-attachment.json',self.proof)
        (self.output/'host-events.jsonl').write_text('{"kind":"host_stopped"}\n',encoding='utf-8')
        self.host_receipt=dict(host_pid=777,host_start_time='original-host-start')
        self.publication=dict(kind='macro_policy_native_release',run_id=self.row['run_id'],binding=self.binding.public(),
            native_release_verified=True,native_release_contract=no_attach.KIND,**self.host_receipt)
        self.stop=dict(status='released',receipt=dict(binding_hash=self.binding.binding_hash,native_release_verified=True,
            native_release_contract=no_attach.KIND,**self.host_receipt))
        self.backend=SimpleNamespace(journal=SimpleNamespace(get_command=lambda *_:self.stop,unresolved=lambda *_:[],
            commands_for_run=lambda *_:[dict(operation='host_start',status='completed'),dict(operation='macro_policy_stop',status='released')]))
        self.reseal()

    def reseal(self):
        self.write(self.output/'native-no-attachment.json',self.proof)
        pin=history.sha(self.output/'native-no-attachment.json')
        self.publication['no_attachment_sha256']=pin;self.stop['receipt']['no_attachment_sha256']=pin
        self.write(self.output/'macro-release.json',self.publication)
        self.stop['receipt']['release_sha256']=history.sha(self.output/'macro-release.json')

    def test_complete_committed_proof_survives_unselected_orphan_artifacts(self):
        self.complete_no_attachment()
        (self.output/'native6-orphan-return.json').write_bytes(b'unselected original artifact, never parsed')
        (self.output/'native6-orphan-journal.bin').write_bytes(b'unselected original binary')
        before={p:p.read_bytes() for p in self.output.iterdir() if p.is_file()}
        with patch.object(orphan,'verified_capture',side_effect=AssertionError('wrong protocol')):
            self.assertTrue(history.verified_return(self.backend,self.row,self.binding,self.host_receipt))
        self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_changed_no_attachment_proof_does_not_fallback_to_other_protocol(self):
        self.complete_no_attachment();self.proof['actual_OS_after']['pid']=124;self.reseal()
        with patch.object(orphan,'verified_capture',return_value=True) as other:
            self.assertFalse(history.verified_return(self.backend,self.row,self.binding,self.host_receipt))
            other.assert_not_called()

    def test_normal_release_missing_full_proof_does_not_fallback_to_orphan(self):
        self.complete_no_attachment()
        self.publication['native_release_contract']=release.KIND;self.stop['receipt']['native_release_contract']=release.KIND;self.reseal()
        (self.output/'native6-orphan-return.json').write_bytes(b'extra artifact')
        with patch.object(orphan,'verified_capture',return_value=True) as other:
            self.assertFalse(history.verified_return(self.backend,self.row,self.binding,self.host_receipt));other.assert_not_called()

    def test_orphan_contract_cannot_borrow_valid_normal_proof(self):
        self.complete_no_attachment();self.stop['receipt']['native_release_contract']=orphan.KIND
        with patch.object(normal,'verified_return',return_value=True) as other:
            self.assertFalse(history.verified_return(self.backend,self.row,self.binding,self.host_receipt));other.assert_not_called()

    def test_unreleased_and_unknown_contracts_have_no_fallback(self):
        self.complete_no_attachment()
        for status,contract in [('uncertain',no_attach.KIND),('released','unrecognized')]:
            self.stop['status']=status;self.stop['receipt']['native_release_contract']=contract
            self.assertFalse(history.verified_return(self.backend,self.row,self.binding,self.host_receipt))

    def test_extracted_normal_path_retains_every_original_verifier_statement(self):
        def function(module):
            return next(n for n in ast.parse(Path(module.__file__).read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='verified_return')
        old=function(original).body[0];new=function(normal).body[0]
        self.assertIsInstance(old,ast.Try);self.assertIsInstance(new,ast.Try)
        self.assertEqual([ast.dump(n) for n in old.body[1:]],[ast.dump(n) for n in new.body])
        self.assertEqual([ast.dump(n) for n in old.handlers],[ast.dump(n) for n in new.handlers])


class RecoveryEntry(unittest.TestCase):
    def test_committed_normal_no_attachment_unknown_never_collect_or_rewrite(self):
        for contract in (release.KIND,no_attach.KIND,'unknown'):
            backend=SimpleNamespace(journal=SimpleNamespace(get_command=lambda *_:dict(status='released',receipt=dict(native_release_contract=contract))))
            with patch.object(recovery,'collect_orphan',side_effect=AssertionError('must not collect')):
                self.assertFalse(recovery.recover_after_stop(backend,dict(run_id='run'),None,{},None))

    def test_unfinished_stop_still_uses_original_recovery(self):
        for status in ('reserved','dispatching','uncertain'):
            backend=SimpleNamespace(journal=SimpleNamespace(get_command=lambda *_:dict(status=status,receipt=dict(native_release_contract=orphan.KIND))))
            with patch.object(recovery,'collect_orphan',return_value=True) as collect:
                self.assertTrue(recovery.recover_after_stop(backend,dict(run_id='run'),None,{},None));collect.assert_called_once()

    def test_committed_orphan_only_replays_proof_without_new_capture(self):
        backend=SimpleNamespace(journal=SimpleNamespace(get_command=lambda *_:dict(status='released',receipt=dict(native_release_contract=orphan.KIND))))
        for valid in (True,False):
            with patch.object(recovery,'collect_orphan',side_effect=AssertionError('must not collect')),patch.object(recovery,'review_return',return_value=valid) as verify:
                self.assertEqual(recovery.recover_after_stop(backend,dict(run_id='run'),None,{},None),valid);verify.assert_called_once()

    def test_missing_stop_can_enter_recovery_but_terminal_cancelled_cannot(self):
        def missing(*_):raise JournalError('unknown_command')
        backend=SimpleNamespace(journal=SimpleNamespace(get_command=missing))
        with patch.object(recovery,'collect_orphan',return_value=True) as collect:
            self.assertTrue(recovery.recover_after_stop(backend,dict(run_id='run'),None,{},None));collect.assert_called_once()
        backend.journal.get_command=lambda *_:dict(status='cancelled',receipt={})
        with patch.object(recovery,'collect_orphan',side_effect=AssertionError('must not collect')):
            self.assertFalse(recovery.recover_after_stop(backend,dict(run_id='run'),None,{},None))


class OfflineProjection(unittest.TestCase):
    setUp=history_fixture.Native6History.setUp
    write=staticmethod(history_fixture.Native6History.write)

    def fixture(self,contract,state='running'):
        self.row.update(binding_json=json.dumps(self.binding.public()),request_id='host-start')
        receipt=dict(host_pid=777,host_start_time='old-host',reason_code='host_process_lost_control_returned')
        start=dict(operation='host_start',status='completed',receipt=receipt,payload=dict(capabilities=dict(native_macro=True)))
        stop=dict(status='released',receipt=dict(native_release_contract=contract))
        self.write(self.output/'host-status.json',dict(state=state,runtime_macro=dict(run_id=self.row['run_id'],
            binding_hash=self.binding.binding_hash),session_id=self.binding.session_id,pid=self.binding.game_process_id,
            process_start=self.binding.game_process_start,host_pid=777,host_start_time='old-host'))
        backend=SimpleNamespace(journal=SimpleNamespace(get_command=lambda run,request:stop if request=='macro-stop' else start))
        return backend

    def test_verified_native6_orphan_projects_dead_host_as_fault_without_file_heuristics(self):
        backend=self.fixture(orphan.KIND)
        for verified in (True,False):
            with patch.object(beta_history,'host_ended'),patch.object(history,'verified_return',return_value=verified):
                result=beta_history.closed_status(backend,self.row)
            self.assertEqual(result['state'],'fault' if verified else 'running')
            self.assertEqual(result['native_release_verified'],verified)

    def test_normal_receipt_and_stopped_state_are_not_reclassified_by_extra_files(self):
        backend=self.fixture(release.KIND,state='stopped')
        for name in ('native-orphan-return.json','native6-orphan-return.json'):(self.output/name).write_bytes(b'unselected')
        with patch.object(beta_history,'host_ended'),patch.object(history,'verified_return',return_value=True):
            result=beta_history.closed_status(backend,self.row)
        self.assertEqual(result['state'],'stopped');self.assertTrue(result['native_release_verified'])


if __name__=='__main__':unittest.main()
