"""Read-only replay budget observations, kept separate from the original match."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'production'),str(ROOT/'native-ai')]
from observe_production import Memory
from read_match_state import snapshot
from read_selected_personality import inspect_player
from macro_observation import verify_pins,cache_scores,native_budget
from read_script_flags import inspect_flags


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--seconds',type=int,default=1800);a=p.parse_args()
    raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));run=a.session.resolve().parent
    archive=json.loads((run/'research-settlement.json').read_text(encoding='utf-8-sig'))
    release=json.loads((run/'battle-host/macro-release.json').read_text())
    if (not run.is_relative_to(ROOT/'acceptance/runs') or not 1<=a.seconds<=1800
            or archive.get('natural_settlement_verified') is not True or archive['session_id']!=session['session_id']
            or release.get('native_release_verified') is not True):raise ValueError('archived_released_research_match_required')
    out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_replay_observation_required')
    replay=run/archive['replay'];digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    if replay.resolve().parent!=run or digest(replay)!=archive['replay_sha256']:raise ValueError('replay_changed')
    manifest=json.loads((a.build/'build-manifest.json').read_text());flags=manifest['flags']
    if manifest['package_sha256']!=session['mod_sha256']:raise ValueError('replay_package_mismatch')
    memory=Memory(session['pid'],session)
    try:
        verify_pins(memory.read);initial=snapshot(memory.read)
        if not initial['simulation_frame']:raise ValueError('running_replay_required')
        players=memory.u32(0xce8c9c);owner=memory.u32(players+0x30+3*4)
        if not owner or memory.u32(owner)!=0xc5bce0 or memory.u32(owner+0x20)!=3:
            raise ValueError('replay_player_mismatch')
        identity=None;identity_error=None
        try:identity=inspect_player(memory.read,owner)
        except ValueError as error:identity_error=str(error)
        if identity and int(identity['instance_id'],0)!=0x799613e0:raise ValueError('replay_commander_mismatch')
        ai=int(identity['ai_player'],0) if identity else None
        out.mkdir(parents=True);shutil.copy2(__file__,out/'watcher.py')
        pre=dict(kind='replay_without_external_macro_dispatch',session_id=session['session_id'],pid=session['pid'],
            replay_sha256=digest(replay),watcher_sha256=digest(Path(__file__)),first_frame=initial['simulation_frame'],
            model_calls=0,native_commands=0,process_writes=0,original_match_observation=False,
            native_ai_inspectable=identity is not None,native_ai_initial_error=identity_error)
        (out/'preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
        start=time.monotonic();count=0;errors=0;reason='observation_deadline';last=0
        with (out/'replay-native-observations.jsonl').open('x') as stream:
            while time.monotonic()-start<a.seconds:
                if a.session.read_bytes()!=raw:raise ValueError('replay_session_source_changed')
                state=snapshot(memory.read);frame=state['simulation_frame']
                if not frame:reason='replay_native_frame_reset';break
                if frame<last:reason='replay_frame_rollback';break
                last=frame
                try:
                    if memory.u32(0xce8c9c)!=players or memory.u32(players+0x30+3*4)!=owner:
                        raise ValueError('replay_player_changed')
                    bank=None
                    if identity:
                        if inspect_player(memory.read,owner)!=identity:raise ValueError('replay_identity_changed')
                        scores=cache_scores(memory.read,ai,flags,0xe8,'budget')
                        bank=native_budget(memory.read,ai,scores)
                    row=dict(elapsed_seconds=round(time.monotonic()-start,3),frame=frame,
                        budget_feedback=bank,flags=inspect_flags(memory.read,flags),
                        result_records=state['result_records'])
                    count+=1
                except (ValueError,RuntimeError) as error:
                    errors+=1;row=dict(frame=frame,read_error=str(error))
                stream.write(json.dumps(row)+'\n');stream.flush();time.sleep(.25)
        result=dict(**pre,last_frame=last,records=count,read_errors=errors,reason=reason,
            playback_loaded_verified=True,playback_reached_native_frame_reset=reason=='replay_native_frame_reset',
            full_match_reproduction_verified=False,
            macro_replay_fidelity_verified=False,formal_G7=False,formal_goal_complete=False)
        (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:memory.close()


if __name__=='__main__':main()
