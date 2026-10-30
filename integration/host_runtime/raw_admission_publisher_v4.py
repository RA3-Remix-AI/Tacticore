"""Publish schema4 work after the last fresh gate and all blocking preparation.

Borrows the existing frozen protocol2 probe. Old actions still call its original
apply. A refused preparation is retained with an explicit unpublished record;
it consumes no native sequence and is never an acknowledgement.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from .contracts import ContractError
from .resource_settlement_adapter import SettlementSession,digest,uuid_value,flags_match

ROOT=Path(__file__).resolve().parents[2]
CLIENT=ROOT/'native-ai/macro-policy-runtime-v2/client.py'
CLIENT_SHA='c67cbb37368a415e6fc1a56be0bef631fdeb1a993dde6f8ab3f7559685b666ae'
SOURCE_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
REFUSED='command_publication_refused_v4'
REASON='macro_admission_v4_last_publication_gate_unavailable'
_SEAL=object()


def fail(code='macro_admission_v4_publication_evidence_unverified'):raise ContractError(code)


class PublicationRefusedV4(ContractError):
    def __init__(self,proof):
        super().__init__('macro_admission_v4_publication_refused');self.proof=proof;self._seal=_SEAL


def _native_unchanged(before,after,session,prior):
    return (session.matches_native(before) and session.matches_native(after)
        and type(prior) is int and 0<=prior<=2045
        and all(type(v.get(k)) is int and v[k]==prior for v in (before,after) for k in ('request','ack'))
        and all(type(v.get(k)) is int and v[k]==expected for v in (before,after)
            for k,expected in dict(active=0,phase=1,error=0,self_hook_installed=1,lease_held=1).items()))


def _validate_pair(prepared,refused,session):
    keys={'kind','session_id','pid','monotonic_ns','command_id','seq','prepared_sha256',
        'process_creation_filetime','publication_source_sha256','client_source_sha256',
        'reason_code','native_request_published','raw_seq_before','raw_seq_after','native_before','native_after','proof_sha256'}
    prepared_keys={'kind','session_id','pid','monotonic_ns','command_id','seq','kind_code','mask','duration_frames',
        'process_creation_filetime','publication_source_sha256','client_source_sha256','publication_prior_seq','publication_native_before'}
    if (type(prepared) is not dict or set(prepared)!=prepared_keys or type(refused) is not dict or set(refused)!=keys
            or prepared.get('kind')!='command_prepared' or refused.get('kind')!=REFUSED
            or not uuid_value(prepared.get('command_id')) or refused['command_id']!=prepared['command_id']
            or any((row.get('session_id'),row.get('pid'))!=(session.session_id,session.pid) for row in (prepared,refused))
            or type(prepared.get('pid')) is not int or type(refused['pid']) is not int
            or type(prepared.get('seq')) is not int or refused['seq']!=prepared['seq']
            or type(refused['seq']) is not int or refused['seq']!=refused['raw_seq_before']+1
            or type(prepared.get('monotonic_ns')) is not int or type(refused['monotonic_ns']) is not int
            or not 0<=prepared['monotonic_ns']<=refused['monotonic_ns']
            or refused['process_creation_filetime']!=session.process_creation_filetime
            or type(refused['process_creation_filetime']) is not int
            or refused['publication_source_sha256']!=SOURCE_SHA or refused['client_source_sha256']!=CLIENT_SHA
            or refused['prepared_sha256']!=digest(prepared) or refused['reason_code']!=REASON
            or refused['native_request_published'] is not False
            or type(refused['raw_seq_after']) is not int or refused['raw_seq_after']!=refused['raw_seq_before']
            or not _native_unchanged(refused['native_before'],refused['native_after'],session,refused['raw_seq_before'])
            or prepared.get('publication_source_sha256')!=SOURCE_SHA
            or prepared.get('client_source_sha256')!=CLIENT_SHA
            or prepared.get('process_creation_filetime')!=session.process_creation_filetime
            or prepared.get('publication_prior_seq')!=refused['raw_seq_before']
            or prepared.get('publication_native_before')!=refused['native_before']
            or type(prepared.get('kind_code')) is not int or prepared['kind_code']!=1
            or type(prepared.get('mask')) is not int or not 0<prepared['mask']<1<<20
            or type(prepared.get('duration_frames')) is not int or not 1<=prepared['duration_frames']<=600):fail()
    body={k:v for k,v in refused.items() if k not in ('kind','session_id','pid','monotonic_ns','proof_sha256')}
    if refused['proof_sha256']!=digest(body):fail()


def project_unpublished_records_v4(records,session):
    """Exclude only complete source-bound unpublished pairs; retain originals."""
    if type(session) is not SettlementSession or type(records) is not list or any(type(r) is not dict for r in records):fail()
    session.validate();removed=set();excluded=[]
    for i,refused in enumerate(records):
        if refused.get('kind')!=REFUSED:continue
        command=refused.get('command_id')
        candidates=[(j,row) for j,row in enumerate(records) if row.get('kind')=='command_prepared' and row.get('command_id')==command]
        if (len(candidates)!=1 or any(row.get('command_id')==command and j not in (i,candidates[0][0]) for j,row in enumerate(records))):fail()
        j,prepared=candidates[0]
        if j>=i or j in removed:fail()
        _validate_pair(prepared,refused,session)
        prior_acks=[row for row in records[:j] if row.get('kind')=='command_acknowledged']
        if refused['raw_seq_before']!=(prior_acks[-1].get('seq') if prior_acks else 0):fail()
        # Nothing may physically dispatch between the preparation and its
        # refusal. Read-only observations carry no command UUID.
        if any(row.get('kind') in ('command_prepared','command_acknowledged','transport_closed',REFUSED) for row in records[j+1:i]):fail()
        removed.update((i,j));excluded.append(dict(prepared=deepcopy(prepared),refused=deepcopy(refused),
            raw_pair_sha256=digest(dict(prepared=prepared,refused=refused))))
    return [deepcopy(r) for i,r in enumerate(records) if i not in removed],excluded


def validate_publication_refusal_v4(error,session,command_id):
    if type(error) is not PublicationRefusedV4 or error._seal is not _SEAL or type(error.proof) is not dict:fail()
    proof=error.proof
    if set(proof)!={'reason_code','prepared','refused','raw_pair_sha256'} or proof['reason_code']!=REASON:fail()
    if proof['prepared'].get('command_id')!=command_id:fail()
    _validate_pair(proof['prepared'],proof['refused'],session)
    if proof['raw_pair_sha256']!=digest(dict(prepared=proof['prepared'],refused=proof['refused'])):fail()
    return deepcopy(proof)


class RawAdmissionPublisherV4:
    def __init__(self,raw,session):
        if type(session) is not SettlementSession:fail()
        session.validate()
        method=getattr(type(raw),'command',None)
        if (type(raw).__name__!='MacroPolicyProbe' or not hasattr(method,'__code__')
                or Path(method.__code__.co_filename).resolve()!=CLIENT.resolve()
                or hashlib.sha256(CLIENT.read_bytes()).hexdigest()!=CLIENT_SHA):fail('macro_admission_v4_frozen_raw_probe_required')
        self.raw=raw;self.session=session;self.api=method.__globals__;self.lock=threading.RLock();self.refusals={}
        if not session.matches_native(raw.native_status()):fail()

    def _last_record(self):
        path=Path(self.raw.output)/'policy-probe.jsonl'
        with path.open('rb') as stream:raw=stream.read(256*1024*1024+1)
        if len(raw)>256*1024*1024 or not raw.endswith(b'\n'):fail()
        row=json.loads(raw.splitlines()[-1])
        if type(row) is not dict:fail()
        return row

    def apply(self,actions,duration,command_id,*,last_check):
        with self.lock:return self._apply(actions,duration,command_id,last_check)

    def _apply(self,actions,duration,command_id,last_check):
        raw=self.raw;session=self.session;api=self.api
        mask=api['action_mask'](actions,raw.manifest)
        if not uuid_value(command_id) or not callable(last_check) or type(duration) is not int or not 1<=duration<=600 or mask<=0:fail()
        fingerprint=(1,mask,duration)
        if command_id in self.refusals:
            old,proof=self.refusals[command_id]
            if old!=fingerprint:fail('macro_command_id_conflict')
            raise PublicationRefusedV4(deepcopy(proof))
        if command_id in raw.ledger:
            old=raw.ledger[command_id]
            if old['fingerprint']!=fingerprint:fail('macro_command_id_conflict')
            if old['status']!='acknowledged':fail('macro_previous_command_unknown')
            return old['receipt']
        if raw.pending:fail('macro_outstanding_command_unknown')
        # Every potentially blocking raw preparation, including source/session
        # reads, profile RPM, idle wait, log fsync and log readback, is before
        # the final freshness gate below.
        if raw.session_path.read_bytes()!=raw.session_raw or api['inspect_player'](raw.memory.read,raw.owner)!=raw.native:
            fail('macro_session_identity_changed')
        state=raw.state;api['wait_native_idle'](state)
        prior=raw.seq;before=raw.native_status()
        if not _native_unchanged(before,before,session,prior) or before.get('phase')!=1 or before.get('error')!=0:fail()
        seq=prior+1
        raw.event('command_prepared',command_id=command_id,seq=seq,kind_code=1,mask=mask,duration_frames=duration,
            process_creation_filetime=session.process_creation_filetime,publication_source_sha256=SOURCE_SHA,
            client_source_sha256=CLIENT_SHA,publication_prior_seq=prior,publication_native_before=before)
        prepared=self._last_record()
        if (prepared.get('command_id'),prepared.get('seq'),prepared.get('mask'))!=(command_id,seq,mask):fail()
        try:
            last_check()
            after=raw.native_status()
            if (raw.seq!=prior or raw.pending or command_id in raw.ledger or not _native_unchanged(before,after,session,prior)
                    or after.get('phase')!=1 or after.get('error')!=0):fail()
        except Exception:
            after=raw.native_status()
            if raw.seq!=prior or raw.pending or command_id in raw.ledger or not _native_unchanged(before,after,session,prior):raise
            body=dict(command_id=command_id,seq=seq,prepared_sha256=digest(prepared),process_creation_filetime=session.process_creation_filetime,
                publication_source_sha256=SOURCE_SHA,client_source_sha256=CLIENT_SHA,reason_code=REASON,native_request_published=False,
                raw_seq_before=prior,raw_seq_after=raw.seq,native_before=before,native_after=after)
            raw.event(REFUSED,**body,proof_sha256=digest(body));refused=self._last_record()
            _validate_pair(prepared,refused,session)
            proof=dict(reason_code=REASON,prepared=prepared,refused=refused,raw_pair_sha256=digest(dict(prepared=prepared,refused=refused)))
            self.refusals[command_id]=(fingerprint,deepcopy(proof));raise PublicationRefusedV4(proof) from None
        # No file/RPM/wait/callback occurs from the completed last_check to
        # shared request publication. From here on every exception is unknown.
        raw.seq=seq;raw.pending=True;raw.ledger[command_id]=dict(fingerprint=fingerprint,status='unknown')
        state.kind=1;state.mask=mask;state.duration_frames=duration;state.request=seq
        deadline=time.monotonic()+5;flags=None;ack_native=None
        while time.monotonic()<deadline:
            if state.phase==4 or raw.host.poll() is not None:break
            if state.ack==seq and state.active==0:
                # Native writes ack before dropping its callback lock. Wait
                # read-only for a stable unlocked independent flag window.
                first=raw.native_status();observed=api['inspect_flags'](raw.memory.read,raw.manifest['flags']);last=raw.native_status()
                required=dict(request=seq,ack=seq,active=0,phase=1,error=0,applied_mask=mask,cleanup_verified=0,self_hook_installed=1,lease_held=1)
                if (all(session.matches_native(v) and all(type(v.get(k)) is int and v[k]==wanted for k,wanted in required.items()) for v in (first,last))
                        and first.get('deadline_frame')==last.get('deadline_frame') and type(first.get('last_frame')) is int
                        and type(last.get('last_frame')) is int and first['last_frame']<=last['last_frame']
                        and flags_match(observed,raw.manifest['flags'],mask)):
                    flags=observed;ack_native=last;break
            time.sleep(.01)
        if ack_native is None:
            raw.event('command_unknown',command_id=command_id,seq=seq,native=raw.native_status());fail('macro_native_command_unknown')
        receipt=dict(command_id=command_id,seq=seq,native_gate_acknowledged=True,independent_flags=flags,
            native=ack_native,effect_verified=False,capability_granted=False)
        raw.ledger[command_id].update(status='acknowledged',receipt=receipt);raw.pending=False
        raw.event('command_acknowledged',**receipt);return receipt


def create_raw_admission_publisher_v4(raw_probe,session):return RawAdmissionPublisherV4(raw_probe,session)
