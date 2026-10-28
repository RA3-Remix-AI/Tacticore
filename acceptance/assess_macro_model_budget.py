"""Independently join frozen public configuration, provider, plan and native evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from integration.host_runtime.macro_policy_runtime import trial,ratios_match,PRESETS,COMMANDER
from integration.host_runtime.profiles import normalize_profile

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return [json.loads(line) for line in Path(p).read_text(encoding='utf-8').splitlines()]

def feedback_memory(context):
    memory=context.get('working_memory',{});strategy=memory.get('current_strategy') or {}
    return strategy.get('origin')=='model' and any(f.get('status')=='native_budget_adopted'
        and f.get('native_effect_verified') is True and f.get('actions')==strategy.get('macro_actions')
        and f.get('actions') for f in memory.get('recent_execution_feedback',[]))

def context_call_order(events,context,start,response):
    # Windows monotonic clock resolution may give adjacent events equal ticks.
    # Journal order must still be strict, while clock readings cannot regress.
    return (events.index(context)<events.index(start)<events.index(response)
        and context['monotonic_ns']<=start['monotonic_ns']<=response['monotonic_ns'])


def assess(directory):
    directory=Path(directory).resolve();summary=load(directory/'summary.json')
    profile=load(directory/'profile.json');application=load(directory/'application.json')
    registration=load(directory/'registration.json');scope=load(directory/'scope.json')
    sources=load(directory/'sources.json');events=rows(directory/'model-macro-events.jsonl')
    _,final,manifest,native,_=trial(directory/'transport')
    draft=dict(profile['draft'],model=profile['model']);effective=normalize_profile(draft)
    contexts=[r for r in events if r['kind']=='model_macro_request_context']
    starts=[r for r in events if r['kind']=='commander_model_call_started']
    responses=[r for r in events if r['kind']=='commander_model_response_returned']
    decisions=[r for r in events if r['kind']=='model_macro_decision']
    dispatches=[r for r in events if r['kind']=='model_macro_native_acknowledged']
    accepted=[r for r in decisions if r['status']=='accepted']
    acknowledgements={r['command_id']:r for r in native if r['kind']=='command_acknowledged'}
    flags={r['action']:r['flag'] for r in manifest['consumers']}
    observed=[r for r in events if r['kind']=='model_macro_native_feedback']
    checks={}
    checks['frozen_sources_intact']=all((directory/'source'/r['copy']).resolve().parent==(directory/'source').resolve()
        and sha(directory/'source'/r['copy'])==r['sha256'] for r in sources)
    checks['current_profile_and_revision_bound']=(profile['revision']==4 and effective.effective_hash==profile['effective']['effective_hash']
        ==application['effective_hash']==summary['effective_hash']==registration['effective_hash']
        and profile['library_hash']==registration['library_sha256']
        and application['profile_id']==COMMANDER and application['profile_revision']==4
        and application['traits_sha256']==hashlib.sha256(effective.traits.encode('utf-8')).hexdigest())
    checks['two_budget_presets_only']=set(scope['available_actions'])==set(PRESETS) and scope['package_sha256']==final['mod_sha256']
    checks['actual_provider_responses']=(len(responses)>=2 and len(responses)==summary['real_model_responses']
        and all(r.get('real_network_verified') is True and r.get('transport_mode')=='provider_transport'
            and r.get('transport_receipt',{}).get('real_network_verified') is True
            and r['transport_receipt'].get('injected_transport') is False and r['transport_receipt'].get('https') is True
            and r['transport_receipt'].get('loopback') is False and r['transport_receipt'].get('expected_origin') is True
            and r['transport_receipt'].get('http_status')==200 and r['transport_receipt'].get('response_complete') is True
            and r['profile_revision']==4 and r['effective_hash']==effective.effective_hash for r in responses))
    checks['exact_context_before_each_request']=(len(contexts)==len(starts)==len(responses)
        and all(context_call_order(events,c,s,r)
            and c['sequence']==s['call_sequence']==r['call_sequence']
            and c['context']['snapshot_id']==s['snapshot_id']==r['snapshot_id']
            and c['context_sha256']==hashlib.sha256(json.dumps(c['context'],ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
            for c,s,r in zip(contexts,starts,responses)))
    checks['macro_mode_without_legacy_unit_jobs']=bool(contexts) and all(c['context']['control_mode']=='macro_native'
        and set(c['context']['allowed_macro_actions'])==set(PRESETS)
        and c['context']['working_memory']['battlefield']['formations']==[]
        and c['context']['working_memory']['active_goals']==[] for c in contexts)
    chains=[]
    for dispatch in dispatches:
        decision=next((r for r in accepted if r['plan']['plan_id']==dispatch['plan_id']),None)
        ack=acknowledgements.get(dispatch['command_id'])
        actions=dispatch['actions'];one=actions[0] if len(actions)==1 else None
        native_effect=[r for r in native if r.get('kind')=='macro_observation' and decision
            and r.get('label')=='model_round_'+str(decision['round']) and one in PRESETS
            and r.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag')==flags[one]
            and ratios_match(r['observation']['budget_feedback']['account_shares'],PRESETS[one])]
        plan=decision['plan'] if decision else {}
        binding=(plan.get('origin')=='model' and plan.get('session_id')==summary['session_id']
            and plan.get('commander_id')==COMMANDER and plan.get('player_id')==3
            and plan.get('macro_actions')==actions and plan.get('tactical_tasks')==[]
            and plan.get('runtime_task') is None and bool(ack) and ack['seq']==dispatch['seq']
            and dispatch['command_id']==str(uuid.uuid5(uuid.UUID(summary['session_id']),dispatch['plan_id']+':'+effective.effective_hash)))
        if ack:
            mask=sum(1<<manifest['flags'].index(flags[action]) for action in actions)
            binding=binding and ack['native']['applied_mask']==mask
        chains.append(dict(plan_id=dispatch['plan_id'],actions=actions,binding_verified=bool(binding),
            native_effect_samples=len(native_effect),first_effect_frame=native_effect[0]['observation']['frame'] if native_effect else None))
    checks['accepted_plans_only_dispatch']=len(dispatches)==len(accepted) and len(accepted)>=2 and all(r['binding_verified'] for r in chains)
    checks['native_budget_adopted']=sum(bool(r['native_effect_samples']) for r in chains)>=2
    feedback_contexts=[c for c in contexts if feedback_memory(c['context'])]
    checks['native_feedback_reaches_later_model_request']=bool(feedback_contexts)
    stops=[i for i,r in enumerate(events) if r['kind']=='macro_model_trial_stop_requested']
    checks['stop_has_no_later_model_calls']=len(stops)==1 and not any(r['kind']=='commander_model_call_started' for r in events[stops[0]+1:])
    checks['native_stop_and_helper_exit']=final['cleanup_verified'] is True and summary['cleanup_verified'] is True
    post=directory/'post-stop-native-budget.json'
    checks['native_policy_released_after_stop']=post.exists() and load(post)['budget_feedback']['selected_macro_flag'] is None
    return dict(kind='independent_real_model_macro_budget_assessment',session_id=summary['session_id'],
        profile_revision=profile['revision'],effective_hash=effective.effective_hash,checks=checks,
        budget_loop_verified=all(checks.values()),real_responses=len(responses),accepted=len(accepted),
        rejected_decisions=[dict(round=r['round'],reason_code=r['reason_code']) for r in decisions if r['status']!='accepted'],
        chains=chains,contexts_with_native_feedback=len(feedback_contexts),
        evidence={str(p):sha(p) for p in [directory/'summary.json',directory/'model-macro-events.jsonl',
            directory/'sources.json',directory/'transport/preflight.json',directory/'transport/final-state.json',
            directory/'transport/policy-probe.jsonl',Path(__file__)]},
        product_client_integration_verified=False,construction_or_production_verified=False,
        style_comparison_verified=False,formal_full_match_verified=False,formal_goal_complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=assess(args.directory)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(output=str(args.output),checks=result['checks'],budget_loop_verified=result['budget_loop_verified'])))
