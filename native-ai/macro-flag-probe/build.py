"""Compile a fresh x86 diagnostic flag ABI probe, without loading it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['diagnostic_abi', 'scout_state','build_airfield'], default='diagnostic_abi')
    parser.add_argument('--epoch', type=int)
    args = parser.parse_args()
    if args.epoch is not None and (args.mode=='diagnostic_abi' or not 1<=args.epoch<=999):
        raise ValueError('epoch_requires_macro_mode_and_1_to_999')
    if args.mode=='build_airfield' and args.epoch is None:
        raise ValueError('airfield_requires_compiled_epoch')
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(HERE / 'bin'):
        raise ValueError('fresh_probe_bin_directory_required')
    compiler = ROOT / 'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe'
    out.mkdir(parents=True)
    manifest = dict(sources={p.name: digest(p) for p in [HERE/'shared.h', HERE/'native.cpp', HERE/'host.cpp', Path(__file__)]},
        compiler_sha256=digest(compiler), architecture='x86', native_game_calls=0,
        native_code_patches=0, diagnostic_flag_only=args.mode=='diagnostic_abi', mode=args.mode, field_verified=False,
        capability_granted=False, artifacts={})
    library = 'MacroScoutState.dll' if args.mode=='scout_state' else 'MacroFlagABI.dll'
    define = ['-DMACRO_SCOUT_STATE'] if args.mode=='scout_state' else []
    if args.epoch is not None:
        library=f'MacroAirfieldV{args.epoch}.dll' if args.mode=='build_airfield' else f'MacroScoutStateV{args.epoch}.dll'
        define.append(f'-DPROBE_EPOCH={args.epoch}')
    if args.mode=='build_airfield':define.append('-DMACRO_BUILD_AIRFIELD')
    manifest['epoch']=args.epoch
    for source, binary, extra in [('native.cpp', library, ['-shared', '-Wl,--kill-at']),
                                   ('host.cpp', 'macro_flag_host.exe', [])]:
        with (out/(source+'.log')).open('w', encoding='utf-8') as log:
            subprocess.run([str(compiler), '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-D_WIN32_WINNT=0x0601',
                '-static-libgcc', '-static-libstdc++', *define, *extra, str(HERE/source), '-o', str(out/binary), '-luser32'],
                stdout=log, stderr=subprocess.STDOUT, check=True)
        manifest['artifacts'][binary] = digest(out/binary)
    manifest['layout'] = json.loads(subprocess.check_output([str(out/'macro_flag_host.exe'), '--layout'], text=True))
    (out/'build-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(out), **manifest)))


if __name__ == '__main__':
    main()
