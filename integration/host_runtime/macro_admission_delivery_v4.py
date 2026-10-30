"""Narrow proof of refusal before invoking native; never settles unknown work."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .contracts import ContractError
from .resource_admission_reservations_v4 import AdmissionReservationStoreV4
from .resource_settlement_adapter import SettlementSession,digest,uuid_value

_SEAL=object()
DELIVERY_SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class BeforeNativeRefusalProofV4:
    session:SettlementSession
    command_id:str
    reason_code:str
    stage:str
    evidence_sha256:str
    seal:object


class BeforeNativeRefusalV4(ContractError):
    def __init__(self,proof):
        super().__init__('macro_admission_v4_refused_before_native');self.proof=proof


def refusal_before_native_v4(session,command_id,reason,stage,evidence):
    """Trusted guarded call only, while its native-call-entered flag is false."""
    if (type(session) is not SettlementSession or not uuid_value(command_id)
            or stage not in ('before_durable_intent','after_durable_intent','after_raw_prepared_before_publication')
            or type(reason) is not str or not 1<=len(reason)<=160 or not reason.replace('_','').isalnum()):raise ContractError('macro_admission_v4_refusal_proof_invalid')
    return BeforeNativeRefusalV4(BeforeNativeRefusalProofV4(session,command_id,reason,stage,digest(evidence),_SEAL))


def abort_proven_before_native_v4(store,proof):
    """New trusted adapter; old store and unknown transitions remain unchanged."""
    if (type(store) is not AdmissionReservationStoreV4 or type(proof) is not BeforeNativeRefusalProofV4
            or proof.seal is not _SEAL or proof.session!=store.session):raise ContractError('macro_admission_v4_refusal_proof_invalid')
    with store._lock:
        row=store.rows.get(proof.command_id)
        if (row is None or row['status'] not in ('reserved','delivering')
                or any(row[key] is not None for key in ('work_ack','clear_fact','reconciliation_fact'))):
            raise ContractError('macro_admission_v4_refusal_transition_invalid')
        rows=deepcopy(store.rows);rows[proof.command_id]['status']='aborted_before_delivery'
        store._commit(rows)
        return store.public(proof.command_id)


def known_not_invoked_receipt_v4(session,run,command_id,payload,reason,guard_sha256):
    body=dict(source='guarded_admission_no_native_invocation_v4',schema_version=1,
        reason_code='macro_admission_v4_known_not_invoked',native_delivery_attempted=False,native_call_entered=False,
        native_gate_acknowledged=False,refusal_reason=reason,stage='after_durable_intent',run_id=run,command_id=command_id,
        session_id=session.session_id,pid=session.pid,process_creation_filetime=session.process_creation_filetime,
        payload_sha256=digest(payload),guard_source_sha256=guard_sha256,delivery_adapter_source_sha256=DELIVERY_SOURCE_SHA256)
    return dict(body,proof_sha256=digest(body))


def known_not_published_receipt_v4(session,run,command_id,payload,reason,guard_sha256,raw_pair):
    """A new explicit receipt for an entered publisher with no shared request."""
    body=dict(source='guarded_admission_no_native_publication_v4',schema_version=1,
        reason_code='macro_admission_v4_known_not_published',native_delivery_attempted=False,
        publisher_call_entered=True,native_request_published=False,native_gate_acknowledged=False,
        refusal_reason=reason,stage='after_raw_prepared_before_publication',run_id=run,command_id=command_id,
        session_id=session.session_id,pid=session.pid,process_creation_filetime=session.process_creation_filetime,
        payload_sha256=digest(payload),guard_source_sha256=guard_sha256,
        delivery_adapter_source_sha256=DELIVERY_SOURCE_SHA256,raw_unpublished_pair=deepcopy(raw_pair))
    return dict(body,proof_sha256=digest(body))


def project_known_not_invoked_v4(durable,records,session,guard_sha256):
    """Only the new exact guarded receipt can exclude a no-op from raw history.

    Unknown/failed legacy receipts are retained. This never removes unresolved
    IDs or a transport-unknown entry; any raw command with that UUID conflicts.
    """
    if type(durable) is not dict or type(durable.get('commands')) is not list or type(records) is not list:
        raise ContractError('macro_admission_v4_no_invocation_history_unverified')
    from .raw_admission_publisher_v4 import project_unpublished_records_v4
    physical_records,raw_excluded=project_unpublished_records_v4(records,session)
    projected=deepcopy(durable);kept=[];excluded=[];claimed_raw_pairs=[]
    for row in durable['commands']:
        receipt=row.get('receipt')or{}
        source=receipt.get('source')
        if source not in ('guarded_admission_no_native_invocation_v4','guarded_admission_no_native_publication_v4'):
            kept.append(deepcopy(row));continue
        payload=row.get('payload');command=receipt.get('command_id')
        if source=='guarded_admission_no_native_publication_v4':
            pair=receipt.get('raw_unpublished_pair')
            candidates=[value for value in raw_excluded if value['prepared'].get('command_id')==command]
            if (len(candidates)!=1 or pair!=candidates[0] or type(payload) is not dict
                    or pair['prepared'].get('duration_frames')!=payload.get('duration_frames')
                    or type(payload.get('duration_frames')) is not int):
                raise ContractError('macro_admission_v4_no_publication_history_unverified')
            expected=known_not_published_receipt_v4(session,durable.get('run_id'),command,payload,receipt.get('refusal_reason'),guard_sha256,pair)
            claimed_raw_pairs.append(pair['raw_pair_sha256'])
        else:
            if any(item.get('command_id')==command for item in records):raise ContractError('macro_admission_v4_no_invocation_history_unverified')
            expected=known_not_invoked_receipt_v4(session,durable.get('run_id'),command,payload,receipt.get('refusal_reason'),guard_sha256)
        if (row.get('operation')!='macro_policy' or row.get('status')!='failed' or type(payload) is not dict
                or not uuid_value(command) or row.get('request_id')!=command or payload.get('native_command_id')!=command
                or row.get('run_id')!=durable.get('run_id') or digest(receipt)!=digest(expected)
                or type(receipt.get('refusal_reason')) is not str or not receipt['refusal_reason']
                or row.get('command_id') in durable.get('unresolved_command_ids',[])
                or command in durable.get('transport_unknown_command_ids',[])
                or any(item.get('command_id')==command for item in physical_records)):
            raise ContractError('macro_admission_v4_no_invocation_history_unverified')
        excluded.append(deepcopy(row))
    raw_pairs=[pair['raw_pair_sha256'] for pair in raw_excluded]
    if (len(claimed_raw_pairs)!=len(set(claimed_raw_pairs)) or len(raw_pairs)!=len(set(raw_pairs))
            or set(claimed_raw_pairs)!=set(raw_pairs)):
        raise ContractError('macro_admission_v4_unpublished_durable_history_incomplete')
    projected['commands']=kept
    return projected,excluded
