"""Version/session-pinned read-only production-interface and resource sampler.

No remote writes, injection, game calls, queue mutation, or model calls occur.
Opaque words are explicitly not interpreted as a production queue.
"""
import argparse, ctypes as c, hashlib, json, math, struct, sys, time
from ctypes import wintypes as w
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from probe import k, EXPECTED
from session_package import verify_session_package

k.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
k.GetProcessTimes.restype=w.BOOL

class Memory:
    def __init__(self,pid,session):
        self.pid=pid;self.handle=k.OpenProcess(0x410,False,pid)
        if not self.handle:raise c.WinError(c.get_last_error())
        path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(self.handle,0,path,c.byref(size)):raise c.WinError(c.get_last_error())
        self.path=path.value
        if Path(self.path).name.lower()!='ra3_1.12.game' or hashlib.sha256(Path(self.path).read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Unsupported game executable')
        times=[w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(self.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())
        ticks=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        self.start_timestamp=(ticks-116444736000000000)/10000000
        recorded=datetime.fromisoformat(session['start_time']).timestamp()
        if abs(self.start_timestamp-recorded)>0.001:raise RuntimeError('PID startup identity mismatch')
        if session['pid']!=pid:raise RuntimeError('Session PID mismatch')
    def read(self,address,n):
        if n==0:return b''
        if not 0x10000<=address<0x100000000 or not 0<n<=0x2000:raise RuntimeError('Read bounds')
        buf=c.create_string_buffer(n);got=c.c_size_t()
        if not k.ReadProcessMemory(self.handle,address,buf,n,c.byref(got)) or got.value!=n:raise RuntimeError('Read unavailable')
        return buf.raw
    def u32(self,p):return struct.unpack('<I',self.read(p,4))[0]
    def i32(self,p):return struct.unpack('<i',self.read(p,4))[0]
    def f32(self,p):return struct.unpack('<f',self.read(p,4))[0]
    def close(self):k.CloseHandle(self.handle)

def module_pointer(p):return 0x400000<=p<0xd3b000

def decode_this_adjustor(code,entry):
    """Recognize only literal common this-adjustor+jmp encodings, not arbitrary code."""
    if len(code)>=8 and code[:2]==b'\x83\xe9' and code[3]==0xe9:
        amount=struct.unpack('<b',code[2:3])[0]
        return -amount,entry+8+struct.unpack('<i',code[4:8])[0]
    if len(code)>=11 and code[:2]==b'\x81\xe9' and code[6]==0xe9:
        return -struct.unpack('<i',code[2:6])[0],entry+11+struct.unpack('<i',code[7:11])[0]
    if len(code)>=8 and code[:2]==b'\x83\xc1' and code[3]==0xe9:
        return struct.unpack('<b',code[2:3])[0],entry+8+struct.unpack('<i',code[4:8])[0]
    return None

def queue_candidate(mem,full_module):
    """Provisional schema from the native xfer routine; never asserts live production."""
    if not module_pointer(mem.u32(full_module)):raise RuntimeError('No module vtable')
    head,tail=mem.u32(full_module+0x34),mem.u32(full_module+0x38)
    if bool(head)!=bool(tail):raise RuntimeError('Inconsistent queue endpoints')
    nodes=[];seen=set();node=head;previous=0
    while node:
        if node%4 or node in seen or len(nodes)>=128:raise RuntimeError('Queue cycle/alignment/bounds')
        seen.add(node);raw=mem.read(node,0x70)
        if struct.unpack_from('<I',raw,4)[0]!=full_module:raise RuntimeError('Queue node module link mismatch')
        kind=struct.unpack_from('<I',raw,0xc)[0]
        if kind not in (1,2):raise RuntimeError('Unknown provisional production kind')
        back=struct.unpack_from('<I',raw,0x58)[0]
        if back!=previous:raise RuntimeError('Queue back-link mismatch')
        template=struct.unpack_from('<I',raw,0x10 if kind==1 else 0x14)[0]
        template_hash=mem.u32(template+8) if template else 0
        nodes.append(dict(address=hex(node),kind_raw=kind,kind_candidate='unit' if kind==1 else 'upgrade',template=hex(template),template_hash=hex(template_hash),production_id_raw=struct.unpack_from('<I',raw,0x18)[0],float_plus_1c=struct.unpack_from('<f',raw,0x1c)[0],float_plus_20=struct.unpack_from('<f',raw,0x20)[0],raw_plus_24=struct.unpack_from('<I',raw,0x24)[0],raw_plus_28=struct.unpack_from('<I',raw,0x28)[0],raw_plus_2c=struct.unpack_from('<I',raw,0x2c)[0],native_cost_plus_30=struct.unpack_from('<I',raw,0x30)[0],paid_accumulator_plus_68=struct.unpack_from('<I',raw,0x68)[0],raw=raw.hex()))
        previous=node;node=struct.unpack_from('<I',raw,0x54)[0]
    if previous!=tail:raise RuntimeError('Queue tail mismatch')
    return dict(schema='provisional_native_xfer',module=hex(full_module),head=hex(head),tail=hex(tail),nodes=nodes,semantics_verified_by_live_production=False)

def read_owner(mem,owner,index):
    if mem.u32(owner)!=0xc5bce0 or mem.u32(owner+0x20)!=index:raise RuntimeError('Player identity mismatch')
    ai=mem.u32(owner+0x90)
    if not ai or mem.u32(ai)!=0xc60f60:raise RuntimeError('Selected owner has no validated native AIPlayer')
    result=dict(address=hex(owner),owner_index=index,ai_player=hex(ai),computer_identity_evidence='AIPlayer vtable 0xc60f60',resource_available=False)
    start,end=mem.u32(owner+0xe4),mem.u32(owner+0xe8)
    result['resource_vector']=[hex(start),hex(end)]
    if start and 4<=end-start<=64 and (end-start)%4==0:
        resource=mem.u32(start)
        raw4,raw14=mem.i32(resource+4),mem.i32(resource+0x14)
        result.update(resource_available=True,resource=hex(resource),raw_plus_4=raw4,raw_plus_14=raw14,display_sum=raw4+raw14,
                      resource_evidence='Static native UI chain 0x83be10(index0), +4 plus +0x14; no transaction attribution')
    return result

def read_factory(mem,candidate,owner):
    thing=int(candidate['address'],0)
    if mem.u32(thing)!=0xc4db60 or mem.u32(thing+0x418)!=owner or mem.u32(mem.u32(thing+4)+8)!=int(candidate['type_hash'],0):raise RuntimeError('Factory candidate identity changed')
    body=mem.u32(thing+0x33c);hp=mem.f32(body+4)
    if not math.isfinite(hp) or hp<=0:raise RuntimeError('Factory not alive')
    result=dict(address=hex(thing),template=candidate['catalog']['template'],hp=hp,xyz=struct.unpack('<fff',mem.read(thing+0x38,12)),production_interface_available=False,thing_plus_310=hex(mem.u32(thing+0x310)),thing_plus_3c0=hex(mem.u32(thing+0x3c0)))
    wrapper=mem.u32(thing+0x3b4)
    result['interface_wrapper']=hex(wrapper)
    if not wrapper:return result
    interface=mem.u32(wrapper+0x14)
    result['interface']=hex(interface)
    if not interface:return result
    vtable=mem.u32(interface)
    if not module_pointer(vtable):return result
    build=mem.u32(vtable+0x24)
    if not module_pointer(build):return result
    result.update(production_interface_available=True,vtable=hex(vtable),unit_build_function=hex(build),unit_build_first_64_bytes=mem.read(build,64).hex(),opaque_interface_first_0x200_bytes=mem.read(interface,0x200).hex(),queue_schema_verified=False)
    adjusted=decode_this_adjustor(mem.read(build,16),build)
    known_prefix=bytes.fromhex('81eca8000000538bd98b43dc8b5058558d6bdc')
    if build==0x723f50 and mem.read(build,len(known_prefix))==known_prefix:
        adjusted=(-0x24,build)
    if adjusted:
        delta,implementation=adjusted;result['this_adjustor_candidate']=dict(delta=delta,implementation=hex(implementation))
        try:result['queue_candidate']=queue_candidate(mem,interface+delta)
        except RuntimeError as error:result['queue_candidate_error']=str(error)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--owner-index',type=int,default=3);ap.add_argument('--samples',type=int,default=1);ap.add_argument('--interval',type=float,default=1)
    args=ap.parse_args()
    if not 1<=args.samples<=60 or not .1<=args.interval<=10:raise ValueError('Sample bounds')
    session_bytes=args.session.read_bytes();session=json.loads(session_bytes.decode('utf-8-sig'))
    if not session.get('session_id'):raise RuntimeError('Explicit game session ID required')
    package=verify_session_package(session)
    snapshot=json.loads(args.snapshot.read_text(encoding='utf-8-sig'))
    if snapshot['pid']!=session['pid'] or snapshot['sha256']!=EXPECTED:raise RuntimeError('Snapshot identity mismatch')
    owners={int(x['owner_address'],0) for x in snapshot['candidates'] if x['owner_index_candidate']==args.owner_index}
    if len(owners)!=1:raise RuntimeError('Require exactly one selected owner')
    owner=next(iter(owners))
    factories=[x for x in snapshot['candidates'] if int(x['owner_address'],0)==owner and x['catalog'].get('cls')==5 and any(part in x['catalog'].get('template','') for part in ['Barracks','WarFactory','NavalYard','Airfield','ConstructionYard'])]
    memory=Memory(session['pid'],session);samples=[];initial_ai=None;started=time.monotonic()
    target=ROOT/('observation-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
    try:
        for index in range(args.samples):
            if args.session.read_bytes()!=session_bytes:raise RuntimeError('Active session record changed')
            player=read_owner(memory,owner,args.owner_index)
            if initial_ai is None:initial_ai=player['ai_player']
            elif initial_ai!=player['ai_player']:raise RuntimeError('Native AI identity changed; possible new match')
            outputs=[]
            for factory in factories:
                try:outputs.append(read_factory(memory,factory,owner))
                except RuntimeError as error:outputs.append(dict(address=factory['address'],read_error=str(error)))
            samples.append(dict(index=index,elapsed_wall_seconds=round(time.monotonic()-started,3),player=player,factories=outputs))
            report=dict(session_id=session['session_id'],pid=session['pid'],process_start=session['start_time'],mod_sha256=session['mod_sha256'],executable_sha256=EXPECTED,source_snapshot=str(args.snapshot.resolve()),source_snapshot_sha256=hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),mutations=False,game_session_independently_verified=False,queue_verified=False,spend_verified=False,produced_unit_verified=False,samples=samples,note='Session association is supplied by orchestrator; live-match tick identity and game time are not yet independently available. Opaque structures are not a queue schema. Balance deltas do not attribute spend.')
            target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(dict(sample=index,resource_available=player['resource_available'],factory_interfaces=sum(x.get('production_interface_available',False) for x in outputs),report=str(target)),ensure_ascii=False),flush=True)
            if index+1<args.samples:time.sleep(args.interval)
    finally:memory.close()
if __name__=='__main__':main()
