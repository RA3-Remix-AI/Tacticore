"""Join model building choices to original native queues and subsequent requests."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from acceptance.assess_macro_desktop_production import assess as assess_common,load,records,sha
from integration.host_runtime.macro_policy_runtime import trial
from integration.host_runtime.macro_construction_feedback import ConstructionFeedback,ACTION
from integration.host_runtime.contracts import ContractError


def assess(run,run_id):
    common=assess_common(run,run_id)
    _,final,manifest,stream,_=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    host=run/'battle-host';events=records(host/'host-events.jsonl');status=load(host/'host-status.json')
    profile=load(host/'profile.json');plans={r['plan_id']:r['plan'] for r in events if r['kind']=='plan_applied'}
    requests=[r for r in events if r['kind']=='model_macro_request_context']
    commands=[r for r in events if r['kind']=='model_macro_construction_acknowledged']
    acks={r['command_id']:r for r in stream if r['kind']=='command_acknowledged'}
    flags={r['action']:r['flag'] for r in manifest['consumers']};results=[]
    for command in commands:
        plan=plans.get(command['plan_id'],{});ack=acks.get(command['command_id'],{})
        request=next((r for r in requests if r['context']['snapshot_id']==plan.get('snapshot_id')),None)
        context=request['context'] if request else {}
        bound=(plan.get('origin')=='model' and plan.get('session_id')==final['session_id'] and plan.get('player_id')==3
            and plan.get('commander_id')==profile['profile_id'] and plan.get('macro_actions')==command['actions']
            and ACTION in context.get('allowed_macro_actions',()) and plan.get('macro_production') is None
            and context.get('macro_policy_catalog',{}).get(ACTION,{}).get('domain')=='construction')
        mask=sum(1<<manifest['flags'].index(flags[action]) for action in command['actions'])
        ack_bound=ack.get('seq')==command['seq'] and ack.get('native',{}).get('applied_mask')==mask
        position=next((i for i,r in enumerate(stream) if r is ack),-1)
        builder=None;census=None
        for row in stream[:position]:
            if row['kind']=='native_builder_observation' and 'observation' in row:builder=row['observation']
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
        tracker=ConstructionFeedback(builder,census)
        baseline_empty=not tracker.baseline_queues and not tracker.baseline_objects
        release=None;reason=None;bounded=False;snapshots={};discarded=0;positive=[]
        later={r['command_id'] for r in commands if r['seq']>command['seq']}
        later_frame=min((acks[key]['native']['last_frame'] for key in later if key in acks),default=0xffffffff)
        for row in stream[position+1:]:
            if row['kind']=='command_acknowledged' and row['command_id'] in later:break
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']=='native_builder_observation' and 'observation' in row:
                builder=row['observation']
                try:tracker.observe(builder,census,flags[ACTION])
                except ContractError:discarded+=1;continue
                public=tracker.public();snapshots[tracker.frames]=public
                if release is None and tracker.positive:positive.append(builder['frame'])
            if row['kind']=='command_acknowledged' and row['seq']>command['seq'] and release is None:
                release=row
                if row['native']['applied_mask']==0:
                    if row['native']['kind']==2 and status['state']=='stopped' and status['reason_code']=='user_stop':
                        reason='stopped';bounded=True
                    elif tracker.new_queues:
                        reason='queue_observed';bounded=(tracker.frames[0]<=row['native']['last_frame']<=tracker.frames[0]+15
                            and row['native']['last_frame']<=ack.get('native',{}).get('deadline_frame',0))
                    elif tracker.new_objects:reason='target_present';bounded=True
                    elif tracker.eligible!=tracker.baseline_builders:reason='builder_unavailable';bounded=True
                    else:
                        expiry=min(int(plan['expires_at_game_seconds']*15),ack['native']['deadline_frame'])
                        if expiry<=row['native']['last_frame']<=expiry+30:reason='expired';bounded=True
                if reason:
                    tracker.mark_policy_released(reason);snapshots[tracker.frames]=tracker.public()
        feedback=[]
        for r in requests:
            value=r['context'].get('macro_construction_feedback')
            if request is None or r['sequence']<=request['sequence'] or value is None or value.get('builder_frame',0)>=later_frame:continue
            observation=snapshots.get((value.get('builder_frame'),value.get('own_census_frame')))
            matches=(observation is not None and value.get('source')=='native_construction_observation'
                and all(value.get(k)==observation[k] for k in ('observed_new_queue_count','new_own_construction_object_observations',
                    'policy_released','construction_completed_verified'))
                and all(observation[k]==v for k,v in value.items() if k in observation))
            fresh=all(-15<=r['context']['game_time_seconds']*15-value[k]<=30 for k in ('builder_frame','own_census_frame'))
            feedback.append(dict(request_sequence=r['sequence'],observed_facts_match=matches,within_freshness=fresh))
        results.append(dict(plan_id=command['plan_id'],native_seq=command['seq'],model_plan_bound=bound,
            native_ack_matches=ack_bound,empty_target_baseline=baseline_empty,positive_native_build_frames=positive,
            release_reason=reason,bounded_release_verified=bounded,
            release_after_first_queue_verified=bounded and reason=='queue_observed' and len(tracker.new_queues)==1,
            later_model_feedback=feedback,final_observations=tracker.public(),discarded_native_pairs=discarded))
    checks={k:v for k,v in common['checks'].items() if k not in {
        'model_intent_native_queue_effect','production_feedback_reaches_later_real_requests'}}
    checks.update(model_build_choice_native_effect=bool(results) and all(r['model_plan_bound'] and r['native_ack_matches']
        and r['empty_target_baseline'] and r['positive_native_build_frames'] and r['release_after_first_queue_verified']
        and r['final_observations']['new_own_construction_object_observations'] for r in results),
        feedback_reaches_later_genuine_requests=bool(results) and all(r['later_model_feedback'] and all(
            f['observed_facts_match'] and f['within_freshness'] for f in r['later_model_feedback']) for r in results))
    stop=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    quiet=stop is not None and not any(r['kind'] in {'commander_model_call_started','model_macro_construction_prepared',
        'model_macro_production_prepared','model_macro_dispatch_prepared'} for r in events[stop+1:])
    some_effect=any(r['model_plan_bound'] and r['native_ack_matches'] and r['empty_target_baseline']
        and r['positive_native_build_frames'] and r['release_after_first_queue_verified']
        and r['final_observations']['new_own_construction_object_observations'] for r in results)
    lifecycle=(bool(results) and all(r['model_plan_bound'] and r['native_ack_matches'] and r['empty_target_baseline']
        and r['bounded_release_verified'] for r in results) and all(bool(v) for k,v in checks.items()
            if k!='model_build_choice_native_effect'))
    user_stop=status['state']=='stopped' and status['reason_code']=='user_stop' and quiet
    return dict(kind='desktop_macro_construction_evidence_assessment',run_id=run_id,session_id=final['session_id'],checks=checks,
        construction_commands=len(results),construction_results=results,real_model_responses=common['real_model_responses'],
        native_plan_dispatches=common['native_plan_dispatches'],native_construction_subset_verified=all(bool(v) for v in checks.values()),
        user_stop_completed=user_stop,some_model_construction_effect_verified=bool(some_effect),
        bounded_construction_lifecycle_verified=lifecycle,
        durable_construction_loop_verified=lifecycle and bool(some_effect) and user_stop and not any(r['kind']=='host_fault' for r in events),
        directed_acceptance_scenario='本轮建造链路验收场景' in profile.get('custom_traits',''),
        autonomous_build_choice_verified=False,free_choice_style_effect_verified=False,
        terminal_state=status['state'],terminal_reason=status['reason_code'],construction_completed_verified=False,
        exclusive_model_attribution_verified=False,full_G5_verified=False,full_G6_verified=False,full_G7_verified=False,
        formal_goal_complete=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-directory',type=Path,required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_assessment_directory_required')
    value=assess(a.run_directory.resolve(),a.run_id);out.mkdir(parents=True);shutil.copy2(__file__,out/'assessor.py')
    value['assessor_sha256']=sha(Path(__file__))
    (out/'assessment.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k!='construction_results'}))


if __name__=='__main__':main()
