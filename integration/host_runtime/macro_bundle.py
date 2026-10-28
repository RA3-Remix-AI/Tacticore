"""Native-bootstrap budget capability bundle. Never accepted from model/RPC data."""
from pathlib import Path
import hashlib
import json

from .contracts import ContractError
from .macro_policy_runtime import verify_budget_scope
from .macro_production_runtime import verify_production_preference_scope
from .macro_production_choices import extend_production_scope
from .macro_construction_scope import extend_construction_scope
from .macro_technology_budget_scope import extend_technology_budget_scope
from .macro_scouting import extend_scouting_scope
from .macro_region_scope import extend_regional_scope,STATIC_SHA
from .macro_base_defense_scope import extend_base_defense_scope,STATIC_SHA as BASE_DEFENSE_STATIC_SHA
from .macro_group_role_scope import extend_group_role_scope,STATIC_SHA as GROUP_ROLE_STATIC_SHA,REVISION_STATIC_SHA

ROOT=Path(__file__).resolve().parents[2]
FIELDS={'schema_version','kind','build','visibility','normal','host_loss','expiry','pins'}
PRODUCTION_FIELDS=FIELDS|{'production','production_static'}
CHOICE_FIELDS=PRODUCTION_FIELDS|{'production_choices'}
CONSTRUCTION_FIELDS=CHOICE_FIELDS|{'construction'}
TECHNOLOGY_FIELDS=CONSTRUCTION_FIELDS|{'technology_budget'}
SCOUTING_FIELDS=TECHNOLOGY_FIELDS|{'scouting'}
REGIONAL_FIELDS=SCOUTING_FIELDS|{'qualification_build','regional','regional_static'}
BASE_DEFENSE_FIELDS=REGIONAL_FIELDS|{'regional_build','base_defense','base_defense_static'}
GROUP_ROLE_FIELDS=BASE_DEFENSE_FIELDS|{'base_defense_build','group_roles','group_roles_static','group_role_revision_static'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required_files(value):
    paths=[]
    for key in ('normal','host_loss','expiry'):
        paths.extend(Path(value[key])/name for name in ('preflight.json','final-state.json','policy-probe.jsonl'))
    paths.extend(Path(value['visibility'])/name for name in ('build-capability.json','template-safety.json'))
    build=Path(value['build']);manifest=json.loads((build/'build-manifest.json').read_text(encoding='utf-8-sig'))
    paths.extend([build/'build-manifest.json',build/'profile.h',*[build/name for name in manifest['artifacts']]])
    paths.extend(ROOT/name for name in ('integration/macro_host.py','native-ai/macro-policy-runtime/client.py','native-ai/macro_observation.py',
        'integration/host_runtime/macro_live.py','integration/host_runtime/macro_desktop.py',
        'integration/host_runtime/macro_durable.py','integration/host_runtime/macro_bundle.py',
        'integration/host_runtime/macro_policy_runtime.py'))
    if value['schema_version']>=2:
        directory=Path(value['production']);static=Path(value['production_static'])
        paths.extend(directory/name for name in ('driver-preflight.json','count-driver.py',
            'transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl'))
        paths.append(static/'audit.json')
        paths.extend(ROOT/name for name in ('integration/host_runtime/macro_production_runtime.py',
            'integration/host_runtime/macro_production_feedback.py','integration/host_runtime/macro_production_public.py',
            'integration/host_runtime/macro_infrastructure.py',
            'integration/host_runtime/macro_forces.py',
            'native-ai/macro_build_observation.py','strategy/macro_policy.py','strategy/engine.py','strategy/http_adapter.py'))
    if value['schema_version']>=3:
        paths.append(ROOT/'integration/host_runtime/macro_production_choices.py')
        for item in value['production_choices']:
            folder=Path(item)
            paths.extend(folder/name for name in ('driver-preflight.json','count-driver.py','transport/preflight.json',
                'transport/final-state.json','transport/policy-probe.jsonl'))
            driver=json.loads((folder/'driver-preflight.json').read_text(encoding='utf-8-sig'))
            paths.extend(folder/'driver-source'/source['copy'] for source in driver['sources'])
    if value['schema_version']>=4:
        folder=Path(value['construction'])
        paths.extend(folder/name for name in ('driver-preflight.json','early-driver.py',
            'transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl'))
        paths.extend(ROOT/name for name in ('integration/host_runtime/macro_construction_feedback.py',
            'integration/host_runtime/macro_construction_scope.py'))
    if value['schema_version']>=5:
        folder=Path(value['technology_budget'])
        paths.extend(folder/name for name in ('driver-preflight.json','technology-driver.py',
            'transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl'))
        paths.append(ROOT/'integration/host_runtime/macro_technology_budget_scope.py')
    if value['schema_version']>=6:
        folder=Path(value['scouting'])
        paths.extend(folder/name for name in ('driver-preflight.json','scout-driver.py','visibility-binding.json',
            'lawful-snapshots.jsonl','driver-result.json','transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl'))
        paths.append(ROOT/'integration/host_runtime/macro_scouting.py')
    if value['schema_version']>=7:
        base_build=Path(value['qualification_build']);base_manifest=json.loads((base_build/'build-manifest.json').read_text())
        paths.extend([base_build/'build-manifest.json',base_build/'profile.h',*[base_build/name for name in base_manifest['artifacts']]])
        folder=Path(value['regional']);static=Path(value['regional_static'])
        if digest(static/'audit.json')!=STATIC_SHA:raise ContractError('macro_region_static_preservation_required')
        audit=json.loads((static/'audit.json').read_text())
        paths.extend(Path(p) for p in audit['evidence'])
        paths.extend(static/name for name in ('audit.json','auditor.py'))
        paths.extend(folder/name for name in ('driver-preflight.json','region-driver.py','inspect_macro_runtime_candidates.py',
            'transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl'))
        paths.extend(ROOT/name for name in ('integration/host_runtime/macro_region_scope.py',
            'integration/host_runtime/macro_regions.py','native-ai/read_public_region_targets.py'))
    if value['schema_version']>=8:
        build=Path(value['regional_build']);manifest=json.loads((build/'build-manifest.json').read_text())
        paths.extend([build/'build-manifest.json',build/'profile.h',*[build/name for name in manifest['artifacts']]])
        static=Path(value['base_defense_static']);audit=json.loads((static/'audit.json').read_text())
        if digest(static/'audit.json')!=BASE_DEFENSE_STATIC_SHA:raise ContractError('macro_base_defense_preservation_required')
        paths.extend(Path(path) for path in audit['evidence'])
        paths.extend(static/name for name in ('audit.json','auditor.py'))
        folder=Path(value['base_defense'])
        paths.extend(folder/name for name in ('driver-preflight.json','base-defense-driver.py','inspect_area_defense_runtime_candidates.py',
            'transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl'))
        paths.extend(ROOT/name for name in ('integration/host_runtime/macro_base_defense_scope.py',
            'native-ai/macro_area_defense_observation.py','native-ai/verify_area_defense_observer.py',
            'native-ai/macro-policy-runtime/client_area_defense.py'))
    if value['schema_version']>=9:
        build=Path(value['base_defense_build']);manifest=json.loads((build/'build-manifest.json').read_text())
        paths.extend([build/'build-manifest.json',build/'profile.h',*[build/name for name in manifest['artifacts']]])
        for key,expected in (('group_roles_static',GROUP_ROLE_STATIC_SHA),('group_role_revision_static',REVISION_STATIC_SHA)):
            static=Path(value[key]);audit=json.loads((static/'audit.json').read_text())
            if digest(static/'audit.json')!=expected:raise ContractError('macro_group_role_static_required')
            paths.extend(Path(p) for p in audit['evidence']);paths.extend(static/n for n in ('audit.json','auditor.py'))
        for item in value['group_roles']:
            folder=Path(item);driver=json.loads((folder/'driver-preflight.json').read_text())
            filename='group-role-attack-first-driver.py' if driver['kind']=='fixed_original_native_group_roles_attack_first_trial' else 'group-role-driver.py'
            paths.extend(folder/name for name in ('driver-preflight.json',filename,
                'transport/preflight.json','transport/final-state.json','transport/policy-probe.jsonl'))
        paths.extend(ROOT/name for name in ('integration/host_runtime/macro_group_role_scope.py',
            'integration/host_runtime/macro_group_role_contract.py','native-ai/macro_group_role_observation.py',
            'native-ai/verify_group_role_observer.py','native-ai/macro-policy-runtime/client_group_roles.py'))
    return paths


def load_bundle(path,session=None):
    path=Path(path)
    try:
        size=path.stat().st_size
        if size>65536:raise ValueError()
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        version=value['schema_version']
        if (version not in (8,9) and size>32768) or (version==8 and size>49152):raise ValueError()
        if (type(version) is not int or version not in (1,2,3,4,5,6,7,8,9)
                or set(value)!={1:FIELDS,2:PRODUCTION_FIELDS,3:CHOICE_FIELDS,4:CONSTRUCTION_FIELDS,5:TECHNOLOGY_FIELDS,6:SCOUTING_FIELDS,7:REGIONAL_FIELDS,8:BASE_DEFENSE_FIELDS,9:GROUP_ROLE_FIELDS}[version]
                or value['kind']!={1:'verified_macro_budget_bootstrap',2:'verified_macro_production_bootstrap',3:'verified_macro_production_choices_bootstrap',4:'verified_macro_construction_bootstrap',5:'verified_macro_technology_budget_bootstrap',6:'verified_macro_scouting_bootstrap',7:'verified_macro_regional_bootstrap',8:'verified_macro_base_defense_bootstrap',9:'verified_macro_group_roles_bootstrap'}[version]):raise ValueError()
        for key in ('build','visibility','normal','host_loss','expiry',*(('production','production_static') if version>=2 else ()),*(('construction',) if version>=4 else ()),*(('technology_budget',) if version>=5 else ()),*(('scouting',) if version>=6 else ()),*(('qualification_build','regional','regional_static') if version>=7 else ()),*(('regional_build','base_defense','base_defense_static') if version>=8 else ())):
            folder=Path(value[key])
            if not folder.is_absolute() or not folder.is_dir() or str(folder).startswith('\\\\'):
                raise ValueError()
        if version>=3:
            choices=value['production_choices']
            if (type(choices) is not list or not (1 if version==3 else 0)<=len(choices)<=9 or len(set(choices))!=len(choices)
                    or any(not Path(p).is_absolute() or not Path(p).is_dir() or str(p).startswith('\\\\') for p in choices)):
                raise ValueError()
        if version>=9:
            for key in ('base_defense_build','group_roles_static','group_role_revision_static'):
                folder=Path(value[key])
                if not folder.is_absolute() or not folder.is_dir() or str(folder).startswith('\\\\'):raise ValueError()
            groups=value['group_roles']
            if (type(groups) is not list or not 1<=len(groups)<=3 or len(set(groups))!=len(groups)
                    or any(not Path(p).is_absolute() or not Path(p).is_dir() or str(p).startswith('\\\\') for p in groups)):
                raise ValueError()
        expected={str(file.resolve()):digest(file) for file in required_files(value)}
        if value['pins']!=expected:raise ValueError()
        scope=verify_budget_scope(value['normal'],value['host_loss'],value['expiry'],value.get('qualification_build',value['build']))
        if version>=5:scope=extend_technology_budget_scope(scope,value['technology_budget'])
        if version>=2:scope=verify_production_preference_scope(scope,value['production'],value['production_static'])
        if version>=3 and value['production_choices']:scope=extend_production_scope(scope,value['production_choices'])
        if version>=4:scope=extend_construction_scope(scope,value['construction'])
        if version>=6:scope=extend_scouting_scope(scope,value['scouting'])
        if version>=7:scope=extend_regional_scope(scope,value['regional'],value['regional_static'],value.get('regional_build',value['build']))
        if version>=8:scope=extend_base_defense_scope(scope,value['base_defense'],value['base_defense_static'],value.get('base_defense_build',value['build']))
        if version>=9:scope=extend_group_role_scope(scope,value['group_roles'],value['group_roles_static'],value['group_role_revision_static'],value['build'])
        if session is not None and session['mod_sha256']!=scope.package_sha256:raise ValueError()
        return value,scope
    except (OSError,ValueError,KeyError,TypeError):
        raise ContractError('macro_bundle_not_qualified') from None


def create_bundle(path,*,build,visibility,normal,host_loss,expiry,production=None,production_static=None,production_choices=None,construction=None,technology_budget=None,scouting=None,qualification_build=None,regional=None,regional_static=None,regional_build=None,base_defense=None,base_defense_static=None,base_defense_build=None,group_roles=None,group_roles_static=None,group_role_revision_static=None):
    if (production is None)!=(production_static is None):raise ContractError('macro_production_bundle_incomplete')
    if production_choices is not None and production is None:raise ContractError('macro_production_bundle_incomplete')
    if construction is not None and production is None:raise ContractError('macro_construction_bundle_incomplete')
    if technology_budget is not None and construction is None:raise ContractError('macro_technology_bundle_incomplete')
    if scouting is not None and technology_budget is None:raise ContractError('macro_scout_bundle_incomplete')
    if any(v is not None for v in (qualification_build,regional,regional_static)) and (scouting is None
            or any(v is None for v in (qualification_build,regional,regional_static))):raise ContractError('macro_region_bundle_incomplete')
    if any(v is not None for v in (regional_build,base_defense,base_defense_static)) and (regional is None
            or any(v is None for v in (regional_build,base_defense,base_defense_static))):raise ContractError('macro_base_defense_bundle_incomplete')
    if any(v is not None for v in (base_defense_build,group_roles,group_roles_static,group_role_revision_static)) and (base_defense is None
            or any(v is None for v in (base_defense_build,group_roles,group_roles_static,group_role_revision_static))):
        raise ContractError('macro_group_roles_bundle_incomplete')
    value=dict(schema_version=1,kind='verified_macro_budget_bootstrap',
        **{key:str(Path(item).resolve()) for key,item in dict(build=build,visibility=visibility,
            normal=normal,host_loss=host_loss,expiry=expiry).items()})
    if production is not None:
        value.update(schema_version=2,kind='verified_macro_production_bootstrap',
            production=str(Path(production).resolve()),production_static=str(Path(production_static).resolve()))
    if production_choices is not None:
        value.update(schema_version=3,kind='verified_macro_production_choices_bootstrap',
            production_choices=[str(Path(p).resolve()) for p in production_choices])
    if construction is not None:
        value.update(schema_version=4,kind='verified_macro_construction_bootstrap',
            construction=str(Path(construction).resolve()),production_choices=value.get('production_choices',[]))
    if technology_budget is not None:
        value.update(schema_version=5,kind='verified_macro_technology_budget_bootstrap',
            technology_budget=str(Path(technology_budget).resolve()))
    if scouting is not None:
        value.update(schema_version=6,kind='verified_macro_scouting_bootstrap',scouting=str(Path(scouting).resolve()))
    if regional is not None:
        value.update(schema_version=7,kind='verified_macro_regional_bootstrap',
            qualification_build=str(Path(qualification_build).resolve()),regional=str(Path(regional).resolve()),
            regional_static=str(Path(regional_static).resolve()))
    if base_defense is not None:
        value.update(schema_version=8,kind='verified_macro_base_defense_bootstrap',regional_build=str(Path(regional_build).resolve()),
            base_defense=str(Path(base_defense).resolve()),base_defense_static=str(Path(base_defense_static).resolve()))
    if group_roles is not None:
        value.update(schema_version=9,kind='verified_macro_group_roles_bootstrap',base_defense_build=str(Path(base_defense_build).resolve()),
            group_roles=[str(Path(p).resolve()) for p in group_roles],group_roles_static=str(Path(group_roles_static).resolve()),
            group_role_revision_static=str(Path(group_role_revision_static).resolve()))
    value['pins']={str(file.resolve()):digest(file) for file in required_files(value)}
    with Path(path).open('x',encoding='utf8') as stream:json.dump(value,stream,indent=2)
    return load_bundle(path)[1].public()
