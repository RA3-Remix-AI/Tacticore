"""Read-only Windows beta preflight. A Python stage is never a release pass."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tomllib

from locked_python_runtime import digest, plain

REPO = Path(__file__).resolve().parents[2]
MAX_FILE = 256 * 1024 * 1024


def unique_object(pairs):
    value = {}
    for key, entry in pairs:
        if key in value:
            raise ValueError('runtime_duplicate_json_key')
        value[key] = entry
    return value


def read_json(path, maximum=4 * 1024 * 1024):
    path = plain(path)
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('runtime_manifest_unbounded')
    return json.loads(raw, object_pairs_hook=unique_object)


def relative(name):
    return (type(name) is str and bool(name) and '\\' not in name and ':' not in name
            and not name.startswith('/') and all(part not in ('', '.', '..') for part in name.split('/')))


def verify_inventory(root, expected=None):
    root = plain(root)
    manifest_path = root / 'manifest.json'
    manifest = read_json(manifest_path)
    pin = digest(manifest_path)
    if expected is not None and pin != expected:
        raise ValueError('runtime_manifest_pin_mismatch')
    if (type(manifest) is not dict or set(manifest) != {'schema_version', 'python', 'working_directory', 'files'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
            or manifest['python'] != 'python/python.exe' or manifest['working_directory'] != 'app/integration'
            or type(manifest['files']) is not dict or not 1 <= len(manifest['files']) <= 100000):
        raise ValueError('runtime_manifest_invalid')
    files = manifest['files']
    required = {'python/python.exe', 'app/integration/host_runtime/bridge_service.py'}
    if not required <= files.keys():
        raise ValueError('runtime_manifest_entrypoint_missing')
    folded = set()
    for name, sha in files.items():
        if (not relative(name) or name.casefold() == 'manifest.json' or type(sha) is not str
                or re.fullmatch('[0-9a-f]{64}', sha) is None or name.casefold() in folded):
            raise ValueError('runtime_manifest_path_or_digest_invalid')
        folded.add(name.casefold())
    observed = set()
    for index, path in enumerate(root.rglob('*')):
        if index >= 150000:
            raise ValueError('runtime_inventory_unbounded')
        plain(path)
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if name == 'manifest.json':
            continue
        if path.stat().st_size > MAX_FILE or name not in files or digest(path) != files[name]:
            raise ValueError('runtime_inventory_changed')
        observed.add(name)
    if observed != files.keys():
        raise ValueError('runtime_inventory_incomplete')
    return dict(manifest_sha256=pin, files=len(files))


def source_preflight(repo):
    repo = Path(repo)
    blockers, pins = [], {}

    def block(code, path, detail):
        blockers.append(dict(code=code, path=path, detail=detail))

    def source(name):
        try:
            path = plain(repo / name)
            text = path.read_text(encoding='utf-8')
            pins[name] = digest(path)
            return text
        except OSError:
            block('release_source_missing', name, 'Required release input is unavailable.')
            return ''

    host = source('native-ai/strategic-unified-runtime-v5/host.cpp')
    if re.search(r'[A-Za-z]:\\\\', host):
        block('native_game_path_machine_bound', 'native-ai/strategic-unified-runtime-v5/host.cpp',
              'The Native helper embeds an absolute developer game image path.')
    builder = source('native-ai/strategic-unified-runtime-v5/build.py')
    if all(token in builder for token in ('SOURCE_PINS', 'str(ROOT', 'JOURNAL_ROOT', 'DEPLOYMENT_ROOT')) or (
            'JOURNAL_ROOT' in builder and "ROOT/'reports" in builder):
        block('native_profile_machine_bound', 'native-ai/strategic-unified-runtime-v5/build.py',
              'Compiled input locks, journal and deployment roots require a new portable Native candidate.')
    sdk = source('native-ai/strategic-unified-runtime-v5/client.py')
    if "ROOT/'reports'" in sdk or "ROOT/'reports/" in sdk:
        block('native_sdk_repository_writes', 'native-ai/strategic-unified-runtime-v5/client.py',
              'The SDK and durable return journal require repository reports paths.')
    qualification = source('integration/host_runtime/strategic_unified_bundle_v5.py')
    if 'legacy_bundle' in qualification and 'source-pins.json' in qualification:
        block('qualification_developer_archive_required', 'integration/host_runtime/strategic_unified_bundle_v5.py',
              'Schema13 loads original research archives and developer source paths at runtime.')
    # Native5 is the only currently wired strategic transport. Removing strings
    # cannot qualify it: implementing and reviewing a new runtime contract is a
    # separate milestone, not a magic --allow flag or a user-supplied pass bit.
    block('portable_native_contract_pending', 'integration/host_runtime/strategic_unified_transport_v5.py',
          'No portable strategic runtime/qualification integration has been accepted yet.')
    try:
        tauri = json.loads(source('desktop-ui/src-tauri/tauri.conf.json'))
        package = json.loads(source('desktop-ui/package.json'))
        cargo = tomllib.loads(source('desktop-ui/src-tauri/Cargo.toml'))
        versions = (tauri['version'], package['version'], cargo['package']['version'])
        if len(set(versions)) != 1:
            block('release_versions_disagree', 'desktop-ui', 'Tauri, npm and Rust versions must agree.')
        if not re.fullmatch(r'0\.1\.\d+-beta(?:\.\d+)?', versions[0]):
            block('beta_version_pending', 'desktop-ui', 'The release candidate has no coordinated beta version yet.')
        if tauri.get('bundle', {}).get('active') is not True:
            block('windows_installer_disabled', 'desktop-ui/src-tauri/tauri.conf.json', 'The installer is not enabled yet.')
    except (KeyError, ValueError, TypeError):
        block('release_configuration_invalid', 'desktop-ui', 'Release configuration cannot be validated.')
    return dict(schema_version=1, kind='windows_beta_preflight', scope='source_readiness',
                ready=not blockers, blockers=blockers, source_sha256=pins,
                game_access=False, model_requests=0, historical_formal_games_reused=False)


def preflight(repo=REPO, runtime=None):
    report = source_preflight(repo)
    if runtime is None:
        report['blockers'].append(dict(code='release_runtime_missing', path='', detail='No complete frozen runtime supplied.'))
    else:
        try:
            report['runtime'] = verify_inventory(runtime)
            files = read_json(Path(runtime) / 'manifest.json')['files']
            natives = {PurePosixPath(name).name for name in files}
            native6 = {'native/strategic6/StrategicCommanderV6.dll', 'native/strategic6/manager_host.exe',
                       'native/strategic6/build-manifest.json'} <= files.keys()
            if native6:
                report['blockers'].append(dict(code='native6_offline_candidate_not_qualified', path='runtime/native/strategic6',
                                              detail='The Native6 offline candidate has no field/product grant or accepted natural games.'))
            elif not {'StrategicCommanderV5.dll', 'manager_host.exe'} <= natives:
                report['blockers'].append(dict(code='strategic_native_payload_missing', path='runtime',
                                              detail='The current strategic helper/DLL payload is missing.'))
            if 'release-stage.json' in files:
                stage = read_json(Path(runtime) / 'release-stage.json')
                if stage.get('kind') == 'locked_python_stage':
                    report['blockers'].append(dict(code='python_stage_not_game_release', path='runtime/release-stage.json',
                                                  detail='This artifact is an offline Python foundation only.'))
        except (OSError, ValueError, TypeError) as error:
            # No raw paths/environment/traceback in the public report.
            report['blockers'].append(dict(code='release_runtime_invalid', path='runtime', detail=type(error).__name__))
    report['ready'] = not report['blockers']
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = preflight(runtime=args.runtime)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(encoded)
    print(encoded, end='')
    sys.exit(0 if report['ready'] else 2)
