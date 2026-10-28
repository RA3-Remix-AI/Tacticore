"""Observe original AI with no model host or macro delivery; no game writes."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'production'),str(ROOT/'native-ai')]
from observe_production import Memory,k
from read_match_state import snapshot
from read_script_flags import inspect_flags
from read_selected_personality import inspect_player
from macro_observation import own_census,verify_pins,cache_scores,native_budget
from match_participants import verify_two_ai

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','output'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--seconds',type=int,default=1200);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports') or not 1<=a.seconds<=1800:raise ValueError('fresh_bounded_baseline_required')
    raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));run=Path(session['run_directory'])
    if (run/'battle-host').exists():raise ValueError('baseline_cannot_include_macro_host')
    manifest=json.loads((a.build/'build-manifest.json').read_text())
    if manifest['package_sha256']!=session['mod_sha256']:raise ValueError('baseline_package_binding')
    registry=json.loads(Path(session['registry']).read_text());memory=Memory(session['pid'],session)
    try:
        verify_pins(memory.read);state=snapshot(memory.read)
        participants=verify_two_ai(memory,state,registry,3,4,2)
        owner=int(next(r['player'] for r in state['victory_conditions']['participants'] if r['player_index']==3),0)
        identity=inspect_player(memory.read,owner);ai=int(identity['ai_player'],0)
        k.OpenMutexW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenMutexW.restype=w.HANDLE
        out.mkdir();source=out/'source';source.mkdir();pins=[]
        for i,path in enumerate([Path(__file__),ROOT/'native-ai/macro_observation.py',ROOT/'native-ai/read_match_state.py',
                ROOT/'native-ai/read_script_flags.py',ROOT/'integration/match_participants.py',a.session,a.build/'build-manifest.json']):
            target=source/(str(i)+'-'+path.name);shutil.copy2(path,target)
            pins.append(dict(path=str(path.resolve()),copy=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        pre=dict(kind='original_native_ai_baseline_observer',session_id=session['session_id'],pid=session['pid'],
            process_creation_filetime=session['process_creation_filetime'],package_sha256=session['mod_sha256'],
            first_observed_frame=state['simulation_frame'],statistics_begin_mid_match=True,participants=participants,
            model_calls=0,native_calls=0,unit_orders=0,process_writes=0,sources=pins)
        (out/'preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
        started=time.monotonic();count=0;reason='observation_deadline'
        with (out/'baseline.jsonl').open('x') as stream:
            while time.monotonic()-started<a.seconds:
                if a.session.read_bytes()!=raw or (run/'battle-host').exists():raise ValueError('baseline_scope_changed')
                state=snapshot(memory.read)
                if not state['simulation_frame']:reason='native_frame_reset';break
                lease=k.OpenMutexW(0x100000,False,'Local\\RA3MacroPolicyLease_'+str(session['pid']))
                if lease:k.CloseHandle(lease);raise ValueError('baseline_macro_lease_present')
                flags=inspect_flags(memory.read,manifest['flags'])
                if any(r['present'] and r['value'] is not False for r in flags['flags']):raise ValueError('baseline_macro_gate_active')
                if inspect_player(memory.read,owner)!=identity:raise ValueError('baseline_player_identity_changed')
                census=own_census(memory,owner);scores=cache_scores(memory.read,ai,manifest['flags'],0xe8,'budget')
                budget=native_budget(memory.read,ai,scores)
                if budget['selected_macro_flag'] is not None:raise ValueError('baseline_macro_budget_selected')
                row=dict(frame=census['frame'],credits=census['resources']['display_sum'],
                    own_template_presence_counts=dict(Counter(r['type_hash'] for r in census['own_objects'])),
                    account_shares=budget['account_shares'],all_macro_flags_clear=True,native_macro_lease_absent=True,
                    enemy_details_read=False,model_calls=0,native_calls=0,process_writes=0)
                stream.write(json.dumps(row)+'\n');stream.flush();count+=1;time.sleep(5)
        (out/'report.json').write_text(json.dumps(dict(session_id=session['session_id'],pid=session['pid'],
            reason=reason,samples=count,elapsed_seconds=round(time.monotonic()-started,3),model_calls=0,
            native_calls=0,unit_orders=0,process_writes=0,natural_settlement_verified=False,formal_goal_complete=False),indent=2)+'\n')
        print(json.dumps(dict(output=str(out),samples=count,reason=reason)))
    finally:memory.close()

if __name__=='__main__':main()
