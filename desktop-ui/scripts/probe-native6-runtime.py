"""Probe a Native6 offline package, optionally copying to a fresh location."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'integration'))
from host_runtime.native6_paths import plain_local
from host_runtime.native6_runtime_contract import read, sha, verify_build, verify_inventory


def relocate(source, destination):
    source = plain_local(source)
    destination = plain_local(destination, existing=False)
    if destination.exists() or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('native6_fresh_separate_relocation_required')
    inventory = verify_inventory(source)
    pin = sha(source / 'manifest.json')
    destination.mkdir(parents=True)
    for name, digest in sorted(inventory['files'].items()):
        path = plain_local(source / name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if sha(path) != digest or sha(target) != digest:
            raise ValueError('native6_source_changed_during_relocation')
    shutil.copyfile(source / 'manifest.json', destination / 'manifest.json')
    verify_inventory(source, expected=pin)
    verify_inventory(destination, expected=pin)
    return destination


def probe(runtime, destination=None):
    runtime = plain_local(runtime)
    verify_build(runtime / 'native/strategic6')
    if destination is not None:
        runtime = relocate(runtime, destination)
    before = sha(runtime / 'manifest.json')
    with tempfile.TemporaryDirectory(prefix='native6-clean-cwd-') as temporary:
        temporary = Path(temporary)
        for name in ('host_runtime', 'build', 'observe_production'):
            (temporary / (name + '.py')).write_text("raise RuntimeError('untrusted cwd imported')\n", encoding='utf-8')
        environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH') if key in os.environ}
        environment.update(PYTHONHOME=str(temporary / 'missing-python'), PYTHONPATH=str(temporary),
                           LOCALAPPDATA=str(temporary / 'hostile-local'), APPDATA=str(temporary / 'hostile-roaming'),
                           TEMP=str(temporary), TMP=str(temporary), USERPROFILE=str(temporary), HOME=str(temporary))
        result = subprocess.run([str(runtime / 'python/python.exe'), '-I', '-S', '-B', '-m',
                                 'host_runtime.native6_offline_probe', '--runtime', str(runtime)],
                                cwd=temporary, env=environment, capture_output=True, timeout=120,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            # Save no raw environment or user credentials in a public error.
            raise ValueError('native6_isolated_probe_failed:' + result.stderr.decode('utf-8', errors='replace')[-2000:])
        report = json.loads(result.stdout)
    verify_inventory(runtime, expected=before)
    if report['runtime_manifest_sha256'] != before or report['game_access'] is not False or report['formal_games'] != 0:
        raise ValueError('native6_offline_probe_contract_changed')
    return dict(report, relocated=destination is not None, hostile_environment_and_cwd_ignored=True,
                user_provider_environment_not_inherited=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--relocate-to', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('native6_new_probe_output_required')
    report = probe(args.runtime, args.relocate_to)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report))
