"""Exercise frozen Native6 lock_hash in a separate, non-attaching EXE.

Build-only harness includes the exact frozen native.cpp. It calls only
runtime_input and lock_hash, never prepare/tick/Native/OS process APIs.
No replacement DLL, input file or manifest is written to the candidate.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'integration'))
from host_runtime.native6_runtime_contract import sha,verify_build,verify_inventory

HARNESS=r'''
#include "native.cpp"
int main(){
 wchar_t root[1024];if(!portable_argument(1,root,1024))return 2;
 for(unsigned i=0;i<SOURCE_PIN_COUNT;i++){
  wchar_t path[1024];if(!runtime_input(root,SOURCE_PINS[i].path,path,1024)||!lock_hash(path,SOURCE_PINS[i].sha))return 3;
 }
 printf("%u\n",input_count);fflush(stdout);getchar();
 for(unsigned i=0;i<input_count;i++)CloseHandle(inputs[i]);return 0;
}
'''


def probe(runtime,compiler,output):
    runtime=Path(runtime).absolute();output=Path(output).absolute();compiler=Path(compiler).absolute()
    pin=sha(runtime/'manifest.json');inventory=verify_inventory(runtime,expected=pin)
    manifest=verify_build(runtime/'native/strategic6')
    if sha(compiler)!=manifest['build_source_pins']['toolchain/i686-w64-mingw32-g++.exe']:raise ValueError('compiler_changed')
    source=runtime/'native/strategic6'
    for name in ('native.cpp','shared.h','flags.h','flag_api.h','portable_paths.h','strategic_manager_gate_enable_candidate_v2.h'):
        if sha(source/name)!=manifest['build_source_pins'][name]:raise ValueError('frozen_source_changed')
    output.mkdir()  # a separate new harness directory, never candidate output
    (output/'harness.cpp').write_text(HARNESS,encoding='ascii')
    command=[str(compiler),'-std=c++17','-D_WIN32_WINNT=0x0601','-O2','-static-libgcc','-static-libstdc++',
        '-I',str(source),str(output/'harness.cpp'),'-o',str(output/'harness.exe'),'-ladvapi32','-lshell32','-lole32','-luuid']
    compiled=subprocess.run(command,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    (output/'compile.log').write_bytes(compiled.stdout+compiled.stderr)
    if compiled.returncode:raise ValueError('native6_lock_harness_compile_failed')
    k=c.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE];k.CreateFileW.restype=w.HANDLE
    k.CloseHandle.argtypes=[w.HANDLE]
    started=time.monotonic()
    child=subprocess.Popen([str(output/'harness.exe'),str(runtime)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    denied=0
    try:
        # The bounded native input set is fully hashed before the ready count.
        count=int(child.stdout.readline())
        if count!=len(manifest['input_pins']):raise ValueError('native6_lock_count_changed')
        acquired_ms=round((time.monotonic()-started)*1000)
        for name in manifest['input_pins']:
            for access in (0x40000000,0x10000):  # GENERIC_WRITE / DELETE; never WriteFile/DeleteFile
                handle=k.CreateFileW(str(runtime/name),access,7,None,3,0x80,None)
                if handle not in (None,c.c_void_p(-1).value):
                    k.CloseHandle(handle);raise ValueError('native6_input_not_held:'+name)
                if c.get_last_error()!=32:raise ValueError('native6_lock_denial_not_sharing_violation')
                denied+=1
        child.communicate(b'\n',timeout=10)
        if child.returncode:raise ValueError('native6_lock_harness_failed')
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)
    # Opening a writable handle succeeds only AFTER all harness handles close.
    # No contents are changed. This distinguishes sharing denial from ACLs.
    handle=k.CreateFileW(str(runtime/'python/Lib/site-packages.zip'),0x40000000,7,None,3,0x80,None)
    if handle in (None,c.c_void_p(-1).value):raise ValueError('native6_lock_harness_did_not_release')
    k.CloseHandle(handle);verify_inventory(runtime,expected=pin)
    return dict(kind='native6_exact_frozen_input_lock_smoke',runtime_manifest_sha256=pin,
        runtime_input_pins=count,native_handle_bound=4096,source_pin_limit=4093,write_and_delete_handles_denied=denied,
        all_input_hashes_verified_by_frozen_cpp=True,dependency_container_continuously_locked=True,
        lock_acquisition_ms=acquired_ms,harness_exit=child.returncode,inventory_unchanged=True,
        harness_sha256=sha(output/'harness.exe'),game_access=False,native_commands=0,formal_games=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('runtime','compiler','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();result=probe(args.runtime,args.compiler,args.output)
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
