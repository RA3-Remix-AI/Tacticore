"""Research far-then-near public region goals through original native AI.

Fixed policy; no model, unit IDs in commands, direct unit orders or product grant.
The original AI recruits and operates each native task group.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path,PureWindowsPath
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from observe_production import Memory
from read_match_state import snapshot
from read_selected_personality import inspect_player
from macro_area_defense_observation import own_census
from inspect_area_defense_runtime_candidates import inspect_candidates

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--wait-seconds',type=int,default=300);a=p.parse_args();out=a.output.resolve()
    raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));run=Path(session['run_directory']).resolve()
    if (out.exists() or not out.is_relative_to(ROOT/'reports') or not run.is_relative_to(ROOT/'acceptance/runs')
            or a.session.resolve().parent!=run or session.get('phase')!='macro_native_interface_probe'
            or (run/'battle-host').exists() or not 1<=a.wait_seconds<=300):raise ValueError('fresh_owned_region_research_required')
    package=json.loads(Path(session['macro_package_report']).read_text())
    if (package.get('regional_waypoints_revision') not in (1,2,3) or package.get('regional_map_id')!='map_mp_2_black1b'
            or package['big_sha256']!=session['mod_sha256']):raise ValueError('reviewed_region_package_required')
    if package.get('area_defense_candidate_revision')!=1:raise ValueError('area_defense_candidate_required')
    out.mkdir();shutil.copy2(__file__,out/'area-defense-driver.py')
    diagnostic=Path(__file__).with_name('inspect_area_defense_runtime_candidates.py')
    shutil.copy2(diagnostic,out/diagnostic.name)
    memory=Memory(session['pid'],session);transport=None
    try:
        deadline=time.monotonic()+a.wait_seconds
        while True:
            if a.session.read_bytes()!=raw:raise ValueError('region_session_changed')
            try:state=snapshot(memory.read)
            except (ValueError,RuntimeError):state=None
            if state and state['simulation_frame']>=1800 and not state['pause_flag_candidate']:
                if any(r['victory_frame'] or r['defeat_frame'] for r in state['result_records']):raise ValueError('live_region_match_required')
                break
            if time.monotonic()>=deadline:raise ValueError('region_wait_deadline_before_attach')
            time.sleep(.25)
        owners=[int(r['player'],0) for r in state['victory_conditions']['participants'] if r['player_index']==3]
        if len(owners)!=1:raise ValueError('unique_region_owner_required')
        logic=memory.u32(0xcd8ce4);map_pointer=memory.u32(logic+0x98)
        map_path=PureWindowsPath(memory.read(map_pointer,260).split(b'\0',1)[0].decode('ascii'))
        if (map_path.suffix.lower()!='.map' or map_path.stem.lower()!='map_mp_2_black1b'
                or map_path.parent.name.lower()!='map_mp_2_black1b'):
            raise ValueError('region_trial_requires_reviewed_actual_map')
        owner=owners[0];native=inspect_player(memory.read,owner)
        if int(native['instance_id'],0)!=0x799613e0:raise ValueError('regional_personality_mismatch')
        census=own_census(memory,owner);yards=[r for r in census['own_objects'] if r['type_hash']=='0xc16ff13f']
        if len(yards)!=1:raise ValueError('unique_own_region_origin_required')
        targets=[r for r in package['consumers'] if r['action'] in ('deployattack','deploydefense')]
        if len(targets)!=2 or any(r['target_policy']!='fixed_public_start_waypoint' for r in targets):
            raise ValueError('bounded_public_region_consumers_required')
        targets.sort(key=lambda r:math.dist(yards[0]['xyz'],r['waypoint_xyz']),reverse=True)
        pre=dict(kind='fixed_far_then_near_native_area_defense_candidate_trial',session_id=session['session_id'],pid=session['pid'],
            process_creation_filetime=session['process_creation_filetime'],driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            diagnostic_sha256=hashlib.sha256(diagnostic.read_bytes()).hexdigest(),
            targets=[dict(action=r['action'],waypoint_name=r['waypoint_name'],waypoint_xyz=r['waypoint_xyz'],region_id=r['region_id']) for r in targets],
            initial_own_construction_yard_xyz=yards[0]['xyz'],initial_frame=census['frame'],model_calls=0,unit_orders=0,
            actual_map_id=map_path.stem.lower(),
            enemy_live_details_read=False,capability_granted=False,formal_goal_complete=False)
        (out/'driver-preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
        spec=importlib.util.spec_from_file_location('region_research_transport',ROOT/'native-ai/macro-policy-runtime/client_area_defense.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        transport=module.MacroPolicyProbe(a.session,owner,a.build,out/'transport')
        transport.observe('before_regional_policy')
        for index,target in enumerate(targets):
            transport.event('fixed_region_preference',index=index,**pre['targets'][index],model_calls=0)
            transport.apply([target['action']],1800);deadline=time.monotonic()+125;diagnosed=False
            while time.monotonic()<deadline:
                if a.session.read_bytes()!=raw:raise ValueError('region_session_changed')
                transport.observe('region_far' if index==0 else 'region_near');time.sleep(.5)
                if not diagnosed and time.monotonic()>deadline-75:
                    result=inspect_candidates(memory,owner,transport.manifest['flags'])
                    (out/('runtime-diagnostic-'+str(index)+'.json')).write_text(json.dumps(result,indent=2)+'\n')
                    diagnosed=True
            transport.apply([],1);transport.observe('regional_policy_released_'+str(index));time.sleep(3)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:transport.observe('after_region_reassignment');time.sleep(.5)
    finally:
        if transport:transport.close()
        memory.close()
    print(json.dumps(dict(output=str(out),model_calls=0,unit_orders=0,capability_granted=False)))

if __name__=='__main__':main()
