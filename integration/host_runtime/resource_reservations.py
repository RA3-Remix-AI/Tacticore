"""Trusted backend resource facts and a single unresolved product reservation.

This module does no I/O and accepts no model/RPC dictionaries. Source strings
identify reviewed backend readers; callers must inject those readers explicitly.
Native AI's own concurrent spending is never a host-enforced global budget.
"""
from dataclasses import asdict,dataclass
import copy
import math
import json
from typing import Protocol
import uuid
import threading
from functools import wraps

from .contracts import ContractError

COST_SOURCE='native_read_only_target_upper_cost_and_player_resources_v2'
CURRENT_QUEUE_BUDGET_SOURCE='native_current_owned_production_upgrade_queue_budget_v3'
SETTLEMENT_SOURCES={
    'queue_accepted':'native_bound_queue_acceptance_v1',
    'payment_consumed':'native_bound_queue_cash_payment_v1',
    'queue_cancelled':'native_cancelled_queue_cash_settlement_v1',
    'preference_cleared':'native_independent_twenty_flag_clear_v1',
    'no_queue_accepted':'native_complete_request_acceptance_audit_v1',
    'refund_observed':'native_bound_queue_cash_refund_v1'}
TERMINAL=('consumed','cancelled','released_without_queue','aborted_before_delivery')


def positive(value):return type(value) is int and 0<value<=0xffffffff
def amount(value):return type(value) is int and 0<=value<=0xffffffff
def token(value):return type(value) is str and 0<len(value)<=128 and all(ord(c)>=32 for c in value)
def fingerprint(value):return json.loads(json.dumps(asdict(value),allow_nan=False))
def pointer(value):
    try:return type(value) is str and value==hex(int(value,0)) and 0x10000<=int(value,0)<=0x7ffefffc and int(value,0)%4==0
    except ValueError:return False
def serialized(method):
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        with self._lock:return method(self,*args,**kwargs)
    return wrapped


@dataclass(frozen=True)
class NativeCostFact:
    """Complete existing same-wallet payment obligations, not bank forecasts.

The commitment is not an engine hard lock already removed from credits. It is
a conservative upper bound of obligations that may still draw this balance.
"""
    session_id:str
    player_id:int
    action:str
    template_hash:str
    source:str
    frame:int
    upper_cost:int
    credits:int
    existing_native_payment_commitment_upper_bound:int
    game_identity:tuple
    upper_cost_verified:bool=False
    credits_verified:bool=False
    existing_native_payment_commitment_upper_bound_verified:bool=False
    additional_count:int=1


@dataclass(frozen=True)
class CurrentQueueBudgetFact:
    """Narrow current-credit filter; future autonomous/repair/ability spend excluded."""
    session_id:str
    player_id:int
    action:str
    template_hash:str
    source:str
    frame:int
    upper_cost:int
    credits:int
    production_upgrade_queue_payment_commitment_upper_bound:int
    game_identity:tuple
    producer_thing_id:int
    producer_type_hash:str
    upper_cost_verified:bool=False
    credits_verified:bool=False
    production_upgrade_queue_payment_commitment_upper_bound_verified:bool=False
    all_owned_production_updates_observed:bool=False
    all_production_and_upgrade_nodes_observed:bool=False
    loaded_target_schema_verified:bool=False
    native_quote_context_verified:bool=False
    producer_definition_verified:bool=False
    single_new_request_hard_limit_verified:bool=False
    native_ai_autonomous_spending_covered:bool=False
    repair_and_ability_spending_covered:bool=False
    additional_count:int=1


class CostSupplier(Protocol):
    def __call__(self,action:str,sample:dict,game_seconds:float)->NativeCostFact|CurrentQueueBudgetFact:...


def commitment(fact):
    return fact.existing_native_payment_commitment_upper_bound if type(fact) is NativeCostFact else fact.production_upgrade_queue_payment_commitment_upper_bound


def validate_cost(fact,*,session_id,player_id,action,template_hash,game_identity,game_seconds,component_frames=(),producer_ids=()):
    from .macro_expansion_scope import TARGETS
    if type(fact) not in (NativeCostFact,CurrentQueueBudgetFact):raise ContractError('blocked_native_cost_reservation_unverified')
    narrow=type(fact) is CurrentQueueBudgetFact
    if (fact.source!=(CURRENT_QUEUE_BUDGET_SOURCE if narrow else COST_SOURCE)
            or fact.session_id!=session_id or fact.player_id!=player_id or type(fact.player_id) is not int or player_id!=3
            or action not in TARGETS or TARGETS[action][0]!=template_hash
            or fact.action!=action or fact.template_hash!=template_hash or fact.game_identity!=tuple(game_identity)
            or type(fact.game_identity) is not tuple or len(fact.game_identity)!=3 or not all(pointer(value) for value in fact.game_identity)
            or type(fact.additional_count) is not int or fact.additional_count!=1
            or fact.upper_cost_verified is not True or fact.credits_verified is not True
            or not positive(fact.upper_cost) or not amount(fact.credits) or not amount(commitment(fact))
            or commitment(fact)>fact.credits or not positive(fact.frame)
            or type(game_seconds) not in (float,int) or not math.isfinite(game_seconds)
            or not -15<=game_seconds*15-fact.frame<=15
            or any(not positive(frame) for frame in component_frames)
            or max((fact.frame,*component_frames))-min((fact.frame,*component_frames))>15):
        raise ContractError('blocked_native_cost_reservation_unverified')
    if narrow:
        if (any(getattr(fact,key) is not True for key in ('production_upgrade_queue_payment_commitment_upper_bound_verified',
                'all_owned_production_updates_observed','all_production_and_upgrade_nodes_observed',
                'loaded_target_schema_verified','native_quote_context_verified','producer_definition_verified'))
                or not positive(fact.producer_thing_id) or tuple(producer_ids)!=(fact.producer_thing_id,)
                or fact.producer_type_hash!=TARGETS[action][1]
                or any(getattr(fact,key) is not False for key in ('single_new_request_hard_limit_verified',
                    'native_ai_autonomous_spending_covered','repair_and_ability_spending_covered'))):
            raise ContractError('blocked_native_cost_reservation_unverified')
    elif fact.existing_native_payment_commitment_upper_bound_verified is not True:
        raise ContractError('blocked_native_cost_reservation_unverified')
    if fact.upper_cost>fact.credits-commitment(fact):
        raise ContractError('macro_resource_insufficient_unreserved_credits')
    return fact


@dataclass(frozen=True)
class ResourceSettlementFact:
    fact_id:str
    session_id:str
    player_id:int
    plan_id:str
    command_id:str
    action:str
    template_hash:str
    kind:str
    source:str
    frame:int
    native_seq:int
    verified:bool=False
    queue_key:tuple|None=None
    native_cost:int|None=None
    paid_amount:int|None=None
    cash_attribution_verified:bool=False
    clear_seq:int|None=None
    refund_amount:int|None=None


class ResourceReservationStore:
    """One outstanding reservation; unresolved delivery is permanently retained.

persist(snapshot), when supplied, runs before committing state. A production
backend can journal these snapshots before any native delivery. Recovered
nonterminal records become unknown and cannot authorize another delivery.
"""
    def __init__(self,session_id,*,persist=None):
        if not token(session_id):raise ContractError('macro_resource_session_required')
        self.session_id=session_id;self.persist=persist;self.rows={};self.fact_ids={};self._lock=threading.RLock()

    @serialized
    def snapshot(self):
        return copy.deepcopy(dict(schema_version=2,session_id=self.session_id,rows=self.rows,fact_ids=self.fact_ids))

    def _commit(self,rows,fact_ids=None):
        snapshot=dict(schema_version=2,session_id=self.session_id,rows=rows,
            fact_ids=self.fact_ids if fact_ids is None else fact_ids)
        if self.persist is not None:self.persist(copy.deepcopy(snapshot))
        self.rows=rows;self.fact_ids=snapshot['fact_ids']

    @classmethod
    def from_snapshot(cls,value,*,persist=None):
        if (type(value) is dict and type(value.get('schema_version')) is int and value['schema_version']==1
                and value.get('rows')=={} and value.get('fact_ids')=={}):value=dict(value,schema_version=2)
        elif type(value) is dict and value.get('schema_version')==1:
            raise ContractError('macro_resource_legacy_cost_semantics_unverified')
        if (type(value) is not dict or set(value)!={'schema_version','session_id','rows','fact_ids'}
                or type(value['schema_version']) is not int or value['schema_version']!=2
                or type(value['rows']) is not dict or type(value['fact_ids']) is not dict
                or len(value['rows'])>2047 or len(value['fact_ids'])>32768):
            raise ContractError('macro_resource_snapshot_invalid')
        result=cls(value['session_id'],persist=persist)
        rows=copy.deepcopy(value['rows'])
        for command_id,row in rows.items():
            fields={'session_id','plan_id','command_id','action','template_hash','player_id','cost_fact','upper_cost','status',
                'native_seq','queue_key','native_cost','paid_amount','preference_cleared','cancelled','no_queue_verified',
                'refund_amount','last_frame'}
            if (type(row) is not dict or set(row)!=fields or row.get('command_id')!=command_id or row.get('session_id')!=result.session_id
                    or not token(row.get('plan_id')) or not positive(row.get('upper_cost'))
                    or row.get('status') not in (*TERMINAL,'reserved','delivering','acknowledged','queue_accepted','unknown')):
                raise ContractError('macro_resource_snapshot_invalid')
            try:
                raw=dict(row['cost_fact']);raw['game_identity']=tuple(raw['game_identity'])
                fact=(CurrentQueueBudgetFact if raw.get('source')==CURRENT_QUEUE_BUDGET_SOURCE else NativeCostFact)(**raw)
                validate_cost(fact,session_id=result.session_id,player_id=3,action=row['action'],template_hash=row['template_hash'],
                    game_identity=fact.game_identity,game_seconds=fact.frame/15,
                    producer_ids=(fact.producer_thing_id,) if type(fact) is CurrentQueueBudgetFact else ())
            except (TypeError,KeyError,ValueError):raise ContractError('macro_resource_snapshot_invalid') from None
            if (fact.upper_cost!=row['upper_cost'] or type(row['player_id']) is not int or row['player_id']!=3
                    or not positive(row['last_frame']) or row['last_frame']<fact.frame
                    or any(type(row[key]) is not bool for key in ('preference_cleared','cancelled','no_queue_verified'))
                    or row['native_seq'] is not None and (not positive(row['native_seq']) or row['native_seq']>2047)
                    or not amount(row['paid_amount']) or row['refund_amount'] is not None and (
                        not amount(row['refund_amount']) or row['refund_amount']>row['paid_amount'])):
                raise ContractError('macro_resource_snapshot_invalid')
            if row['queue_key'] is not None:
                if (type(row['queue_key']) not in (list,tuple) or len(row['queue_key'])!=2
                        or not all(positive(v) for v in row['queue_key']) or not positive(row['native_cost'])
                        or not row['paid_amount']<=row['native_cost']<=row['upper_cost']):
                    raise ContractError('macro_resource_snapshot_invalid')
                row['queue_key']=tuple(row['queue_key'])
            elif row['native_cost'] is not None or row['paid_amount']!=0 or row['cancelled']:
                raise ContractError('macro_resource_snapshot_invalid')
            if (row['status'] in ('acknowledged','queue_accepted','consumed','cancelled','released_without_queue') and row['native_seq'] is None
                    or row['status'] in ('consumed','cancelled','released_without_queue') and not row['preference_cleared']
                    or row['status']=='consumed' and (row['native_cost'] is None or row['paid_amount']!=row['native_cost'])
                    or row['status']=='cancelled' and not row['cancelled']
                    or row['status']=='released_without_queue' and (not row['no_queue_verified'] or row['queue_key'] is not None)):
                raise ContractError('macro_resource_snapshot_invalid')
            try:
                if str(uuid.UUID(command_id))!=command_id:raise ValueError()
            except (ValueError,TypeError,AttributeError):raise ContractError('macro_resource_snapshot_invalid') from None
            if row['status'] not in TERMINAL:row['status']='unknown'
        if sum(row['status'] not in TERMINAL for row in rows.values())>1:
            raise ContractError('macro_resource_snapshot_invalid')
        if len({row['plan_id'] for row in rows.values()})!=len(rows):raise ContractError('macro_resource_snapshot_invalid')
        for fact_id,raw in value['fact_ids'].items():
            try:
                restored=dict(raw)
                if restored.get('queue_key') is not None:restored['queue_key']=tuple(restored['queue_key'])
                fact=ResourceSettlementFact(**restored);row=rows[fact.command_id]
            except (KeyError,TypeError,ValueError):raise ContractError('macro_resource_snapshot_invalid') from None
            if (not token(fact_id) or fact.fact_id!=fact_id or fact.verified is not True
                    or fact.kind not in SETTLEMENT_SOURCES or fact.source!=SETTLEMENT_SOURCES[fact.kind]
                    or not positive(fact.frame) or not positive(fact.native_seq) or fact.native_seq>2047
                    or any(getattr(fact,key)!=row[key] for key in ('session_id','player_id','plan_id','command_id','action','template_hash'))):
                raise ContractError('macro_resource_snapshot_invalid')
        result.rows=rows;result.fact_ids=copy.deepcopy(value['fact_ids']);return result

    @property
    @serialized
    def unresolved(self):return any(row['status'] not in TERMINAL for row in self.rows.values())

    @serialized
    def can_reserve(self,fact):
        if self.unresolved:raise ContractError('macro_resource_reservation_unresolved')
        if type(fact) not in (NativeCostFact,CurrentQueueBudgetFact) or fact.session_id!=self.session_id:
            raise ContractError('blocked_native_cost_reservation_unverified')
        return True

    @serialized
    def reserve(self,plan_id,command_id,fact):
        if not token(plan_id):raise ContractError('macro_resource_plan_required')
        try:
            if str(uuid.UUID(command_id))!=command_id:raise ValueError()
        except (ValueError,TypeError,AttributeError):raise ContractError('macro_resource_command_required') from None
        cost_fingerprint=fingerprint(fact) if type(fact) in (NativeCostFact,CurrentQueueBudgetFact) else None
        if command_id in self.rows:
            row=self.rows[command_id]
            if row['plan_id']!=plan_id or row['cost_fact']!=cost_fingerprint:raise ContractError('macro_resource_id_conflict')
            return copy.deepcopy(row)
        self.can_reserve(fact)
        if len(self.rows)>=2047:raise ContractError('macro_resource_reservation_limit')
        validate_cost(fact,session_id=self.session_id,player_id=3,action=fact.action,template_hash=fact.template_hash,
            game_identity=fact.game_identity,game_seconds=fact.frame/15,
            producer_ids=(fact.producer_thing_id,) if type(fact) is CurrentQueueBudgetFact else ())
        if any(row['plan_id']==plan_id for row in self.rows.values()):raise ContractError('macro_resource_id_conflict')
        row=dict(session_id=self.session_id,plan_id=plan_id,command_id=command_id,action=fact.action,
            template_hash=fact.template_hash,player_id=3,cost_fact=cost_fingerprint,upper_cost=fact.upper_cost,status='reserved',
            native_seq=None,queue_key=None,native_cost=None,paid_amount=0,preference_cleared=False,
            cancelled=False,no_queue_verified=False,refund_amount=None,last_frame=fact.frame)
        rows=copy.deepcopy(self.rows);rows[command_id]=row;self._commit(rows);return copy.deepcopy(row)

    @serialized
    def _transition(self,command_id,allowed,status,**fields):
        row=self.rows.get(command_id)
        if row is None or row['status'] not in allowed:raise ContractError('macro_resource_transition_refused')
        rows=copy.deepcopy(self.rows);rows[command_id].update(status=status,**fields);self._commit(rows)

    def delivery_started(self,command_id):self._transition(command_id,('reserved',),'delivering')
    def delivery_unknown(self,command_id):self._transition(command_id,('delivering','acknowledged','queue_accepted'),'unknown')
    def acknowledged(self,command_id,seq):
        if not positive(seq) or seq>2047:raise ContractError('macro_resource_native_sequence_required')
        self._transition(command_id,('delivering',),'acknowledged',native_seq=seq)
    def abort_before_delivery(self,command_id):
        self._transition(command_id,('reserved',),'aborted_before_delivery')

    @serialized
    def settle(self,fact):
        if type(fact) is not ResourceSettlementFact:raise ContractError('macro_resource_settlement_unverified')
        fact_fingerprint=fingerprint(fact)
        if fact.fact_id in self.fact_ids:
            if self.fact_ids[fact.fact_id]!=fact_fingerprint:raise ContractError('macro_resource_fact_id_conflict')
            return self.public(fact.command_id)
        if len(self.fact_ids)>=32768:raise ContractError('macro_resource_fact_limit')
        row=self.rows.get(fact.command_id)
        if (row is None or row['status'] not in ('acknowledged','queue_accepted')
                and not (row['status']=='cancelled' and fact.kind=='refund_observed')
                or not token(fact.fact_id) or fact.verified is not True or fact.kind not in SETTLEMENT_SOURCES
                or fact.source!=SETTLEMENT_SOURCES[fact.kind] or not positive(fact.frame) or fact.frame<row['last_frame']
                or type(fact.native_seq) is not int or fact.native_seq!=row['native_seq']
                or any(getattr(fact,key)!=row[key] for key in ('session_id','player_id','plan_id','command_id','action','template_hash'))):
            raise ContractError('macro_resource_settlement_unverified')
        updated=copy.deepcopy(row)
        if fact.kind in ('queue_accepted','payment_consumed','queue_cancelled'):
            if fact.clear_seq is not None or fact.refund_amount is not None:
                raise ContractError('macro_resource_settlement_shape')
        elif fact.kind in ('preference_cleared','no_queue_accepted'):
            if (any(value is not None for value in (fact.queue_key,fact.native_cost,fact.paid_amount,fact.refund_amount))
                    or fact.cash_attribution_verified is not False or fact.kind=='no_queue_accepted' and fact.clear_seq is not None):
                raise ContractError('macro_resource_settlement_shape')
        elif any(value is not None for value in (fact.native_cost,fact.paid_amount,fact.clear_seq)):
            raise ContractError('macro_resource_settlement_shape')
        if fact.kind in ('queue_accepted','payment_consumed','queue_cancelled'):
            if (type(fact.queue_key) is not tuple or len(fact.queue_key)!=2 or any(not positive(v) for v in fact.queue_key)
                    or not positive(fact.native_cost) or fact.native_cost>row['upper_cost']
                    or not amount(fact.paid_amount) or fact.paid_amount>fact.native_cost
                    or row['queue_key'] is not None and (fact.queue_key!=row['queue_key'] or fact.native_cost!=row['native_cost'])):
                raise ContractError('macro_resource_queue_settlement_unverified')
            if fact.kind!='queue_accepted' and (row['queue_key'] is None or fact.cash_attribution_verified is not True
                    or fact.paid_amount<row['paid_amount']):
                raise ContractError('macro_resource_payment_attribution_unverified')
            if fact.kind=='queue_accepted':
                if row['queue_key'] is not None:raise ContractError('macro_resource_second_queue_refused')
                updated.update(queue_key=fact.queue_key,native_cost=fact.native_cost,status='queue_accepted')
            else:updated['paid_amount']=fact.paid_amount
            if fact.kind=='queue_cancelled':updated['cancelled']=True
        elif fact.kind=='preference_cleared':
            if not positive(fact.clear_seq) or not fact.native_seq<fact.clear_seq<=2048:
                raise ContractError('macro_resource_independent_release_required')
            updated['preference_cleared']=True
        elif fact.kind=='no_queue_accepted':
            if row['queue_key'] is not None or not row['preference_cleared']:
                raise ContractError('macro_resource_complete_acceptance_audit_required')
            updated['no_queue_verified']=True
        else:
            if (row['queue_key'] is None or fact.queue_key!=row['queue_key'] or not amount(fact.refund_amount)
                    or fact.refund_amount>row['paid_amount'] or fact.cash_attribution_verified is not True):
                raise ContractError('macro_resource_refund_attribution_unverified')
            updated['refund_amount']=fact.refund_amount
        if updated['preference_cleared']:
            if updated['no_queue_verified']:updated['status']='released_without_queue'
            elif updated['cancelled']:updated['status']='cancelled'
            elif updated['native_cost'] is not None and updated['paid_amount']==updated['native_cost']:updated['status']='consumed'
        updated['last_frame']=fact.frame
        rows=copy.deepcopy(self.rows);rows[fact.command_id]=updated
        facts=copy.deepcopy(self.fact_ids);facts[fact.fact_id]=fact_fingerprint;self._commit(rows,facts)
        return self.public(fact.command_id)

    @serialized
    def public(self,command_id):
        row=self.rows[command_id];held=row['status'] not in TERMINAL
        return dict(source='trusted_product_resource_reservation',status=row['status'],additional_count=1,
            budget_semantics='available_credit_filter_and_single_host_request_reservation',
            funding_scope='current_owned_production_upgrade_queues' if row['cost_fact']['source']==CURRENT_QUEUE_BUDGET_SOURCE else 'complete_existing_native_payment_commitments',
            single_new_request_hard_limit_verified=False,host_influenced_spending_cap_verified=False,
            upper_cost_reserved=row['upper_cost'],held_reservation_amount=row['upper_cost'] if held else 0,
            actual_cash_payment_verified_amount=row['paid_amount'],refund_verified_amount=row['refund_amount'],
            queue_acceptance_independently_verified=row['queue_key'] is not None,
            preference_release_independently_verified=row['preference_cleared'],
            cancellation_independently_verified=row['cancelled'],no_queue_acceptance_independently_verified=row['no_queue_verified'],
            budget_hard_cap_verified=False,native_ai_autonomous_spending_controlled=False,
            automatic_retry_allowed=False)


def compact_reservation(value):
    amounts=('upper_cost_reserved','held_reservation_amount','actual_cash_payment_verified_amount')
    flags=('queue_acceptance_independently_verified','preference_release_independently_verified',
        'cancellation_independently_verified','no_queue_acceptance_independently_verified')
    statuses=(*TERMINAL,'reserved','delivering','acknowledged','queue_accepted','unknown')
    if (type(value) is not dict or value.get('source')!='trusted_product_resource_reservation'
            or value.get('funding_scope') not in ('current_owned_production_upgrade_queues','complete_existing_native_payment_commitments')
            or value.get('status') not in statuses or type(value.get('additional_count')) is not int or value['additional_count']!=1
            or any(not amount(value.get(key)) for key in amounts) or not positive(value['upper_cost_reserved'])
            or any(type(value.get(key)) is not bool for key in flags)
            or value['held_reservation_amount']!=(0 if value['status'] in TERMINAL else value['upper_cost_reserved'])
            or value['actual_cash_payment_verified_amount']>value['upper_cost_reserved']
            or value.get('refund_verified_amount') is not None and (not amount(value['refund_verified_amount'])
                or value['refund_verified_amount']>value['actual_cash_payment_verified_amount'])
            or value['status'] in ('consumed','cancelled','released_without_queue') and not value['preference_release_independently_verified']
            or value['cancellation_independently_verified'] and not value['queue_acceptance_independently_verified']
            or value['no_queue_acceptance_independently_verified'] and value['queue_acceptance_independently_verified']):
        raise ContractError('macro_resource_public_fact_invalid')
    return {**{key:value[key] for key in ('source','status','additional_count',*amounts,*flags,'refund_verified_amount','funding_scope')},
        'budget_semantics':'available_credit_filter_and_single_host_request_reservation',
        'single_new_request_hard_limit_verified':False,'host_influenced_spending_cap_verified':False,
        'budget_hard_cap_verified':False,'native_ai_autonomous_spending_controlled':False,'automatic_retry_allowed':False}
