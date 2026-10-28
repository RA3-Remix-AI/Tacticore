"""Independently check paired frozen-context provider/style receipts; no network."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'integration'))
from host_runtime.profiles import normalize_profile

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def records(p):return [json.loads(l) for l in p.read_text().splitlines()]

def evaluate(directory):
    pre=load(directory/'preflight.json');context=load(directory/'public-context.json');drafts=load(directory/'public-drafts.json')
    events=records(directory/'provider-events.jsonl');outcomes=records(directory/'outcomes.jsonl')
    if (pre['context_sha256']!=sha(directory/'public-context.json') or pre['drafts_sha256']!=sha(directory/'public-drafts.json')
        or any(sha(directory/'source'/r['copy'])!=r['sha256'] for r in pre['sources'])):raise ValueError('shadow_frozen_sources_changed')
    styles=pre.get('styles',['original','scouting'])
    if type(styles) is not list or len(styles)!=2 or styles[0]!='original' or len(set(styles))!=2 or set(styles)!=set(drafts):
        raise ValueError('shadow_two_recorded_styles_required')
    keys={(pair,style) for pair in range(1,pre['pairs']+1) for style in styles}
    if len(outcomes)!=len(keys) or {(r['pair'],r['style']) for r in outcomes}!=keys:raise ValueError('shadow_paired_outcomes')
    responses=[];request_hashes={style:set() for style in drafts};choices={style:set() for style in drafts}
    for outcome in outcomes:
        pair,style=outcome['pair'],outcome['style']
        selected=[r for r in events if r['pair']==pair and r['style']==style]
        starts=[r for r in selected if r['kind']=='commander_model_call_started']
        returned=[r for r in selected if r['kind']=='commander_model_response_returned']
        if len(starts)!=1 or len(returned)!=1:raise ValueError('one_actual_response_per_style_pair')
        response=returned[0];receipt=response['transport_receipt'];resolved=dict(drafts[style]);resolved['model']=response['model']
        effective=normalize_profile(resolved)
        if (response['effective_hash']!=effective.effective_hash or outcome['effective_hash']!=effective.effective_hash
            or response['traits_sha256']!=hashlib.sha256(effective.traits.encode()).hexdigest()
            or response['snapshot_id']!=context['snapshot_id'] or starts[0]['snapshot_id']!=context['snapshot_id']
            or outcome['same_context_sha256']!=pre['context_sha256'] or outcome['native_dispatches']!=0
            or not all(receipt.get(k)==v for k,v in dict(real_network_verified=True,injected_transport=False,
                expected_origin=True,https=True,loopback=False,http_status=200,response_complete=True).items())):
            raise ValueError('shadow_provider_profile_binding')
        request_hashes[style].add(receipt['request_sha256'])
        if outcome['valid_policy']:
            if outcome.get('transport_receipt')!=receipt:raise ValueError('shadow_valid_policy_receipt')
            choices[style].add(json.dumps([outcome['macro_actions'],outcome['macro_production']],sort_keys=True))
        responses.append(dict(pair=pair,style=style,profile_revision=effective.revision,real_provider_response=True,
            valid_policy=outcome['valid_policy'],reason_code=outcome.get('reason_code')))
    differences=sum(a['macro_actions']!=b['macro_actions'] or a['macro_production']!=b['macro_production']
        for a,b in zip(outcomes[::2],outcomes[1::2]) if a['valid_policy'] and b['valid_policy'])
    return dict(kind='independent_macro_style_shadow_assessment',pairs=pre['pairs'],real_provider_returns=len(responses),
        valid_policies=sum(r['valid_policy'] for r in responses),responses=responses,
        same_wire_request_within_each_style=all(len(v)==1 for v in request_hashes.values()),
        actual_style_profile_consumed=True,same_public_observation=True,valid_decision_difference_pairs=differences,
        within_style_decision_variation={k:len(v)>1 for k,v in choices.items()},
        causal_style_effect_verified=False,model_nondeterminism_controlled=False,live_behavior_difference_verified=False,
        native_dispatches=0,live_game_access=False,win_rate_effect_verified=False,formal_goal_complete=False,
        evidence={str((directory/n).resolve()):sha(directory/n) for n in ('preflight.json','public-context.json',
            'public-drafts.json','provider-events.jsonl','outcomes.jsonl')})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_shadow_assessment_required')
    value=evaluate(a.study.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))

if __name__=='__main__':main()
