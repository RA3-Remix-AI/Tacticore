"""Fresh x86 passive AI flag query observer build; no native game calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epoch', type=int, required=True)
    args=parser.parse_args(); out=args.output.resolve()
    if out.exists() or not out.is_relative_to(HERE/'bin') or not 1<=args.epoch<=999:
        raise ValueError('fresh_observer_bin_required')
    compiler=ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe'
    cc=ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-gcc.exe'
    mh=ROOT/'reference/Ra3-Copilot/ra3-copilot/third_party/minhook-1.3.3'
    out.mkdir(parents=True)
    sources=[HERE/'observer.cpp', Path(__file__), mh/'include/MinHook.h']
    objects=[]
    with (out/'compile.log').open('w',encoding='utf-8') as log:
        for file in ['buffer.c','hook.c','trampoline.c','hde/hde32.c']:
            source=mh/'src'/file; target=out/(source.stem+'.o'); sources.append(source); objects.append(str(target))
            subprocess.run([str(cc),'-O2','-Wall','-c',str(source),'-I',str(mh/'include'),'-o',str(target)],stdout=log,stderr=subprocess.STDOUT,check=True)
        base=[str(compiler),'-std=c++17','-O2','-Wall','-Wextra','-static-libgcc','-static-libstdc++','-DOBSERVER_EPOCH='+str(args.epoch)]
        subprocess.run(base+['-DFLAG_QUERY_DLL','-shared','-Wl,--kill-at',str(HERE/'observer.cpp'),'-I',str(mh/'include'),*objects,'-o',str(out/('MacroFlagQueryV'+str(args.epoch)+'.dll')),'-luser32'],stdout=log,stderr=subprocess.STDOUT,check=True)
        subprocess.run(base+[str(HERE/'observer.cpp'),'-o',str(out/'observe_flag_query.exe'),'-luser32','-ladvapi32'],stdout=log,stderr=subprocess.STDOUT,check=True)
    shutil.copy2(HERE/'observer.cpp',out/'observer.cpp')
    manifest=dict(sources=[dict(path=str(p),sha256=sha(p)) for p in sources],compiler_sha256=sha(compiler),
        artifacts={name:sha(out/name) for name in ['MacroFlagQueryV'+str(args.epoch)+'.dll','observe_flag_query.exe']},epoch=args.epoch,
        native_game_calls=0,passive_only=True,field_verified=False,capability_granted=False)
    (out/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),**manifest)))


if __name__=='__main__':
    main()
