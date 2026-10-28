"""Join a genuine macro host's result boundary with independent natural-end facts."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import assess,records,load,sha
from assess_macro_budget_lifecycles import join as join_budget_lifecycles
from integration.host_runtime.macro_policy_runtime import trial


def evaluate(run,run_id,download,original_export,watch,production_assessment=None,scouting_assessment=None,regional_assessment=None,construction_assessment=None):
    common=assess(run,run_id,download,original_export)
    host=run/'battle-host';status=load(host/'host-status.json');events=records(host/'host-events.jsonl')
    pre,final,manifest,rows,_=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    archive=load(run/'research-settlement.json');independent=load(run/'post-stop-independent-native.json')
    watched=records(watch/'native-match-transitions.jsonl');watch_report=load(watch/'report.json')
    candidates=[r for r in watched if any(v.get('defeat_frame') or v.get('victory_frame') for v in r.get('result_records',[]))]
    first=min((r['simulation_frame'] for r in candidates),default=None)
    last_live=max((r.get('simulation_frame',0) for r in watched),default=0)
    first_live=min((r['simulation_frame'] for r in watched if r.get('simulation_frame')),default=None)
    observations=[r['observation'] for r in rows if r['kind']=='macro_observation' and 'observation' in r]
    acks=[r for r in rows if r['kind']=='command_acknowledged']
    ack_by_seq={r['seq']:r for r in acks};matches=[]
    all_dispatches=[r for r in events if r['kind'] in ('model_macro_native_acknowledged',
        'model_macro_production_acknowledged','model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged')]
    production_dispatches=[r for r in all_dispatches if r['kind']=='model_macro_production_acknowledged']
    construction_dispatches=[r for r in all_dispatches if r['kind']=='model_macro_construction_acknowledged']
    scouting_dispatches=[r for r in all_dispatches if r['kind']=='model_macro_scout_acknowledged']
    regional_dispatches=[r for r in all_dispatches if r['kind']=='model_macro_region_acknowledged']
    regional=None;regional_verified=not regional_dispatches
    if regional_assessment is not None:
        regional=load(regional_assessment)
        regional_verified=(regional['run_id']==run_id and regional['session_id']==final['session_id']
            and regional['native_macro_plan_dispatches']==len(all_dispatches)
            and regional['regional_commands']==len(regional_dispatches)
            and regional['bounded_regional_feedback_loop_verified'] is True
            and regional['bounded_regional_lifecycles_verified'] is True
            and regional['no_new_commands_after_stop_verified'] is True
            and sha(regional_assessment.parent/'assessor.py')==regional['assessor_sha256'])
    scouting=None;scouting_verified=not scouting_dispatches
    if scouting_assessment is not None:
        scouting=load(scouting_assessment)
        scouting_verified=(scouting['run_id']==run_id and scouting['session_id']==final['session_id']
            and scouting['native_macro_plan_dispatches']==len(all_dispatches)
            and scouting['scouting_commands']==len(scouting_dispatches)
            and scouting['bounded_scouting_feedback_loop_verified'] is True
            and scouting['bounded_scouting_lifecycles_verified'] is True
            and scouting['no_new_commands_after_stop_verified'] is True
            and sha(scouting_assessment.parent/'assessor.py')==scouting['assessor_sha256'])
    construction=None;construction_verified=not construction_dispatches
    if construction_assessment is not None:
        construction=load(construction_assessment)
        construction_verified=(construction['run_id']==run_id and construction['session_id']==final['session_id']
            and construction['native_plan_dispatches']==len(all_dispatches)
            and construction['construction_commands']==len(construction_dispatches)
            and construction['bounded_construction_lifecycle_verified'] is True
            and construction['checks']['feedback_reaches_later_genuine_requests'] is True
            and construction['checks']['pre_execution_sources_retained'] is True
            and construction['checks']['bundle_source_pins_match'] is True
            and sha(construction_assessment.parent/'assessor.py')==construction['assessor_sha256'])
    work=None;work_verified=not production_dispatches
    if production_assessment is not None:
        work=load(production_assessment)
        work_verified=(work['run_id']==run_id and work['session_id']==final['session_id']
            and work['native_plan_dispatches']==len(all_dispatches) and work['production_commands']==len(production_dispatches)
            and work['bounded_production_lifecycle_verified'] is True
            and work['checks']['production_feedback_reaches_later_real_requests'] is True
            and work['checks']['pre_execution_sources_retained'] is True and work['checks']['bundle_source_pins_match'] is True
            and sha(production_assessment.parent/'assessor.py')==work['assessor_sha256'])
    consumers={r['action']:r['flag'] for r in manifest['consumers']}
    all_acks=bool(all_dispatches) and len({r['command_id'] for r in all_dispatches})==len(all_dispatches)
    for dispatch in all_dispatches:
        ack=ack_by_seq.get(dispatch['seq'],{})
        mask=sum(1<<manifest['flags'].index(consumers[action]) for action in dispatch['actions'])
        all_acks=all_acks and ack.get('command_id')==dispatch['command_id'] and ack.get('native',{}).get('applied_mask')==mask
    for index,match in enumerate(common['native_matches']):
        ack=ack_by_seq[match['native_seq']]
        next_frame=ack_by_seq[common['native_matches'][index+1]['native_seq']]['native']['last_frame'] if index+1<len(common['native_matches']) else final['native']['last_frame']
        delegated=[o for o in observations if ack['native']['last_frame']<=o['frame']<next_frame
            and o['budget_feedback']['selected_macro_flag'] is None] if match['actions']==[] else []
        matches.append(dict(**match,matching_native_delegation_samples=len(delegated),
            corresponding_budget_or_delegation_observed=match['matching_native_samples']>=2 or len(delegated)>=2))
    stop=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    quiet=stop is not None and not any(r['kind']=='commander_model_call_started'
        or r['kind'].endswith('_prepared') or r in all_dispatches for r in events[stop+1:])
    shared={k:v for k,v in common['checks'].items() if k not in ('user_stop_completed','native_ack_and_budget_effect')}
    checks=dict(**shared,host_ended_on_native_result=status['state']=='result_candidate'
        and status['reason_code']=='native_result_requires_visual_confirmation' and not any(r['kind']=='host_fault' for r in events),
        every_budget_or_delegation_effect=bool(matches) and all(m['native_ack_matches'] and m['model_plan_bound']
            and m['corresponding_budget_or_delegation_observed'] for m in matches),
        all_model_native_acknowledgements_bound=bool(all_acks),
        bounded_work_and_feedback_verified=work_verified,
        bounded_construction_and_feedback_verified=construction_verified,
        bounded_scouting_and_feedback_verified=scouting_verified,
        bounded_regional_and_feedback_verified=regional_verified,
        no_new_requests_or_commands_after_stop=quiet,
        independent_natural_lifecycle=watch_report['session_id']==final['session_id'] and watch_report['pid']==final['pid']
            and watch_report['reason']=='native_lifecycle_frame_reset' and watch_report['read_errors']==0
            and watched[-1].get('simulation_frame')==0 and first is not None,
        native_cleanup_within_result_window=first is not None and first<=final['native']['last_frame']<=last_live,
        visual_and_replay_archive_bound=archive['session_id']==final['session_id'] and archive['pid']==final['pid']
            and archive['process_creation_filetime']==final['process_creation_filetime']
            and archive['natural_settlement_verified'] is True
            and all((run/archive[key]).resolve().parent==run and sha(run/archive[key])==archive[key+'_sha256'] for key in ('screenshot','replay')),
        later_original_native_readback_clear=independent['session_id']==final['session_id']
            and independent['state']['simulation_frame']==0 and len(independent['flags']['flags'])==13
            and all(not r['present'] or r['value'] is False for r in independent['flags']['flags']))
    # Retain the strict every-intent effect result above. Natural session
    # operation is a separate claim: an unadopted native preference may expire
    # correctly, and must never be relabelled as an observed effect.
    budgets,all_bound=join_budget_lifecycles(events,rows,manifest,final)
    bounded_checks={k:v for k,v in checks.items() if k not in ('every_budget_or_delegation_effect',
        'bounded_scouting_and_feedback_verified','bounded_regional_and_feedback_verified')}
    bounded_checks.update(all_budget_intents_bound_and_time_limited=all_bound
        and all(r['model_and_ack_bound'] and r['bounded_activation'] for r in budgets),
        explicit_delegation_observed=all(r['native_ack_matches'] and r['model_plan_bound']
            and r['matching_native_delegation_samples']>=2 for r in matches if not r['actions']),
        bounded_scouting_lifecycles=not scouting_dispatches or bool(scouting)
            and scouting['run_id']==run_id and scouting['session_id']==final['session_id']
            and scouting['scouting_commands']==len(scouting_dispatches)
            and scouting['bounded_scouting_lifecycles_verified'] is True
            and scouting['no_new_commands_after_stop_verified'] is True
            and sha(scouting_assessment.parent/'assessor.py')==scouting['assessor_sha256'],
        bounded_regional_lifecycles=not regional_dispatches or bool(regional)
            and regional['run_id']==run_id and regional['session_id']==final['session_id']
            and regional['regional_commands']==len(regional_dispatches)
            and regional['bounded_regional_lifecycles_verified'] is True
            and regional['no_new_commands_after_stop_verified'] is True
            and sha(regional_assessment.parent/'assessor.py')==regional['assessor_sha256'],
        some_observed_effect_returns_to_real_model=any(r['native_adoption_verified']
            and r['feedback_to_later_genuine_response_verified'] for r in budgets)
            or bool(regional) and regional_verified or bool(scouting) and scouting_verified
            or bool(work) and work_verified and any(r['model_plan_bound'] and r['native_ack_matches']
                and r['final_observations']['observed_new_queue_count']>0 for r in work['production_results'])
            or bool(construction) and construction_verified and construction['some_model_construction_effect_verified'] is True)
    evidence_paths=[run/'research-settlement.json',run/'research-settlement.png',run/'research-natural.RA3Replay',
        run/'post-stop-independent-native.json',host/'macro-release.json',watch/'report.json',watch/'native-match-transitions.jsonl',download,original_export]
    if production_assessment is not None:evidence_paths.append(production_assessment)
    if scouting_assessment is not None:evidence_paths.append(scouting_assessment)
    if regional_assessment is not None:evidence_paths.append(regional_assessment)
    if construction_assessment is not None:evidence_paths.append(construction_assessment)
    return dict(kind='macro_host_natural_release_assessment',run_id=run_id,session_id=final['session_id'],checks=checks,
        real_model_responses=common['real_model_responses'],native_macro_plan_dispatches=len(all_dispatches),
        budget_or_delegation_commands=common['native_dispatches'],production_commands=len(production_dispatches),
        construction_commands=len(construction_dispatches),
        scouting_commands=len(scouting_dispatches),
        regional_commands=len(regional_dispatches),
        some_model_regional_feedback_loop_verified=bool(regional) and regional_verified,
        some_model_construction_effect_verified=bool(construction) and construction_verified
            and construction['some_model_construction_effect_verified'] is True,
        some_model_scouting_feedback_loop_verified=bool(scouting) and scouting_verified,
        some_model_production_queue_effect_verified=bool(work) and any(r['model_plan_bound'] and r['native_ack_matches']
            and r['final_observations']['observed_new_queue_count']>0 for r in work['production_results']),
        native_matches=matches,host_native_start_frame=final['native']['start_frame'],first_watched_live_frame=first_live,
        first_native_result_frame=first,native_cleanup_frame=final['native']['last_frame'],last_watched_live_frame=last_live,
        natural_result_release_subset_verified=all(checks.values()),
        bounded_natural_session_checks=bounded_checks,
        bounded_natural_result_and_release_verified=all(bounded_checks.values()),
        budget_adopted_intents=sum(r['native_adoption_verified'] for r in budgets),
        budget_unadopted_intents=sum(not r['native_adoption_verified'] for r in budgets),
        budget_lifecycle_join_source_sha256=sha(Path(__file__).with_name('assess_macro_budget_lifecycles.py')),
        model_technology_budget_selected=any('budgettech' in r['actions'] for r in all_dispatches),
        host_started_mid_match=first_live is None or final['native']['start_frame']>first_live+450,
        full_G5_verified=False,full_G6_verified=False,full_G7_verified=False,
        replay_fidelity_verified=False,winner_mapping_verified=False,formal_goal_complete=False,
        evidence={str(p):sha(p) for p in evidence_paths})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','download','original-export','watch','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run-id',required=True)
    for name in ('production','scouting','regional','construction'):p.add_argument('--'+name+'-assessment',type=Path)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_natural_release_assessment_required')
    value=evaluate(a.run_directory.resolve(),a.run_id,a.download.resolve(),a.original_export.resolve(),a.watch.resolve(),
        a.production_assessment.resolve() if a.production_assessment else None,
        a.scouting_assessment.resolve() if a.scouting_assessment else None,
        a.regional_assessment.resolve() if a.regional_assessment else None,
        a.construction_assessment.resolve() if a.construction_assessment else None)
    out.mkdir(parents=True);shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    shutil.copy2(Path(__file__).with_name('assess_macro_budget_lifecycles.py'),out/'budget-lifecycle-helper.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('native_matches','evidence')}))


if __name__=='__main__':main()
