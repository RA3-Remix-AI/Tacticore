import base64
import csv
import hashlib
import importlib.metadata as metadata
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from locked_python_runtime import copy_application, copy_locked_dependencies, read_lock
from release_preflight import REPO, digest, preflight, verify_inventory


class ReleaseFoundationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='beta-release-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.site = self.root / 'site'
        self.site.mkdir()
        self.lock = self.root / 'requirements.lock'
        self.lock.write_text('sample-package==1.0\n', encoding='utf-8')

    def distribution(self, name='sample-package', version='1.0', extra=None):
        folder = name.replace('-', '_')
        info = self.site / (folder + '-' + version + '.dist-info')
        files = {folder + '/__init__.py': b'VALUE = 7\n',
                 info.name + '/METADATA': f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n'.encode(),
                 info.name + '/licenses/LICENSE': b'fixture license\n',
                 info.name + '/direct_url.json': b'{"url":"file:///private/build/tree"}'}
        files.update(extra or {})
        rows = []
        for relative, raw in files.items():
            path = self.site / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            pin = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
            rows.append([relative, 'sha256=' + pin, len(raw)])
        rows.append([info.name + '/RECORD', '', ''])
        output = io.StringIO(newline='')
        csv.writer(output).writerows(rows)
        (info / 'RECORD').write_text(output.getvalue(), encoding='utf-8', newline='')
        return metadata.PathDistribution(info)

    def inventory_fixture(self):
        root = self.root / 'runtime'
        for name, raw in {'python/python.exe': b'fixture interpreter',
                          'app/integration/host_runtime/bridge_service.py': b'# fixture',
                          'nested/manifest.json': b'not the top-level manifest'}.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        files = {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*') if p.is_file()}
        manifest = dict(schema_version=1, python='python/python.exe', working_directory='app/integration', files=files)
        (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return root, manifest

    def test_only_locked_distributions_are_copied_and_private_metadata_is_excluded(self):
        selected = self.distribution()
        unrelated = self.distribution('unrequested', extra={'unrequested.pth': b'import malicious'})
        target = self.root / 'out'
        inventory, notices = copy_locked_dependencies(self.lock, target, distributions=[selected, unrelated])
        self.assertEqual([(r['name'], r['version']) for r in inventory], [('sample-package', '1.0')])
        self.assertFalse((target / 'unrequested').exists())
        self.assertFalse(list(target.rglob('direct_url.json')))
        self.assertEqual(len(notices[0]['license_files']), 1)
        self.assertEqual(notices[0]['redistribution_review'], 'pending')

    def test_installed_wheel_record_detects_tampering(self):
        package = self.distribution()
        (self.site / 'sample_package/__init__.py').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError, 'record_changed'):
            copy_locked_dependencies(self.lock, self.root / 'out', distributions=[package])

    def test_locked_package_import_hooks_and_parent_escape_are_rejected(self):
        for index, extra in enumerate(({'sample.pth': b'import malicious'}, {'../escape.py': b'escape'})):
            package = self.distribution(extra=extra)
            with self.assertRaises(ValueError):
                copy_locked_dependencies(self.lock, self.root / f'out{index}', distributions=[package])

    def test_missing_recorded_resource_is_not_filtered_out_by_metadata_api(self):
        package = self.distribution(extra={'sample_package/required-resource.json': b'{}'})
        (self.site / 'sample_package/required-resource.json').unlink()
        with self.assertRaises((OSError, ValueError)):
            copy_locked_dependencies(self.lock, self.root / 'out', distributions=[package])

    def test_version_missing_and_duplicate_distribution_fail(self):
        package = self.distribution()
        for distributions in ([], [package, package], [self.distribution(version='2.0')]):
            with self.assertRaises(ValueError):
                copy_locked_dependencies(self.lock, self.root / 'out', distributions=distributions)

    def test_dependency_file_collision_is_not_silently_overwritten(self):
        self.lock.write_text('sample-package==1.0\nother==1.0\n', encoding='utf-8')
        first = self.distribution(extra={'shared.py': b'same'})
        second = self.distribution('other', extra={'shared.py': b'same'})
        with self.assertRaisesRegex(ValueError, 'collision'):
            copy_locked_dependencies(self.lock, self.root / 'out', distributions=[first, second])

    def test_lock_rejects_unpinned_and_duplicate_normalized_names(self):
        for text in ('sample-package>=1\n', 'sample-package==1.0\nSample_Package==1.0\n', '-e ../source\n'):
            self.lock.write_text(text, encoding='utf-8')
            with self.assertRaises(ValueError):
                read_lock(self.lock)

    def test_inventory_rejects_extra_code_changed_binary_and_missing_file(self):
        root, _ = self.inventory_fixture()
        original = verify_inventory(root)
        self.assertEqual(original['files'], 3)
        extra = root / 'python/injected.py'
        extra.write_bytes(b'import injected')
        with self.assertRaisesRegex(ValueError, 'changed'):
            verify_inventory(root)
        extra.unlink()
        binary = root / 'python/python.exe'
        binary.write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError, 'changed'):
            verify_inventory(root)
        binary.unlink()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            verify_inventory(root)

    def test_inventory_rejects_duplicate_json_paths_traversal_and_case_aliases(self):
        root, manifest = self.inventory_fixture()
        (root / 'manifest.json').write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            verify_inventory(root)
        for name in ('../escape.py', 'python/./x', 'python\\x', 'C:/x', 'PYTHON/PYTHON.EXE'):
            changed = dict(manifest, files=dict(manifest['files'], **{name: '0' * 64}))
            (root / 'manifest.json').write_text(json.dumps(changed), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'path_or_digest'):
                verify_inventory(root)

    def test_preflight_reports_actual_native5_relocation_blockers(self):
        report = preflight(REPO)
        codes = {r['code'] for r in report['blockers']}
        self.assertFalse(report['ready'])
        self.assertTrue({'native_game_path_machine_bound', 'native_profile_machine_bound',
                         'native_sdk_repository_writes', 'qualification_developer_archive_required',
                         'portable_native_contract_pending', 'release_runtime_missing'} <= codes)

    def test_complete_python_inventory_is_not_a_game_release(self):
        root, _ = self.inventory_fixture()
        report = preflight(REPO, root)
        self.assertFalse(report['ready'])
        self.assertIn('strategic_native_payload_missing', {r['code'] for r in report['blockers']})

    def test_legacy_packager_requires_explicit_research_opt_in_before_writing(self):
        spec = importlib.util.spec_from_file_location('legacy_packager', SCRIPTS / 'package-runtime.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = self.root / 'not-created'
        with self.assertRaisesRegex(ValueError, 'not_beta'):
            module.package(target)
        self.assertFalse(target.exists())

    def test_stage_refuses_output_inside_sources_or_with_parent_traversal(self):
        spec = importlib.util.spec_from_file_location('stage_packager', SCRIPTS / 'stage-python-runtime.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for target in (REPO / 'integration/no-beta-output', self.root / 'child/../runtime'):
            with self.assertRaisesRegex(ValueError, 'unsafe_output'):
                module.stage(target)
            self.assertFalse(target.exists())

    def test_application_collection_excludes_untracked_python_and_secret_files(self):
        repo = self.root / 'source'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        for name in ('probe.py', 'integration/host_runtime/bridge_service.py', 'strategy/model_backend.py'):
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'# reviewed source\n')
            subprocess.run(['git', '-C', str(repo), 'add', '--', name], check=True)
        (repo / 'strategy/local_credentials.py').write_bytes(b'TEST_SECRET = "must-not-collect"')
        (repo / 'strategy/secret.json').write_bytes(b'{"key":"must-not-collect"}')
        output = self.root / 'application'
        result = copy_application(repo, output)
        self.assertEqual(len(result['files']), 3)
        self.assertFalse((output / 'strategy/local_credentials.py').exists())
        self.assertFalse((output / 'strategy/secret.json').exists())


if __name__ == '__main__':
    unittest.main()
