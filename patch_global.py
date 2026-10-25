"""Lab-only additive global.12 stream overlay. Never changes game installation."""
import sys,struct,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,r'E:\RA3Modding\Reference')
sys.path.insert(0,str(ROOT.parent/'TriadFront/tools'))
sys.path.insert(0,r'E:\RA3Modding\Analysis\Remix037')
from inspect_data import big_entries
from read_remix_meshes import unpack_refpack
from manifest import parse

def parts(path):
    b=path.read_bytes();h=list(struct.unpack_from('<12I',b));rows=parse(path)
    start=48+h[3]*48+h[8];mrefs=b[start:start+h[9]]
    files={s:path.with_suffix('.'+s).read_bytes() for s in ['bin','relo','imp']}
    return h,rows,mrefs,files

def main():
    stage=Path(r'E:\RA3Modding\SDK\BuiltMods\mods\CommanderLab\data')
    baseline=ROOT/'reports/global-baseline';baseline.mkdir(exist_ok=True)
    wanted={'data\\global.12.'+ext for ext in ['manifest','bin','relo','imp']}
    for name,raw in big_entries(Path(r'E:\RedRar3\Data\Core12.big')):
        if name.lower() in wanted:(baseline/name.split('\\')[-1]).write_bytes(unpack_refpack(raw))
    path=baseline/'global.12.manifest';h,old,mrefs,files=parts(path)
    _,new,_,newfiles=parts(stage/'mod.manifest')
    added=[r for r in new if r['name'].startswith('AIPersonalityDefinition:TFLLM')]
    assert len(added)==4
    specs=[(r,files) for r in old]+[(r,newfiles) for r in added]
    refs=bytearray();names=bytearray();sources=bytearray();records=[]
    blobs={ext:bytearray(struct.pack('<I',h[1])) for ext in files}
    for r,data in specs:
        ro,no,so=len(refs),len(names),len(sources)
        for key in r['refs']:refs.extend(struct.pack('<2I',*key))
        names.extend(r['name'].encode()+b'\0');sources.extend(r['source'].encode()+b'\0')
        records.append(struct.pack('<12I',r['type_id'],r['instance_id'],r['type_hash'],r['instance_hash'],ro,len(r['refs']),no,so,r['binary_size'],r['relo_size'],r['imp_size'],r['flags']))
        for ext,off,size in [('bin','binary_offset','binary_size'),('relo','relo_offset','relo_size'),('imp','imp_offset','imp_size')]:
            payload=data[ext][r[off]:r[off]+r[size]];assert len(payload)==r[size];blobs[ext].extend(payload)
    h[3]=len(specs);h[4]=len(blobs['bin'])-4
    h[5]=max(r['binary_size'] for r,_ in specs);h[6]=max(r['relo_size'] for r,_ in specs);h[7]=max(r['imp_size'] for r,_ in specs)
    h[8:12]=[len(refs),len(mrefs),len(names),len(sources)]
    dest=stage/'global.12.manifest';dest.write_bytes(struct.pack('<12I',*h)+b''.join(records)+refs+mrefs+names+sources)
    for ext,data in blobs.items():dest.with_suffix('.'+ext).write_bytes(data)
    after=parse(dest);assert len(after)==len(old)+4
    # Existing resources must retain both metadata and exact payload bytes.
    for original,current in zip(old,after):
        assert original['name']==current['name'] and original['refs']==current['refs']
        for ext,off,size in [('bin','binary_offset','binary_size'),('relo','relo_offset','relo_size'),('imp','imp_offset','imp_size')]:
            assert files[ext][original[off]:original[off]+original[size]]==blobs[ext][current[off]:current[off]+current[size]]
    (ROOT/'reports/global-overlay.json').write_text(json.dumps({'baseline_resources':len(old),'added':[r['name'] for r in added],'preserved_original_payloads':True,'runtime_verified':False},indent=2),encoding='utf-8')
    print('Global overlay: preserved',len(old),'resources, added',len(added))
if __name__=='__main__':
    raise RuntimeError('Disabled: global overlay experiment did not pass runtime validation. Keep only for research.')
