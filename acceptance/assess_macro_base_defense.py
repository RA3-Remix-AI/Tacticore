"""Observe native defenders assigned near own infrastructure, without micro gates."""
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

PACKAGE_SHA='7a78e3cb66f759aa66b0e877fcc7eca725b4469f3091c0932944967eaf9f0828'


def defense_presence(observations,flag,owner,begin,end):
    tracks={};active=[];cleared=[]
    for obs in observations:
        state=obs['state_scores'].get(flag,{})
        tasks=[t for t in obs['runtimes'] if t['group']==state.get('group') and t['native_execution_active']]
        if obs['frame']>end and state.get('score')==0 and not tasks:cleared.append(obs['frame'])
        if not begin<=obs['frame']<end or state.get('score',0)<=0:continue
        census=obs['construction_feedback']
        if census.get('enemy_details_read') is not False:raise ValueError('own_infrastructure_source_required')
        structures=[r for r in census['own_objects'] if r['type_hash'] in TEMPLATES.values() and r['hp']>0]
        for task in tasks:
            if task.get('native_tactic_family')!='static_defense':raise ValueError('original_native_base_defense_required')
            active.append(obs['frame'])
            for group in task.get('owned_groups',[]):
                if not group.get('found') or not group.get('all_members_resolved'):continue
                for member in group['members']:
                    if member['owner']!=owner:raise ValueError('foreign_defender_rejected')
                    point=member['xyz']
                    if len(point)!=3 or any(not math.isfinite(v) for v in point):raise ValueError('bad_defender_position')
                    if structures and min(math.dist(point[:2],r['xyz'][:2]) for r in structures)<=500:
                        key=(group['native_id'],member['thing_id'])
                        tracks.setdefault(key,set()).add(obs['frame'])
    positive=[sorted(v) for v in tracks.values() if len(v)>=3 and max(v)-min(v)>=15]
    first=min((v[0] for v in positive),default=None)
    return dict(active_native_task_samples=len(set(active)),own_defender_tracks_near_infrastructure=len(positive),
        first_verified_presence_frame=first,
        effect_within_model_maximum_60_seconds=first is not None and first-begin<900,
        native_defender_presence_near_own_infrastructure_verified=bool(positive),
        inactive_after_release_samples=len(cleared),
        exact_structure_selection_verified=False,mission_success_verified=False,combat_outcome_verified=False)


def evaluate(directory):
    driver=load(directory/'driver-preflight.json');pre,final,manifest,rows,evidence=trial(directory/'transport')
    if (manifest['package_sha256']!=PACKAGE_SHA or driver['kind']!='fixed_native_own_base_defense_then_public_attack_trial'
            or driver['session_id']!=final['session_id'] or driver['pid']!=final['pid']
            or driver['process_creation_filetime']!=final['process_creation_filetime']
            or driver['model_calls']!=0 or driver['unit_orders']!=0 or driver['enemy_live_details_read'] is not False
            or sha(directory/'base-defense-driver.py')!=driver['driver_sha256']
            or sha(directory/'inspect_area_defense_runtime_candidates.py')!=driver['diagnostic_sha256']):
        raise ValueError('fixed_base_defense_binding')
    consumer=next(r for r in manifest['consumers'] if r['action']=='deploydefense')
    if (consumer['target_policy']!='original_native_friendly_land_structure'
            or consumer['native_tactic']!='StaticDefense' or consumer['native_micro_manager']!='DefenseMicroManager'
            or consumer['native_target_heuristic']!='FriendlyLandStructureHeuristic'):
        raise ValueError('original_native_base_consumer_required')
    acks=[r for r in rows if r['kind']=='command_acknowledged'];actions={r['action']:r for r in manifest['consumers']}
    masks=[1<<manifest['flags'].index(actions[t['action']]['flag']) for t in driver['targets']]
    if (len(acks)!=5 or [t['action'] for t in driver['targets']]!=['deploydefense','deployattack']
            or [r['native']['applied_mask'] for r in acks]!=[masks[0],0,masks[1],0,0]):
        raise ValueError('fixed_base_defense_sequence')
    begin,end=acks[0]['native']['last_frame'],acks[1]['native']['last_frame']
    effect=defense_presence([r['observation'] for r in rows if 'observation' in r],consumer['flag'],pre['native']['player'],begin,end)
    return dict(kind='original_native_own_infrastructure_defense_assessment',session_id=final['session_id'],pid=final['pid'],
        package_sha256=manifest['package_sha256'],begin_frame=begin,end_frame=end,**effect,
        native_cleanup_verified=final['cleanup_verified'],
        bounded_native_base_defense_effect_verified=effect['native_defender_presence_near_own_infrastructure_verified']
            and effect['effect_within_model_maximum_60_seconds'] and effect['inactive_after_release_samples']>=2,
        native_ai_selects_structure_and_operates_units=True,model_calls=0,unit_orders=0,
        product_capability_granted=False,formal_goal_complete=False,evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('trial','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_base_defense_assessment_required')
    value=evaluate(a.trial.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))


if __name__=='__main__':main()
