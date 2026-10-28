"""Join genuine model infrastructure-defense plans, native groups and feedback.

The native AI chooses the friendly structure and operates its units. Presence
near audited own infrastructure is the bounded effect, not mission success.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import assess,records,load,sha
from assess_macro_base_defense import defense_presence,PACKAGE_SHA
from integration.host_runtime.macro_policy_runtime import trial

GOAL='original_native_defense_of_own_infrastructure'
DISPATCHES=('model_macro_native_acknowledged','model_macro_production_acknowledged',
    'model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged')


def evaluate(run,run_id,download,original):
    common=assess(run,run_id,download,original);host=run/'battle-host'
    pre,final,manifest,raw,native_evidence=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    if manifest['package_sha256']!=PACKAGE_SHA:raise ValueError('base_defense_package_required')
    consumer=next(r for r in manifest['consumers'] if r['action']=='deploydefense')
    if (consumer.get('target_policy')!='original_native_friendly_land_structure'
            or consumer.get('native_tactic')!='StaticDefense'
            or consumer.get('native_micro_manager')!='DefenseMicroManager'
            or consumer.get('native_target_heuristic')!='FriendlyLandStructureHeuristic'):
        raise ValueError('base_defense_native_consumer_required')
    events=records(host/'host-events.jsonl')
    plans={r['plan_id']:r['plan'] for r in events if r['kind']=='plan_applied'}
    requests={r['context']['snapshot_id']:r for r in events if r['kind']=='model_macro_request_context'}
    responses={r['snapshot_id'] for r in events if r['kind']=='commander_model_response_returned'}
    regional=[r for r in events if r['kind']=='model_macro_region_acknowledged']
    dispatches=[r for r in regional if 'deploydefense' in r['actions']]
    acks={r['command_id']:r for r in raw if r['kind']=='command_acknowledged'}
    observations=[r['observation'] for r in raw if r['kind']=='macro_observation' and 'observation' in r]
    flags={r['action']:r['flag'] for r in manifest['consumers']};results=[]
    for d in dispatches:
        if d.get('goal')!=GOAL or d.get('target_region')!='region_8_3':raise ValueError('base_defense_goal_required')
        plan=plans.get(d['plan_id'],{});request=requests.get(plan.get('snapshot_id'),{})
        context=request.get('context',{});ack=acks.get(d['command_id'],{});native=ack.get('native',{})
        begin=native.get('last_frame',0);deadline=native.get('deadline_frame',0)
        release_id=str(uuid.uuid5(uuid.UUID(final['session_id']),d['plan_id']+':region-release:'+common['effective_hash']))
        release=acks.get(release_id);release_frame=release['native']['last_frame'] if release else final['native']['last_frame']
        end=min(deadline,release_frame)
        effect=defense_presence(observations,flags['deploydefense'],pre['native']['player'],begin,end)
        next_begin=min((acks[x['command_id']]['native']['last_frame'] for x in regional if x['seq']>d['seq']),default=0xffffffff)
        later=[]
        for snapshot_id,r in requests.items():
            c=r['context'];f=c.get('macro_regional_feedback') or {};frame=f.get('observed_frame')
            if (snapshot_id not in responses or type(frame) is not int or not begin<frame<next_begin
                    or not -15<=c['game_time_seconds']*15-frame<=30
                    or f.get('source')!='native_regional_group_observation' or f.get('goal')!=GOAL
                    or f.get('native_tactic_family')!='static_defense'
                    or f.get('target_policy')!='original_native_friendly_land_structure'
                    or f.get('action')!='deploydefense' or f.get('target_region')!='region_8_3'
                    or f.get('native_execution_observed') is not True
                    or f.get('defender_groups_near_infrastructure',0)<=0):continue
            upto=defense_presence(observations,flags['deploydefense'],pre['native']['player'],begin,min(end,frame+1))
            if upto['native_defender_presence_near_own_infrastructure_verified']:
                later.append(dict(sequence=r['sequence'],snapshot_id=snapshot_id,feedback=f))
        catalog=context.get('macro_policy_catalog',{}).get('deploydefense',{})
        catalog_bound=('deploydefense' in context.get('allowed_macro_actions',[])
            and catalog.get('goal')==GOAL and catalog.get('target_region')=='region_8_3'
            and catalog.get('target_policy')=='original_native_friendly_land_structure'
            and catalog.get('native_ai_selects_structure_and_operates_group') is True
            and catalog.get('maximum_duration_seconds')==60)
        expected_mask=sum(1<<manifest['flags'].index(flags[a]) for a in d['actions'])
        results.append(dict(plan_id=d['plan_id'],action='deploydefense',goal=GOAL,target_region='region_8_3',
            native_seq=d['seq'],begin_frame=begin,native_deadline_frame=deadline,effect_window_end=end,
            release_or_stop_frame=release_frame,
            real_model_plan_bound=plan.get('origin')=='model' and plan.get('macro_actions')==d['actions']
                and plan.get('objective_region')=='region_8_3' and plan.get('session_id')==final['session_id']
                and plan.get('snapshot_id') in responses and context.get('session_id')==final['session_id'],
            qualified_goal_in_actual_request=catalog_bound,
            native_ack_matches=ack.get('seq')==d['seq'] and native.get('applied_mask')==expected_mask,
            bounded_native_duration=0<deadline-begin<=900,
            known_release_or_terminal_cleanup=(release is not None and release['native']['applied_mask']==0
                and release_frame>=begin) or release is None and final['cleanup_verified'] is True,
            **effect,later_real_model_feedback=later,feedback_returned_to_later_model_verified=bool(later)))
    frozen=load(host/'sources.json')['sources']
    names={'macro_regions.py','macro_base_defense_scope.py','macro_live.py'}
    sources=[r for r in frozen if Path(r['path']).name in names]
    source_valid={Path(r['path']).name for r in sources}==names and all(sha(host/'source'/r['copy'])==r['sha256'] for r in sources)
    subset=('exact_pre_execution_sources_retained','current_profile_consumed','exact_public_request_context_retained',
        'real_provider_response','macro_unit_jobs_absent','native_cleanup_verified','multiple_real_model_rounds',
        'native_feedback_in_each_followup_request','downloaded_export_matches')
    shared={**{k:common['checks'][k] for k in subset},'pre_execution_defense_sources_retained':source_valid}
    stop=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    quiet=stop is not None and not any(r['kind']=='commander_model_call_started' or r['kind'].endswith('_prepared')
        or r['kind'] in DISPATCHES for r in events[stop+1:])
    bounded=bool(results) and all(r['real_model_plan_bound'] and r['qualified_goal_in_actual_request']
        and r['native_ack_matches'] and r['bounded_native_duration'] and r['known_release_or_terminal_cleanup'] for r in results)
    positive=lambda r:r['native_defender_presence_near_own_infrastructure_verified'] and r['effect_within_model_maximum_60_seconds']
    return dict(kind='desktop_model_native_infrastructure_defense_assessment',run_id=run_id,session_id=final['session_id'],
        shared_checks=shared,real_model_responses=common['real_model_responses'],defense_commands=len(results),
        defense_results=results,some_model_native_defense_effect_verified=any(positive(r) for r in results),
        bounded_defense_lifecycles_verified=bounded,no_new_commands_after_stop_verified=quiet,
        bounded_model_defense_feedback_loop_verified=all(shared.values()) and bounded and quiet
            and any(positive(r) and r['feedback_returned_to_later_model_verified'] for r in results),
        native_ai_selects_structure_and_operates_units=True,exact_structure_selection_verified=False,
        mission_success_verified=False,combat_outcome_verified=False,full_G6_verified=False,formal_goal_complete=False,
        evidence={**common['evidence'],**native_evidence,str(host/'macro-snapshots.jsonl'):sha(host/'macro-snapshots.jsonl')})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','download','original-export','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run-id',required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_defense_assessment_required')
    value=evaluate(a.run_directory.resolve(),a.run_id,a.download.resolve(),a.original_export.resolve())
    out.mkdir();shutil.copy2(__file__,out/'assessor.py');shutil.copy2(ROOT/'acceptance/assess_macro_base_defense.py',out/'presence-helper.py')
    value['assessor_sha256']=sha(out/'assessor.py');value['presence_helper_sha256']=sha(out/'presence-helper.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('defense_results','evidence')}))


if __name__=='__main__':main()
