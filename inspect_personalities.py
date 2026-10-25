"""Read-only inspection of the version-pinned native personality store."""
import argparse,ctypes as c,hashlib,json,struct,sys,time
from pathlib import Path
from probe import k,ROOT,EXPECTED
from ctypes import wintypes as w
sys.path.insert(0,r'E:\RA3Modding\Analysis\Remix037')
from manifest import parse

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--catalog',type=Path,action='append',default=[],help='Additional compiled mod/metadata manifest; repeatable')
    ap.add_argument('--output',type=Path,help='Explicit snapshot output path')
    ap.add_argument('--label',default='',help='Experiment variant/session label, not an identity')
    args=ap.parse_args()
    h=k.OpenProcess(0x410,False,args.pid)
    if not h:raise c.WinError(c.get_last_error())
    try:
        path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(h,0,path,c.byref(size)):raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Unsupported executable')
        def read(addr,n):
            if not n:return b''
            b=c.create_string_buffer(n);got=c.c_size_t()
            if not k.ReadProcessMemory(h,addr,b,n,c.byref(got)) or got.value!=n:raise RuntimeError('Read failed')
            return b.raw
        def word(addr):return struct.unpack('<I',read(addr,4))[0]
        store=word(0xce98ec)
        if word(store)!=0xc606b8:raise RuntimeError('Personality store signature mismatch')
        start,end=word(store+0x24),word(store+0x28)
        if not 0<=end-start<=4096 or (end-start)%4:raise RuntimeError('Invalid store bounds')
        catalog={};catalogs=[]
        for file in [Path(r'E:\RA3Modding\SDK\BuiltMods\sagexml\global.manifest'),Path(r'E:\RA3Modding\SDK\BuiltMods\mods\CommanderLab\data\mod.manifest')]+args.catalog:
            if file.exists():catalog.update({r['instance_id']:r['name'] for r in parse(file) if r['name'].startswith('AIPersonalityDefinition:')})
            if file.exists():catalogs.append(dict(path=str(file),sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
        rows=[]
        for wrapper in struct.unpack('<'+'I'*((end-start)//4),read(start,end-start)):
            data=word(wrapper);count=word(data+0xec);array=word(data+0xf0)
            if count>32:raise RuntimeError('Invalid side array')
            values=list(struct.unpack('<'+'I'*count,read(array,count*4)))
            ident=word(wrapper+0x18)
            # Immediately following Side is PersonalityMap: array of (Side,
            # Personality) strong references. The stock schema and the probe
            # binary layout establish this 8-byte entry layout. Inspect Random
            # too; its valid Null Side alone says nothing about mapped sides.
            map_count,map_array=word(data+0xf4),word(data+0xf8)
            if map_count>32:raise RuntimeError('Invalid personality map array')
            maps=[]
            for i in range(map_count):
                side,personality=struct.unpack('<II',read(map_array+8*i,8))
                maps.append(dict(side=hex(side),personality=hex(personality),has_null_reference=not side or not personality))
            rows.append(dict(name=catalog.get(ident,hex(ident)),instance_id=hex(ident),wrapper=hex(wrapper),data=hex(data),side_count=count,side_references=[hex(v) for v in values],has_null_side=any(v==0 for v in values),personality_maps=maps))
        out=args.output or ROOT/'reports'/('personalities-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(dict(pid=args.pid,executable_sha256=EXPECTED,label=args.label,catalogs=catalogs,store=hex(store),count=len(rows),rows=rows,note='Read-only, non-atomic inspection. Presence in store does not prove selectable or operational. Catalog name is annotation; instance_id is the native identity.'),ensure_ascii=False,indent=2),encoding='utf-8')
        print(out)
    finally:k.CloseHandle(h)
if __name__=='__main__':main()
