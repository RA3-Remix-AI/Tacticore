"""Economic-harassment semantics above the independent native mission verifier.

No controller or network. A TrustedHarassRoute is supplied by the trusted host's
pre-dispatch ledger, never inferred from a model response or a renamed receipt.
The native verifier still proves every movement/order/damage/retreat/return link.
"""
from dataclasses import dataclass,asdict
import hashlib,importlib,json,math,uuid
from pathlib import Path

import mission_combat_qualification as native

ECONOMY_TEMPLATES={'0xc45aaeab':'SovietRefinery'}
HERE=Path(__file__).resolve().parent
# Explicit reviewed builds, never a directory inferred from model/raw text.
NATIVE_BUILDS={
    'mission-combat':('TacticalMissionCombat.dll','82b31a8078c89ba6919ec435ce2c32767df1cd594f0bafae7bdc24f85b3c2e6d','mission_combat_qualification','bea306b96ede34097bf5716db59f7f462d8e1f1c30c86fec5df0de829daa3247'),
    'mission-combat-v2':('TacticalMissionCombat2.dll','477c262303b104b68095ae91436bb01f615f08c98a7842d8538036405394dd84','mission_combat_v2_qualification','b2a83aa477fa342a3cc8e73ec1b90cc2c0a551802c4478698121ff9d570bf7f8'),
    'mission-combat-v3':('TacticalMissionCombat3.dll','8b6cf5c7a60a281e82817c7d78dd2264b781436e54640aecdfdbb868415d2468','mission_combat_v3_qualification','e2248a02f0afab955942ca89d14384c695c2f87c53d53263b9aa5559cce4c305'),
}


@dataclass(frozen=True)
class TrustedHarassRoute:
    session_id:str
    pid:int
    player_id:int
    commander_id:str
    mission_id:str
    command_id:str
    actor_id:int
    target_contact_id:str
    target_object_id:int
    target_type_hash:str
    target_role:str
    dispatch_frame:int
    deadline_frame:int
    retreat_region:str
    retreat_source:str
    retreat_xyz:tuple[float,float,float]
    module:str='raid'
    purpose:str='harass_economy'
    executor_directory:str='mission-combat'


def canonical(value):
    try:return isinstance(value,str) and str(uuid.UUID(value))==value
    except (ValueError,AttributeError):return False


def same_uuid(value,expected):
    try:return isinstance(value,str) and uuid.UUID(value)==uuid.UUID(expected)
    except (ValueError,AttributeError):return False


def native_backend(report,route):
    if not isinstance(route.executor_directory,str):return None
    spec=NATIVE_BUILDS.get(route.executor_directory)
    if spec is None:return None
    dll,digest,module_name,qualifier_digest=spec
    if report.get('native_binary_sha256')!=digest:return None
    if report.get('executor_directory',route.executor_directory)!=route.executor_directory:return None
    path=HERE/route.executor_directory/'bin'/dll;qualifier=HERE/(module_name+'.py')
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest or hashlib.sha256(qualifier.read_bytes()).hexdigest()!=qualifier_digest:return None
        backend=native if module_name=='mission_combat_qualification' else importlib.import_module(module_name)
        if Path(backend.__file__).resolve()!=qualifier.resolve():return None
    except (OSError,ImportError,AttributeError):return None
    return backend


def qualify(report,route,receipt=None):
    if not isinstance(route,TrustedHarassRoute):raise ValueError('trusted_harass_route_required')
    q=report.get('request',{});n=report.get('native',{});pre=report.get('preflight',{});target=report.get('private_target',{});mission=q.get('mission',{})
    canonical_route=all(canonical(getattr(route,k)) for k in ('session_id','commander_id','mission_id','command_id'))
    scalar_route=all(type(getattr(route,k)) is int and getattr(route,k)>0 for k in ('pid','player_id','actor_id','target_object_id','dispatch_frame','deadline_frame'))
    point=isinstance(route.retreat_xyz,tuple) and len(route.retreat_xyz)==3 and all(type(v) in (float,int) and math.isfinite(v) for v in route.retreat_xyz)
    checks={
        'trusted_purpose':route.module=='raid' and route.purpose=='harass_economy',
        'route_shape':canonical_route and scalar_route and route.player_id==3 and point and isinstance(route.target_contact_id,str) and route.target_contact_id.startswith('contact_') and route.retreat_region=='home_base' and route.retreat_source in {'own_home_base','own_actor_history'},
        'same_host_binding':report.get('session_id')==pre.get('session_id')==n.get('session_id')==route.session_id and pre.get('pid')==route.pid and pre.get('player_id')==route.player_id and pre.get('commander_id')==n.get('commander_id')==route.commander_id,
        'exact_economic_target':route.target_role==q.get('target_role')=='economy' and route.target_type_hash in ECONOMY_TEMPLATES and target.get('type_hash')==route.target_type_hash and q.get('target_object_id')==target.get('object_id')==route.target_object_id and q.get('target_contact_id')==route.target_contact_id and target.get('owner_player_id') not in {None,route.player_id},
        'allocated_actor':pre.get('selected',{}).get('object_id')==route.actor_id and pre.get('selected',{}).get('type_hash')=='0x19ab11af',
        'continuous_protocol':q.get('mission_protocol')=='continuous_tactical_v1',
        'frozen_deadline':mission.get('expires_frame')==q.get('expires_frame')==n.get('mission_deadline_frame')==route.deadline_frame and route.dispatch_frame<=n.get('issued_frame',0)<n.get('returned_frame',0)<=route.deadline_frame and 300<=route.deadline_frame-route.dispatch_frame<=4500,
    }
    checks['child_command_and_task']=bool(canonical_route and n.get('command_id')==q.get('command_id')==str(uuid.uuid5(uuid.UUID(route.command_id),str(route.actor_id))) and n.get('task_id')==q.get('task_id')==str(uuid.uuid5(uuid.UUID(route.mission_id),str(route.actor_id))) and type(q.get('seq')) is int and q['seq']>0 and q['seq']==n.get('seq'))
    retreat=mission.get('retreat_point',{})
    checks['frozen_trusted_retreat']=point and retreat.get('source')==route.retreat_source and retreat.get('xyz')==list(route.retreat_xyz) and n.get('retreat_goal')==list(route.retreat_xyz)
    backend=native_backend(report,route)
    checks['native_version_route']=backend is not None
    try:base=backend.qualify(report) if backend else {'status':'not_passed','checks':{},'effect_verified':False,'source_damage_amount':0}
    except (ValueError,KeyError,TypeError,OverflowError,IndexError):base={'status':'not_passed','checks':{},'effect_verified':False,'source_damage_amount':0}
    checks['native_entire_chain']=base.get('status')=='continuous_ak_combat_mission_verified' and bool(base.get('checks')) and all(v is True for v in base['checks'].values())
    checks['actual_economy_effect']=base.get('effect_verified') is True and base.get('harass_economy_verified') is True and type(base.get('source_damage_amount')) in (float,int) and math.isfinite(base['source_damage_amount']) and base['source_damage_amount']>0
    checks['approach_retreat_restoration']=all(base.get(k) is True for k in ('approach_verified','retreat_verified','restoration_verified'))
    effect=all(v is True for v in checks.values())
    formal=None
    if receipt is not None:
        formal=isinstance(receipt,dict) and same_uuid(receipt.get('task_id'),route.mission_id) and all(receipt.get(k)==value for k,value in [('module','raid'),('purpose','harass_economy'),('session_id',route.session_id),('commander_id',route.commander_id),('player_id',route.player_id),('command_id',route.command_id),('status','completed'),('completed',True),('goal_observed',True),('restoration_verified',True),('object_ids',[route.actor_id]),('target_contact_id',route.target_contact_id)]) and all(type(receipt.get(k)) is bool for k in ('completed','goal_observed','restoration_verified'))
        formal=bool(formal and effect)
    raw_route=json.dumps(asdict(route),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return dict(status='continuous_economic_harassment_verified' if effect else 'not_passed',checks=checks,harass_economy_verified=effect,formal_harass_verified=formal,source_damage_amount=base.get('source_damage_amount',0) if effect else 0,native_assessment=base,native_executor_directory=route.executor_directory,native_qualifier_sha256=NATIVE_BUILDS[route.executor_directory][3] if backend else None,trusted_route_sha256=hashlib.sha256(raw_route).hexdigest(),scope='exact_economy_target_continuous_approach_source_damage_retreat_return',main_attack_label_is_not_harassment_evidence=True)


def qualify_path(path,route,receipt=None):
    path=Path(path).resolve();raw=path.read_bytes();result=qualify(json.loads(raw.decode('utf-8-sig')),route,receipt)
    result.update(source_report=str(path),source_sha256=hashlib.sha256(raw).hexdigest(),semantic_qualifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    return result
