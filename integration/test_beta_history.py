"""Failed OS enumeration and file tampering cannot certify historical return."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from types import ModuleType
import sys
import unittest
import importlib.util
from unittest.mock import patch

from host_runtime import beta_history as h,session_discovery_native as native
from host_runtime.contracts import ContractError


class BetaHistory(unittest.TestCase):
    def test_failed_first_and_partial_next_never_attest_host_absence(self):
        for first in (True,False):
            closed=[];api=native.Win32ReadOnly.__new__(native.Win32ReadOnly)
            def initial(handle,pointer):
                if first:c.set_last_error(5);return False
                row=c.cast(pointer,c.POINTER(native.PROCESSENTRY32W)).contents
                row.szExeFile='other.exe';row.th32ProcessID=1;return True
            def next_row(*_):c.set_last_error(5);return False
            api.k=SimpleNamespace(CreateToolhelp32Snapshot=lambda *_:123,Process32FirstW=initial,
                Process32NextW=next_row,CloseHandle=closed.append)
            with patch.object(native,'Win32ReadOnly',return_value=api),patch('host_runtime.native5_helper_identity_v1.process_identity') as actual:
                with self.assertRaises(ContractError):h.host_ended(dict(host_pid=456,host_start_time='2026-01-01T00:00:00+00:00'))
                actual.assert_not_called()
            self.assertEqual(closed,[123])

    def test_current_python_incarnation_and_access_denied_remain_blockers(self):
        from host_runtime.session_discovery_native import creation_start
        ticks=133000000000000000;receipt=dict(host_pid=456,host_start_time=creation_start(ticks))
        with patch.object(native,'Win32ReadOnly',return_value=SimpleNamespace(process_ids=lambda _:[456])):
            with patch('host_runtime.native5_helper_identity_v1.process_identity',return_value=dict(alive=True,process_creation_filetime=ticks)):
                with self.assertRaisesRegex(ContractError,'beta_existing_run_unreleased'):h.host_ended(receipt)
            with patch('host_runtime.native5_helper_identity_v1.process_identity',side_effect=OSError(5,'denied')):
                with self.assertRaises(ContractError):h.host_ended(receipt)

    def test_historical_context_uses_same_trusted_bytecode_without_changing_live_globals(self):
        from host_runtime import strategic_no_attachment_v5 as live
        before=(live.ROOT,live.__file__,live.verified_return)
        context=h.FileReviewContext(Path('C:/qualified-original-root'))
        copied=context.module(live.__name__)
        self.assertEqual(copied.ROOT,Path('C:/qualified-original-root'))
        self.assertEqual(Path(copied.__file__),Path('C:/qualified-original-root/integration/host_runtime/strategic_no_attachment_v5.py'))
        self.assertIs(copied.verified_return.__code__,live.verified_return.__code__)
        self.assertEqual((live.ROOT,live.__file__,live.verified_return),before)

    def test_explicit_builder_loader_never_executes_unverified_old_source(self):
        with tempfile.TemporaryDirectory() as folder:
            old=Path(folder)/'original';path=old/'native-ai/strategic-portable-runtime-v6/build.py'
            path.parent.mkdir(parents=True);path.write_text("raise AssertionError('old_source_executed')\n",encoding='utf-8')
            context=h.FileReviewContext(old)
            spec=context.spec('synthetic_closed_history_builder',path);builder=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            self.assertTrue(callable(builder.verify))
            self.assertEqual(Path(builder.__file__),path)
            self.assertEqual(path.read_text(encoding='utf-8'),"raise AssertionError('old_source_executed')\n")

    def test_external_search_path_and_cached_module_cannot_reenter_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);outside=base/'external';outside.mkdir()
            (outside/'unowned_review_plugin.py').write_text("raise AssertionError('external_source_executed')\n",encoding='utf-8')
            context=h.FileReviewContext(base/'old')
            with patch.object(sys,'path',[str(outside),*sys.path]):
                with self.assertRaises(ModuleNotFoundError):context.import_module('unowned_review_plugin')
            bad=ModuleType('unowned_review_plugin');bad.__file__=str(outside/'unowned_review_plugin.py')
            with patch.dict(sys.modules,unowned_review_plugin=bad):
                with self.assertRaises(ContractError):context.import_module('unowned_review_plugin')

    def test_cached_package_paths_parents_and_children_are_checked_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            outside=Path(folder);(outside/'child.py').write_text("raise AssertionError('external_child_executed')\n",encoding='utf-8')
            context=h.FileReviewContext(outside/'old')
            package=ModuleType('review_package');package.__file__=str(context.package/'safe.py');package.__path__=[str(outside)]
            with patch.dict(sys.modules,review_package=package):
                for name,items in [('review_package',('child',)),('review_package.child',())]:
                    with self.assertRaises(ContractError):context.import_module(name,fromlist=items)
            package.__path__=[str(context.package)]
            child=ModuleType('review_package.child');child.__file__=str(outside/'child.py')
            package.child=child
            with patch.dict(sys.modules,{'review_package':package,'review_package.child':child}):
                with self.assertRaises(ContractError):context.import_module('review_package',fromlist=('child',))

    def test_report_root_requires_the_frozen_host_hash_and_fixed_source_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'original';output=base/'output';source=output/'source'
            root.mkdir();source.mkdir(parents=True);raw=b'# frozen evidence source, never executed\n'
            (source/'0-macro_host.py').write_bytes(raw)
            entry=dict(path=str(root/'integration/macro_host.py'),copy='0-macro_host.py',sha256=hashlib.sha256(raw).hexdigest())
            (output/'sources.json').write_text(json.dumps(dict(kind='pre_execution_macro_host_sources',sources=[entry])),encoding='utf-8')
            self.assertEqual(h.source_root(dict(output_path=str(output))),root)
            (source/'0-macro_host.py').write_bytes(b'# changed')
            with self.assertRaises(ContractError):h.source_root(dict(output_path=str(output)))


if __name__=='__main__':unittest.main()
