"""Pure macro intent contract. Capability lists come from trusted host evidence."""
from dataclasses import dataclass, asdict

ACTIONS={
    'build_airfield':'construction','buildreactor':'construction','buildtech':'construction','economyrefinery':'construction',
    'produceconscript':'production','produceflak':'production','producetank':'production',
    'budgeteconomy':'budget','budgetarmy':'budget','budgettech':'budget',
    'deployattack':'deployment','deploydefense':'deployment','scout':'scouting',
    'regroup':'deployment','withdraw':'deployment','reinforce':'deployment',
    'buildpower':'construction','buildbarracks':'construction','buildfactory':'construction',
    'buildrefinery':'construction','buildbattlelab':'construction',
    'producesickle':'production','producebullfrog':'production'}
try:
    from .native_unified_contract_v5 import NEW_DOMAINS,additional_catalog
except ImportError:
    from native_unified_contract_v5 import NEW_DOMAINS,additional_catalog
ACTIONS.update(NEW_DOMAINS)
INITIAL_PRODUCTION_COUNTS={'producesickle':(1,), 'producebullfrog':(1,)}
CONSTRUCTION_BUILDINGS={'buildpower':'power_plant','buildbarracks':'barracks','buildfactory':'war_factory',
    'buildrefinery':'refinery','buildbattlelab':'battle_lab'}
GROUP_ROLE_GOALS={'regroup':'regroup_native_force_at_own_home_waypoint',
    'withdraw':'withdraw_native_group_to_own_home_region',
    'reinforce':'reinforce_own_base_through_original_reactive_defense'}

# These exact defaults repeat the global macro prompt. Only omit their known
# values in the model projection; native qualification and policy validation
# still consume the full contracts. Preserve every other field and value.
_PROMPT_DEFAULTS={
    'exclusive_with_other_construction_or_production':True,
    'native_unit_operations_unchanged':True,
    'native_ai_operates_units':True,
    'native_ai_selects_and_operates_group':True,
    'arrival_and_mission_success_guaranteed':False,
    'arbitrary_unit_selection_supported':False,
    'all_units_or_physical_home_return_guaranteed':False,
    'legacy_action_name_is_not_mission_purpose':True,
    'arbitrary_region_selection_supported':False,
    'new_contacts_are_lawful_but_not_exclusively_attributed':True,
    'native_ai_selects_placement_and_build_execution':True,
    'construction_completed_guaranteed':False,
    'native_opening_and_prerequisite_gates_remain_active':True,
    'retry_requires_new_decision':True,
}


def model_catalog(catalog):
    """Remove only repeated known defaults, without changing authorization."""
    result={action:{key:value for key,value in description.items()
        if key not in _PROMPT_DEFAULTS or value is not _PROMPT_DEFAULTS[key]}
        for action,description in catalog.items()}
    for description in result.values():
        if isinstance(description.get('quantity'),dict):
            description['quantity']={key:value for key,value in description['quantity'].items()
                if not (key=='completed_units_guaranteed' and value is False
                    or key=='replacement_requires_new_decision' and value is True)}
        if description.get('region_semantics') in ('fixed_public_own_home_region','eastern_home_base_anchor_native_base_selection'):
            del description['region_semantics']
    return result
BUDGET_PRESETS={
    'budgeteconomy':dict(investment=.4,special_operations=0,production=.25,defense=.1,technology=.15,slush_fund=.1),
    'budgetarmy':dict(investment=.1,special_operations=0,production=.7,defense=.1,technology=.05,slush_fund=.05),
    'budgettech':dict(investment=.15,special_operations=0,production=.25,defense=.1,technology=.4,slush_fund=.1)}


def parse_control(raw):
    if (not isinstance(raw,dict) or not {'mode','available_actions'}<=set(raw)<={'mode','available_actions','production_counts','region_targets'}
            or raw['mode']!='macro_native'):
        raise ValueError('macro_control_fields')
    actions=raw['available_actions']
    if not isinstance(actions,list) or len(actions)>len(ACTIONS) or any(type(a) is not str or a not in ACTIONS for a in actions) or len(set(actions))!=len(actions):
        raise ValueError('macro_capability_actions')
    return tuple(actions)

def parse_region_targets(raw,actions,regions):
    deployment={action for action in actions if ACTIONS[action]=='deployment'}
    targets=raw.get('region_targets')
    if targets is None:
        if deployment:raise ValueError('macro_region_capabilities_missing')
        return None
    if (type(targets) is not dict or set(targets)!=deployment
            or any(type(region) is not str or region not in regions for region in targets.values())):
        raise ValueError('macro_region_capabilities')
    return tuple(sorted(targets.items()))

def validate_region_target(actions,target,request_targets,latest_targets):
    for action in actions:
        if ACTIONS[action]=='deployment' and any(dict(targets or ()).get(action)!=target or target is None
                for targets in (request_targets,latest_targets)):
            raise ValueError('macro_region_target_binding')


def parse_counts(raw,actions):
    counts=raw.get('production_counts')
    if counts is None:return None
    if (type(counts) is not dict or set(counts)!={action for action in actions if ACTIONS[action]=='production'}
            or any(type(values) is not list or not values or len(values)>3
                or any(type(n) is not int or not 1<=n<=3 for n in values) or len(set(values))!=len(values)
                for values in counts.values())
            or any(action in INITIAL_PRODUCTION_COUNTS and tuple(sorted(values))!=INITIAL_PRODUCTION_COUNTS[action]
                   for action,values in counts.items())):
        raise ValueError('macro_production_capability_counts')
    return tuple(sorted((action,tuple(sorted(values))) for action,values in counts.items()))


def validate_actions(raw,request_capabilities,latest_capabilities):
    if not isinstance(raw,list) or len(raw)>5 or any(type(a) is not str or a not in ACTIONS for a in raw) or len(set(raw))!=len(raw):
        raise ValueError('macro_policy_actions')
    if any(action not in (request_capabilities or ()) or action not in (latest_capabilities or ()) for action in raw):
        raise ValueError('unsupported_macro_action')
    domains=[ACTIONS[action] for action in raw]
    if len(set(domains))!=len(domains):raise ValueError('conflicting_macro_actions')
    # Current native host tracks one bounded build/production preference at a
    # time. Express the same limit before model plans can be accepted.
    if sum(domain in ('construction','production','scouting','deployment','expansion') for domain in domains)>1:
        raise ValueError('conflicting_macro_work_actions')
    return tuple(raw)


@dataclass(frozen=True)
class ProductionQuantity:
    action: str
    additional_count: int

    def public(self):
        return asdict(self)


def validate_production(raw, actions, *, macro_mode, request_counts=None, latest_counts=None):
    production=[action for action in actions if ACTIONS[action]=='production']
    if not production:
        if raw is not None:raise ValueError('macro_production_without_action')
        return None
    if (not macro_mode or type(raw) is not dict or set(raw)!={'action','additional_count'}
            or raw['action']!=production[0] or type(raw['additional_count']) is not int
            or not 1<=raw['additional_count']<=3):
        raise ValueError('macro_production_quantity')
    if any(counts is not None and raw['additional_count'] not in dict(counts).get(raw['action'],())
           for counts in (request_counts,latest_counts)):
        raise ValueError('macro_production_quantity_not_qualified')
    if raw['action'] in INITIAL_PRODUCTION_COUNTS and raw['additional_count'] not in INITIAL_PRODUCTION_COUNTS[raw['action']]:
        raise ValueError('macro_production_quantity_not_qualified')
    return ProductionQuantity(raw['action'],raw['additional_count'])


def public_descriptions(actions,counts=None,region_targets=None):
    descriptions={action:dict(domain=ACTIONS[action],
        **({'exclusive_with_other_construction_or_production':True} if ACTIONS[action] in ('construction','production','scouting','deployment') else {}),
        **({'control_basis':'one_bounded_native_scout_preference','target_policy':'original_native_scout_target_selection',
            'maximum_duration_seconds':90,'arbitrary_region_selection_supported':False,
            'native_ai_operates_units':True,'new_contacts_are_lawful_but_not_exclusively_attributed':True}
            if action=='scout' else {}),
        **({'target_region':dict(region_targets or ())[action],
            'goal':GROUP_ROLE_GOALS.get(action,'native_combat_group_to_fixed_public_waypoint'),'maximum_duration_seconds':60,
            'native_ai_selects_and_operates_group':True,'legacy_action_name_is_not_mission_purpose':True,
            'arrival_and_mission_success_guaranteed':False} if ACTIONS[action]=='deployment' else {}),
        **({'native_account_shares':dict(BUDGET_PRESETS[action])} if action in BUDGET_PRESETS else {}),
        **({'quantity':dict(field='macro_production',
            **(dict(allowed_additional_counts=list(dict(counts)[action])) if counts is not None else
               dict(allowed_additional_counts=list(INITIAL_PRODUCTION_COUNTS[action])) if action in INITIAL_PRODUCTION_COUNTS
               else dict(additional_count_min=1,additional_count_max=3)),
            control_basis='new_native_queue_acceptances',completed_units_guaranteed=False,
            replacement_requires_new_decision=True)} if ACTIONS[action]=='production' else {}),
        **({'control_basis':'one_native_construction_preference',
            'release_on':'first_new_matching_queue_or_expiry',
            'construction_completed_guaranteed':False,'native_ai_selects_placement_and_build_execution':True,
            'native_opening_and_prerequisite_gates_remain_active':True,
            **({'building':CONSTRUCTION_BUILDINGS[action]} if action in CONSTRUCTION_BUILDINGS else {}),
            **({'building':'super_reactor','observed_native_queue_cost':2000,
                'cost_source':'qualified_native_queue_observation','supports_native_production_action':'producetank',
                'resource_semantics':'native_queue_uses_incremental_payment_not_full_upfront_charge'} if action=='buildreactor' else {}),
            'retry_requires_new_decision':True} if ACTIONS[action]=='construction' else {})) for action in actions}
    return {action:{**description,**additional_catalog((action,)).get(action,{})} for action,description in descriptions.items()}


# Only exact, named defaults are shared by the strategic wire contract. Ordered
# entries define reversible presence masks; no arbitrary False traversal occurs.
STRATEGY_CATALOG_DEFAULTS=(
    ('construction',('control_basis',),'one_native_construction_preference'),
    ('construction',('release_on',),'first_new_matching_queue_or_expiry'),
    ('construction',('resource_semantics',),'native_queue_uses_incremental_payment_not_full_upfront_charge'),
    ('production',('quantity','field'),'macro_production'),
    ('production',('quantity','control_basis'),'new_native_queue_acceptances'),
    ('deployment',('maximum_duration_seconds',),60),
)
STRATEGY_FEEDBACK_DEFAULTS=(
    ('payment_verified',False), ('completed_units_verified',False),
    ('construction_completed_verified',False), ('completed_technology_verified',False),
    ('exact_queue_to_unit_link_verified',False), ('exact_queue_to_object_link_verified',False),
    ('exclusive_macro_attribution_verified',False), ('automatic_retry_allowed',False),
    ('unit_operation_policy','native_ai'), ('ready_for_combat_verified',False),
    ('recruitability_verified',False), ('grants_capability',False),
)
STRATEGY_FEEDBACK_SECTIONS=('macro_execution_feedback','macro_production_feedback','macro_construction_feedback',
    'macro_scouting_feedback','macro_regional_feedback','own_infrastructure','own_forces')
_STRATEGY_ALIAS_FIELDS=(
    'domain','target_policy','target_region','goal','observed_frame','release_reason','policy_released',
    'region_id','mobile','construction_yards','native_account_shares','investment','special_operations',
    'production','defense','technology','slush_fund','quantity','allowed_additional_counts',
    'requires_existing_forward_force','status','action','builder_frame','own_census_frame',
    'observed_queue_count','observed_cost_sum','observed_paid_field_sum','fully_paid_queue_count',
    'observed_new_queue_count','additional_queue_observations_after_release','fully_paid_queue_observations',
    'view_frame','active_native_tactics','allocated_native_groups','native_execution_observed',
    'moved_native_groups','mission_success_verified','refinery','super_reactor','battle_lab',
    'own_perspective','enemy_details_read','coverage','building','control_basis','maximum_duration_seconds',
    'requires_fresh_native_readiness_and_dependency','native_ai_selects_location_and_operates_units')
_STRATEGY_ALIASES={('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'[index]):field
    for index,field in enumerate(_STRATEGY_ALIAS_FIELDS)}
STRATEGY_DEFAULT_SCHEMA_NAME='native_macro_public_defaults_v2'


def _copy_public(value):
    import json
    def pairs(items):
        result={}
        for key,item in items:
            if key in result:raise ValueError('macro_public_duplicate_key')
            result[key]=item
        return result
    def invalid(_):raise ValueError('macro_public_nonfinite')
    raw=value if type(value) in (str,bytes) else json.dumps(value,ensure_ascii=False,allow_nan=False)
    result=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    if type(result) is not dict:raise ValueError('macro_public_object')
    return result


def _alias_fields(value,mapping,*,restore=False):
    if type(value) is dict:
        result={}
        for key,item in value.items():
            if key in _STRATEGY_ALIASES and (not restore or key not in mapping):
                raise ValueError('macro_public_unknown_alias')
            target=mapping.get(key,key)
            if target in result:raise ValueError('macro_public_alias_conflict')
            result[target]=_alias_fields(item,mapping,restore=restore)
        return result
    if type(value) is list:return [_alias_fields(item,mapping,restore=restore) for item in value]
    return value


def _select_aliases(context):
    from collections import Counter
    counts=Counter()
    def walk(value):
        if type(value) is dict:
            for key,item in value.items():counts[key]+=1;walk(item)
        elif type(value) is list:
            for item in value:walk(item)
    for section in ('macro_policy_catalog',*STRATEGY_FEEDBACK_SECTIONS):walk(context.get(section,{}))
    # Include the escaped-JSON overhead of the single global alias table.
    return {alias:field for alias,field in _STRATEGY_ALIASES.items()
        if counts[field]*(len(field)-len(alias))>len(field)+len(alias)+16}


def strategic_public_defaults():
    """Public contract for decoding omitted fixed values, generated from source."""
    catalog={}
    for domain,path,value in STRATEGY_CATALOG_DEFAULTS:
        target=catalog.setdefault(domain,{})
        for key in path[:-1]:target=target.setdefault(key,{})
        target[path[-1]]=value
    return dict(catalog=catalog,feedback=dict(false_fields=[key for key,value in STRATEGY_FEEDBACK_DEFAULTS
        if value is False],unit_operation_policy='native_ai'))


def strategic_default_prompt(*, strategic_only=False):
    """Exact named-schema semantics, generated from the verification whitelist."""
    verified=[key[:-9] for key,value in STRATEGY_FEEDBACK_DEFAULTS if value is False and key.endswith('_verified')]
    other=[key for key,value in STRATEGY_FEEDBACK_DEFAULTS if value is False and not key.endswith('_verified')]
    details = ('' if strategic_only else
        'construction=one native preference/first matching queue|expiry/incremental not upfront;'
        'production=macro_production/new queue acceptances;')
    return ('Masked defaults:{'+','.join(verified)+'}_verified=false;'+','.join(other)+'=false;'
        'unit_operation_policy=native_ai;'+details+
        'deployment=max60.Explicit wins;false *_verified=unverified.')


def _same_default(actual,expected):
    return type(actual) is type(expected) and actual==expected


def project_strategy_defaults(context):
    """Reversibly omit only exact duplicate contract values in the new mode."""
    result=restore_public_defaults(context)
    metadata=dict(version=2,definitions=STRATEGY_DEFAULT_SCHEMA_NAME,catalog={},feedback={})
    for action,description in result.get('macro_policy_catalog',{}).items():
        mask=0
        for index,(domain,path,default) in enumerate(STRATEGY_CATALOG_DEFAULTS):
            if description.get('domain')!=domain:continue
            parent=description
            for key in path[:-1]:parent=parent.get(key,{}) if isinstance(parent,dict) else {}
            if isinstance(parent,dict) and path[-1] in parent and _same_default(parent[path[-1]],default):
                del parent[path[-1]];mask|=1<<index
        if mask:metadata['catalog'][action]=mask
    for section in STRATEGY_FEEDBACK_SECTIONS:
        value=result.get(section)
        if type(value) is not dict:continue
        mask=0
        for index,(key,default) in enumerate(STRATEGY_FEEDBACK_DEFAULTS):
            if key in value and _same_default(value[key],default):
                del value[key];mask|=1<<index
        if mask:metadata['feedback'][section]=mask
    metadata['catalog']=[metadata['catalog'].get(name,0) for name in sorted(result.get('macro_policy_catalog',{}))]
    metadata['feedback']=[metadata['feedback'].get(name,0) for name in STRATEGY_FEEDBACK_SECTIONS]
    metadata['aliases']=_select_aliases(result)
    packing={field:alias for alias,field in metadata['aliases'].items()}
    for section in ('macro_policy_catalog',*STRATEGY_FEEDBACK_SECTIONS):
        if section in result:result[section]=_alias_fields(result[section],packing)
    result['macro_default_contract']=metadata
    return result


def restore_public_defaults(context):
    """Restore exactly the omitted fields, retaining all changed/unknown values."""
    result=_copy_public(context)
    metadata=result.pop('macro_default_contract',None)
    if metadata is None:return result
    if (type(metadata) is not dict or type(metadata.get('version')) is not int
            or metadata['version'] not in (1,2)
            or metadata.get('definitions')!=(strategic_public_defaults() if metadata['version']==1 else STRATEGY_DEFAULT_SCHEMA_NAME)):
        raise ValueError('macro_default_contract_invalid')
    if metadata['version']==1:
        if set(metadata)!={'version','definitions','catalog','feedback'} or any(type(metadata[k]) is not dict for k in ('catalog','feedback')):
            raise ValueError('macro_default_contract_invalid')
    else:
        if (set(metadata)!={'version','definitions','catalog','feedback','aliases'} or type(metadata['aliases']) is not dict
                or any(alias not in _STRATEGY_ALIASES or _STRATEGY_ALIASES[alias]!=field for alias,field in metadata['aliases'].items())):
            raise ValueError('macro_public_unknown_alias')
        for section in ('macro_policy_catalog',*STRATEGY_FEEDBACK_SECTIONS):
            if section in result:result[section]=_alias_fields(result[section],metadata['aliases'],restore=True)
        names=sorted(result.get('macro_policy_catalog',{}))
        if (type(metadata['catalog']) is not list or len(metadata['catalog'])!=len(names)
                or type(metadata['feedback']) is not list or len(metadata['feedback'])!=len(STRATEGY_FEEDBACK_SECTIONS)):
            raise ValueError('macro_default_contract_invalid')
        for values in (metadata['catalog'],metadata['feedback']):
            if any(type(mask) is not int or mask<0 for mask in values):raise ValueError('macro_default_contract_mask')
        metadata['catalog']={name:mask for name,mask in zip(names,metadata['catalog']) if mask}
        metadata['feedback']={name:mask for name,mask in zip(STRATEGY_FEEDBACK_SECTIONS,metadata['feedback']) if mask}
    for group,definitions in (('catalog',STRATEGY_CATALOG_DEFAULTS),('feedback',STRATEGY_FEEDBACK_DEFAULTS)):
        for name,mask in metadata[group].items():
            if type(mask) is not int or mask<=0 or mask>=(1<<len(definitions)):
                raise ValueError('macro_default_contract_mask')
            if group=='catalog':
                target=result.get('macro_policy_catalog',{}).get(name)
            else:
                if name not in STRATEGY_FEEDBACK_SECTIONS:raise ValueError('macro_default_contract_section')
                target=result.get(name)
            if type(target) is not dict:raise ValueError('macro_default_contract_target')
            for index,definition in enumerate(definitions):
                if not(mask&(1<<index)):continue
                if group=='catalog':
                    domain,path,default=definition
                    if target.get('domain')!=domain:raise ValueError('macro_default_contract_domain')
                else:
                    key,default=definition;path=(key,)
                parent=target
                for key in path[:-1]:
                    if type(parent.get(key)) is not dict:raise ValueError('macro_default_contract_path')
                    parent=parent[key]
                if path[-1] in parent:raise ValueError('macro_default_contract_conflict')
                parent[path[-1]]=default
    return result
