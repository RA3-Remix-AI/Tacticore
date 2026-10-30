"""Independent temporary-library crash/restart and multi-instance tests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'strategy'),str(ROOT)]
import test_connection_config_service_v1 as base
from host_runtime import connection_config_service_v1 as service_module
from host_runtime import connection_config_bootstrap_v1 as bootstrap
from host_runtime import connection_config_atomic_v1 as atomic
from host_runtime.connection_config_service_v1 import ConnectionConfigServiceV1
from host_runtime.profile_store import ProfileStore
from host_runtime.contracts import ContractError
from http_adapter import load_profile

SCRATCH=Path('D:/CodexScratch/ra3-independent-next/connection-config-v1')


class IndependentConnectionTests(unittest.TestCase):
    def case(self):
        SCRATCH.mkdir(parents=True,exist_ok=True);case=base.ConnectionConfigTests(methodName='runTest')
        original=tempfile.TemporaryDirectory
        with patch.object(tempfile,'TemporaryDirectory',side_effect=lambda **kwargs:original(dir=SCRATCH,**kwargs)):case.setUp()
        self.addCleanup(case.tearDown)
        return case

    def restart(self,case):
        case.service.close();case.store.close()
        case.store=ProfileStore(case.lib,case.root/'state')
        case.service=ConnectionConfigServiceV1(case.store,stopped_guard=lambda:case.allowed,registration_path=case.registration)

    def style(self,case):
        before=case.store.get_profile(base.PROFILE)['profile'];draft=deepcopy(before['draft'])
        draft['custom_traits']='independent persisted old style 宏观'
        case.store.save_profile(str(uuid.uuid4()),draft,before['revision'])
        return case.store.get_profile(base.PROFILE)['profile']

    def recover(self,case,before):
        self.restart(case)
        pending=case.invoke('connections.configuration',{})['result'];self.assertFalse(pending['ready'])
        with self.assertRaises(ContractError):
            with case.service.admission_barrier():self.fail('launch forbidden during recovery')
        result=case.invoke('connections.recover',pending['recovery'][0]);self.assertTrue(result['ok'],result)
        self.assertTrue(result['result']['saved'])
        after=case.store.get_profile(base.PROFILE)['profile']
        self.assertEqual(after['revision'],before['revision']+1)
        self.assertEqual(after['custom_traits'],before['custom_traits']);self.assertTrue(after['validation']['ok'])
        self.assertEqual(load_profile(case.lib,base.PROFILE).key,base.FAKE_KEY)
        repeated=case.invoke('connections.recover',pending['recovery'][0]);self.assertTrue(repeated['ok'])
        self.assertEqual(case.store.get_profile(base.PROFILE)['profile']['revision'],after['revision'])
        with case.service.admission_barrier():pass

    def test_restart_after_registration_swap_failure_recovers_actual_dpapi_and_style(self):
        case=self.case();before=self.style(case);args=case.args();real=service_module.atomic_bytes
        def write(path,raw):
            if Path(path)==case.registration:raise OSError('ARTIFICIAL CRASH ONLY')
            return real(path,raw)
        with patch.object(service_module,'atomic_bytes',side_effect=write):self.assertFalse(case.invoke('connections.configure',args)['ok'])
        self.recover(case,before)

    def test_restart_after_store_commit_but_before_configuration_sqlite_commit(self):
        case=self.case();before=self.style(case);args=case.args();real=case.service._db
        class CommitFault:
            armed=True
            def execute(self,sql,*values):
                if sql=='COMMIT' and self.armed:self.armed=False;raise OSError('ARTIFICIAL COMMIT CRASH')
                return real.execute(sql,*values)
            def close(self):real.close()
        case.service._db=CommitFault()
        self.assertFalse(case.invoke('connections.configure',args)['ok'])
        # Draft DB committed already, configuration DB rolled back: actual cross-DB recovery.
        self.assertEqual(case.store.get_profile(base.PROFILE)['profile']['revision'],before['revision']+1)
        self.recover(case,before)

    def test_restart_after_both_commits_before_intent_close_is_idempotent(self):
        case=self.case();before=self.style(case);args=case.args();request=str(uuid.uuid4());real=case.service._write_intent
        def write(intent):
            if intent['phase']=='completed':raise OSError('ARTIFICIAL INTENT CLOSE CRASH')
            return real(intent)
        with patch.object(case.service,'_write_intent',side_effect=write):self.assertFalse(case.invoke('connections.configure',args,request)['ok'])
        self.recover(case,before)
        result=case.invoke('connections.configure',args,request);self.assertTrue(result['ok'],result)
        self.assertEqual(case.store.get_profile(base.PROFILE)['profile']['revision'],before['revision']+1)

    def test_two_instances_share_admission_barrier_without_new_key_write(self):
        case=self.case();args=case.args();other_store=ProfileStore(case.lib,case.root/'state')
        self.addCleanup(other_store.close)
        other=ConnectionConfigServiceV1(other_store,stopped_guard=lambda:True,registration_path=case.registration)
        self.addCleanup(other.close);started=threading.Event();entered=threading.Event();release=threading.Event();advanced=threading.Event()
        protect=other.credentials.protect
        def mark(value):advanced.set();return protect(value)
        other.credentials.protect=mark
        original=case.lib.read_bytes()
        def admission():
            with case.service.admission_barrier():entered.set();release.wait(3)
        def save():
            started.set();return other.handle(dict(schema_version=1,request_id=str(uuid.uuid4()),operation='connections.configure',args=args))
        with ThreadPoolExecutor(max_workers=2) as pool:
            held=pool.submit(admission);self.assertTrue(entered.wait(1));saved=pool.submit(save);self.assertTrue(started.wait(1))
            self.assertFalse(advanced.wait(.15));self.assertFalse(saved.done());self.assertEqual(case.lib.read_bytes(),original)
            self.assertEqual(list((case.lib.parent/'secrets').glob('*.dpapi')),[])
            release.set();held.result(timeout=3);result=saved.result(timeout=3)
        self.assertTrue(result['ok'],result)
        self.assertTrue(advanced.is_set())
        self.assertEqual(load_profile(case.lib,base.PROFILE).key,base.FAKE_KEY)

    def test_second_stopped_recheck_catches_new_unreleased_run_after_barrier(self):
        case=self.case();args=case.args();calls=[]
        case.service.stopped_guard=lambda: calls.append(True) or len(calls)==1
        before=case.lib.read_bytes();result=case.invoke('connections.configure',args)
        self.assertEqual(result['error']['code'],'connection_config_run_unreleased');self.assertEqual(case.lib.read_bytes(),before)
        self.assertEqual(case.service.configuration({})['ready'],True)

    def test_torn_first_use_stage_never_publishes_partial_marker_library_or_registration(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        for target in ('connection-first-use-v1.json','library.json','registration.json'):
            with self.subTest(target=target),tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
                root=Path(folder);args=(root/'library.json',root/'registration.json',root/'state');real=atomic.write_stage
                def tear(stream,raw):
                    if Path(stream.name).name.startswith(target+'.'):
                        stream.write(raw[:9]);stream.flush();raise OSError('ARTIFICIAL TORN STAGE')
                    return real(stream,raw)
                with patch.object(atomic,'write_stage',side_effect=tear),self.assertRaises(OSError):
                    bootstrap.initialize_connection_library_v1(*args,commander_id=base.PROFILE)
                self.assertEqual(list(root.rglob('*.stage')),[])
                failed=root/'state'/target if target=='connection-first-use-v1.json' else root/target
                self.assertFalse(failed.exists())
                self.assertTrue(bootstrap.initialize_connection_library_v1(*args,commander_id=base.PROFILE)['initialized'])

    def test_torn_receipt_key_stage_can_restart_without_replacing_an_existing_key(self):
        case=self.case();case.service.close();path=case.root/'state/connection-receipts-v1.dpapi';path.unlink()
        other=ConnectionConfigServiceV1.__new__(ConnectionConfigServiceV1);real=atomic.write_stage
        def tear(stream,raw):
            if Path(stream.name).name.startswith(path.name+'.'):
                stream.write(raw[:9]);stream.flush();raise OSError('ARTIFICIAL TORN KEY STAGE')
            return real(stream,raw)
        try:
            with patch.object(atomic,'write_stage',side_effect=tear),self.assertRaises(OSError):
                other.__init__(case.store,stopped_guard=lambda:True,registration_path=case.registration)
        finally:
            if hasattr(other,'_db'):other._db.close()
        self.assertFalse(path.exists());self.assertEqual(list(path.parent.glob('*.stage')),[])
        case.service=ConnectionConfigServiceV1(case.store,stopped_guard=lambda:True,registration_path=case.registration)
        self.assertTrue(case.service.configuration({})['ready'])

    def test_exclusive_publication_keeps_a_competing_complete_winner(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            path=Path(folder)/'exclusive';real=atomic.os.link
            def win(source,target):Path(target).write_bytes(b'complete-winner');return real(source,target)
            with patch.object(atomic.os,'link',side_effect=win),self.assertRaises(FileExistsError):
                atomic.exclusive_bytes(path,b'losing-publisher')
            self.assertEqual(path.read_bytes(),b'complete-winner');self.assertEqual(list(path.parent.glob('*.stage')),[])

    def test_receipt_key_publication_loser_loads_the_winning_dpapi_key(self):
        case=self.case();case.service.close();path=case.root/'state/connection-receipts-v1.dpapi';path.unlink()
        real=atomic.os.link;winning='1'*64;cipher=case.service.credentials.protect(winning)
        def win(source,target):Path(target).write_bytes(cipher);return real(source,target)
        with patch.object(atomic.os,'link',side_effect=win):
            case.service=ConnectionConfigServiceV1(case.store,stopped_guard=lambda:True,registration_path=case.registration)
        self.assertEqual(case.service._receipt_key,bytes.fromhex(winning));self.assertEqual(path.read_bytes(),cipher)
        self.assertTrue(case.service.configuration({})['ready'])

    def test_existing_corrupt_receipt_key_remains_refused_and_is_never_replaced(self):
        case=self.case();before=case.lib.read_bytes();path=case.root/'state/connection-receipts-v1.dpapi';path.write_bytes(b'artificial-torn-cipher')
        other=ConnectionConfigServiceV1.__new__(ConnectionConfigServiceV1)
        try:
            with self.assertRaisesRegex(ContractError,'connection_config_unavailable'):
                other.__init__(case.store,stopped_guard=lambda:True,registration_path=case.registration)
        finally:
            if hasattr(other,'_db'):other._db.close()
        self.assertEqual(case.lib.read_bytes(),before)


if __name__=='__main__':unittest.main()
