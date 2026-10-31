"""Explicit durable STOP -> fresh read-only Native6 return -> ledger receipt.

Historical delivery remains uncertain. No helper exit code, strategic effect,
Native operation, heartbeat, command retry or concurrent broker RPC is invented.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import uuid

from .contracts import ContractError
from .native5_orphan_return_v1 import ended_certificate
from .native6_lifecycle import context
from .native6_runtime_contract import read,sha
from .native6_release import _verified_current_restoration,verified_journal
from .strategic_unified_unknown_return_v5 import covered_unknown_ownership

KIND='native6_orphan_return_v1'


def inputs(row,binding,receipt):
    session=read(Path(row['session_path']));frozen,manifest,inventory=context(row,session,binding)
    identity=read(Path(frozen['report'])/'helper-identity.json');b=identity['native_binding'];parent=identity['parent'];helper=identity['helper']
    parent_start=datetime.fromtimestamp((parent['process_creation_filetime']-116444736000000000)/10000000,timezone.utc).isoformat()
    if (identity.get('kind')!='portable_native6_helper_identity_v1' or identity['session_id']!=binding.session_id
            or parent['pid']!=receipt['host_pid'] or parent_start!=receipt['host_start_time']
            or identity['source_sha256']!=inventory['files'].get('app/integration/host_runtime/native6_readonly_return.py')
            or identity['helper_sha256']!=manifest['artifacts']['manager_host.exe']
            or identity['build_manifest_sha256']!=inventory['files'].get('native/strategic6/build-manifest.json')
            or b['pid']!=binding.game_process_id or (b['start_low']|b['start_high']<<32)!=session['process_creation_filetime']
            or bytes(b['session'])!=uuid.UUID(binding.session_id).bytes or bytes(b['package']).hex()!=binding.mod_sha256
            or bytes(b['sources']).hex()!=manifest['source_closure_sha256']
            or bytes(b['runtime_manifest']).hex()!=frozen['runtime_manifest_sha256'] or b['runtime_root']!=frozen['runtime_root']
            or Path(b['game_image'])!=Path(session['game']) or Path(b['deployment'])!=Path(session['mod_big'])):
        raise ContractError('native6_orphan_identity_changed')
    return session,frozen,manifest,inventory,identity


def verified_capture(value,raw,session,frozen,manifest,identity,binding,run_id):
    try:
        proof=value['current_restoration']
        return (value['kind']==KIND and value['run_id']==run_id and value['binding']==binding.public()
            and value['helper_identity']==identity and value['helper_exit_code'] is None
            and proof.get('host_returncode') is None
            and value['native_commands_issued']==0 and type(value['native_commands_issued']) is int
            and value['mapping_access']=='FILE_MAP_READ' and value['ownership_return_claimed'] is False
            and ended_certificate(value['parent_ended'],identity['parent'])
            and ended_certificate(value['helper_ended_before'],identity['helper'])
            and ended_certificate(value['helper_ended_after'],identity['helper'])
            and proof['native']['binding']==identity['native_binding'] and verified_journal(raw,proof['native'])
            and value['native_journal_sha256']==__import__('hashlib').sha256(raw).hexdigest()
            and _verified_current_restoration(proof,pid=binding.game_process_id,ticks=session['process_creation_filetime'],
                session_id=binding.session_id,package=binding.mod_sha256,flags=manifest['flags'],closure=manifest['source_closure_sha256']))
    except (KeyError,ValueError,TypeError,OverflowError):return False


def capture(row,binding,receipt):
    session,frozen,manifest,inventory,identity=inputs(row,binding,receipt)
    from .native6_transport import native_module
    from .native6_readonly_return import collect_existing_readonly
    _,sdk=native_module();value,raw=collect_existing_readonly(sdk,session,identity)
    value.update(kind=KIND,run_id=row['run_id'],binding=binding.public(),capture_source_sha256=sha(__file__),
                 native_journal_sha256=__import__('hashlib').sha256(raw).hexdigest())
    if (value['capture_source_sha256']!=inventory['files'].get('app/integration/host_runtime/native6_orphan_return.py')
            or not verified_capture(value,raw,session,frozen,manifest,identity,binding,row['run_id'])):
        raise ContractError('native6_orphan_return_not_verified')
    return value,raw


def verified_return(backend,row,binding,receipt):
    try:
        session,frozen,manifest,inventory,identity=inputs(row,binding,receipt);output=Path(row['output_path'])
        path=output/'native6-orphan-return.json';value=read(path);raw=(output/'native6-orphan-journal.bin').read_bytes()
        stop=backend.journal.get_command(row['run_id'],'macro-stop');r=stop['receipt'] or {}
        return (stop['status']=='released' and r.get('native_release_contract')==KIND and r.get('binding_hash')==binding.binding_hash
            and r.get('orphan_return_sha256')==sha(path) and r.get('native_release_verified') is True
            and all(r.get(key)==receipt.get(key) for key in ('host_pid','host_start_time'))
            and value['capture_source_sha256']==inventory['files'].get('app/integration/host_runtime/native6_orphan_return.py')
            and verified_capture(value,raw,session,frozen,manifest,identity,binding,row['run_id'])
            and covered_unknown_ownership(backend.journal.unresolved(row['run_id']),backend.journal.commands_for_run(row['run_id']),stop))
    except (OSError,ValueError,TypeError,KeyError,OverflowError,ContractError):return False


def recover_after_stop(backend,row,binding,receipt,atomic):
    from .strategic_stop_gate_v1 import StrategicStopGateV1
    gate=StrategicStopGateV1(row['run_id'],binding,Path(row['output_path']))
    if not gate.committed():return False
    if verified_return(backend,row,binding,receipt):return True
    with gate._mutex(stop_writer=True):
        if backend.spawner.identity(receipt['host_pid'])==receipt['host_start_time']:return False
        if verified_return(backend,row,binding,receipt):return True
        output=Path(row['output_path']);path=output/'native6-orphan-return.json'
        fresh,raw=capture(row,binding,receipt)
        if path.exists():
            old=read(path);old_raw=(output/'native6-orphan-journal.bin').read_bytes()
            session,frozen,manifest,inventory,identity=inputs(row,binding,receipt)
            if (not verified_capture(old,old_raw,session,frozen,manifest,identity,binding,row['run_id'])
                    or old['current_restoration']['native']!=fresh['current_restoration']['native'] or old_raw!=raw):return False
        else:
            raw_path=output/'native6-orphan-journal.bin'
            if raw_path.exists():
                if raw_path.read_bytes()!=raw:return False
            else:
                with raw_path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            atomic(path,fresh)
        owned={'host_start','macro_policy','native_strategic_v5','macro_policy_stop'}
        for pending in backend.journal.unresolved(row['run_id']):
            if pending['operation'] in owned and pending['status'] in ('dispatching','accepted','started'):
                backend.journal.record_outcome(row['run_id'],pending['request_id'],'uncertain',
                    dict(reason_code='owner_interrupted',previous_status=pending['status'],previous_receipt=pending['receipt']))
            elif pending['operation'] in ('macro_policy','native_strategic_v5') and pending['status']=='reserved':
                backend.journal.record_outcome(row['run_id'],pending['request_id'],'cancelled',dict(reason_code='owner_ended_before_dispatch',native_delivery_attempted=False))
        start=backend.journal.get_command(row['run_id'],row['request_id'])
        if start['status']=='uncertain':backend.journal.resolve_uncertain(row['run_id'],row['request_id'],'completed',
            dict(receipt,reason_code='host_process_lost_control_returned'),evidence_id=KIND)
        stop=backend.journal.reserve_command(row['run_id'],'macro-stop','macro_policy_stop',dict(binding_hash=binding.binding_hash))
        result=dict(binding_hash=binding.binding_hash,host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'],
            native_release_verified=True,native_release_contract=KIND,orphan_return_sha256=sha(path),helper_exit_code=None)
        if stop['status']=='reserved':
            backend.journal.mark_dispatching(row['run_id'],'macro-stop');backend.journal.record_outcome(row['run_id'],'macro-stop','released',result)
        elif stop['status']=='uncertain':backend.journal.resolve_uncertain(row['run_id'],'macro-stop','released',result,evidence_id=KIND)
        elif stop['status']!='released':return False
        return verified_return(backend,row,binding,receipt)
