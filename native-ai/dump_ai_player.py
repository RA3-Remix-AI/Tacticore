"""Inspect AI component candidates and native command sources without writes."""
import argparse,ctypes as c,hashlib,json,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from probe import k,EXPECTED
from ctypes import wintypes as w

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--owner-index',type=int,default=3);a=ap.parse_args()
    snapshot=json.loads(a.snapshot.read_text(encoding='utf-8-sig'))
    if snapshot['pid']!=a.pid:raise RuntimeError('Snapshot process mismatch')
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
        def in_module(p):return 0x400000<=p<0xd3b000
        owners=sorted({int(x['owner_address'],0) for x in snapshot['candidates'] if x['owner_index_candidate']==a.owner_index})
        players=[]
        for owner in owners:
            if word(owner+0x20)!=a.owner_index or not in_module(word(owner)):continue
            ai=word(owner+0x90)
            if not ai or not in_module(word(ai)):continue
            components=[]
            for label,offset in [('unit_builder_part_1',0x104+0x3d0),('unit_builder_part_2',0x104+0x460),('base_builder',0x104+0x354)]:
                address=ai+offset;vt=word(address);setter=word(vt+4) if in_module(vt) else 0
                components.append(dict(label=label,address=hex(address),vtable=hex(vt),setter=hex(setter),first_32_bytes=read(address,32).hex(),setter_first_32_bytes=read(setter,32).hex() if in_module(setter) else None))
            players.append(dict(owner=hex(owner),owner_index=a.owner_index,owner_vtable=hex(word(owner)),ai_player=hex(ai),ai_player_vtable=hex(word(ai)),ai_player_first_0x120_bytes=read(ai,0x120).hex(),components=components))
        units=[]
        for candidate in snapshot['candidates']:
            if candidate['owner_index_candidate']!=a.owner_index or not candidate['catalog'] or candidate['catalog'].get('category')!=0:continue
            obj=int(candidate['address'],0)
            try:
                if word(obj)!=0xc4db60 or word(obj+0x418)!=int(candidate['owner_address'],0) or word(word(obj+4)+8)!=int(candidate['type_hash'],0):continue
                ai=word(obj+0x374);body=word(obj+0x33c);hp=struct.unpack('<f',read(body+4,4))[0]
                if hp<=0 or not in_module(word(ai)):continue
                units.append(dict(address=hex(obj),name=candidate['catalog']['template'],owner=hex(word(obj+0x418)),ai=hex(ai),hp=hp,command_source_raw=word(ai+0x50),xyz=struct.unpack('<fff',read(obj+0x38,12))))
            except RuntimeError:continue
        report=dict(pid=a.pid,source_snapshot=str(a.snapshot),players=players,units=units,mutations=False,note='Offsets established by static call-chain analysis; component labels are candidates until dynamic toggle/production validation. Sources 0/1/2/3 follow SDK CommandSourceType.')
        target=ROOT/('ai-player-'+time.strftime('%Y%m%d-%H%M%S')+'.json');target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(target)
        for p in players:print(json.dumps(p,ensure_ascii=False))
        for u in units:print(json.dumps(u,ensure_ascii=False))
    finally:k.CloseHandle(h)
if __name__=='__main__':main()
