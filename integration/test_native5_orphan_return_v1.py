"""CPU proof mutations and handle failures; no Native/game/model calls."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import uuid

from host_runtime.native5_helper_identity_v1 import ended_incarnation
from host_runtime.native5_orphan_return_v1 import KIND,readonly_memory,collect_current,verified_capture,recover_after_stop
from host_runtime.journal import CommandJournal
from host_runtime.strategic_stop_gate_v1 import StrategicStopGateV1
from host_runtime.strategic_unified_release_v5 import verified_proof

ROOT=Path(__file__).resolve().parents[1]


class RecoveryProof(unittest.TestCase):
    def setUp(self):
        source=ROOT/'reports/strategic-unified-natural-terminal-52600-20261029-v1/independent-release.json'
        if not source.is_file():
            raise unittest.SkipTest('requires the local historical Native return proof and journal')
        proof=json.loads(source.read_bytes())
        b=proof['native']['binding'];self.sid=str(uuid.UUID(bytes=bytes(b['session'])))
        journal=ROOT/'reports/strategic-unified-native-journal'/(uuid.UUID(self.sid).hex+'.bin')
        if not journal.is_file():
            raise unittest.SkipTest('requires the local historical Native return journal')
        self.raw=journal.read_bytes()
        self.args=dict(pid=b['pid'],ticks=b['start_low']|(b['start_high']<<32),session_id=self.sid,
            package=bytes(b['package']).hex(),flags=[r['name'] for r in proof['flags']['flags']],closure=bytes(b['sources']).hex())
        self.session=dict(process_creation_filetime=self.args['ticks'])
        self.manifest=dict(flags=self.args['flags'],source_closure_sha256=self.args['closure'])
        self.binding=SimpleNamespace(game_process_id=b['pid'],session_id=self.sid,mod_sha256=self.args['package'],public=lambda:dict(session_id=self.sid))
        self.identity=dict(native_binding=b)
        ended=dict(ended=True,reason='pid_absent',exit_code=None)
        self.value=dict(kind=KIND,run_id='fixture',binding=self.binding.public(),helper_identity=self.identity,
            helper_exit_code=None,parent_ended=ended,helper_ended_before=ended,helper_ended_after=ended,
            restoration=proof,native_journal_sha256=__import__('hashlib').sha256(self.raw).hexdigest(),
            native_commands_issued=0,mapping_access='FILE_MAP_READ')
    def verify(self,value=None,raw=None):
        return verified_capture(value or self.value,self.raw if raw is None else raw,self.session,self.manifest,self.identity,self.binding,self.value['run_id'])
    def test_unknown_exit_code_uses_separate_contract_not_legacy_success(self):
        self.assertTrue(verified_proof(self.value['restoration'],**self.args))
        self.value['restoration'].pop('host_process_ended')
        self.value['restoration']['host_returncode']=None
        self.assertTrue(self.verify())
        self.assertFalse(verified_proof(self.value['restoration'],**self.args))
    def test_each_lifecycle_or_ownership_mutation_fails(self):
        changes=[lambda v:v.update(helper_exit_code=0),lambda v:v.update(mapping_access='FILE_MAP_ALL_ACCESS'),
            lambda v:v.update(native_commands_issued=1),lambda v:v.update(run_id='other'),
            lambda v:v.update(helper_ended_before=dict(ended=False,reason='still_alive',exit_code=None)),
            lambda v:v['restoration']['native'].update(hook_held=1),
            lambda v:v['restoration']['native'].update(lease_held=1),
            lambda v:v['restoration']['components'][2].update(enabled=0),
            lambda v:v['restoration']['actual_OS_after'].update(pid=1),
            lambda v:v['restoration'].update(frame_after=v['restoration']['frame']+3)]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                v=copy.deepcopy(self.value);change(v);self.assertFalse(self.verify(v))
        self.assertFalse(self.verify(raw=self.raw[:-1]))
    def test_partial_memory_constructor_closes_once_and_keeps_original_error(self):
        opened=[];closed=[]
        class Memory:
            def __init__(self,*args):self.handle=17;opened.append(self);raise RuntimeError('original_read_failure')
            def close(self):closed.append(self.handle)
        with self.assertRaisesRegex(RuntimeError,'original_read_failure'):readonly_memory(Memory,1,{})
        self.assertEqual(closed,[17]);self.assertIsNone(opened[0].handle)
    def test_repeated_failed_collection_restores_borrowed_module_memory(self):
        closed=[]
        class Memory:
            def __init__(self,*args):self.handle=17;raise RuntimeError('changed_root')
            def close(self):closed.append(self.handle)
        client=SimpleNamespace(Memory=Memory)
        client.Probe=SimpleNamespace(independent_release=lambda _:client.Memory(123,{}))
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError,'changed_root'):collect_current(client,object())
            self.assertIs(client.Memory,Memory)
        self.assertEqual(closed,[17,17])


class Incarnation(unittest.TestCase):
    def test_live_and_pid_reuse_and_access_failure_are_distinct(self):
        expected=dict(pid=123,process_creation_filetime=456)
        with patch('host_runtime.native5_helper_identity_v1.process_identity',return_value=dict(expected,alive=True)):
            self.assertFalse(ended_incarnation(expected)['ended'])
        with patch('host_runtime.native5_helper_identity_v1.process_identity',return_value=dict(pid=123,process_creation_filetime=789,alive=True)):
            result=ended_incarnation(expected);self.assertTrue(result['ended']);self.assertIsNone(result['exit_code'])
        error=OSError('access denied');error.winerror=5
        with patch('host_runtime.native5_helper_identity_v1.process_identity',side_effect=error):
            with self.assertRaises(OSError):ended_incarnation(expected)
        error=OSError('no process');error.winerror=87
        with patch('host_runtime.native5_helper_identity_v1.process_identity',side_effect=error):
            self.assertEqual(ended_incarnation(expected),dict(ended=True,reason='pid_absent',exit_code=None))
    def test_invalid_identity_never_turns_an_os_failure_into_ended(self):
        for field in ('pid','process_creation_filetime'):
            for bad in (0,-1,True,'123',None):
                value=dict(pid=123,process_creation_filetime=456);value[field]=bad
                with self.subTest(field=field,bad=bad):
                    with patch('host_runtime.native5_helper_identity_v1.process_identity') as query:
                        with self.assertRaises(ValueError):ended_incarnation(value)
                        query.assert_not_called()


class LedgerRecovery(RecoveryProof):
    """Real ledger and real mutex, injected read-only collector/OS evidence."""
    def setUp(self):
        super().setUp();self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name);self.run=str(uuid.uuid4());self.value['run_id']=self.run
        self.value['capture_source_sha256']='c'*64;self.binding.binding_hash='a'*64
        self.row=dict(run_id=self.run,output_path=str(self.output),request_id='start')
        self.receipt=dict(host_pid=123,host_start_time='fixture-start')
        self.journal=CommandJournal(self.output/'journal.sqlite3');self.addCleanup(self.journal.close)
        self.journal.register_run(self.run,self.binding.public())
        self.journal.reserve_command(self.run,'start','host_start',{});self.journal.mark_dispatching(self.run,'start')
        self.journal.record_outcome(self.run,'start','started',self.receipt)
        self.backend=SimpleNamespace(journal=self.journal,spawner=SimpleNamespace(identity=lambda _:None))
        self.gate=StrategicStopGateV1(self.run,self.binding,self.output)
        self.gate.publish_stop(self.atomic)
    @staticmethod
    def atomic(path,value):Path(path).write_text(json.dumps(value),encoding='utf-8')
    def recover(self,*,capture_error=None):
        module='host_runtime.native5_orphan_return_v1.'
        with patch(module+'inputs',return_value=(self.session,self.manifest,self.output,self.identity)),patch(module+'archived_sha',return_value='c'*64),patch(module+'capture',return_value=(self.value,self.raw),side_effect=capture_error) as collector:
            result=recover_after_stop(self.backend,self.row,self.binding,self.receipt,self.atomic)
            return result,collector.call_count
    def test_unknown_delivery_preserved_and_second_review_does_not_capture_again(self):
        ident=str(uuid.uuid4())
        self.journal.reserve_command(self.run,ident,'macro_policy',dict(actions=['withdraw'],plan_id=str(uuid.uuid4()),native_command_id=ident,duration_frames=60,not_after_frame=100,unit_operation_policy='native_ai'))
        self.journal.mark_dispatching(self.run,ident)
        result,calls=self.recover();self.assertTrue(result);self.assertEqual(calls,1)
        self.assertEqual(self.journal.get_command(self.run,ident)['status'],'uncertain')
        self.assertEqual(self.journal.get_command(self.run,'macro-stop')['status'],'released')
        self.assertEqual(self.recover(),(True,0))
    def test_existing_uncommitted_file_rechecks_current_roots_before_ledger_change(self):
        self.atomic(self.output/'native-orphan-return.json',self.value)
        (self.output/'native-orphan-journal.bin').write_bytes(self.raw)
        with self.assertRaisesRegex(RuntimeError,'root_changed'):self.recover(capture_error=RuntimeError('root_changed'))
        self.assertEqual(self.journal.get_command(self.run,'start')['status'],'started')
        self.assertEqual(len(self.journal.commands_for_run(self.run)),1)
    def test_wrong_source_leftover_never_changes_ledger(self):
        wrong=dict(self.value,capture_source_sha256='d'*64)
        self.atomic(self.output/'native-orphan-return.json',wrong);(self.output/'native-orphan-journal.bin').write_bytes(self.raw)
        self.assertEqual(self.recover(),(False,0));self.assertEqual(self.journal.get_command(self.run,'start')['status'],'started')
    def test_concurrent_broker_owned_stop_is_not_reconciled_as_host_owned(self):
        self.journal.reserve_command(self.run,'gui-stop','host_stop',{})
        self.journal.mark_dispatching(self.run,'gui-stop')
        self.assertFalse(self.recover()[0])
        self.assertEqual(self.journal.get_command(self.run,'gui-stop')['status'],'dispatching')
        self.journal.record_outcome(self.run,'gui-stop','completed',dict(reason_code='host_stop_requested'))
        self.assertTrue(self.recover()[0])


if __name__=='__main__':unittest.main()
