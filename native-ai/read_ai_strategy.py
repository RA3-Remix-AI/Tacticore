"""Read-only strategic/selector candidate telemetry for a qualified Player."""
import argparse,ctypes as c,hashlib,json,struct,sys,time
from pathlib import Path
from ctypes import wintypes as w
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent))
from probe import k,EXPECTED
from read_selected_personality import inspect_player
DIRECTIVES=['Normal','Assault','HoldPosition','HoldObject','Help']
FEEDBACK=['Normal','BuildingForces','SendingForces','InCombat','InDanger','Attacking','Defending','Expanding','Assault','HoldPosition','HoldObject','LowOnCredits','LowOnPower','OnGuard']
def sample(read,player):
    def word(p):return struct.unpack('<I',read(p,4))[0]
    native=inspect_player(read,player);ai=int(native['ai_player'],0);directive=word(ai+0x8ec);feedback=word(ai+0x8f8)
    row=dict(native=native,coop_ai_index_raw=hex(word(player+0x94)),directive_raw=directive,
             directive=DIRECTIVES[directive] if directive<len(DIRECTIVES) else 'unknown',
             feedback_raw=feedback,feedback=FEEDBACK[feedback] if feedback<len(FEEDBACK) else 'unknown',
             directive_expiry_frame_raw=word(ai+0x8f4),directive_change_frame=word(ai+0x8fc),
             mutations=False,strategic_control_verified=False)
    tactical=word(ai+0x6f8)
    if tactical:
        selector=word(tactical+0x34);row['tactical']=hex(tactical);row['selector']=hex(selector)
        if selector:
            start,end=word(selector+8),word(selector+0xc)
            row['selector_lock_raw']=struct.unpack('<H',read(selector+0x30,2))[0]
            row['priority_mode_flags_raw']=list(read(selector+0x24,2));row['automatic_scheme_raw']=word(selector+0x20)
            if 0<=end-start<=512 and (end-start)%8==0:
                values=struct.unpack('<'+'I'*((end-start)//4),read(start,end-start)) if end>start else []
                # 0x8af950 compares entry+4 with enemyIndex when removing one;
                # native sorted entries are (priority, playerIndex), not reverse.
                row['priority_entries']=[dict(priority=values[i],player_index=values[i+1]) for i in range(0,len(values),2)]
            else:row['priority_entries_error']='Unvalidated vector layout/bounds'
    return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);ap.add_argument('--player',type=lambda x:int(x,0),required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    h=k.OpenProcess(0x410,False,a.pid)
    if not h:raise c.WinError(c.get_last_error())
    try:
        path=c.create_unicode_buffer(32768);n=w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(h,0,path,c.byref(n)):raise c.WinError(c.get_last_error())
        if hashlib.sha256(Path(path.value).read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Unsupported executable')
        def read(p,size):
            if not size:return b''
            buf=c.create_string_buffer(size);got=c.c_size_t()
            if not k.ReadProcessMemory(h,p,buf,size,c.byref(got)) or got.value!=size:raise ValueError('Read failed '+hex(p))
            return buf.raw
        report=dict(pid=a.pid,sampled_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**sample(read,a.player));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(a.output);print(json.dumps(report,ensure_ascii=False))
    finally:k.CloseHandle(h)
if __name__=='__main__':main()
