"""Trusted external evidence roots and relocated immutable binary provenance."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from host_runtime import evidence_adapter as adapter
from host_runtime.contracts import ContractError


class RelocatedExecutorPin(unittest.TestCase):
    def test_historical_path_is_only_provenance_and_current_package_hash_stays_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'app';directory=root/'production/persistent/bin-v2';directory.mkdir(parents=True)
            dll=directory/'ProductionPersistent.dll';dll.write_bytes(b'fixed dll');host=directory/'persistent_host.exe';host.write_bytes(b'fixed host')
            source=Path(temp)/'absent-original-checkout';self.assertFalse(source.exists())
            layout=root/'companion-layout.json';layout.write_text(json.dumps(dict(schema_version=1,source_root=str(source))))
            scope=root/'production/persistent/capability-evidence.json'
            scope.write_text(json.dumps(dict(binaries={name:dict(path=str(source/path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for name,path in [('pause_guard_v2_dll',dll),('pause_guard_v2_host',host)]})))
            with patch.multiple(adapter,ROOT=root,PRODUCTION_EXECUTOR=dll,PRODUCTION_HOST=host,PRODUCTION_SCOPE=scope):
                self.assertEqual(adapter._production_integrity()[0],hashlib.sha256(dll.read_bytes()).hexdigest())
                layout.write_text(json.dumps(dict(schema_version=1,source_root=str(Path(temp)/'wrong-original'))))
                with self.assertRaises(ContractError):adapter._production_integrity()
                layout.write_text(json.dumps(dict(schema_version=1,source_root=str(source))))
                dll.write_bytes(b'changed current dll')
                with self.assertRaises(ContractError):adapter._production_integrity()

    def test_explicit_root_is_forwarded_only_from_trusted_argument(self):
        from types import SimpleNamespace
        calls=[];root=Path('C:/trusted/root')
        fake=SimpleNamespace(capability_evidence=lambda path,session,**kw:calls.append(('production',kw)),conscript_evidence=lambda path,session,**kw:calls.append(('persistent',kw)))
        with patch.object(adapter,'_existing_module',return_value=fake):
            adapter._production(Path('report'),{'acceptance_root':'untrusted'},root=root)
            adapter._persistent(Path('status'),{'acceptance_root':'untrusted'},root=root)
        self.assertEqual(calls,[('production',dict(root=root)),('persistent',dict(root=root))])

    def test_host_never_takes_acceptance_root_from_session_object(self):
        host=adapter._existing_module('battle_host')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'report.json';path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'acceptance runs'):
                host.capability_evidence(path,dict(acceptance_root=str(root)))
            with self.assertRaisesRegex(ValueError,'outside acceptance runs'):
                host.conscript_evidence(path,dict(acceptance_root=str(root)))
            with self.assertRaisesRegex(ValueError,'Invalid trusted acceptance root'):
                host.capability_evidence(path,{},root=Path('.'))


if __name__=='__main__':unittest.main()
