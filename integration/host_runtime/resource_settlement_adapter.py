"""Offline-testable trusted queue settlement; no memory access or capability grant.

Queue acceptance, preference clearing and cash attribution are independent.
The current registered reader supplies queue fields, not cash attribution;
without a separately qualified cash supplier this adapter never releases money.
"""
from dataclasses import asdict,dataclass
import hashlib
import json
import threading
import uuid

from .contracts import ContractError
from .macro_expansion_scope import TARGETS
from .macro_expansion_feedback import live_gate
from .resource_reservations import ResourceReservationStore,ResourceSettlementFact,SETTLEMENT_SOURCES,positive,amount,pointer,serialized

QUEUE_SOURCE='native_registry_and_live_union_owned_queue_research_observation_v1'
CASH_SOURCE='native_intent_bound_queue_cash_debit_attribution_v1'


def fail(code='macro_resource_settlement_source_unverified'):raise ContractError(code)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(value):return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)
def uuid_value(value):
    try:return type(value) is str and str(uuid.UUID(value))==value
    except (ValueError,AttributeError):return False
def hash_value(value):
    try:return type(value) is str and value==hex(int(value,0)) and 0<=int(value,0)<=0xffffffff
    except ValueError:return False


@dataclass(frozen=True)
class SettlementSession:
    session_id:str
    pid:int
    process_creation_filetime:int
    executable_sha256:str
    package_sha256:str
    game_identity:tuple
    ai_player:str
    personality_wrapper:str
    player_template:str

    def validate(self):
        if (not uuid_value(self.session_id) or not positive(self.pid)
                or type(self.process_creation_filetime) is not int or not 0<self.process_creation_filetime<2**64
                or not sha(self.executable_sha256) or not sha(self.package_sha256)
                or type(self.game_identity) is not tuple or len(self.game_identity)!=3
                or not all(pointer(p) for p in (*self.game_identity,self.ai_player,self.personality_wrapper,self.player_template))):fail()

    def matches_native(self,native):
        ticks=self.process_creation_filetime
        required=dict(magic=0x4d503032,version=2,pid=self.pid,start_low=ticks&0xffffffff,start_high=ticks>>32,
            owner=int(self.game_identity[1],0),ai=int(self.ai_player,0),personality=int(self.personality_wrapper,0),
            player_template=int(self.player_template,0),personality_id=0x799613e0)
        return type(native) is dict and all(type(native.get(k)) is int and native[k]==v for k,v in required.items())


@dataclass(frozen=True)
class Producer:
    thing_id:int
    thing:str
    type_hash:str
    modules:tuple


@dataclass(frozen=True)
class Queue:
    producer_id:int
    producer_thing:str
    module:str
    node:str
    kind:int
    production_id:int
    target:str
    target_hash:str
    cost:int
    paid:int

    @property
    def key(self):return self.producer_id,self.production_id
    @property
    def identity(self):
        return (self.producer_id,self.producer_thing,self.module,self.node,self.kind,self.production_id,self.target,self.target_hash,self.cost)


@dataclass(frozen=True)
class RegisteredQueueSnapshot:
    session:SettlementSession
    frame:int
    frame_after:int
    producers:tuple
    queues:tuple
    source_sha256:str


def registered_snapshot(session,raw):
    """Bind the frozen C reader output to a fresh backend-held process identity.

    session must come from the trusted handle PID/FILETIME/image binding on each
    sample. This function does not open a process or qualify union coverage.
    """
    if type(session) is not SettlementSession:fail()
    session.validate()
    try:
        identity=dict(game=session.game_identity[0],owner=session.game_identity[1],owner_index=3,template_factory=session.game_identity[2])
        if (raw.get('source')!=QUEUE_SOURCE or type(raw.get('schema_version')) is not int or raw['schema_version']!=1
                or raw.get('kind')!='native_own_production_queue_commitment_observation' or raw.get('session_identity')!=identity
                or any(raw.get(k) is not True for k in ('registered_roster_scan_complete','live_roster_scan_complete',
                    'roster_union_scan_complete','roster_scan_complete','queue_scan_complete','necessary_fields_stable'))
                or raw.get('paid_stability_policy')!='strict_equal_double_read'
                or raw.get('native_calls')!=0 or type(raw.get('native_calls')) is not int
                or raw.get('process_writes')!=0 or type(raw.get('process_writes')) is not int or raw.get('enemy_details_read') is not False
                or not positive(raw.get('frame')) or not positive(raw.get('frame_after')) or not 0<=raw['frame_after']-raw['frame']<=2):fail()
        producers={};addresses=set();all_modules={}
        for row in raw['module_census']:
            ident,thing,kind=row['thing_id'],row['thing'],row['template_hash']
            if not positive(ident) or not pointer(thing) or not hash_value(kind) or ident in producers or thing in addresses or row.get('module_vector_terminated') is not True:fail()
            modules=[]
            for item in row['modules']:
                module,vtable=item['module'],item['vtable']
                if not pointer(module) or not pointer(vtable) or module in all_modules:fail()
                all_modules[module]=(ident,vtable);modules.append((module,vtable))
            producers[ident]=Producer(ident,thing,kind,tuple(modules));addresses.add(thing)
        queues=[];keys=set();nodes=set();seen_modules=set()
        for row in raw['queues']:
            module,ident=row['module'],row['producer_thing_id'];producer=producers.get(ident)
            if not positive(ident) or producer is None or module in seen_modules or all_modules.get(module)!=(ident,'0xc3fad0'):fail()
            seen_modules.add(module);previous='0x0';rows=row['nodes']
            if (row['head']!=(rows[0]['node'] if rows else '0x0') or row['tail']!=(rows[-1]['node'] if rows else '0x0')):fail()
            for index,node in enumerate(rows):
                queue=Queue(ident,node['producer_thing'],module,node['node'],node['kind'],node['native_queue_id'],
                    node['target'],node['target_hash'],node['native_total_cost'],node['native_paid_accumulator'])
                if (type(node['producer_thing_id']) is not int or node['producer_thing_id']!=ident or queue.producer_thing!=producer.thing or node['module']!=module
                        or not all(pointer(p) for p in (queue.node,queue.target)) or type(queue.kind) is not int or queue.kind not in (1,2)
                        or not positive(queue.production_id) or not hash_value(queue.target_hash) or not positive(queue.cost)
                        or queue.cost>0x7fffffff or not amount(queue.paid) or queue.paid>queue.cost
                        or type(node['outstanding_payment_upper_bound']) is not int or node['outstanding_payment_upper_bound']!=queue.cost-queue.paid
                        or node.get('paid_stability_policy')!='strict_equal_double_read'
                        or queue.key in keys or queue.node in nodes or node['previous']!=previous
                        or node['next']!=(rows[index+1]['node'] if index+1<len(rows) else '0x0')):fail()
                keys.add(queue.key);nodes.add(queue.node);queues.append(queue);previous=queue.node
        if any(vtable=='0xc3fad0' and module not in seen_modules for module,(_,vtable) in all_modules.items()):fail()
        return RegisteredQueueSnapshot(session,raw['frame'],raw['frame_after'],tuple(producers.values()),tuple(queues),digest(raw))
    except (KeyError,TypeError,ValueError,AttributeError):fail()


@dataclass(frozen=True)
class QueueCashAttribution:
    """No production source currently signs this separate proof contract."""
    session:SettlementSession
    command_id:str
    native_seq:int
    queue_identity:tuple
    frame:int
    previous_verified_paid:int
    cumulative_verified_paid:int
    evidence_sha256:str
    source:str=CASH_SOURCE
    debit_path_verified:bool=False
    queue_birth_bound_to_intent:bool=False
    zero_paid_at_queue_initialization_verified:bool=False
    no_transfer_or_load_since_queue_birth:bool=False
    cash_attribution_verified:bool=False


def flags_match(value,names,mask):
    rows=value.get('flags') if type(value) is dict else None
    return (type(rows) is list and len(rows)==20 and [r.get('name') for r in rows if type(r) is dict]==list(names)
        and all((r.get('present') is True and r.get('value') is True) if mask&(1<<i)
            else (r.get('present') is False and r.get('value') is None or r.get('present') is True and r.get('value') is False)
            for i,r in enumerate(rows)))


def acknowledgement(prepared,ack,session,names,mask,*,kind,duration):
    ident=prepared.get('command_id');seq=prepared.get('seq');native=ack.get('native',{})
    if (not uuid_value(ident) or type(seq) is not int or not 1<=seq<=2048 or prepared.get('kind')!='command_prepared'
            or ack.get('kind')!='command_acknowledged' or ack.get('command_id')!=ident or ack.get('native_gate_acknowledged') is not True
            or any((r.get('session_id'),r.get('pid'))!=(session.session_id,session.pid) for r in (prepared,ack))
            or any(type(prepared.get(k)) is not int for k in ('kind_code','mask','duration_frames'))
            or (prepared['kind_code'],prepared['mask'],prepared['duration_frames'])!=(kind,mask,duration)
            or type(ack.get('seq')) is not int or ack['seq']!=seq or not session.matches_native(native)
            or any(type(native.get(k)) is not int or native[k]!=v for k,v in dict(request=seq,ack=seq,error=0,phase=1,
                applied_mask=mask,self_hook_installed=1,lease_held=1).items())
            or not flags_match(ack.get('independent_flags'),names,mask) or not positive(native.get('last_frame'))):fail()
    return seq,native


class NativeResourceSettlementAdapter:
    """One bound intent. Persist each fact through the original store before commit.

    No caller can clear unknown delivery, infer cancellation/refunds, or claim a
    no-acceptance audit from snapshots. cash_supplier defaults to unavailable.
    """
    @classmethod
    def bind(cls,store,session,command_id,*,manifest,prepared,ack,baseline,baseline_sample,cash_supplier=None):
        if type(store) is not ResourceReservationStore or type(session) is not SettlementSession or type(baseline) is not RegisteredQueueSnapshot:fail()
        session.validate();row=store.snapshot()['rows'].get(command_id)
        if (row is None or row['status']!='acknowledged' or row['session_id']!=session.session_id
                or baseline.session!=session or prepared.get('command_id')!=command_id
                or tuple(row['cost_fact']['game_identity'])!=session.game_identity or row['action'] not in TARGETS
                or cash_supplier is not None and not callable(cash_supplier)):fail()
        action=row['action'];target,producer,_=TARGETS[action];names=manifest.get('flags');consumers=manifest.get('consumers')
        if (manifest.get('protocol_version')!=2 or type(manifest.get('protocol_version')) is not int
                or manifest.get('package_sha256')!=session.package_sha256 or type(names) is not list or len(names)!=20
                or any(type(n) is not str for n in names) or len(set(names))!=20 or type(consumers) is not list
                or len(consumers)!=20 or any(type(r) is not dict or type(r.get('action')) is not str for r in consumers)
                or len({r['action'] for r in consumers})!=20 or [r.get('flag') for r in consumers]!=names):fail()
        work=[i for i,r in enumerate(consumers) if r.get('action')==action]
        budgets={i for i,r in enumerate(consumers) if r.get('action') in ('budgeteconomy','budgetarmy','budgettech')}
        mask=prepared.get('mask');duration=prepared.get('duration_frames')
        if (len(work)!=1 or type(mask) is not int or not 0<mask<1<<20 or not mask&(1<<work[0])
                or mask&~sum(1<<i for i in (*budgets,*work)) or sum(bool(mask&(1<<i)) for i in budgets)>1
                or type(duration) is not int or not 1<=duration<=600):fail()
        seq,native=acknowledgement(prepared,ack,session,names,mask,kind=1,duration=duration)
        deadline=native.get('deadline_frame');start=deadline-duration if type(deadline) is int else 0
        if (seq!=row['native_seq'] or seq>2047 or not 0<start<=native['last_frame']<deadline
                or type(native.get('active')) is not int or native['active']!=1):fail()
        gate=live_gate(action,baseline_sample,baseline.frame/15)
        identity=baseline_sample.get('dependency',{}).get('session_identity')
        if identity!=dict(game=session.game_identity[0],owner=session.game_identity[1],owner_index=3,template_factory=session.game_identity[2]):fail()
        frames=(*gate['frames'],baseline.frame,baseline.frame_after,row['cost_fact']['frame'])
        if max(frames)>start or min(frames)<start-15:fail()
        producers=[p for p in baseline.producers if p.thing_id in gate['producer_ids'] and p.type_hash==producer]
        if len(producers)!=1 or any(q.producer_id==producers[0].thing_id and q.kind==1 and q.target_hash==target for q in baseline.queues):fail()
        result=cls();result.store=store;result.session=session;result.row=row;result.names=tuple(names)
        result.producer=producers[0];result.mask=mask;result.start=start;result.deadline=deadline
        result.accepted=None;result.last_queue=None;result.verified_paid=0;result.cleared=None;result.blocked=None
        result.last_frame=baseline.frame_after;result.cash_supplier=cash_supplier
        result._lock=threading.RLock()
        result.request_evidence_sha256=digest(dict(prepared=prepared,ack=ack,manifest=manifest,
            baseline_queue_sha256=baseline.source_sha256,baseline_sample=baseline_sample))
        return result

    def _row(self):
        row=self.store.snapshot()['rows'][self.row['command_id']]
        if row['status'] not in ('acknowledged','queue_accepted'):fail('macro_resource_settlement_unknown_or_terminal')
        return row

    def _fact(self,kind,frame,*,evidence_sha256,**fields):
        if not sha(evidence_sha256):fail()
        row=self.row;seed=digest(dict(kind=kind,frame=frame,fields=fields,
            request_evidence_sha256=self.request_evidence_sha256,source_evidence_sha256=evidence_sha256))
        return ResourceSettlementFact(str(uuid.uuid5(uuid.UUID(self.session.session_id),row['command_id']+':'+seed)),
            row['session_id'],3,row['plan_id'],row['command_id'],row['action'],row['template_hash'],kind,SETTLEMENT_SOURCES[kind],
            frame,row['native_seq'],verified=True,**fields)

    @serialized
    def observe(self,snapshot,*,native=None,flags=None):
        self._row()
        if self.blocked is not None:fail(self.blocked)
        if type(snapshot) is not RegisteredQueueSnapshot or snapshot.session!=self.session or not sha(snapshot.source_sha256):fail()
        if snapshot.frame<self.last_frame:fail('macro_resource_settlement_frame_regressed')
        producers=[p for p in snapshot.producers if p.thing_id==self.producer.thing_id]
        if producers!=[self.producer]:self.blocked='macro_resource_settlement_producer_changed';fail(self.blocked)
        matches=[q for q in snapshot.queues if q.producer_id==self.producer.thing_id and q.kind==1 and q.target_hash==self.row['template_hash']]
        facts=[]
        if self.accepted is None:
            if self.cleared is not None:return ()
            if (not self.session.matches_native(native) or any(type(native.get(k)) is not int or native[k]!=v for k,v in
                    dict(request=self.row['native_seq'],ack=self.row['native_seq'],phase=1,error=0,active=1,applied_mask=self.mask,
                        self_hook_installed=1,lease_held=1,deadline_frame=self.deadline,cleanup_verified=0).items()) or not flags_match(flags,self.names,self.mask)
                    or not self.start<=snapshot.frame<=snapshot.frame_after<self.deadline
                    or not positive(native.get('last_frame')) or abs(native['last_frame']-snapshot.frame_after)>15):fail()
            if len(matches)>1:self.blocked='macro_resource_multiple_queue_mapping_unverified';fail(self.blocked)
            if not matches:self.last_frame=snapshot.frame_after;return ()
            queue=matches[0]
            if queue.cost>self.row['upper_cost']:self.blocked='macro_resource_queue_exceeds_reservation';fail(self.blocked)
            fact=self._fact('queue_accepted',snapshot.frame_after,evidence_sha256=snapshot.source_sha256,
                queue_key=queue.key,native_cost=queue.cost,paid_amount=queue.paid)
            self.store.settle(fact);self.accepted=queue;self.last_queue=queue;facts.append(fact)
        else:
            current=[q for q in matches if q.identity==self.accepted.identity]
            if len(current)!=1 or self.cleared is None and len(matches)!=1:
                self.blocked='macro_resource_queue_disappeared_or_changed';fail(self.blocked)
            queue=current[0]
            if queue.paid<self.last_queue.paid:self.blocked='macro_resource_paid_field_regressed';fail(self.blocked)
        if self.cash_supplier is not None:
            proof=self.cash_supplier(self.session,self.row['command_id'],self.row['native_seq'],queue,snapshot.frame_after,self.verified_paid)
            if proof is not None:
                if (type(proof) is not QueueCashAttribution or proof.source!=CASH_SOURCE or proof.session!=self.session
                        or proof.command_id!=self.row['command_id'] or proof.native_seq!=self.row['native_seq']
                        or proof.queue_identity!=queue.identity or proof.frame!=snapshot.frame_after
                        or type(proof.previous_verified_paid) is not int or proof.previous_verified_paid!=self.verified_paid
                        or type(proof.cumulative_verified_paid) is not int or proof.cumulative_verified_paid!=queue.paid
                        or proof.cumulative_verified_paid<self.verified_paid or not sha(proof.evidence_sha256)
                        or any(getattr(proof,k) is not True for k in ('debit_path_verified','queue_birth_bound_to_intent',
                            'zero_paid_at_queue_initialization_verified','no_transfer_or_load_since_queue_birth','cash_attribution_verified'))):
                    self.blocked='macro_resource_payment_attribution_unverified';fail(self.blocked)
                if proof.cumulative_verified_paid>self.verified_paid:
                    fact=self._fact('payment_consumed',snapshot.frame_after,evidence_sha256=digest(asdict(proof)),queue_key=queue.key,native_cost=queue.cost,
                        paid_amount=proof.cumulative_verified_paid,cash_attribution_verified=True)
                    self.store.settle(fact);self.verified_paid=proof.cumulative_verified_paid;facts.append(fact)
        self.last_queue=queue;self.last_frame=snapshot.frame_after
        return tuple(facts)

    @serialized
    def independent_clear(self,prepared,ack):
        # A replayed clear can be returned after later cash facts; the store's
        # persisted fact-id ledger handles that exact replay idempotently.
        seq,native=acknowledgement(prepared,ack,self.session,self.names,0,kind=1,duration=1)
        if (seq!=self.row['native_seq']+1 or prepared.get('command_id')==self.row['command_id']
                or any(type(native.get(k)) is not int or native[k]!=v for k,v in
                    dict(active=0,cleanup_verified=1,deadline_frame=0).items())):fail()
        fact=self._fact('preference_cleared',native['last_frame'],evidence_sha256=digest(dict(prepared=prepared,ack=ack)),clear_seq=seq)
        if self.cleared is not None:
            if fact!=self.cleared:fail()
            self.store.settle(fact);return fact
        if native['last_frame']<self.last_frame:fail()
        self._row();self.store.settle(fact);self.cleared=fact;self.last_frame=native['last_frame'];return fact
