"""Independently replay original-native group role effects, excluding late samples."""
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
from integration.host_runtime.macro_infrastructure import TEMPLATES

PACKAGE_SHA='aec5131537d2852c5ccda55391e85a74a3457256859fc94a924832cacc0da756'
ATTACK_FIRST_SHA='bf0bb3105dc9d1124173ff8aa6ccfa15e494ceb550f78e05600092356970c260'


def tracks(observations,flag,owner,begin,end,family):
    found={};active=set();inactive=set();discarded=0
    for obs in observations:
        state=obs['state_scores'].get(flag,{})
        tasks=[t for t in obs['runtimes'] if t['group']==state.get('group') and t['native_execution_active']]
        if obs['frame']>end and state.get('score')==0 and not tasks:inactive.add(obs['frame'])
        if not begin<=obs['frame']<end or state.get('score',0)<=0:continue
        census=obs['construction_feedback']
        if census.get('enemy_details_read') is not False:raise ValueError('own_role_census_required')
        if abs(census['frame']-obs['frame'])>15:
            discarded+=1;continue
        buildings=[r for r in census['own_objects'] if r['type_hash'] in TEMPLATES.values() and r['hp']>0]
        for task in tasks:
            if task.get('native_tactic_family')!=family:raise ValueError('role_native_family_mismatch')
            active.add(obs['frame'])
            for group in task.get('owned_groups',[]):
                if not group.get('found') or not group.get('all_members_resolved'):continue
                for member in group['members']:
                    if member['owner']!=owner:raise ValueError('foreign_role_member')
                    point=member['xyz']
                    if len(point)!=3 or any(not math.isfinite(v) for v in point):raise ValueError('bad_role_position')
                    key=(member['thing_id'],member['address'],member['type_hash'])
                    near=bool(buildings) and min(math.dist(point[:2],b['xyz'][:2]) for b in buildings)<=500
                    found.setdefault(key,[]).append((obs['frame'],point,near))
    return found,len(active),len(inactive),discarded


def movement(track,target):
    first=track[0][1]
    return dict(samples=len(track),first_frame=track[0][0],last_frame=track[-1][0],
        first_target_distance=math.dist(first[:2],target),
        displacement=max(math.dist(first,p) for _,p,_ in track),
        target_progress=max(math.dist(first[:2],target)-math.dist(p[:2],target) for _,p,_ in track))


def evaluate(directory):
    driver=load(directory/'driver-preflight.json');pre,final,manifest,rows,evidence=trial(directory/'transport')
    variants={'fixed_original_native_group_roles_trial':('group-role-driver.py',PACKAGE_SHA,['regroup','deployattack','withdraw','reinforce']),
        'fixed_original_native_group_roles_attack_first_trial':('group-role-attack-first-driver.py',ATTACK_FIRST_SHA,['deployattack','withdraw','reinforce','regroup'])}
    variant=variants.get(driver.get('kind'))
    if (variant is None or manifest['package_sha256']!=variant[1]
            or any(driver[k]!=final[k] for k in ('session_id','pid','process_creation_filetime'))
            or driver['model_calls']!=0 or driver['unit_orders']!=0 or driver['enemy_live_details_read'] is not False
            or sha(directory/variant[0])!=driver['driver_sha256']
            or [s['action'] for s in driver['steps']]!=variant[2]):
        raise ValueError('fixed_group_role_binding')
    acks=[r for r in rows if r['kind']=='command_acknowledged'];by={r['action']:r for r in manifest['consumers']}
    masks=[1<<manifest['flags'].index(by[s['action']]['flag']) for s in driver['steps']]
    if len(acks)!=9 or [r['native']['applied_mask'] for r in acks]!=[masks[0],0,masks[1],0,masks[2],0,masks[3],0,0]:
        raise ValueError('fixed_group_role_ack_sequence')
    observations=[r['observation'] for r in rows if r['kind']=='macro_observation' and 'observation' in r]
    home=by['regroup']['waypoint_xyz'][:2];west=by['deployattack']['waypoint_xyz'][:2]
    results=[];advance_members=set()
    for index,step in enumerate(driver['steps']):
        action=step['action'];ack,release=acks[index*2:index*2+2];begin=ack['native']['last_frame']
        deadline=ack['native']['deadline_frame'];end=min(deadline,release['native']['last_frame'])
        family='reactive_defense' if action=='reinforce' else 'simple_attack';target=west if action=='deployattack' else home
        members,active,inactive,discarded=tracks(observations,by[action]['flag'],pre['native']['player'],begin,end,family)
        summaries={k:movement(t,target) for k,t in members.items()}
        progressing={k for k,t in summaries.items() if t['samples']>=2 and t['displacement']>10 and t['target_progress']>50}
        near={k for k,t in members.items() if len(f:=[f for f,p,n in t if math.dist(p[:2],home)<=500])>=3 and max(f)-min(f)>=15}
        near_infrastructure={k for k,t in members.items() if len(f:=[f for f,p,n in t if n])>=3 and max(f)-min(f)>=15}
        if action=='deployattack':advance_members=progressing;positive=bool(progressing)
        elif action=='regroup':positive=len(near)>=2
        # Withdrawal may redirect forces that the original AI advanced itself.
        # Earlier model/fixed attack attribution is an additional metric, not
        # a prerequisite for a valid high-level withdrawal of existing forces.
        elif action=='withdraw':positive=bool({k for k in progressing if summaries[k]['first_target_distance']>750})
        else:positive=bool({k for k in near_infrastructure if summaries[k]['displacement']>10})
        results.append(dict(action=action,goal=by[action].get('goal','native_combat_group_to_fixed_public_waypoint'),
            native_tactic_family=family,native_seq=ack['seq'],begin_frame=begin,native_deadline_frame=deadline,
            effect_window_end=end,release_frame=release['native']['last_frame'],active_native_task_samples=active,
            discarded_unpaired_native_samples=discarded,
            native_inactive_after_release_samples=inactive,own_member_tracks=len(members),
            own_members_progressing_toward_target=len(progressing),own_members_near_home=len(near),
            own_members_near_infrastructure=len(near_infrastructure),
            prior_advance_members_now_progressing_home=len(progressing&advance_members) if action=='withdraw' else 0,
            own_tracks=list(summaries.values()),bounded_native_role_effect_verified=positive,
            known_native_release=release['native']['applied_mask']==0 and release['native']['last_frame']>=begin,
            model_max_60_seconds=0<deadline-begin<=900))
    qualified=[r['action'] for r in results if r['action']!='deployattack' and r['bounded_native_role_effect_verified']
        and r['known_native_release'] and r['model_max_60_seconds'] and r['native_inactive_after_release_samples']>=2]
    return dict(kind='fixed_original_native_group_role_effect_assessment',session_id=final['session_id'],pid=final['pid'],
        package_sha256=manifest['package_sha256'],role_results=results,qualified_fixed_role_effects=qualified,
        all_three_fixed_role_effects_verified=set(qualified)=={'regroup','withdraw','reinforce'},
        native_cleanup_verified=final['cleanup_verified'],model_calls=0,unit_orders=0,
        independent_model_role_feedback_verified=False,product_capability_granted=False,formal_goal_complete=False,evidence=evidence)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_group_role_assessment_required')
    value=evaluate(a.trial.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('role_results','evidence')}))
