"""Bounded public records of expansion and admission; never execution grants."""
from .contracts import ContractError
from .macro_expansion_feedback import compact_expansion_feedback
from .macro_admission_feedback_v4 import compact_admission_feedback_v4
from .resource_admission_reservations_v4 import CLOSED

EVENTS_V4 = frozenset((
    'model_macro_expansion_prepared', 'model_macro_expansion_acknowledged',
    'model_macro_expansion_delivery_prepared', 'macro_expansion_feedback',
    'macro_expansion_preference_released', 'macro_resource_feedback',
    'macro_admission_current_state_reconciled', 'macro_admission_request_not_delivered'))
WORK = frozenset(('buildpower', 'buildbarracks', 'buildfactory', 'buildrefinery',
                  'buildbattlelab', 'producesickle', 'producebullfrog'))
BUDGET = frozenset(('budgeteconomy', 'budgetarmy', 'budgettech'))
UNVERIFIED = ('budget_hard_cap_verified', 'exact_queue_to_object_link_verified',
              'payment_verified', 'unit_exit_verified', 'technology_unlock_verified',
              'exclusive_macro_attribution_verified', 'automatic_retry_allowed')


def fail():
    raise ContractError('macro_expansion_diagnostics_invalid')


def expansion_record(value):
    if type(value) is not dict or any(value.get(key) is not False for key in UNVERIFIED):
        fail()
    frames = [value.get(key) for key in ('builder_frame', 'own_census_frame')]
    if any(type(frame) is not int or not 0 < frame <= 0xffffffff for frame in frames):
        fail()
    result = compact_expansion_feedback(value, max(frames) / 15)
    if result.get('resource_reservation_verified') is not False:
        fail()
    for key in ('observed_queue_cost_sum', 'observed_paid_field_sum'):
        if result[key] > 2**53 - 1:
            fail()
    result['record_only'] = True
    result['global_native_release_verified'] = False
    return result


def admission_record(value):
    result = compact_admission_feedback_v4(value)
    for key in ('active_buffer_amount', 'reconciled_credits', 'reconciled_production_upgrade_debt_upper'):
        if result[key] is not None and result[key] > 2**53 - 1:
            fail()
    # Only the existence of a blocked condition is exported. No exception or
    # caller-supplied reason string enters a downloadable diagnostic.
    result['reconciliation_waiting'] = result.pop('reconciliation_blocked_reason', None) is not None
    result['record_only'] = True
    result['global_native_release_verified'] = False
    return result


def project_expansion_event_v4(kind, payload):
    if kind not in EVENTS_V4 or type(payload) is not dict:
        fail()
    if kind == 'macro_expansion_feedback':
        return expansion_record(payload)
    if kind == 'macro_expansion_preference_released':
        return expansion_record(payload.get('feedback'))
    if kind in ('macro_resource_feedback', 'macro_admission_current_state_reconciled'):
        result = admission_record(payload if kind == 'macro_resource_feedback' else payload.get('admission_buffer'))
        if kind == 'macro_admission_current_state_reconciled' and result['status'] != CLOSED:
            fail()
        return result
    if kind == 'macro_admission_request_not_delivered':
        # This remains a host record. Only the independent raw reviewer can
        # verify non-publication and exempt the durable row from a ledger.
        return dict(record_only=True, reported_not_delivered=True,
                    native_nonpublication_independently_verified=False,
                    global_native_release_verified=False)
    actions = payload.get('actions')
    if (payload.get('admission_schema_version') != 4 or type(payload.get('admission_schema_version')) is not int
            or type(actions) is not list or not 1 <= len(actions) <= 2
            or any(type(action) is not str or action not in WORK | BUDGET for action in actions)
            or len(set(actions)) != len(actions) or sum(action in WORK for action in actions) != 1
            or kind != 'model_macro_expansion_delivery_prepared'
            and (type(payload.get('additional_count')) is not int or payload['additional_count'] != 1)):
        fail()
    result = dict(actions=list(actions), admission_schema_version=4,
                  record_only=True, native_effect_verified=False, global_native_release_verified=False)
    if kind != 'model_macro_expansion_delivery_prepared':result['additional_count']=1
    if kind == 'model_macro_expansion_acknowledged':
        if (payload.get('native_gate_acknowledged') is not True or payload.get('native_effect_verified') is not False
                or type(payload.get('seq')) is not int or not 1 <= payload['seq'] <= 2047):
            fail()
        result.update(seq=payload['seq'], native_gate_acknowledged=True)
    return result
