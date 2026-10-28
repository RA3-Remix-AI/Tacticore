"""Assess fixed public-region native task effects without unit operation claims."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import load,records,sha
from integration.host_runtime.macro_policy_runtime import trial

def evaluate(directory):
    driver=load(directory/'driver-preflight.json')
    pre,final,manifest,rows,evidence=trial(directory/'transport')
    if (sha(directory/'region-driver.py')!=driver['driver_sha256'] or driver['session_id']!=final['session_id']
        or driver['pid']!=final['pid'] or driver['process_creation_filetime']!=final['process_creation_filetime']
        or driver['model_calls']!=0 or driver['unit_orders']!=0 or driver['enemy_live_details_read'] is not False
        or driver['actual_map_id']!='map_mp_2_black1b'):raise ValueError('fixed_region_driver_binding')
    acks=[r for r in rows if r['kind']=='command_acknowledged']
    flags={r['action']:r['flag'] for r in manifest['consumers']}
    masks=[1<<manifest['flags'].index(flags[t['action']]) for t in driver['targets']]
    if len(acks)!=5 or [r['native']['applied_mask'] for r in acks]!=[masks[0],0,masks[1],0,0]:
        raise ValueError('fixed_region_command_sequence')
    observations=[r['observation'] for r in rows if r.get('observation')]
    effects=[]
    for index,target in enumerate(driver['targets']):
        begin=acks[2*index]['native']['last_frame'];end=acks[2*index+1]['native']['last_frame']
        flag=flags[target['action']];tracks={};positive=[];inactive=[]
        for o in observations:
            state=o['state_scores'][flag]
            matching=[t for t in o['runtimes'] if t['group']==state['group'] and t['native_execution_active']]
            if begin<=o['frame']<end and state['score']>0:
                positive.append(o['frame'])
                for t in matching:
                    for group in t.get('owned_groups',[]):
                        if not group.get('found') or not group.get('all_members_resolved'):continue
                        for member in group['members']:
                            if member['owner']!=pre['native']['player']:raise ValueError('foreign_regional_member')
                            key=(t['address'],group['native_id'],member['thing_id'])
                            tracks.setdefault(key,[]).append((o['frame'],member['xyz']))
            if o['frame']>end and state['score']==0 and not matching:inactive.append(o['frame'])
        summaries=[]
        for track in tracks.values():
            distance=lambda xyz:math.dist(xyz[:2],target['waypoint_xyz'][:2])
            summaries.append(dict(samples=len(track),first_frame=track[0][0],last_frame=track[-1][0],
                maximum_displacement=max(math.dist(track[0][1],v[1]) for v in track),
                first_distance_to_public_target=distance(track[0][1]),
                closest_distance_to_public_target=min(distance(v[1]) for v in track),
                progress_toward_public_target=distance(track[0][1])-min(distance(v[1]) for v in track)))
        effects.append(dict(action=target['action'],region_id=target['region_id'],begin_frame=begin,end_frame=end,
            positive_native_state_samples=len(set(positive)),own_native_group_tracks=summaries,
            own_group_progress_verified=any(t['samples']>=2 and t['maximum_displacement']>10
                and t['progress_toward_public_target']>50 for t in summaries),inactive_after_release_samples=len(inactive)))
    evidence.update({str((directory/n).resolve()):sha(directory/n) for n in ('driver-preflight.json','region-driver.py')})
    return dict(kind='fixed_native_public_regions_assessment',session_id=final['session_id'],pid=final['pid'],
        process_creation_filetime=final['process_creation_filetime'],package_sha256=manifest['package_sha256'],
        effects=effects,native_command_sequence_verified=True,native_cleanup_verified=final['cleanup_verified'],
        both_public_region_effects_verified=all(t['own_group_progress_verified'] for t in effects),
        original_unit_ai_retained=True,model_calls=0,unit_orders=0,model_regional_choice_verified=False,
        same_units_reassigned_verified=False,arbitrary_xy_control_verified=False,capability_granted=False,
        formal_goal_complete=False,evidence=evidence)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trial',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_region_assessment_required')
    value=evaluate(a.trial.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))

if __name__=='__main__':main()
