"""Raw receipt/ledger adapters for schema4 current-state buffer reconciliation.

No reader is auto-qualified here. The FinancialStateV4 must come from a separate
reviewed fresh complete financial source; current research false stays false.
"""
from copy import deepcopy
from dataclasses import replace

from .resource_settlement_adapter import SettlementSession,acknowledgement,flags_match,digest,uuid_value
from .resource_reservations import positive
from .macro_expansion_scope import TARGETS
from .resource_admission_reservations_v4 import (KnownPreferenceAckV4,IndependentPreferenceClearV4,NativeLedgerWindowV4,
    AdmissionReconciliationV4,AdmissionReservationStoreV4,validate_ack,validate_clear,reconciliation_identity,fail)


def work_ack_v4(session,action,manifest,prepared,ack,*,completed_monotonic_ns):
    if type(session) is not SettlementSession or action not in TARGETS:fail()
    session.validate();names=manifest.get('flags');consumers=manifest.get('consumers')
    if (type(manifest.get('protocol_version')) is not int or manifest['protocol_version']!=2
            or manifest.get('package_sha256')!=session.package_sha256 or type(names) is not list or len(names)!=20
            or any(type(n) is not str or not n for n in names) or len(set(names))!=20
            or type(consumers) is not list or len(consumers)!=20 or any(type(c) is not dict or type(c.get('action')) is not str for c in consumers)
            or [c.get('flag') for c in consumers]!=names or len({c['action'] for c in consumers})!=20):fail()
    indexes=[i for i,c in enumerate(consumers) if c['action']==action]
    budgets=[i for i,c in enumerate(consumers) if c['action'] in ('budgeteconomy','budgetarmy','budgettech')]
    mask=prepared.get('mask');duration=prepared.get('duration_frames')
    if (len(indexes)!=1 or type(mask) is not int or not 0<mask<1<<20 or not mask&(1<<indexes[0])
            or mask&~sum(1<<i for i in (*indexes,*budgets)) or sum(bool(mask&(1<<i)) for i in budgets)>1
            or type(duration) is not int or not 1<=duration<=600):fail()
    seq,native=acknowledgement(prepared,ack,session,names,mask,kind=1,duration=duration)
    deadline=native.get('deadline_frame');start=deadline-duration if type(deadline) is int else 0
    # Native active is the callback reentrancy lock, not an intent activity
    # flag. A completed stable ACK has released that lock, even for mask!=0.
    if type(native.get('active')) is not int or native['active']!=0 or type(native.get('cleanup_verified')) is not int or native['cleanup_verified']!=0:fail()
    fact=KnownPreferenceAckV4(session,prepared['command_id'],action,seq,tuple(names),1<<indexes[0],mask,start,deadline,
        native['last_frame'],completed_monotonic_ns,digest(dict(manifest=manifest,prepared=prepared,ack=ack)),verified=True)
    validate_ack(fact,session,fact.command_id,action);return fact


def independent_clear_v4(work,prepared,ack,*,completed_monotonic_ns):
    if type(work) is not KnownPreferenceAckV4:fail()
    validate_ack(work,work.session,work.command_id,work.action)
    seq,native=acknowledgement(prepared,ack,work.session,work.flag_names,0,kind=1,duration=1)
    if any(type(native.get(k)) is not int or native[k]!=v for k,v in dict(active=0,cleanup_verified=1,deadline_frame=0).items()):fail()
    fact=IndependentPreferenceClearV4(work.session,work.command_id,work.native_seq,prepared['command_id'],seq,native['last_frame'],
        completed_monotonic_ns,digest(dict(prepared=prepared,ack=ack)),verified=True)
    validate_clear(fact,work);return fact


def native_ledger_window_v4(work,clear,manifest,records_before,records_after,*,native_before,flags_before,native_after,flags_after,
                           durable_before,durable_after,started_monotonic_ns,ended_monotonic_ns):
    """Full unchanged command prefix 1..latest plus physical native double read.

    Caller must hold the shared native dispatch lock around both ledger reads,
    the financial read and final store commit; neither omitted history nor an
    unknown/half-delivered command can be certified by this factory.
    """
    validate_ack(work,work.session,work.command_id,work.action);validate_clear(clear,work)
    before,after=deepcopy(records_before),deepcopy(records_after)
    allowed={'attach_prepared','attach_acknowledged','command_prepared','command_acknowledged',
        'macro_observation','native_builder_observation','transport_closed'}
    if (type(before) is not list or type(after) is not list or before!=after or not before
            or any(type(r) is not dict for r in before)
            or any(r.get('kind') not in allowed or (r.get('session_id'),r.get('pid'))!=(work.session.session_id,work.session.pid) for r in before)):
        fail('macro_admission_v4_ledger_unknown_or_changed')
    prepared=[r for r in before if r.get('kind')=='command_prepared'];acks=[r for r in before if r.get('kind')=='command_acknowledged']
    if not 1<=len(prepared)<=2048 or len(prepared)!=len(acks):fail('macro_admission_v4_ledger_incomplete')
    latest=len(prepared)
    if ([r.get('seq') for r in prepared]!=list(range(1,latest+1)) or [r.get('seq') for r in acks]!=list(range(1,latest+1))
            or len({r.get('command_id') for r in prepared})!=latest):fail('macro_admission_v4_ledger_incomplete')
    for index,(pending,receipt) in enumerate(zip(prepared,acks)):
        seq=index+1;native=receipt.get('native',{});mask=pending.get('mask');duration=pending.get('duration_frames');kind=pending.get('kind_code')
        if (not uuid_value(pending.get('command_id')) or receipt.get('command_id')!=pending['command_id']
                or any(type(r.get('seq')) is not int or r['seq']!=seq or (r.get('session_id'),r.get('pid'))!=(work.session.session_id,work.session.pid) for r in (pending,receipt))
                or before.index(pending)>=before.index(receipt) or index and before.index(acks[index-1])>=before.index(pending)
                or receipt.get('native_gate_acknowledged') is not True or not work.session.matches_native(native)
                or type(kind) is not int or kind not in (1,2) or type(mask) is not int or not 0<=mask<1<<20
                or type(duration) is not int or kind==1 and (seq>2047 or not 1<=duration<=4500)
                or kind==2 and (mask!=0 or duration!=0)
                or any(type(native.get(k)) is not int or native[k]!=v for k,v in dict(request=seq,ack=seq,error=0,applied_mask=mask if kind==1 else 0).items())
                or not flags_match(receipt.get('independent_flags'),work.flag_names,mask if kind==1 else 0)):
            fail('macro_admission_v4_ledger_receipt_unverified')
        def state_is(expected):return all(type(native.get(k)) is int and native[k]==v for k,v in expected.items())
        if kind==1:
            if not state_is(dict(phase=1,self_hook_installed=1,lease_held=1,active=0)):fail()
        elif not state_is(dict(phase=2,self_hook_installed=0,lease_held=0,active=0,cleanup_verified=1)):fail()
    work_pairs=[(p,a) for p,a in zip(prepared,acks) if p.get('command_id')==work.command_id]
    clear_pairs=[(p,a) for p,a in zip(prepared,acks) if p.get('command_id')==clear.command_id]
    if len(work_pairs)!=1 or len(clear_pairs)!=1:fail()
    if work_ack_v4(work.session,work.action,manifest,*work_pairs[0],completed_monotonic_ns=work.completed_monotonic_ns)!=work:fail()
    if independent_clear_v4(work,*clear_pairs[0],completed_monotonic_ns=clear.completed_monotonic_ns)!=clear:fail()
    required={'session_id','pid','process_creation_filetime','run_id','commands','unresolved_command_ids','transport_unknown_command_ids'}
    if (type(durable_before) is not dict or type(durable_after) is not dict or set(durable_before)!=required
            or durable_before!=durable_after or durable_before['session_id']!=work.session.session_id
            or type(durable_before['pid']) is not int or durable_before['pid']!=work.session.pid
            or type(durable_before['process_creation_filetime']) is not int or durable_before['process_creation_filetime']!=work.session.process_creation_filetime
            or not uuid_value(durable_before['run_id']) or durable_before['unresolved_command_ids']!=[]
            or durable_before['transport_unknown_command_ids']!=[] or type(durable_before['commands']) is not list or len(durable_before['commands'])>8192
            or any(type(r) is not dict or type(r.get('payload')) is not dict or r.get('status') in ('reserved','dispatching','uncertain') for r in durable_before['commands'])):
        fail('macro_admission_v4_durable_ledger_unknown_or_changed')
    commands=[r for r in durable_before['commands'] if r.get('operation')=='macro_policy']
    by_native={r.get('payload',{}).get('native_command_id'):r for r in commands}
    applied=[p for p in prepared if p['kind_code']==1]
    if len(by_native)!=len(commands) or set(by_native)!={p['command_id'] for p in applied}:fail('macro_admission_v4_durable_ledger_incomplete')
    action_bits={row['action']:1<<i for i,row in enumerate(manifest['consumers'])}
    for pending in applied:
        command=by_native[pending['command_id']];payload=command.get('payload',{});receipt=command.get('receipt',{})
        actions=payload.get('actions')
        if (command.get('run_id')!=durable_before['run_id'] or command.get('status')!='completed' or command.get('request_id')!=pending['command_id']
                or type(actions) is not list or any(type(a) is not str for a in actions) or len(actions)!=len(set(actions)) or any(a not in action_bits for a in actions)
                or sum(action_bits[a] for a in actions)!=pending['mask'] or payload.get('duration_frames')!=pending['duration_frames']
                or type(payload.get('duration_frames')) is not int or type(receipt) is not dict or receipt.get('native_gate_acknowledged') is not True
                or type(receipt.get('seq')) is not int or receipt['seq']!=pending['seq']):fail('macro_admission_v4_durable_ack_unverified')
    for native,flags in ((native_before,flags_before),(native_after,flags_after)):
        mask=native.get('applied_mask') if type(native) is dict else None
        if (not work.session.matches_native(native) or type(mask) is not int or not 0<=mask<1<<20 or mask&work.work_mask
                or any(type(native.get(k)) is not int or native[k]!=v for k,v in dict(request=latest,ack=latest,error=0).items())
                or not flags_match(flags,work.flag_names,mask) or not positive(native.get('last_frame'))):fail('macro_admission_v4_current_native_state_unverified')
        phase=native.get('phase')
        if type(phase) is not int or phase not in (1,2):fail()
        expected=dict(self_hook_installed=int(phase==1),lease_held=int(phase==1),active=0)
        if phase==2:expected.update(active=0,applied_mask=0,cleanup_verified=1)
        if any(type(native.get(k)) is not int or native[k]!=v for k,v in expected.items()):fail()
    if (native_before.get('request')!=native_after.get('request') or native_before.get('applied_mask')!=native_after.get('applied_mask')
            or native_before['last_frame']>native_after['last_frame']):fail()
    return NativeLedgerWindowV4(work.session,work.source_evidence_sha256,clear.source_evidence_sha256,latest,native_before['last_frame'],native_after['last_frame'],
        started_monotonic_ns,ended_monotonic_ns,digest(dict(before=before,after=after,native_before=native_before,flags_before=flags_before,
            native_after=native_after,flags_after=flags_after,durable_before=durable_before,durable_after=durable_after)),complete_command_history_verified=True,
        durable_journal_unchanged_and_complete_verified=True,
        ledger_unchanged_across_financial_window=True,original_work_flag_still_clear_verified=True)


def reconciliation_v4(store,command_id,financial,ledger,*,current_game_frame,now_monotonic_ns):
    """Apply through the new store only; old financial APIs are not called."""
    if type(store) is not AdmissionReservationStoreV4:fail('macro_admission_v4_store_required')
    with store._lock:
        row=deepcopy(store.rows.get(command_id))
        if row is None or row['work_ack'] is None or row['clear_fact'] is None:fail()
        fact=AdmissionReconciliationV4('00000000-0000-0000-0000-000000000000',store.session.session_id,row['plan_id'],command_id,
            row['work_ack'].native_seq,row['clear_fact'].native_seq,financial,ledger)
        fact=replace(fact,fact_id=reconciliation_identity(fact))
        store.reconcile(fact,current_game_frame=current_game_frame,now_monotonic_ns=now_monotonic_ns)
        return fact
