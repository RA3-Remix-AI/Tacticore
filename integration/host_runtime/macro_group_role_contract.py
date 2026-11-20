"""Bounded high-level role meanings; these constants grant no native capability."""
GOAL='original_native_defense_of_own_infrastructure'


def defense_catalog_override():
    return dict(deploydefense=dict(domain='deployment',exclusive_with_other_construction_or_production=True,
        target_region='region_8_3',goal=GOAL,target_policy='original_native_friendly_land_structure',
        region_semantics='eastern_home_base_anchor_not_a_specific_structure_or_move_destination',
        maximum_duration_seconds=60,native_ai_selects_structure_and_operates_group=True,
        legacy_action_name_is_not_mission_purpose=False,arrival_and_mission_success_guaranteed=False))


HOME_REGION='region_8_3'
ROLE_GOALS={
    'regroup':'regroup_native_force_at_own_home_waypoint',
    'withdraw':'withdraw_native_group_to_own_home_region',
    'reinforce':'reinforce_own_base_through_original_reactive_defense'}
ROLE_FAMILIES={'regroup':'simple_attack','withdraw':'simple_attack','reinforce':'reactive_defense'}


def group_role_catalog_overrides():
    result=defense_catalog_override()
    for action,goal in ROLE_GOALS.items():
        infrastructure=action=='reinforce'
        result[action]=dict(domain='deployment',exclusive_with_other_construction_or_production=True,
            target_region=HOME_REGION,goal=goal,
            target_policy='original_native_most_recently_attacked_own_base' if infrastructure else 'fixed_public_own_home_start_waypoint',
            region_semantics='eastern_home_base_anchor_native_base_selection' if infrastructure else 'fixed_public_own_home_region',
            maximum_duration_seconds=60,native_ai_selects_and_operates_group=True,
            native_unit_operations_unchanged=True,arrival_and_mission_success_guaranteed=False,
            requires_existing_forward_force=action=='withdraw',
            all_units_or_physical_home_return_guaranteed=False,
            arbitrary_unit_selection_supported=False)
    return result


def home_group_role_catalog_overrides(home_region):
    from .contracts import ContractError
    from .scenario import is_region

    # Any runtime-derived own region; the live own-base origin check binds it.
    if not is_region(home_region):
        raise ContractError('macro_base_defense_catalog_region_binding')
    result = group_role_catalog_overrides()
    for description in result.values():
        description['target_region'] = home_region
    result['deploydefense']['region_semantics'] = 'own_home_base_anchor_not_a_specific_structure_or_move_destination'
    result['reinforce']['region_semantics'] = 'own_home_base_anchor_native_base_selection'
    return result


def home_strategic_catalog_overrides(home_region):
    from native_unified_contract_v5 import additional_catalog

    result = home_group_role_catalog_overrides(home_region)
    result['expand'] = dict(additional_catalog(('expand',))['expand'],
                            native_expansion_interval_seconds=240)
    return result
