"""Historical software recognition never substitutes for full return proof."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from host_runtime import native6_history as h,native6_lifecycle as live
from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.native6_runtime_contract import GAME_SHA,PACKAGE_SHA,FIELD_KIND


class Native6History(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.base=Path(temp.name)
        self.output=self.base/'output';self.source=self.output/'source';self.source.mkdir(parents=True)
        self.root=self.base/'never-import-this-old-root';self.root.mkdir();self.report=self.base/'report';self.report.mkdir()
        self.binding=SessionBinding.from_dict(dict(schema_version=1,session_id=str(uuid.uuid4()),host_id=str(uuid.uuid4()),
            commander_id=str(uuid.uuid4()),player_id=3,game_process_id=123,game_process_start='2026-10-31T15:10:45.1994388+00:00',
            game_sha256=GAME_SHA,mod_sha256=PACKAGE_SHA))
        self.session=dict(session_id=self.binding.session_id,pid=123,process_creation_filetime=134379330451994388,
            start_time=self.binding.game_process_start,mod_sha256=PACKAGE_SHA,game=str(self.base/'RA3_1.12.game'))
        self.row=dict(run_id=str(uuid.uuid4()),output_path=str(self.output),session_path=str(self.source/'1-session.json'))
        closure='c'*64
        build=dict(kind=FIELD_KIND,protocol_version=6,package_sha256=PACKAGE_SHA,source_closure_sha256=closure)
        inventory=dict(files={})
        for name in ('native6_lifecycle.py','native6_release.py','native6_no_attachment.py','native6_orphan_return.py',
                     'native5_orphan_return_v1.py','strategic_unified_unknown_return_v5.py'):
            inventory['files']['app/integration/host_runtime/'+name]=h.sha(Path(h.__file__).with_name(name))
        values=[b"raise AssertionError('historical_host_source_executed')\n",self.session,None,{},self.binding.public(),inventory,build,{}]
        names=['macro_host.py','session.json','trial.json','profile.json','binding.json','manifest.json','build-manifest.json','native6-trial.json']
        for i in (0,1,3,4,6,7):self.write(self.source/(str(i)+'-'+names[i]),values[i])
        for index,key in ((0,'app/integration/macro_host.py'),(6,'native/strategic6/build-manifest.json'),(7,'qualification/native6-trial.json')):
            inventory['files'][key]=h.sha(self.source/(str(index)+'-'+names[index]))
        self.write(self.source/'5-manifest.json',inventory);self.pin=h.sha(self.source/'5-manifest.json')
        values[2]=dict(schema_version=14,kind='native6_manifest_bound_trial',runtime_root=str(self.root),runtime_manifest_sha256=self.pin)
        self.write(self.source/'2-trial.json',values[2])
        sources=[dict(path=str(self.root/name),copy=str(i)+'-'+name,sha256=h.sha(self.source/(str(i)+'-'+name))) for i,name in enumerate(names)]
        self.write(self.output/'sources.json',dict(kind='pre_execution_macro_host_sources',sources=sources))
        self.value=dict(kind=live.KIND,run_id=self.row['run_id'],binding=self.binding.public(),runtime_root=str(self.root),
            runtime_manifest_sha256=self.pin,report=str(self.report),sources_sha256=h.sha(self.output/'sources.json'))
        self.write(self.output/'native6-context.json',self.value)
        self.addCleanup(patch.stopall)
        patch.dict(h.PRIOR,{self.pin:closure},clear=True).start();patch.object(h,'trusted_pin',return_value='f'*64).start()
        patch.object(live,'report_directory',return_value=self.report).start()

    @staticmethod
    def write(path,value):path.write_bytes(value if isinstance(value,bytes) else json.dumps(value,sort_keys=True).encode())

    def test_original_context_replays_without_old_code_or_live_global_changes(self):
        before=(live.context,live.verified_return,live.runtime_root,live.trusted_pin)
        self.assertEqual(h.context(self.row,self.session,self.binding)[0],self.value)
        self.assertEqual((live.context,live.verified_return,live.runtime_root,live.trusted_pin),before)

    def test_unknown_old_software_and_changed_source_are_rejected(self):
        with patch.dict(h.PRIOR,{},clear=True):
            with self.assertRaises(ContractError):h.context(self.row,self.session,self.binding)
        (self.source/'0-macro_host.py').write_bytes(b'changed-source')
        with self.assertRaises(ContractError):h.context(self.row,self.session,self.binding)

    def test_current_manifest_replays_from_temporary_installer_without_live_root_rebinding(self):
        # Installer guard runs beside its own verified new runtime, while the
        # recorded root is comparison-only data from the original install.
        before=(live.context,live.runtime_root,live.trusted_pin)
        with patch.object(h,'trusted_pin',return_value=self.pin),patch.dict(h.PRIOR,{},clear=True),\
                patch.object(live,'runtime_root',return_value=self.base/'new-installer-guard'):
            root_function=live.runtime_root
            self.assertEqual(h.context(self.row,self.session,self.binding)[0],self.value)
            self.assertIs(live.runtime_root,root_function)
            self.value['runtime_root']=str(self.base/'substituted-old-root')
            self.write(self.output/'native6-context.json',self.value)
            with self.assertRaises(ContractError):h.context(self.row,self.session,self.binding)
        self.assertEqual((live.context,live.runtime_root,live.trusted_pin),before)

    def test_old_manifest_and_build_cannot_repin_themselves(self):
        for filename in ('5-manifest.json','6-build-manifest.json'):
            path=self.source/filename;raw=path.read_bytes();path.write_bytes(raw+b' ')
            with self.assertRaises(ContractError):h.context(self.row,self.session,self.binding)
            path.write_bytes(raw)
        with patch.dict(h.PRIOR,{self.pin:'d'*64},clear=True):
            with self.assertRaises(ContractError):h.context(self.row,self.session,self.binding)

    def test_changed_current_verifier_is_not_used_to_reinterpret_old_proof(self):
        real=h.sha
        def changed(path):return '0'*64 if Path(path).name=='native6_release.py' else real(path)
        with patch.object(h,'sha',side_effect=changed):
            with self.assertRaises(ContractError):h.context(self.row,self.session,self.binding)

    def test_old_identity_and_scalar_release_do_not_grant_return(self):
        self.assertFalse(h.verified_return(SimpleNamespace(),self.row,self.binding,{}))
        self.write(self.output/'macro-release.json',dict(kind='macro_policy_native_release',run_id=self.row['run_id'],
            binding=self.binding.public(),native_release_verified=True,host_pid=777,host_start_time='old',
            native_release_contract='native6_unified_release_v1'))
        receipt=dict(binding_hash=self.binding.binding_hash,release_sha256=h.sha(self.output/'macro-release.json'),
            native_release_verified=True,host_pid=777,host_start_time='old',native_release_contract='native6_unified_release_v1')
        backend=SimpleNamespace(journal=SimpleNamespace(get_command=lambda *_:dict(status='released',receipt=receipt)))
        self.assertFalse(h.verified_return(backend,self.row,self.binding,receipt))
        wrong=SessionBinding.from_dict(dict(self.binding.public(),session_id=str(uuid.uuid4())))
        with self.assertRaises(ContractError):h.context(self.row,self.session,wrong)


if __name__=='__main__':unittest.main()
