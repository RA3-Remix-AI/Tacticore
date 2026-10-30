"""Independent offline assessment of the separate primed refinery research."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from acceptance import assess_macro_expansion_field as common
from acceptance import macro_expansion_primed_trial as primed

def native_binding(native,session,owner):
    try:
        creation=session['process_creation_filetime']
        required=dict(magic=0x4d503032,version=2,pid=session['pid'],start_low=creation&0xffffffff,start_high=creation>>32,
            owner=int(owner['player'],0),ai=int(owner['ai_player'],0),personality=int(owner['personality_wrapper'],0),
            player_template=int(owner['player_template'],0),personality_id=0x799613e0)
    except (KeyError,ValueError,TypeError):return False
    return type(native) is dict and all(type(native.get(k)) is int and native[k]==v for k,v in required.items())

def ack_binding(prepared,event,transport,session,mask):
    if type(prepared) is not dict or type(event) is not dict:return False
    receipt=event.get('receipt');window=prepared.get('window',{});ident=prepared.get('command_id')
    if type(receipt) is not dict or type(window) is not dict:return False
    try:
        if type(ident) is not str or str(uuid.UUID(ident))!=ident:return False
        begin,end=primed.receipt_window(receipt,window['native_duration_frames'])
    except (KeyError,ValueError,TypeError,AttributeError):return False
    seq=receipt['seq'];native=receipt['native']
    pending=[e for e in transport if e.get('kind')=='command_prepared' and e.get('command_id')==ident]
    acks=[e for e in transport if e.get('kind')=='command_acknowledged' and e.get('command_id')==ident]
    if len(pending)!=1 or len(acks)!=1:return False
    p,a=pending[0],acks[0]
    return (receipt.get('command_id')==ident and 0<seq<=2048 and type(window.get('native_duration_frames')) is int
        and all(type(p.get(k)) is int for k in ('seq','kind_code','mask','duration_frames'))
        and (p['seq'],p['kind_code'],p['mask'],p['duration_frames'])==(seq,1,mask,window['native_duration_frames'])
        and transport.index(p)<transport.index(a) and type(a.get('seq')) is int and a['seq']==seq
        and a.get('native_gate_acknowledged') is True and a.get('native')==native
        and a.get('independent_flags')==receipt.get('independent_flags')
        and common.flag_state(receipt.get('independent_flags'),prepared['_flags'],mask)
        and all((e.get('session_id'),e.get('pid'))==(session.get('session_id'),session.get('pid')) for e in (p,a))
        and all(type(native.get(k)) is int and native[k]==v for k,v in dict(request=seq,ack=seq,applied_mask=mask,phase=1,error=0,self_hook_installed=1,lease_held=1).items())
        and type(native.get('last_frame')) is int and begin<=native['last_frame']<end)

def assess_data(pre,events,transport,final,result,*,source_integrity,transport_preflight=None):
    session=pre.get('session',{});manifest=pre.get('manifest',{});config=pre.get('config',{});flags=manifest.get('flags',[])
    consumers={c.get('action'):c.get('flag') for c in manifest.get('consumers',[]) if type(c) is dict}
    valid_scope=(pre.get('kind')=='primed_macro_expansion_field_preflight' and type(pre.get('schema_version')) is int and pre['schema_version']==1
        and pre.get('protocol_version')==manifest.get('protocol_version')==2 and len(flags)==20 and len(set(flags))==20
        and consumers.get('budgeteconomy') in flags and consumers.get('buildrefinery') in flags)
    try:expected=primed.options(config['seconds'],config['prime_seconds'],config['interval'],config['allow_unknown_native_precondition'])
    except (KeyError,ValueError,TypeError):expected=None
    budget_flag=consumers.get('budgeteconomy');work_flag=consumers.get('buildrefinery')
    budget_mask=1<<flags.index(budget_flag) if budget_flag in flags else 0
    work_mask=budget_mask|(1<<flags.index(work_flag)) if work_flag in flags else 0
    samples=[e for e in events if e.get('kind')=='sample'];valid=[e for e in samples if primed.sample_frames(e.get('sample')) is not None]
    def single(kind):
        found=[e for e in events if e.get('kind')==kind];return found[0] if len(found)==1 else None
    pp,pa,wp,wa,clear=[single(k) for k in ('budget_prime_prepared','budget_prime_acknowledged','intent_prepared','intent_acknowledged','intent_cleared')]
    began=result.get('live_lifecycle_began_monotonic_ns');ended=result.get('live_lifecycle_ended_monotonic_ns')
    checks=dict(source_archives_intact=source_integrity is True,fixed_primed_scope=valid_scope and expected==config and type(config.get('model_calls')) is int,
        zero_model_and_unit_orders=all(type(data.get(key)) is int and data[key]==0 for data in (pre,result) for key in ('model_calls','unit_orders'))
            and pre.get('enemy_details_read') is False and result.get('enemy_details_read') is False,
        session_package_bound=type(session.get('pid')) is int and session['pid']>0 and type(session.get('process_creation_filetime')) is int
            and session['process_creation_filetime']>0 and session.get('mod_sha256')==manifest.get('package_sha256'),
        lifecycle_within_sixty_seconds=type(began) is int and type(ended) is int and expected is not None and 0<=ended-began<=config['seconds']*1e9,
        sources_unchanged_at_end=result.get('source_archives_unchanged') is True and result.get('source_originals_unchanged') is True,
        memory_closed=result.get('memory_closed') is True,
        transport_session_bound=all(e.get('session_id')==session.get('session_id') and e.get('pid')==session.get('pid') for e in transport),
        scenario_and_frames_verified=bool(valid) and len(valid)==len(samples) and all(common.scenario_matches(e['sample']) for e in valid),
        no_unknown_or_fault=not any(e.get('kind') in ('trial_fault','clear_unknown','close_unknown','initialization_failed') for e in events)
            and not any(e.get('kind') in ('command_unknown','independent_readback_unknown') for e in transport))
    native_identities=[e['sample']['macro'].get('native',{}) for e in valid]
    checks['p3_identity_consistent']=bool(native_identities) and all(n==native_identities[0] and n.get('player_index')==3
        and n.get('instance_id')=='0x799613e0' and n.get('store_membership_verified') is True and n.get('side_matches_player') is True for n in native_identities)
    owner=native_identities[0] if native_identities else {}
    checks['native_process_incarnation_bound']=all(native_binding(e['sample'].get('native'),session,owner) for e in valid if e.get('phase')!='before_attach') and native_binding((final or {}).get('native'),session,owner)
    checks['initial_transport_quiescent']=(type(transport_preflight) is dict and transport_preflight.get('session_sha256')==pre.get('session_sha256')
        and transport_preflight.get('process_creation_filetime')==session.get('process_creation_filetime')
        and transport_preflight.get('native')==(native_identities[0] if native_identities else None)
        and common.flag_state(transport_preflight.get('initial_flags'),flags))
    checks['independent_clean_close']=(type(final) is dict and all(final.get(k)==session.get(k) for k in ('session_id','pid','process_creation_filetime','mod_sha256'))
        and final.get('cleanup_verified') is True and type(final.get('host_returncode')) is int and final['host_returncode']==0 and final.get('unknown_command_ids')==[]
        and common.flag_state(final.get('independent_flags'),flags)
        and all(type(final.get('native',{}).get(k)) is int and final['native'][k]==v for k,v in dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0).items()))
    effects=dict(prime_budget_frames=[],work_budget_frames=[],positive_state_frames=[],matching_new_queue_observations=[],
        baseline_object_ids=[],baseline_queue_count=None,completion_verified=False,payment_verified=False,exclusive_attribution_verified=False)
    checks.update(prime_ack_bound=False,prime_wall_at_most_fifteen=False,two_distinct_prime_budget_frames=False,
        fresh_legal_post_prime_baseline=False,work_ack_bound=False,work_window_at_most_four_seconds=False,
        explicit_clear_bound=False,work_budget_reobserved=False,positive_native_score_inside_work=False,matching_new_queue_inside_work=False)
    def augmented(event):return dict(event,_flags=flags) if type(event) is dict else None
    checks['prime_ack_bound']=ack_binding(augmented(pp),pa,transport,session,budget_mask)
    checks['work_ack_bound']=ack_binding(augmented(wp),wa,transport,session,work_mask)
    checks['prime_ack_bound']=checks['prime_ack_bound'] and native_binding(pa['receipt']['native'],session,owner)
    checks['work_ack_bound']=checks['work_ack_bound'] and native_binding(wa['receipt']['native'],session,owner)
    checks['close_ack_bound']=False
    if type(final) is dict and native_binding(final.get('native'),session,owner):
        seq=final['native'].get('ack');stop=[e for e in transport if e.get('kind')=='command_prepared' and e.get('seq')==seq]
        acks=[e for e in transport if e.get('kind')=='command_acknowledged' and e.get('seq')==seq]
        if len(stop)==len(acks)==1:
            pending,ack=stop[0],acks[0]
            checks['close_ack_bound']=(type(seq) is int and final['native'].get('request')==seq
                and all(type(pending.get(k)) is int for k in ('seq','kind_code','mask','duration_frames'))
                and type(ack.get('seq')) is int and ack['seq']==seq and pending.get('kind_code')==2
                and pending.get('mask')==0 and pending.get('duration_frames')==0 and pending.get('command_id')==ack.get('command_id')
                and ack.get('native_gate_acknowledged') is True and native_binding(ack.get('native'),session,owner)
                and transport.index(pending)<transport.index(ack) and common.flag_state(ack.get('independent_flags'),flags)
                and all(type(ack['native'].get(k)) is int and ack['native'][k]==v for k,v in dict(request=seq,ack=seq,phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0).items()))
    pending=[e for e in transport if e.get('kind')=='command_prepared'];acks=[e for e in transport if e.get('kind')=='command_acknowledged']
    checks['exact_four_command_ledger']=(len(pending)==len(acks)==4
        and all(type(e.get('seq')) is int for e in pending+acks)
        and sorted(e['seq'] for e in pending)==sorted(e['seq'] for e in acks)==[1,2,3,4]
        and len({e.get('command_id') for e in pending})==4 and {e.get('command_id') for e in pending}=={e.get('command_id') for e in acks})
    if checks['prime_ack_bound']:
        window=pp['window'];start,end=window.get('starts_monotonic_ns'),window.get('expires_monotonic_ns')
        checks['prime_wall_at_most_fifteen']=(type(start) is int and type(end) is int and 0<end-start<=15e9
            and window.get('kind')=='budget_prime_research_window' and window.get('model_calls')==0
            and 1<=window['native_duration_frames']<=225 and pp.get('policy')==['budgeteconomy'] and events.index(pp)<events.index(pa))
        if checks['prime_wall_at_most_fifteen']:
            prime_samples=[e for e in valid if e.get('phase')=='prime' and events.index(pa)<events.index(e)
                and (wp is None or events.index(e)<events.index(wp))
                and primed.within(e['sample'],pa['receipt'],window,budget_mask,manifest) and primed.budget_adopted(e['sample'],budget_flag)]
            effects['prime_budget_frames']=sorted({e['sample']['budget']['frame'] for e in prime_samples})
            checks['two_distinct_prime_budget_frames']=len(effects['prime_budget_frames'])>=2
            baselines=[e for e in valid if e.get('phase')=='work_baseline' and wp is not None
                and events.index(pa)<events.index(e)<events.index(wp)]
            baseline=baselines[-1] if baselines else None
            if checks['two_distinct_prime_budget_frames'] and baseline:
                sample=baseline['sample'];prime_end=max(e['sample']['ended_monotonic_ns'] for e in prime_samples)
                checks['fresh_legal_post_prime_baseline']=(sample['started_monotonic_ns']>=prime_end
                    and min(primed.sample_frames(sample))>=max(effects['prime_budget_frames'])
                    and primed.within(sample,pa['receipt'],window,budget_mask,manifest) and primed.budget_adopted(sample,budget_flag)
                    and primed.precondition(sample,config,manifest,primed=True))
                if checks['fresh_legal_post_prime_baseline']:
                    _,baseline_queues,objects=common.native_queues(sample,'0xc45aaeab')
                    effects['baseline_object_ids']=sorted(i for i,kind in objects.items() if kind=='0xc45aaeab')
                    effects['baseline_queue_count']=len(baseline_queues)
    if checks['work_ack_bound'] and checks['prime_ack_bound']:
        receipt=wa['receipt'];window=wp['window'];start,end=window.get('starts_monotonic_ns'),window.get('expires_monotonic_ns')
        checks['work_window_at_most_four_seconds']=(type(start) is int and type(end) is int and 0<end-start<=4e9
            and 1<=window['native_duration_frames']<=60 and window.get('model_calls')==0 and window.get('unknown_native_precondition_probe') is True
            and wp.get('policy')==['buildrefinery','budgeteconomy'] and wp.get('additional_count')==1
            and wp.get('target_type_hash')=='0xc45aaeab' and receipt['seq']==pa['receipt']['seq']+1
            and window.get('kind')=='fixed_intent_research_window'
            and events.index(pa)<events.index(wp)<events.index(wa))
        checks['explicit_clear_bound']=common.explicit_clear_chain(clear,transport,flags,session,wp['command_id'],receipt['seq'],receipt['native']['last_frame'])
        checks['explicit_clear_bound']=checks['explicit_clear_bound'] and native_binding(clear['receipt']['native'],session,owner)
        timing=(checks['explicit_clear_bound'] and type(clear.get('monotonic_ns')) is int
            and type(start) is int and events.index(wa)<events.index(clear) and start<=clear['monotonic_ns']<=start+5_000_000_000)
        checks['explicit_clear_bound']=bool(timing)
        seen_queues=set()
        for event in valid:
            if event.get('phase')!='active':continue
            sample=event['sample'];_,queues,_=common.native_queues(sample,'0xc45aaeab')
            first=set(queues)-seen_queues;seen_queues.update(queues)
            legal=(checks['fresh_legal_post_prime_baseline'] and checks['work_window_at_most_four_seconds'] and checks['explicit_clear_bound']
                and events.index(wa)<events.index(event)<events.index(clear)
                and sample['ended_monotonic_ns']<=clear['monotonic_ns'] and all(f<=clear['receipt']['native']['last_frame'] for f in primed.sample_frames(sample))
                and primed.within(sample,receipt,window,work_mask,manifest) and primed.budget_adopted(sample,budget_flag))
            if not legal:continue
            effects['work_budget_frames'].append(sample['budget']['frame'])
            if primed.construction.positive_score(sample,work_flag,'0xc45aaeab'):effects['positive_state_frames'].append(sample['builder']['frame'])
            for producer,number in sorted(first):effects['matching_new_queue_observations'].append(dict(frame=sample['builder']['frame'],producer_thing_id=producer,production_id=number))
    checks['work_budget_reobserved']=bool(effects['work_budget_frames'])
    checks['positive_native_score_inside_work']=bool(effects['positive_state_frames'])
    checks['matching_new_queue_inside_work']=bool(effects['matching_new_queue_observations'])
    supported=all(checks.values())
    return dict(kind='primed_macro_expansion_field_assessment',schema_version=1,action='buildrefinery',checks=checks,native_effects=effects,
        disposition='research_consumer_effect_supported' if supported else 'not_qualified',fixed_consumer_effect_supported=supported,
        model_calls=0,product_capability_granted=False,field_qualification_granted=False,formal_runtime_qualification=False,
        open_node_independent_readback_verified=False,formal_goal_complete=False)

def assess(run):
    pre=common.load(run/'driver-preflight.json');events=common.records(run/'primed-trial.jsonl')
    final=common.load(run/'transport/final-state.json') if (run/'transport/final-state.json').exists() else None
    tp=common.load(run/'transport/preflight.json') if (run/'transport/preflight.json').exists() else None
    transport=common.records(run/'transport/policy-probe.jsonl') if (run/'transport/policy-probe.jsonl').exists() else []
    integrity=common.verify_archives(run,pre)
    required=('acceptance/macro_expansion_primed_trial.py','acceptance/assess_macro_expansion_primed_field.py','native-ai/macro_budget_observation.py')
    sources={Path(r['path']).resolve():r for r in pre.get('sources',[])}
    integrity=integrity and all((ROOT/name).resolve() in sources for name in required)
    return assess_data(pre,events,transport,final,common.load(run/'driver-result.json'),source_integrity=integrity,transport_preflight=tp)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports'):raise ValueError('fresh_primed_assessment_required')
    value=assess(args.run.resolve());output.mkdir(parents=True);shutil.copy2(__file__,output/'assessor.py')
    value['assessor_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output/'assessment.json').write_text(json.dumps(value,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(output),disposition=value['disposition'],capability_granted=False)))

if __name__=='__main__':main()
