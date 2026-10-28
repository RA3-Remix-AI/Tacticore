"""G7: genuine macro feedback from opening to an archived natural result.

This checks the user's complete-match criterion. It does not require every
intent to succeed, a win, or native replay fidelity; it does not grant G6/G8.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'acceptance')]
from assess_macro_desktop import load,records,sha


def bound_report(path):
    value=load(path)
    if sha(path.parent/'assessor.py')!=value['assessor_sha256']:raise ValueError('complete_match_assessor_changed')
    evidence=value.get('evidence',{})
    if not evidence or any(sha(Path(p))!=digest for p,digest in evidence.items()):raise ValueError('complete_match_evidence_changed')
    return value


def evaluate(run,natural_path,outcome_path,timeline,delivery):
    session=load(run/'session.json');host=run/'battle-host';status=load(host/'host-status.json')
    natural=bound_report(natural_path);outcome=bound_report(outcome_path)
    if any(v['session_id']!=session['session_id'] for v in (status,natural,outcome)):
        raise ValueError('complete_match_session_mismatch')
    events=records(host/'host-events.jsonl');requests=[r for r in events if r['kind']=='model_macro_request_context']
    plans=[];memory_rounds=0
    for event in events:
        if event['kind']=='plan_applied':plans.append(event['plan'])
        if event['kind']=='model_macro_request_context':
            c=event['context'];strategy=c['working_memory'].get('current_strategy')
            if strategy and strategy.get('origin')=='model' and any(
                    p['macro_actions']==strategy.get('macro_actions') and p['budget']==strategy.get('budget')
                    and p['stance']==strategy.get('stance') and p['snapshot_id']<c['snapshot_id'] for p in plans):
                memory_rounds+=1
    executed=load(run/'executed-client.json')
    retained_frontend=all(sha(run/'executed-client-dist'/r['path'])==r['sha256'] for r in executed['frontend'])
    frozen_host=sha(run/'executed-macro_host.py')==executed['macro_host_sha256']
    review=load(timeline/'browser-review.json');data=load(timeline/'macro-timeline.json')
    timeline_integrity=all(sha(timeline/name)==digest for name,digest in review['files'].items())
    terminal=[r for r in data['events'] if r['type']=='outcome']
    manifest=load(delivery/'manifest.json')
    delivery_integrity=all((delivery/name).parent==delivery and sha(delivery/name)==value['sha256']
        and (delivery/name).stat().st_size==value['bytes'] for name,value in manifest['files'].items())
    checks=dict(
        bounded_natural_session_verified=natural['bounded_natural_result_and_release_verified'] is True,
        started_from_opening=natural['host_started_mid_match'] is False,
        genuine_continued_rounds=natural['real_model_responses']>=3 and natural['native_macro_plan_dispatches']>=2,
        current_client_start_observed=executed.get('opening_wait_armed_via_actual_ui') is True
            and executed.get('client_pid',0)>0 and retained_frontend and frozen_host,
        current_profile_revision_consumed=all(r['context']['commander_id']==session.get('commander_id',r['commander_id'])
            for r in requests) and executed['profile_revision']==load(host/'profile.json')['revision'],
        prior_model_strategy_reaches_later_round=memory_rounds>=2,
        native_effect_and_later_real_feedback=natural['bounded_natural_session_checks']['some_observed_effect_returns_to_real_model'] is True,
        native_opponent_and_natural_outcome=outcome['native_winner_mapping_verified'] is True
            and {outcome['winner_player_index'],outcome['loser_player_index']}=={3,4},
        no_host_fault=not any(r['kind']=='host_fault' for r in events),
        stopped_without_new_commands=natural['checks']['no_new_requests_or_commands_after_stop'] is True,
        independent_native_release=natural['checks']['later_original_native_readback_clear'] is True,
        playable_timeline_and_result=timeline_integrity and review['play_to_end_verified'] is True
            and review['natural_outcome_visible'] is True and data['session_id']==session['session_id']
            and len(terminal)==1 and terminal[0]['model_side_outcome']==outcome['model_side_outcome'],
        screenshots_logs_config_and_replay_delivered=delivery_integrity
            and manifest['session_id']==session['session_id'] and all(n in manifest['files'] for n in
                ('settlement.png','diagnostics.json','commander-config.json','natural.RA3Replay','macro-timeline.html'))
            and sha(delivery/'macro-timeline.html')==sha(timeline/'macro-timeline.html'),
        replay_limits_disclosed=manifest['native_replay_fidelity_verified'] is False
            and data['game_replay_fidelity_verified'] is False)
    paths=[run/'session.json',run/'executed-client.json',natural_path,outcome_path,timeline/'browser-review.json',
        timeline/'macro-timeline.json',timeline/'macro-timeline.html',delivery/'manifest.json',host/'host-events.jsonl']
    return dict(kind='user_macro_G7_complete_match_assessment',session_id=session['session_id'],pid=session['pid'],
        checks=checks,full_G7_verified=all(checks.values()),real_model_responses=natural['real_model_responses'],
        native_macro_plan_dispatches=natural['native_macro_plan_dispatches'],prior_strategy_memory_rounds=memory_rounds,
        model_side_outcome=outcome['model_side_outcome'],all_intents_succeeded=False,
        native_replay_fidelity_verified=False,win_rate_improvement_verified=False,
        full_G6_verified=False,full_G8_verified=False,formal_goal_complete=False,
        evidence={str(p.resolve()):sha(p) for p in paths})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','natural-assessment','outcome-assessment','timeline','delivery','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_complete_match_report_required')
    result=evaluate(a.run_directory.resolve(),a.natural_assessment.resolve(),a.outcome_assessment.resolve(),a.timeline.resolve(),a.delivery.resolve())
    out.mkdir();shutil.copy2(__file__,out/'assessor.py');result['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='evidence'}))


if __name__=='__main__':main()
