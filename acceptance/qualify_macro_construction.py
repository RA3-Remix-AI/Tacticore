"""Read-only qualification/replay of existing native construction evidence."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration')]
from host_runtime.macro_policy_runtime import verify_budget_scope,trial,sha
from host_runtime.macro_production_runtime import verify_production_preference_scope
from host_runtime.macro_construction_scope import extend_construction_scope
from host_runtime.macro_construction_feedback import ConstructionFeedback


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_qualification_directory_required')
    budget=verify_budget_scope(ROOT/'reports/macro-policy-budget-73924-20261028-v3',
        ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',ROOT/'reports/macro-policy-expiry-71320-20261028-v1',
        ROOT/'native-ai/macro-policy-runtime/bin/policy-v22-desktop-choices-20261028')
    production=verify_production_preference_scope(budget,ROOT/'reports/macro-production-count-69152-20261028-v1',
        ROOT/'reports/macro-builder-static-20261028-v2')
    field=ROOT/'reports/macro-early-build-69152-20261028-v1'
    scope=extend_construction_scope(production,field)
    pre,final,manifest,rows,evidence=trial(field/'transport')
    out.mkdir(parents=True);(out/'source').mkdir();sources=[]
    paths=[Path(__file__),ROOT/'integration/host_runtime/macro_construction_feedback.py',
        ROOT/'integration/host_runtime/macro_construction_scope.py',ROOT/'integration/host_runtime/macro_production_runtime.py',
        ROOT/'integration/host_runtime/macro_bundle.py',ROOT/'integration/host_runtime/macro_production_feedback.py',
        ROOT/'integration/macro_host.py',ROOT/'strategy/macro_policy.py',ROOT/'strategy/http_adapter.py',
        ROOT/'desktop-ui/src/NativeApp.tsx']
    for index,path in enumerate(paths):
        copy=out/'source'/(str(index)+'-'+path.name);shutil.copy2(path,copy)
        sources.append(dict(path=str(path.resolve()),copy=copy.name,sha256=sha(copy)))
    census=None;tracker=None;observations=0;timeline={}
    with (out/'public-feedback.jsonl').open('x',encoding='utf8') as stream:
        for row in rows:
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']=='native_builder_observation' and 'observation' in row and census:
                builder=row['observation']
                if tracker is None:tracker=ConstructionFeedback(builder,census)
                tracker.observe(builder,census,scope.construction_flag);observations+=1
                for name,present in [('positive_state',tracker.positive),('new_queue',bool(tracker.new_queues)),('own_object',bool(tracker.new_objects))]:
                    if present and name not in timeline:timeline[name]=dict(builder_frame=builder['frame'],census_frame=census['frame'])
                stream.write(json.dumps(tracker.public())+'\n')
            if row['kind']=='command_acknowledged' and row['native']['applied_mask']==0 and tracker and not tracker.policy_released:
                tracker.mark_policy_released('queue_observed');timeline['original_policy_clear']=row['native']['last_frame']
    result=dict(kind='recorded_native_construction_qualification',session_id=final['session_id'],
        macro_package_sha256=scope.package_sha256,observations=observations,timeline=timeline,feedback=tracker.public(),
        scope=scope.public(),sources=sources,evidence=scope.evidence,model_calls=0,new_live_execution=False,
        real_model_construction_verified=False,current_desktop_construction_verified=False,formal_goal_complete=False,
        limitations=['Original field driver held the preference beyond first queue; new controller release timing needs a new live trial.',
            'Queue and own construction object observations are independent; no exact creation callback.',
            'Final payment and construction completion remain unverified.',
            'Original native AI baseline and model/style contribution comparison remain required.'])
    (out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(output=str(out),observations=observations,timeline=timeline,feedback=tracker.public(),
        model_calls=0,current_desktop_construction_verified=False,formal_goal_complete=False)))


if __name__=='__main__':main()
