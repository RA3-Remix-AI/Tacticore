"""Independent fixed-consumer research; live work exists only in CLI main.

One budget prime, a fresh idle baseline, one bounded work gate, then clear and
close. The first observed queue triggers clear; it is not a native quantity cap.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from acceptance import macro_expansion_field_trial as base
from acceptance import macro_expansion_primed_trial as primed
from acceptance import assess_macro_expansion_field as common

ACCOUNTS = ('investment','special_operations','production','defense','technology','slush_fund')
BUDGETS = {'budgeteconomy':dict(zip(ACCOUNTS,(.4,0,.25,.1,.15,.1))),
           'budgetarmy':dict(zip(ACCOUNTS,(.1,0,.7,.1,.05,.05)))}
SPECS = {
    'buildbarracks':dict(target='0x80d4ea1e',producer='0xc16ff13f',domain='construction',budget='budgeteconomy',
        template='SovietBarracks',producer_template='SovietConstructionYard',absent=True,required=[]),
    'buildfactory':dict(target='0xd50c222e',producer='0xc16ff13f',domain='construction',budget='budgeteconomy',
        template='SovietWarFactory',producer_template='SovietConstructionYard',absent=True,required=['SovietRefinery']),
    'buildbattlelab':dict(target='0xb7377639',producer='0xc16ff13f',domain='construction',budget='budgeteconomy',
        template='SovietTechStructure',producer_template='SovietConstructionYard',absent=True,required=['SovietPowerPlantAdvanced']),
    'producesickle':dict(target='0x60f0b4e9',producer='0xd50c222e',domain='production',budget='budgetarmy',
        template='SovietAntiInfantryVehicle',producer_template='SovietWarFactory',absent=False,required=['SovietWarFactory']),
    'producebullfrog':dict(target='0x522bcb61',producer='0xd50c222e',domain='production',budget='budgetarmy',
        template='SovietAntiAirShip_Ground',producer_template='SovietWarFactory',absent=False,required=['SovietWarFactory']),
}


def options(action, seconds=60, prime_seconds=12, work_seconds=8, interval=.25):
    if action not in SPECS: raise ValueError('consumer_fixed_action_required')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (seconds,prime_seconds,work_seconds,interval)):
        raise ValueError('consumer_finite_bounds')
    if not 35 <= seconds <= 60 or not 1 <= prime_seconds <= 15 or not 1 <= work_seconds <= 12 or not .2 <= interval <= .5:
        raise ValueError('consumer_research_bounds')
    s = SPECS[action]
    return dict(action=action,target_type_hash=s['target'],producer_type_hash=s['producer'],domain=s['domain'],
        seconds=float(seconds),prime_seconds=float(prime_seconds),work_seconds=float(work_seconds),interval=float(interval),
        budget_action=s['budget'],policy=[action,s['budget']],additional_count=1,queue_observation_trigger_count=1,
        hard_native_queue_cap=False,allow_unknown_native_precondition=False,model_calls=0,product_capability_granted=False)


def manifest_consumer(manifest, action):
    s = SPECS[action]; flags = manifest.get('flags'); rows = manifest.get('consumers')
    if (type(manifest.get('protocol_version')) is not int or manifest['protocol_version'] != 2
            or type(flags) is not list or len(flags) != 20 or any(type(f) is not str for f in flags) or len(set(flags)) != 20
            or type(rows) is not list or len(rows) != 20 or any(type(r) is not dict for r in rows) or [r.get('flag') for r in rows] != flags
            or len({r.get('action') for r in rows}) != 20): raise ValueError('consumer_twenty_gate_manifest')
    matches = [r for r in rows if r.get('action') == action]
    if len(matches) != 1: raise ValueError('consumer_unique_manifest_action')
    row = matches[0]
    expected = dict(template=s['template'],producer=s['producer_template'],domain=s['domain'],heuristic='CONSTANT',
        only_if_target_absent=s['absent'],required_own_templates=s['required'])
    if any(row.get(k) != v for k,v in expected.items()) or type(row.get('only_if_target_absent')) is not bool:
        raise ValueError('consumer_manifest_semantics')
    if len([r for r in rows if r.get('action') == s['budget'] and r.get('domain') == 'budget']) != 1:
        raise ValueError('consumer_budget_manifest')
    return row


def budget_adopted(sample, flag, budget_action):
    if primed.sample_frames(sample) is None: return False
    try:
        value=sample['budget']; feedback=value['budget_feedback']; shares=feedback['account_shares']; row=value['state_scores'][flag]
        return (all(type(sample['native'].get(k)) is int for k in ('request','ack','phase','error','applied_mask','self_hook_installed','lease_held'))
            and int(row['definition'],0)+0xc == int(feedback['selected_budget_key'],0)
            and feedback['selected_macro_flag'] == flag and feedback['native_percentages_observed'] is True
            and set(shares) == set(BUDGETS[budget_action]) and all(type(shares[k]) in (int,float)
                and math.isfinite(shares[k]) and abs(shares[k]-v) <= 1e-5 for k,v in BUDGETS[budget_action].items())
            and row['domain'] == 'budget' and row['dirty'] is False and type(row['score']) in (int,float)
            and math.isfinite(row['score']) and row['score'] > 0)
    except (KeyError,ValueError,TypeError): return False


def queue_rows(sample, config):
    """Only exact own producer+target; retain all distinct queues in a batch."""
    census={r['thing_id']:r for r in sample['macro']['construction_feedback']['own_objects']}; producers=set(); queues={}
    for row in sample['builder']['builders']:
        f=row['factory']; ident=f['thing_id']; own=census.get(ident,{})
        if (f.get('type_hash') != config['producer_type_hash'] or own.get('type_hash') != config['producer_type_hash']
                or type(own.get('hp')) not in (int,float) or not math.isfinite(own['hp']) or own['hp'] <= 0
                or f.get('hp',0) <= 0 or row.get('observation_available') is not True): continue
        producers.add(ident)
        for node in row['queue_candidate']['nodes']:
            if node.get('kind_raw') != 1 or node.get('template_hash') != config['target_type_hash']: continue
            number,cost,paid=(node.get(k) for k in ('production_id_raw','native_cost_plus_30','paid_accumulator_plus_68'))
            if type(number) is not int or number <= 0 or type(cost) is not int or cost <= 0 or type(paid) is not int or not 0 <= paid <= cost:
                raise ValueError('consumer_native_queue_fields')
            key=(ident,number)
            if key in queues and queues[key] != (cost,paid): raise ValueError('consumer_queue_conflict')
            queues[key]=(cost,paid)
    return producers,queues


def runtime_guard(sample, config):
    if primed.sample_frames(sample) is None: return 'incoherent_sample'
    if not common.scenario_matches(sample): return 'scenario_not_verified'
    if sample['match'].get('pause_type_candidate') != 0 or sample['match'].get('pause_flag_candidate') != 0: return 'paused'
    rows=[r for r in sample['dependency'].get('actions',[]) if r.get('action') == config['action']]
    if (len(rows) != 1 or rows[0].get('target_type_hash') != config['target_type_hash']
            or rows[0].get('prerequisite_met') is not True or rows[0].get('native_required_objects_met') is not True
            or rows[0].get('sdk_required_objects_match') is not True): return 'native_prerequisite_not_confirmed'
    return None


def baseline_reason(sample, config, manifest, *, primed_baseline=False):
    consumer=manifest_consumer(manifest,config['action']); reason=runtime_guard(sample,config)
    if reason: return reason
    flags=manifest['flags']; budget_flag=next(c['flag'] for c in manifest['consumers'] if c['action'] == config['budget_action'])
    mask=1 << flags.index(budget_flag) if primed_baseline else 0
    if not common.flag_state(sample.get('flags'),flags,mask): return 'unexpected_macro_gates'
    objects=sample['macro']['construction_feedback']['own_objects']
    if consumer['only_if_target_absent'] and any(r.get('type_hash') == config['target_type_hash'] for r in objects):
        return 'native_only_if_absent_target_already_present'
    producers,queues=queue_rows(sample,config)
    if not producers: return 'exact_producer_not_observed'
    dependency=next(r for r in sample['dependency']['actions'] if r['action'] == config['action'])
    candidates=dependency.get('enqueue_admission_candidates',[])
    eligible={r.get('producer_thing_id') for r in candidates if r.get('producer_type_hash') == config['producer_type_hash']
        and r.get('native_factory_category_match') is True and r.get('native_enqueue_admission_met') is True
        and type(r.get('native_enqueue_admission_return')) is int and r['native_enqueue_admission_return'] == 0
        and r.get('native_stop') is False and r.get('native_unpacking') is False
        and type(r.get('queue_occupied')) is int and r['queue_occupied'] == 0 and r.get('unresolved_admission_conditions') == []}
    life={r['thing_id']:r for r in sample['dependency'].get('own_lifecycles',[])}
    if not producers <= eligible: return 'exact_producer_admission_not_ready'
    if any(life.get(i,{}).get('type_hash') != config['producer_type_hash']
            or life.get(i,{}).get('native_required_object_eligible') is not True
            or life.get(i,{}).get('known_operational_blockers') != [] for i in producers): return 'producer_readiness_not_confirmed'
    if queues: return 'existing_target_queue'
    if any(r['queue_candidate']['nodes'] for r in sample['builder']['builders'] if r['factory']['thing_id'] in producers):
        return 'producer_has_existing_queue'
    if any(r.get('producer_thing_id') in producers for r in sample['builder'].get('jobs',{}).get('construction_jobs',[])):
        return 'producer_has_existing_job'
    return None


def execute_window(backend, config, emit, *, clock=time.monotonic, sleep=time.sleep):
    began=clock(); deadline=began+config['seconds']; active_stop=deadline-20
    result=dict(status='not_qualified',model_calls=0,product_capability_granted=False,prime_applied=False,applied=False,
        clear_acknowledged=False,began_monotonic_ns=int(began*1e9),first_observed_new_queues=[],hard_native_queue_cap=False)
    outstanding=False; last_receipt=None; work=False; manifest=backend.manifest
    consumer=manifest_consumer(manifest,config['action']); flag=consumer['flag']
    budget_flag=next(c['flag'] for c in manifest['consumers'] if c['action'] == config['budget_action'])
    budget_mask=1 << manifest['flags'].index(budget_flag); work_mask=budget_mask | (1 << manifest['flags'].index(flag))
    def take(label,phase):
        sample=backend.sample(label); emit('sample',phase=phase,sample=sample); return sample
    def window(seconds,prime=False):
        opened=clock(); return dict(kind='consumer_budget_prime_window' if prime else 'consumer_fixed_work_window',
            model_calls=0,starts_monotonic_ns=int(opened*1e9),expires_monotonic_ns=int((opened+seconds)*1e9),
            native_duration_frames=max(1,int(seconds*15)),unknown_native_precondition_probe=False)
    try:
        emit('trial_started',config=config)
        if clock()+config['work_seconds']+3 >= active_stop: result['reason']='insufficient_lifecycle_budget'; return result
        for label,phase in (('before_attach','before_attach'),('baseline_attached','baseline_attached')):
            if phase == 'baseline_attached': backend.attach()
            sample=take(label,phase); reason=baseline_reason(sample,config,manifest)
            if reason: result['reason']=reason; return result
        available=min(config['prime_seconds'],active_stop-clock()-config['work_seconds']-2)
        if available < 1: result['reason']='insufficient_prime_budget'; return result
        prime=window(available,True); ident=str(uuid.uuid4())
        emit('budget_prime_prepared',command_id=ident,policy=[config['budget_action']],window=prime)
        outstanding=True; receipt=backend.apply([config['budget_action']],prime['native_duration_frames'],ident); last_receipt=receipt
        primed.receipt_window(receipt,prime['native_duration_frames']); emit('budget_prime_acknowledged',receipt=receipt,window=prime)
        result['prime_applied']=True; frames=set()
        while clock()*1e9 < prime['expires_monotonic_ns'] and clock() < active_stop-config['work_seconds']-2:
            sample=take('budget_prime','prime'); reason=runtime_guard(sample,config)
            if reason: result['reason']=reason; return result
            if primed.within(sample,receipt,prime,budget_mask,manifest) and budget_adopted(sample,budget_flag,config['budget_action']):
                frames.add(sample['budget']['frame'])
            if len(frames) >= 2: break
            sleep(min(config['interval'],max(0,prime['expires_monotonic_ns']/1e9-clock())))
        if len(frames) < 2: result['reason']='budget_prime_not_observed_twice'; return result
        sample=take('fresh_post_prime_baseline','work_baseline'); reason=baseline_reason(sample,config,manifest,primed_baseline=True)
        if reason: result['reason']=reason; return result
        if not primed.within(sample,receipt,prime,budget_mask,manifest) or not budget_adopted(sample,budget_flag,config['budget_action']):
            result['reason']='post_prime_budget_not_current'; return result
        producers,baseline=queue_rows(sample,config)
        baseline_objects=sorted(r['thing_id'] for r in sample['macro']['construction_feedback']['own_objects'] if r['type_hash'] == config['target_type_hash'])
        if clock()+config['work_seconds']+1 >= active_stop: result['reason']='insufficient_work_budget'; return result
        work_window=window(config['work_seconds']); ident=str(uuid.uuid4()); old_seq=receipt['seq']
        emit('intent_prepared',command_id=ident,policy=config['policy'],action=config['action'],target_type_hash=config['target_type_hash'],
            producer_type_hash=config['producer_type_hash'],additional_count=1,queue_observation_trigger_count=1,hard_native_queue_cap=False,
            baseline_queues=[list(k) for k in baseline],baseline_objects=baseline_objects,baseline_producer_ids=sorted(producers),window=work_window)
        work=True; last_receipt=None
        receipt=backend.apply(config['policy'],work_window['native_duration_frames'],ident); last_receipt=receipt
        if receipt.get('seq') != old_seq+1: raise ValueError('consumer_work_sequence')
        primed.receipt_window(receipt,work_window['native_duration_frames']); emit('intent_acknowledged',receipt=receipt,window=work_window)
        result['applied']=True; result['reason']='fixed_work_window_expired'
        while clock()*1e9 < work_window['expires_monotonic_ns'] and clock() < active_stop:
            sample=take('consumer_fixed_work','active'); reason=runtime_guard(sample,config)
            if reason: result['reason']=reason; break
            current_producers,queues=queue_rows(sample,config); first=set(queues)-set(baseline)
            if current_producers != producers: result['reason']='producer_set_changed'; break
            legal=primed.within(sample,receipt,work_window,work_mask,manifest)
            if first:
                result['first_observed_new_queues']=[dict(producer_thing_id=p,production_id=n,native_cost=queues[p,n][0],paid=queues[p,n][1]) for p,n in sorted(first)]
                result['reason']='first_matching_native_queue_observed' if legal and budget_adopted(sample,budget_flag,config['budget_action']) else 'queue_without_current_budget_or_window_proof'
                break
            sleep(min(config['interval'],max(0,work_window['expires_monotonic_ns']/1e9-clock())))
        clear=backend.apply([],1,str(uuid.uuid4())); outstanding=False
        emit('intent_cleared',receipt=clear,original_seq=receipt['seq'],reason=result['reason']); result['clear_acknowledged']=True
        take('after_clear','after_clear'); return result
    except BaseException as error:
        result.update(reason='trial_fault',fault=type(error).__name__+': '+str(error)); emit('trial_fault',reason=result['fault']); return result
    finally:
        if outstanding:
            try:
                clear=backend.apply([],1,str(uuid.uuid4())); outstanding=False
                emit('intent_cleared' if work else 'budget_prime_cleared',receipt=clear,
                    original_seq=last_receipt['seq'] if last_receipt else None,reason='finally_cleanup')
                result['clear_acknowledged']=True
            except BaseException as error: emit('clear_unknown',reason=type(error).__name__+': '+str(error))
        try: backend.close()
        except BaseException as error: emit('close_unknown',reason=type(error).__name__+': '+str(error))
        result.update(ended_monotonic_ns=int(clock()*1e9),lifetime_within_limit=clock() <= deadline); emit('trial_finished',result=result)


def freeze_sources(output,session,build):
    manifest,records=primed.freeze_sources(output,session,build)
    for path in (Path(__file__),Path(__file__).with_name('assess_macro_consumer_primed_field.py'),Path(__file__).with_name('test_macro_consumer_primed_field.py')):
        dest=output/'source'/(str(len(records))+'-'+path.name); shutil.copy2(path,dest); digest=base.sha(dest)
        if base.sha(path) != digest: raise ValueError('consumer_source_changed')
        records.append(dict(path=str(path.resolve()),copy=str(dest.relative_to(output)),sha256=digest))
    return manifest,records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','output'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--action',choices=sorted(SPECS),required=True)
    for key,default in (('seconds',60),('prime-seconds',12),('work-seconds',8),('interval',.25)):
        parser.add_argument('--'+key,type=float,default=default)
    a=parser.parse_args(); config=options(a.action,a.seconds,a.prime_seconds,a.work_seconds,a.interval)
    output=a.output.resolve(); session=a.session.resolve(); build=a.build.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports'): raise ValueError('fresh_consumer_research_output_required')
    output.mkdir(parents=True); manifest,sources=freeze_sources(output,session,build); manifest_consumer(manifest,a.action); binding=base.load(session)
    pre=dict(kind='fixed_consumer_primed_field_preflight',schema_version=1,protocol_version=2,config=config,manifest=manifest,sources=sources,
        session=binding,session_path=str(session),session_sha256=base.sha(session),build_path=str(build),
        build_manifest_sha256=base.sha(build/'build-manifest.json'),model_calls=0,unit_orders=0,enemy_details_read=False,
        product_capability_granted=False,sampling_scope=dict(domain='coherent_construction',maximum_component_frame_span=15,dynamic_data_cached=False))
    (output/'driver-preflight.json').write_text(json.dumps(pre,indent=2),encoding='utf8')
    backend=None; result={}; started=time.monotonic_ns()
    with (output/'consumer-trial.jsonl').open('x',encoding='utf8') as stream:
        def emit(kind,**facts):
            stream.write(json.dumps(dict(kind=kind,monotonic_ns=time.monotonic_ns(),**facts),allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
        try:
            backend=primed.LiveBackend(session,build,output,config,sources,emit)
            remaining=config['seconds']-(time.monotonic_ns()-started)/1e9
            result=execute_window(backend,dict(config,seconds=max(.001,remaining)),emit)
        except BaseException as error: emit('initialization_failed',reason=type(error).__name__+': '+str(error)); result=dict(reason='initialization_failed')
        finally:
            if backend and not backend.closed:
                try: backend.close()
                except BaseException as error: emit('close_unknown',reason=type(error).__name__+': '+str(error))
    result.update(model_calls=0,unit_orders=0,enemy_details_read=False,live_lifecycle_began_monotonic_ns=started,
        live_lifecycle_ended_monotonic_ns=time.monotonic_ns(),source_archives_unchanged=base.unchanged(sources,output),
        source_originals_unchanged=base.unchanged(sources),memory_closed=bool(backend is None or backend.memory is None and (backend.transport is None or backend.transport.memory is None)))
    (output/'driver-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(output),reason=result.get('reason'),model_calls=0,capability_granted=False)))


if __name__ == '__main__': main()
