"""Trusted transport evidence and shared dispatch lock for admission schema4.

No process is opened here. A running Host explicitly lends its existing probe,
journal and qualified readers. This module never starts a Host or grants scope.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import threading
import time

from .contracts import ContractError,SessionBinding
from .macro_durable import DurableMacroTransport
from .resource_settlement_adapter import SettlementSession

GUARDED_SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def fail(code='macro_admission_v4_transport_evidence_unverified'):raise ContractError(code)


class NativeDispatchLockV4:
    """One actual reentrant lock, shared by legacy dispatch and new reconciliation."""
    def __init__(self):self._lock=threading.RLock();self._owner=None;self._depth=0
    def __enter__(self):
        self._lock.acquire();self._owner=threading.get_ident();self._depth+=1;return self
    def __exit__(self,*unused):
        self._depth-=1
        if not self._depth:self._owner=None
        self._lock.release()
    def require_owned(self):
        if self._owner!=threading.get_ident() or self._depth<=0:fail('macro_admission_v4_shared_dispatch_lock_required')


@dataclass(frozen=True)
class NativeWindowSnapshotV4:
    records:list
    durable:dict
    native:dict
    flags:dict
    started_monotonic_ns:int
    ended_monotonic_ns:int
    full_durable:dict
    known_not_invoked_exclusions:list
    full_records:list
    unpublished_record_exclusions:list


class LockedMacroTransportV4:
    """Preserves the legacy transport surface, serializes every physical command."""
    def __init__(self,durable,lock,*,clock=time.monotonic_ns):
        if type(lock) is not NativeDispatchLockV4:fail()
        self.delegate=durable;self.lock=lock;self.session=durable.session;self.clock=clock;self.completions={}
    def apply(self,actions,duration_frames,command_id):
        with self.lock:
            begin=self.clock();receipt=self.delegate.apply(actions,duration_frames,command_id);end=self.clock()
            if command_id not in self.completions:self.completions[command_id]=(begin,end,deepcopy(receipt))
            elif self.completions[command_id][2]!=receipt:fail()
            return receipt
    def close(self):
        with self.lock:return self.delegate.close()


class NativeEvidencePortV4:
    """Collect exact fsynced raw receipts and current native/independent flags."""
    def __init__(self,transport,session,manifest,*,records_reader,durable_reader,native_reader,flags_reader,frame_reader,admission_apply,
                 clock=time.monotonic_ns):
        if (type(transport) is not LockedMacroTransportV4 or type(session) is not SettlementSession
                or manifest.get('protocol_version')!=2 or manifest.get('package_sha256')!=session.package_sha256
                or type(manifest.get('flags')) is not list or len(manifest['flags'])!=20
                or any(type(flag) is not str or not flag for flag in manifest['flags']) or len(set(manifest['flags']))!=20
                or any(not callable(reader) for reader in (records_reader,durable_reader,native_reader,flags_reader,frame_reader,admission_apply,clock))):fail()
        session.validate();self.transport=transport;self.lock=transport.lock;self.session=session;self.manifest=deepcopy(manifest)
        self.records_reader=records_reader;self.durable_reader=durable_reader;self.native_reader=native_reader
        self.flags_reader=flags_reader;self.frame_reader=frame_reader;self.clock=clock
        self.admission_apply=admission_apply

    def projected_records(self):
        from .raw_admission_publisher_v4 import project_unpublished_records_v4
        records=deepcopy(self.records_reader())
        projected,excluded=project_unpublished_records_v4(records,self.session)
        return records,projected,excluded

    def current_frame(self):
        self.lock.require_owned();value=self.frame_reader()
        if type(value) is not int or not 0<value<=0xffffffff:fail()
        return value

    def require_new_work_capacity(self,*,uninvoked_command_id=None):
        """Reserve one ordinary clear and the protocol's final close slot."""
        from .macro_admission_delivery_v4 import project_known_not_invoked_v4
        self.lock.require_owned();native=self.native_reader()
        records,_,_=self.projected_records()
        durable,_=project_known_not_invoked_v4(self.durable_reader(),records,self.session,GUARDED_SOURCE_SHA256)
        if (not self.session.matches_native(native)
                or any(type(native.get(key)) is not int or native[key]!=expected for key,expected in
                    dict(phase=1,error=0,self_hook_installed=1,lease_held=1).items())
                or type(native.get('request')) is not int or type(native.get('ack')) is not int
                or not 0<=native['request']==native['ack']<=2045):
            fail('macro_admission_v4_clear_and_stop_capacity_required')
        commands=durable.get('commands') if type(durable) is dict else None
        ignored=[]
        if uninvoked_command_id is not None and type(commands) is list:
            ignored=[row for row in commands if row.get('request_id')==uninvoked_command_id]
            if (len(ignored)!=1 or ignored[0].get('status')!='dispatching' or ignored[0].get('operation')!='macro_policy'
                    or ignored[0].get('payload',{}).get('native_command_id')!=uninvoked_command_id):fail()
        unresolved=[ident for ident in durable.get('unresolved_command_ids',[]) if not any(row.get('command_id')==ident for row in ignored)] if type(durable) is dict else None
        if (type(durable) is not dict or type(durable.get('unresolved_command_ids')) is not list or unresolved!=[]
                or durable.get('transport_unknown_command_ids')!=[] or type(durable.get('commands')) is not list
                or any(row not in ignored and row.get('operation') in ('macro_policy','macro_policy_stop') and row.get('status') not in ('completed','released') for row in durable['commands'])):
            fail('macro_admission_v4_existing_native_ledger_unresolved')

    def known_pair(self,command_id,receipt):
        self.lock.require_owned();timing=self.transport.completions.get(command_id)
        if timing is None or timing[2]!=receipt or type(timing[1]) is not int:fail('macro_admission_v4_unobserved_transport_completion')
        _,records,_=self.projected_records()
        if type(records) is not list:fail()
        prepared=[row for row in records if row.get('kind')=='command_prepared' and row.get('command_id')==command_id]
        acknowledged=[row for row in records if row.get('kind')=='command_acknowledged' and row.get('command_id')==command_id]
        if (len(prepared)!=1 or len(acknowledged)!=1 or records.index(prepared[0])>=records.index(acknowledged[0])
                or receipt.get('seq')!=acknowledged[0].get('seq') or receipt.get('native_gate_acknowledged') is not True
                or any(type(row.get('monotonic_ns')) is not int for row in (*prepared,*acknowledged))
                or not timing[0]<=prepared[0]['monotonic_ns']<=acknowledged[0]['monotonic_ns']<=timing[1]):
            fail('macro_admission_v4_raw_receipt_or_completion_mismatch')
        return deepcopy(prepared[0]),deepcopy(acknowledged[0]),timing[1]

    def guarded_admission_apply(self,actions,duration,command_id,*,prepare_duration,last_check,raw_ack_check):
        """Separate durable path: recheck after fsync, before raw.apply is called.

        The original thirteen still use the unchanged legacy Durable adapter.
        Only this call can sign the narrow not-invoked refusal proof.
        """
        from .macro_admission_delivery_v4 import refusal_before_native_v4,known_not_invoked_receipt_v4
        from .raw_admission_publisher_v4 import PublicationRefusedV4,validate_publication_refusal_v4
        self.lock.require_owned();delegate=self.transport.delegate
        if type(delegate) is not DurableMacroTransport:fail('macro_admission_v4_guarded_durable_required')
        journal,run=delegate.journal,delegate.run_id
        if any(row.get('request_id')==command_id for row in journal.commands_for_run(run)):
            fail('macro_admission_v4_existing_delivery_not_refusable')
        if any(row.get('command_id')==command_id for row in self.records_reader()):
            fail('macro_admission_v4_existing_delivery_not_refusable')
        begin=self.clock()
        try:
            duration=prepare_duration()
            if type(duration) is not int or not 1<=duration<=600:fail()
            last_check(None)
        except Exception as error:
            raise refusal_before_native_v4(self.session,command_id,getattr(error,'code','macro_admission_v4_last_gate_unavailable'),
                'before_durable_intent',dict(command_id=command_id,native_call_entered=False,started_monotonic_ns=begin)) from None
        row=journal.reserve_command(run,command_id,'macro_policy',dict(actions=list(actions),duration_frames=duration,native_command_id=command_id))
        if not row['created']:fail('macro_admission_v4_existing_delivery_not_refusable')
        journal.mark_dispatching(run,command_id)
        try:last_check(command_id)
        except Exception as error:
            reason=getattr(error,'code','macro_admission_v4_last_gate_unavailable')
            receipt=known_not_invoked_receipt_v4(self.session,run,command_id,
                dict(actions=list(actions),duration_frames=duration,native_command_id=command_id),reason,GUARDED_SOURCE_SHA256)
            journal.record_outcome(run,command_id,'failed',receipt)
            raise refusal_before_native_v4(self.session,command_id,reason,'after_durable_intent',
                dict(command_id=command_id,native_call_entered=False,receipt=receipt)) from None
        # From this exact boundary onwards every exception is delivery-unknown;
        # it can never produce a before-native refusal or release the buffer.
        try:
            raw=self.admission_apply(list(actions),duration,command_id,last_check=lambda:last_check(command_id))
            returned=self.clock();_,records,_=self.projected_records()
            prepared=[item for item in records if item.get('kind')=='command_prepared' and item.get('command_id')==command_id]
            acks=[item for item in records if item.get('kind')=='command_acknowledged' and item.get('command_id')==command_id]
            if (len(prepared)!=1 or len(acks)!=1 or records.index(prepared[0])>=records.index(acks[0])
                    or any(type(item.get('monotonic_ns')) is not int for item in (*prepared,*acks))
                    or not begin<=prepared[0]['monotonic_ns']<=acks[0]['monotonic_ns']<=returned
                    or raw.get('seq')!=acks[0].get('seq') or raw.get('native_gate_acknowledged') is not True):fail()
            raw_ack_check(prepared[0],acks[0],returned)
            bounds=acks[0]['native'];start,deadline=bounds.get('last_frame'),bounds.get('deadline_frame')
            receipt=dict(seq=raw['seq'],native_gate_acknowledged=True,native_effect_verified=False,
                native_start_frame=deadline-duration,native_deadline_frame=deadline)
            if type(start) is not int or type(deadline) is not int or not 0<deadline-duration<=start<deadline:fail()
            journal.record_outcome(run,command_id,'completed',receipt)
            end=self.clock();self.transport.completions[command_id]=(begin,end,deepcopy(receipt))
            return receipt
        except PublicationRefusedV4 as error:
            from .macro_admission_delivery_v4 import known_not_published_receipt_v4
            proof=validate_publication_refusal_v4(error,self.session,command_id)
            prepared=proof['prepared'];refused=proof['refused']
            expected_mask=sum(1<<i for i,row in enumerate(self.manifest['consumers']) if row['action'] in actions)
            if (prepared.get('kind_code'),prepared.get('mask'),prepared.get('duration_frames'))!=(1,expected_mask,duration):
                raise ContractError('macro_admission_v4_no_publication_payload_mismatch') from error
            pair=dict(prepared=prepared,refused=refused,raw_pair_sha256=proof['raw_pair_sha256'])
            receipt=known_not_published_receipt_v4(self.session,run,command_id,
                dict(actions=list(actions),duration_frames=duration,native_command_id=command_id),proof['reason_code'],GUARDED_SOURCE_SHA256,pair)
            journal.record_outcome(run,command_id,'failed',receipt)
            raise refusal_before_native_v4(self.session,command_id,proof['reason_code'],
                'after_raw_prepared_before_publication',dict(command_id=command_id,native_request_published=False,receipt=receipt)) from None
        except BaseException:
            current=journal.get_command(run,command_id)
            if current['status']=='dispatching':
                journal.record_outcome(run,command_id,'uncertain',dict(reason_code='macro_admission_v4_delivery_or_raw_ack_unknown'))
            raise

    def snapshot(self):
        from .macro_admission_delivery_v4 import project_known_not_invoked_v4
        self.lock.require_owned();begin=self.clock()
        full_records,records,record_exclusions=self.projected_records();full=deepcopy(self.durable_reader())
        durable,excluded=project_known_not_invoked_v4(full,full_records,self.session,GUARDED_SOURCE_SHA256)
        native=deepcopy(self.native_reader());flags=deepcopy(self.flags_reader());end=self.clock()
        if type(begin) is not int or type(end) is not int or not 0<=begin<=end:fail()
        mask=native.get('applied_mask') if type(native) is dict else None
        if (not self.session.matches_native(native) or type(mask) is not int or not 0<=mask<1<<20
                or type(native.get('cleanup_verified')) is not int or native['cleanup_verified']!=int(mask==0)):
            fail('macro_admission_v4_current_native_cleanup_unknown')
        return NativeWindowSnapshotV4(records,durable,native,flags,begin,end,full,excluded,full_records,record_exclusions)


def create_native_evidence_port_v4(raw_probe,journal,run_id,session,*,read_flags,lock=None,clock=time.monotonic_ns,admission_apply=None):
    """Production adapter over existing handles and exact raw transport files."""
    lock=NativeDispatchLockV4() if lock is None else lock
    if type(session) is not SettlementSession or not callable(read_flags):fail()
    session.validate();manifest=deepcopy(raw_probe.manifest)
    registered=journal._run(run_id)
    binding=SessionBinding.from_dict(json.loads(registered['binding']))
    from .session_discovery_native import require_creation
    require_creation(binding.game_process_start,session.process_creation_filetime)
    if (binding.session_id!=session.session_id or binding.game_process_id!=session.pid or binding.player_id!=3
            or binding.game_sha256!=session.executable_sha256 or binding.mod_sha256!=session.package_sha256
            or raw_probe.session.get('start_time')!=binding.game_process_start):fail('macro_admission_v4_durable_session_binding_mismatch')
    if (raw_probe.session.get('session_id')!=session.session_id or raw_probe.session.get('pid')!=session.pid
            or raw_probe.session.get('process_creation_filetime')!=session.process_creation_filetime
            or raw_probe.session.get('mod_sha256')!=session.package_sha256
            or not session.matches_native(raw_probe.native_status())):fail()
    durable=DurableMacroTransport(raw_probe,journal,run_id)
    locked=LockedMacroTransportV4(durable,lock,clock=clock)
    if admission_apply is None:
        from .raw_admission_publisher_v4 import create_raw_admission_publisher_v4
        admission_apply=create_raw_admission_publisher_v4(raw_probe,session).apply
    record_path=Path(raw_probe.output)/'policy-probe.jsonl'
    def records():
        if raw_probe.manifest!=manifest:fail()
        with record_path.open('rb') as stream:raw=stream.read(256*1024*1024+1)
        if len(raw)>256*1024*1024 or not raw.endswith(b'\n'):fail('macro_admission_v4_complete_fsynced_records_required')
        result=[json.loads(line) for line in raw.splitlines()]
        if any(type(row) is not dict for row in result):fail()
        return result
    def ledger():
        commands=journal.commands_for_run(run_id);unknown=[ident for ident,row in raw_probe.ledger.items() if row.get('status')!='acknowledged']
        if raw_probe.pending:unknown.append('native_pending')
        unresolved=[row['command_id'] for row in journal.unresolved(run_id) if row.get('operation')!='host_start']
        return dict(session_id=session.session_id,pid=session.pid,process_creation_filetime=session.process_creation_filetime,
            run_id=run_id,commands=commands,unresolved_command_ids=unresolved,transport_unknown_command_ids=unknown)
    def frame():
        game=int(session.game_identity[0],0)
        if raw_probe.memory.u32(0xcd8ce4)!=game:fail('macro_admission_v4_current_game_identity_changed')
        return raw_probe.memory.u32(game+0x50)
    return NativeEvidencePortV4(locked,session,manifest,records_reader=records,durable_reader=ledger,
        native_reader=raw_probe.native_status,flags_reader=lambda:read_flags(raw_probe.memory.read,manifest['flags']),
        frame_reader=frame,admission_apply=admission_apply,clock=clock)


def create_expansion_controller_v4(raw_probe,journal,run_id,scope,session,effective_hash,event,*,
        read_flags,cost_supplier=None,financial_supplier=None,persist=None,store=None,clock=time.monotonic_ns,admission_apply=None):
    """Explicit trusted injection; no automatic reader qualification or fallback."""
    from .macro_expansion_runtime_v4 import MacroExpansionControllerV4
    from .resource_admission_reservations_v4 import AdmissionReservationStoreV4
    if cost_supplier is not None:
        from .macro_admission_factory_v4 import QualifiedAdmissionCostSupplierV4
        if type(cost_supplier) is not QualifiedAdmissionCostSupplierV4:fail('macro_admission_v4_qualified_cost_supplier_required')
    if financial_supplier is not None:
        from .macro_cost_factory_v2 import QualifiedQuotelessFinancialSupplierV4
        if type(financial_supplier) is not QualifiedQuotelessFinancialSupplierV4:fail('macro_admission_v4_qualified_financial_supplier_required')
    for supplier in (cost_supplier,financial_supplier):
        if supplier is None:continue
        guards=getattr(supplier,'required_guard_files',None)
        if (not callable(supplier) or getattr(supplier,'session',None)!=session or type(guards) is not dict or not guards
                or any(type(path) is not str or type(digest) is not str or len(digest)!=64 for path,digest in guards.items())):
            fail('macro_admission_v4_qualified_supplier_binding_required')
    if store is None:
        if not callable(persist):fail('macro_admission_v4_durable_store_required')
        store=AdmissionReservationStoreV4(session,persist=persist)
        persist(store.snapshot())
    elif type(store) is not AdmissionReservationStoreV4 or store.session!=session or not callable(store.persist):fail()
    port=create_native_evidence_port_v4(raw_probe,journal,run_id,session,read_flags=read_flags,clock=clock,admission_apply=admission_apply)
    return MacroExpansionControllerV4(port,scope,session.session_id,effective_hash,event,
        cost_supplier=cost_supplier,financial_supplier=financial_supplier,reservation_store=store)
