"""Trusted fixed-field qualification for three original-native group roles."""
from dataclasses import dataclass,fields,replace
import math
from pathlib import Path

from .contracts import ContractError
from .macro_policy_runtime import ROOT,load,sha,trial
from .macro_base_defense_scope import BaseDefenseScope,PACKAGE_SHA as BASE_PACKAGE_SHA
from .macro_group_role_contract import ROLE_GOALS,ROLE_FAMILIES,HOME_REGION,group_role_catalog_overrides
from .macro_infrastructure import TEMPLATES

PACKAGE_SHA='bf0bb3105dc9d1124173ff8aa6ccfa15e494ceb550f78e05600092356970c260'
STATIC_SHA='f8add621515cafe258bcad577502a625170135477822ee1a72f6a7d86b13af77'
DRIVER_SHA='3f40ca859513664eeb13895aaf2757a06e2633cfa1c4b7e4e44315b6e1e50165'
PRIOR_PACKAGE_SHA='aec5131537d2852c5ccda55391e85a74a3457256859fc94a924832cacc0da756'
PRIOR_DRIVER_SHA='b91b5ea5d83d78b28562929ff3e5c05016c2fca9fe0ad8d21c1c6af44c98a705'
REVISION_STATIC_SHA='bbe4f0ae723270d7d8edf83ecf75b4b7c4b00e95b4c1b606878d9622e40e02d5'
ALIASES={'regroup':'build_airfield','withdraw':'buildtech','reinforce':'economyrefinery'}
HOME=(4404.11669921875,2016.0247802734375)


@dataclass(frozen=True)
class GroupRoleScope(BaseDefenseScope):
    native_transport_client='client_group_roles.py'
    def regional_family_for(self,action):return ROLE_FAMILIES.get(action) or super().regional_family_for(action)
    def regional_goal_for(self,action):return ROLE_GOALS.get(action) or super().regional_goal_for(action)
    def model_catalog_overrides(self):return group_role_catalog_overrides()
    def public(self):
        value=super().public();value.update(group_roles_granted=sorted(ROLE_GOALS),
            group_role_goals=dict(ROLE_GOALS),unit_operation_policy='native_ai',physical_home_return_guaranteed=False)
        return value


def verify_role_effect(rows,flag,owner,begin,end,action):
    tracks={};inactive=set()
    for row in rows:
        if row['kind']!='macro_observation' or 'observation' not in row:continue
        obs=row['observation'];state=obs['state_scores'][flag]
        tasks=[t for t in obs['runtimes'] if t['group']==state['group'] and t['native_execution_active']]
        if obs['frame']>end and state['score']==0 and not tasks:inactive.add(obs['frame'])
        if not begin<=obs['frame']<end or state['score']<=0:continue
        census=obs['construction_feedback']
        if census.get('enemy_details_read') is not False:raise ContractError('macro_group_role_own_census_required')
        if abs(census['frame']-obs['frame'])>15:continue
        structures=[r for r in census['own_objects'] if r['type_hash'] in TEMPLATES.values() and r['hp']>0]
        for task in tasks:
            if task.get('native_tactic_family')!=ROLE_FAMILIES[action]:raise ContractError('macro_group_role_native_family')
            for group in task.get('owned_groups',[]):
                if not group.get('found') or not group.get('all_members_resolved'):continue
                for member in group['members']:
                    if member['owner']!=owner:raise ContractError('macro_group_role_foreign_member')
                    point=member['xyz']
                    if len(point)!=3 or any(not math.isfinite(v) for v in point):raise ContractError('macro_group_role_position')
                    near=bool(structures) and min(math.dist(point[:2],r['xyz'][:2]) for r in structures)<=500
                    key=member['thing_id'],member['address'],member['type_hash']
                    tracks.setdefault(key,[]).append((obs['frame'],point,near))
    near_home=0;positive=False
    for track in tracks.values():
        first=track[0][1];displacement=max(math.dist(first,p) for _,p,_ in track)
        progress=max(math.dist(first[:2],HOME)-math.dist(p[:2],HOME) for _,p,_ in track)
        near_frames=[f for f,p,n in track if math.dist(p[:2],HOME)<=500]
        infrastructure_frames=[f for f,p,n in track if n]
        if len(near_frames)>=3 and max(near_frames)-min(near_frames)>=15:near_home+=1
        if action=='withdraw' and len(track)>=2 and math.dist(first[:2],HOME)>750 and displacement>10 and progress>50:positive=True
        if (action=='reinforce' and displacement>10 and len(infrastructure_frames)>=3
                and max(infrastructure_frames)-min(infrastructure_frames)>=15):positive=True
    if action=='regroup':positive=near_home>=2
    if not positive or len(inactive)<2:raise ContractError('macro_group_role_effect_or_release_missing')


def read_group_role_field(directory):
    directory=Path(directory).resolve();driver=load(directory/'driver-preflight.json')
    pre,final,manifest,rows,evidence=trial(directory/'transport')
    variants={
        'fixed_original_native_group_roles_attack_first_trial':(PACKAGE_SHA,DRIVER_SHA,'group-role-attack-first-driver.py',('deployattack','withdraw','reinforce','regroup')),
        'fixed_original_native_group_roles_trial':(PRIOR_PACKAGE_SHA,PRIOR_DRIVER_SHA,'group-role-driver.py',('regroup','deployattack','withdraw','reinforce'))}
    variant=variants.get(driver.get('kind'))
    if variant is None:raise ContractError('macro_group_role_field_binding')
    package_sha,driver_sha,driver_name,expected=variant
    if (driver['driver_sha256']!=driver_sha or sha(directory/driver_name)!=driver_sha
            or any(driver[k]!=final[k] for k in ('session_id','pid','process_creation_filetime'))
            or driver['model_calls']!=0 or driver['unit_orders']!=0 or driver['enemy_live_details_read'] is not False
            or manifest['package_sha256']!=package_sha or [s['action'] for s in driver['steps']]!=list(expected)):
        raise ContractError('macro_group_role_field_binding')
    if [int(v//512) for v in driver['initial_own_construction_yard_xyz'][:2]]!=[8,3]:
        raise ContractError('macro_group_role_eastern_origin_required')
    sources={Path(r['path']).name:r for r in pre['sources']}
    for name in ('client_group_roles.py','macro_group_role_observation.py','verify_group_role_observer.py'):
        row=sources.get(name);current=ROOT/('native-ai/macro-policy-runtime/'+name if name.startswith('client_') else 'native-ai/'+name)
        if row is None or sha(current)!=row['sha256']:raise ContractError('macro_group_role_reader_changed')
    consumers={r['action']:r for r in manifest['consumers']}
    acks=[r for r in rows if r['kind']=='command_acknowledged']
    masks=[1<<manifest['flags'].index(consumers[a]['flag']) for a in expected]
    if len(acks)!=9 or [r['native']['applied_mask'] for r in acks]!=[masks[0],0,masks[1],0,masks[2],0,masks[3],0,0]:
        raise ContractError('macro_group_role_field_sequence')
    prefix='/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_'
    qualified=set()
    for index,action in enumerate(expected):
        if action not in ROLE_GOALS:continue
        consumer=consumers[action]
        if (consumer['goal']!=ROLE_GOALS[action] or consumer['flag']!=prefix+ALIASES[action]
                or consumer['native_tactic']!=('ReactiveDefense' if action=='reinforce' else 'SimpleAttack')
                or consumer['native_micro_manager']!=('ReactiveDefenseMicroManager' if action=='reinforce' else 'GrowingAttacksMicroManager_MEDIUM')):
            raise ContractError('macro_group_role_consumer_binding')
        ack,release=acks[index*2:index*2+2];begin=ack['native']['last_frame'];deadline=ack['native']['deadline_frame']
        if not 0<deadline-begin<=900:raise ContractError('macro_group_role_duration')
        try:verify_role_effect(rows,consumer['flag'],pre['native']['player'],begin,min(deadline,release['native']['last_frame']),action)
        except ContractError as error:
            if error.code!='macro_group_role_effect_or_release_missing':raise
        else:
            # The old withdrawal consumer changed and cannot qualify the new
            # recruitment policy, even if an older field ever showed movement.
            if package_sha==PACKAGE_SHA or action!='withdraw':qualified.add(action)
    for name in ('driver-preflight.json',driver_name):evidence[str(directory/name)]=sha(directory/name)
    return manifest,evidence,qualified


def verify_group_role_field(directory):
    manifest,evidence,qualified=read_group_role_field(directory)
    if qualified!=set(ROLE_GOALS):raise ContractError('macro_group_roles_incomplete')
    return manifest,evidence


def verify_group_role_fields(directories,revision_static_directory):
    paths=[Path(p).resolve() for p in directories]
    if not 1<=len(paths)<=3 or len(set(paths))!=len(paths):raise ContractError('macro_group_role_field_set')
    results=[read_group_role_field(p) for p in paths];qualified=set().union(*(r[2] for r in results))
    current=[r for r in results if r[0]['package_sha256']==PACKAGE_SHA]
    if qualified!=set(ROLE_GOALS) or not current:raise ContractError('macro_group_roles_incomplete')
    evidence={p:h for _,items,_ in results for p,h in items.items()}
    if any(r[0]['package_sha256']==PRIOR_PACKAGE_SHA for r in results):
        static=Path(revision_static_directory).resolve();audit=load(static/'audit.json')
        if (sha(static/'audit.json')!=REVISION_STATIC_SHA or sha(static/'auditor.py')!=audit['auditor_sha256']
                or audit['old_package_sha256']!=PRIOR_PACKAGE_SHA or audit['package_sha256']!=PACKAGE_SHA
                or audit['regroup_and_reinforce_consumers_preserved'] is not True):
            raise ContractError('macro_group_role_revision_bridge_required')
        for path,digest in audit['evidence'].items():
            p=Path(path).resolve()
            if not p.is_relative_to(ROOT) or sha(p)!=digest:raise ContractError('macro_group_role_revision_changed')
        evidence.update(audit['evidence']);evidence.update({str(static/n):sha(static/n) for n in ('audit.json','auditor.py')})
    return current[0][0],evidence


def extend_group_role_scope(base,directories,static_directory,revision_static_directory,build):
    if not isinstance(base,BaseDefenseScope) or base.package_sha256!=BASE_PACKAGE_SHA:
        raise ContractError('macro_group_roles_base_defense_scope_required')
    static=Path(static_directory).resolve();audit=load(static/'audit.json')
    if (sha(static/'audit.json')!=STATIC_SHA or sha(static/'auditor.py')!=audit['auditor_sha256']
            or audit['base_package_sha256']!=BASE_PACKAGE_SHA or audit['package_sha256']!=PACKAGE_SHA
            or audit['qualified_consumers_preserved'] is not True or audit['original_micro_assets_preserved'] is not True):
        raise ContractError('macro_group_role_preservation_required')
    for path,digest in audit['evidence'].items():
        p=Path(path).resolve()
        if not p.is_relative_to(ROOT) or sha(p)!=digest:raise ContractError('macro_group_role_package_changed')
    field,evidence=verify_group_role_fields(directories,revision_static_directory);current=load(Path(build)/'build-manifest.json')
    if (field['sources']!=base.budget.native_sources or tuple(field['flags'])!=base.budget.flags
            or current['sources']!=field['sources'] or current['flags']!=field['flags']
            or current['package_sha256']!=PACKAGE_SHA or current['consumers']!=field['consumers']):
        raise ContractError('macro_group_role_execution_build_mismatch')
    evidence={**base.evidence,**evidence,**audit['evidence'],
        **{str(static/name):sha(static/name) for name in ('audit.json','auditor.py')}}
    budget=replace(base.budget,package_sha256=PACKAGE_SHA,evidence=evidence)
    flags={r['action']:r['flag'] for r in current['consumers']}
    targets=base.regional_targets+tuple((a,HOME_REGION,flags[a],*HOME) for a in ROLE_GOALS)
    return GroupRoleScope(**{f.name:getattr(base,f.name) for f in fields(BaseDefenseScope) if f.name not in ('budget','evidence','regional_targets')},
        budget=budget,evidence=evidence,regional_targets=targets)
