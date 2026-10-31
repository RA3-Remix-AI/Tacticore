"""Build a fresh, non-attaching Native6 companion candidate offline.

The compiler and reviewed C++ are build-only inputs. The resulting verifier
uses relative companion pins; it never opens the developer archive/toolchain.
The default stays non-attaching. --field-candidate requires a freshly audited
qualification capsule and creates a bounded trial, never a product approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'integration'))
from host_runtime.native6_paths import plain_local
from host_runtime.native6_runtime_contract import (
    ACTIONS, ARTIFACTS, FLAGS, GAME_SHA, KIND, FIELD_KIND, PACKAGE_SHA, closure, profile,
    sha, verify_build, verify_inventory, locked_inputs,
)

COMPILER_SHA = '4f77a5812d96094f6ec565235ab9c2c6acfc7e77b4dc6cea07bf98f3985a7560'
REVIEWED_HEADER_SHA = '496258307efa49da49babfec511b84440ba268d432b30266feee7a735b76af09'
SOURCES = ('native.cpp', 'host.cpp', 'shared.h', 'flags.h', 'flag_api.h', 'portable_paths.h')


def verify(build):
    return verify_build(build)


def run(command, log):
    result = subprocess.run(list(map(str, command)), capture_output=True, timeout=120,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    log.write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError('native6_offline_tool_failed:' + log.name)
    return result.stdout


def seal(root):
    files = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*')) if p.is_file() and p != root / 'manifest.json'}
    value = dict(schema_version=1, python='python/python.exe', working_directory='app/integration', files=files)
    (root / 'manifest.json').write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')


def build(runtime, source_root, compiler, *, field_candidate=False):
    runtime, source_root, compiler = (plain_local(p) for p in (runtime, source_root, compiler))
    inventory = verify_inventory(runtime)
    if field_candidate:
        from host_runtime.native6_qualification import verify_capsule
        verify_capsule(runtime,inventory)
    output = runtime / 'native/strategic6'
    if output.exists() or compiler.name != 'i686-w64-mingw32-g++.exe' or sha(compiler) != COMPILER_SHA:
        raise ValueError('native6_fresh_output_and_reviewed_compiler_required')
    pins = locked_inputs(inventory)
    required = {'app/native-ai/strategic-portable-runtime-v6/client.py',
                'app/native-ai/strategic-portable-runtime-v6/build.py',
                'app/integration/host_runtime/native6_paths.py',
                'app/integration/host_runtime/native6_runtime_contract.py'}
    if not required <= pins.keys():
        raise ValueError('native6_sdk_must_be_staged_before_compilation')
    here = source_root / 'native-ai/strategic-portable-runtime-v6'
    header = source_root / 'native-ai/strategic_manager_gate_enable_candidate_v2.h'
    if sha(header) != REVIEWED_HEADER_SHA:
        raise ValueError('native6_reviewed_manager_api_changed')
    sources = {name: plain_local(here / name) for name in SOURCES}
    sources['strategic_manager_gate_enable_candidate_v2.h'] = header
    provenance = {name: sha(path) for name, path in sources.items()}
    provenance['toolchain/i686-w64-mingw32-g++.exe'] = COMPILER_SHA
    digest = closure(pins, provenance,field_candidate=field_candidate)
    output.mkdir(parents=True)
    for name, path in sources.items():
        shutil.copyfile(path, output / name)
        if sha(output / name) != provenance[name]:
            raise ValueError('native6_build_source_changed')
    (output / 'profile.h').write_text(profile(pins, provenance,field_candidate=field_candidate), encoding='ascii', newline='\n')
    for source, name, extra in (('native.cpp', ARTIFACTS[0], ['-shared', '-Wl,--kill-at']), ('host.cpp', ARTIFACTS[1], [])):
        run([compiler, '-std=c++17', '-D_WIN32_WINNT=0x0601', '-O2', '-Wall', '-Wextra', '-Werror',
             '-Wno-misleading-indentation', '-static-libgcc', '-static-libstdc++', output / source,
             '-o', output / name, *extra, '-ladvapi32', '-lshell32', '-lole32', '-luuid'], output / (name + '.compile.log'))
    helper = output / ARTIFACTS[1]
    layout = json.loads(run([helper, '--layout'], output / 'layout.log'))
    run([helper, '--check-export'], output / 'export.log')
    masks = json.loads(run([helper, '--all-masks'], output / 'masks.log'))
    expected = [mask for mask in range(1026) if not mask & ~1023 and (mask & 0x70).bit_count() <= 1 and (mask & 0x38f).bit_count() <= 1]
    if masks != expected:
        raise ValueError('native6_compiled_masks_changed')
    compiled = json.loads(run([helper, '--profile'], output / 'profile.log'))
    if compiled != dict(protocol_version=6, field_candidate=field_candidate, source_closure_sha256=digest, package_sha256=PACKAGE_SHA, game_sha256=GAME_SHA):
        raise ValueError('native6_compiled_profile_mismatch')
    if any(sha(path) != provenance[name] for name, path in sources.items()) or sha(compiler) != COMPILER_SHA:
        raise ValueError('native6_build_inputs_changed')
    if any(sha(runtime / name) != pin for name, pin in pins.items()):
        raise ValueError('native6_runtime_code_changed_during_build')
    value = dict(schema_version=1, kind=FIELD_KIND if field_candidate else KIND, protocol_version=6, compile_only=not field_candidate, admission_ready=field_candidate,
                 product_capability_granted=False, formal_games=0, game_sha256=GAME_SHA, package_sha256=PACKAGE_SHA,
                 actions=list(ACTIONS), flags=list(FLAGS), input_pins=pins, build_source_pins=provenance,
                 source_closure_sha256=digest, artifacts={name: sha(output / name) for name in ARTIFACTS}, layout=layout)
    (output / 'build-manifest.json').write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')
    # A distinct stage marker keeps the existing Rust release guard closed.
    (runtime / 'release-stage.json').write_text(json.dumps(dict(schema_version=1, kind='portable_native6_field_trial_candidate' if field_candidate else 'portable_native6_offline_candidate',
        native_transport_included=True, game_qualified=False, public_release_ready=False), sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    seal(runtime)
    verify(output)
    return dict(schema_version=1, kind=value['kind'], source_closure_sha256=digest, runtime_manifest_sha256=sha(runtime / 'manifest.json'),
                runtime_code_pins=len(pins), layout=layout, native_attach_permitted=field_candidate, game_access=False,
                model_requests=0, formal_games=0, public_release_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--field-candidate',action='store_true',help='Build a separately frozen trial binary; requires verified visibility data and native-launcher trust. Never grants product acceptance.')
    args = parser.parse_args()
    print(json.dumps(build(args.runtime, args.source_root, args.compiler,field_candidate=args.field_candidate)))
