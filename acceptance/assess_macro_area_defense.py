"""Qualify an original native area task, without judging unit combat details."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import load,sha
from integration.host_runtime.macro_policy_runtime import trial

PACKAGES={
    'fc37713607e40ffc2457d83da7494aeaf2d50e1d1aba66bb3c9640ba235713e9':('area-defense-driver.py','DefenseMicroManager',500),
    'c76b3c9492848cdc91b7221cf5247d4ff0d6cf99bebb7f432f5624372d939622':('area-hold-driver.py','BeaconHoldMicroManager',250),
}


def task_effect(observations,flag,owner,begin,end,target,family,defense_radius=500):
    frames={};cleared=[];families=set()
    for obs in observations:
        state=obs['state_scores'].get(flag,{})
        matching=[r for r in obs['runtimes'] if r['group']==state.get('group') and r['native_execution_active']]
        if begin<=obs['frame']<end and state.get('score',0)>0:
            for task in matching:
                if task.get('native_tactic_family')!=family:raise ValueError('area_task_native_family')
                families.add(family)
                for group in task.get('owned_groups',[]):
                    if not group.get('found') or not group.get('all_members_resolved'):continue
                    for member in group['members']:
                        if member['owner']!=owner:raise ValueError('area_task_foreign_member')
                        point=member['xyz']
                        if len(point)!=3 or any(not math.isfinite(v) for v in point):raise ValueError('area_task_position')
                        key=(task['address'],group['native_id'],member['thing_id'])
                        frames.setdefault(key,{})[obs['frame']]=math.dist(point[:2],target)
        if obs['frame']>end and state.get('score')==0 and not matching:cleared.append(obs['frame'])
    progress=0;present=0;duration=0
    for track in frames.values():
        ordered=sorted(track.items());span=ordered[-1][0]-ordered[0][0]
        if len(ordered)<3:continue
        if ordered[0][1]-min(v for _,v in ordered)>50:progress+=1
        # A native-owned defense group already stationed in its defense area
        # is a valid area task. It need not receive unnecessary move orders.
        inside=[frame for frame,distance in ordered if distance<=defense_radius]
        if len(inside)>=3 and max(inside)-min(inside)>=225:
            present+=1;duration=max(duration,max(inside)-min(inside))
    return dict(native_tactic_family=family,owned_group_tracks=len(frames),
        own_members_progressing_toward_area=progress,own_members_observed_in_defense_area=present,
        longest_observed_defense_area_span_frames=duration,
        native_task_and_own_group_verified=bool(frames),
        bounded_area_effect_verified=bool(progress or family=='static_defense' and present),
        inactive_after_release_samples=len(cleared),
        continuous_between_samples_verified=False,combat_success_verified=False)


def evaluate(directory):
    driver=load(directory/'driver-preflight.json')
    pre,final,manifest,rows,evidence=trial(directory/'transport')
    if manifest['package_sha256'] not in PACKAGES:raise ValueError('reviewed_native_area_package_required')
    driver_name,micro_manager,radius=PACKAGES[manifest['package_sha256']]
    if driver.get('kind')=='fixed_near_hold_then_far_native_area_candidate_trial':
        if micro_manager!='BeaconHoldMicroManager':raise ValueError('reviewed_near_hold_package_required')
        driver_name='area-hold-near-driver.py'
    if driver.get('kind')=='fixed_hold_then_attack_native_area_candidate_trial':
        if micro_manager!='BeaconHoldMicroManager':raise ValueError('reviewed_hold_first_package_required')
        driver_name='area-hold-first-driver.py'
    if (driver['session_id']!=final['session_id']
            or driver['pid']!=final['pid'] or driver['process_creation_filetime']!=final['process_creation_filetime']
            or sha(directory/driver_name)!=driver['driver_sha256']
            or sha(directory/'inspect_area_defense_runtime_candidates.py')!=driver['diagnostic_sha256']
            or driver['model_calls']!=0 or driver['unit_orders']!=0 or driver['enemy_live_details_read'] is not False
            or driver['actual_map_id']!='map_mp_2_black1b'):raise ValueError('area_defense_fixed_trial_binding')
    by={r['action']:r for r in manifest['consumers']}
    acks=[r for r in rows if r['kind']=='command_acknowledged']
    masks=[1<<manifest['flags'].index(by[t['action']]['flag']) for t in driver['targets']]
    if (len(driver['targets'])!=2 or {t['action'] for t in driver['targets']}!={'deployattack','deploydefense'}
            or len(acks)!=5 or [r['native']['applied_mask'] for r in acks]!=[masks[0],0,masks[1],0,0]):
        raise ValueError('area_defense_fixed_command_sequence')
    observations=[r['observation'] for r in rows if 'observation' in r];effects=[]
    for index,target in enumerate(driver['targets']):
        consumer=by[target['action']];defense=target['action']=='deploydefense'
        if (consumer['native_tactic']!=('StaticDefense' if defense else 'SimpleAttack')
                or consumer['native_micro_manager']!=(micro_manager if defense else 'GrowingAttacksMicroManager_MEDIUM')
                or defense and consumer['native_defense_radius']!=radius
                or consumer['waypoint_xyz']!=target['waypoint_xyz'] or consumer['region_id']!=target['region_id']):
            raise ValueError('area_defense_compiled_consumer_binding')
        begin=acks[2*index]['native']['last_frame'];end=acks[2*index+1]['native']['last_frame']
        effect=task_effect(observations,consumer['flag'],pre['native']['player'],begin,end,
            target['waypoint_xyz'][:2],'static_defense' if defense else 'simple_attack',radius)
        effects.append(dict(action=target['action'],region_id=target['region_id'],begin_frame=begin,end_frame=end,**effect))
    return dict(kind='fixed_original_native_area_defense_assessment',session_id=final['session_id'],pid=final['pid'],
        package_sha256=manifest['package_sha256'],effects=effects,native_cleanup_verified=final['cleanup_verified'],
        both_area_task_effects_verified=all(r['bounded_area_effect_verified'] and r['inactive_after_release_samples']>0 for r in effects),
        native_defense_task_verified=any(r['action']=='deploydefense' and r['native_task_and_own_group_verified'] for r in effects),
        original_unit_ai_retained=True,model_calls=0,unit_orders=0,product_capability_granted=False,
        formal_goal_complete=False,evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('trial','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_area_assessment_required')
    value=evaluate(a.trial.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py')
    value['assessor_sha256']=sha(out/'assessor.py');(out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))


if __name__=='__main__':main()
