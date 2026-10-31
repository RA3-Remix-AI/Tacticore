"""Build-time CPython staging. No configuration, game files or Native grant.

Only distributions in the exact version lock are collected. Their installed
RECORD hashes are checked before and after copying; arbitrary site-packages,
editable packages, scripts and .pth import hooks are never collected.
"""
from __future__ import annotations

import base64
import compileall
import csv
import hashlib
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import py_compile
import re
import shutil
import subprocess
import sys
import zipfile

APPLICATION_SOURCES = ('integration', 'strategy', 'production', 'native-ai', 'tactical', 'visibility', 'agent_runtime/src')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            result.update(block)
    return result.hexdigest()


def plain(path):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or getattr(ancestor.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('runtime_source_reparse_rejected')
    return path


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def read_lock(path):
    result = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)', line)
        if not match or normalize(match[1]) in result:
            raise ValueError('runtime_exact_dependency_lock_required')
        result[normalize(match[1])] = match[2]
    if not result:
        raise ValueError('runtime_exact_dependency_lock_required')
    return result


def _record_name(name):
    name = str(name)
    if '\\' in name or ':' in name or name.startswith('/'):
        raise ValueError('runtime_dependency_record_path_invalid')
    parts = name.split('/')
    # Windows wheel entry-point launchers are build-environment executables,
    # not part of the embedded library. No other parent traversal is allowed.
    if len(parts) == 4 and parts[:3] == ['..', '..', 'Scripts'] and parts[3] not in ('', '.', '..'):
        return None
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('runtime_dependency_record_path_invalid')
    if '__pycache__' in parts or name.endswith(('.pyc', '.pyo')):
        return None
    if name.endswith('.pth'):
        raise ValueError('runtime_dependency_import_hook_rejected')
    if any(part.endswith('.dist-info') for part in parts):
        if parts[-1] in ('RECORD', 'INSTALLER', 'REQUESTED', 'direct_url.json'):
            return None
    return PurePosixPath(name)


def copy_locked_dependencies(lock, destination, *, distributions=None):
    required = read_lock(lock)
    installed = {}
    for distribution in metadata.distributions() if distributions is None else distributions:
        name = normalize(distribution.metadata['Name'])
        if name in required:
            if name in installed:
                raise ValueError('runtime_duplicate_distribution')
            installed[name] = distribution
    if set(installed) != set(required):
        raise ValueError('runtime_locked_dependency_missing')
    destination = Path(destination)
    inventory, owners, notices = [], {}, []
    for name, version in sorted(required.items()):
        distribution = installed[name]
        record_text = distribution.read_text('RECORD')
        if distribution.version != version or not record_text:
            raise ValueError('runtime_locked_dependency_version_or_record_mismatch')
        root = plain(distribution.locate_file(''))
        files, licenses, recorded = {}, [], set()
        # Distribution.files silently filters missing entries in some Python
        # versions. Read RECORD itself so missing resources fail packaging.
        for row in csv.reader(io.StringIO(record_text, newline='')):
            if len(row) != 3 or row[0].casefold() in recorded:
                raise ValueError('runtime_dependency_record_invalid')
            recorded.add(row[0].casefold())
            relative = _record_name(row[0])
            if relative is None:
                continue
            relative = relative.as_posix()
            # Every runtime file must have a strong installed wheel RECORD pin.
            if not re.fullmatch(r'sha256=[A-Za-z0-9_-]{43}', row[1]) or not re.fullmatch(r'0|[1-9][0-9]*', row[2]):
                raise ValueError('runtime_dependency_record_sha256_required')
            source = plain(distribution.locate_file(row[0]))
            if not source.is_file() or not source.is_relative_to(root):
                raise ValueError('runtime_dependency_record_path_invalid')
            actual = digest(source)
            encoded = base64.urlsafe_b64encode(bytes.fromhex(actual)).rstrip(b'=').decode('ascii')
            if encoded != row[1][len('sha256='):] or source.stat().st_size != int(row[2]):
                raise ValueError('runtime_dependency_record_changed')
            if relative in owners or (destination / relative).exists():
                raise ValueError('runtime_dependency_file_collision')
            owners[relative] = name
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if digest(target) != actual or digest(source) != actual:
                raise ValueError('runtime_dependency_changed_during_copy')
            files[relative] = actual
            if re.search(r'(^|/)(licen[cs]e[^/]*|copying[^/]*|notice[^/]*)$', relative, re.I):
                licenses.append(relative)
        if not files:
            raise ValueError('runtime_dependency_empty_record')
        inventory.append(dict(name=name, version=version, files=files, licenses=licenses))
        notices.append(dict(name=name, version=version,
                            declared_license=distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or '',
                            license_files=licenses, redistribution_review='pending'))
    return inventory, notices


def copy_filtered(source, destination, predicate):
    source = plain(source)
    if not source.is_dir():
        raise ValueError('runtime_source_directory_required')
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if not predicate(relative):
            continue
        plain(path)
        if path.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            if digest(path) != digest(target):
                raise ValueError('runtime_source_changed_during_copy')


def copy_application(repo, destination):
    repo, destination = Path(repo), Path(destination)
    # Build from the reviewed Git inventory, never a recursive collection of
    # local Python files (which could include a user's scratch credentials).
    names = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z', '--', *APPLICATION_SOURCES,
        'probe.py','acceptance/capture_macro_before_attach_v5.py']).decode('utf-8').split('\0')
    files = {}
    for name in sorted(filter(None, names)):
        relative = PurePosixPath(name)
        if relative.suffix != '.py' or relative.name.startswith('test_') or any(part in ('__pycache__', 'tests', 'reports', 'runs', '.venv') for part in relative.parts):
            continue
        if name.startswith('/') or any(part in ('', '.', '..') for part in name.split('/')) or '\\' in name or ':' in name:
            raise ValueError('runtime_application_path_invalid')
        source = plain(repo / name)
        before = digest(source)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != before:
            raise ValueError('runtime_source_changed_during_copy')
        files[name] = before
    required = {'probe.py', 'integration/host_runtime/bridge_service.py', 'strategy/model_backend.py'}
    if not required <= files.keys():
        raise ValueError('runtime_application_entrypoint_missing')
    if any(digest(plain(repo / name)) != pin for name, pin in files.items()):
        raise ValueError('runtime_source_changed_during_copy')
    return dict(tracked_python_sources_only=True, files=files)


def copy_python(destination, lock):
    if os.name != 'nt' or sys.version_info[:2] != (3, 12) or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('runtime_windows_x64_cpython312_required')
    destination = Path(destination)
    if destination.exists():
        raise ValueError('runtime_python_output_must_be_new')
    destination.mkdir(parents=True)
    lock_pin = digest(plain(lock))
    base = plain(sys.base_prefix)
    interpreter = {}
    for name in ('python.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        source = plain(base / name)
        before = digest(source)
        shutil.copyfile(source, destination / name)
        if digest(source) != before or digest(destination / name) != before:
            raise ValueError('runtime_interpreter_changed_during_copy')
        interpreter[name] = before
    copy_filtered(base / 'DLLs', destination / 'DLLs', lambda p: p.suffix.lower() in ('.pyd', '.dll'))
    excluded = {'site-packages', 'test', 'idlelib', 'tkinter', 'ensurepip', '__pycache__'}
    copy_filtered(base / 'Lib', destination / 'Lib', lambda p: p.parts[0] not in excluded and '__pycache__' not in p.parts and p.suffix.lower() in ('.py', '.json', '.txt', '.pem', '.crt'))
    dependencies, notices = copy_locked_dependencies(lock, destination / 'Lib/site-packages')
    if digest(lock) != lock_pin:
        raise ValueError('runtime_dependency_lock_changed_during_copy')
    return dict(implementation='CPython', version=platform.python_version(), architecture='x64',
                interpreter_files=interpreter, lock_sha256=lock_pin, distributions=dependencies), notices


def seal_stage(destination):
    destination = Path(destination)
    if not compileall.compile_dir(str(destination), quiet=2, force=True, stripdir=str(destination), prependdir='runtime',
                                  invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH):
        raise ValueError('runtime_compile_failed')
    compact_dependencies(destination)
    files = {p.relative_to(destination).as_posix(): digest(p) for p in sorted(destination.rglob('*')) if p.is_file()}
    manifest = dict(schema_version=1, python='python/python.exe', working_directory='app/integration', files=files)
    raw = (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    (destination / 'manifest.json').write_bytes(raw)
    return dict(files=len(files), bytes=sum((destination / name).stat().st_size for name in files),
                manifest_sha256=hashlib.sha256(raw).hexdigest())


def compact_dependencies(destination):
    """One immutable container for pure dependencies; retain native/file users.

    Preserve all source AND checked caches, including stdlib, as lockable
    executable inputs. No increased Native handle bound or cache-read bypass.
    """
    destination=Path(destination);site=destination/'python/Lib/site-packages'
    archive=destination/'python/Lib/site-packages.zip'
    if archive.exists():raise ValueError('runtime_dependency_container_already_exists')
    keep=set()
    for path in site.rglob('*'):
        if not path.is_file():continue
        plain(path)
        if path.suffix.lower() in ('.pyd','.dll') or path.suffix=='.py' and '__file__' in path.read_text(encoding='utf-8',errors='strict'):
            keep.add(path.relative_to(site).parts[0])
    members={};directories=set();originals=[]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as container:
        for path in sorted(site.rglob('*')):
            if not path.is_file() or path.relative_to(site).parts[0] in keep:continue
            plain(path);name=path.relative_to(site).as_posix();pin=digest(path);raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('runtime_dependency_changed_during_container')
            parent=Path(name).parent
            for directory in reversed(parent.parents):
                if str(directory)!='.':directories.add(directory.as_posix()+'/')
            if str(parent)!='.':directories.add(parent.as_posix()+'/')
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            container.writestr(info,raw);members[name]=pin;originals.append(path)
        for name in sorted(directories):container.writestr(zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)),b'')
    with zipfile.ZipFile(archive) as container:
        if len(container.namelist())!=len(set(container.namelist())):raise ValueError('runtime_dependency_duplicate_container_entry')
        for name,pin in members.items():
            if hashlib.sha256(container.read(name)).hexdigest()!=pin:raise ValueError('runtime_dependency_container_changed')
    for path in originals:
        if not path.is_relative_to(site) or digest(path)!=members[path.relative_to(site).as_posix()]:
            raise ValueError('runtime_dependency_changed_during_container')
        path.unlink()  # only exact, verified files in this invocation's fresh stage
    for path in sorted((p for p in site.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        if not any(path.iterdir()):path.rmdir()
    pth=destination/'python/python312._pth'
    lines=pth.read_text(encoding='utf-8').splitlines()
    if lines.count('Lib/site-packages')!=1:raise ValueError('runtime_fixed_dependency_import_path_required')
    lines.insert(lines.index('Lib/site-packages'),'Lib/site-packages.zip')
    pth.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    metadata=dict(schema_version=1,kind='verified_pure_python_dependency_container',archive='python/Lib/site-packages.zip',
                  archive_sha256=digest(archive),members=members,filesystem_groups=sorted(keep),
                  wheel_download_hash_lock=False,redistribution_review='pending')
    (destination/'dependency-container.json').write_text(json.dumps(metadata,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    notice=destination/'third-party-inventory.json'
    if notice.is_file():
        inventory=json.loads(notice.read_text(encoding='utf-8'))
        for row in inventory['dependencies']:
            row['license_locations']=[dict(kind='zip_member',archive=metadata['archive'],member=name) if name in members
                else dict(kind='file',path='python/Lib/site-packages/'+name) for name in row['license_files']]
        notice.write_text(json.dumps(inventory,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
