"""One qualified native infrastructure-defense task; existing AI does combat."""
from dataclasses import dataclass,fields,replace
import math
from pathlib import Path
import xml.etree.ElementTree as E

from .contracts import ContractError
from .macro_policy_runtime import ROOT,load,sha,trial
from .macro_region_scope import RegionalScope,PACKAGE_SHA as REGIONAL_PACKAGE_SHA
from .macro_infrastructure import TEMPLATES

PACKAGE_SHA='7a78e3cb66f759aa66b0e877fcc7eca725b4469f3091c0932944967eaf9f0828'
STATIC_SHA='d435dd6767a8748a8e96880ca66d9ce4c65c14c14600fa067021f16ff1b4556b'
DRIVER_SHA='104c551c969042c40a91f9250812830c87581c41e7b3dd15117b120702581ee8'
GOAL='original_native_defense_of_own_infrastructure'


def defense_catalog_override():
    return dict(deploydefense=dict(domain='deployment',exclusive_with_other_construction_or_production=True,
        target_region='region_8_3',goal=GOAL,target_policy='original_native_friendly_land_structure',
        region_semantics='eastern_home_base_anchor_not_a_specific_structure_or_move_destination',
        maximum_duration_seconds=60,native_ai_selects_structure_and_operates_group=True,
        legacy_action_name_is_not_mission_purpose=False,arrival_and_mission_success_guaranteed=False))


@dataclass(frozen=True)
class BaseDefenseScope(RegionalScope):
    def regional_family_for(self,action):return 'static_defense' if action=='deploydefense' else 'simple_attack'
    def regional_goal_for(self,action):return GOAL if action=='deploydefense' else 'native_combat_group_to_fixed_public_waypoint'

    @property
    def required_origin_region(self):return 'region_8_3'

    def model_catalog_overrides(self):
        return defense_catalog_override()

    def public(self):
        result=super().public()
        result.update(regional_goal='verified_waypoint_and_own_infrastructure_tasks',
            regional_goal_by_action={a:self.regional_goal_for(a) for a in self.regional_action_regions},
            base_defense_granted=True,base_defense_anchor='region_8_3',
            base_defense_goal=GOAL,base_defense_target_policy='original_native_friendly_land_structure',
            complete_attack_defense_or_retreat_mission_guaranteed=False)
        return result


def verify_base_defense_field(directory):
    directory=Path(directory).resolve();driver=load(directory/'driver-preflight.json')
    pre,final,manifest,rows,evidence=trial(directory/'transport')
    sources={Path(r['path']).name:r for r in pre['sources']}
    if (driver.get('kind')!='fixed_native_own_base_defense_then_public_attack_trial'
            or driver.get('driver_sha256')!=DRIVER_SHA or sha(directory/'base-defense-driver.py')!=DRIVER_SHA
            or sha(directory/'inspect_area_defense_runtime_candidates.py')!=driver.get('diagnostic_sha256')
            or driver.get('session_id')!=final['session_id'] or driver.get('pid')!=final['pid']
            or driver.get('process_creation_filetime')!=final['process_creation_filetime']
            or driver.get('model_calls')!=0 or driver.get('unit_orders')!=0 or driver.get('enemy_live_details_read') is not False
            or manifest['package_sha256']!=PACKAGE_SHA
            or any(name not in sources or sources[name]['sha256']!=sha(ROOT/'native-ai'/name) for name in
                ('macro_observation.py','macro_area_defense_observation.py','verify_area_defense_observer.py'))
            or sources.get('client_area_defense.py',{}).get('sha256')!=sha(ROOT/'native-ai/macro-policy-runtime/client_area_defense.py')):
        raise ContractError('macro_base_defense_field_binding')
    consumer=next(r for r in manifest['consumers'] if r['action']=='deploydefense')
    if (consumer.get('target_policy')!='original_native_friendly_land_structure'
            or consumer.get('native_tactic')!='StaticDefense' or consumer.get('native_micro_manager')!='DefenseMicroManager'
            or consumer.get('native_target_heuristic')!='FriendlyLandStructureHeuristic'):
        raise ContractError('macro_base_defense_consumer_required')
    report=next(Path(r['path']) for r in pre['sources'] if Path(r['path']).name=='build-report.json')
    root=E.parse(report.parent/'MacroProbe.xml').getroot();ns={'s':'uri:ea.com:eala:asset'}
    state=root.find("s:AIStrategicStateDefinition[@id='"+consumer['state'].split(':',1)[1]+"']",ns)
    if (state is None or state.find('s:TargetHeuristic',ns).get('TargetHeuristic')!='FriendlyLandStructureHeuristic'
            or state.find('s:Tactic',ns).get('Tactic')!='StaticDefense'
            or state.find('s:Tactic/s:TeamTemplate',ns).get('MicroManager')!='DefenseMicroManager'):
        raise ContractError('macro_base_defense_original_task_xml_required')
    acks=[r for r in rows if r['kind']=='command_acknowledged']
    by={r['action']:r for r in manifest['consumers']}
    masks=[1<<manifest['flags'].index(by[a]['flag']) for a in ('deploydefense','deployattack')]
    if (len(acks)!=5 or [r['native']['applied_mask'] for r in acks]!=[masks[0],0,masks[1],0,0]
            or [r['action'] for r in driver['targets']]!=['deploydefense','deployattack']):
        raise ContractError('macro_base_defense_field_sequence')
    origin=driver['initial_own_construction_yard_xyz']
    if [int(origin[0]//512),int(origin[1]//512)]!=[8,3]:raise ContractError('macro_base_defense_eastern_origin_required')
    begin,end=acks[0]['native']['last_frame'],acks[1]['native']['last_frame'];tracks={};cleared=[]
    if not 0<acks[0]['native']['deadline_frame']-begin<=1800:raise ContractError('macro_base_defense_field_duration')
    for row in rows:
        obs=row.get('observation')
        if obs is None:continue
        state=obs['state_scores'][consumer['flag']]
        matching=[t for t in obs['runtimes'] if t['group']==state['group'] and t['native_execution_active']]
        if obs['frame']>end and state['score']==0 and not matching:cleared.append(obs['frame'])
        if not begin<=obs['frame']<min(end,begin+900) or state['score']<=0:continue
        census=obs['construction_feedback']
        if census.get('enemy_details_read') is not False:raise ContractError('macro_base_defense_own_census_required')
        structures=[r for r in census['own_objects'] if r['type_hash'] in TEMPLATES.values() and r['hp']>0]
        for task in matching:
            if task.get('native_tactic_family')!='static_defense':raise ContractError('macro_base_defense_native_family')
            for group in task.get('owned_groups',[]):
                if not group.get('found') or not group.get('all_members_resolved'):continue
                for member in group['members']:
                    if member['owner']!=pre['native']['player']:raise ContractError('macro_base_defense_foreign_member')
                    point=member['xyz']
                    if len(point)!=3 or any(not math.isfinite(v) for v in point):raise ContractError('macro_base_defense_position')
                    if structures and min(math.dist(point[:2],r['xyz'][:2]) for r in structures)<=500:
                        tracks.setdefault((group['native_id'],member['thing_id']),set()).add(obs['frame'])
    if not any(len(v)>=3 and max(v)-min(v)>=15 for v in tracks.values()) or len(cleared)<2:
        raise ContractError('macro_base_defense_effect_or_release_missing')
    for name in ('driver-preflight.json','base-defense-driver.py','inspect_area_defense_runtime_candidates.py'):
        evidence[str(directory/name)]=sha(directory/name)
    return manifest,evidence


def extend_base_defense_scope(base,directory,static_directory,build):
    if not isinstance(base,RegionalScope) or base.package_sha256!=REGIONAL_PACKAGE_SHA:
        raise ContractError('macro_base_defense_regional_base_required')
    static=Path(static_directory).resolve();audit=load(static/'audit.json')
    if (sha(static/'audit.json')!=STATIC_SHA or sha(static/'auditor.py')!=audit['auditor_sha256']
            or audit['base_package_sha256']!=REGIONAL_PACKAGE_SHA or audit['package_sha256']!=PACKAGE_SHA
            or audit.get('only_east_task_definition_changed') is not True
            or audit.get('qualified_west_attack_budget_build_production_and_scout_preserved') is not True):
        raise ContractError('macro_base_defense_preservation_required')
    for path,digest in audit['evidence'].items():
        p=Path(path).resolve()
        if not p.is_relative_to(ROOT) or sha(p)!=digest:raise ContractError('macro_base_defense_package_changed')
    field,evidence=verify_base_defense_field(directory);current=load(Path(build)/'build-manifest.json')
    if (field['sources']!=base.budget.native_sources or tuple(field['flags'])!=base.budget.flags
            or current['sources']!=field['sources'] or current['flags']!=field['flags']
            or current['package_sha256']!=PACKAGE_SHA or current['consumers']!=field['consumers']):
        raise ContractError('macro_base_defense_execution_build_mismatch')
    evidence={**base.evidence,**evidence,**audit['evidence'],
        **{str(static/name):sha(static/name) for name in ('audit.json','auditor.py')}}
    budget=replace(base.budget,package_sha256=PACKAGE_SHA,evidence=evidence)
    return BaseDefenseScope(**{f.name:getattr(base,f.name) for f in fields(RegionalScope) if f.name not in ('budget','evidence')},
        budget=budget,evidence=evidence)
