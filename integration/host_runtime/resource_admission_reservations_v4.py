"""Current-state admission buffers, not a payment or total-spending ledger.

Independent schema4 records never upgrade the strict resource-reservations v2
records. Closing a buffer proves neither payment/refund nor absent latent work.
"""
from dataclasses import asdict,dataclass,fields
import copy
import json
import threading

from .contracts import ContractError
from .macro_expansion_scope import TARGETS
from .resource_settlement_adapter import SettlementSession,sha,uuid_value,digest
from .resource_reservations import positive,amount,token,serialized

FINANCE_SOURCE='native_complete_current_production_upgrade_financial_state_v4'
COST_SOURCE='native_fresh_complete_queue_admission_cost_v4'
ACK_SOURCE='native_known_preference_original_ack_v4'
CLEAR_SOURCE='native_independent_twenty_flag_preference_clear_v4'
LEDGER_SOURCE='native_complete_known_command_ledger_window_v4'
RECONCILIATION_SOURCE='native_after_clear_complete_current_state_admission_reconciliation_v4'
KIND='active_preference_buffer_ledger_v4'
CLOSED='closed_after_current_state_reconciliation'
TERMINAL=(CLOSED,'aborted_before_delivery')
EXCLUSIONS=('future_unaccepted_native_spending','prior_preference_selected_but_not_enqueued_work',
    'future_native_autonomous_spending','repair_and_ability_spending')


def fail(code='macro_admission_v4_unverified'):raise ContractError(code)
def encoded(value):return json.loads(json.dumps(asdict(value),allow_nan=False))


@dataclass(frozen=True)
class FinancialStateV4:
    session:SettlementSession
    frame:int
    frame_after:int
    component_frames:tuple
    started_monotonic_ns:int
    ended_monotonic_ns:int
    credits:int
    production_upgrade_commitment_upper_bound:int
    coverage_contract_sha256:str
    source_evidence_sha256:str
    source:str=FINANCE_SOURCE
    complete_registered_live_union_coverage_verified:bool=False
    all_production_upgrade_modules_and_nodes_verified:bool=False
    same_financial_window_stable:bool=False
    native_payment_balance_currency_verified:bool=False
    owner_lifecycle_contract_verified:bool=False
    field_complete_queue_coverage_qualified:bool=False
    held_handle_identity_before_after_verified:bool=False
    gc_inactive_verified:bool=False
    future_unaccepted_spending_covered:bool=False
    prior_preference_latent_work_covered:bool=False
    actual_payment_attribution_verified:bool=False
    exclusive_enqueue_causality_verified:bool=False
    hard_total_spending_limit_verified:bool=False


@dataclass(frozen=True)
class AdmissionCostV4:
    financial:FinancialStateV4
    action:str
    template_hash:str
    producer_thing_id:int
    producer_type_hash:str
    quote_frame:int
    upper_cost:int
    source_evidence_sha256:str
    source:str=COST_SOURCE
    native_upper_cost_verified:bool=False
    loaded_target_schema_verified:bool=False
    current_quote_and_producer_verified:bool=False


@dataclass(frozen=True)
class KnownPreferenceAckV4:
    session:SettlementSession
    command_id:str
    action:str
    native_seq:int
    flag_names:tuple
    work_mask:int
    applied_mask:int
    start_frame:int
    deadline_frame:int
    ack_frame:int
    completed_monotonic_ns:int
    source_evidence_sha256:str
    source:str=ACK_SOURCE
    verified:bool=False


@dataclass(frozen=True)
class IndependentPreferenceClearV4:
    session:SettlementSession
    original_command_id:str
    original_seq:int
    command_id:str
    native_seq:int
    frame:int
    completed_monotonic_ns:int
    source_evidence_sha256:str
    source:str=CLEAR_SOURCE
    verified:bool=False


@dataclass(frozen=True)
class NativeLedgerWindowV4:
    session:SettlementSession
    original_ack_evidence_sha256:str
    clear_ack_evidence_sha256:str
    latest_known_seq:int
    frame_before:int
    frame_after:int
    started_monotonic_ns:int
    ended_monotonic_ns:int
    source_evidence_sha256:str
    unknown_or_outstanding_command_ids:tuple=()
    source:str=LEDGER_SOURCE
    complete_command_history_verified:bool=False
    durable_journal_unchanged_and_complete_verified:bool=False
    ledger_unchanged_across_financial_window:bool=False
    original_work_flag_still_clear_verified:bool=False


@dataclass(frozen=True)
class AdmissionReconciliationV4:
    fact_id:str
    session_id:str
    plan_id:str
    command_id:str
    original_seq:int
    clear_seq:int
    financial:FinancialStateV4
    ledger:NativeLedgerWindowV4
    source:str=RECONCILIATION_SOURCE
    meaning:str='active_preference_buffer_closed_after_current_state_reconciliation'
    actual_payment_verified:bool=False
    refund_verified:bool=False
    no_queue_ever_accepted_verified:bool=False
    latent_native_work_cancelled_verified:bool=False


def validate_financial(fact,session,*,current_game_frame,now_monotonic_ns):
    if type(fact) is not FinancialStateV4 or type(session) is not SettlementSession:fail()
    session.validate()
    true=('complete_registered_live_union_coverage_verified','all_production_upgrade_modules_and_nodes_verified',
        'same_financial_window_stable','native_payment_balance_currency_verified','owner_lifecycle_contract_verified',
        'field_complete_queue_coverage_qualified','held_handle_identity_before_after_verified','gc_inactive_verified')
    false=('future_unaccepted_spending_covered','prior_preference_latent_work_covered','actual_payment_attribution_verified',
        'exclusive_enqueue_causality_verified','hard_total_spending_limit_verified')
    if (fact.source!=FINANCE_SOURCE or type(fact.session) is not SettlementSession or fact.session!=session or any(getattr(fact,k) is not True for k in true)
            or any(getattr(fact,k) is not False for k in false) or not positive(fact.frame) or not positive(fact.frame_after)
            or not 0<=fact.frame_after-fact.frame<=2 or type(fact.component_frames) is not tuple or not fact.component_frames
            or any(not positive(f) or not fact.frame<=f<=fact.frame_after for f in fact.component_frames)
            or type(fact.started_monotonic_ns) is not int or type(fact.ended_monotonic_ns) is not int
            or not 0<=fact.started_monotonic_ns<=fact.ended_monotonic_ns
            or type(now_monotonic_ns) is not int or not 0<=now_monotonic_ns-fact.ended_monotonic_ns<=1_000_000_000
            or not positive(current_game_frame) or not 0<=current_game_frame-fact.frame_after<=15
            or not amount(fact.credits) or not amount(fact.production_upgrade_commitment_upper_bound)
            or not sha(fact.coverage_contract_sha256) or not sha(fact.source_evidence_sha256)):fail('macro_admission_v4_financial_state_unverified')
    return fact


def validate_cost(fact,session,*,current_game_frame,now_monotonic_ns):
    if type(fact) is not AdmissionCostV4:fail('macro_admission_v4_cost_required')
    validate_financial(fact.financial,session,current_game_frame=current_game_frame,now_monotonic_ns=now_monotonic_ns)
    if (fact.source!=COST_SOURCE or fact.action not in TARGETS or (fact.template_hash,fact.producer_type_hash)!=TARGETS[fact.action][:2]
            or not positive(fact.producer_thing_id) or not positive(fact.upper_cost) or not positive(fact.quote_frame)
            or not 0<=current_game_frame-fact.quote_frame<=15
            or max(fact.quote_frame,fact.financial.frame_after)-min(fact.quote_frame,fact.financial.frame)>15
            or any(getattr(fact,k) is not True for k in ('native_upper_cost_verified','loaded_target_schema_verified','current_quote_and_producer_verified'))
            or not sha(fact.source_evidence_sha256)):fail('macro_admission_v4_cost_unverified')
    if fact.upper_cost>fact.financial.credits-fact.financial.production_upgrade_commitment_upper_bound:
        fail('macro_admission_v4_insufficient_current_funds')


def validate_ack(fact,session,command,action):
    if (type(fact) is not KnownPreferenceAckV4 or fact.source!=ACK_SOURCE or fact.verified is not True
            or type(fact.session) is not SettlementSession or fact.session!=session or fact.command_id!=command or fact.action!=action or not uuid_value(command)
            or type(fact.native_seq) is not int or not 1<=fact.native_seq<=2046
            or type(fact.flag_names) is not tuple or len(fact.flag_names)!=20 or len(set(fact.flag_names))!=20
            or any(type(n) is not str or not n for n in fact.flag_names)
            or type(fact.work_mask) is not int or fact.work_mask<=0 or fact.work_mask&(fact.work_mask-1)
            or type(fact.applied_mask) is not int or not 0<fact.applied_mask<1<<20 or not fact.applied_mask&fact.work_mask
            or any(not positive(f) for f in (fact.start_frame,fact.deadline_frame,fact.ack_frame))
            or not fact.start_frame<=fact.ack_frame<fact.deadline_frame or not 1<=fact.deadline_frame-fact.start_frame<=600
            or type(fact.completed_monotonic_ns) is not int or fact.completed_monotonic_ns<0 or not sha(fact.source_evidence_sha256)):fail()


def validate_clear(fact,work):
    if (type(fact) is not IndependentPreferenceClearV4 or fact.source!=CLEAR_SOURCE or fact.verified is not True
            or type(fact.session) is not SettlementSession or fact.session!=work.session or fact.original_command_id!=work.command_id
            or type(fact.original_seq) is not int or fact.original_seq!=work.native_seq
            or not uuid_value(fact.command_id) or fact.command_id==work.command_id or type(fact.native_seq) is not int
            or fact.native_seq!=work.native_seq+1 or fact.native_seq>2047 or not positive(fact.frame) or fact.frame<work.ack_frame
            or type(fact.completed_monotonic_ns) is not int or fact.completed_monotonic_ns<=work.completed_monotonic_ns
            or not sha(fact.source_evidence_sha256)):fail('macro_admission_v4_independent_clear_unverified')


def reconciliation_identity(fact):
    body=encoded(fact);body.pop('fact_id')
    import uuid
    return str(uuid.uuid5(uuid.UUID(fact.session_id),digest(body)))


def validate_reconciliation(fact,row,session,*,current_game_frame,now_monotonic_ns):
    if type(fact) is not AdmissionReconciliationV4:fail()
    work=row['work_ack'];clear=row['clear_fact'];finance=fact.financial;ledger=fact.ledger
    if (fact.source!=RECONCILIATION_SOURCE or fact.meaning!='active_preference_buffer_closed_after_current_state_reconciliation'
            or any(getattr(fact,k) is not False for k in ('actual_payment_verified','refund_verified','no_queue_ever_accepted_verified','latent_native_work_cancelled_verified'))
            or fact.session_id!=session.session_id or fact.plan_id!=row['plan_id'] or fact.command_id!=row['command_id']
            or type(fact.original_seq) is not int or type(fact.clear_seq) is not int or fact.original_seq!=work.native_seq or fact.clear_seq!=clear.native_seq
            or not uuid_value(fact.fact_id) or fact.fact_id!=reconciliation_identity(fact)):
        fail('macro_admission_v4_reconciliation_binding')
    validate_financial(finance,session,current_game_frame=current_game_frame,now_monotonic_ns=now_monotonic_ns)
    if (min((finance.frame,*finance.component_frames))<=clear.frame or finance.started_monotonic_ns<=clear.completed_monotonic_ns
            or type(ledger) is not NativeLedgerWindowV4 or ledger.source!=LEDGER_SOURCE or ledger.session!=session
            or ledger.original_ack_evidence_sha256!=work.source_evidence_sha256 or ledger.clear_ack_evidence_sha256!=clear.source_evidence_sha256
            or type(ledger.latest_known_seq) is not int or not clear.native_seq<=ledger.latest_known_seq<=2048
            or type(ledger.unknown_or_outstanding_command_ids) is not tuple or ledger.unknown_or_outstanding_command_ids!=()
            or any(getattr(ledger,k) is not True for k in ('complete_command_history_verified','durable_journal_unchanged_and_complete_verified',
                'ledger_unchanged_across_financial_window','original_work_flag_still_clear_verified'))
            or not positive(ledger.frame_before) or not positive(ledger.frame_after)
            or not clear.frame<=ledger.frame_before<=finance.frame<=finance.frame_after<=ledger.frame_after
            or ledger.frame_after-ledger.frame_before>15
            or type(ledger.started_monotonic_ns) is not int or type(ledger.ended_monotonic_ns) is not int
            or not clear.completed_monotonic_ns<ledger.started_monotonic_ns<=finance.started_monotonic_ns<=finance.ended_monotonic_ns<=ledger.ended_monotonic_ns<=now_monotonic_ns
            or not sha(ledger.source_evidence_sha256)):
        fail('macro_admission_v4_after_clear_financial_window_unverified')


class AdmissionReservationStoreV4:
    def __init__(self,session,*,persist=None):
        if type(session) is not SettlementSession:fail()
        session.validate();self.session=session;self.persist=persist;self.rows={};self.fact_ids={};self._lock=threading.RLock()

    @serialized
    def snapshot(self):
        return self._snapshot_for(self.rows,self.fact_ids)

    def _snapshot_for(self,source_rows,fact_ids):
        rows={key:{name:encoded(value) if name in ('cost_fact','work_ack','clear_fact','reconciliation_fact') and value is not None else copy.deepcopy(value)
            for name,value in row.items()} for key,row in source_rows.items()}
        return dict(schema_version=4,kind=KIND,session=encoded(self.session),rows=rows,fact_ids=copy.deepcopy(fact_ids))

    def _commit(self,rows,facts=None):
        facts=self.fact_ids if facts is None else facts
        snapshot=self._snapshot_for(rows,facts)
        if self.persist is not None:self.persist(copy.deepcopy(snapshot))
        self.rows=rows;self.fact_ids=facts

    @property
    @serialized
    def unresolved(self):return any(row['status'] not in TERMINAL for row in self.rows.values())

    @serialized
    def reserve(self,plan_id,command_id,cost_fact,*,current_game_frame,now_monotonic_ns):
        if not token(plan_id) or not uuid_value(command_id):fail()
        if command_id in self.rows:
            row=self.rows[command_id]
            if row['plan_id']!=plan_id or row['cost_fact']!=cost_fact:fail('macro_admission_v4_id_conflict')
            return self.public(command_id)
        if self.unresolved:fail('macro_admission_v4_active_buffer_unresolved')
        validate_cost(cost_fact,self.session,current_game_frame=current_game_frame,now_monotonic_ns=now_monotonic_ns)
        previous=[r['reconciliation_fact'].financial.ended_monotonic_ns for r in self.rows.values() if r['status']==CLOSED]
        if previous and cost_fact.financial.started_monotonic_ns<=max(previous):fail('macro_admission_v4_next_request_requires_new_financial_read')
        if len(self.rows)>=2047 or any(row['plan_id']==plan_id for row in self.rows.values()):fail()
        row=dict(session_id=self.session.session_id,plan_id=plan_id,command_id=command_id,action=cost_fact.action,
            template_hash=cost_fact.template_hash,player_id=3,buffer_amount=cost_fact.upper_cost,status='reserved',
            cost_fact=cost_fact,work_ack=None,clear_fact=None,reconciliation_fact=None,last_frame=cost_fact.financial.frame_after)
        rows=copy.deepcopy(self.rows);rows[command_id]=row;self._commit(rows);return self.public(command_id)

    @serialized
    def _transition(self,command_id,allowed,status):
        row=self.rows.get(command_id)
        if row is None or row['status'] not in allowed:fail('macro_admission_v4_transition_refused')
        rows=copy.deepcopy(self.rows);rows[command_id]['status']=status;self._commit(rows)

    def delivery_started(self,command_id):self._transition(command_id,('reserved',),'delivering')
    def delivery_unknown(self,command_id):self._transition(command_id,('delivering','acknowledged','preference_cleared'),'unknown')
    def abort_before_delivery(self,command_id):self._transition(command_id,('reserved',),'aborted_before_delivery')

    @serialized
    def acknowledge(self,fact):
        if type(fact) is not KnownPreferenceAckV4:fail()
        row=self.rows.get(fact.command_id)
        if row is None or row['status']=='unknown':fail('macro_admission_v4_unknown_not_reconcilable')
        validate_ack(fact,self.session,row['command_id'],row['action'])
        if row['work_ack'] is not None:
            if row['work_ack']!=fact:fail()
            return self.public(fact.command_id)
        if row['status']!='delivering' or fact.start_frame<row['last_frame']:fail()
        rows=copy.deepcopy(self.rows);rows[fact.command_id].update(status='acknowledged',work_ack=fact,last_frame=fact.ack_frame)
        self._commit(rows);return self.public(fact.command_id)

    @serialized
    def clear(self,fact):
        if type(fact) is not IndependentPreferenceClearV4:fail()
        row=self.rows.get(fact.original_command_id)
        if row is None or row['status']=='unknown' or row['work_ack'] is None:fail('macro_admission_v4_unknown_not_reconcilable')
        validate_clear(fact,row['work_ack'])
        if row['clear_fact'] is not None:
            if row['clear_fact']!=fact:fail()
            return self.public(row['command_id'])
        if row['status']!='acknowledged':fail()
        rows=copy.deepcopy(self.rows);rows[row['command_id']].update(status='preference_cleared',clear_fact=fact,last_frame=fact.frame)
        self._commit(rows);return self.public(row['command_id'])

    @serialized
    def reconcile(self,fact,*,current_game_frame,now_monotonic_ns):
        if type(fact) is not AdmissionReconciliationV4:fail()
        row=self.rows.get(fact.command_id)
        if row is None or row['status']=='unknown':fail('macro_admission_v4_unknown_not_reconcilable')
        if fact.fact_id in self.fact_ids:
            if self.fact_ids[fact.fact_id]!=encoded(fact):fail('macro_admission_v4_fact_conflict')
            return self.public(fact.command_id)
        if row['status']!='preference_cleared' or len(self.fact_ids)>=32768:fail()
        validate_reconciliation(fact,row,self.session,current_game_frame=current_game_frame,now_monotonic_ns=now_monotonic_ns)
        rows=copy.deepcopy(self.rows);rows[fact.command_id].update(status=CLOSED,reconciliation_fact=fact,last_frame=fact.financial.frame_after)
        facts=copy.deepcopy(self.fact_ids);facts[fact.fact_id]=encoded(fact);self._commit(rows,facts);return self.public(fact.command_id)

    @serialized
    def public(self,command_id):
        row=self.rows[command_id];recon=row['reconciliation_fact'];closed=row['status']==CLOSED
        return dict(source='active_preference_admission_buffer_v4',schema_version=4,status=row['status'],
            buffer_semantics='active_preference_buffer_closed_after_current_state_reconciliation',
            active_buffer_amount=0 if row['status'] in TERMINAL else row['buffer_amount'],
            original_ack_independently_known=row['work_ack'] is not None,preference_clear_independently_verified=row['clear_fact'] is not None,
            current_state_reconciliation_verified=closed,current_credits=recon.financial.credits if recon else None,
            current_production_upgrade_commitment_upper_bound=recon.financial.production_upgrade_commitment_upper_bound if recon else None,
            current_available_credit_filter=max(0,recon.financial.credits-recon.financial.production_upgrade_commitment_upper_bound) if recon else None,
            current_financial_shortfall=max(0,recon.financial.production_upgrade_commitment_upper_bound-recon.financial.credits) if recon else None,
            actual_cash_payment=None,refund_amount=None,no_queue_ever_accepted=None,exclusive_enqueue_causality=None,
            latent_native_work_cancelled=None,excluded_spending=list(EXCLUSIONS),hard_total_spending_limit_verified=False,
            new_dispatch_authorized=False,next_dispatch_requires_fresh_cost_and_financial_state=True,automatic_retry_allowed=False)


def _restore(cls,value):
    if type(value) is not dict or set(value)!={field.name for field in fields(cls)}:fail('macro_admission_v4_snapshot_invalid')
    raw=copy.deepcopy(value)
    if 'session' in raw:
        raw['session']=_restore(SettlementSession,raw['session'])
    if cls is SettlementSession:raw['game_identity']=tuple(raw['game_identity'])
    if cls is FinancialStateV4:raw['component_frames']=tuple(raw['component_frames'])
    if cls is AdmissionCostV4:raw['financial']=_restore(FinancialStateV4,raw['financial'])
    if cls is KnownPreferenceAckV4:raw['flag_names']=tuple(raw['flag_names'])
    if cls is NativeLedgerWindowV4:raw['unknown_or_outstanding_command_ids']=tuple(raw['unknown_or_outstanding_command_ids'])
    if cls is AdmissionReconciliationV4:
        raw['financial']=_restore(FinancialStateV4,raw['financial']);raw['ledger']=_restore(NativeLedgerWindowV4,raw['ledger'])
    return cls(**raw)


def restore_store_v4(value,*,persist=None):
    """No old-store migration, no resumed nonterminal record becomes known."""
    try:
        if (type(value) is not dict or set(value)!={'schema_version','kind','session','rows','fact_ids'}
                or type(value['schema_version']) is not int or value['schema_version']!=4 or value['kind']!=KIND
                or type(value['rows']) is not dict or len(value['rows'])>2047 or type(value['fact_ids']) is not dict
                or len(value['fact_ids'])>32768):fail('macro_admission_v4_snapshot_invalid')
        store=AdmissionReservationStoreV4(_restore(SettlementSession,value['session']),persist=persist);rows={};seen_plans=set();facts={}
        required={'session_id','plan_id','command_id','action','template_hash','player_id','buffer_amount','status','cost_fact','work_ack','clear_fact','reconciliation_fact','last_frame'}
        for command,raw in value['rows'].items():
            if type(raw) is not dict or set(raw)!=required:fail()
            row=copy.deepcopy(raw)
            for key,cls in (('cost_fact',AdmissionCostV4),('work_ack',KnownPreferenceAckV4),('clear_fact',IndependentPreferenceClearV4),('reconciliation_fact',AdmissionReconciliationV4)):
                if row[key] is not None:row[key]=_restore(cls,row[key])
            cost=row['cost_fact']
            validate_cost(cost,store.session,current_game_frame=max(cost.quote_frame,cost.financial.frame_after),now_monotonic_ns=cost.financial.ended_monotonic_ns)
            if (not uuid_value(command) or command!=row['command_id'] or row['session_id']!=store.session.session_id
                    or not token(row['plan_id']) or row['plan_id'] in seen_plans or row['action']!=cost.action or row['template_hash']!=cost.template_hash
                    or type(row['player_id']) is not int or row['player_id']!=3 or not positive(row['buffer_amount']) or row['buffer_amount']!=cost.upper_cost
                    or not positive(row['last_frame']) or row['last_frame']<cost.financial.frame_after
                    or row['status'] not in (*TERMINAL,'reserved','delivering','acknowledged','preference_cleared','unknown')):fail()
            if row['work_ack'] is not None:validate_ack(row['work_ack'],store.session,command,row['action'])
            if row['clear_fact'] is not None:
                if row['work_ack'] is None:fail()
                validate_clear(row['clear_fact'],row['work_ack'])
            if row['status'] in ('acknowledged','preference_cleared',CLOSED) and row['work_ack'] is None:fail()
            if row['status'] in ('preference_cleared',CLOSED) and row['clear_fact'] is None:fail()
            if row['status'] in ('reserved','delivering','aborted_before_delivery') and (row['work_ack'] is not None or row['clear_fact'] is not None):fail()
            if row['status']=='acknowledged' and row['clear_fact'] is not None:fail()
            if row['status']==CLOSED:
                recon=row['reconciliation_fact']
                if recon is None:fail()
                validate_reconciliation(recon,row,store.session,current_game_frame=recon.financial.frame_after,now_monotonic_ns=recon.ledger.ended_monotonic_ns)
                if value['fact_ids'].get(recon.fact_id)!=encoded(recon):fail()
                facts[recon.fact_id]=encoded(recon)
            elif row['reconciliation_fact'] is not None:fail()
            if row['status'] not in TERMINAL:row['status']='unknown'
            rows[command]=row;seen_plans.add(row['plan_id'])
        if facts!=value['fact_ids'] or sum(row['status'] not in TERMINAL for row in rows.values())>1:fail()
        store.rows=rows;store.fact_ids=facts;return store
    except (KeyError,TypeError,ValueError,AttributeError):fail('macro_admission_v4_snapshot_invalid')
