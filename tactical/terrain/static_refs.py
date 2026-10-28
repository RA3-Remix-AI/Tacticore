"""Find absolute .text word references in the pinned PE, without loading it."""
import argparse,hashlib,json,struct
from pathlib import Path
GAME_SHA='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'

def references(path,address,relative_call=False):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=GAME_SHA:raise ValueError('unsupported_game')
    u16=lambda p:struct.unpack_from('<H',raw,p)[0]
    u32=lambda p:struct.unpack_from('<I',raw,p)[0]
    pe=u32(0x3c);optional=pe+24;base=u32(optional+28);found=[]
    for index in range(u16(pe+6)):
        section=optional+u16(pe+20)+40*index
        if raw[section:section+8].rstrip(b'\0')!=b'.text':continue
        va,size,start=u32(section+12),u32(section+16),u32(section+20)
        if relative_call:
            for offset in range(start,start+size-4):
                if raw[offset]==0xe8 and base+va+offset-start+5+struct.unpack_from('<i',raw,offset+1)[0]==address:
                    found.append(dict(instruction_va=hex(base+va+offset-start),raw_hex=raw[offset:offset+5].hex()))
            continue
        cursor=start
        while True:
            offset=raw.find(struct.pack('<I',address),cursor,start+size)
            if offset<0:break
            found.append(dict(word_va=hex(base+va+offset-start),preceding_bytes=raw[max(start,offset-8):offset].hex(),
                following_bytes=raw[offset+4:offset+16].hex()))
            cursor=offset+1
    return dict(kind='static_relative_call_candidates' if relative_call else 'static_absolute_word_candidates',game_sha256=GAME_SHA,address=hex(address),references=found,
        native_calls=0,game_writes=0,query_permission_granted=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--game',type=Path,required=True)
    p.add_argument('--address',type=lambda x:int(x,0),required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=references(a.game,a.address)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(dict(count=len(result['references']),word_addresses=[x['word_va'] for x in result['references']])))
