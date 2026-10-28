"""Early macro construction qualification; fixed policy, zero model calls.

Arms during the lobby, waits for this exact process/match, then lets native
OpeningMoveHeuristic decide when to consume the policy. No unit operations.
"""
import argparse
import importlib.util
import json
import hashlib
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from observe_production import Memory
from read_match_state import snapshot
from macro_observation import own_census
from read_selected_personality import inspect_player

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--hold-seconds',type=int,default=180);a=p.parse_args()
    if not 150<=a.hold_seconds<=180:raise ValueError('bounded_early_build_window')
    out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_early_build_output')
    session_raw=a.session.read_bytes();session=json.loads(session_raw.decode('utf-8-sig'))
    out.mkdir(parents=True);shutil.copy2(Path(__file__),out/'early-driver.py')
    manifest=json.loads((a.build/'build-manifest.json').read_text())
    if manifest['package_sha256']!=session['mod_sha256']:raise ValueError('early_build_package_mismatch')
    evidence=dict(kind='early_native_macro_build_trial',session_id=session['session_id'],
        driver_sha256=hashlib.sha256((out/'early-driver.py').read_bytes()).hexdigest(),
        policy=['buildreactor','budgetarmy'],target_type_hash='0x524bbd01',model_calls=0,
        capability_granted=False,formal_goal_complete=False)
    with (out/'driver-preflight.json').open('x',encoding='utf-8') as f:json.dump(evidence,f,indent=2)
    memory=Memory(session['pid'],session);transport=None
    try:
        ready=None;deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if a.session.read_bytes()!=session_raw:raise ValueError('early_build_session_changed')
            try:state=snapshot(memory.read)
            except (ValueError,RuntimeError):time.sleep(.25);continue
            frame=state['simulation_frame']
            if frame>=30:
                if frame>600:raise ValueError('early_build_window_missed_no_attach')
                owners=[int(r['player'],0) for r in state.get('victory_conditions',{}).get('participants',[]) if r.get('player_index')==3]
                if len(owners)!=1:raise ValueError('early_build_unique_owner_required')
                owner=owners[0];native=inspect_player(memory.read,owner)
                if int(native['instance_id'],0)!=0x799613e0:raise ValueError('early_build_personality_mismatch')
                census=own_census(memory,owner)
                if any(r['type_hash']=='0x524bbd01' for r in census['own_objects']):raise ValueError('early_build_target_already_present_no_attach')
                ready=dict(frame=frame,owner=hex(owner),native=native,census=census);break
            time.sleep(.25)
        if ready is None:raise ValueError('early_build_waiting_deadline_no_attach')
        with (out/'early-state.json').open('x',encoding='utf-8') as f:json.dump(ready,f,indent=2)
        spec=importlib.util.spec_from_file_location('early_macro_policy_transport',ROOT/'native-ai/macro-policy-runtime/client.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        transport=module.MacroPolicyProbe(a.session,owner,a.build,out/'transport',build_feedback=True)
        transport.event('early_fixed_macro_policy',policy=evidence['policy'],target_type_hash=evidence['target_type_hash'],model_calls=0)
        transport.observe('before_early_policy');transport.apply(['buildreactor','budgetarmy'],3900)
        deadline=time.monotonic()+a.hold_seconds
        while time.monotonic()<deadline:
            transport.observe('early_construction_policy_held');time.sleep(.25)
        transport.apply([],1);transport.observe('early_construction_policy_released')
        time.sleep(2);transport.observe('after_native_policy_reassessment')
        # Releasing a policy does not cancel an already accepted native job.
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            transport.observe('native_completion_after_policy_release');time.sleep(.25)
    finally:
        if transport:transport.close()
        memory.close()
    print(json.dumps(dict(output=str(out),model_calls=0,capability_granted=False)))
