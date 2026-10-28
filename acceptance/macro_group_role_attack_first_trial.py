"""Fixed native regroup, advance, withdraw and reinforce qualification trial.

No model, arbitrary unit selection, unit orders or execution capability grant.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path,PureWindowsPath
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from observe_production import Memory
from read_match_state import snapshot
from read_selected_personality import inspect_player
from macro_group_role_observation import own_census

PACKAGE_SHA='bf0bb3105dc9d1124173ff8aa6ccfa15e494ceb550f78e05600092356970c260'
STEPS=(('deployattack',1800,125),('withdraw',900,65),('reinforce',900,65),('regroup',900,65))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--wait-seconds',type=int,default=300);a=p.parse_args();out=a.output.resolve()
    raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));run=Path(session['run_directory']).resolve()
    if (out.exists() or not out.is_relative_to(ROOT/'reports') or a.session.resolve().parent!=run
            or not run.is_relative_to(ROOT/'acceptance/runs') or (run/'battle-host').exists()
            or session.get('phase')!='macro_native_interface_probe' or not 1<=a.wait_seconds<=600
            or session['mod_sha256']!=PACKAGE_SHA):raise ValueError('fresh_owned_group_role_trial_required')
    package=json.loads(Path(session['macro_package_report']).read_text())
    if package.get('group_roles_candidate_revision')!=2 or package['big_sha256']!=PACKAGE_SHA:
        raise ValueError('reviewed_group_role_package_required')
    memory=Memory(session['pid'],session);transport=None;out.mkdir();shutil.copy2(__file__,out/'group-role-attack-first-driver.py')
    try:
        deadline=time.monotonic()+a.wait_seconds
        while True:
            if a.session.read_bytes()!=raw:raise ValueError('group_role_session_changed')
            try:state=snapshot(memory.read)
            except (ValueError,RuntimeError):state=None
            if state and state['simulation_frame']>=1800 and not state['pause_flag_candidate']:
                if any(r['victory_frame'] or r['defeat_frame'] for r in state['result_records']):raise ValueError('live_group_role_match_required')
                break
            if time.monotonic()>=deadline:raise ValueError('group_role_wait_deadline_before_attach')
            time.sleep(.25)
        owners=[int(r['player'],0) for r in state['victory_conditions']['participants'] if r['player_index']==3]
        if len(owners)!=1:raise ValueError('unique_group_role_owner_required')
        logic=memory.u32(0xcd8ce4);map_pointer=memory.u32(logic+0x98)
        map_path=PureWindowsPath(memory.read(map_pointer,260).split(b'\0',1)[0].decode('ascii'))
        if map_path.stem.lower()!='map_mp_2_black1b' or map_path.parent.name.lower()!='map_mp_2_black1b':
            raise ValueError('reviewed_group_role_map_required')
        owner=owners[0];native=inspect_player(memory.read,owner)
        if int(native['instance_id'],0)!=0x799613e0:raise ValueError('group_role_personality_mismatch')
        census=own_census(memory,owner);yards=[r for r in census['own_objects'] if r['type_hash']=='0xc16ff13f']
        if len(yards)!=1 or [int(v//512) for v in yards[0]['xyz'][:2]]!=[8,3]:raise ValueError('east_own_origin_required')
        pre=dict(kind='fixed_original_native_group_roles_attack_first_trial',session_id=session['session_id'],pid=session['pid'],
            process_creation_filetime=session['process_creation_filetime'],package_sha256=PACKAGE_SHA,
            driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            steps=[dict(action=action,duration_frames=duration,observation_wall_seconds=seconds) for action,duration,seconds in STEPS],
            initial_own_construction_yard_xyz=yards[0]['xyz'],initial_frame=census['frame'],model_calls=0,unit_orders=0,
            actual_map_id=map_path.stem.lower(),enemy_live_details_read=False,capability_granted=False,formal_goal_complete=False)
        (out/'driver-preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
        spec=importlib.util.spec_from_file_location('group_role_research_transport',ROOT/'native-ai/macro-policy-runtime/client_group_roles.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        transport=module.MacroPolicyProbe(a.session,owner,a.build,out/'transport')
        transport.observe('before_group_roles')
        for index,(action,duration,seconds) in enumerate(STEPS):
            transport.event('fixed_group_role_preference',index=index,action=action,model_calls=0)
            transport.apply([action],duration);deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if a.session.read_bytes()!=raw:raise ValueError('group_role_session_changed')
                transport.observe(action);time.sleep(.5)
            transport.apply([],1);transport.observe('released_'+action);time.sleep(3)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:transport.observe('after_group_roles');time.sleep(.5)
    finally:
        if transport:transport.close()
        memory.close()
    print(json.dumps(dict(output=str(out),model_calls=0,unit_orders=0,capability_granted=False)))


if __name__=='__main__':main()
