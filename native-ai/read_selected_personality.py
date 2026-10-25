"""Read-only effective AI personality, cross-checked with native store membership.

This reads the effective in-match personality, not a lobby ordinal or display
name. No function calls, process writes, hooks or identity guesses from names.
"""
import argparse,ctypes as c,datetime,hashlib,json,struct,sys,time
from pathlib import Path
from ctypes import wintypes as w
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from probe import k,EXPECTED

def inspect_player(read,player):
    def word(address):return struct.unpack('<I',read(address,4))[0]
    if word(player)!=0xc5bce0:raise ValueError('Player vtable mismatch')
    index=word(player+0x20);side=word(player+0x10);ai=word(player+0x90)
    if not 0<=index<16 or not side:raise ValueError('Invalid Player index/side')
    if not ai or word(ai)!=0xc60f60:raise ValueError('No expected AIPlayer')
    if word(ai+8)!=player or word(ai+0x8a8)!=player:raise ValueError('AIPlayer owner links mismatch')
    personality=word(ai+0x8b0)
    store=word(0xce98ec)
    if not store or word(store)!=0xc606b8:raise ValueError('Personality store mismatch')
    start,end=word(store+0x24),word(store+0x28)
    if not 0<=end-start<=16384 or (end-start)%4:raise ValueError('Invalid personality store bounds')
    wrappers=list(struct.unpack('<'+'I'*((end-start)//4),read(start,end-start)))
    if not personality or wrappers.count(personality)!=1:raise ValueError('Effective personality not uniquely registered')
    ident=word(personality+0x18);data=word(personality)
    if sum(word(x+0x18)==ident for x in wrappers)!=1:raise ValueError('Ambiguous native instance ID')
    count,array=word(data+0xec),word(data+0xf0)
    if not 1<=count<=32:raise ValueError('Invalid effective Side array')
    sides=list(struct.unpack('<'+'I'*count,read(array,4*count)))
    if 0 in sides or side not in sides:raise ValueError('Effective personality Side does not match Player template')
    # A match may end during these reads. Reject changed chains rather than
    # persist a mixed-session identity. This remains a non-atomic sample.
    if word(player+0x90)!=ai or word(ai+0x8b0)!=personality or word(store+0x24)!=start or word(store+0x28)!=end:
        raise ValueError('Identity changed while reading; retry with a fresh session sample')
    return dict(player=hex(player),player_index=index,player_template=hex(side),ai_player=hex(ai),
                personality_wrapper=hex(personality),personality_data=hex(data),instance_id=hex(ident),
                side_references=[hex(x) for x in sides],store=hex(store),store_count=len(wrappers),
                store_membership_verified=True,side_matches_player=True,mutations=False)

def resolve_registry(native,registry,session):
    matches=[(commander,asset) for commander in registry.get('commanders',[])
             for asset in commander.get('assets',[])
             if int(asset['instance_id'],0)==int(native['instance_id'],0)]
    if len(matches)!=1:raise ValueError('Native ID has no unique commander UUID in registry')
    commander,asset=matches[0]
    package=registry.get('package_sha256','').lower()
    package_matches=bool(package and session and package==session.get('mod_sha256','').lower())
    return dict(commander_id=commander['id'],display_name=commander['name'],
                connection_id=commander['connection_id'],asset_id=asset['asset_id'],side=asset['side'],
                identity_revision=registry['identity_revision'],registry_revision=registry['registry_revision'],
                compiled_ids_verified=registry.get('compiled_ids_verified') is True,
                session_package_matches=package_matches,
                personality_binding_verified=package_matches and registry.get('compiled_ids_verified') is True,
                game_sync_verified=False,strategic_control_verified=False)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid',required=True,type=int);ap.add_argument('--player',required=True,type=lambda x:int(x,0))
    ap.add_argument('--registry',type=Path);ap.add_argument('--session',type=Path);ap.add_argument('--output',type=Path)
    a=ap.parse_args();session=json.loads(a.session.read_text(encoding='utf-8-sig')) if a.session else None
    if session and session['pid']!=a.pid:raise ValueError('Session PID mismatch')
    handle=k.OpenProcess(0x410,False,a.pid)
    if not handle:raise c.WinError(c.get_last_error())
    try:
        created,exited,kernel,user=w.FILETIME(),w.FILETIME(),w.FILETIME(),w.FILETIME()
        k.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
        if not k.GetProcessTimes(handle,c.byref(created),c.byref(exited),c.byref(kernel),c.byref(user)):raise c.WinError(c.get_last_error())
        creation=(created.dwHighDateTime<<32)|created.dwLowDateTime
        if session:
            recorded=session.get('start_time') or session.get('started')
            if not recorded:raise ValueError('Session missing process start time')
            actual_time=creation/10000000-11644473600
            if abs(datetime.datetime.fromisoformat(recorded).timestamp()-actual_time)>0.001:raise ValueError('Session process start time mismatch')
        path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(handle,0,path,c.byref(size)):raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Unsupported executable')
        def read(address,length):
            if not length:return b''
            buf=c.create_string_buffer(length);got=c.c_size_t()
            if not k.ReadProcessMemory(handle,address,buf,length,c.byref(got)) or got.value!=length:raise ValueError('Read failed '+hex(address))
            return buf.raw
        # Pinned signatures prove the selected build retains the constructor
        # source/destination fields used here; they are never called.
        if read(0x8d5727,6)!=bytes.fromhex('89beb0080000') or read(0x844a3f,6)!=bytes.fromhex('898690000000'):
            raise ValueError('Identity constructor signatures mismatch')
        native=inspect_player(read,a.player)
        report=dict(pid=a.pid,process_creation_filetime=creation,sampled_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                    executable_sha256=EXPECTED,session_id=session.get('session_id') if session else None,
                    native=native,game_sync_verified=False,note='Effective in-match personality; non-atomic read; no command issued.')
        if a.registry:
            registry=json.loads(a.registry.read_text(encoding='utf-8-sig'))
            report['binding']=resolve_registry(native,registry,session)
            report['registry_sha256']=hashlib.sha256(a.registry.read_bytes()).hexdigest()
        out=a.output or ROOT/('selected-personality-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(out);print(json.dumps(report,ensure_ascii=False))
    finally:k.CloseHandle(handle)
if __name__=='__main__':main()
