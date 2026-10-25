"""Actual frozen native artifacts and Python helper pins; no mocked source hash."""
import copy
import importlib.util
from pathlib import Path
import unittest

H=Path(__file__).resolve().parent
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
w=load('mf6_source_wrapper_test',H/'lease.py')
q=load('mf6_source_qualifier_test',H/'formation_mission_qualification.py')


class SourceBundle(unittest.TestCase):
    def fixture(self):
        files=dict(native_binary_sha256=H/'bin/TacticalMissionFormation6.dll',native_host_sha256=H/'bin/tactical_host.exe',native_source_sha256=H/'lease.cpp',native_shared_sha256=H/'shared.h',wrapper_sha256=H/'lease.py',native_revision_sha256=H/'revision.json',native_layout_sha256=H/'native_layout.py',mission_contract_sha256=H/'mission_contract.py')
        result={k:w.sha(p) for k,p in files.items()};result.update(native_includes_sha256={p.name:w.sha(p) for p in H.glob('*.cpp.inc')},supplemental_sources=w.supplemental())
        return result

    def test_actual_compiled_revision_report_and_all_helpers_agree(self):
        report=self.fixture()
        self.assertTrue(q.source_pins(report))
        self.assertTrue(w.frozen_sources_match(report))
        self.assertTrue(all(report['supplemental_sources'].get(p.name)==w.sha(p) for p in q.source_paths()))

    def test_missing_helper_or_bad_primary_never_uses_cached_true(self):
        baseline=self.fixture()
        for path in q.source_paths():
            report=copy.deepcopy(baseline);report['supplemental_sources'].pop(path.name,None);report['cached_source_verified']=True
            self.assertFalse(q.source_pins(report),path.name)
        for key in ('native_binary_sha256','native_host_sha256','native_source_sha256','native_shared_sha256','wrapper_sha256','native_revision_sha256','native_layout_sha256','mission_contract_sha256'):
            report=copy.deepcopy(baseline);report[key]='0'*64
            self.assertFalse(q.source_pins(report),key)

    def test_includes_are_exact_complete_and_cannot_mix_compiled_versions(self):
        baseline=self.fixture();self.assertTrue(baseline['native_includes_sha256'])
        for name in baseline['native_includes_sha256']:
            report=copy.deepcopy(baseline);report['native_includes_sha256'][name]='0'*64
            self.assertFalse(q.source_pins(report),name)
        report=copy.deepcopy(baseline);report['native_includes_sha256']['invented.cpp.inc']='0'*64
        self.assertFalse(q.source_pins(report))


if __name__=='__main__':unittest.main()
