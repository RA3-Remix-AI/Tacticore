"""Cross-process admission barrier for durable STOP and strategic batches.

One admitted native batch owns the mutex through its child ACKs. STOP commits
under the same mutex. Provider admission only holds it through call_started;
an already admitted provider request may finish, but cannot dispatch later.
No game handle, Native call, model call, or lease operation is performed here.
"""
from contextlib import contextmanager
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime,timezone
import json
import hashlib
import os
from pathlib import Path
import time
import uuid

from .contracts import ContractError


class StrategicStopGateV1:
    def __init__(self,run_id,binding,output):
        self.run_id=str(uuid.UUID(run_id));self.session_id=binding.session_id
        self.binding_hash=binding.binding_hash;self.path=Path(output)/'stop.json'
        self.audit=self.path.with_name('strategic-admission.jsonl')
        if not self.path.is_absolute():raise ContractError('strategic_stop_output_not_absolute')
        self.name='Local'+chr(92)+'TacticoreStrategicStopV1_'+self.run_id+'_'+self.binding_hash

    def _event(self,event,**facts):
        raw=self.audit.read_bytes() if self.audit.exists() else b''
        if len(raw)>8*1024*1024 or raw and not raw.endswith(b'\n'):
            raise ContractError('strategic_stop_audit_unknown')
        sequence=0
        if raw:
            last=json.loads(raw.splitlines()[-1]);sequence=last['sequence']
            if (last['run_id']!=self.run_id or last['binding_hash']!=self.binding_hash
                    or type(sequence) is not int or not 0<sequence<16384):
                raise ContractError('strategic_stop_audit_unknown')
        value=dict(schema_version=1,source='strategic_stop_admission_barrier_v1',run_id=self.run_id,
            session_id=self.session_id,binding_hash=self.binding_hash,sequence=sequence+1,
            monotonic_ns=time.monotonic_ns(),utc=datetime.now(timezone.utc).isoformat(),
            process_id=os.getpid(),event=event,**facts)
        self.audit.parent.mkdir(parents=True,exist_ok=True)
        with self.audit.open('ab') as stream:
            stream.write((json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode())
            stream.flush();os.fsync(stream.fileno())
        return value

    @contextmanager
    def _mutex(self,*,stop_writer=False):
        k=c.WinDLL('kernel32',use_last_error=True)
        k.CreateMutexW.argtypes=[c.c_void_p,w.BOOL,w.LPCWSTR];k.CreateMutexW.restype=w.HANDLE
        k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
        k.ReleaseMutex.argtypes=[w.HANDLE];k.CloseHandle.argtypes=[w.HANDLE]
        handle=k.CreateMutexW(None,False,self.name)
        if not handle:raise ContractError('strategic_stop_barrier_unavailable')
        owned=False
        try:
            result=k.WaitForSingleObject(handle,45000)
            owned=result in (0,0x80)
            if not owned:raise ContractError('strategic_stop_barrier_unavailable')
            if result==0x80 and not stop_writer:raise ContractError('strategic_stop_barrier_abandoned')
            yield
        finally:
            if owned:k.ReleaseMutex(handle)
            k.CloseHandle(handle)

    def committed(self):
        if not self.path.exists():return False
        try:
            value=json.loads(self.path.read_bytes())
            if (value.get('session_id')!=self.session_id
                    or value.get('run_id',self.run_id)!=self.run_id
                    or value.get('binding_hash',self.binding_hash)!=self.binding_hash):
                raise ValueError()
            return True
        except (ValueError,OSError):raise ContractError('strategic_stop_binding_changed') from None

    @contextmanager
    def admit(self,kind='provider_request',**facts):
        with self._mutex():
            if kind not in ('provider_request','native_constructor','native_batch'):
                raise ContractError('strategic_stop_admission_kind_invalid')
            if self.committed():
                self._event('admission_denied',kind=kind,**facts)
                raise ContractError('strategic_stop_already_committed')
            ticket=self._event('admitted',kind=kind,admission_id=str(uuid.uuid4()),**facts)
            try:yield ticket
            except BaseException:
                self._event('admission_finished',kind=kind,admission_id=ticket['admission_id'],outcome='failed')
                raise
            else:self._event('admission_finished',kind=kind,admission_id=ticket['admission_id'],outcome='completed')

    def publish_stop(self,atomic):
        with self._mutex(stop_writer=True):
            if self.committed():
                self._event('stop_already_committed',stop_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
                return
            atomic(self.path,dict(session_id=self.session_id,run_id=self.run_id,binding_hash=self.binding_hash,
                source='strategic_stop_admission_barrier_v1',write_started_at_utc=datetime.now(timezone.utc).isoformat()))
            self._event('stop_committed',stop_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
