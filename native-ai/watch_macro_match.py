"""Retain native outcome/lifecycle transitions before match-end cleanup erases them."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'production'),str(ROOT/'native-ai')]
from observe_production import Memory,k
from session_package import verify_session_package
from read_match_state import snapshot


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--seconds',type=int,default=1800);args=p.parse_args()
    if not 1<=args.seconds<=3600:raise ValueError('bounded_match_watch_duration')
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_local_match_watch_required')
    raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));verify_session_package(session)
    memory=Memory(session['pid'],session);created=[w.FILETIME() for _ in range(4)]
    try:
        if not k.GetProcessTimes(memory.handle,*[c.byref(x) for x in created]):raise c.WinError(c.get_last_error())
        if created[0].dwLowDateTime|created[0].dwHighDateTime<<32!=session.get('process_creation_filetime'):
            raise ValueError('match_watch_exact_process_creation')
        out.mkdir(parents=True);sources=out/'source';sources.mkdir()
        pins=[]
        for index,path in enumerate([Path(__file__),ROOT/'native-ai/read_match_state.py',ROOT/'production/observe_production.py',ROOT/'production/session_package.py',ROOT/'probe.py',args.session]):
            target=sources/(str(index)+'-'+path.name);shutil.copy2(path,target)
            pins.append(dict(path=str(path.resolve()),copy=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        (out/'preflight.json').write_text(json.dumps(dict(session_id=session['session_id'],pid=session['pid'],process_creation_filetime=session['process_creation_filetime'],mod_sha256=session['mod_sha256'],sources=pins),indent=2)+'\n',encoding='utf-8')
        started=time.monotonic();last=None;had_frames=False;previous_frame=0;reason='observation_deadline';records=0;errors=0
        with (out/'native-match-transitions.jsonl').open('x',encoding='utf-8') as stream:
            while time.monotonic()-started<args.seconds:
                if args.session.read_bytes()!=raw:reason='session_file_changed';break
                if (args.session.resolve().parent/'fixture-ended.json').exists():reason='owned_research_fixture_ended';break
                try:
                    value=snapshot(memory.read);frame=value['simulation_frame']
                    signature=json.dumps({key:v for key,v in value.items() if key!='simulation_frame'},sort_keys=True)
                    if signature!=last or frame//15!=previous_frame//15 or not frame:
                        stream.write(json.dumps(dict(elapsed_seconds=round(time.monotonic()-started,3),**value))+'\n');stream.flush();records+=1;last=signature
                    if frame:had_frames=True
                    if had_frames and frame==0:reason='native_lifecycle_frame_reset';break
                    if frame and previous_frame and frame<previous_frame:reason='frame_rollback';break
                    previous_frame=frame
                except (ValueError,RuntimeError) as error:
                    errors+=1;stream.write(json.dumps(dict(read_error=str(error),elapsed_seconds=round(time.monotonic()-started,3)))+'\n');stream.flush()
                time.sleep(.2)
        (out/'report.json').write_text(json.dumps(dict(session_id=session['session_id'],pid=session['pid'],reason=reason,
            records=records,read_errors=errors,elapsed_seconds=round(time.monotonic()-started,3),had_live_frames=had_frames,
            natural_settlement_verified=False,winner_verified=False,model_calls_by_watcher=0,
            whole_session_model_calls=None,native_calls=0,process_writes=0),indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(output=str(out),reason=reason,records=records,read_errors=errors)))
    finally:memory.close()


if __name__=='__main__':main()
