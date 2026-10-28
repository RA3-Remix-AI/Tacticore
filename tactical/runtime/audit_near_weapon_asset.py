"""Inspect actual BIG stream payloads for the Conscript AK47; no game process.

The native getter's schema+4 field is cross-checked against compiled assets.
This static audit cannot establish a live entry, effective range or a shot.
"""
import argparse,hashlib,importlib.util,json,math,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT.parent/'Mods/TFCommanderPlay/TFNames.big'
EXPECTED_MOD='2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665'
TYPE,ASSET=0x94d4d96e,0x447ea26e
sha=lambda data:hashlib.sha256(data).hexdigest()
HASH_SOURCE=ROOT/'reference/Ra3-Copilot/unit-codes/tools/sage_hash.py'
spec=importlib.util.spec_from_file_location('range_audit_sage_hash',HASH_SOURCE);hash_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(hash_module)
RANGE_FIELDS=['AttackRange','MinimumAttackRange','RangeBonusMinHeight','RangeBonus','RangeBonusPerFoot']

def tokenized_ranges(blob):
    # WeaponTemplate is xas:typeGroup="Tokenized". The on-disk payload starts
    # with (field-name hash, type token, data offset), not runtime schema floats.
    values=[];tokens=[]
    for index,name in enumerate(RANGE_FIELDS):
        key,kind,offset=struct.unpack_from('<3I',blob,12*index)
        if key!=hash_module.sage_hash(name) or offset<60 or offset+4>len(blob):raise ValueError('Tokenized range field identity/extent')
        value=struct.unpack_from('<f',blob,offset)[0]
        if not math.isfinite(value):raise ValueError('Nonfinite compiled field')
        values.append(value);tokens.append(dict(name=name,field_hash=hex(key),type_token=hex(kind),data_offset=offset,value=value))
    return values,tokens

def unpack(data):
    if len(data)<5 or data[1]!=0xfb or data[0]&0x7e!=0x10:return data
    width=4 if data[0]&0x80 else 3;expected=int.from_bytes(data[2:2+width],'big')
    if expected>512*1024*1024:raise ValueError('Research payload limit')
    cursor=2+width*(2 if data[0]&1 else 1);out=bytearray()
    while cursor<len(data):
        control=data[cursor];cursor+=1;length=0;distance=0;done=False
        if control<0x80:
            value=data[cursor];cursor+=1;literal=control&3;length=((control>>2)&7)+3;distance=((control&0x60)<<3)+value+1
        elif control<0xc0:
            a,b=data[cursor:cursor+2];cursor+=2;literal=a>>6;length=(control&0x3f)+4;distance=((a&0x3f)<<8)+b+1
        elif control<0xe0:
            a,b,d=data[cursor:cursor+3];cursor+=3;literal=control&3;length=((control&12)<<6)+d+5;distance=((control&16)<<12)+(a<<8)+b+1
        elif control<0xfc:literal=((control&31)<<2)+4
        else:literal=control&3;done=True
        if cursor+literal>len(data):raise ValueError('Truncated RefPack literal')
        out.extend(data[cursor:cursor+literal]);cursor+=literal
        if length:
            if not 0<distance<=len(out):raise ValueError('Invalid RefPack backreference')
            start=len(out)-distance
            if length<=distance:out.extend(out[start:start+length])
            else:out.extend((out[start:]*((length+distance-1)//distance))[:length])
        if len(out)>expected:raise ValueError('RefPack output overflow')
        if done:break
    if len(out)!=expected:raise ValueError('RefPack output size mismatch')
    return bytes(out)

def big_index(stream):
    magic,total,count,end=struct.unpack('>4sIII',stream.read(16))
    if magic not in (b'BIG4',b'BIGF') or count>200000:raise ValueError('Unsupported BIG header')
    index={}
    for _ in range(count):
        offset,size=struct.unpack('>II',stream.read(8));name=bytearray()
        while True:
            char=stream.read(1)
            if char==b'\0':break
            if not char or len(name)>2048:raise ValueError('BIG name bounds')
            name.extend(char)
        key=name.decode('ascii').lower()
        if key in index:raise ValueError('Duplicate BIG entry')
        index[key]=(offset,size)
    return index

def manifest_rows(data):
    header=struct.unpack_from('<12I',data);count=header[3]
    refs=48+count*48;manifests=refs+header[8];names=manifests+header[9];sources=names+header[10]
    if count>200000 or sources+header[11]!=len(data):raise ValueError('Manifest extent')
    def string(base,size,offset):
        if offset>=size:raise ValueError('Manifest string offset')
        end=data.index(0,base+offset,base+size);return data[base+offset:end].decode('utf-8')
    binary=4;rows=[]
    for index in range(count):
        row=struct.unpack_from('<12I',data,48+48*index)
        rows.append(dict(index=index,type_id=row[0],instance_id=row[1],type_hash=row[2],instance_hash=row[3],
            name=string(names,header[10],row[6]),source=string(sources,header[11],row[7]),binary_offset=binary,binary_size=row[8],flags=row[11]))
        binary+=row[8]
    return rows

def audit(output):
    output=output.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports'):raise ValueError('Fresh local report directory required')
    if sha(MOD.read_bytes())!=EXPECTED_MOD:raise ValueError('Exact active mod required')
    output.mkdir();records=[]
    for archive,names in [(Path('E:/RedRar3/Data/GlobalStream.big'),['data\\global.manifest']),
                          (Path('E:/RedRar3/Data/StaticStream.big'),['data\\static.manifest','data\\static_l.manifest','data\\static_m.manifest']),
                          (MOD,['data\\mod.manifest','data\\mod_l.manifest','data\\mod_m.manifest'])]:
        with archive.open('rb')as stream:
            entries=big_index(stream)
            for name in names:
                offset,size=entries[name];stream.seek(offset);packed=stream.read(size);manifest=unpack(packed)
                rows=manifest_rows(manifest);matches=[row for row in rows if row['type_id']==TYPE and row['instance_id']==ASSET]
                label=('mod-'if archive==MOD else 'stock-')+Path(name.replace('\\','/')).stem
                (output/(label+'.manifest')).write_bytes(manifest)
                row=dict(archive=str(archive),manifest_entry=name,manifest_sha256=sha(manifest),manifest_stored_sha256=sha(packed),matches=[])
                if len(matches)>1:raise ValueError('Duplicate weapon asset')
                for asset in matches:
                    if not asset['binary_size']:
                        row['matches'].append(dict(asset,compiled_available=False,base_stream_reference=True))
                        continue
                    bin_name=name[:-9]+'.bin';bin_offset,bin_size=entries[bin_name];stream.seek(bin_offset);binary=unpack(stream.read(bin_size))
                    start=asset['binary_offset'];end=start+asset['binary_size']
                    if not 24<=asset['binary_size'] or end>len(binary):raise ValueError('Compiled weapon extent')
                    blob=binary[start:end];path=output/(label+'-ak47.bin');path.write_bytes(blob)
                    ranges,tokens=tokenized_ranges(blob)
                    row['matches'].append(dict(asset,compiled_available=True,compiled_file=path.name,compiled_sha256=sha(blob),tokens=tokens,
                        base_range=ranges[0],minimum_range=ranges[1],bonus_min_height=ranges[2],bonus=ranges[3],bonus_per_foot=ranges[4],
                        first_24_bytes=blob[:24].hex()))
                records.append(row)
    result=dict(kind='near_compiled_weapon_static_asset_audit',mod_sha256=EXPECTED_MOD,weapon_type=hex(TYPE),weapon_asset=hex(ASSET),
        records=records,process_opened=False,game_sdk_calls=0,live_weapon_verified=False,effective_range_verified=False,attack_granted=False,
        source_sha256=sha(Path(__file__).read_bytes()),hash_source_sha256=sha(HASH_SOURCE.read_bytes()))
    (output/'audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),streams=len(records),weapons=[dict(stream=row['manifest_entry'],ranges=[(a['base_range'],a['minimum_range'],a['bonus'])for a in row['matches']if a['compiled_available']],base_references=sum(not a['compiled_available']for a in row['matches']))for row in records])))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();audit(args.output)
