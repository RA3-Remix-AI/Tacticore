"""Read-only client projection; never grants an entry or dispatches work."""
from copy import deepcopy
from .contracts import ContractError
from .macro_delegation_boundary_v1 import KIND as BOUNDARY, STRATEGIC_ACTIONS, validate_policy

KIND = 'commander_strategic_client_record_v1'
UNCONNECTED = ('native_construction_pause', 'native_production_pause', 'resource_expansion')
BUDGETS = ('budgeteconomy', 'budgetarmy', 'budgettech')


def action_list(value):
    if type(value) not in (list, tuple) or len(value) > 64 or any(type(a) is not str for a in value):
        raise ContractError('strategic_client_actions_invalid')
    return list(dict.fromkeys(a for a in value if a in STRATEGIC_ACTIONS))


def preflight_capabilities(capabilities):
    """Current strategic Host admission only; never apply to old journals."""
    if type(capabilities) is not dict or capabilities.get('native_macro') is not True:
        raise ContractError('strategic_client_macro_admission_required')
    result = deepcopy(capabilities)
    result['available_macro_actions'] = action_list(result.get('available_macro_actions', []))
    result['macro_production_counts'] = {}
    result['supported_units'] = []
    result['supported_foci'] = ['native_baseline']
    result['commander_boundary'] = BOUNDARY
    return result


def project(status, capabilities):
    """Caller first validates run/session/host identity through existing RPC."""
    if type(status) is not dict or type(capabilities) is not dict:
        raise ContractError('strategic_client_bound_status_required')
    execution = status.get('execution')
    marker = execution.get('commander_boundary') if type(execution) is dict else None
    boundary = 'strategic_only' if marker == BOUNDARY else 'historical_precision' if marker == 'historical_precision' else 'unverified'
    actions = action_list(capabilities.get('available_macro_actions', [])) if boundary == 'strategic_only' else []
    plan = status.get('current_plan')
    current = None
    intent = 'awaiting'
    if boundary == 'strategic_only' and plan is not None:
        try:
            validate_policy(plan)
            raw = plan['macro_actions']
            from .strategic_contract_v5 import split_intents
            try:split_intents(raw)
            except ValueError:raise ContractError('strategic_client_plan_shape_invalid') from None
            if any(a not in actions for a in raw):
                raise ContractError('strategic_client_unoffered_action')
            current = list(raw)
            intent = 'reported'
        except (ContractError, KeyError, TypeError):
            intent = 'invalid'
    feedback = status.get('macro_feedback')
    adoption = 'unavailable'
    selected = None
    if boundary == 'strategic_only' and type(feedback) is dict:
        states = {'native_budget_adopted': 'adopted', 'native_budget_pending': 'pending',
                  'native_budget_clearing': 'clearing', 'native_delegation_observed': 'not_observed'}
        value, state = feedback.get('selected_policy'), feedback.get('status')
        if type(state) is str and state in states and (value is None or value in BUDGETS):
            adoption, selected = states[state], value
        if adoption in ('adopted', 'pending') and selected is None:
            adoption = 'unavailable'
        if adoption == 'not_observed' and selected is not None:
            adoption, selected = 'unavailable', None
    return dict(schema_version=1, kind=KIND, boundary=boundary, available_actions=actions,
                current_actions=current, current_intent_state=intent, budget_adoption=adoption,
                budget_policy=selected, unconnected_intents=[name for name,action in zip(UNCONNECTED,
                    ('pauseconstruction','pauseproduction','expand')) if action not in actions], details_owner='native_ai',
                record_only=True, dispatch_authorized=False, native_acceptance_proves_success=False,
                extra_preferences_clear_is_global_stop=False)
