"""Independently join desktop profile, provider, native policy and export evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from integration.host_runtime.macro_policy_runtime import trial,PRESETS,ratios_match


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def records(path):return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]


def feedback_verified(context,observations,actions):
    value=context.get('macro_execution_feedback') or {};frame=value.get('observed_frame')
    if (value.get('source')!='native_macro_budget_observation' or type(frame) is not int
            or not -15<=context.get('game_time_seconds',-10)*15-frame<=30):return False
    for observation in observations:
        if observation['frame']!=frame:continue
        bank=observation['budget_feedback']
        selected=next((action for action,flag in actions.items() if flag==bank['selected_macro_flag']),None)
        if selected!=value.get('selected_policy'):continue
        if value.get('status')=='native_budget_adopted':
            if (value.get('actions')==[selected] and selected in PRESETS and value.get('native_effect_verified') is True
                    and ratios_match(bank['account_shares'],PRESETS[selected])):return True
        elif value.get('status') in ('native_budget_pending','native_delegation_observed','native_budget_clearing'):
            if value.get('native_effect_verified') is False:return True
    return False


def assess(run_directory,run_id,download,original_export):
    output=run_directory/'battle-host';native=ROOT/'reports'/('macro-desktop-'+run_id)
    pre,final,manifest,native_rows,native_evidence=trial(native)
    status=load(output/'host-status.json');profile=load(output/'profile.json');rows=records(output/'host-events.jsonl')
    frozen=load(output/'sources.json')['sources']
    source_valid=all((output/'source'/row['copy']).resolve().parent==(output/'source').resolve()
        and sha(output/'source'/row['copy'])==row['sha256'] for row in frozen)
    requests=[row for row in rows if row['kind']=='model_macro_request_context']
    responses=[row for row in rows if row['kind']=='commander_model_response_returned']
    dispatches=[row for row in rows if row['kind']=='model_macro_native_acknowledged']
    actions={row['action']:row['flag'] for row in manifest['consumers'] if row['action'] in PRESETS}
    raw_acks={row['command_id']:row for row in native_rows if row['kind']=='command_acknowledged'}
    feedback=[row['observation'] for row in native_rows if row['kind']=='macro_observation' and 'observation' in row]
    matches=[]
    plans={row['plan_id']:row['plan'] for row in rows if row['kind']=='plan_applied'}
    for index,dispatch in enumerate(dispatches):
        selected=dispatch['actions'];ack=raw_acks.get(dispatch['command_id'],{})
        expected_mask=sum(1<<manifest['flags'].index(actions[action]) for action in selected if action in actions)
        plan=plans.get(dispatch['plan_id'],{})
        plan_bound=(plan.get('origin')=='model' and plan.get('macro_actions')==selected
            and plan.get('session_id')==final['session_id'] and plan.get('player_id')==3
            and any(request['context'].get('snapshot_id')==plan.get('snapshot_id')
                    and request['context'].get('session_id')==final['session_id'] for request in requests))
        next_frame=raw_acks.get(dispatches[index+1]['command_id'],{}).get('native',{}).get('last_frame',0xffffffff) if index+1<len(dispatches) else 0xffffffff
        adopted=[sample for sample in feedback if len(selected)==1 and selected[0] in PRESETS
            and ack.get('native',{}).get('last_frame',0)<=sample['frame']<next_frame
            and sample['frame']<=ack.get('native',{}).get('deadline_frame',0)
            and sample['budget_feedback']['selected_macro_flag']==actions[selected[0]]
            and ratios_match(sample['budget_feedback']['account_shares'],PRESETS[selected[0]])]
        matches.append(dict(plan_id=dispatch['plan_id'],actions=selected,native_seq=dispatch['seq'],
            native_ack_matches=ack.get('seq')==dispatch['seq'] and ack.get('native',{}).get('applied_mask')==expected_mask,
            model_plan_bound=plan_bound,matching_native_samples=len(adopted)))
    binding=load(output/'macro-release.json')['binding'];export=load(download)
    stop_indices=[index for index,row in enumerate(rows) if row['kind']=='macro_host_stop_started']
    stopped_without_later_command=bool(stop_indices) and not any(row['kind'] in (
        'commander_model_call_started','model_macro_dispatch_prepared','model_macro_native_acknowledged')
        for row in rows[stop_indices[-1]+1:])
    checks=dict(
        exact_pre_execution_sources_retained=source_valid,
        current_profile_consumed=bool(responses) and all(row.get('profile_revision')==profile['revision']
            and row.get('effective_hash')==profile['effective']['effective_hash'] for row in responses)
            and status['profile_application']['effective_hash']==profile['effective']['effective_hash'],
        exact_public_request_context_retained=bool(requests) and all(
            hashlib.sha256(json.dumps(row['context'],ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')).hexdigest()==row['context_sha256']
            and row['context'].get('control_mode')=='macro_native' for row in requests),
        real_provider_response=bool(responses) and all(
            all((row.get('transport_receipt') or {}).get(key)==value for key,value in dict(
                real_network_verified=True,injected_transport=False,expected_origin=True,https=True,loopback=False,
                http_status=200,response_complete=True).items()) for row in responses),
        native_ack_and_budget_effect=bool(matches) and all(row['model_plan_bound'] and row['native_ack_matches'] and row['matching_native_samples']>=2 for row in matches),
        macro_unit_jobs_absent=status['jobs']==[] and all(not (row['context'].get('working_memory') or {}).get('active_goals') for row in requests),
        native_cleanup_verified=final['cleanup_verified'] and final['unknown_command_ids']==[],
        user_stop_completed=status['state']=='stopped' and status['reason_code']=='user_stop' and stopped_without_later_command,
        multiple_real_model_rounds=len(responses)>=2,
        native_feedback_in_each_followup_request=len(requests)>=2 and all(
            feedback_verified(request['context'],feedback,actions) for request in requests),
        downloaded_export_matches=sha(download)==sha(original_export) and export.get('run_id')==run_id
            and export.get('binding')==binding and export.get('redacted') is True
            and all(value is False for value in export.get('redaction',{}).values() if type(value) is bool))
    return dict(kind='desktop_macro_budget_evidence_assessment',run_id=run_id,session_id=final['session_id'],
        profile_revision=profile['revision'],effective_hash=profile['effective']['effective_hash'],checks=checks,
        real_model_responses=len(responses),native_dispatches=len(dispatches),native_matches=matches,
        request_feedback=[dict(sequence=row['sequence'],native_sample_matches=feedback_verified(row['context'],feedback,actions),
            historical_feedback_count=len(row['context']['working_memory'].get('recent_execution_feedback',[]))) for row in requests],
        host_state=status['state'],host_reason=status['reason_code'],
        desktop_budget_subset_verified=all(checks.values()),full_G5_verified=False,full_G7_verified=False,formal_goal_complete=False,
        evidence={**native_evidence,**{str(path):sha(path) for path in [output/'host-events.jsonl',output/'host-status.json',
            output/'sources.json',output/'profile.json',download,original_export]}})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','download','original-export','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--run-id',required=True);args=parser.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_desktop_macro_assessment')
    result=assess(args.run_directory.resolve(),args.run_id,args.download.resolve(),args.original_export.resolve())
    out.mkdir();shutil.copy2(Path(__file__),out/'assessor.py');shutil.copy2(args.download,out/'downloaded-diagnostics.json')
    result['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({key:value for key,value in result.items() if key!='evidence'}))


if __name__=='__main__':main()
