"""Match actual public facility facts to retained own census and native queues.

This independently recomputes the projection; it does not import its producer.
Foundations, paid accumulators and available builders never prove completion.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from integration.host_runtime.macro_policy_runtime import trial

TYPES=dict(construction_yard='0xc16ff13f',barracks='0x80d4ea1e',war_factory='0xd50c222e',
           refinery='0xc45aaeab',super_reactor='0x524bbd01',battle_lab='0xb7377639')
QUEUE_NAMES=('refinery','super_reactor','battle_lab')

def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def records(path):return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]

def independent_projection(builder,census):
    if (builder['source']!='native_macro_builder_read_only' or builder['process_writes']!=0
            or builder['native_calls']!=0 or census['enemy_details_read'] is not False
            or abs(builder['frame']-census['frame'])>15):raise ValueError('unqualified_own_sample')
    own={r['thing_id']:r for r in census['own_objects']}
    if len(own)!=len(census['own_objects']):raise ValueError('duplicate_own_object')
    counts=Counter()
    for r in own.values():
        if r['type_hash'] in TYPES.values():
            if not math.isfinite(r['hp']) or r['hp']<=0:raise ValueError('invalid_own_hp')
            counts[r['type_hash']]+=1
    eligible=set();queues={name:{} for name in QUEUE_NAMES}
    for r in builder['builders']:
        f=r['factory'];ident=f['thing_id']
        if (f['type_hash']!=TYPES['construction_yard'] or r.get('observation_available') is not True
                or not math.isfinite(f.get('hp',0)) or f.get('hp',0)<=0
                or own.get(ident,{}).get('type_hash')!=TYPES['construction_yard']):continue
        eligible.add(ident)
        for node in r['queue_candidate']['nodes']:
            if node['kind_raw']!=1:continue
            for name in QUEUE_NAMES:
                if node['template_hash']!=TYPES[name]:continue
                key=(ident,node['production_id_raw'])
                pair=(node['native_cost_plus_30'],node['paid_accumulator_plus_68'])
                if not 0<=pair[1]<=pair[0] or pair[0]<=0:raise ValueError('invalid_queue_payment_field')
                if key in queues[name] and queues[name][key]!=pair:raise ValueError('inconsistent_queue')
                queues[name][key]=pair
    return dict(source='bound_own_infrastructure_observation',builder_frame=builder['frame'],own_census_frame=census['frame'],
        own_template_presence_counts={name:counts[kind] for name,kind in TYPES.items()},available_construction_yards=len(eligible),
        construction_queues={name:dict(observed_queue_count=len(q),observed_cost_sum=sum(v[0] for v in q.values()),
            observed_paid_field_sum=sum(v[1] for v in q.values()),fully_paid_queue_count=sum(v[0]==v[1] for v in q.values()))
            for name,q in queues.items()},presence_includes_unfinished_foundations=True,completed_technology_verified=False,
        exact_queue_to_object_link_verified=False,payment_verified=False,grants_capability=False,own_perspective=True,
        enemy_details_read=False,coverage='named_soviet_templates_only')

def evaluate(run,run_id):
    native=ROOT/'reports'/('macro-desktop-'+run_id)
    pre,final,manifest,raw,_=trial(native)
    events=records(run/'battle-host/host-events.jsonl')
    requests=[r for r in events if r['kind']=='model_macro_request_context']
    responses=[r for r in events if r['kind']=='commander_model_response_returned']
    sources=load(run/'battle-host/sources.json')['sources']
    frozen_ok=all(sha(run/'battle-host/source'/r['copy'])==r['sha256'] for r in sources)
    module_pinned=any(Path(r['path']).name=='macro_infrastructure.py' for r in sources)
    pairs=defaultdict(list);census=None;excluded=[]
    for r in raw:
        if r['session_id']!=final['session_id'] or r['pid']!=final['pid']:raise ValueError('native_sample_binding')
        if r['kind']=='macro_observation' and 'observation' in r:census=r['observation']['construction_feedback']
        if r['kind']=='native_builder_observation' and 'observation' in r and census:
            b=r['observation']
            try:value=independent_projection(b,census)
            except ValueError as error:
                excluded.append(dict(builder_frame=b['frame'],own_census_frame=census['frame'],reason=str(error)))
                continue
            pairs[(b['frame'],census['frame'])].append(value)
    matches=[]
    for r in requests:
        ctx=r['context'];facts=ctx.get('own_infrastructure',{});key=(facts.get('builder_frame'),facts.get('own_census_frame'))
        encoded=json.dumps(ctx,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
        matches.append(dict(sequence=r['sequence'],snapshot_id=ctx['snapshot_id'],game_time_seconds=ctx['game_time_seconds'],
            context_hash_matches=hashlib.sha256(encoded).hexdigest()==r['context_sha256'],
            exact_own_sample_match=any(facts==v for v in pairs.get(key,[])),
            fresh=all(type(f) is int and -15<=ctx['game_time_seconds']*15-f<=30 for f in key)))
    ids={m['snapshot_id'] for m in matches if all(m[k] for k in ('context_hash_matches','exact_own_sample_match','fresh'))}
    checks=dict(pre_execution_projection_source_pinned=module_pinned and frozen_ok,
        every_public_request_has_exact_fresh_own_facts=bool(matches) and all(all(m[k] for k in ('context_hash_matches','exact_own_sample_match','fresh')) for m in matches),
        real_responses_bound_to_these_requests=bool(responses) and all(r['snapshot_id'] in ids and all(
            r.get('transport_receipt',{}).get(k)==v for k,v in dict(real_network_verified=True,https=True,http_status=200,
            injected_transport=False,expected_origin=True,response_complete=True).items()) for r in responses))
    evidence=[run/'battle-host/host-events.jsonl',run/'battle-host/sources.json',native/'policy-probe.jsonl',native/'preflight.json',native/'final-state.json']
    return dict(kind='macro_own_infrastructure_field_assessment',run_id=run_id,session_id=final['session_id'],checks=checks,
        request_count=len(requests),real_response_count=len(responses),request_matches=matches,
        excluded_native_pairs=excluded,
        own_infrastructure_delivery_verified=all(checks.values()),building_completion_verified=False,
        payment_verified=False,model_construction_choice_verified=False,full_G6_verified=False,formal_goal_complete=False,
        evidence={str(p):sha(p) for p in evidence})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-directory',required=True,type=Path)
    p.add_argument('--run-id',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_infrastructure_assessment_required')
    value=evaluate(a.run_directory.resolve(),a.run_id)
    out.mkdir();shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('request_matches','excluded_native_pairs','evidence')}))

if __name__=='__main__':main()
