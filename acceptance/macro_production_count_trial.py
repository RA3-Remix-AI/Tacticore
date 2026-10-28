"""Fixed macro production count study, using native AI queues and no unit orders."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from integration.host_runtime.macro_production_feedback import ProductionFeedback,TARGETS

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('session','build','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--owner',type=lambda value:int(value,0),required=True)
    p.add_argument('--action',choices=sorted(TARGETS),default='produceflak')
    p.add_argument('--additional-count',type=int,default=2);a=p.parse_args()
    target=TARGETS[a.action][0]
    if not 1<=a.additional_count<=3:raise ValueError('bounded_native_macro_production_count')
    out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_macro_production_count_output')
    out.mkdir(parents=True);shutil.copy2(Path(__file__),out/'count-driver.py')
    (out/'driver-source').mkdir();driver_sources=[]
    for name in ('macro_production_feedback.py','contracts.py'):
        source=ROOT/'integration/host_runtime'/name;copy=out/'driver-source'/name;shutil.copy2(source,copy)
        driver_sources.append(dict(path=str(source),copy=copy.name,sha256=hashlib.sha256(copy.read_bytes()).hexdigest()))
    with (out/'driver-preflight.json').open('x',encoding='utf8') as stream:
        json.dump(dict(driver_sha256=hashlib.sha256((out/'count-driver.py').read_bytes()).hexdigest(),
            policy=[a.action,'budgetarmy'],target=target,additional_count=a.additional_count,
            sources=driver_sources,model_calls=0,product_capability_granted=False),stream,indent=2)
    spec=importlib.util.spec_from_file_location('macro_count_transport',ROOT/'native-ai/macro-policy-runtime/client.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    transport=None;baseline_ids=set();baseline_queues=set();new_ids=set();new_queues=set();released=False;tracker=None
    try:
        transport=module.MacroPolicyProbe(a.session,a.owner,a.build,out/'transport',build_feedback=True)
        before=transport.observe('before_count_policy')
        if 'observation' not in before or 'build_observation' not in before:raise ValueError('macro_production_baseline_unavailable')
        tracker=ProductionFeedback(a.action,a.additional_count,before['build_observation'],before['observation']['construction_feedback'])
        if len(tracker.eligible)!=1 or tracker.baseline_queues:raise ValueError('empty_target_queue_single_producer_required')
        baseline_ids=set(tracker.baseline_units);baseline_queues=set(tracker.baseline_queues)
        transport.event('macro_count_baseline',action=a.action,target_type_hash=target,own_count=len(baseline_ids),
            existing_queues=[list(pair) for pair in sorted(baseline_queues)],additional_count=a.additional_count)
        transport.apply([a.action,'budgetarmy'],900)
        began=time.monotonic();after_release=None
        while time.monotonic()-began<65:
            value=transport.observe('count_policy_released' if released else 'count_policy_held')
            if 'build_observation' in value and 'observation' in value:
                feedback=tracker.observe(value['build_observation'],value['observation']['construction_feedback'])
                new_queues=set(tracker.new_queues);new_ids=set(tracker.new_units)
                transport.event('macro_production_public_feedback',feedback=feedback)
            if not released and (tracker.release_required or len(tracker.eligible)!=1 or time.monotonic()-began>=40):
                transport.apply([],1);released=True;after_release=time.monotonic()
                tracker.mark_policy_released('queue_target_observed' if len(tracker.new_queues)>=a.additional_count
                    else 'producer_unavailable' if tracker.release_required else 'scope_changed' if len(tracker.eligible)!=1 else 'expired')
                transport.event('macro_count_policy_released',new_matching_queues=[list(pair) for pair in sorted(new_queues)],
                    new_own_objects=sorted(new_ids),count_target=a.additional_count,
                    target_observed=len(new_queues)>=a.additional_count,overshoot=len(new_queues)>a.additional_count)
            if released and time.monotonic()-after_release>=20:break
            time.sleep(.25)
    finally:
        if transport:transport.close()
    final=json.loads((out/'transport/final-state.json').read_text())
    result=dict(kind='native_macro_production_count_study',session_id=final['session_id'],action=a.action,target_type_hash=target,
        baseline_own_count=len(baseline_ids),additional_count_requested=a.additional_count,
        observed_new_matching_queues=[list(pair) for pair in sorted(new_queues)],observed_new_own_objects=sorted(new_ids),
        queue_target_observed=len(new_queues)>=a.additional_count,queue_target_overshot=len(new_queues)>a.additional_count,
        native_policy_released=released,cleanup_verified=final['cleanup_verified'],
        public_feedback=tracker.public() if tracker else None,
        model_calls=0,exclusive_model_attribution_verified=False,product_capability_granted=False,formal_goal_complete=False)
    with (out/'count-review.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))
