"""Build an explicit, isolated companion snapshot. Never collect user data."""
from __future__ import annotations
import argparse
import compileall
import hashlib
import json
from pathlib import Path
import shutil
import sys
import py_compile

REPO = Path(__file__).resolve().parents[2]
SOURCES = ('integration', 'strategy', 'production', 'native-ai', 'tactical', 'visibility', 'agent_runtime/src')
BINARIES = ('production/bin/observe_build.exe', 'production/bin/NativeProductionObserver.dll',
            'production/bin/run_flak.exe', 'production/bin/FlakOneShot.dll',
            'production/persistent/bin-v2/persistent_host.exe', 'production/persistent/bin-v2/ProductionPersistent.dll')
RESOURCES = ('probe.py', 'production/persistent/capability-evidence.json', 'reference/Ra3-Copilot/ra3-copilot/src/battle_catalog.h')


def copy_native_runtime(destination):
    """Keep the independently rechecked native build with the companion.

    Build inputs are inert verifier resources. No report-selected path or user
    acceptance data is collected. A concurrent native rebuild aborts packaging.
    """
    source = REPO / 'tactical/runtime'
    raw = (source / 'bin/build-manifest.json').read_bytes()
    manifest = json.loads(raw)
    if manifest.get('protocol') != 'tactical_runtime_v1':raise ValueError('runtime_manifest_invalid')
    outputs = {row['file'] for row in manifest['outputs']}
    if outputs != {'TacticoreRuntime1.dll', 'runtime_host.exe', 'atomic_publish.dll'}:
        raise ValueError('runtime_manifest_invalid')
    for group, prefix in (('inputs', Path()), ('outputs', Path('bin'))):
        seen = set()
        for row in manifest[group]:
            name = row['file']
            if not isinstance(name,str) or Path(name).name != name or name in seen or '/' in name or '\\' in name or ':' in name:
                raise ValueError('runtime_manifest_path_invalid')
            seen.add(name)
            path = source / prefix / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('runtime_build_changed_during_package')
            target = destination / 'app/tactical/runtime' / prefix / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('runtime_build_changed_during_package')
    if (source / 'bin/build-manifest.json').read_bytes() != raw:
        raise ValueError('runtime_build_changed_during_package')
    target = destination / 'app/tactical/runtime/bin/build-manifest.json'
    target.write_bytes(raw)


def copy_tree(source, target, predicate):
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('source_symlink_rejected')
        if path.is_file() and predicate(path.relative_to(source)):
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def package(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('output_must_be_new')
    if destination == REPO or REPO.is_relative_to(destination):
        raise ValueError('unsafe_output')
    destination.mkdir(parents=True)
    base = Path(sys.base_prefix)
    python = destination / 'python'
    python.mkdir()
    for name in ('python.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        shutil.copy2(base / name, python / name)
    copy_tree(base / 'DLLs', python / 'DLLs', lambda p: p.suffix.lower() in ('.pyd', '.dll'))
    copy_tree(base / 'Lib', python / 'Lib', lambda p: p.parts[0] not in ('site-packages', 'test', 'idlelib', 'tkinter', 'ensurepip', '__pycache__') and '__pycache__' not in p.parts and p.suffix.lower() in ('.py', '.json', '.txt', '.pem', '.crt'))
    copy_tree(Path(sys.prefix) / 'Lib/site-packages', python / 'Lib/site-packages', lambda p: p.parts[0] not in ('pip', 'pip-25.0.1.dist-info') and '__pycache__' not in p.parts and p.suffix.lower() not in ('.pyc', '.pth'))
    for source in SOURCES:
        copy_tree(REPO / source, destination / 'app' / source, lambda p: p.suffix == '.py' and not p.name.startswith('test_') and '__pycache__' not in p.parts)
    for source in BINARIES + RESOURCES:
        target = destination / 'app' / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / source, target)
    copy_native_runtime(destination)
    # Preserve the original meaning of historical absolute executor pins while
    # all actual code/binary reads remain under this manifest-bound companion.
    (destination/'app/companion-layout.json').write_text(json.dumps(dict(schema_version=1,source_root=str(REPO)),sort_keys=True)+'\n',encoding='utf-8')
    # _pth disables environment/cwd/user-site imports and ignores site .pth files.
    # No import-site line is present. Every application path is fixed at build time.
    imports = ['Lib', 'DLLs', 'Lib/site-packages', '../app'] + ['../app/' + p for p in SOURCES]
    (python / 'python312._pth').write_text('\n'.join(imports) + '\n', encoding='utf-8')
    # Host grandchildren retain this fixed interpreter layout. Checked-hash pycs
    # prevent new cache files even when legacy child entrypoints omit -B.
    if not compileall.compile_dir(str(destination), quiet=2, force=True, stripdir=str(destination), prependdir='runtime', invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH):
        raise ValueError('companion_compile_failed')
    files = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(destination.rglob('*')) if p.is_file()}
    manifest = dict(schema_version=1, python='python/python.exe', working_directory='app/integration', files=files)
    raw = (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    (destination / 'manifest.json').write_bytes(raw)
    return dict(files=len(files),bytes=sum((destination / p).stat().st_size for p in files),manifest_sha256=hashlib.sha256(raw).hexdigest(),credentials_collected=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(package(parser.parse_args().output)))
