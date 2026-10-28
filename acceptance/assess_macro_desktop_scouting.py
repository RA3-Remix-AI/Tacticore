"""Join real model scouting, native groups, lawful contacts and later requests.

No exclusive revelation, mission success or arbitrary-region claim is inferred.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import assess,records,load,sha
from integration.host_runtime.macro_policy_runtime import trial

def evaluate(run,run_id,download,original):
    common=assess(run,run_id,download,original);host=run/'battle-host'
    pre,final,manifest,raw,_=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    events=records(host/'host-events.jsonl');snapshots=records(host/'macro-snapshots.jsonl')
    plans={r['plan_id']:r['plan'] for r in events if r['kind']=='plan_applied'}
    requests=[r for r in events if r['kind']=='model_macro_request_context']
    response_ids={r['snapshot_id'] for r in events if r['kind']=='commander_model_response_returned'}
    dispatches=[r for r in events if r['kind']=='model_macro_scout_acknowledged']
    all_dispatches=[r for r in events if r['kind'] in ('model_macro_native_acknowledged','model_macro_production_acknowledged',
        'model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged')]
    acks={r['command_id']:r for r in raw if r['kind']=='command_acknowledged'}
    observations=[r['observation'] for r in raw if r['kind']=='macro_observation' and 'observation' in r]
    action_flags={r['action']:r['flag'] for r in manifest['consumers']};flag=action_flags['scout'];results=[]
    for d in dispatches:
        plan=plans.get(d['plan_id'],{});ack=acks.get(d['command_id'],{});native=ack.get('native',{})
        release_id=str(uuid.uuid5(uuid.UUID(final['session_id']),d['plan_id']+':scout-release:'+common['effective_hash']))
        release=acks.get(release_id);begin=native.get('last_frame',0);end=release['native']['last_frame'] if release else final['native']['last_frame']
        tracks={};active_frames=[];cleared=[]
        for o in observations:
            state=o['state_scores'].get(flag,{})
            matching=[r for r in o['runtimes'] if r['group']==state.get('group') and r['native_execution_active']]
            if begin<=o['frame']<end and state.get('score',0)>0:
                owned=False
                for t in matching:
                    for g in t.get('owned_groups',[]):
                        if not g.get('found') or not g.get('all_members_resolved'):continue
                        for m in g['members']:
                            if m['owner']!=pre['native']['player']:raise ValueError('foreign_scout_member')
                            tracks.setdefault((t['address'],g['native_id'],m['thing_id']),[]).append((o['frame'],m['xyz']))
                            owned=True
                if owned:active_frames.append(o['frame'])
            if o['frame']>end and state.get('score')==0 and not matching:cleared.append(o['frame'])
        displacement=[dict(samples=len(t),first_frame=t[0][0],last_frame=t[-1][0],
            maximum_distance_from_first=max(math.dist(t[0][1],v[1]) for v in t)) for t in tracks.values()]
        candidates=[s for s in snapshots if s['game_time_seconds']*15<=begin]
        baseline=max(candidates,key=lambda s:s['game_time_seconds']) if candidates else None
        def current(s):return {c['contact_id'] for c in s['battlefield']['contacts'] if c['currently_visible'] and c['relation']=='enemy'}
        legal_ids=set()
        if baseline:
            for s in snapshots:
                if begin<=s['game_time_seconds']*15<=end and s['battlefield']['visibility_verified'] and s['battlefield']['viewer_player_id']==3:
                    legal_ids.update(current(s)-current(baseline))
        expected_mask=sum(1<<manifest['flags'].index(action_flags[a]) for a in d['actions'])
        next_begin=min((acks[x['command_id']]['native']['last_frame'] for x in dispatches
            if x['seq']>d['seq']),default=0xffffffff)
        later=[]
        for r in requests:
            c=r['context'];feedback=c.get('macro_scouting_feedback') or {};frame=feedback.get('observed_frame')
            if (c['snapshot_id'] in response_ids and type(frame) is int and begin<frame<next_begin
                    and -15<=c['game_time_seconds']*15-frame<=30
                    and feedback.get('native_execution_observed') is True and feedback.get('moved_native_groups',0)>0
                    and feedback.get('source')=='native_scout_and_lawful_view_observation'):
                later.append(r)
        later_feedback=[dict(sequence=r['sequence'],snapshot_id=r['context']['snapshot_id'],feedback=r['context']['macro_scouting_feedback']) for r in later]
        results.append(dict(plan_id=d['plan_id'],native_seq=d['seq'],begin_frame=begin,release_or_stop_frame=end,
            real_model_plan_bound=plan.get('origin')=='model' and plan.get('macro_actions')==d['actions']
                and plan.get('session_id')==final['session_id'] and plan.get('snapshot_id') in response_ids,
            native_ack_matches=ack.get('seq')==d['seq'] and native.get('applied_mask')==expected_mask,
            native_positive_own_group_samples=len(set(active_frames)),own_group_tracks=displacement,
            own_native_group_movement_verified=any(t['samples']>=2 and t['maximum_distance_from_first']>10 for t in displacement),
            new_legal_contacts_in_bound_window=len(legal_ids),native_inactive_after_release_samples=len(cleared),
            bounded_native_duration=0<native.get('deadline_frame',0)-begin<=1350,
            known_release_or_terminal_cleanup=(release is not None and release['native']['applied_mask']==0
                and release['native']['last_frame']>=begin) or release is None and final['cleanup_verified'] is True,
            later_real_model_feedback=later_feedback,
            feedback_returned_to_later_model_verified=bool(later_feedback)))
    source=next(r for r in load(host/'sources.json')['sources'] if Path(r['path']).name=='macro_scouting.py')
    checks=dict(**{k:v for k,v in common['checks'].items() if k not in ('native_ack_and_budget_effect',)},
        pre_execution_scout_controller_frozen=sha(host/'source'/source['copy'])==source['sha256'],
        native_scout_effect_verified=bool(results) and all(r['real_model_plan_bound'] and r['native_ack_matches']
            and r['native_positive_own_group_samples']>=2 and r['own_native_group_movement_verified'] for r in results),
        scouting_feedback_reaches_later_real_model=bool(results) and all(r['feedback_returned_to_later_model_verified'] for r in results))
    positive=lambda r:r['real_model_plan_bound'] and r['native_ack_matches'] and r['native_positive_own_group_samples']>=2 and r['own_native_group_movement_verified']
    bounded=bool(results) and all(r['real_model_plan_bound'] and r['native_ack_matches'] and r['bounded_native_duration']
        and r['known_release_or_terminal_cleanup'] for r in results)
    some_loop=any(positive(r) and r['feedback_returned_to_later_model_verified'] for r in results)
    stop=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    quiet=stop is not None and not any(r['kind']=='commander_model_call_started' or r['kind'].endswith('_prepared')
        or r['kind'].startswith('model_macro_') and r['kind'].endswith('_acknowledged') for r in events[stop+1:])
    subset_keys=('exact_pre_execution_sources_retained','current_profile_consumed','exact_public_request_context_retained',
        'real_provider_response','macro_unit_jobs_absent','native_cleanup_verified','multiple_real_model_rounds',
        'native_feedback_in_each_followup_request','downloaded_export_matches','pre_execution_scout_controller_frozen')
    return dict(kind='desktop_macro_scouting_assessment',run_id=run_id,session_id=final['session_id'],checks=checks,
        real_model_responses=common['real_model_responses'],native_macro_plan_dispatches=len(all_dispatches),scouting_commands=len(dispatches),
        scouting_results=results,scouting_loop_verified=all(checks.values()),exclusive_visibility_attribution_verified=False,
        all_scouting_attempts_have_effect=checks['native_scout_effect_verified'],
        some_scouting_native_effect_verified=any(positive(r) for r in results),
        bounded_scouting_lifecycles_verified=bounded,no_new_commands_after_stop_verified=quiet,
        bounded_scouting_feedback_loop_verified=some_loop and bounded and quiet and all(checks[k] for k in subset_keys),
        arbitrary_region_selection_verified=False,mission_success_verified=False,full_G6_verified=False,full_G7_verified=False,
        formal_goal_complete=False,evidence={**common['evidence'],str(host/'macro-snapshots.jsonl'):sha(host/'macro-snapshots.jsonl')})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','download','original-export','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run-id',required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_scouting_assessment_required')
    value=evaluate(a.run_directory.resolve(),a.run_id,a.download.resolve(),a.original_export.resolve())
    out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('scouting_results','evidence')}))

if __name__=='__main__':main()
