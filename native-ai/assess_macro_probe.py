"""Assess bounded native macro trials; never promote them to a product grant."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(directory):
    report=json.loads((directory/'report.json').read_text(encoding='utf-8'))
    preflight=json.loads((directory/'preflight.json').read_text(encoding='utf-8'))
    for source in preflight['sources']:
        if sha(directory/'source'/source['copy'])!=source['sha256']:
            raise ValueError('macro_trial_source_changed')
    rows=[json.loads(line) for line in (directory/'macro-observations.jsonl').read_text(encoding='utf-8').splitlines()]
    samples=[row['observation'] for row in rows if 'observation' in row]
    if not samples:raise ValueError('macro_trial_no_samples')
    identity=preflight['native'];flag=report['flag_name'];transitions=report['transitions']
    if any(sample['native']!=identity for sample in samples):raise ValueError('macro_trial_identity_changed')
    if [r['request'] for r in transitions]!=[1,2,3] or [r['expected'] for r in transitions]!=[False,True,False]:
        raise ValueError('macro_trial_transitions')
    begin,end=transitions[1]['frame'],transitions[2]['frame']
    final=report.get('native_final',{})
    stopped=(report.get('complete') is True and report.get('host_returncode')==0 and
        all(final.get(k)==v for k,v in dict(phase=2,ack=3,error=0,active=0,cleanup_verified=1).items()))
    tracks={};active_frames=[];cleared_frames=[];terrain=[]
    for sample in samples:
        frame=sample['frame'];runtimes=sample['runtimes']
        if any(r['native_execution_active'] for r in runtimes):active_frames.append(frame)
        if frame>end and sample['state_scores'].get(flag,{}).get('score')==0 and not any(r['native_execution_active'] for r in runtimes):
            cleared_frames.append(frame)
        if sample.get('terrain_feedback') is not None:terrain.append(dict(frame=frame,**sample['terrain_feedback']))
        if not begin<=frame<=end:continue
        for runtime in runtimes:
            if not runtime['native_execution_active']:continue
            for group in runtime.get('owned_groups',[]):
                for member in group.get('members',[]):
                    if member['owner']!=identity['player']:raise ValueError('macro_trial_member_owner')
                    key=(runtime['address'],group['native_id'],member['thing_id'])
                    tracks.setdefault(key,[]).append(dict(frame=frame,xyz=member['xyz'],type_hash=member['type_hash']))
    movement=[]
    for (runtime,group,thing),track in tracks.items():
        if any(b['frame']<a['frame'] for a,b in zip(track,track[1:])):raise ValueError('macro_trial_frame_rollback')
        movement.append(dict(runtime=runtime,native_group_id=group,own_thing_id=thing,type_hash=track[0]['type_hash'],
            samples=len(track),first=track[0],last=track[-1],
            displacement=math.dist(track[0]['xyz'],track[-1]['xyz']),
            sampled_path_length=sum(math.dist(a['xyz'],b['xyz']) for a,b in zip(track,track[1:]))))
    return dict(kind='bounded_native_macro_trial_assessment',session_id=report['session_id'],pid=report['pid'],
        mod_sha256=preflight['mod_sha256'],native=identity,mode=report['mode'],gate_begin_frame=begin,gate_clear_frame=end,
        valid_samples=len(samples),read_errors=[r for r in rows if 'read_error' in r],
        helper_stop_verified=stopped,native_execution_active_frames=active_frames,
        native_score_zero_and_execution_inactive_after_clear_frames=cleared_frames,
        own_native_group_tracks=movement,own_group_movement_observed=any(r['displacement']>10 for r in movement),
        terrain_samples=len(terrain),terrain_first=terrain[0] if terrain else None,terrain_last=terrain[-1] if terrain else None,
        max_new_clear_since_initial=max((r['newly_clear_since_initial'] for r in terrain),default=None),
        macro_scout_exclusive_visibility_attribution=False,enemy_intel_feedback_verified=False,
        model_calls=0,formal_match_verified=False,capability_granted=False,
        evidence={name:sha(directory/name) for name in ['report.json','preflight.json','macro-observations.jsonl']})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trial',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=assess(args.trial)
    with args.output.open('x',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=str(args.output.resolve()),helper_stop_verified=result['helper_stop_verified'],
        own_group_movement_observed=result['own_group_movement_observed'],capability_granted=False)))


if __name__=='__main__':main()
