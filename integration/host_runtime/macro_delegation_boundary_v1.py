"""User-authorized strategic boundary, shared by request and dispatch gates.

This can only remove authority from an already qualified native scope. It never
maps broad intent to an exact building, unit template, quantity or unit order.
"""
import copy

from .contracts import ContractError

KIND = 'native_ai_details_v1'
STRATEGIC_ACTIONS = frozenset({
    'budgeteconomy', 'budgetarmy', 'budgettech', 'scout',
    'deployattack', 'deploydefense', 'regroup', 'withdraw', 'reinforce',
    'expand', 'pauseconstruction', 'advanceconstruction', 'pauseproduction', 'advanceproduction',
})


def strategic_actions(actions):
    return tuple(action for action in actions if action in STRATEGIC_ACTIONS)


def restrict_snapshot(snapshot):
    result = copy.deepcopy(snapshot)
    control = result.get('macro_control')
    if type(control) is not dict:
        raise ContractError('strategic_boundary_macro_control_required')
    control['available_actions'] = list(strategic_actions(control['available_actions']))
    control['production_counts'] = {}
    if 'region_targets' in control:
        control['region_targets'] = {key: value for key, value in control['region_targets'].items()
                                     if key in control['available_actions']}
    result['capabilities']['production_focus'] = ['native_baseline']
    return result


def restrict_context(context):
    result = copy.deepcopy(context)
    actions = strategic_actions(result.get('allowed_macro_actions', ()))
    result['allowed_macro_actions'] = list(actions)
    result['allowed_production_focus'] = ['native_baseline']
    result['macro_policy_catalog'] = {key: value for key, value in result.get('macro_policy_catalog', {}).items()
                                      if key in actions}
    # Keep legitimate own infrastructure/forces and strategic observations,
    # but do not spend model input on precise queue/monetary execution contracts.
    for key in ('macro_production_feedback', 'macro_construction_feedback',
                'macro_expansion_feedback', 'macro_resource_feedback'):
        result.pop(key, None)
    battlefield = result.get('working_memory', {}).get('battlefield')
    if (type(battlefield) is dict and type(battlefield.get('contacts')) is list
            and (battlefield['contacts'] or 'contact_groups' not in battlefield)):
        # Strategic decisions need lawful concentrations and observation ages,
        # not individually addressable targets. Keep visible/last-seen groups
        # separate and both age bounds; never rejuvenate an old observation.
        groups = {}
        for row in battlefield['contacts']:
            key = (row['region_id'], row['role'], row['relation'], row['currently_visible'])
            at = row['observed_at_game_seconds']
            if key not in groups:
                groups[key] = dict(region_id=key[0], role=key[1], relation=key[2],
                    currently_visible=key[3], observations=0, oldest_game_seconds=at, newest_game_seconds=at)
            group = groups[key]
            group['observations'] += 1
            group['oldest_game_seconds'] = min(group['oldest_game_seconds'], at)
            group['newest_game_seconds'] = max(group['newest_game_seconds'], at)
        battlefield['contacts'] = []
        battlefield['contact_groups'] = list(groups.values())
    result['native_delegation'] = dict(
        kind=KIND, details_owner='native_ai',
        construction_and_production='native_ai_selects_and_executes',
        empty_actions='release_extra_preferences_not_global_native_stop',
        budget_actions='priority_preferences_not_construction_or_expansion_permission',
        exact_templates_quantities_coordinates_unit_orders=False,
    )
    strategy = result.get('macro_strategy')
    if type(strategy) is dict and type(strategy.get('fact_catalog')) is dict:
        if 'capabilities.actions' in strategy['fact_catalog']:
            strategy['fact_catalog']['capabilities.actions'] = list(actions)
    return result


def validate_policy(policy):
    value = policy.public() if hasattr(policy, 'public') else policy
    if type(value) is not dict:
        raise ContractError('strategic_boundary_policy_required')
    actions = value.get('macro_actions')
    if (type(actions) not in (list, tuple)
            or any(type(action) is not str or action not in STRATEGIC_ACTIONS for action in actions)):
        raise ContractError('strategic_boundary_detailed_action_refused')
    if value.get('macro_production') is not None:
        raise ContractError('strategic_boundary_quantity_refused')
    if value.get('production_focus') != 'native_baseline':
        raise ContractError('strategic_boundary_composition_refused')
    if value.get('tactical_tasks') not in (None, [], ()) or value.get('runtime_task') is not None:
        raise ContractError('strategic_boundary_unit_orders_refused')
    return policy
