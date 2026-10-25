"""Extract selected stock frontend streams to research directory, read-only game."""
import hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent.parent/'TriadFront/tools'))
from read_remix_meshes import unpack_refpack
WANTED={'fes_m_skirmishgamesetup','fem_m_gamesetup','fe_m_assetsgamesetup','std_mousedropdownmenu'}
def main():
    archive=Path(r'E:\RedRar3\Data\Apt.big');out=ROOT/'frontend-assets';out.mkdir(exist_ok=True);entries=[]
    with archive.open('rb') as f:
        _,_,count,_=struct.unpack('>4sIII',f.read(16))
        for _ in range(count):
            offset,size=struct.unpack('>II',f.read(8));name=bytearray()
            while (b:=f.read(1))!=b'\0':
                if not b:raise ValueError('Truncated index')
                name.extend(b)
            name=name.decode('ascii');file=Path(name.replace('\\','/'))
            if file.stem in WANTED:entries.append((name,offset,size))
        report=[]
        for name,offset,size in entries:
            f.seek(offset);raw=f.read(size);data=unpack_refpack(raw);target=out/Path(name.replace('\\','/')).name;target.write_bytes(data)
            report.append(dict(archive=str(archive),entry=name,offset=offset,stored_size=size,output=str(target),sha256=hashlib.sha256(data).hexdigest()))
    (out/'extraction.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(out)
if __name__=='__main__':main()
