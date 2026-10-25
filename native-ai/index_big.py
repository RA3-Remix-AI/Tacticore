"""List matching BIG entries without reading multi-gigabyte payloads."""
import argparse,json,struct
from pathlib import Path
def main():
    ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path);ap.add_argument('terms',nargs='*');a=ap.parse_args();rows=[]
    with a.archive.open('rb') as f:
        magic,total,count,end=struct.unpack('>4sIII',f.read(16))
        if magic not in (b'BIG4',b'BIGF'):raise ValueError('Not BIG')
        for _ in range(count):
            offset,size=struct.unpack('>II',f.read(8));name=bytearray()
            while (b:=f.read(1))!=b'\0':
                if not b:raise ValueError('Truncated index')
                name.extend(b)
            name=name.decode('ascii')
            if not a.terms or any(t.lower() in name.lower() for t in a.terms):rows.append(dict(name=name,offset=offset,size=size))
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
