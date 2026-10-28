"""Replay frozen native production observations through the macro feedback contract.

This reads an existing trial only. It is not a new live/model execution or grant.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from integration.host_runtime.macro_production_feedback import ProductionFeedback
from integration.host_runtime.contracts import ContractError


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(directory,event):
    directory=Path(directory)
    final=json.loads((directory/'final-state.json').read_text(encoding='utf-8-sig'))
    pre=json.loads((directory/'preflight.json').read_text(encoding='utf-8-sig'))
    for source in pre['sources']:
        copy=directory/'source'/source['copy']
        if copy.resolve().parent!=(directory/'source').resolve() or sha(copy)!=source['sha256']:
            raise ContractError('macro_production_frozen_source_changed')
    tracker=None;census=None;observations=0;discarded=0
    with (directory/'policy-probe.jsonl').open(encoding='utf8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['session_id']!=final['session_id'] or row['pid']!=final['pid']:
                raise ContractError('macro_production_replay_binding')
            if row['kind']=='macro_observation' and 'observation' in row:
                census=row['observation']['construction_feedback']
            elif row['kind']=='native_builder_observation' and 'observation' in row and census:
                try:
                    if tracker is None:tracker=ProductionFeedback('produceflak',2,row['observation'],census)
                    else:tracker.observe(row['observation'],census)
                except ContractError as error:
                    discarded+=1;event(dict(kind='sample_discarded',reason_code=error.code));continue
                observations+=1;event(dict(kind='public_macro_production_feedback',feedback=tracker.public()))
            elif row['kind']=='macro_count_policy_released' and tracker:
                tracker.mark_policy_released('queue_target_observed' if row['target_observed'] else 'expired')
    if tracker is None:raise ContractError('macro_production_replay_no_observations')
    return dict(kind='recorded_macro_production_feedback_replay',session_id=final['session_id'],
        observations=observations,discarded=discarded,feedback=tracker.public(),
        original_cleanup_verified=final['cleanup_verified'],model_calls=0,new_live_execution=False,
        product_capability_granted=False,formal_goal_complete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();directory=args.trial.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_feedback_replay_output')
    out.mkdir(parents=True);(out/'source').mkdir();sources=[]
    for index,path in enumerate([Path(__file__),ROOT/'integration/host_runtime/macro_production_feedback.py',
            ROOT/'strategy/macro_policy.py',ROOT/'strategy/engine.py',ROOT/'strategy/http_adapter.py']):
        copy=out/'source'/(str(index)+'-'+path.name);shutil.copy2(path,copy)
        sources.append(dict(path=str(path.resolve()),copy=copy.name,sha256=sha(copy)))
    evidence={str(directory/name):sha(directory/name) for name in ['preflight.json','final-state.json','policy-probe.jsonl']}
    with (out/'public-feedback.jsonl').open('x',encoding='utf8') as stream:
        result=replay(directory,lambda value:stream.write(json.dumps(value,ensure_ascii=False)+'\n'))
    result.update(sources=sources,evidence=evidence)
    (out/'assessment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({key:value for key,value in result.items() if key not in ('sources','evidence')}))


if __name__=='__main__':main()
