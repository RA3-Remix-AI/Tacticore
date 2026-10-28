"""Bounded production observations for model requests; no private identities."""
from .contracts import ContractError
from .macro_production_feedback import TARGETS

COUNTS=('additional_count_requested','observed_new_queue_count','additional_queue_observations_after_release',
        'fully_paid_queue_observations','new_own_unit_observations','available_producer_count',
        'incomplete_queues_with_unavailable_producer')
BOOLS=('queue_target_observed','queue_target_overshot','producer_unavailable_observed','policy_released')
STATUSES={'native_production_partial_producer_unavailable','native_production_producer_unavailable',
          'native_production_queue_target_observed','native_production_pending'}
REASONS={None,'queue_target_observed','producer_unavailable','scope_changed','expired','stopped'}


def compact_production_feedback(value,game_seconds):
    if (type(value) is not dict or value.get('action') not in TARGETS or value.get('status') not in STATUSES
            or value.get('release_reason') not in REASONS
            or any(type(value.get(key)) is not int or not 0<=value[key]<=100000 for key in COUNTS)
            or not 1<=value['additional_count_requested']<=3
            or any(type(value.get(key)) is not bool for key in BOOLS)
            or any(type(value.get(key)) is not int or not 0<value[key]<=0xffffffff
                   or not -15<=game_seconds*15-value[key]<=30 for key in ('builder_frame','own_census_frame'))):
        raise ContractError('macro_production_feedback_invalid_or_stale')
    return dict(source='native_production_observation',action=value['action'],status=value['status'],
        release_reason=value['release_reason'],**{key:value[key] for key in (*COUNTS,*BOOLS,'builder_frame','own_census_frame')},
        count_control_basis='new_native_queue_acceptances',completed_units_verified=False,
        exact_queue_to_unit_link_verified=False,exclusive_macro_attribution_verified=False,
        payment_verified=False,automatic_retry_allowed=False,unit_operation_policy='native_ai')
