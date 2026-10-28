"""Join genuine model destinations with owned native groups and later feedback.

Movement toward either fixed public waypoint is a bounded effect. It does not
prove arrival, combat success, selection of an arbitrary point or micro control.
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

TARGETS={'deployattack':('region_1_3',(857.539978,2015.354004)),
         'deploydefense':('region_8_3',(4404.116699,2016.024780))}
DISPATCHES=('model_macro_native_acknowledged','model_macro_production_acknowledged',
    'model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged')

def tracks_in_window(observations,flag,owner,begin,end,target):
    tracks={};active=set();cleared=set()
    for o in observations:
        state=o['state_scores'].get(flag,{})
        matching=[r for r in o['runtimes'] if r['group']==state.get('group') and r['native_execution_active']]
        if begin<=o['frame']<end and state.get('score',0)>0:
            for t in matching:
                if t.get('native_tactic_family')!='simple_attack':raise ValueError('regional_native_family_mismatch')
                for g in t.get('owned_groups',[]):
                    if not g.get('found') or not g.get('all_members_resolved'):continue
                    for m in g['members']:
                        if m['owner']!=owner:raise ValueError('foreign_regional_member')
                        if len(m['xyz'])!=3 or any(not math.isfinite(v) for v in m['xyz']):
                            raise ValueError('regional_nonfinite_position')
                        tracks.setdefault((t['address'],g['native_id'],m['thing_id']),[]).append((o['frame'],m['xyz']))
                        active.add(o['frame'])
        if o['frame']>end and state.get('score')==0 and not matching:cleared.add(o['frame'])
    summary=[dict(samples=len(t),first_frame=t[0][0],last_frame=t[-1][0],
        displacement=max(math.dist(t[0][1],v[1]) for v in t),
        progress_toward_public_target=max(math.dist(t[0][1][:2],target)-math.dist(v[1][:2],target) for v in t))
        for t in tracks.values()]
    return summary,len(active),len(cleared)


def progressing_members(observations,flag,owner,begin,end,target):
    """Private identity join used only to check later macro reassignment."""
    tracks={}
    for o in observations:
        if not begin<=o['frame']<end:continue
        state=o['state_scores'].get(flag,{})
        if state.get('score',0)<=0:continue
        for tactic in o['runtimes']:
            if tactic['group']!=state.get('group') or not tactic['native_execution_active']:continue
            if tactic.get('native_tactic_family')!='simple_attack':raise ValueError('regional_native_family_mismatch')
            for group in tactic.get('owned_groups',[]):
                if not group.get('found') or not group.get('all_members_resolved'):continue
                for member in group['members']:
                    if member['owner']!=owner:raise ValueError('foreign_regional_member')
                    point=member['xyz']
                    if len(point)!=3 or any(not math.isfinite(v) for v in point):raise ValueError('regional_nonfinite_position')
                    key=(member['thing_id'],member['address'],member['type_hash'])
                    tracks.setdefault(key,{})[o['frame']]=point
    positive={}
    for key,track in tracks.items():
        ordered=sorted(track.items());first=ordered[0][1]
        if (len(ordered)>=2 and max(math.dist(first[:2],target)-math.dist(p[:2],target) for _,p in ordered)>50
                and max(math.dist(first,p) for _,p in ordered)>10):positive[key]=ordered
    return positive


def reassigned_members(observations,windows):
    """Require progress at both destinations plus continuous live own identity.

    Presence between samples cannot prove every intervening simulation frame.
    No identities, addresses, coordinates or unit orders enter the report.
    """
    result=[]
    for earlier,later in zip(windows,windows[1:]):
        if earlier['target_region']==later['target_region']:continue
        verified=0;minimum_samples=None
        for key in set(earlier['members'])&set(later['members']):
            start=earlier['members'][key][0][0];end=later['members'][key][-1][0]
            samples=[o['construction_feedback'] for o in observations if start<=o['frame']<=end
                and 'construction_feedback' in o]
            if (len(samples)<2 or any(c.get('enemy_details_read') is not False or
                    not any((m['thing_id'],m['address'],m['type_hash'])==key and math.isfinite(m['hp']) and m['hp']>0
                        for m in c['own_objects']) for c in samples)):
                continue
            verified+=1;minimum_samples=min(minimum_samples or len(samples),len(samples))
        result.append(dict(earlier_plan_id=earlier['plan_id'],later_plan_id=later['plan_id'],
            earlier_native_seq=earlier['native_seq'],later_native_seq=later['native_seq'],
            earlier_region=earlier['target_region'],later_region=later['target_region'],
            same_live_own_members_progressing_at_both_targets=verified,
            minimum_intervening_own_census_samples=minimum_samples or 0,
            continuous_between_samples_verified=False,unit_operation_policy='native_ai'))
    return result


def evaluate(run,run_id,download,original):
    common=assess(run,run_id,download,original);host=run/'battle-host'
    pre,final,manifest,raw,_=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    events=records(host/'host-events.jsonl')
    plans={r['plan_id']:r['plan'] for r in events if r['kind']=='plan_applied'}
    requests=[r for r in events if r['kind']=='model_macro_request_context']
    response_ids={r['snapshot_id'] for r in events if r['kind']=='commander_model_response_returned'}
    dispatches=[r for r in events if r['kind']=='model_macro_region_acknowledged']
    all_dispatches=[r for r in events if r['kind'] in DISPATCHES]
    acks={r['command_id']:r for r in raw if r['kind']=='command_acknowledged'}
    observations=[r['observation'] for r in raw if r['kind']=='macro_observation' and 'observation' in r]
    flags={r['action']:r['flag'] for r in manifest['consumers']};results=[];member_windows=[]
    for d in dispatches:
        regional=[a for a in d['actions'] if a in TARGETS]
        if len(regional)!=1:raise ValueError('regional_action_count')
        action=regional[0];region,target=TARGETS[action];plan=plans.get(d['plan_id'],{})
        ack=acks.get(d['command_id'],{});native=ack.get('native',{});begin=native.get('last_frame',0)
        release_id=str(uuid.uuid5(uuid.UUID(final['session_id']),d['plan_id']+':region-release:'+common['effective_hash']))
        release=acks.get(release_id);end=release['native']['last_frame'] if release else final['native']['last_frame']
        tracks,active,cleared=tracks_in_window(observations,flags[action],pre['native']['player'],begin,end,target)
        members=progressing_members(observations,flags[action],pre['native']['player'],begin,end,target)
        if members:member_windows.append(dict(plan_id=d['plan_id'],native_seq=d['seq'],target_region=region,members=members))
        expected_mask=sum(1<<manifest['flags'].index(flags[a]) for a in d['actions'])
        next_begin=min((acks[x['command_id']]['native']['last_frame'] for x in dispatches if x['seq']>d['seq']),default=0xffffffff)
        later=[]
        for r in requests:
            c=r['context'];feedback=c.get('macro_regional_feedback') or {};frame=feedback.get('observed_frame')
            if (c['snapshot_id'] in response_ids and type(frame) is int and begin<frame<next_begin
                    and -15<=c['game_time_seconds']*15-frame<=30
                    and feedback.get('source')=='native_regional_group_observation'
                    and feedback.get('action')==action and feedback.get('target_region')==region
                    and feedback.get('native_execution_observed') is True
                    and feedback.get('groups_progressing_toward_region',0)>0):
                upto,_,_=tracks_in_window(observations,flags[action],pre['native']['player'],begin,min(end,frame+1),target)
                if any(t['samples']>=2 and t['progress_toward_public_target']>50 for t in upto):
                    later.append(dict(sequence=r['sequence'],snapshot_id=c['snapshot_id'],feedback=feedback))
        results.append(dict(plan_id=d['plan_id'],action=action,target_region=region,native_seq=d['seq'],begin_frame=begin,
            release_or_stop_frame=end,real_model_plan_bound=plan.get('origin')=='model' and plan.get('macro_actions')==d['actions']
                and plan.get('objective_region')==region and d.get('target_region')==region
                and plan.get('session_id')==final['session_id'] and plan.get('snapshot_id') in response_ids,
            native_ack_matches=ack.get('seq')==d['seq'] and native.get('applied_mask')==expected_mask,
            native_positive_own_group_samples=active,own_group_tracks=tracks,native_inactive_after_release_samples=cleared,
            own_native_group_progress_verified=any(t['samples']>=2 and t['displacement']>10 and t['progress_toward_public_target']>50 for t in tracks),
            bounded_native_duration=0<native.get('deadline_frame',0)-begin<=900,
            known_release_or_terminal_cleanup=(release is not None and release['native']['applied_mask']==0
                and release['native']['last_frame']>=begin) or release is None and final['cleanup_verified'] is True,
            later_real_model_feedback=later,feedback_returned_to_later_model_verified=bool(later)))
    frozen=load(host/'sources.json')['sources']
    region_sources=[r for r in frozen if Path(r['path']).name in ('macro_regions.py','macro_region_scope.py')]
    source_valid=len(region_sources)==2 and all(sha(host/'source'/r['copy'])==r['sha256'] for r in region_sources)
    positive=lambda r:r['real_model_plan_bound'] and r['native_ack_matches'] and r['native_positive_own_group_samples']>=2 and r['own_native_group_progress_verified']
    bounded=bool(results) and all(r['real_model_plan_bound'] and r['native_ack_matches'] and r['bounded_native_duration'] and r['known_release_or_terminal_cleanup'] for r in results)
    stop=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    quiet=stop is not None and not any(r['kind']=='commander_model_call_started' or r['kind'].endswith('_prepared')
        or r['kind'] in DISPATCHES for r in events[stop+1:])
    subset=('exact_pre_execution_sources_retained','current_profile_consumed','exact_public_request_context_retained',
        'real_provider_response','macro_unit_jobs_absent','native_cleanup_verified','multiple_real_model_rounds',
        'native_feedback_in_each_followup_request','downloaded_export_matches')
    shared=all(common['checks'][k] for k in subset) and source_valid
    reassigned=reassigned_members(observations,member_windows)
    return dict(kind='desktop_macro_regional_assessment',run_id=run_id,session_id=final['session_id'],
        shared_checks={**{k:common['checks'][k] for k in subset},'pre_execution_regional_sources_retained':source_valid},
        real_model_responses=common['real_model_responses'],native_macro_plan_dispatches=len(all_dispatches),regional_commands=len(results),
        regional_results=results,some_regional_native_effect_verified=any(positive(r) for r in results),
        bounded_regional_lifecycles_verified=bounded,no_new_commands_after_stop_verified=quiet,
        bounded_regional_feedback_loop_verified=shared and bounded and quiet and any(positive(r) and r['feedback_returned_to_later_model_verified'] for r in results),
        model_selected_public_regions=sorted({r['target_region'] for r in results if positive(r)}),
        arrival_verified=False,mission_success_verified=False,arbitrary_xy_control=False,
        same_units_reassigned_verified=shared and bounded and quiet and any(
            r['same_live_own_members_progressing_at_both_targets']>0 for r in reassigned),
        observed_macro_reassignments=reassigned,
        full_G6_verified=False,full_G7_verified=False,formal_goal_complete=False,
        evidence={**common['evidence'],str(host/'macro-snapshots.jsonl'):sha(host/'macro-snapshots.jsonl')})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','download','original-export','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run-id',required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_regional_assessment_required')
    value=evaluate(a.run_directory.resolve(),a.run_id,a.download.resolve(),a.original_export.resolve())
    out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('regional_results','evidence')}))

if __name__=='__main__':main()
