"""Independent, read-only native settlement recorder for observer AI matches."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent/'production'),str(ROOT.parent/'native-ai')]
from observe_production import Memory
from read_match_state import snapshot

def atomic(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
    for attempt in range(25):
        try:temporary.replace(path);return
        except PermissionError:
            if attempt==24:raise
            time.sleep(.02)

class Recorder:
    def __init__(self):self.last_live=None;self.candidate=None;self.ended=False
    def observe(self,state):
        frame=state.get('simulation_frame',0)
        participants=state.get('victory_conditions',{}).get('participants',[])
        active=frame>0 and bool(participants)
        if active:self.last_live=state
        records=state.get('result_records',[])
        signalled=any(x.get('defeat_frame') or x.get('victory_frame') for x in records) or any(x.get('defeated_flag_raw') for x in participants)
        if active and signalled:self.candidate=state
        if self.last_live is not None and frame==0 and state.get('mode_raw')==9:self.ended=True
        return dict(active=active,result_candidate=active and signalled,lifecycle_ended=self.ended)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--max-wall-seconds',type=int,default=1800)
    args=parser.parse_args()
    if not 10<=args.max_wall_seconds<=7200:raise ValueError('Wall-time bound')
    raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'))
    output=Path(session['run_directory'])/'settlement-watch';output.mkdir(parents=True,exist_ok=True)
    memory=Memory(session['pid'],session);recorder=Recorder();started=time.monotonic();previous=None;count=0;reason='time_limit'
    try:
        while time.monotonic()-started<args.max_wall_seconds:
            if args.session.read_bytes()!=raw:reason='session_changed';break
            state=snapshot(memory.read);count+=1
            flags=recorder.observe(state)
            key=json.dumps([state.get('mode_raw'),state.get('result_records'),state.get('victory_conditions',{}).get('participants')],sort_keys=True)
            if key!=previous:
                with (output/'events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(wall_seconds=time.monotonic()-started,state=state,**flags))+'\n')
                previous=key
            if flags['active']:atomic(output/'last-live.json',state)
            if flags['result_candidate']:atomic(output/'result-candidate.json',state)
            if recorder.ended:reason='native_lifecycle_ended';break
            time.sleep(.1)
    except (ValueError,RuntimeError,OSError) as error:
        reason='native_unavailable';atomic(output/'error.json',{'type':type(error).__name__})
    finally:memory.close()
    final=dict(session_id=session['session_id'],pid=session['pid'],samples=count,reason_code=reason,had_live_match=recorder.last_live is not None,had_native_result_candidate=recorder.candidate is not None,native_lifecycle_ended=recorder.ended,visual_confirmation_required=True,mutations=False)
    atomic(output/'status.json',final);print(json.dumps(final))

if __name__=='__main__':main()
