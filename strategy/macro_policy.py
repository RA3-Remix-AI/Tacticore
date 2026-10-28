"""Pure macro intent contract. Capability lists come from trusted host evidence."""
from dataclasses import dataclass, asdict

ACTIONS={
    'build_airfield':'construction','buildreactor':'construction','buildtech':'construction','economyrefinery':'construction',
    'produceconscript':'production','produceflak':'production','producetank':'production',
    'budgeteconomy':'budget','budgetarmy':'budget','budgettech':'budget',
    'deployattack':'deployment','deploydefense':'deployment','scout':'scouting',
    'regroup':'deployment','withdraw':'deployment','reinforce':'deployment'}
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
                for values in counts.values())):
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
    if sum(domain in ('construction','production','scouting','deployment') for domain in domains)>1:
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
    return ProductionQuantity(raw['action'],raw['additional_count'])


def public_descriptions(actions,counts=None,region_targets=None):
    return {action:dict(domain=ACTIONS[action],
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
            **(dict(allowed_additional_counts=list(dict(counts)[action])) if counts is not None else dict(additional_count_min=1,additional_count_max=3)),
            control_basis='new_native_queue_acceptances',completed_units_guaranteed=False,
            replacement_requires_new_decision=True)} if ACTIONS[action]=='production' else {}),
        **({'control_basis':'one_native_construction_preference',
            'release_on':'first_new_matching_queue_or_expiry',
            'construction_completed_guaranteed':False,'native_ai_selects_placement_and_build_execution':True,
            'native_opening_and_prerequisite_gates_remain_active':True,
            **({'building':'super_reactor','observed_native_queue_cost':2000,
                'cost_source':'qualified_native_queue_observation','supports_native_production_action':'producetank',
                'resource_semantics':'native_queue_uses_incremental_payment_not_full_upfront_charge'} if action=='buildreactor' else {}),
            'retry_requires_new_decision':True} if ACTIONS[action]=='construction' else {})) for action in actions}
