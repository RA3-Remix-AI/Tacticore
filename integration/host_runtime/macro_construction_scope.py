"""Replay reviewed early-reactor field evidence before granting one build preference."""
from dataclasses import replace
from pathlib import Path

from .contracts import ContractError
from .macro_policy_runtime import load,sha,trial
from .macro_production_runtime import ProductionPreferenceScope
from .macro_construction_feedback import ConstructionFeedback,TARGET,ACTION

DRIVER='28c19430361994a9249f75d0f1a7352cd778f29e0c7cecdc5ba68bc63bc031a2'


def extend_construction_scope(scope,directory):
    if not isinstance(scope,ProductionPreferenceScope):raise ContractError('macro_construction_production_scope_required')
    folder=Path(directory).resolve();driver=load(folder/'driver-preflight.json')
    audits=[Path(path) for path,digest in scope.evidence.items() if Path(path).name=='audit.json'
            and digest=='e53731a72b9e1f8cdc6286cbae31d0d16340379e5219e94a1e2948ef3abb048b']
    if len(audits)!=1 or sha(audits[0])!=scope.evidence[str(audits[0])]:raise ContractError('macro_construction_static_audit')
    checks={row['address']:row['bytes'] for row in load(audits[0])['byte_checks']}
    if checks.get('0x8d2c19')!='6807020000' or checks.get('0x8d5ce1')!='e8faceffff':
        raise ContractError('macro_construction_static_consumer')
    if (driver.get('driver_sha256')!=DRIVER or sha(folder/'early-driver.py')!=DRIVER
            or driver.get('policy')!=[ACTION,'budgetarmy'] or driver.get('target_type_hash')!=TARGET
            or driver.get('model_calls')!=0):raise ContractError('macro_construction_field_driver')
    pre,final,manifest,rows,evidence=trial(folder/'transport')
    if (manifest['package_sha256']!=scope.package_sha256 or manifest['sources']!=scope.budget.native_sources
            or tuple(manifest['flags'])!=scope.budget.flags):raise ContractError('macro_construction_transport')
    flag=next(row['flag'] for row in manifest['consumers'] if row['action']==ACTION)
    mask=sum(1<<manifest['flags'].index(name) for name in (flag,scope.budget.action_flags['budgetarmy']))
    acks=[row for row in rows if row['kind']=='command_acknowledged']
    if len(acks)!=3 or [row['native']['applied_mask'] for row in acks]!=[mask,0,0]:
        raise ContractError('macro_construction_gate_sequence')
    census=None;tracker=None;positive=None;queue=None;own=None
    for row in rows:
        if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
        if row['kind']=='native_builder_observation' and 'observation' in row and census:
            builder=row['observation']
            if tracker is None:
                tracker=ConstructionFeedback(builder,census)
                if tracker.baseline_queues or tracker.baseline_objects:raise ContractError('macro_construction_initial_target_present')
            tracker.observe(builder,census,flag)
            if tracker.positive and positive is None:positive=builder['frame']
            if tracker.new_queues and queue is None:queue=builder['frame']
            if tracker.new_objects and own is None:own=census['frame']
        if row is acks[1] and tracker:tracker.mark_policy_released('queue_observed')
    if (tracker is None or positive is None or queue is None or own is None or len(tracker.new_queues)!=1
            or not acks[0]['native']['last_frame']<=positive<=queue<=acks[1]['native']['last_frame']
            or not acks[0]['native']['last_frame']<=own<=acks[1]['native']['last_frame']
            or acks[1]['native']['last_frame']>acks[0]['native']['deadline_frame']):
        raise ContractError('macro_construction_native_sequence')
    for name in ('driver-preflight.json','early-driver.py'):evidence[str(folder/name)]=sha(folder/name)
    return replace(scope,construction_flag=flag,evidence={**scope.evidence,**evidence})
