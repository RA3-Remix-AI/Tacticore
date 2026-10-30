"""Pure file-proof cache tests: no registration, native process or model access."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from host_runtime.contracts import ContractError
from host_runtime import macro_bundle_cache as module
from host_runtime import macro_bundle


class FileScopeCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.proof=self.root/'proof';self.proof.write_bytes(b'original evidence')
        self.source=self.root/'trusted_source.py';self.source.write_text('original source')
        self.bundle=self.root/'bundle.json';self.value=dict(kind='artificial_file_scope',pins={str(self.proof):module.stable_file(self.proof)[0].sha256})
        self.save();self.calls=0
        self.scope=SimpleNamespace(package_sha256='a'*64,evidence={'nested':{'value':1}})
        self.cache=module.VerifiedFileScopeCache(capacity=2,source_paths=(self.source,))

    def save(self):self.bundle.write_text(json.dumps(self.value))
    def validate(self,path):
        self.calls+=1
        return json.loads(path.read_text()),self.scope
    def load(self):return self.cache.load(self.bundle,self.validate)
    def refused(self,call):
        with self.assertRaises(ContractError) as caught:call()
        self.assertEqual(caught.exception.code,'macro_bundle_not_qualified')

    def test_every_hit_rehashes_complete_pin_set_without_repeating_full_validator(self):
        original=module.stable_file;reads=[]
        def record(path,**kwargs):reads.append(Path(path));return original(path,**kwargs)
        with patch.object(module,'stable_file',side_effect=record):
            self.load();self.load();self.load()
        self.assertEqual(self.calls,1);self.assertEqual(reads.count(self.proof),3)
        self.assertGreaterEqual(reads.count(self.source),6)

    def test_returned_bundle_and_scope_nested_mutation_cannot_contaminate_later_caller(self):
        value,scope=self.load();value['pins'].clear();scope.evidence['nested']['value']=99
        next_value,next_scope=self.load()
        self.assertEqual(next_value,self.value);self.assertEqual(next_scope.evidence['nested']['value'],1)
        self.assertIsNot(next_scope,self.scope);self.assertIsNot(next_scope,scope);self.assertEqual(self.calls,1)

    def test_same_size_evidence_tamper_with_restored_mtime_rejected_without_fallback(self):
        self.load();before=self.proof.stat();self.proof.write_bytes(b'changed! evidence')
        self.assertEqual(self.proof.stat().st_size,before.st_size)
        os.utime(self.proof,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.refused(self.load);self.assertEqual(self.calls,1)

    def test_bundle_whitespace_and_changed_pin_membership_never_reuse_old_scope(self):
        original=self.bundle.read_bytes()
        self.load();self.bundle.write_bytes(original+b' ')
        self.refused(self.load);self.assertEqual(self.calls,1)
        for mode in ('remove','add','change'):
            self.bundle.write_bytes(original);self.cache.clear();self.load()
            changed=deepcopy(self.value)
            if mode=='remove':changed['pins'].clear()
            elif mode=='add':changed['pins'][str(self.source)]='a'*64
            else:changed['pins'][str(self.proof)]='f'*64
            self.bundle.write_text(json.dumps(changed));calls=self.calls
            self.refused(self.load);self.assertEqual(self.calls,calls)

    def test_source_guard_applies_to_cached_and_new_bundle_without_mtime_shortcut(self):
        self.load();before=self.source.stat();self.source.write_text('modified source')
        os.utime(self.source,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.refused(self.load);self.assertEqual(self.calls,1)
        self.bundle=self.root/'new.json';self.save();self.refused(self.load);self.assertEqual(self.calls,1)

    def test_replaced_file_identity_is_rejected_even_for_identical_bytes(self):
        self.load();before=self.proof.stat();replacement=self.root/'replacement'
        replacement.write_bytes(self.proof.read_bytes());replacement.replace(self.proof)
        os.utime(self.proof,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.refused(self.load);self.assertEqual(self.calls,1)

    def test_failure_or_partial_result_never_populates_cache(self):
        def fail(path):raise ContractError('incomplete_file_proof')
        self.refused(lambda:self.cache.load(self.bundle,fail));self.assertFalse(self.cache._entries)
        self.refused(lambda:self.cache.load(self.bundle,lambda path:({'pins':{}},self.scope)))
        self.assertFalse(self.cache._entries);self.load();self.assertEqual(self.calls,1)

    def test_evidence_changed_during_cold_verification_cannot_be_committed(self):
        def changed(path):
            value,scope=self.validate(path);self.proof.write_bytes(b'changed! evidence');return value,scope
        self.refused(lambda:self.cache.load(self.bundle,changed));self.assertFalse(self.cache._entries)

    def test_bundle_changed_while_hit_hashes_evidence_is_rejected(self):
        self.load();original=module.stable_file
        def changed(path,**kwargs):
            value=original(path,**kwargs)
            if Path(path)==self.proof:self.bundle.write_bytes(self.bundle.read_bytes()+b' ')
            return value
        with patch.object(module,'stable_file',side_effect=changed):self.refused(self.load)
        self.assertEqual(self.calls,1)

    def test_concurrent_first_load_runs_complete_validator_once_and_returns_distinct_copies(self):
        lock=threading.Lock()
        def slow(path):
            with lock:self.calls+=1
            time.sleep(.02)
            return json.loads(path.read_text()),self.scope
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.cache.load(self.bundle,slow),range(8)))
        self.assertEqual(self.calls,1);self.assertEqual(len({id(scope) for _,scope in results}),8)

    def test_lru_capacity_is_bounded_and_evicted_scope_requires_complete_revalidation(self):
        first=self.bundle
        for index in range(3):
            self.bundle=self.root/(str(index)+'.json');self.save();self.load()
        self.assertEqual(len(self.cache._entries),2);self.assertEqual(self.calls,3)
        self.bundle=self.root/'0.json';self.load();self.assertEqual(self.calls,4)
        self.bundle=first

    def test_session_package_is_checked_each_time_and_never_a_cache_key_or_cached_fact(self):
        with patch.object(macro_bundle,'_FILE_SCOPE_CACHE',self.cache),patch.object(macro_bundle,'_load_bundle_uncached',side_effect=self.validate):
            macro_bundle.load_bundle(self.bundle,{'mod_sha256':'a'*64})
            for wrong in ('b'*64,None):self.refused(lambda:macro_bundle.load_bundle(self.bundle,{'mod_sha256':wrong}))
            _,scope=macro_bundle.load_bundle(self.bundle,{'mod_sha256':'a'*64})
            self.assertEqual(scope.package_sha256,'a'*64);self.assertEqual(self.calls,1)

    def test_evidence_symlink_retarget_with_identical_bytes_changes_origin(self):
        target=self.root/'other';target.write_bytes(self.proof.read_bytes());alias=self.root/'alias'
        try:alias.symlink_to(self.proof)
        except OSError:self.skipTest('symlink unavailable')
        self.value['pins']={str(alias):module.stable_file(alias)[0].sha256};self.save();self.load()
        alias.unlink();alias.symlink_to(target)
        self.refused(self.load);self.assertEqual(self.calls,1)
