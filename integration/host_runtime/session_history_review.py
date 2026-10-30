"""Explicit offline legacy-history classification; never releases native control.

Reads the original index/journal/status and existing independent release proof.
Only a new metadata sidecar is written. No credentials, process or game access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from .contracts import ContractError,SessionBinding,content_hash,identifier,canonical_json

KIND='legacy_native_history_admission_review'
PROTOCOL='independently_released_legacy_native_v1'


def fail():raise ContractError('run_history_unverifiable')
def proof_path(backend,run_id):return Path(backend.state_dir)/'session-history-reviews'/(run_id+'-v1.json')


def inspect_legacy(backend,row,binding,session):
    from .session_discovery_native import read_object,_local_path,require_creation
    identifier(row['run_id']);identifier(row['request_id'])
    if SessionBinding.from_dict(json.loads(row['binding_json']))!=binding:fail()
    original,session_sha=read_object(_local_path(Path(row['session_path'])))
    if original!=session:fail()
    if (session.get('session_id')!=binding.session_id or type(session.get('pid')) is not int
            or session['pid']!=binding.game_process_id or session.get('start_time')!=binding.game_process_start
            or session.get('mod_sha256')!=binding.mod_sha256):fail()
    ticks=session.get('process_creation_filetime')
    try:
        if datetime.fromisoformat(binding.game_process_start).tzinfo is None:fail()
    except (TypeError,ValueError):fail()
    if ticks is not None:require_creation(binding.game_process_start,ticks)
    # None stays None: an old ISO timestamp is never invented into raw FILETIME.
    start=backend.journal.get_command(row['run_id'],row['request_id'])
    commands=backend.journal.commands_for_run(row['run_id'])
    receipt=start.get('receipt') or {};caps=(start.get('payload')or{}).get('capabilities')
    if (type(caps) is not dict or 'native_macro' in caps and caps['native_macro'] is not False
            or caps.get('control_mode') not in (None,'macro_native') or type(caps.get('supported_units')) is not list
            or any(key in caps and type(caps[key]) is not bool for key in ('tactics_supported','runtime_tactical_supported'))
            or start.get('operation')!='host_start' or start.get('status')!='completed'
            or receipt.get('reason_code')!='host_process_ended'
            or type(receipt.get('host_pid')) is not int or receipt['host_pid']<=0
            or type(receipt.get('host_start_time')) is not str or backend.journal.unresolved(row['run_id'])):fail()
    status,status_sha=read_object(_local_path(Path(row['output_path'])/'host-status.json'))
    runtime=status.get('runtime_production') or {}
    if (status.get('state') not in ('stopped','fault','result_candidate')
            or receipt.get('final_host_state')!=status['state'] or runtime.get('run_id')!=row['run_id']
            or runtime.get('binding_hash')!=binding.binding_hash or status.get('session_id')!=binding.session_id
            or status.get('pid')!=binding.game_process_id or status.get('process_start')!=binding.game_process_start
            or any(status.get(key)!=receipt.get(key) for key in ('host_pid','host_start_time'))
            or backend._release_receipt(row['run_id'],binding,receipt) is not True):fail()
    release_pins={}
    reviews={'review_host_release':('unattached-release-review.json','unattached_host_release_review'),
        'review_idle_runtime_release':('idle-runtime-release-review.json','idle_runtime_host_release_review'),
        'review_runtime_host_release':('runtime-epochs-release-review.json','runtime_epoch_host_release_review')}
    for command in commands:
        if command.get('status')!='released' or command.get('operation') not in reviews:continue
        filename,kind=reviews[command['operation']]
        path=_local_path(Path(backend.state_dir)/'runs'/row['run_id']/filename)
        proof,proof_sha=read_object(path,8*1024*1024);evidence=command.get('receipt')or{}
        if (proof_sha!=evidence.get('review_sha256') or proof.get('kind')!=kind or proof.get('binding')!=binding.public()
                or proof.get('run_id')!=row['run_id'] or proof.get('native_release_verified') is not True
                or any(proof.get(key)!=receipt.get(key) for key in ('host_pid','host_start_time'))):fail()
        release_pins[str(path)]=proof_sha
    # Classify the original release protocol, never invent a macro epoch or
    # manufacture missing historical capability fields into a current grant.
    if any(row.get('status')=='released' and row.get('operation')=='review_runtime_host_release' for row in commands):
        family='legacy_tactical_runtime_v1'
    elif any(row.get('status')=='released' and row.get('operation')=='review_idle_runtime_release' for row in commands):
        family='legacy_idle_runtime_v1'
    elif any(row.get('status')=='released' and row.get('operation')=='review_host_release' for row in commands):
        family='legacy_unattached_native_v1'
    elif any(row.get('status')=='released' and row.get('operation')=='stop'
            and (row.get('receipt')or{}).get('reason_code')=='native_receipt_verified'
            and ((row.get('receipt')or{}).get('facts')or{}).get('source')=='native_persistent_production' for row in commands):
        family='legacy_persistent_production_v1'
    else:fail()
    return dict(schema_version=1,kind=KIND,run_id=row['run_id'],request_id=row['request_id'],binding=binding.public(),
        control_family=family,original_declared_control_mode=caps.get('control_mode'),
        history_protocol=PROTOCOL,original_native_epoch=None,process_creation_filetime=ticks,
        original_process_start=binding.game_process_start,session_path=str(Path(row['session_path'])),session_sha256=session_sha,
        host_status_sha256=status_sha,original_host_start_sha256=content_hash(start),original_command_inventory_sha256=content_hash(commands),
        original_release_artifacts=release_pins,
        existing_independent_release_recomputed=True,original_receipts_preserved=True,
        reviewer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        game_access=False,credentials_accessed=False,model_calls=0,native_writes=0)


def validate_review(backend,row,binding,session):
    from .session_discovery_native import read_object,_local_path
    value,digest=read_object(_local_path(proof_path(backend,row['run_id'])))
    if canonical_json(value)!=canonical_json(inspect_legacy(backend,row,binding,session)):fail()
    return value,digest


def review(backend,run_id):
    from .session_discovery_native import read_object,_local_path
    identifier(run_id);row=backend._launch(run_id)
    binding=SessionBinding.from_dict(json.loads(row['binding_json']))
    session,_=read_object(_local_path(Path(row['session_path'])))
    value=inspect_legacy(backend,row,binding,session);target=proof_path(backend,run_id)
    if target.exists():
        _,digest=validate_review(backend,row,binding,session)
        return dict(reviewed=True,idempotent=True,run_id=run_id,review_sha256=digest,history_protocol=PROTOCOL)
    target.parent.mkdir(parents=True,exist_ok=True);_local_path(target.parent,directory=True)
    if inspect_legacy(backend,row,binding,session)!=value:fail()
    import os
    with target.open('x',encoding='utf8') as stream:
        stream.write(canonical_json(value));stream.flush();os.fsync(stream.fileno())
    _,digest=validate_review(backend,row,binding,session)
    return dict(reviewed=True,idempotent=False,run_id=run_id,review_sha256=digest,history_protocol=PROTOCOL,
        game_access=False,credentials_accessed=False,model_calls=0,original_receipts_preserved=True)


def open_offline_backend(state_dir):
    """Both original SQLite files are opened mode=ro, never via a profile store."""
    from .session_discovery_native import _local_path
    from .desktop_backend import DesktopBackend
    from .journal import CommandJournal
    class ReadOnlyJournal(CommandJournal):
        @contextmanager
        def _transaction(self):
            with self._lock:
                self._db.execute('BEGIN')
                try:
                    yield
                    self._db.execute('COMMIT')
                except BaseException:
                    self._db.execute('ROLLBACK');raise
    state=_local_path(Path(state_dir),directory=True)
    paths=[_local_path(state/name) for name in ('desktop-launch-index.sqlite3','host-runtime.sqlite3')]
    connections=[]
    try:
        for path in paths:
            db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;connections.append(db)
        journal=ReadOnlyJournal.__new__(ReadOnlyJournal);journal._db=connections[1];journal._lock=threading.RLock();journal._closed=False
        backend=DesktopBackend.__new__(DesktopBackend);backend._db=connections[0];backend.state_dir=state
        backend.journal=journal;backend.discovery=None;backend._lock=threading.RLock()
        return backend
    except BaseException:
        for connection in connections:connection.close()
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,required=True);parser.add_argument('--run-id',required=True)
    args=parser.parse_args(argv);backend=None
    try:
        backend=open_offline_backend(args.state_dir);result=review(backend,args.run_id)
        print(json.dumps(result));return 0
    except Exception:
        print(json.dumps(dict(reviewed=False,reason_code='run_history_unverifiable')));return 2
    finally:
        if backend is not None:backend.close()


if __name__=='__main__':raise SystemExit(main())
