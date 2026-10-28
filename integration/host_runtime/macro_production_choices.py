"""Qualify additional production choices from bounded native field records."""
from dataclasses import replace
from pathlib import Path

from .contracts import ContractError
from .macro_policy_runtime import load,sha,trial
from .macro_production_feedback import ProductionFeedback,TARGETS
from .macro_production_runtime import ProductionPreferenceScope,prerequisites_present

REVIEWED_DRIVER='07f18b7fbeab944189f745dbc53b63334a309733812da629d3152c421216b441'


def extend_production_scope(scope,directories):
    if not isinstance(scope,ProductionPreferenceScope) or not directories or len(directories)>9:
        raise ContractError('macro_production_choice_scope_required')
    counts={action:set(values) for action,values in scope.production_counts.items()}
    flags=scope.production_flags;evidence=dict(scope.evidence);seen=set()
    for directory in directories:
        folder=Path(directory).resolve();driver=load(folder/'driver-preflight.json')
        action=driver.get('policy',[None])[0];number=driver.get('additional_count')
        if (action not in TARGETS or type(number) is not int or not 1<=number<=3
                or driver.get('policy')!=[action,'budgetarmy'] or driver.get('target')!=TARGETS[action][0]
                or driver.get('model_calls')!=0 or driver.get('driver_sha256')!=REVIEWED_DRIVER
                or sha(folder/'count-driver.py')!=REVIEWED_DRIVER or (action,number) in seen):
            raise ContractError('macro_production_choice_driver')
        seen.add((action,number))
        for source in driver['sources']:
            path=(folder/'driver-source'/source['copy']).resolve()
            if path.parent!=(folder/'driver-source').resolve() or sha(path)!=source['sha256']:
                raise ContractError('macro_production_choice_source')
            evidence[str(path)]=sha(path)
        pre,final,manifest,rows,pins=trial(folder/'transport')
        if (manifest['package_sha256']!=scope.package_sha256 or manifest['sources']!=scope.budget.native_sources
                or tuple(manifest['flags'])!=scope.budget.flags):raise ContractError('macro_production_choice_transport')
        flag=next(r['flag'] for r in manifest['consumers'] if r['action']==action)
        mask=sum(1<<manifest['flags'].index(name) for name in (flag,scope.budget.action_flags['budgetarmy']))
        acks=[r for r in rows if r['kind']=='command_acknowledged']
        if len(acks)!=3 or [r['native']['applied_mask'] for r in acks]!=[mask,0,0]:
            raise ContractError('macro_production_choice_gate_sequence')
        census=None;tracker=None;positive=[];target_frame=None;release=False
        for row in rows:
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']=='native_builder_observation' and 'observation' in row and census:
                builder=row['observation']
                if tracker is None:
                    tracker=ProductionFeedback(action,number,builder,census)
                    if tracker.baseline_queues or len(tracker.eligible)!=1 or not prerequisites_present(action,census):
                        raise ContractError('macro_production_choice_initial_scope')
                else:tracker.observe(builder,census)
                if not release and len(tracker.eligible)!=1:raise ContractError('macro_production_choice_producer_scope')
                if (not release and acks[0]['native']['last_frame']<=builder['frame']<acks[1]['native']['last_frame']
                        and any(e['flag']==flag and e['state_score']>0 and any(item['build_type_hash_raw']==TARGETS[action][0]
                            for item in e['entries']) for e in builder['macro_entries'])):positive.append(builder['frame'])
                if len(tracker.new_queues)>=number and target_frame is None:target_frame=builder['frame']
            if row is acks[1]:
                if (tracker is None or len(tracker.new_queues)!=number or target_frame is None
                        or not target_frame<=row['native']['last_frame']<=target_frame+15
                        or row['native']['last_frame']>acks[0]['native']['deadline_frame']):
                    raise ContractError('macro_production_choice_release')
                tracker.mark_policy_released('queue_target_observed');release=True
        if (not positive or target_frame is None or not release or len(tracker.new_queues)!=number
                or tracker.public()['queue_target_overshot']):raise ContractError('macro_production_choice_effect')
        counts.setdefault(action,set()).add(number);flags[action]=flag;evidence.update(pins)
        for path in (folder/'driver-preflight.json',folder/'count-driver.py'):evidence[str(path)]=sha(path)
    extras=tuple((action,tuple(sorted(values)),flags[action]) for action,values in sorted(counts.items()) if action!='produceflak')
    return replace(scope,available_counts=tuple(sorted(counts['produceflak'])),extra_choices=extras,evidence=evidence)
