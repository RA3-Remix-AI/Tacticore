"""Read-only comparison of native skirmish vector and ordered enumeration tree."""
import argparse,ctypes as c,hashlib,json,struct,sys
from pathlib import Path
from ctypes import wintypes as w
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent))
from probe import k,EXPECTED

def inspect_indexes(read):
    def word(p):return struct.unpack('<I',read(p,4))[0]
    store=word(0xce98ec)
    if word(store)!=0xc606b8:raise ValueError('Store mismatch')
    start,end=word(store+0x24),word(store+0x28)
    if not 0<=end-start<=16384 or (end-start)%4:raise ValueError('Vector bounds')
    wrappers=list(struct.unpack('<'+'I'*((end-start)//4),read(start,end-start)))
    def asset(wrapper):
        data=word(wrapper);count,array=word(data+0xec),word(data+0xf0)
        if not 0<=count<=32:raise ValueError('Side bounds')
        length,chars=word(data+4),word(data+8)
        if not 0<=length<=256:raise ValueError('PersonalityType length')
        return dict(wrapper=hex(wrapper),instance_id=hex(word(wrapper+0x18)),
                    personality_type=read(chars,length).decode('utf-8','replace') if length else '',
                    skirmish=bool(read(data+0x1fc,1)[0]),registration_nonempty_field=word(data+0xc),
                    sides=[hex(x) for x in struct.unpack('<'+'I'*count,read(array,count*4))],
                    raw_first_24=read(data,24).hex())
    vector=[asset(x) for x in wrappers]
    sentinel=store+0x38;node=word(store+0x3c);tree=[];seen=set()
    while node!=sentinel:
        if not node or node in seen or len(seen)>4096:raise ValueError('Tree cycle/invalid node')
        seen.add(node);wrapper=word(node+0x14)
        tree.append(dict(node=hex(node),in_vector=wrapper in wrappers,**asset(wrapper)))
        # Exact structural traversal used by native increment 0xb74a10.
        right=word(node)
        if right:
            node=right
            for _ in range(4096):
                left=word(node+4)
                if not left:break
                node=left
            else:raise ValueError('Tree traversal bound')
        else:
            current=node;parent=word(node+8)
            for _ in range(4096):
                if current!=word(parent):break
                current=parent;parent=word(parent+8)
            else:raise ValueError('Tree ascent bound')
            node=parent if word(current)!=parent else current
    return dict(store=hex(store),vector_count=len(vector),tree_count=len(tree),vector=vector,tree=tree,
                vector_missing_from_tree=[hex(x) for x in wrappers if x not in {int(r['wrapper'],0) for r in tree}],mutations=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    h=k.OpenProcess(0x410,False,a.pid)
    if not h:raise c.WinError(c.get_last_error())
    try:
        path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(h,0,path,c.byref(size)):raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Unsupported game')
        def read(p,n):
            if not n:return b''
            buf=c.create_string_buffer(n);got=c.c_size_t()
            if not k.ReadProcessMemory(h,p,buf,n,c.byref(got)) or got.value!=n:raise ValueError('Read failed '+hex(p))
            return buf.raw
        report=dict(pid=a.pid,**inspect_indexes(read));a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(a.output);print(json.dumps({k:v for k,v in report.items() if k not in ['vector','tree']},ensure_ascii=False))
    finally:k.CloseHandle(h)
if __name__=='__main__':main()
