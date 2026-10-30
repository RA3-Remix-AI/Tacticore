"""Manager-only high-level pause/enable/expiry; no model, no precise orders."""
import argparse
import importlib.util
import json
import os
import shutil
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'native-ai/strategic-manager-runtime-v4'))
from client import Probe
from build import verify,sha
sys.path.insert(0,str(ROOT/'acceptance'))
from run_guarded_strategic_trial_v1 import SourceLocks,record_owner

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','output'):p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();manifest=verify(args.build);session=json.loads(args.session.read_bytes());output=args.output.resolve()
    if output.exists():raise ValueError('fresh_manager_field_required')
    pins=dict(manifest['input_pins'])
    for path in [Path(__file__).resolve(),args.session.resolve(),args.build.resolve()/'build-manifest.json',args.build.resolve()/'profile.h',*(args.build.resolve()/name for name in manifest['artifacts']),Path(session['mod_big'])]:pins[str(path)]=sha(path)
    locks=SourceLocks(pins);trial=None;started=time.monotonic();error=None;returned=False
    try:
        if any(sha(path)!=expected for path,expected in pins.items()):raise ValueError('manager_source_changed_before_locks')
        record_owner(session,'field_running',pins,trial_output=str(output),transport='manager_only_v4')
        trial=Probe.__new__(Probe)
        trial.__init__(args.session,args.build,output)
        source=output/'source';source.mkdir();copies=[]
        objects=ROOT/'reports/strategic-source-objects';objects.mkdir(exist_ok=True)
        for index,(path,expected) in enumerate(pins.items()):
            target=source/(str(index)+'-'+Path(path).name);obj=objects/expected
            if not obj.exists():
                temp=objects/(expected+'.prepared');shutil.copy2(path,temp)
                if sha(temp)!=expected:raise ValueError('manager_archive_changed')
                temp.replace(obj)
            if sha(obj)!=expected:raise ValueError('manager_archive_object_corrupt')
            os.link(obj,target)
            copies.append(dict(path=path,copy=target.name,sha256=expected))
        (output/'source-pins.json').write_text(json.dumps(copies,indent=2)+'\n',encoding='utf8')
        trial.event('research_started',runner_sha256=sha(__file__),model_calls=0,precise_orders=0,formal_games=0)
        # Bounded intent family tests. Native AI retains all selections/details.
        for gate in (0,1):
            trial.command('pause',gate,120,10000)
            for _ in range(3):trial.event('manager_observation',native=trial.status());time.sleep(1)
            trial.command('enable',gate,60,10000)
            expiry=trial.status()['gates'][gate]['deadline_frame'];deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                status=trial.status();trial.event('awaiting_expiry',native=status)
                if status['last_frame']>expiry and status['gates'][gate]['phase']==4:break
                if status['phase']!=1:raise ValueError('manager_native_became_unavailable')
                time.sleep(1)
            else:raise ValueError('manager_expiry_baseline_not_observed')
        trial.event('research_sequence_complete',native=trial.status(),strategic_effect_verified=False)
    except BaseException as exc:
        error=type(exc).__name__+':'+str(exc)
        if trial and trial.log:trial.event('research_failure',reason=error)
        raise
    finally:
        if trial is not None:
            try:trial.close();returned=True
            except BaseException:
                record_owner(session,'field_cleanup_pending',pins,trial_output=str(output),failure=error)
                # Never unlock an unresolved owned trial or claim successful STOP.
                while trial.state is not None and trial.state.phase not in (2,4):time.sleep(1)
                trial.close();returned=True
        if returned or trial is None:
            record_owner(session,'implementing',{},last_trial=str(output),last_native_release_verified=(output/'independent-release.json').exists(),game_still_open=True)
            locks.close()
        print(json.dumps(dict(elapsed_seconds=round(time.monotonic()-started,2),native_return_review=(output/'independent-release.json').exists(),failure=error,formal_games=0)),flush=True)

if __name__=='__main__':main()
