"""Separate fixed refinery research: bounded budget prime, fresh work baseline.

Never run on import. Only main creates the explicit live backend. Model calls,
unit orders, arbitrary native calls and product grants remain absent.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from acceptance import macro_expansion_field_trial as construction
from acceptance import assess_macro_expansion_field as common
ACCOUNTS=('investment','special_operations','production','defense','technology','slush_fund')
ECONOMY=dict(zip(ACCOUNTS,(.4,0,.25,.1,.15,.1)))

def options(seconds=60,prime_seconds=12,interval=.25,allow=False):
    construction.options('buildrefinery',seconds,interval,allow,True)
    if (type(prime_seconds) not in (float,int) or not math.isfinite(prime_seconds) or not 1<=prime_seconds<=15
            or not 35<=seconds<=60 or allow is not True):raise ValueError('primed_research_bounds')
    return dict(action='buildrefinery',target_type_hash='0xc45aaeab',seconds=float(seconds),prime_seconds=float(prime_seconds),
        interval=float(interval),policy=['buildrefinery','budgeteconomy'],allow_unknown_native_precondition=True,
        work_seconds=4.,model_calls=0,product_capability_granted=False)

def sample_frames(sample):
    frames=common.sample_frames(sample)
    if frames is None:return None
    try:
        value=sample['budget'];first,last=value['frame'],value['frame_after'];timing=sample['component_timings']['budget']
        if (value.get('source')!='native_macro_budget_domain_read_only' or value.get('own_perspective') is not True
                or value.get('enemy_details_read') is not False or value.get('native_calls')!=0 or value.get('process_writes')!=0
                or value.get('strategic_runtime_sample_included') is not False or value.get('native')!=sample['macro']['native']
                or type(first) is not int or type(last) is not int or not 0<first<=last<=first+2
                or type(timing.get('started_monotonic_ns')) is not int or type(timing.get('ended_monotonic_ns')) is not int
                or not sample['started_monotonic_ns']<=timing['started_monotonic_ns']<=timing['ended_monotonic_ns']<=sample['ended_monotonic_ns']
                or timing.get('duration_ns')!=timing['ended_monotonic_ns']-timing['started_monotonic_ns'] or timing.get('read_error') is not None):return None
        frames=frames+[first,last]
        return frames if max(frames)-min(frames)<=15 else None
    except (KeyError,TypeError):return None

def budget_adopted(sample,flag):
    if sample_frames(sample) is None:return False
    value=sample['budget'];feedback=value.get('budget_feedback',{});shares=feedback.get('account_shares');row=value.get('state_scores',{}).get(flag,{})
    try:definition_bound=int(row['definition'],0)+0xc==int(feedback['selected_budget_key'],0)
    except (KeyError,TypeError,ValueError):return False
    return (definition_bound and feedback.get('selected_macro_flag')==flag and feedback.get('native_percentages_observed') is True
        and type(shares) is dict and set(shares)==set(ECONOMY)
        and all(type(shares[k]) in (int,float) and math.isfinite(shares[k]) and abs(shares[k]-v)<=1e-5 for k,v in ECONOMY.items())
        and row.get('domain')=='budget' and row.get('dirty') is False and type(row.get('score')) in (int,float)
        and math.isfinite(row['score']) and row['score']>0)

def precondition(sample,config,manifest,*,primed=False):
    """Validate the allowed budget-only gate directly, without editing facts."""
    if sample_frames(sample) is None or not common.scenario_matches(sample):return False
    mask=1<<manifest['flags'].index(next(c['flag'] for c in manifest['consumers'] if c['action']=='budgeteconomy')) if primed else 0
    if not common.flag_state(sample.get('flags'),manifest['flags'],mask):return False
    if construction.held_guard(sample,config) is not None:return False
    actions=[r for r in sample['dependency'].get('actions',[]) if r.get('action')=='buildrefinery']
    if len(actions)!=1 or actions[0].get('sdk_required_objects_match') is not True or actions[0].get('native_required_objects_met') is not True:return False
    admissions=actions[0].get('enqueue_admission_candidates',[])
    if not any(r.get('native_enqueue_admission_met') is True and type(r.get('queue_occupied')) is int and r['queue_occupied']==0
            and r.get('native_factory_category_match') is True and r.get('native_stop') is False and r.get('native_unpacking') is False for r in admissions):return False
    producers,queues=construction.queue_pairs(sample,config['target_type_hash'])
    if len(producers)!=1 or queues:return False
    if any(row.get('producer_thing_id') in producers for row in sample['builder'].get('jobs',{}).get('construction_jobs',[])):return False
    # Any existing conyard queue means the producer is busy, even if it is a
    # different building. Never force a second construction preference.
    return all(not row['queue_candidate']['nodes'] for row in sample['builder']['builders']
        if row.get('factory',{}).get('thing_id') in producers)

def receipt_window(receipt,duration):
    if type(receipt) is not dict or receipt.get('native_gate_acknowledged') is not True:raise ValueError('primed_ack_required')
    native=receipt.get('native',{});seq=receipt.get('seq');end=native.get('deadline_frame')
    if (type(seq) is not int or seq<=0 or type(end) is not int or not 0<end-duration<end
            or native.get('request')!=seq or native.get('ack')!=seq or native.get('error')!=0 or native.get('phase')!=1):
        raise ValueError('primed_native_window')
    return end-duration,end

def within(sample,receipt,window,mask,manifest):
    frames=sample_frames(sample)
    if frames is None:return False
    try:begin,end=receipt_window(receipt,window['native_duration_frames'])
    except ValueError:return False
    native=sample.get('native',{});seq=receipt['seq']
    return (window['starts_monotonic_ns']<=sample['started_monotonic_ns']<=sample['ended_monotonic_ns']<=window['expires_monotonic_ns']
        and all(begin<=f<end for f in frames) and native.get('request')==native.get('ack')==seq
        and native.get('phase')==1 and native.get('error')==0 and native.get('applied_mask')==mask
        and native.get('lease_held')==native.get('self_hook_installed')==1
        and common.flag_state(sample.get('flags'),manifest['flags'],mask))

def execute_window(backend,config,emit,*,clock=time.monotonic,sleep=time.sleep):
    began=clock();deadline=began+config['seconds'];active_stop=deadline-20
    result=dict(status='not_qualified',model_calls=0,product_capability_granted=False,prime_applied=False,applied=False,
        clear_acknowledged=False,began_monotonic_ns=int(began*1e9))
    outstanding=False;last_receipt=None;work=False;manifest=backend.manifest
    budget_flag=next(c['flag'] for c in manifest['consumers'] if c['action']=='budgeteconomy')
    work_flag=next(c['flag'] for c in manifest['consumers'] if c['action']=='buildrefinery')
    budget_mask=1<<manifest['flags'].index(budget_flag);work_mask=budget_mask|(1<<manifest['flags'].index(work_flag))
    def take(label,phase):
        sample=backend.sample(label);emit('sample',phase=phase,sample=sample);return sample
    def window(seconds,prime=False):
        opened=clock();return dict(kind='budget_prime_research_window' if prime else 'fixed_intent_research_window',model_calls=0,starts_monotonic_ns=int(opened*1e9),
            expires_monotonic_ns=int((opened+seconds)*1e9),native_duration_frames=max(1,int(seconds*15)),unknown_native_precondition_probe=not prime)
    try:
        emit('trial_started',config=config)
        if clock()+7>=active_stop:result['reason']='insufficient_lifecycle_budget';return result
        initial=take('before_attach','before_attach')
        if not precondition(initial,config,manifest):result['reason']='initial_precondition_not_supported';return result
        if clock()+7>=active_stop:result['reason']='insufficient_lifecycle_budget';return result
        backend.attach();baseline=take('baseline_attached','baseline_attached')
        if not precondition(baseline,config,manifest):result['reason']='attached_precondition_not_supported';return result
        available=min(config['prime_seconds'],active_stop-clock()-6)
        if available<1:result['reason']='insufficient_prime_budget';return result
        prime=window(available,True);ident=str(uuid.uuid4());emit('budget_prime_prepared',command_id=ident,policy=['budgeteconomy'],window=prime)
        outstanding=True;receipt=backend.apply(['budgeteconomy'],prime['native_duration_frames'],ident);last_receipt=receipt
        receipt_window(receipt,prime['native_duration_frames']);emit('budget_prime_acknowledged',receipt=receipt,window=prime)
        result['prime_applied']=True;frames=set()
        while clock()*1e9<prime['expires_monotonic_ns'] and clock()<active_stop-6:
            sample=take('budget_prime','prime')
            if sample_frames(sample) is None or construction.held_guard(sample,config):result['reason']='prime_sample_or_precondition_failed';return result
            if within(sample,receipt,prime,budget_mask,manifest) and budget_adopted(sample,budget_flag):frames.add(sample['budget']['frame'])
            if len(frames)>=2:break
            sleep(min(config['interval'],max(0,prime['expires_monotonic_ns']/1e9-clock())))
        if len(frames)<2:result['reason']='budget_prime_not_observed_twice';return result
        sample=take('fresh_post_prime_baseline','work_baseline')
        if not (within(sample,receipt,prime,budget_mask,manifest) and budget_adopted(sample,budget_flag)
                and precondition(sample,config,manifest,primed=True)):
            result['reason']='post_prime_baseline_not_ready';return result
        _,baseline_queues=construction.queue_pairs(sample,config['target_type_hash'])
        baseline_objects={r['thing_id'] for r in sample['macro']['construction_feedback']['own_objects'] if r['type_hash']==config['target_type_hash']}
        if clock()+6>=active_stop:result['reason']='insufficient_work_budget';return result
        work_window=window(config['work_seconds']);ident=str(uuid.uuid4())
        emit('intent_prepared',command_id=ident,policy=config['policy'],action='buildrefinery',target_type_hash=config['target_type_hash'],
            additional_count=1,window=work_window,baseline_queues=[list(k) for k in baseline_queues],baseline_objects=sorted(baseline_objects))
        work=True;prime_seq=receipt['seq'];last_receipt=None
        receipt=backend.apply(config['policy'],work_window['native_duration_frames'],ident);last_receipt=receipt
        if receipt.get('seq')!=prime_seq+1:raise ValueError('primed_work_sequence')
        receipt_window(receipt,work_window['native_duration_frames']);emit('intent_acknowledged',receipt=receipt,window=work_window)
        result['applied']=True;positive=False;result['reason']='fixed_work_window_expired'
        while clock()*1e9<work_window['expires_monotonic_ns'] and clock()<active_stop:
            sample=take('primed_fixed_work','active')
            if sample_frames(sample) is None or construction.held_guard(sample,config):result['reason']='work_sample_or_precondition_failed';break
            legal=within(sample,receipt,work_window,work_mask,manifest);budget=legal and budget_adopted(sample,budget_flag)
            _,queues=construction.queue_pairs(sample,config['target_type_hash'])
            if queues-baseline_queues:
                result['reason']='first_matching_native_queue_observed' if budget else 'queue_without_current_budget_proof';break
            if budget:positive |= construction.positive_score(sample,work_flag,config['target_type_hash'])
            if clock()-work_window['starts_monotonic_ns']/1e9>=3 and not positive:result['reason']='no_positive_native_score';break
            sleep(min(config['interval'],max(0,work_window['expires_monotonic_ns']/1e9-clock())))
        clear=backend.apply([],1,str(uuid.uuid4()));outstanding=False
        emit('intent_cleared',receipt=clear,original_seq=receipt['seq'],reason=result['reason'])
        result['clear_acknowledged']=True
        take('after_clear','after_clear');return result
    except BaseException as error:
        result.update(reason='trial_fault',fault=type(error).__name__+': '+str(error));emit('trial_fault',reason=result['fault']);return result
    finally:
        if outstanding:
            try:
                clear=backend.apply([],1,str(uuid.uuid4()));outstanding=False
                emit('intent_cleared' if work else 'budget_prime_cleared',receipt=clear,
                    original_seq=last_receipt['seq'] if last_receipt else None,reason='finally_cleanup')
                result['clear_acknowledged']=True
            except BaseException as error:emit('clear_unknown',reason=type(error).__name__+': '+str(error))
        try:backend.close()
        except BaseException as error:emit('close_unknown',reason=type(error).__name__+': '+str(error))
        result.update(ended_monotonic_ns=int(clock()*1e9),lifetime_within_limit=clock()<=deadline)
        emit('trial_finished',result=result)

class LiveBackend(construction.LiveBackend):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        try:
            from macro_budget_observation import BudgetObserver,EXE_SHA256
            flags=[c['flag'] for c in self.manifest['consumers'] if c['action'] in ('budgeteconomy','budgetarmy','budgettech')]
            self.budget=BudgetObserver(self.memory.read,self.owner,self.native,flags,expected_logic=self.logic,
                inspect_identity=lambda:self.runtime.inspect_player(self.memory.read,self.owner),executable_sha256=EXE_SHA256)
        except BaseException:self.close();raise
    def sample(self,label):
        sample=super().sample(label)
        construction.timed_component(sample,'budget',self.budget.sample)
        construction.timed_component(sample,'identity_final',self.identity)
        sample['ended_monotonic_ns']=time.monotonic_ns()
        return sample

def freeze_sources(output,session,build):
    manifest,records=construction.freeze_sources(output,session,build)
    for path in (Path(__file__),Path(__file__).with_name('assess_macro_expansion_primed_field.py'),
            Path(__file__).with_name('test_macro_expansion_primed_field.py'),ROOT/'native-ai/macro_budget_observation.py',ROOT/'native-ai/test_macro_budget_observation.py'):
        dest=output/'source'/(str(len(records))+'-'+path.name);shutil.copy2(path,dest)
        digest=construction.sha(dest)
        if construction.sha(path)!=digest:raise ValueError('primed_source_changed')
        records.append(dict(path=str(path.resolve()),copy=str(dest.relative_to(output)),sha256=digest))
    return manifest,records

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=60);parser.add_argument('--prime-seconds',type=float,default=12)
    parser.add_argument('--interval',type=float,default=.25);parser.add_argument('--allow-unknown-native-precondition',action='store_true')
    args=parser.parse_args();config=options(args.seconds,args.prime_seconds,args.interval,args.allow_unknown_native_precondition)
    output=args.output.resolve();session=args.session.resolve();build=args.build.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports'):raise ValueError('fresh_primed_research_output_required')
    output.mkdir(parents=True);manifest,sources=freeze_sources(output,session,build);binding=construction.load(session)
    pre=dict(kind='primed_macro_expansion_field_preflight',schema_version=1,protocol_version=2,config=config,manifest=manifest,sources=sources,
        session=binding,session_path=str(session),session_sha256=construction.sha(session),build_path=str(build),build_manifest_sha256=construction.sha(build/'build-manifest.json'),
        model_calls=0,unit_orders=0,enemy_details_read=False,product_capability_granted=False,
        scenario_scope=dict(map_id=construction.MAP_ID,required_origin_region=construction.ORIGIN_REGION,region_cell_size=512,public_map_and_own_origin_required=True,enemy_positions_read=False),
        sampling_scope=dict(domain='coherent_construction',maximum_component_frame_span=15,dynamic_data_cached=False,full_macro_preflight_is_diagnostic_only=True))
    (output/'driver-preflight.json').write_text(json.dumps(pre,indent=2),encoding='utf8')
    backend=None;result={};started=time.monotonic_ns()
    with (output/'primed-trial.jsonl').open('x',encoding='utf8') as stream:
        def emit(kind,**facts):
            stream.write(json.dumps(dict(kind=kind,monotonic_ns=time.monotonic_ns(),**facts),allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
        try:
            backend=LiveBackend(session,build,output,config,sources,emit)
            remaining=config['seconds']-(time.monotonic_ns()-started)/1e9
            result=execute_window(backend,dict(config,seconds=max(.001,remaining)),emit)
        except BaseException as error:emit('initialization_failed',reason=type(error).__name__+': '+str(error));result=dict(reason='initialization_failed')
        finally:
            if backend and not backend.closed:
                try:backend.close()
                except BaseException as error:emit('close_unknown',reason=type(error).__name__+': '+str(error))
    result.update(model_calls=0,unit_orders=0,enemy_details_read=False,live_lifecycle_began_monotonic_ns=started,
        live_lifecycle_ended_monotonic_ns=time.monotonic_ns(),source_archives_unchanged=construction.unchanged(sources,output),
        source_originals_unchanged=construction.unchanged(sources),memory_closed=bool(backend is None or backend.memory is None and (backend.transport is None or backend.transport.memory is None)))
    (output/'driver-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(output),reason=result.get('reason'),model_calls=0,capability_granted=False)))

if __name__=='__main__':main()
