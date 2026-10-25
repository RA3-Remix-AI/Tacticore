"""Explicit one-unit movement experiment; logs baseline and post-command samples."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import time
from probe import k, EXPECTED, ROOT

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--snapshot',type=Path,required=True)
    ap.add_argument('--unit',required=True)
    ap.add_argument('--owner-index',type=int,required=True)
    args=ap.parse_args()
    snapshot=json.loads(args.snapshot.read_text(encoding='utf-8-sig'))
    if snapshot['pid']!=args.pid or snapshot['sha256']!=EXPECTED:
        raise RuntimeError('Snapshot process/version mismatch')
    unit=next(x for x in snapshot['candidates'] if int(x['address'],0)==int(args.unit,0))
    if unit['owner_index_candidate']!=args.owner_index or unit['catalog'].get('cls')!=1:
        raise RuntimeError('Only an explicitly selected infantry candidate is allowed')
    handle=k.OpenProcess(0x0400|0x10,False,args.pid)
    if not handle: raise c.WinError(c.get_last_error())
    try:
        path=c.create_unicode_buffer(32768);length=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(handle,0,path,c.byref(length)):
            raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest()!=EXPECTED:
            raise RuntimeError('Executable hash mismatch')
        def read(addr,n):
            buf=c.create_string_buffer(n);got=c.c_size_t()
            if not k.ReadProcessMemory(handle,addr,buf,n,c.byref(got)) or got.value!=n:
                raise RuntimeError('Object read failed')
            return buf.raw
        def u32(addr): return struct.unpack('<I',read(addr,4))[0]
        address=int(args.unit,0);owner=int(unit['owner_address'],0);expected_hash=int(unit['type_hash'],0)
        started=time.monotonic();samples=[]
        def sample(phase):
            raw=read(address,0x41c)
            if struct.unpack_from('<I',raw)[0]!=0xc4db60 or struct.unpack_from('<I',raw,0x418)[0]!=owner:
                raise RuntimeError('Object identity changed')
            if u32(u32(address+4)+8)!=expected_hash: raise RuntimeError('Type changed')
            xyz=struct.unpack_from('<fff',raw,0x38)
            if not all(math.isfinite(x) for x in xyz): raise RuntimeError('Bad coordinates')
            hp=struct.unpack('<f',read(u32(address+0x33c)+4,4))[0]
            if not math.isfinite(hp) or hp<=0: raise RuntimeError('Unit not alive')
            item=dict(seconds=round(time.monotonic()-started,3),phase=phase,xyz=xyz,hp=hp)
            samples.append(item)
            return xyz
        for _ in range(8): sample('baseline');time.sleep(.25)
        origin=sample('before_command');target=[origin[0]+100,origin[1],origin[2]]
        command=[str(ROOT/'bin/controller.exe'),str(args.pid),'move',hex(address),hex(owner),hex(expected_hash),*[str(v) for v in target]]
        issued=time.monotonic()-started
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        for _ in range(48): sample('after_command');time.sleep(.25)
        stdout,stderr=proc.communicate(timeout=5)
        baseline_distance=math.dist(samples[0]['xyz'],origin)
        distances=[math.dist(s['xyz'],target) for s in samples if s['phase']=='after_command']
        result=dict(pid=args.pid,unit=unit,target=target,issued_seconds=issued,
                    controller_exit=proc.returncode,controller_stdout=stdout,controller_stderr=stderr,
                    baseline_displacement=baseline_distance,min_target_distance=min(distances),
                    final_target_distance=distances[-1],samples=samples,
                    note='Window-thread experimental call, not a production simulation-thread API. AI ownership inferred from explicit local match setup. Coordinate evidence only; no visual arrival assertion.')
        out=ROOT/'reports'/('move-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(report=str(out),controller_exit=proc.returncode,baseline_displacement=baseline_distance,min_target_distance=min(distances),final_target_distance=distances[-1]),ensure_ascii=False))
    finally: k.CloseHandle(handle)

if __name__=='__main__':main()
