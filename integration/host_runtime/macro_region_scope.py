"""Two evidence-bound public region goals, executed by original native AI."""
from dataclasses import dataclass,fields,replace
import math
from pathlib import Path

from .contracts import ContractError
from .macro_policy_runtime import ROOT,load,sha,trial
from .macro_scouting import ScoutingScope

DRIVER_SHA='709e5c23925e18b76fddd6dfa541a8b0a7ec92bc34d05ad803b57076ce10eb8d'
STATIC_SHA='3a89e5666cb6703ea8b0876772b078684cc2599cb4a3577408bbeb942139842d'
PACKAGE_SHA='4a65c9b683c9de210f84aa14383cc99f1bef9fe066b7295151bf1edce46171bd'
PUBLIC_TARGETS={'deployattack':('region_1_3',857.5399780273438,2015.35400390625),
                'deploydefense':('region_8_3',4404.11669921875,2016.0247802734375)}

@dataclass(frozen=True)
class RegionalScope(ScoutingScope):
    regional_targets:tuple=()

    @property
    def regional_action_regions(self):return {action:region for action,region,flag,x,y in self.regional_targets}

    @property
    def available_actions(self):return super().available_actions+tuple(self.regional_action_regions)

    def public(self):
        return dict(**super().public(),regional_deployment_granted=bool(self.regional_targets),
            regional_action_regions=self.regional_action_regions,regional_map_id='map_mp_2_black1b',
            regional_goal='native_combat_group_to_fixed_public_waypoint',
            native_ai_selects_and_operates_group=True,arbitrary_xy_control_granted=False,
            complete_attack_defense_or_retreat_mission_guaranteed=False)

def verified_regional_field(directory):
    directory=Path(directory).resolve();driver=load(directory/'driver-preflight.json')
    pre,final,manifest,rows,evidence=trial(directory/'transport')
    sources={Path(r['path']).name:r for r in pre['sources']}
    if (driver.get('driver_sha256')!=DRIVER_SHA or sha(directory/'region-driver.py')!=DRIVER_SHA
            or sha(directory/'inspect_macro_runtime_candidates.py')!=driver.get('diagnostic_sha256')
            or driver.get('session_id')!=final['session_id'] or driver.get('pid')!=final['pid']
            or driver.get('process_creation_filetime')!=final['process_creation_filetime']
            or driver.get('model_calls')!=0 or driver.get('unit_orders')!=0 or driver.get('enemy_live_details_read') is not False
            or driver.get('actual_map_id')!='map_mp_2_black1b' or manifest['package_sha256']!=PACKAGE_SHA
            or sources['macro_observation.py']['sha256']!=sha(ROOT/'native-ai/macro_observation.py')):
        raise ContractError('macro_region_fixed_field_binding')
    targets=driver['targets']
    if len(targets)!=2 or {t['action'] for t in targets}!=set(PUBLIC_TARGETS):raise ContractError('macro_region_two_targets_required')
    by={t['action']:t for t in manifest['consumers']};acks=[r for r in rows if r['kind']=='command_acknowledged']
    masks=[1<<manifest['flags'].index(by[t['action']]['flag']) for t in targets]
    if len(acks)!=5 or [r['native']['applied_mask'] for r in acks]!=[masks[0],0,masks[1],0,0]:
        raise ContractError('macro_region_field_gate_sequence')
    observations=[r['observation'] for r in rows if r.get('observation')];qualified=[]
    for index,target in enumerate(targets):
        action=target['action'];region,x,y=PUBLIC_TARGETS[action];consumer=by[action]
        if (target['region_id']!=region or target['waypoint_xyz'][:2]!=[x,y]
                or consumer.get('region_id')!=region or consumer.get('waypoint_xyz')[:2]!=[x,y]
                or consumer.get('native_tactic')!='SimpleAttack'
                or consumer.get('native_micro_manager')!='GrowingAttacksMicroManager_MEDIUM'
                or consumer.get('native_recruitment_priority')!='HIGH'
                or consumer.get('native_waypoint_require_unique_target') is not False
                or consumer.get('unit_orders_exposed') is not False):raise ContractError('macro_region_public_target_binding')
        begin=acks[2*index]['native']['last_frame'];end=acks[2*index+1]['native']['last_frame']
        if not 0<acks[2*index]['native']['deadline_frame']-begin<=1800:raise ContractError('macro_region_field_duration')
        tracks={};cleared=set()
        for obs in observations:
            state=obs['state_scores'][consumer['flag']]
            matching=[t for t in obs['runtimes'] if t['group']==state['group'] and t['native_execution_active']]
            if begin<=obs['frame']<end and state['score']>0:
                for runtime in matching:
                    if runtime.get('native_tactic_family')!='simple_attack':raise ContractError('macro_region_native_tactic_type')
                    for group in runtime.get('owned_groups',[]):
                        if not group.get('found') or not group.get('all_members_resolved'):continue
                        for member in group['members']:
                            if member['owner']!=pre['native']['player']:raise ContractError('macro_region_foreign_member')
                            key=(runtime['address'],group['native_id'],member['thing_id'])
                            tracks.setdefault(key,[]).append((obs['frame'],member['xyz']))
            if obs['frame']>end and state['score']==0 and not matching:cleared.add(obs['frame'])
        def progress(track):
            distance=lambda xyz:math.dist(xyz[:2],(x,y))
            return (len({v[0] for v in track})>=2 and max(math.dist(track[0][1],v[1]) for v in track)>10
                and distance(track[0][1])-min(distance(v[1]) for v in track)>50)
        if not any(progress(t) for t in tracks.values()) or len(cleared)<2:
            raise ContractError('macro_region_native_effect_missing')
        qualified.append((action,region,consumer['flag'],x,y))
    for name in ('driver-preflight.json','region-driver.py','inspect_macro_runtime_candidates.py'):
        evidence[str(directory/name)]=sha(directory/name)
    return pre,final,manifest,tuple(sorted(qualified)),evidence

def extend_regional_scope(base,directory,static_directory,build):
    if not isinstance(base,ScoutingScope):raise ContractError('macro_region_scouting_base_required')
    static=Path(static_directory);audit=load(static/'audit.json')
    if (sha(static/'audit.json')!=STATIC_SHA or sha(static/'auditor.py')!=audit['auditor_sha256']
            or audit['base_package_sha256']!=base.package_sha256 or audit['regional_package_sha256']!=PACKAGE_SHA
            or audit['qualified_budget_build_production_and_scout_assets_preserved'] is not True):
        raise ContractError('macro_region_static_preservation_required')
    for path,digest in audit['evidence'].items():
        p=Path(path).resolve()
        if not p.is_relative_to(ROOT) or sha(p)!=digest:raise ContractError('macro_region_package_evidence_changed')
    pre,final,manifest,targets,evidence=verified_regional_field(directory)
    current=load(Path(build)/'build-manifest.json')
    if (manifest['sources']!=base.budget.native_sources or tuple(manifest['flags'])!=base.budget.flags
            or current['sources']!=manifest['sources'] or current['flags']!=manifest['flags']
            or current['package_sha256']!=PACKAGE_SHA or current['consumers']!=manifest['consumers']):
        raise ContractError('macro_region_execution_build_mismatch')
    evidence.update(audit['evidence']);evidence.update({str(static/n):sha(static/n) for n in ('audit.json','auditor.py')})
    evidence={**base.evidence,**evidence};budget=replace(base.budget,package_sha256=PACKAGE_SHA,evidence=evidence)
    return RegionalScope(**{f.name:getattr(base,f.name) for f in fields(ScoutingScope) if f.name not in ('budget','evidence')},
        budget=budget,evidence=evidence,regional_targets=targets)
