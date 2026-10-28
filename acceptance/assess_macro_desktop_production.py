"""Join genuine model production intent with native gates, queues and next requests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from integration.host_runtime.macro_policy_runtime import trial
from integration.host_runtime.macro_production_feedback import ProductionFeedback,TARGETS,frames


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def records(path):return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(run,run_id):
    host=run/'battle-host';native=ROOT/'reports'/('macro-desktop-'+run_id)
    pre,final,manifest,stream,_=trial(native)
    status=load(host/'host-status.json');profile=load(host/'profile.json');events=records(host/'host-events.jsonl')
    sources=load(host/'sources.json')['sources']
    retained=all((host/'source'/r['copy']).resolve().parent==(host/'source').resolve()
        and sha(host/'source'/r['copy'])==r['sha256'] for r in sources)
    frozen={r['path']:host/'source'/r['copy'] for r in sources}
    bundles=[path for path in frozen.values() if path.name.endswith('macro-budget-bundle.json')]
    pin_sources=bool(len(bundles)==1) and all(str(path) not in load(bundles[0])['pins']
        or sha(copy)==load(bundles[0])['pins'][str(path)] for path,copy in ((Path(p),c) for p,c in frozen.items()))
    requests=[r for r in events if r['kind']=='model_macro_request_context']
    responses=[r for r in events if r['kind']=='commander_model_response_returned']
    plans={r['plan_id']:r['plan'] for r in events if r['kind']=='plan_applied'}
    dispatches=[r for r in events if r['kind']=='model_macro_production_acknowledged']
    acks={r['command_id']:r for r in stream if r['kind']=='command_acknowledged'}
    consumers={r['action']:r['flag'] for r in manifest['consumers']}
    results=[]
    for command in dispatches:
        ack=acks.get(command['command_id'],{});plan=plans.get(command['plan_id'],{})
        quantity=plan.get('macro_production') or {};action=quantity.get('action');number=quantity.get('additional_count')
        if action not in TARGETS or type(number) is not int or not 1<=number<=3:
            raise ValueError('recorded_production_plan_invalid')
        request=next((r['context'] for r in requests if r['context']['snapshot_id']==plan.get('snapshot_id')), {})
        request_sequence=next((r['sequence'] for r in requests if r['context'] is request),0)
        plan_bound=(plan.get('origin')=='model' and plan.get('session_id')==final['session_id']
            and plan.get('player_id')==3 and plan.get('commander_id')==profile['profile_id']
            and plan.get('macro_actions')==command['actions']
            and quantity==dict(action=action,additional_count=command['additional_count'])
            and action in request.get('allowed_macro_actions',())
            and number in request.get('macro_policy_catalog',{}).get(action,{}).get('quantity',{}).get('allowed_additional_counts',()))
        expected=sum(1<<manifest['flags'].index(consumers[action]) for action in command['actions'])
        ack_bound=ack.get('seq')==command['seq'] and ack.get('native',{}).get('applied_mask')==expected
        position=next((i for i,r in enumerate(stream) if r is ack),-1)
        census=None;builder=None
        for row in stream[:position]:
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']=='native_builder_observation' and 'observation' in row:builder=row['observation']
        tracker=ProductionFeedback(action,number,builder,census)
        expiry=min(int(plan['expires_at_game_seconds']*15),ack['native']['deadline_frame'])
        baseline_empty=not tracker.baseline_queues
        release=None;release_on_time=False;release_reason=None;bounded_release=False;positive=[];snapshots={};discarded=0
        next_command_ids={r['command_id'] for r in dispatches if r['seq']>command['seq']}
        next_production_frame=min((acks[key]['native']['last_frame'] for key in next_command_ids if key in acks),default=0xffffffff)
        for row in stream[position+1:]:
            if row['kind']=='command_acknowledged' and row['command_id'] in next_command_ids:break
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']=='native_builder_observation' and 'observation' in row:
                sample=row['observation']
                try:
                    pair=frames(sample,census)
                    # Native expiry precedes observation of a later queue.
                    # Replay the same chronological boundary independently;
                    # never attribute a post-expiry queue to this intent.
                    if max(pair)>=expiry and not tracker.policy_released:
                        tracker.mark_policy_released('expired')
                    public=tracker.observe(sample,census)
                except ValueError:discarded+=1;continue
                snapshots[(public['builder_frame'],public['own_census_frame'])]=public
                if release is None and any(entry['flag']==consumers[action] and entry['state_score']>0
                        and any(e['build_type_hash_raw']==TARGETS[action][0] for e in entry['entries']) for entry in sample['macro_entries']):
                    positive.append(sample['frame'])
            if (row['kind']=='command_acknowledged' and row['seq']>command['seq'] and release is None):
                release=row
                if len(tracker.new_queues)>=number and row['native']['applied_mask']==0:
                    release_on_time=(tracker.frames[0]<=row['native']['last_frame']<=tracker.frames[0]+15
                        and row['native']['last_frame']<=ack.get('native',{}).get('deadline_frame',0))
                    release_reason='queue_target_observed';bounded_release=release_on_time
                elif row['native']['applied_mask']==0:
                    if row['native']['kind']==2 and status['state']=='stopped' and status['reason_code']=='user_stop':
                        release_reason='stopped';bounded_release=True
                    elif not tracker.eligible or tracker.unavailable:
                        release_reason='producer_unavailable';bounded_release=True
                    elif len(tracker.eligible)!=1:
                        release_reason='scope_changed';bounded_release=True
                    else:
                        if expiry<=row['native']['last_frame']<=expiry+30:
                            release_reason='expired';bounded_release=True
                if release_reason:
                    tracker.mark_policy_released(release_reason)
                    public=tracker.public();snapshots[(public['builder_frame'],public['own_census_frame'])]=public
        feedback=[]
        for r in requests:
            c=r['context'];value=c.get('macro_production_feedback')
            if r['sequence']<=request_sequence:continue
            if value is None or c['game_time_seconds']<plan.get('based_on_game_time_seconds',86400):continue
            if (value.get('action')!=action or value.get('additional_count_requested')!=number
                    or value.get('builder_frame',0)>=next_production_frame):continue
            observation=snapshots.get((value.get('builder_frame'),value.get('own_census_frame')))
            matches=(observation is not None and value.get('source')=='native_production_observation'
                and {'observed_new_queue_count','new_own_unit_observations','policy_released','completed_units_verified'}<=set(value)
                and all(observation[k]==v for k,v in value.items() if k in observation))
            fresh=all(-15<=c['game_time_seconds']*15-value[key]<=30 for key in ('builder_frame','own_census_frame'))
            feedback.append(dict(request_sequence=r['sequence'],observed_counts_match=matches,within_freshness=fresh))
        release_verified=bool(release and release_on_time and tracker.policy_released and release['native']['applied_mask']==0
            and len(tracker.new_queues)==number and not tracker.public()['queue_target_overshot'])
        results.append(dict(plan_id=command['plan_id'],action=action,additional_count=number,request_sequence=request_sequence,
            request_snapshot_id=plan.get('snapshot_id'),native_seq=command['seq'],
            model_plan_bound=plan_bound,native_ack_matches=ack_bound,empty_target_queue_baseline=baseline_empty,
            positive_native_build_state_frames=positive,release_after_observed_queue_target=release_verified,
            bounded_release_verified=bounded_release,release_reason=release_reason,
            observed_queue_goal_met=len(tracker.new_queues)==number,
            production_feedback_in_followup_requests=feedback,final_observations=tracker.public(),discarded_native_pairs=discarded))
    checks=dict(pre_execution_sources_retained=retained,bundle_source_pins_match=pin_sources,
        exact_context_hashes=bool(requests) and all(hashlib.sha256(json.dumps(r['context'],ensure_ascii=False,
            allow_nan=False,separators=(',',':')).encode()).hexdigest()==r['context_sha256'] for r in requests),
        same_current_profile=bool(responses) and all(r.get('profile_revision')==profile['revision'] and
            r.get('effective_hash')==profile['effective']['effective_hash'] for r in responses),
        genuine_provider=bool(responses) and all(all((r.get('transport_receipt') or {}).get(k)==v for k,v in
            dict(real_network_verified=True,injected_transport=False,expected_origin=True,https=True,loopback=False,
                http_status=200,response_complete=True).items()) for r in responses),
        model_intent_native_queue_effect=bool(results) and all(r['model_plan_bound'] and r['native_ack_matches']
            and r['empty_target_queue_baseline'] and r['positive_native_build_state_frames'] and r['release_after_observed_queue_target'] for r in results),
        production_feedback_reaches_later_real_requests=bool(results) and all(r['release_reason']=='stopped' or
            r['production_feedback_in_followup_requests'] and all(f['observed_counts_match'] and f['within_freshness']
                for f in r['production_feedback_in_followup_requests']) for r in results),
        native_cleanup_verified=final['cleanup_verified'] and not final['unknown_command_ids'] and final['host_returncode']==0,
        no_unit_jobs=status['jobs']==[] and all(not p.get('tactical_tasks') and p.get('runtime_task') is None for p in plans.values()))
    stop_index=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    stop_quiet=stop_index is not None and not any(r['kind'] in {'commander_model_call_started','model_macro_production_prepared',
        'model_macro_dispatch_prepared'} for r in events[stop_index+1:])
    user_stop=status['state']=='stopped' and status['reason_code']=='user_stop' and stop_quiet
    lifecycle=(bool(results) and all(r['model_plan_bound'] and r['native_ack_matches'] and r['empty_target_queue_baseline']
        and r['bounded_release_verified'] for r in results) and all(bool(v) for k,v in checks.items() if k!='model_intent_native_queue_effect'))
    return dict(kind='desktop_macro_production_evidence_assessment',run_id=run_id,session_id=final['session_id'],checks=checks,
        real_model_responses=len(responses),accepted_plans=len(plans),engine_accepted_plans=status['metrics']['accepted'],
        native_plan_dispatches=len(plans),production_commands=len(results),production_results=results,
        native_production_subset_verified=all(bool(v) for v in checks.values()),terminal_state=status['state'],terminal_reason=status['reason_code'],
        user_stop_completed=user_stop,bounded_production_lifecycle_verified=lifecycle,
        durable_production_loop_verified=lifecycle and user_stop and not any(r['kind']=='host_fault' for r in events),
        completed_units_callback_verified=False,exclusive_model_attribution_verified=False,
        full_G5_verified=False,full_G6_verified=False,full_G7_verified=False,formal_goal_complete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-directory',type=Path,required=True);parser.add_argument('--run-id',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_report_directory_required')
    value=assess(args.run_directory.resolve(),args.run_id);out.mkdir(parents=True)
    shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(Path(__file__))
    (out/'assessment.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(output=str(out),checks=value['checks'],native_production_subset_verified=value['native_production_subset_verified'],
        terminal_state=value['terminal_state'],terminal_reason=value['terminal_reason'],formal_goal_complete=False)))


if __name__=='__main__':main()
