"""Actual field-pinned macro registration and desktop launch boundary checks."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid
import threading
import time

from host_runtime.contracts import ContractError
from host_runtime.desktop_backend import SessionRegistration
from host_runtime.macro_bundle import create_bundle,load_bundle
from host_runtime.macro_durable import DurableMacroTransport
from host_runtime.journal import CommandJournal
import test_host_runtime_desktop_backend as legacy

ROOT=Path(__file__).resolve().parents[1]
PACKAGE='2bb7bb23a448d962e25f7bc76f498c0aa5d9239ceb0a78e3a442c8457b842276'


def bundle(path,production=False,choices=None):
    return create_bundle(path,build=ROOT/'native-ai/macro-policy-runtime/bin/policy-v13-production-feedback-20261028',
        visibility=ROOT/'reports/macro-visibility-2bb7bb23-derived-20261028-v1',
        normal=ROOT/'reports/macro-policy-budget-73924-20261028-v3',
        host_loss=ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',
        expiry=ROOT/'reports/macro-policy-expiry-71320-20261028-v1',
        **(dict(production=ROOT/'reports/macro-production-count-69152-20261028-v1',
            production_static=ROOT/'reports/macro-builder-static-20261028-v2') if production else {}),
        **(dict(production_choices=choices) if choices is not None else {}))


class MacroRegistrationTests(unittest.TestCase):
    def test_choice_bundle_qualifies_each_count_pair_and_pins_native_field_records(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'macro-choices.json'
            public=bundle(path,production=True,choices=[ROOT/'reports/macro-production-conscript1-60136-20261028-v1',
                ROOT/'reports/macro-production-flak3-60136-20261028-v1',ROOT/'reports/macro-production-tank1-60136-20261028-v2'])
            self.assertEqual(public['production_counts'],{'produceflak':[2,3],'produceconscript':[1],'producetank':[1]})
            value=json.loads(path.read_text());self.assertEqual(value['schema_version'],3)
            self.assertTrue(any(p.endswith('macro_production_choices.py') for p in value['pins']))
            value['pins'][str(ROOT/'reports/macro-production-conscript1-60136-20261028-v1/transport/policy-probe.jsonl')]='0'*64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)

    def test_field_bundle_and_registration_require_no_old_unit_executor(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=root/'session.json';path=root/'macro.json'
            session.write_text(json.dumps(dict(run_directory=str(root),mod_sha256=PACKAGE)))
            public=bundle(path)
            registration=SessionRegistration.trusted(session,root=root,macro_bundle=path)
            self.assertIsNone(registration.production_report);self.assertIsNone(registration.persistent_status)
            self.assertEqual(set(public['available_actions']),{'budgeteconomy','budgetarmy'})
            self.assertEqual(set(registration.evidence_paths()),{'session_file','macro_bundle'})
            with self.assertRaisesRegex(ContractError,'mixed_evidence'):
                SessionRegistration.trusted(session,session,session,root=root,macro_bundle=path)
            value=json.loads(path.read_text());value['pins'][next(iter(value['pins']))]='0'*64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)

    def test_production_bundle_qualifies_observed_count_and_pins_new_consumers(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'macro-production.json';public=bundle(path,production=True)
            self.assertEqual(public['available_additional_counts'],[2])
            self.assertFalse(public['completed_units_guaranteed'])
            value=json.loads(path.read_text())
            self.assertEqual(value['schema_version'],2)
            self.assertTrue(any(name.endswith('macro_production_public.py') for name in value['pins']))
            value['production']=str(ROOT/'reports/macro-production-count-69152-20261028-v2')
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)

    def test_bundle_cannot_authorize_another_package(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'macro.json';bundle(path)
            with self.assertRaisesRegex(ContractError,'not_qualified'):
                load_bundle(path,dict(mod_sha256='0'*64))

    def test_versioned_session_filename_is_bound_by_exact_hash(self):
        from host_runtime.macro_policy_runtime import trial
        pre,final,manifest,rows,evidence=trial(ROOT/'reports/macro-desktop-7db4aa27-998e-4432-b0f4-1f763f754cde')
        self.assertTrue(final['cleanup_verified'])
        self.assertEqual(final['session_id'],'0dfb3af0-82e3-4f9f-b42a-4a2a2daad25d')
        self.assertTrue(any(Path(row['path']).name=='desktop-session-v2.json' for row in pre['sources']))


class MacroDesktopLaunchTests(legacy.DesktopBackendTests):
    def setUp(self):
        super().setUp()
        value=json.loads(self.session.read_text());value['mod_sha256']=PACKAGE
        self.session.write_text(json.dumps(value));self.bundle=self.run/'macro.json';bundle(self.bundle)
        original=self.checks.check
        def check(*args):
            admission=original(*args)
            from dataclasses import replace
            return replace(admission,capabilities=dict(control_mode='macro_native',native_macro=True,
                available_macro_actions=['budgeteconomy','budgetarmy'],supported_units=[],supported_foci=['native_baseline'],
                tactics_supported=False,runtime_tactical_supported=False,runtime_recovery_supported=False,runtime_purposes=[]))
        self.checks.check=check
        self.backend.register_session(self.session,macro_bundle=self.bundle)

    # Inherit only setup/helpers; legacy tests intentionally use schema1.
    def test_macro_path_launches_bound_host_and_survives_registration_reload(self):
        self.assertEqual(self.backend._registration().macro_bundle,self.bundle)
        result,request,args=self.start()
        command=self.spawner.commands[0]
        self.assertTrue(any(str(item).endswith('macro_host.py') for item in command))
        self.assertIn('--macro-bundle',command)
        for old in ('--persistent-evidence','--runtime-report','--evidence'):
            self.assertNotIn(old,command)
        self.assertEqual(self.backend._registration().macro_bundle,self.bundle)
        self.assertTrue(self.backend.journal.get_command(result['run_id'],request)['payload']['capabilities']['native_macro'])
        self.backend.run_start(self.profile,args,request)
        self.assertEqual(len(self.spawner.commands),1)

    def test_schema2_registration_hash_prevents_stale_bundle_changes(self):
        value=json.loads(self.bundle.read_text());value['kind']='invented'
        self.bundle.write_text(json.dumps(value))
        self.assertFalse(self.ready()['ready']);self.assertEqual(self.spawner.commands,[])


# Avoid running the legacy suite a second time through inheritance.
for name in dir(legacy.DesktopBackendTests):
    if name.startswith('test_'):setattr(MacroDesktopLaunchTests,name,None)


class DurableMacroTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.journal=CommandJournal(Path(self.temp.name)/'ledger.db')
        self.run=str(uuid.uuid4());self.journal.register_run(self.run,dict(session_id='test'))
        self.calls=[]
        def apply(actions,duration,ident):self.calls.append(ident);return dict(seq=1)
        self.native=SimpleNamespace(session={},apply=apply,close=lambda:None)
        self.transport=DurableMacroTransport(self.native,self.journal,self.run)

    def tearDown(self):self.journal.close();self.temp.cleanup()

    def test_native_intent_is_durable_before_call_and_duplicate_does_not_deliver(self):
        ident=str(uuid.uuid4());original=self.native.apply
        def apply(*args):
            self.assertEqual(self.journal.get_command(self.run,ident)['status'],'dispatching')
            return original(*args)
        self.native.apply=apply
        first=self.transport.apply(['budgetarmy'],450,ident)
        self.assertEqual(self.transport.apply(['budgetarmy'],450,ident),first)
        self.assertEqual(self.calls,[ident]);self.assertFalse(first['native_effect_verified'])

    def test_uncertain_native_delivery_is_terminal_and_never_retried(self):
        ident=str(uuid.uuid4())
        def apply(*args):self.calls.append(ident);raise RuntimeError('private diagnostic')
        self.native.apply=apply
        with self.assertRaises(RuntimeError):self.transport.apply(['budgetarmy'],450,ident)
        with self.assertRaisesRegex(ContractError,'already_claimed'):self.transport.apply(['budgetarmy'],450,ident)
        self.assertEqual(self.calls,[ident]);self.assertEqual(self.journal.get_command(self.run,ident)['status'],'uncertain')


class MacroStatusWriteTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows file-sharing regression')
    def test_ui_reader_temporarily_holding_status_does_not_fault_writer(self):
        import ctypes
        from ctypes import wintypes
        from host_runtime.desktop_backend import _atomic
        win=ctypes.WinDLL('kernel32',use_last_error=True)
        win.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,
                                 wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        win.CreateFileW.restype=wintypes.HANDLE;win.CloseHandle.argtypes=[wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'host-status.json';_atomic(path,dict(sequence=1))
            handle=win.CreateFileW(str(path),0x80000000,1,None,3,0,None)
            self.assertNotIn(handle,(None,ctypes.c_void_p(-1).value))
            def release():time.sleep(.08);win.CloseHandle(handle)
            worker=threading.Thread(target=release);worker.start()
            try:_atomic(path,dict(sequence=2))
            finally:worker.join()
            self.assertEqual(json.loads(path.read_text()),dict(sequence=2))
            self.assertEqual(list(Path(temp).glob('*.tmp')),[])


if __name__=='__main__':unittest.main()
