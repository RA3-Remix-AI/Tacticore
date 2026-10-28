"""Map a no-model fixed macro trial's natural result from native records."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_outcome import load,sha,map_terminal,verify_static
from integration.host_runtime.macro_policy_runtime import trial


def evaluate(run,watch,fixed):
    session=load(run/'session.json');people=load(run/'fixed-participants.json');archive=load(run/'research-settlement.json')
    pre=load(watch/'preflight.json');report=load(watch/'report.json');driver=load(fixed/'driver-preflight.json')
    _,final,_,commands,evidence=trial(fixed/'transport')
    if ((run/'battle-host').exists() or report['reason']!='native_lifecycle_frame_reset' or report['read_errors']!=0
            or people['model_calls']!=0 or people['native_commands_by_recorder']!=0 or people['process_writes']!=0
            or driver['model_calls']!=0 or driver['unit_orders']!=0
            or archive['real_model_responses']!=0 or archive['planning_mode']!='fixed_native_macro_policy'
            or archive['natural_settlement_verified'] is not True):raise ValueError('fixed_no_model_natural_scope_required')
    for value in (people,archive,driver,final):
        if any(value[k]!=session[k] for k in ('session_id','pid','process_creation_filetime')):
            raise ValueError('fixed_outcome_session_mismatch')
    if any(pre[k]!=session[k] for k in ('session_id','pid','process_creation_filetime','mod_sha256')):
        raise ValueError('fixed_outcome_watch_binding')
    for source in pre['sources']:
        if sha(watch/'source'/source['copy'])!=source['sha256']:raise ValueError('fixed_watch_source_changed')
    for source,digest in people['sources'].items():
        if sha(Path(source))!=digest:raise ValueError('fixed_participant_source_changed')
    for name in ('screenshot','replay'):
        if sha(run/archive[name])!=archive[name+'_sha256']:raise ValueError('fixed_natural_archive_changed')
    rows=[json.loads(s) for s in (watch/'native-match-transitions.jsonl').read_text().splitlines()]
    if rows[-1].get('simulation_frame')!=0:raise ValueError('fixed_native_frame_reset_required')
    last=[r for r in rows if r.get('simulation_frame')][-1]
    own=next(r for r in last['victory_conditions']['participants'] if r['player_index']==3)
    if int(own['player'],0)!=people['handshake']['player'] or int(last['game_logic'],0)!=people['handshake']['game_logic']:
        raise ValueError('fixed_native_owner_changed')
    result=map_terminal(last,people['participants']);controlled=result.pop('model_side_outcome')
    outcome_frame=min(v for r in last['result_records'] for v in (r['defeat_frame'],r['victory_frame']) if v)
    if not people['frame']<outcome_frame or not final['native']['last_frame']<outcome_frame:
        raise ValueError('fixed_participants_and_policy_must_precede_natural_result')
    pins=verify_static(Path(session['game']))
    paths=[run/'session.json',run/'fixed-participants.json',run/'research-settlement.json',watch/'preflight.json',
        watch/'report.json',watch/'native-match-transitions.jsonl',fixed/'driver-preflight.json']
    return dict(kind='fixed_macro_native_two_ai_natural_outcome',session_id=session['session_id'],pid=session['pid'],
        **result,controlled_side_outcome=controlled,native_winner_mapping_verified=True,last_live_frame=last['simulation_frame'],
        native_result_byte_checks=pins,model_calls=0,unit_orders=0,fixed_macro_intents=2,
        fixed_native_flag_commands_including_clears=len([r for r in commands if r['kind']=='command_acknowledged']),
        fixed_policy_released_before_natural_result=True,native_cleanup_verified=final['cleanup_verified'],
        model_win_contribution_verified=False,causal_policy_win_effect_verified=False,formal_goal_complete=False,
        evidence={**evidence,**{str(p.resolve()):sha(p) for p in paths}})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','watch','fixed-trial','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_fixed_outcome_required')
    value=evaluate(a.run_directory.resolve(),a.watch.resolve(),a.fixed_trial.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py')
    value['assessor_sha256']=sha(out/'assessor.py');(out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('evidence','native_result_byte_checks')}))


if __name__=='__main__':main()
