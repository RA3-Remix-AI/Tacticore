"""Version-pinned, read-only native frame/pause/result evidence.

Result fields are evidence, not an automatic match-ended verdict; slot/player
mapping and lifecycle must be checked against the actual game result screen.
"""
import argparse,ctypes as c,hashlib,json,struct,sys,time
from pathlib import Path
from ctypes import wintypes as w
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent))
from probe import k,EXPECTED

def snapshot(read):
    def word(p):return struct.unpack('<I',read(p,4))[0]
    logic=word(0xcd8ce4)
    if not logic or word(logic)!=0xbeb630:raise ValueError('GameLogic signature mismatch')
    slots=[]
    for index in range(6):
        fields=list(struct.unpack('<8I',read(0xce3378+index*32,32)))
        slots.append(dict(native_index=index,quit_frame=fields[1],defeat_frame=fields[2],victory_frame=fields[3],
                          disconnect_frame_candidate=fields[4],raw=fields,
                          outcome_evidence='victory_frame_recorded' if fields[3] else 'defeat_frame_recorded' if fields[2] else 'none'))
    result=dict(game_logic=hex(logic),simulation_frame=word(logic+0x50),
                pause_type_candidate=word(logic+0x15c),pause_flag_candidate=read(logic+0x160,1)[0],
                mode_raw=word(logic+0x148),logic_flag_0x44=read(logic+0x44,1)[0],
                result_records=slots,match_ended_verified=False,mutations=False)
    manager=word(0xcdd1a0)
    if manager and word(manager)==0xc07ab8:
        participants=[]
        for index in range(20):
            player=word(manager+0x48+4*index)
            if player:
                try:
                    participants.append(dict(manager_index=index,player=hex(player),
                                             player_index=word(player+0x20),player_vtable=hex(word(player)),
                                             defeated_flag_raw=read(manager+0xa0+index,1)[0]))
                except ValueError:participants.append(dict(manager_index=index,player=hex(player),read_failed=True))
        result['victory_conditions']=dict(address=hex(manager),participants=participants,
                                          flags_b4_b6_raw=list(read(manager+0xb4,3)),
                                          flags_c8_cd_raw=list(read(manager+0xc8,6)),
                                          native_index_c0_raw=word(manager+0xc0),raw_c4=word(manager+0xc4))
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--seconds',type=float,default=0)
    ap.add_argument('--interval',type=float,default=0.2);ap.add_argument('--label',default='');a=ap.parse_args()
    if not 0<=a.seconds<=30 or not 0.05<=a.interval<=5:raise ValueError('Bounded sampling only: seconds<=30, interval>=.05')
    h=k.OpenProcess(0x410,False,a.pid)
    if not h:raise c.WinError(c.get_last_error())
    try:
        path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(h,0,path,c.byref(size)):raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Unsupported executable')
        def read(p,n):
            buf=c.create_string_buffer(n);got=c.c_size_t()
            if not k.ReadProcessMemory(h,p,buf,n,c.byref(got)) or got.value!=n:raise ValueError('Read failed '+hex(p))
            return buf.raw
        if read(0x4e062e,7)!=bytes.fromhex('c7470c00000000') or read(0x600685,6)!=bytes.fromhex('89908433ce00'):
            raise ValueError('Pinned pause/result signatures mismatch')
        start=time.monotonic();samples=[]
        while True:
            samples.append(dict(wall_ms=round((time.monotonic()-start)*1000),**snapshot(read)))
            if time.monotonic()-start>=a.seconds:break
            time.sleep(max(0,min(a.interval,a.seconds-(time.monotonic()-start))))
        report=dict(pid=a.pid,label=a.label,sampled_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                    executable_sha256=EXPECTED,samples=samples,mutations=False)
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(a.output);print(json.dumps(samples[-1]))
    finally:k.CloseHandle(h)
if __name__=='__main__':main()
