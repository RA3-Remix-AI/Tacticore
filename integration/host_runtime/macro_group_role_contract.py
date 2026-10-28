"""Bounded high-level role meanings; these constants grant no native capability."""
from .macro_base_defense_scope import defense_catalog_override

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
