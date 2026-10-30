"""Explicit schema4 model projection; never translated into old cash facts."""
from .contracts import ContractError
from .macro_policy_runtime import MacroRequestAudit
from .macro_expansion_feedback import compact_expansion_feedback
from .resource_admission_reservations_v4 import EXCLUSIONS,CLOSED
from .resource_reservations import amount

PUBLIC_KEYS=set(('source','schema_version','status','buffer_semantics','active_buffer_amount','original_ack_independently_known',
    'preference_clear_independently_verified','current_state_reconciliation_verified','current_credits',
    'current_production_upgrade_commitment_upper_bound','current_available_credit_filter','current_financial_shortfall',
    'actual_cash_payment','refund_amount','no_queue_ever_accepted','exclusive_enqueue_causality','latent_native_work_cancelled',
    'excluded_spending','hard_total_spending_limit_verified','new_dispatch_authorized',
    'next_dispatch_requires_fresh_cost_and_financial_state','automatic_retry_allowed','reconciliation_blocked_reason','financial_observation_frames'))
MODEL_EXCLUSIONS=['future_unaccepted_work_including_prior_selected_latent','future_native_autonomous_repair_and_ability_spending']


def compact_admission_feedback_v4(value):
    if type(value) is dict and 'known_ack' in value:
        # Host status may already hold this exact validated model projection.
        # Revalidate its inverse rather than silently accepting arbitrary maps.
        from copy import deepcopy
        restore_admission_feedback_v4(value)
        return deepcopy(value)
    if (type(value) is not dict or set(value)!=PUBLIC_KEYS or value.get('source')!='active_preference_admission_buffer_v4'
            or type(value.get('schema_version')) is not int or value['schema_version']!=4
            or value.get('status') not in ('reserved','delivering','acknowledged','preference_cleared','unknown',CLOSED,'aborted_before_delivery')
            or value.get('buffer_semantics')!='active_preference_buffer_closed_after_current_state_reconciliation'
            or not amount(value.get('active_buffer_amount')) or value.get('excluded_spending')!=list(EXCLUSIONS)
            or any(value.get(key) is not None for key in ('actual_cash_payment','refund_amount','no_queue_ever_accepted','exclusive_enqueue_causality','latent_native_work_cancelled'))
            or any(value.get(key) is not False for key in ('hard_total_spending_limit_verified','new_dispatch_authorized','automatic_retry_allowed'))
            or value.get('next_dispatch_requires_fresh_cost_and_financial_state') is not True
            or any(type(value.get(key)) is not bool for key in ('original_ack_independently_known','preference_clear_independently_verified','current_state_reconciliation_verified'))):
        raise ContractError('macro_admission_v4_feedback_invalid')
    closed=value['status']==CLOSED
    if (value['current_state_reconciliation_verified'] is not closed
            or value['status'] in (CLOSED,'aborted_before_delivery') and value['active_buffer_amount']!=0
            or value['status'] not in (CLOSED,'aborted_before_delivery') and value['active_buffer_amount']<=0
            or value['preference_clear_independently_verified'] and not value['original_ack_independently_known']
            or value['status'] in ('reserved','delivering','aborted_before_delivery') and (value['original_ack_independently_known'] or value['preference_clear_independently_verified'])
            or value['status']=='acknowledged' and (not value['original_ack_independently_known'] or value['preference_clear_independently_verified'])
            or closed and (value['active_buffer_amount']!=0 or not value['original_ack_independently_known'] or not value['preference_clear_independently_verified'])
            or value['status']=='preference_cleared' and (not value['original_ack_independently_known'] or not value['preference_clear_independently_verified'])):
        raise ContractError('macro_admission_v4_feedback_invalid')
    values=('current_credits','current_production_upgrade_commitment_upper_bound','current_available_credit_filter','current_financial_shortfall')
    if any(not amount(value.get(key)) if closed else value.get(key) is not None for key in values):
        raise ContractError('macro_admission_v4_feedback_invalid')
    if closed:
        credits,debt=value[values[0]],value[values[1]]
        if value[values[2]]!=max(0,credits-debt) or value[values[3]]!=max(0,debt-credits):raise ContractError('macro_admission_v4_feedback_invalid')
    frames=value['financial_observation_frames']
    if (closed and (type(frames) is not list or len(frames)!=2 or any(type(frame) is not int or not 0<frame<=0xffffffff for frame in frames)
            or not 0<=frames[1]-frames[0]<=2) or not closed and frames is not None):raise ContractError('macro_admission_v4_feedback_invalid')
    reason=value.get('reconciliation_blocked_reason')
    if closed and reason is not None or reason is not None and (type(reason) is not str or not 1<=len(reason)<=160 or not reason.replace('_','').isalnum()):
        raise ContractError('macro_admission_v4_feedback_invalid')
    keys=('source','schema_version','status','active_buffer_amount')
    result=dict(**{key:value[key] for key in keys},
        known_ack=value['original_ack_independently_known'],independent_clear=value['preference_clear_independently_verified'],
        reconciled_credits=value['current_credits'],reconciled_production_upgrade_debt_upper=value['current_production_upgrade_commitment_upper_bound'],
        reconciled_frames=list(frames) if frames is not None else None,
        unverified_outcomes=['actual_cash_payment','refund','no_queue_ever_accepted','exclusive_enqueue_causality','latent_work_cancelled'],
        excluded_spending=list(MODEL_EXCLUSIONS),hard_spending_cap_verified=False,dispatch_authorized=False,
        next_requires_fresh_cost_and_state=True,automatic_retry=False)
    if reason is not None:result['reconciliation_blocked_reason']=reason
    return result


def restore_admission_feedback_v4(value):
    """Exact inverse; only deterministic/redundant fields use schema defaults."""
    if (type(value) is not dict or value.get('source')!='active_preference_admission_buffer_v4'
            or type(value.get('schema_version')) is not int or value['schema_version']!=4):raise ContractError('macro_admission_v4_feedback_invalid')
    raw=dict(value);raw.pop('unverified_outcomes',None)
    raw['buffer_semantics']='active_preference_buffer_closed_after_current_state_reconciliation'
    raw['original_ack_independently_known']=raw.pop('known_ack',None)
    raw['preference_clear_independently_verified']=raw.pop('independent_clear',None)
    raw['current_credits']=raw.pop('reconciled_credits',None)
    raw['current_production_upgrade_commitment_upper_bound']=raw.pop('reconciled_production_upgrade_debt_upper',None)
    raw['financial_observation_frames']=raw.pop('reconciled_frames',None)
    if raw.get('excluded_spending')!=MODEL_EXCLUSIONS:raise ContractError('macro_admission_v4_feedback_invalid')
    raw['excluded_spending']=list(EXCLUSIONS)
    for public,compact in (('hard_total_spending_limit_verified','hard_spending_cap_verified'),
            ('new_dispatch_authorized','dispatch_authorized'),('next_dispatch_requires_fresh_cost_and_financial_state','next_requires_fresh_cost_and_state'),
            ('automatic_retry_allowed','automatic_retry')):
        raw[public]=raw.pop(compact,None)
    closed=raw.get('status')==CLOSED;raw['current_state_reconciliation_verified']=closed
    credits,debt=raw.get('current_credits'),raw.get('current_production_upgrade_commitment_upper_bound')
    if closed and (not amount(credits) or not amount(debt)):raise ContractError('macro_admission_v4_feedback_invalid')
    raw['current_available_credit_filter']=max(0,credits-debt) if closed else None
    raw['current_financial_shortfall']=max(0,debt-credits) if closed else None
    raw.setdefault('reconciliation_blocked_reason',None)
    for key in ('actual_cash_payment','refund_amount','no_queue_ever_accepted','exclusive_enqueue_causality','latent_native_work_cancelled'):raw[key]=None
    if compact_admission_feedback_v4(raw)!=value:raise ContractError('macro_admission_v4_feedback_invalid')
    if set(raw)!=PUBLIC_KEYS:raise ContractError('macro_admission_v4_feedback_invalid')
    return raw


class MacroRequestAuditV4(MacroRequestAudit):
    def _expansion_context(self,context):
        result=dict(context)
        if self.expansion_supplier is not None:
            value=self.expansion_supplier()
            if value is not None:result['macro_expansion_feedback']=compact_expansion_feedback(value,context['game_time_seconds'])
        if self.resource_supplier is not None:
            value=self.resource_supplier()
            if value is not None:result['macro_resource_feedback']=compact_admission_feedback_v4(value)
        return result
