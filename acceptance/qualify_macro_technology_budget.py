"""Read-only qualification of native technology-budget research evidence."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration')]
from host_runtime.macro_policy_runtime import verify_budget_scope,trial,sha,PRESETS,ratios_match
from host_runtime.macro_technology_budget_scope import extend_technology_budget_scope


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('field','build','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_qualification_report_required')
    original=verify_budget_scope(ROOT/'reports/macro-policy-budget-73924-20261028-v3',
        ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',ROOT/'reports/macro-policy-expiry-71320-20261028-v1',args.build)
    scope=extend_technology_budget_scope(original,args.field)
    pre,final,manifest,rows,evidence=trial(args.field/'transport')
    flag=scope.action_flags['budgettech'];samples=[r['observation'] for r in rows
        if r['kind']=='macro_observation' and r.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag')==flag
        and ratios_match(r['observation']['budget_feedback'].get('account_shares'),PRESETS['budgettech'])]
    result=dict(kind='fixed_native_technology_budget_qualification',field=str(args.field.resolve()),
        session_id=final['session_id'],pid=final['pid'],model_calls=0,native_account_adoption_verified=True,
        adopted_samples=len(samples),first_adopted_frame=samples[0]['frame'],last_adopted_frame=samples[-1]['frame'],
        native_account_shares=PRESETS['budgettech'],normal_release_verified=True,
        actual_payment_verified=False,technology_upgrade_verified=False,model_choice_verified=False,
        formal_goal_complete=False,scope=scope.public(),evidence=scope.evidence)
    out.mkdir(parents=True);sources=out/'source';sources.mkdir()
    result['qualification_sources']=[]
    for index,path in enumerate([Path(__file__),ROOT/'integration/host_runtime/macro_policy_runtime.py',
            ROOT/'integration/host_runtime/macro_technology_budget_scope.py']):
        target=sources/(str(index)+'-'+path.name);shutil.copy2(path,target)
        result['qualification_sources'].append(dict(path=str(path.resolve()),copy=target.name,sha256=sha(target)))
    (out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:result[key] for key in ('pid','adopted_samples','first_adopted_frame','last_adopted_frame','native_account_adoption_verified','model_choice_verified','formal_goal_complete')}))


if __name__=='__main__':main()
