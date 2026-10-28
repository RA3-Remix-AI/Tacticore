"""Own roster locations for macro planning; presence never grants recruitment."""
import math
import re

from .contracts import ContractError

MOBILE_ROLES=('infantry','armor','anti_air','anti_armor','air','naval')
NAMED_UNITS={
    'conscript':('0x19ab11af','SovietAntiInfantryInfantry'),
    'flak_trooper':('0x2c358c61','SovietAntiVehicleInfantry'),
    'hammer_tank':('0x94b3590b','SovietAntiVehicleVehicleTech1'),
    'war_bear':('0x33026fa1','SovietScoutInfantry'),
}
MAX_REGIONS=4


def observe_forces(census,safety):
    if (type(census) is not dict or census.get('enemy_details_read') is not False
            or type(census.get('frame')) is not int or not 0<census['frame']<=0xffffffff
            or type(census.get('own_objects')) is not list or len(census['own_objects'])>8192
            or type(safety) is not dict or type(safety.get('templates')) is not dict):
        raise ContractError('macro_forces_source')
    templates=safety['templates'];roles={};named=dict.fromkeys(NAMED_UNITS,0)
    regions={};seen=set();unclassified=0;unlocated=0
    for row in census['own_objects']:
        if type(row) is not dict:raise ContractError('macro_forces_shape')
        oid=row.get('thing_id');hp=row.get('hp');xyz=row.get('xyz')
        if (type(oid) is not int or not 0<oid<=0xffffffff or oid in seen
                or type(hp) not in (int,float) or not math.isfinite(hp) or hp<=0
                or type(xyz) is not list or len(xyz)!=3
                or any(type(x) not in (int,float) or not math.isfinite(x) for x in xyz)):
            raise ContractError('macro_forces_own_identity_or_position')
        seen.add(oid);safe=templates.get(row.get('type_hash'))
        if not safe or safe.get('source_audited_no_intrinsic_stealth') is not True:
            unclassified+=1;continue
        role=safe.get('role')
        if role not in MOBILE_ROLES and role not in ('structure','economy'):
            raise ContractError('macro_forces_template_role')
        if role in MOBILE_ROLES:roles[role]=roles.get(role,0)+1
        for name,(template,unit) in NAMED_UNITS.items():
            if row['type_hash']==template:
                if safe.get('template')!=unit:raise ContractError('macro_forces_template_binding')
                named[name]+=1
        if not (0<=xyz[0]<65536 and 0<=xyz[1]<65536):unlocated+=1;continue
        region='region_'+str(int(xyz[0]//512))+'_'+str(int(xyz[1]//512))
        counts=regions.setdefault(region,dict(mobile=0,construction_yards=0))
        counts['mobile']+=int(role in MOBILE_ROLES)
        counts['construction_yards']+=int(safe.get('template')=='SovietConstructionYard')
    # Prioritize known home regions, then concentrations. Omission is explicit.
    ordered=sorted(regions,key=lambda r:(-regions[r]['construction_yards'],-regions[r]['mobile'],r))
    retained=[dict(region_id=r,**regions[r]) for r in ordered[:MAX_REGIONS]]
    return dict(source='bound_own_force_presence',observed_frame=census['frame'],own_perspective=True,
        enemy_details_read=False,mobile_role_counts=roles,named_unit_counts=named,regions=retained,
        omitted_region_count=max(0,len(regions)-MAX_REGIONS),unclassified_objects=unclassified,
        unlocated_classified_objects=unlocated,coverage='audited_template_presence_only',
        ready_for_combat_verified=False,recruitability_verified=False,unit_operation_policy='native_ai')


def compact_forces(value,game_seconds):
    if (type(value) is not dict or value.get('source')!='bound_own_force_presence'
            or value.get('own_perspective') is not True or value.get('enemy_details_read') is not False):
        raise ContractError('macro_forces_source')
    frame=value.get('observed_frame')
    if (type(game_seconds) not in (int,float) or not math.isfinite(game_seconds)
            or type(frame) is not int or not 0<frame<=0xffffffff or not -15<=game_seconds*15-frame<=30):
        raise ContractError('macro_forces_stale')
    def count(v):
        if type(v) is not int or not 0<=v<=8192:raise ContractError('macro_forces_count')
        return v
    roles=value.get('mobile_role_counts');named=value.get('named_unit_counts');regions=value.get('regions')
    if (type(roles) is not dict or set(roles)-set(MOBILE_ROLES) or type(named) is not dict
            or set(named)!=set(NAMED_UNITS) or type(regions) is not list or len(regions)>MAX_REGIONS):
        raise ContractError('macro_forces_shape')
    public=[];seen=set()
    for row in regions:
        if type(row) is not dict:raise ContractError('macro_forces_shape')
        region=row.get('region_id')
        if (type(region) is not str or re.fullmatch(r'region_(?:0|[1-9][0-9]{0,2})_(?:0|[1-9][0-9]{0,2})',region) is None
                or region in seen):raise ContractError('macro_forces_region')
        if any(int(v)>=128 for v in region.split('_')[1:]):raise ContractError('macro_forces_region')
        seen.add(region);public.append(dict(region_id=region,mobile=count(row.get('mobile')),
            construction_yards=count(row.get('construction_yards'))))
    total=sum(count(v) for v in roles.values())
    if total>8192 or sum(r['mobile'] for r in public)>total or sum(count(v) for v in named.values())>total:
        raise ContractError('macro_forces_count_consistency')
    return dict(source='bound_own_force_presence',observed_frame=frame,own_perspective=True,enemy_details_read=False,
        mobile_role_counts={k:count(v) for k,v in roles.items()},named_unit_counts={k:count(v) for k,v in named.items()},
        regions=public,**{k:count(value.get(k)) for k in ('omitted_region_count','unclassified_objects','unlocated_classified_objects')},
        coverage='audited_template_presence_only',ready_for_combat_verified=False,recruitability_verified=False,
        unit_operation_policy='native_ai')
