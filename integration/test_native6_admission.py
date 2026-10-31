"""Authority and lawful-view rejection tests; no Game/model access."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from host_runtime import native6_qualification as q
from host_runtime import native6_visibility as visibility
from host_runtime.contracts import ContractError
from host_runtime.native6_no_attachment import verified_capture,KIND


class Admission(unittest.TestCase):
    def test_developer_tree_and_inherited_pin_cannot_create_authority(self):
        with patch.dict(os.environ,TACTICORE_RUNTIME_MANIFEST_SHA256='a'*64):
            with self.assertRaises(ContractError):q.current()

    def test_descriptor_fields_and_manifest_pin_rechecked_each_load(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'trial.json'
            descriptor=dict(schema_version=14,kind=q.KIND,runtime_root=str(root),runtime_manifest_sha256='a'*64)
            inventory=dict(files={});manifest={}
            authority=(root,'a'*64,inventory,manifest,{})
            with patch.object(q,'current',return_value=authority) as current:
                path.write_text(json.dumps(descriptor),encoding='utf-8')
                _,scope=q.load(path)
                self.assertEqual(scope.native_transport_protocol,6)
                self.assertEqual(len(scope.available_actions),14)
                current.return_value=(root,'b'*64,inventory,manifest,{})
                with self.assertRaises(ContractError):q.load(path)
                current.return_value=authority
                for change in ({'product_acceptance_verified':True},{'schema_version':13},{'runtime_root':str(root/'other')}):
                    path.write_text(json.dumps(dict(descriptor,**change)),encoding='utf-8')
                    with self.assertRaises(ContractError):q.load(path)

    def test_missing_pin_rejected_before_reading_inventory_or_build(self):
        with patch.object(q,'verify_inventory') as inventory:
            for pin in (None,'','A'*64,True):
                with self.assertRaises(ContractError):q.verify_qualification(Path('C:/unused'),pin)
            inventory.assert_not_called()

    def test_observer_or_wrong_package_denied_before_memory_reads(self):
        memory=SimpleNamespace(read=lambda *_:self.fail('unqualified memory read'))
        for viewer in (2,4,True,'3'):
            with self.assertRaises(ValueError):visibility.bind_session(memory,{},viewer)
        with patch.object(visibility,'current',return_value=(Path('C:/runtime'),'a'*64,{}, {},dict(package_sha256=q.PACKAGE_SHA))):
            with self.assertRaises(ValueError):visibility.bind_session(memory,dict(mod_sha256='b'*64,registry='C:/other'),3)

    def test_native_signature_drift_rejected_before_world_or_shroud_reads(self):
        session=dict(mod_sha256=q.PACKAGE_SHA,registry='C:/runtime/qualification/registry.json',pid=123)
        memory=SimpleNamespace(pid=123,read=lambda *_:b'\x01'*24,u32=lambda *_:self.fail('world read after signature mismatch'))
        cap=dict(package_sha256=q.PACKAGE_SHA,safety={},expected_signatures={'0x992130':'00'*24})
        with patch.object(visibility,'current',return_value=(Path('C:/runtime'),'a'*64,{}, {},cap)):
            with self.assertRaisesRegex(ValueError,'signature changed'):visibility.bind_session(memory,session,3)

    def test_no_attachment_requires_native6_mapping_both_times(self):
        binding=SimpleNamespace(game_process_id=123,game_sha256='a'*64,public=lambda:dict(epoch='fixture'))
        session=dict(game='C:/Game/RA3_1.12.game',process_creation_filetime=456)
        objects=dict(source='win32_read_only_macro_channel_and_semaphore_v1',mapping_name='Local\\RA3StrategicCommanderV6_123',
            semaphore_name='Local\\RA3MacroPolicyLease_123',mapping_status='absent',semaphore_status='absent',
            mapping_open_error=2,semaphore_open_error=2,native_writes=0,acquire_or_wait_calls=0)
        proof=dict(kind=KIND,schema_version=1,run_id='run',binding=binding.public(),actual_OS_before=dict(pid=123,process_creation_filetime=456),
            actual_OS_after=dict(pid=123,process_creation_filetime=456),policy_modules_before=[],policy_modules_after=[],
            no_control_acquired=True,manager_restoration_claimed=False,mission_effect_verified=False,
            image_before=str(Path(session['game']).resolve()),image_after=str(Path(session['game']).resolve()),image_sha256='a'*64,
            started_monotonic_ns=1,ended_monotonic_ns=10,objects_before=objects,objects_after=copy.deepcopy(objects))
        self.assertTrue(verified_capture(proof,session,binding,'run'))
        for side in ('objects_before','objects_after'):
            wrong=copy.deepcopy(proof);wrong[side]['mapping_name']='Local\\RA3StrategicCommanderV5_123'
            self.assertFalse(verified_capture(wrong,session,binding,'run'))
        proof['policy_modules_after']=['manager_native.dll']
        self.assertFalse(verified_capture(proof,session,binding,'run'))


if __name__=='__main__':unittest.main()
