"""Read-only RA3 1.12 ScriptEngine action metadata and static handlers."""
import argparse,ctypes as c,hashlib,json,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from probe import k,EXPECTED
from ctypes import wintypes as w

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);a=ap.parse_args()
    h=k.OpenProcess(0x410,False,a.pid)
    if not h:raise c.WinError(c.get_last_error())
    try:
        path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(h,0,path,c.byref(size)):raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Unsupported executable')
        def read(addr,n):
            if not n:return b''
            b=c.create_string_buffer(n);got=c.c_size_t()
            if not k.ReadProcessMemory(h,addr,b,n,c.byref(got)) or got.value!=n:raise RuntimeError('Read failed '+hex(addr))
            return b.raw
        def word(addr):return struct.unpack('<I',read(addr,4))[0]
        def string(addr,limit=512):
            if not addr:return ''
            chunks=[]
            for i in range(limit):
                b=read(addr+i,1)
                if b==b'\0':return b''.join(chunks).decode('utf-8',errors='replace')
                chunks.append(b)
            return '<unterminated>'
        expected=bytes.fromhex('81ec4c0600005355568bb4245c060000')
        if read(0x5a2b40,len(expected))!=expected:raise RuntimeError('Dispatcher signature mismatch')
        if read(0x5a2b70,7)!=bytes.fromhex('ff24856cd05a00'):raise RuntimeError('Dispatcher jump table mismatch')
        engine=word(0xcdd190)
        if not engine:raise RuntimeError('ScriptEngine not initialized; enter a local match')
        rows=[]
        for i in range(0x23d):
            entry=engine+0x48+i*0x80
            raw=read(entry,0x80);nameptr=struct.unpack_from('<I',raw,0xc)[0]
            if not nameptr:continue
            name=string(nameptr)
            if not name or name=='<unterminated>':continue
            handler=word(0x5ad06c+i*4)
            rows.append(dict(index=i,name=name,entry=hex(entry),nparams=struct.unpack_from('<I',raw,0x48)[0],
                             words=[hex(v) for v in struct.unpack('<32I',raw)],handler=hex(handler)))
        report=dict(pid=a.pid,executable=path.value,sha256=EXPECTED,engine=hex(engine),actions=rows,
                    note='Read-only metadata; handler addresses are jump-table case blocks, NOT standalone callable APIs. Param enums and argument order require disassembly.')
        target=ROOT/('actions-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        relevant=[r for r in rows if r['name'].startswith(('PLAYER_AI_','SKIRMISH_AI_','UNIT_AI_','TEAM_AI_')) or r['name'] in ['NAMED_USE_COMMANDBUTTON','SET_REF_TO_NEREST_TEAM_OF_UNNAMED_TYPE_OWNED_BY_PLAYER','SET_REF_TO_NAMED','NAMED_BUILD_STRUCTURE_AT_WAYPOINT']]
        (ROOT/'actions-relevant.json').write_text(json.dumps(relevant,ensure_ascii=False,indent=2),encoding='utf-8')
        print(target)
        for r in relevant:print(r['index'],r['name'],r['nparams'],r['handler'])
    finally:k.CloseHandle(h)
if __name__=='__main__':main()
