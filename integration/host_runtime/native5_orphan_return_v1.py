"""Explicit STOP recovery after a Native5 product Host has died.

Only existing read-only mappings and query handles are used. This contract
does not invent the lost helper exit code or rewrite strategic delivery.
Older epochs without a persisted helper incarnation remain unknown.
"""
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from .contracts import ContractError
from .native5_helper_identity_v1 import ended_incarnation
from .strategic_unified_release_v5 import _verified_current_restoration,verified_journal

ROOT=Path(__file__).resolve().parents[2]
KIND='strategic_unified_orphan_return_v1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())


def readonly_memory(memory_type,pid,session):
    """Close partial query handles if the frozen Memory constructor fails."""
    memory=memory_type.__new__(memory_type)
    try:memory_type.__init__(memory,pid,session)
    except BaseException:
        if getattr(memory,'handle',None):
            try:memory.close()
            finally:memory.handle=None
        raise
    return memory


def collect_current(client,reader):
    original=client.Memory
    client.Memory=lambda pid,session:readonly_memory(original,pid,session)
    try:return client.Probe.independent_release(reader)
    finally:client.Memory=original


def archived_sha(row,path):
    output=Path(row['output_path']);index=load(output/'sources.json')['sources']
    rows=[r for r in index if Path(r['path']).resolve()==Path(path).resolve()]
    if len(rows)!=1:raise ValueError('orphan_source_not_frozen')
    record=rows[0]
    if Path(record['copy']).name!=record['copy'] or sha(output/'source'/record['copy'])!=record['sha256']:
        raise ValueError('orphan_archive_changed')
    bundle=load(output/'source'/index[2]['copy'])
    if bundle.get('schema_version')!=13 or bundle['pins'].get(str(Path(path).resolve()))!=record['sha256']:
        raise ValueError('orphan_source_not_pinned')
    return record['sha256']


def inputs(row,binding,host_receipt):
    from .session_discovery_native import frozen_manifest
    session=load(row['session_path']);manifest=frozen_manifest(row,session,binding)
    if manifest.get('protocol_version')!=5:raise ValueError('orphan_requires_native5')
    report=ROOT/'reports'/('macro-desktop-'+row['run_id'])
    identity=load(report/'helper-identity.json')
    native_binding=identity['native_binding'];helper=identity['helper'];parent=identity['parent']
    for process in (parent,helper):
        if (type(process.get('pid')) is not int or not 0<process['pid']<=0xffffffff
                or type(process.get('process_creation_filetime')) is not int
                or not 0<process['process_creation_filetime']<=0xffffffffffffffff):
            raise ValueError('orphan_os_identity_bounds')
    index=load(Path(row['output_path'])/'sources.json')['sources']
    frozen=load(Path(row['output_path'])/'source'/index[2]['copy'])['pins']
    parent_start=datetime.fromtimestamp((parent['process_creation_filetime']-116444736000000000)/10000000,timezone.utc).isoformat()
    if (identity.get('kind')!='native5_helper_identity_v1' or identity['session_id']!=binding.session_id
            or identity['game_pid']!=binding.game_process_id or identity['game_creation_filetime']!=session['process_creation_filetime']
            or identity['capture_source_sha256']!=archived_sha(row,ROOT/'integration/host_runtime/native5_helper_identity_v1.py')
            or parent['pid']!=host_receipt['host_pid'] or parent_start!=host_receipt['host_start_time']
            or helper.get('alive') is not True or parent.get('alive') is not True
            or type(helper['pid']) is not int or helper['pid']<=0
            or type(helper['process_creation_filetime']) is not int or helper['process_creation_filetime']<=0
            or Path(helper['image']).name.lower()!='manager_host.exe'
            or identity['helper_image_sha256']!=manifest['artifacts']['manager_host.exe']
            or frozen.get(str(Path(helper['image']).resolve()))!=identity['helper_image_sha256']
            or frozen.get(str(Path(helper['image']).parent/'build-manifest.json'))!=identity['build_manifest_sha256']
            or bytes(native_binding['session'])!=uuid.UUID(binding.session_id).bytes
            or bytes(native_binding['package']).hex()!=binding.mod_sha256
            or bytes(native_binding['sources']).hex()!=manifest['source_closure_sha256']):
        raise ValueError('orphan_helper_seal_mismatch')
    archived_sha(row,ROOT/'integration/host_runtime/strategic_unified_transport_v5.py')
    return session,manifest,report,identity


def ended_certificate(value,expected=None):
    if (not isinstance(value,dict) or value.get('ended') is not True or value.get('exit_code') is not None):return False
    if value.get('reason')=='pid_absent':return set(value)=={'ended','reason','exit_code'}
    current=value.get('current')
    if (value.get('reason') not in ('different_incarnation','same_incarnation_ended') or not isinstance(current,dict)
            or expected is None or current.get('pid')!=expected['pid']
            or type(current.get('process_creation_filetime')) is not int
            or current['process_creation_filetime']<=0 or type(current.get('alive')) is not bool):return False
    if value['reason']=='different_incarnation':return current['process_creation_filetime']!=expected['process_creation_filetime']
    return (current['process_creation_filetime']==expected['process_creation_filetime']
        and current['alive'] is False
        and current.get('image') in (None,expected['image']))


def verified_capture(value,raw_journal,session,manifest,identity,binding,run_id):
    """File-only: this is deliberately separate from the old exit-code contract."""
    try:
        p=value['restoration']
        return (value['kind']==KIND and value['run_id']==run_id and value['binding']==binding.public()
            and value['helper_identity']==identity and value['helper_exit_code'] is None
            and ended_certificate(value['parent_ended'],identity.get('parent'))
            and ended_certificate(value['helper_ended_before'],identity.get('helper'))
            and ended_certificate(value['helper_ended_after'],identity.get('helper'))
            and type(value['native_commands_issued']) is int and value['native_commands_issued']==0
            and value['mapping_access']=='FILE_MAP_READ'
            and p['native']['binding']==identity['native_binding']
            and value['native_journal_sha256']==hashlib.sha256(raw_journal).hexdigest()
            and verified_journal(raw_journal,p['native'])
            and _verified_current_restoration(p,pid=binding.game_process_id,ticks=session['process_creation_filetime'],
                session_id=binding.session_id,package=binding.mod_sha256,flags=manifest['flags'],closure=manifest['source_closure_sha256']))
    except (KeyError,ValueError,TypeError,OverflowError):return False


def capture(row,binding,host_receipt):
    session,manifest,report,identity=inputs(row,binding,host_receipt)
    parent=ended_incarnation(identity['parent']);before=ended_incarnation(identity['helper'])
    if not ended_certificate(parent,identity['parent']) or not ended_certificate(before,identity['helper']):raise ValueError('orphan_process_still_alive')
    from .strategic_unified_transport_v5 import native_module
    _,client=native_module()
    k=c.WinDLL('kernel32',use_last_error=True)
    k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE
    k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
    k.UnmapViewOfFile.argtypes=[c.c_void_p];k.CloseHandle.argtypes=[w.HANDLE]
    mapping=k.OpenFileMappingW(4,False,'Local'+chr(92)+'RA3StrategicCommanderV5_'+str(session['pid']))
    if not mapping:raise c.WinError(c.get_last_error())
    view=None
    try:
        view=k.MapViewOfFile(mapping,4,0,0,1440)
        if not view:raise c.WinError(c.get_last_error())
        state=client.Shared.from_address(view)
        status=lambda:client.projection(client.Shared.from_buffer_copy(c.string_at(view,1440)))
        if status()['binding']!=identity['native_binding']:raise ValueError('orphan_native_epoch_changed')
        # Borrow only the frozen collector's read method. No Probe constructor,
        # heartbeat, native command, helper spawn, close or lease wait occurs.
        reader=SimpleNamespace(kernel=k,session=session,manifest=manifest,state=state,
            binding=bytes(state.binding),status=status,unknown=None)
        proof=collect_current(client,reader)
        journal=ROOT/'reports/strategic-unified-native-journal'/(uuid.UUID(session['session_id']).hex+'.bin')
        # Successful attach already created this durable journal, including
        # the zero-record case. A missing file is unknown, not an empty file.
        raw=journal.read_bytes()
        proof.update(native_durable_journal_verified=bool(raw),native_durable_journal_records=len(raw)//1360)
        after=ended_incarnation(identity['helper'])
        value=dict(kind=KIND,run_id=row['run_id'],binding=binding.public(),helper_identity=identity,
            parent_ended=parent,helper_ended_before=before,helper_ended_after=after,helper_exit_code=None,
            restoration=proof,native_journal_sha256=hashlib.sha256(raw).hexdigest(),
            capture_source_sha256=sha(__file__),native_commands_issued=0,mapping_access='FILE_MAP_READ')
        if not verified_capture(value,raw,session,manifest,identity,binding,row['run_id']):
            raise ValueError('orphan_restoration_not_verified')
        return value,raw
    finally:
        if view:k.UnmapViewOfFile(view)
        k.CloseHandle(mapping)


def verified_return(backend,row,binding,host_receipt):
    try:
        session,manifest,report,identity=inputs(row,binding,host_receipt)
        output=Path(row['output_path']);value=load(output/'native-orphan-return.json')
        raw=(output/'native-orphan-journal.bin').read_bytes()
        stop=backend.journal.get_command(row['run_id'],'macro-stop');receipt=stop['receipt'] or {}
        from .strategic_unified_unknown_return_v5 import covered_unknown_ownership
        return (value['capture_source_sha256']==archived_sha(row,__file__)
            and stop['status']=='released' and receipt.get('native_release_contract')==KIND
            and receipt.get('orphan_return_sha256')==sha(output/'native-orphan-return.json')
            and receipt.get('binding_hash')==binding.binding_hash
            and receipt.get('host_pid')==host_receipt['host_pid']
            and receipt.get('host_start_time')==host_receipt['host_start_time']
            and receipt.get('native_release_verified') is True
            and verified_capture(value,raw,session,manifest,identity,binding,row['run_id'])
            and covered_unknown_ownership(backend.journal.unresolved(row['run_id']),
                backend.journal.commands_for_run(row['run_id']),stop))
    except (OSError,ValueError,KeyError,TypeError,OverflowError,ContractError):return False


def recover_after_stop(backend,row,binding,host_receipt,atomic):
    """Idempotent maintenance only after explicit durable STOP and owner death."""
    from .strategic_stop_gate_v1 import StrategicStopGateV1
    from .journal import JournalError
    gate=StrategicStopGateV1(row['run_id'],binding,Path(row['output_path']))
    if not gate.committed():return False
    if verified_return(backend,row,binding,host_receipt):return True
    with gate._mutex(stop_writer=True):
        if backend.spawner.identity(host_receipt['host_pid'])==host_receipt['host_start_time']:return False
        if verified_return(backend,row,binding,host_receipt):return True
        output=Path(row['output_path']);path=output/'native-orphan-return.json'
        if path.exists():
            session,manifest,_,identity=inputs(row,binding,host_receipt);value=load(path)
            raw=(output/'native-orphan-journal.bin').read_bytes()
            if (value['capture_source_sha256']!=archived_sha(row,__file__)
                    or not verified_capture(value,raw,session,manifest,identity,binding,row['run_id'])):return False
            # An uncommitted leftover file is not a release receipt. Re-read
            # the live epoch, roots, baseline, helper end and durable journal
            # before changing any ledger row. Preserve the original file.
            fresh,fresh_raw=capture(row,binding,host_receipt)
            if (fresh['capture_source_sha256']!=archived_sha(row,__file__)
                    or fresh['restoration']['native']!=value['restoration']['native']
                    or fresh['helper_identity']!=value['helper_identity'] or fresh_raw!=raw):return False
        else:
            value,raw=capture(row,binding,host_receipt)
            if value['capture_source_sha256']!=archived_sha(row,__file__):return False
            raw_path=output/'native-orphan-journal.bin'
            if raw_path.exists():
                if raw_path.read_bytes()!=raw:return False
            else:
                with raw_path.open('xb') as stream:stream.write(raw);stream.flush();__import__('os').fsync(stream.fileno())
            atomic(path,value)
        # The owner is dead and the whole epoch is independently returned.
        # Interrupted delivery stays uncertain; no Native operation is replayed.
        # Do not reconcile concurrent broker-owned host_stop RPCs. Only the
        # dead Host's own operations can have been interrupted by its death.
        owned={'host_start','macro_policy','native_strategic_v5','macro_policy_stop'}
        for pending in backend.journal.unresolved(row['run_id']):
            if pending['operation'] in owned and pending['status'] in ('dispatching','accepted','started'):
                backend.journal.record_outcome(row['run_id'],pending['request_id'],'uncertain',
                    dict(reason_code='owner_interrupted',previous_status=pending['status'],previous_receipt=pending['receipt']))
        for pending in backend.journal.unresolved(row['run_id']):
            if pending['status']=='reserved' and pending['operation'] in ('macro_policy','native_strategic_v5'):
                backend.journal.record_outcome(row['run_id'],pending['request_id'],'cancelled',
                    dict(reason_code='owner_ended_before_dispatch',native_delivery_attempted=False))
        start=backend.journal.get_command(row['run_id'],row['request_id'])
        if start['status']=='uncertain':
            backend.journal.resolve_uncertain(row['run_id'],row['request_id'],'completed',
                dict(host_receipt,reason_code='host_process_lost_control_returned'),evidence_id='native5_orphan_return')
        stop=backend.journal.reserve_command(row['run_id'],'macro-stop','macro_policy_stop',dict(binding_hash=binding.binding_hash))
        receipt=dict(binding_hash=binding.binding_hash,host_pid=host_receipt['host_pid'],host_start_time=host_receipt['host_start_time'],
            native_release_verified=True,native_release_contract=KIND,orphan_return_sha256=sha(path),helper_exit_code=None)
        if stop['status']=='reserved':
            backend.journal.mark_dispatching(row['run_id'],'macro-stop')
            backend.journal.record_outcome(row['run_id'],'macro-stop','released',receipt)
        elif stop['status']=='uncertain':
            backend.journal.resolve_uncertain(row['run_id'],'macro-stop','released',receipt,evidence_id='native5_orphan_return')
        elif stop['status']!='released':return False
        return verified_return(backend,row,binding,host_receipt)
