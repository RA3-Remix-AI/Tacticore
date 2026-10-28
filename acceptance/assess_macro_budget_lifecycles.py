"""Separate budget adoption from bounded intents that native AI did not adopt.

The strict every-budget-effect assessment remains unchanged. A rejected or
unadopted attempt is never relabelled as an effect in this lifecycle report.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import assess,records,load,sha,feedback_verified
from integration.host_runtime.macro_policy_runtime import trial,PRESETS,ratios_match

DISPATCHES={'model_macro_native_acknowledged','model_macro_production_acknowledged',
    'model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged'}

def join(events,rows,manifest,final):
    dispatches=[r for r in events if r['kind'] in DISPATCHES]
    plans={r['plan_id']:r['plan'] for r in events if r['kind']=='plan_applied'}
    response_ids={r['snapshot_id'] for r in events if r['kind']=='commander_model_response_returned'}
    requests=[r for r in events if r['kind']=='model_macro_request_context']
    acks={r['command_id']:r for r in rows if r['kind']=='command_acknowledged'}
    observations=[r['observation'] for r in rows if r['kind']=='macro_observation' and 'observation' in r]
    flags={r['action']:r['flag'] for r in manifest['consumers']};results=[];all_bound=bool(dispatches)
    for d in dispatches:
        ack=acks.get(d['command_id'],{});native=ack.get('native',{});plan=plans.get(d['plan_id'],{})
        mask=sum(1<<manifest['flags'].index(flags[a]) for a in d['actions'])
        bound=(ack.get('seq')==d['seq'] and native.get('applied_mask')==mask
            and plan.get('origin')=='model' and plan.get('macro_actions')==d['actions']
            and plan.get('session_id')==final['session_id'] and plan.get('player_id')==3
            and plan.get('snapshot_id') in response_ids)
        all_bound=all_bound and bound
        budgets=[a for a in d['actions'] if a in PRESETS]
        if len(budgets)>1:raise ValueError('recorded_multiple_budget_presets')
        if not budgets:continue
        action=budgets[0];begin=native.get('last_frame',0);deadline=native.get('deadline_frame',0)
        replacement=min((r['native']['last_frame'] for r in acks.values() if r['seq']>d['seq']),default=final['native']['last_frame'])
        end=min(deadline,replacement,final['native']['last_frame'])
        adopted=[o for o in observations if begin<=o['frame']<=end
            and o['budget_feedback']['selected_macro_flag']==flags[action]
            and ratios_match(o['budget_feedback']['account_shares'],PRESETS[action])]
        later=[]
        for r in requests:
            context=r['context'];feedback=context.get('macro_execution_feedback') or {};frame=feedback.get('observed_frame')
            if (context['snapshot_id'] in response_ids and type(frame) is int and begin<frame<=end
                    and feedback.get('status')=='native_budget_adopted' and feedback.get('actions')==[action]
                    and feedback_verified(context,observations,{a:f for a,f in flags.items() if a in PRESETS})):
                later.append(r['sequence'])
        results.append(dict(plan_id=d['plan_id'],action=action,native_seq=d['seq'],begin_frame=begin,
            replacement_expiry_or_stop_frame=end,native_deadline_frame=deadline,model_and_ack_bound=bound,
            bounded_activation=0<deadline-begin<=900 and begin<=end,
            matching_native_adoption_samples=len(adopted),native_adoption_verified=bound and len(adopted)>=2,
            later_returned_request_sequences=later,feedback_to_later_genuine_response_verified=bool(later)))
    return results,bool(all_bound)

def evaluate(run,run_id,download,original):
    common=assess(run,run_id,download,original);host=run/'battle-host'
    _,final,manifest,rows,_=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    events=records(host/'host-events.jsonl');results,all_bound=join(events,rows,manifest,final)
    shared_keys=('exact_pre_execution_sources_retained','current_profile_consumed','exact_public_request_context_retained',
        'real_provider_response','macro_unit_jobs_absent','native_cleanup_verified','multiple_real_model_rounds',
        'native_feedback_in_each_followup_request','downloaded_export_matches')
    checks={k:common['checks'][k] for k in shared_keys}
    checks['all_native_model_acknowledgements_bound']=all_bound
    stop=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    quiet=stop is not None and not any(r['kind']=='commander_model_call_started' or r['kind'] in DISPATCHES
        or r['kind'].endswith('_prepared') for r in events[stop+1:])
    bounded=bool(results) and all(r['model_and_ack_bound'] and r['bounded_activation'] for r in results)
    positive=[r for r in results if r['native_adoption_verified']]
    return dict(kind='macro_budget_intent_lifecycle_assessment',run_id=run_id,session_id=final['session_id'],checks=checks,
        host_state=common['host_state'],host_reason=common['host_reason'],real_model_responses=common['real_model_responses'],
        budget_intents=len(results),budget_results=results,adopted_budget_intents=len(positive),
        unadopted_budget_intents=len(results)-len(positive),all_budget_intents_adopted=bool(results) and len(positive)==len(results),
        some_model_budget_adoption_verified=all(checks.values()) and bool(positive),bounded_budget_lifecycles_verified=bounded,
        no_new_requests_or_commands_after_stop_verified=quiet,
        bounded_budget_feedback_loop_verified=all(checks.values()) and bounded and quiet
            and any(r['feedback_to_later_genuine_response_verified'] for r in positive),
        model_technology_adoption_verified=all(checks.values()) and any(r['action']=='budgettech' for r in positive),
        payment_verified=False,exclusive_win_attribution_verified=False,full_G6_verified=False,full_G7_verified=False,
        formal_goal_complete=False,evidence=common['evidence'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','download','original-export','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run-id',required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_budget_lifecycle_report_required')
    value=evaluate(a.run_directory.resolve(),a.run_id,a.download.resolve(),a.original_export.resolve())
    out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('budget_results','evidence')}))

if __name__=='__main__':main()
