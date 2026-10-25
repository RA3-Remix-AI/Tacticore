"""Offline raw-immediate xrefs; candidates require disassembly verification."""
import argparse,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'reference/Ra3-Copilot/ra3-copilot/tools'))
from precheck_aob import parse_pe,rva_to_off
GAME=Path(r'E:\RedRar3\Data\RA3_1.12.game')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('strings',nargs='+');a=ap.parse_args()
    raw=GAME.read_bytes();base,size,sections=parse_pe(raw)
    def va(off):
        for name,rva,vs,rp,rs in sections:
            if rp<=off<rp+rs:return base+rva+off-rp
    rows=[]
    for needle in a.strings:
        if needle.startswith('field:'):
            field=int(needle[6:],0);refs=[]
            for name,rva,vs,rp,rs in sections:
                if name!='.text':continue
                at=rp
                while (at:=raw.find(struct.pack('<I',field),at,rp+rs))>=0:
                    if raw[at-2] in (0x8b,0x89,0x83,0xc7,0x8d) and raw[at-1]&0xc0==0x80:
                        refs.append(dict(va=hex(base+rva+at-rp-2),bytes=raw[at-2:at+9].hex()))
                    at+=1
            rows.append(dict(needle=needle,instruction_candidates=refs));continue
        if needle.startswith('call:'):
            target=int(needle[5:],0);refs=[]
            for name,rva,vs,rp,rs in sections:
                if name!='.text':continue
                at=rp
                while (at:=raw.find(b'\xe8',at,rp+rs-4))>=0:
                    if base+rva+(at-rp)+5+struct.unpack_from('<i',raw,at+1)[0]==target:refs.append(hex(base+rva+at-rp))
                    at+=1
            rows.append(dict(needle=needle,target=hex(target),raw_e8_candidates=refs))
            continue
        if needle.startswith('0x'):
            address=int(needle,16);refs=[];point=0;packed=struct.pack('<I',address)
            while (at:=raw.find(packed,point))>=0:
                point=at+1
                refs.append(hex(va(at)) if va(at) else 'file:'+hex(at))
            rows.append(dict(needle=needle,va=hex(address),refs=refs))
            continue
        start=0
        while (off:=raw.find(needle.encode(),start))>=0:
            address=va(off);start=off+1
            if address is None:continue
            refs=[];point=0;packed=struct.pack('<I',address)
            while (at:=raw.find(packed,point))>=0:
                point=at+1
                refs.append(hex(va(at)) if va(at) else 'file:'+hex(at))
            rows.append(dict(needle=needle,va=hex(address),refs=refs))
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
