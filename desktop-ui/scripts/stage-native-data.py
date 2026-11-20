"""Copy the native runtime's data files from an earlier runtime and reseal.

The runtime needs three data files that belong to the mod package, not to the
code: the commander registry, the compiled package report and the lawful-view
data (template safety and native signatures). They do not change when Python
or C++ code changes, so a new runtime takes them from the previous accepted
runtime of the same package. Run after stage-python-runtime.py and before
native-ai/strategic-portable-runtime-v7/build.py (which reseals again).
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'integration'))
from host_runtime.native_runtime import PACKAGE_REPORT, REGISTRY, VISIBILITY_DATA  # noqa: E402
from host_runtime.native_runtime_contract import PACKAGE_SHA, canonical, read, sha, verify_inventory  # noqa: E402

DATA = (REGISTRY, PACKAGE_REPORT, VISIBILITY_DATA)


def check(source):
    """The three files describe exactly this runtime's mod package."""
    registry, package, visibility = (read(source / name) for name in DATA)
    if registry.get('package_sha256') != PACKAGE_SHA or registry.get('compiled_ids_verified') is not True:
        raise ValueError('native_data_registry_package_mismatch')
    if package.get('big_sha256') != PACKAGE_SHA or package.get('compiled') is not True:
        raise ValueError('native_data_package_report_mismatch')
    if visibility.get('package_sha256') != PACKAGE_SHA or not visibility.get('expected_signatures'):
        raise ValueError('native_data_visibility_mismatch')
    if visibility.get('safety', {}).get('package_sha256') != PACKAGE_SHA:
        raise ValueError('native_data_visibility_mismatch')


def stage(runtime, source):
    runtime, source = Path(runtime), Path(source)
    verify_inventory(runtime)
    check(source)
    for name in DATA:
        target = runtime / name
        if target.exists():
            raise ValueError('native_data_already_present')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        if sha(target) != sha(source / name):
            raise ValueError('native_data_copy_changed')
    files = {p.relative_to(runtime).as_posix(): sha(p) for p in sorted(runtime.rglob('*'))
             if p.is_file() and p != runtime / 'manifest.json'}
    value = dict(schema_version=1, python='python/python.exe', working_directory='app/integration', files=files)
    (runtime / 'manifest.json').write_text(canonical(value) + '\n', encoding='utf-8', newline='\n')
    verify_inventory(runtime)
    return dict(kind='native_data_staged', files=list(DATA), package_sha256=PACKAGE_SHA)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True, help='new staged runtime directory')
    parser.add_argument('--from-runtime', type=Path, required=True, help='earlier runtime of the same mod package')
    args = parser.parse_args()
    print(json.dumps(stage(args.runtime, args.from_runtime)))
