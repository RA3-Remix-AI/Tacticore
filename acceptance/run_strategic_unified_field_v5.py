"""One owned unified research controller. No model or precise game orders."""
import argparse
import json
import os
from pathlib import Path
import sys
import shutil
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'native-ai/strategic-unified-runtime-v5'))
from client import Probe
from build import verify,sha
sys.path.insert(0,str(ROOT/'acceptance'))
from run_guarded_strategic_trial_v1 import SourceLocks,record_owner

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--mode',choices=['normal','host_loss','stop_held'],required=True)
    args=parser.parse_args();manifest=verify(args.build);session=json.loads(args.session.read_bytes());output=args.output.resolve()
    pins=dict(manifest['input_pins'])
    for path in [Path(__file__).resolve(),args.session.resolve(),args.build.resolve()/'build-manifest.json',args.build.resolve()/'profile.h',*(args.build.resolve()/name for name in manifest['artifacts']),Path(session['mod_big'])]:pins[str(path)]=sha(path)
    locks=SourceLocks(pins);trial=None;failure=None
    try:
        if any(sha(path)!=expected for path,expected in pins.items()):raise ValueError('unified_source_changed_before_lock')
        record_owner(session,'field_running',pins,trial_output=str(output),transport='unified_v5',mode=args.mode)
        trial=Probe.__new__(Probe);trial.__init__(args.session,args.build,output)
        source=output/'source';source.mkdir();objects=ROOT/'reports/strategic-source-objects';objects.mkdir(exist_ok=True);copies=[]
        for index,(path,expected) in enumerate(pins.items()):
            obj=objects/expected
            if not obj.exists():
                temp=objects/(expected+'.prepared');shutil.copy2(path,temp)
                if sha(temp)!=expected:raise ValueError('unified_source_archive_changed')
                temp.replace(obj)
            if sha(obj)!=expected:raise ValueError('unified_source_archive_corrupt')
            target=source/(str(index)+'-'+Path(path).name);os.link(obj,target)
            copies.append(dict(path=path,copy=target.name,sha256=expected))
        (output/'source-copies.json').write_text(json.dumps(copies,indent=2)+'\n',encoding='utf8')
        (output/'field-runner.py').write_bytes(Path(__file__).read_bytes())
        (output/'source-pins.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8')
        trial.event('unified_research_started',mode=args.mode,runner_sha256=sha(__file__),model_calls=0,precise_orders=0,formal_games=0)
        if args.mode=='normal':
            trial.apply(['budgetarmy'],120)
            trial.command('pause',0,120,10000);trial.command('pause',1,120,10000)
            for _ in range(3):trial.event('combined_native_readback',native=trial.status());time.sleep(1)
            trial.command('enable',0,120,10000);trial.command('enable',1,120,10000)
            deadline=time.monotonic()+14
            while time.monotonic()<deadline:
                status=trial.status();trial.event('awaiting_combined_expiry',native=status)
                if status['phase']!=1:raise ValueError('unified_became_unavailable')
                if status['applied_mask']==0 and all(gate['phase']==4 for gate in status['gates']):break
                time.sleep(.5)
            else:raise ValueError('unified_expiry_not_observed')
            trial.apply(['scout','budgeteconomy'],1800)
            trial.command('pause',0,1800,120000);trial.command('pause',1,1800,120000)
        else:
            trial.apply(['budgetarmy'],1800)
            trial.command('pause',0,1800,120000);trial.command('pause',1,1800,120000)
        trial.event('flags_and_managers_held',native=trial.status())
        if args.mode=='host_loss':
            trial.stopped.set();trial.heartbeat.join(timeout=2)
            trial.event('owned_publisher_and_helper_loss',helper_pid=trial.host.pid)
            trial.host.kill();trial.host.wait(timeout=5)
            deadline=time.monotonic()+14
            while time.monotonic()<deadline:
                status=trial.status();trial.event('readonly_aggregate_return_wait',native=status)
                if status['phase']==2:break
                time.sleep(.5)
            else:raise ValueError('unified_watchdog_return_unresolved')
        trial.close()
    except BaseException as exc:
        failure=type(exc).__name__+':'+str(exc)
        if trial and trial.log:trial.event('unified_research_failed',failure=failure)
        raise
    finally:
        if trial is not None:
            try:trial.close()
            except BaseException:
                record_owner(session,'field_cleanup_pending',pins,trial_output=str(output),failure=failure)
                while trial.state is not None and trial.state.phase not in (2,4):time.sleep(1)
                trial.close()
        record_owner(session,'implementing',{},last_trial=str(output),last_native_release_verified=(output/'independent-release.json').exists(),game_still_open=True)
        locks.close()
        print(json.dumps(dict(mode=args.mode,failure=failure,aggregate_return_review=(output/'independent-release.json').exists(),formal_games=0)))

if __name__=='__main__':main()
