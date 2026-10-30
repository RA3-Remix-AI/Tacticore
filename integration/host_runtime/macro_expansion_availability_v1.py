"""Bounded last-check reasons for display; never a current dispatch permit."""
from .contracts import ContractError

ACTIONS=('buildpower','buildbarracks','buildfactory','buildrefinery','buildbattlelab','producesickle','producebullfrog')
REASONS={
    'macro_admission_v4_insufficient_current_funds':'insufficient_funds',
    'macro_expansion_unique_ready_producer_required':'producer_unready',
    'macro_admission_v4_active_buffer_unresolved':'previous_request_pending',
    'macro_resource_reservation_unresolved':'previous_request_pending',
}


def availability_record(value):
    if type(value) is not dict or len(value)>len(ACTIONS):raise ContractError('macro_expansion_availability_invalid')
    if any(type(action) is not str or action not in ACTIONS or type(reason) is not str or not 1<=len(reason)<=160
           for action,reason in value.items()):raise ContractError('macro_expansion_availability_invalid')
    return dict(schema_version=1,kind='macro_expansion_availability_record_v1',
        entries=[dict(action=action,reason=REASONS.get(value[action],'unverified')) for action in ACTIONS if action in value],
        record_only=True,dispatch_authorized=False,automatic_retry=False,payment_verified=False,global_native_release_verified=False)
