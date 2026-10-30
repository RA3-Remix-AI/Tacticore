"""Offline assessment of fixed consumer research, with separate raw bindings."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from acceptance import macro_consumer_primed_trial as driver
from acceptance import macro_expansion_primed_trial as frames
from acceptance import assess_macro_expansion_field as common
from acceptance import assess_macro_expansion_primed_field as transport_contract


def canonical_uuid(value):
    try: return type(value) is str and str(uuid.UUID(value)) == value
    except (ValueError,AttributeError): return False


def queues(sample,target,producer):
    """Reconstruct accepted queue identities from exact current owned producers."""
    census={r['thing_id']:r for r in sample['macro']['construction_feedback']['own_objects']}; producers=set(); found={}
    for row in sample['builder']['builders']:
        f=row['factory']; ident=f['thing_id']; own=census.get(ident,{})
        if (f.get('type_hash') != producer or own.get('type_hash') != producer or row.get('observation_available') is not True
                or type(own.get('hp')) not in (int,float) or not math.isfinite(own['hp']) or own['hp'] <= 0 or f.get('hp',0) <= 0): continue
        producers.add(ident)
        for node in row['queue_candidate']['nodes']:
            if node.get('kind_raw') != 1 or node.get('template_hash') != target: continue
            number,cost,paid=(node.get(k) for k in ('production_id_raw','native_cost_plus_30','paid_accumulator_plus_68'))
            if type(number) is not int or number <= 0 or type(cost) is not int or cost <= 0 or type(paid) is not int or not 0 <= paid <= cost:
                raise ValueError('consumer_assessment_queue_fields')
            key=(ident,number)
            if key in found and found[key] != (cost,paid): raise ValueError('consumer_assessment_queue_conflict')
            found[key]=(cost,paid)
    return producers,found


def baseline_valid(sample,config,manifest,mask):
    if frames.sample_frames(sample) is None or not common.scenario_matches(sample) or not common.flag_state(sample.get('flags'),manifest['flags'],mask): return False
    if sample['match'].get('pause_type_candidate') != 0 or sample['match'].get('pause_flag_candidate') != 0: return False
    rows=[r for r in sample['dependency'].get('actions',[]) if r.get('action') == config['action']]
    if (len(rows) != 1 or rows[0].get('target_type_hash') != config['target_type_hash'] or rows[0].get('prerequisite_met') is not True
            or rows[0].get('native_required_objects_met') is not True or rows[0].get('sdk_required_objects_match') is not True): return False
    spec=driver.SPECS[config['action']]; objects=sample['macro']['construction_feedback']['own_objects']
    if spec['absent'] and any(o.get('type_hash') == spec['target'] for o in objects): return False
    producers,found=queues(sample,spec['target'],spec['producer'])
    if not producers or found: return False
    admitted=set()
    for r in rows[0].get('enqueue_admission_candidates',[]):
        if (r.get('producer_type_hash') == spec['producer'] and r.get('native_factory_category_match') is True
                and r.get('native_enqueue_admission_met') is True and type(r.get('native_enqueue_admission_return')) is int
                and r['native_enqueue_admission_return'] == 0 and r.get('native_stop') is False and r.get('native_unpacking') is False
                and type(r.get('queue_occupied')) is int and r['queue_occupied'] == 0 and r.get('unresolved_admission_conditions') == []):
            admitted.add(r.get('producer_thing_id'))
    if not producers <= admitted: return False
    life={r['thing_id']:r for r in sample['dependency'].get('own_lifecycles',[])}
    if any(life.get(p,{}).get('type_hash') != spec['producer'] or life.get(p,{}).get('native_required_object_eligible') is not True
            or life.get(p,{}).get('known_operational_blockers') != [] for p in producers): return False
    if any(r['queue_candidate']['nodes'] for r in sample['builder']['builders'] if r['factory']['thing_id'] in producers): return False
    return not any(r.get('producer_thing_id') in producers for r in sample['builder'].get('jobs',{}).get('construction_jobs',[]))


def adopted(sample,flag,budget):
    try:
        row=sample['budget']; state=row['state_scores'][flag]; feedback=row['budget_feedback']; shares=feedback['account_shares']
        return (frames.sample_frames(sample) is not None
            and all(type(sample['native'].get(k)) is int for k in ('request','ack','phase','error','applied_mask','self_hook_installed','lease_held'))
            and feedback.get('selected_macro_flag') == flag
            and feedback.get('native_percentages_observed') is True and int(state['definition'],0)+12 == int(feedback['selected_budget_key'],0)
            and set(shares) == set(driver.BUDGETS[budget]) and all(type(shares[k]) in (int,float) and math.isfinite(shares[k])
                and abs(shares[k]-expected) <= 1e-5 for k,expected in driver.BUDGETS[budget].items())
            and state.get('domain') == 'budget' and state.get('dirty') is False and type(state.get('score')) in (int,float)
            and math.isfinite(state['score']) and state['score'] > 0)
    except (KeyError,TypeError,ValueError): return False


def assess_data(pre,events,transport,final,result,*,source_integrity,transport_preflight=None):
    config=pre.get('config',{}); manifest=pre.get('manifest',{}); session=pre.get('session',{}); flags=manifest.get('flags',[])
    try:
        expected=driver.options(config['action'],config['seconds'],config['prime_seconds'],config['work_seconds'],config['interval'])
        consumer=driver.manifest_consumer(manifest,config['action']); spec=driver.SPECS[config['action']]
        fixed=(config == expected and all(type(config[k]) is type(expected[k]) for k in expected)
            and pre.get('kind') == 'fixed_consumer_primed_field_preflight'
            and type(pre.get('schema_version')) is int and pre['schema_version'] == 1 and pre.get('protocol_version') == 2)
    except (KeyError,TypeError,ValueError): fixed=False; consumer={}; spec={}
    action=config.get('action'); budget=config.get('budget_action'); work_flag=consumer.get('flag')
    budget_flag=next((r.get('flag') for r in manifest.get('consumers',[]) if r.get('action') == budget),None)
    bm=1 << flags.index(budget_flag) if budget_flag in flags else 0; wm=bm | (1 << flags.index(work_flag) if work_flag in flags else 0)
    samples=[e for e in events if e.get('kind') == 'sample']; valid=[e for e in samples if frames.sample_frames(e.get('sample')) is not None]
    def one(kind):
        rows=[e for e in events if e.get('kind') == kind]; return rows[0] if len(rows) == 1 else None
    pp,pa,wp,wa,clear=[one(k) for k in ('budget_prime_prepared','budget_prime_acknowledged','intent_prepared','intent_acknowledged','intent_cleared')]
    natives=[e['sample']['macro'].get('native',{}) for e in valid]; owner=natives[0] if natives else {}
    began=result.get('live_lifecycle_began_monotonic_ns'); ended=result.get('live_lifecycle_ended_monotonic_ns')
    checks=dict(source_archives_intact=source_integrity is True,fixed_consumer_scope=fixed,
        zero_model_and_unit_orders=all(type(d.get(k)) is int and d[k] == 0 for d in (pre,result) for k in ('model_calls','unit_orders'))
            and pre.get('enemy_details_read') is False and result.get('enemy_details_read') is False,
        session_package_bound=type(session.get('pid')) is int and session['pid'] > 0 and type(session.get('process_creation_filetime')) is int
            and session['process_creation_filetime'] > 0 and session.get('mod_sha256') == manifest.get('package_sha256'),
        lifecycle_within_sixty_seconds=fixed and type(began) is int and type(ended) is int and 0 <= ended-began <= config['seconds']*1e9,
        sources_unchanged_at_end=result.get('source_archives_unchanged') is True and result.get('source_originals_unchanged') is True,
        memory_closed=result.get('memory_closed') is True,
        scenario_and_frames_verified=bool(valid) and len(valid) == len(samples) and all(common.scenario_matches(e['sample']) for e in valid),
        p3_identity_consistent=bool(natives) and all(n == owner and n.get('player_index') == 3 and n.get('instance_id') == '0x799613e0'
            and n.get('store_membership_verified') is True and n.get('side_matches_player') is True for n in natives),
        native_process_incarnation_bound=all(transport_contract.native_binding(e['sample'].get('native'),session,owner)
            for e in valid if e.get('phase') != 'before_attach') and transport_contract.native_binding((final or {}).get('native'),session,owner),
        transport_session_bound=bool(transport) and all(e.get('session_id') == session.get('session_id') and e.get('pid') == session.get('pid') for e in transport),
        no_unknown_or_fault=not any(e.get('kind') in ('trial_fault','clear_unknown','close_unknown','initialization_failed') for e in events)
            and not any(e.get('kind') in ('command_unknown','independent_readback_unknown') for e in transport),
        initial_transport_quiescent=type(transport_preflight) is dict and transport_preflight.get('session_sha256') == pre.get('session_sha256')
            and transport_preflight.get('process_creation_filetime') == session.get('process_creation_filetime')
            and transport_preflight.get('native') == owner and common.flag_state(transport_preflight.get('initial_flags'),flags))
    checks.update(prime_ack_bound=False,prime_window_bound=False,two_distinct_prime_budget_frames=False,
        initial_legal_idle_baseline=False,fresh_legal_post_prime_baseline=False,work_ack_bound=False,work_window_bound=False,
        explicit_clear_bound=False,work_budget_reobserved=False,positive_native_score_inside_work=False,
        matching_new_queue_inside_work=False,clear_after_first_queue_without_extra_sample=False,
        exact_four_command_ledger=False,close_ack_bound=False,independent_clean_close=False)
    effects=dict(prime_budget_frames=[],work_budget_frames=[],positive_state_frames=[],matching_new_queue_observations=[],
        first_observed_queue_batch_count=0,baseline_producer_ids=[],baseline_object_ids=[],completion_verified=False,payment_verified=False,
        hard_native_queue_cap=False,exclusive_attribution_verified=False)
    if fixed:
        initial_events=[e for e in valid if e.get('phase') in ('before_attach','baseline_attached')]
        checks['initial_legal_idle_baseline']=([e.get('phase') for e in initial_events] == ['before_attach','baseline_attached']
            and pp is not None and events.index(initial_events[-1]) < events.index(pp)
            and all(baseline_valid(e['sample'],config,manifest,0) for e in initial_events))
        aug=lambda e:dict(e,_flags=flags) if type(e) is dict else None
        checks['prime_ack_bound']=transport_contract.ack_binding(aug(pp),pa,transport,session,bm)
        checks['work_ack_bound']=transport_contract.ack_binding(aug(wp),wa,transport,session,wm)
        for key,event in (('prime_ack_bound',pa),('work_ack_bound',wa)):
            checks[key]=checks[key] and transport_contract.native_binding(event['receipt']['native'],session,owner)
        if checks['prime_ack_bound']:
            window=pp['window']; start,end=window.get('starts_monotonic_ns'),window.get('expires_monotonic_ns')
            checks['prime_window_bound']=(type(start) is int and type(end) is int and 0 < end-start <= config['prime_seconds']*1e9
                and 1 <= window['native_duration_frames'] <= 225 and window.get('kind') == 'consumer_budget_prime_window'
                and window.get('model_calls') == 0 and window.get('unknown_native_precondition_probe') is False
                and pp.get('policy') == [budget] and pa['receipt']['seq'] == 1 and events.index(pp) < events.index(pa))
            good=[e for e in valid if checks['prime_window_bound'] and e.get('phase') == 'prime' and events.index(pa) < events.index(e)
                and wp is not None and events.index(e) < events.index(wp) and frames.within(e['sample'],pa['receipt'],window,bm,manifest)
                and adopted(e['sample'],budget_flag,budget)]
            effects['prime_budget_frames']=sorted({e['sample']['budget']['frame'] for e in good})
            checks['two_distinct_prime_budget_frames']=len(effects['prime_budget_frames']) >= 2
            baselines=[e for e in valid if e.get('phase') == 'work_baseline' and wp is not None and events.index(pa) < events.index(e) < events.index(wp)]
            baseline=baselines[-1] if baselines else None
            if baseline and checks['two_distinct_prime_budget_frames']:
                s=baseline['sample']; producers,old=queues(s,spec['target'],spec['producer'])
                checks['fresh_legal_post_prime_baseline']=(s['started_monotonic_ns'] >= max(e['sample']['ended_monotonic_ns'] for e in good)
                    and min(frames.sample_frames(s)) >= max(effects['prime_budget_frames']) and frames.within(s,pa['receipt'],window,bm,manifest)
                    and adopted(s,budget_flag,budget) and baseline_valid(s,config,manifest,bm) and not old)
                if checks['fresh_legal_post_prime_baseline']:
                    effects['baseline_producer_ids']=sorted(producers)
                    effects['baseline_object_ids']=sorted(r['thing_id'] for r in s['macro']['construction_feedback']['own_objects'] if r['type_hash'] == spec['target'])
        if checks['work_ack_bound'] and checks['prime_ack_bound']:
            window=wp['window']; start,end=window.get('starts_monotonic_ns'),window.get('expires_monotonic_ns'); receipt=wa['receipt']
            checks['work_window_bound']=(type(start) is int and type(end) is int and 0 < end-start <= config['work_seconds']*1e9
                and 1 <= window['native_duration_frames'] <= int(config['work_seconds']*15) and window.get('kind') == 'consumer_fixed_work_window'
                and window.get('model_calls') == 0 and window.get('unknown_native_precondition_probe') is False
                and wp.get('policy') == config['policy'] and wp.get('action') == action and wp.get('target_type_hash') == spec['target']
                and wp.get('producer_type_hash') == spec['producer'] and type(wp.get('additional_count')) is int and wp['additional_count'] == 1
                and type(wp.get('queue_observation_trigger_count')) is int and wp['queue_observation_trigger_count'] == 1
                and wp.get('hard_native_queue_cap') is False and wp.get('baseline_queues') == []
                and wp.get('baseline_producer_ids') == effects['baseline_producer_ids'] and wp.get('baseline_objects') == effects['baseline_object_ids']
                and receipt['seq'] == 2 and events.index(pa) < events.index(wp) < events.index(wa))
            checks['explicit_clear_bound']=common.explicit_clear_chain(clear,transport,flags,session,wp['command_id'],2,receipt['native']['last_frame'])
            checks['explicit_clear_bound']=(checks['explicit_clear_bound'] and transport_contract.native_binding(clear['receipt']['native'],session,owner)
                and type(clear.get('monotonic_ns')) is int and events.index(wa) < events.index(clear)
                and start <= clear['monotonic_ns'] <= end+2_000_000_000)
            seen=set(); first_event=None
            for event in valid:
                if event.get('phase') != 'active': continue
                s=event['sample']; producers,current=queues(s,spec['target'],spec['producer']); new=set(current)-seen; seen.update(current)
                deps=[r for r in s['dependency'].get('actions',[]) if r.get('action') == action]
                prerequisite=(len(deps) == 1 and deps[0].get('target_type_hash') == spec['target']
                    and deps[0].get('prerequisite_met') is True and deps[0].get('native_required_objects_met') is True
                    and deps[0].get('sdk_required_objects_match') is True)
                legal=(prerequisite and checks['fresh_legal_post_prime_baseline'] and checks['work_window_bound'] and checks['explicit_clear_bound']
                    and events.index(wa) < events.index(event) < events.index(clear) and s['ended_monotonic_ns'] <= clear['monotonic_ns']
                    and all(f <= clear['receipt']['native']['last_frame'] for f in frames.sample_frames(s))
                    and producers == set(effects['baseline_producer_ids']) and frames.within(s,receipt,window,wm,manifest)
                    and adopted(s,budget_flag,budget) and s['match'].get('pause_type_candidate') == s['match'].get('pause_flag_candidate') == 0)
                if not legal: continue
                effects['work_budget_frames'].append(s['budget']['frame'])
                if any(r.get('flag') == work_flag and r.get('dirty') is False and type(r.get('state_score')) in (int,float)
                        and math.isfinite(r['state_score']) and r['state_score'] > 0
                        and any(e.get('build_type_hash_raw') == spec['target'] for e in r.get('entries',[])) for r in s['builder'].get('macro_entries',[])):
                    effects['positive_state_frames'].append(s['builder']['frame'])
                if new and first_event is None:
                    first_event=event; effects['first_observed_queue_batch_count']=len(new)
                    for p,n in sorted(new): effects['matching_new_queue_observations'].append(dict(producer_thing_id=p,production_id=n,
                        frame=s['builder']['frame'],native_cost_raw=current[p,n][0],paid_accumulator_raw=current[p,n][1]))
            if first_event:
                checks['clear_after_first_queue_without_extra_sample']=(clear['monotonic_ns']-first_event['sample']['ended_monotonic_ns'] <= 2_000_000_000
                    and not any(e.get('phase') == 'active' for e in events[events.index(first_event)+1:events.index(clear)]))
    pending=[e for e in transport if e.get('kind') == 'command_prepared']; acks=[e for e in transport if e.get('kind') == 'command_acknowledged']
    checks['exact_four_command_ledger']=(len(pending) == len(acks) == 4 and all(type(e.get('seq')) is int for e in pending+acks)
        and [e['seq'] for e in pending] == [e['seq'] for e in acks] == [1,2,3,4]
        and all(canonical_uuid(e.get('command_id')) for e in pending)
        and all(transport.index(acks[i]) < transport.index(pending[i+1]) for i in range(3))
        and len({e.get('command_id') for e in pending}) == 4 and {e.get('command_id') for e in pending} == {e.get('command_id') for e in acks})
    required=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0,request=4,ack=4)
    checks['independent_clean_close']=(type(final) is dict and all(final.get(k) == session.get(k) for k in ('session_id','pid','process_creation_filetime','mod_sha256'))
        and final.get('cleanup_verified') is True and type(final.get('host_returncode')) is int and final['host_returncode'] == 0
        and final.get('unknown_command_ids') == [] and common.flag_state(final.get('independent_flags'),flags)
        and all(type(final.get('native',{}).get(k)) is int and final['native'][k] == v for k,v in required.items()))
    stop=[e for e in pending if e.get('seq') == 4]; stopped=[e for e in acks if e.get('seq') == 4]
    if len(stop) == len(stopped) == 1:
        p,a=stop[0],stopped[0]
        checks['close_ack_bound']=(type(p.get('kind_code')) is int and p['kind_code'] == 2 and type(p.get('mask')) is int and p['mask'] == 0
            and type(p.get('duration_frames')) is int and p['duration_frames'] == 0 and p.get('command_id') == a.get('command_id')
            and a.get('native_gate_acknowledged') is True and transport.index(p) < transport.index(a)
            and transport_contract.native_binding(a.get('native'),session,owner) and common.flag_state(a.get('independent_flags'),flags)
            and all(type(a.get('native',{}).get(k)) is int and a['native'][k] == v for k,v in required.items()))
    checks['work_budget_reobserved']=bool(effects['work_budget_frames']); checks['positive_native_score_inside_work']=bool(effects['positive_state_frames'])
    checks['matching_new_queue_inside_work']=bool(effects['matching_new_queue_observations'])
    supported=all(checks.values())
    return dict(kind='fixed_consumer_primed_field_assessment',schema_version=1,action=action,checks=checks,native_effects=effects,
        disposition='research_consumer_queue_supported' if supported else 'not_qualified',fixed_consumer_effect_supported=supported,
        model_calls=0,product_capability_granted=False,field_qualification_granted=False,formal_runtime_qualification=False,formal_goal_complete=False)


def assess(run):
    pre=common.load(run/'driver-preflight.json'); events=common.records(run/'consumer-trial.jsonl')
    final=common.load(run/'transport/final-state.json') if (run/'transport/final-state.json').exists() else None
    tp=common.load(run/'transport/preflight.json') if (run/'transport/preflight.json').exists() else None
    transport=common.records(run/'transport/policy-probe.jsonl') if (run/'transport/policy-probe.jsonl').exists() else []
    integrity=common.verify_archives(run,pre)
    sources={Path(r['path']).resolve() for r in pre.get('sources',[])}
    required=('acceptance/macro_consumer_primed_trial.py','acceptance/assess_macro_consumer_primed_field.py',
        'acceptance/macro_expansion_primed_trial.py','acceptance/assess_macro_expansion_primed_field.py','native-ai/macro_budget_observation.py')
    return assess_data(pre,events,transport,final,common.load(run/'driver-result.json'),
        source_integrity=integrity and all((ROOT/name).resolve() in sources for name in required),transport_preflight=tp)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--run',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args(); output=a.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports'): raise ValueError('fresh_consumer_assessment_required')
    result=assess(a.run.resolve()); output.mkdir(parents=True); shutil.copy2(__file__,output/'assessor.py')
    result['assessor_sha256']=common.sha(Path(__file__)); (output/'assessment.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(output),disposition=result['disposition'],capability_granted=False)))


if __name__ == '__main__': main()
