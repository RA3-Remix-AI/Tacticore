"""Offline audit of AIPersonalityDefinition Side strong-reference fixups.

RA3 manifest version uses 1-based import indices. An unresolved runtime pointer
does not imply a zero serialized reference; this tool distinguishes them.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,r'E:\RA3Modding\Analysis\Remix037')
from manifest import parse

def read_stream(path):
    raw=path.read_bytes();header=struct.unpack_from('<12I',raw);rows=parse(path)
    start=48+header[3]*48+header[8]
    return dict(path=str(path),header=header,manifest_refs=raw[start:start+header[9]],rows=rows,
                files={x:path.with_suffix('.'+x).read_bytes() for x in ['bin','imp','relo']})

def audit(path,prefix):
    stream=read_stream(path)
    base=parse(r'E:\RA3Modding\SDK\BuiltMods\sagexml\global.manifest')
    names={(r['type_id'],r['instance_id']):r['name'] for r in base+stream['rows']}
    records=[]
    for row in stream['rows']:
        if not row['name'].startswith('AIPersonalityDefinition:'+prefix):continue
        binary=stream['files']['bin'][row['binary_offset']:row['binary_offset']+row['binary_size']]
        imports=stream['files']['imp'][row['imp_offset']:row['imp_offset']+row['imp_size']]
        offsets=struct.unpack('<'+'I'*(len(imports)//4),imports) if imports else ()
        if offsets and offsets[-1]!=0xffffffff:raise ValueError('Missing import terminator')
        count,array=struct.unpack_from('<II',binary,0xec)
        if count>32 or array+count*4>len(binary):raise ValueError('Invalid Side array')
        sides=[]
        for i in range(count):
            offset=array+i*4;index=struct.unpack_from('<I',binary,offset)[0]
            valid=1<=index<=len(row['refs']) and offset in offsets
            key=tuple(row['refs'][index-1]) if valid else None
            sides.append(dict(offset=hex(offset),serialized_import_index=index,offset_in_imp=offset in offsets,
                              reference_key=[hex(x) for x in key] if key else None,
                              target=names.get(key),valid=valid))
        records.append(dict(name=row['name'],side_count=count,sides=sides,
                            binary_sha256=hashlib.sha256(binary).hexdigest(),imports_sha256=hashlib.sha256(imports).hexdigest(),
                            references_sha256=hashlib.sha256(b''.join(struct.pack('<II',*ref) for ref in row['refs'])).hexdigest()))
    return dict(stream=str(path),manifest_refs_hex=stream['manifest_refs'].hex(),manifest_refs_text=stream['manifest_refs'].decode('latin1'),records=records)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stream',type=Path,required=True);ap.add_argument('--compare',type=Path);ap.add_argument('--prefix',default='4TFLLM');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    report=audit(a.stream,a.prefix)
    if a.compare:
        second=audit(a.compare,a.prefix);other={r['name']:r for r in second['records']}
        report['comparison']=dict(stream=str(a.compare),manifest_refs_identical=report['manifest_refs_hex']==second['manifest_refs_hex'],records=[])
        for row in report['records']:
            if row['name'] not in other:continue
            target=other[row['name']]
            report['comparison']['records'].append(dict(name=row['name'],serialized_sides_identical=row['sides']==target['sides'],
                    binary_identical=row['binary_sha256']==target['binary_sha256'],imports_identical=row['imports_sha256']==target['imports_sha256'],references_identical=row['references_sha256']==target['references_sha256']))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(a.output)
    print('Side references valid:',all(s['valid'] for r in report['records'] for s in r['sides']))
    if a.compare:print('Compared',len(report['comparison']['records']),'records')
if __name__=='__main__':main()
