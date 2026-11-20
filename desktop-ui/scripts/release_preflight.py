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

    native = 'native-ai/strategic-portable-runtime-v7/'
    host = source(native + 'host.cpp')
    if re.search(r'[A-Za-z]:\\\\', host):
        block('native_game_path_machine_bound', native + 'host.cpp',
              'The Native helper embeds an absolute developer game image path.')
    builder = source(native + 'build.py')
    if all(token in builder for token in ('SOURCE_PINS', 'str(ROOT', 'JOURNAL_ROOT', 'DEPLOYMENT_ROOT')) or (
            'JOURNAL_ROOT' in builder and "ROOT/'reports" in builder):
        block('native_profile_machine_bound', native + 'build.py',
              'Compiled input locks, journal and deployment roots require a new portable Native candidate.')
    sdk = source(native + 'client.py')
    if "ROOT/'reports'" in sdk or "ROOT/'reports/" in sdk:
        block('native_sdk_repository_writes', native + 'client.py',
              'The SDK and durable return journal require repository reports paths.')
    # A public release still needs accepted natural games with the one native
    # runtime; that is a separate milestone, never a user-supplied pass bit.
    block('portable_native_contract_pending', 'integration/host_runtime/native_transport.py',
          'No portable strategic runtime has been accepted for public release yet.')
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
            payload = {'native/strategic7/StrategicCommanderV7.dll', 'native/strategic7/manager_host.exe',
                       'native/strategic7/build-manifest.json'} <= files.keys()
            if payload:
                report['blockers'].append(dict(code='native_candidate_not_accepted', path='runtime/native/strategic7',
                                              detail='A native trial payload does not establish product acceptance '
                                                     'or accepted natural games.'))
            elif not {'StrategicCommanderV7.dll', 'manager_host.exe'} <= natives:
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


def coordinated_beta_version(tauri, package, cargo):
    """Require one numbered, SemVer-valid beta across the installer and apps."""
    versions = (tauri['version'], package['version'], cargo['package']['version'])
    if any(not isinstance(version, str) for version in versions):
        raise ValueError('beta_version_mismatch')
    if len(set(versions)) != 1 or not re.fullmatch(r'0\.1\.(?:0|[1-9][0-9]*)-beta\.(?:0|[1-9][0-9]*)', versions[0]):
        raise ValueError('beta_version_mismatch')
    return versions[0]


def candidate_preflight(runtime,repo=REPO):
    """Build admission for a frozen installer under test; never public upload."""
    report=dict(schema_version=1,kind='windows_beta_installer_candidate_preflight',ready=False,
                public_release_ready=False,game_access=False,model_requests=0,blockers=[])
    try:
        report['runtime']=verify_inventory(runtime)
        # Import only reviewed repository tools, not arbitrary package modules.
        sys.path.insert(0,str(Path(repo)/'integration'))
        from host_runtime.native_runtime import verify_runtime
        verify_runtime(Path(runtime),report['runtime']['manifest_sha256'])
        stage=read_json(Path(runtime)/'release-stage.json')
        trial=stage.get('kind')=='portable_native7_field_trial_candidate'
        if not trial or stage.get('public_release_ready') is not False:
            raise ValueError('beta_trial_marker_required')
        tauri=read_json(Path(repo)/'desktop-ui/src-tauri/tauri.conf.json')
        package=read_json(Path(repo)/'desktop-ui/package.json')
        cargo=tomllib.loads((Path(repo)/'desktop-ui/src-tauri/Cargo.toml').read_text(encoding='utf-8'))
        coordinated_beta_version(tauri, package, cargo)
        if not tauri['bundle']['active'] or tauri['bundle']['targets']!=['nsis']:
            raise ValueError('beta_installer_required')
        sources=read_json(Path(runtime)/'application-sources.json')['files']
        if any(digest(Path(repo)/name)!=pin for name,pin in sources.items()):
            raise ValueError('candidate_sources_changed')
        required={'integration/host_runtime/beta_setup.py','integration/host_runtime/native_runtime.py'}
        if not required<=sources.keys():raise ValueError('beta_first_use_source_missing')
        report['ready']=True
    except (OSError,ValueError,KeyError,TypeError) as error:
        report['blockers'].append(dict(code='beta_candidate_invalid',detail=str(error) if re.fullmatch('[a-z0-9_]{1,80}',str(error)) else type(error).__name__))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--candidate',action='store_true')
    args = parser.parse_args()
    report = candidate_preflight(args.runtime) if args.candidate else preflight(runtime=args.runtime)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(encoded)
    print(encoded, end='')
    sys.exit(0 if report['ready'] else 2)
