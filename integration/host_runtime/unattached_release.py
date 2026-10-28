"""Trusted read-only reconciliation of a Host that failed before any command.

No native writes, SDK calls, replay or restoration attempt. A new journal entry
preserves the failed Host receipt and records an independently checked release.
"""
from __future__ import annotations

import argparse
import ctypes as c
import hashlib
import json
import os
import struct
from pathlib import Path
import uuid

from .contracts import ContractError, SessionBinding, identifier
from .desktop_backend import DesktopBackend, NativeHostSpawner, _module, _object, _atomic
from .desktop_registry import load_registration
from .profile_store import ProfileStore

# Exact original bytes in the fixed supported RA3 1.12 image. Includes the
# passive observer entry and all five persistent production detours.
ENTRIES = {
    0x723f50: '81eca8000000538bd98b43dc8b5058558d6bdc',
    0x7ba770: '81ec3c010000f605486bce0001535657',
    0x70f440: '83ec08558b6c241085ed568bf1',
    0x849220: '81ecb4000000568bf18b46148b4e04',
    0x73e390: '83ec208b4424248b54242c5355',
    0x789bf0: '51568bf180be3801000000',
}


def review(backend, run_id):
    identifier(run_id)
    row = backend._launch(run_id)
    backend._status(row)  # Reconcile only the ended OS process, never native effects.
    binding = SessionBinding.from_dict(json.loads(row['binding_json']))
    launch = backend.journal.get_command(run_id, row['request_id'])
    receipt = launch.get('receipt') or {}
    if NativeHostSpawner.identity(receipt.get('host_pid', 0)) is not None:
        raise ContractError('host_still_alive')
    status_path = Path(row['output_path'])/'host-status.json'
    status, digest = _object(status_path, 1024*1024)
    runtime = status.get('runtime_production', {})
    if (launch['status'] != 'completed' or status.get('state') != 'fault'
        or status.get('host_pid') != receipt.get('host_pid') or status.get('host_start_time') != receipt.get('host_start_time')
        or status.get('session_id') != binding.session_id or status.get('pid') != binding.game_process_id
        or status.get('process_start') != binding.game_process_start or runtime.get('run_id') != run_id
        or runtime.get('binding_hash') != binding.binding_hash or runtime.get('gateway_attached') is not False
        or status.get('execution', {}).get('executor_connected') is not False):
        raise ContractError('unattached_host_identity_unverified')
    commands = backend.journal._db.execute('SELECT operation FROM commands WHERE run_id=?',(run_id,)).fetchall()
    if any(r['operation'] not in ('host_start','host_stop','review_host_release') for r in commands):
        raise ContractError('prior_native_command_requires_separate_recovery')
    session, _ = _object(row['session_path'])
    if (session.get('session_id') != binding.session_id or session.get('pid') != binding.game_process_id
        or session.get('start_time') != binding.game_process_start):
        raise ContractError('session_changed')
    win = _module('observe_production', Path(__file__).resolve().parents[2]/'production')
    memory = win.Memory(binding.game_process_id, session)
    evidence = [];observer_proof=dict(channel_absent=True)
    try:
        if hashlib.sha256(Path(memory.path).read_bytes()).hexdigest() != binding.game_sha256:
            raise ContractError('game_changed')
        for address, expected in ENTRIES.items():
            actual = memory.read(address, len(bytes.fromhex(expected))).hex()
            evidence.append(dict(address=hex(address),expected=expected,actual=actual))
            if actual != expected:raise ContractError('native_original_entry_unverified')
        win.k.OpenFileMappingW.argtypes=[win.w.DWORD,win.w.BOOL,win.w.LPCWSTR]
        win.k.OpenFileMappingW.restype=win.w.HANDLE
        for prefix in ('RA3ProductionPersistent_','RA3ProductionObserver_'):
            handle=win.k.OpenFileMappingW(4,False,'Local\\'+prefix+str(binding.game_process_id))
            if handle:
                try:
                    if prefix != 'RA3ProductionObserver_':raise ContractError('native_channel_still_present')
                    win.k.MapViewOfFile.argtypes=[win.w.HANDLE,win.w.DWORD,win.w.DWORD,win.w.DWORD,c.c_size_t]
                    win.k.MapViewOfFile.restype=c.c_void_p
                    win.k.UnmapViewOfFile.argtypes=[c.c_void_p]
                    view=win.k.MapViewOfFile(handle,4,0,0,68)
                    if not view:raise ContractError('observer_channel_unreadable')
                    try:
                        raw=c.string_at(view,68)
                        if c.string_at(view,68)!=raw:raise ContractError('observer_channel_unstable')
                        h=struct.unpack('<17I',raw)
                        if not (h[0]==0x50524f44 and h[1]==1 and h[2]==binding.game_process_id
                            and 1<=h[3]<=30 and h[4]>0 and h[4]==h[5] and h[9]==1
                            and h[10]==2 and h[11]==1 and h[12]==0 and h[15]==0 and h[16]==1):
                            raise ContractError('observer_cleanup_unverified')
                        observer_proof=dict(channel_absent=False,raw_header_hex=raw.hex(),state=2,active_callbacks=0,original_bytes_restored=True)
                    finally:win.k.UnmapViewOfFile(view)
                finally:win.k.CloseHandle(handle)
    finally:memory.close()
    # Recheck the source and OS identity after the native reads.
    if _object(status_path,1024*1024)[1] != digest or NativeHostSpawner.identity(receipt['host_pid']) is not None:
        raise ContractError('release_review_source_changed')
    source = dict(schema_version=1,kind='unattached_host_release_review',binding=binding.public(),run_id=run_id,
        host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'],host_status_sha256=digest,
        original_entries=evidence,persistent_channel_absent=True,passive_observer=observer_proof,native_commands_dispatched=0,
        native_release_verified=True,physical_home_claimed=False,natural_result_verified=False)
    target=backend.state_dir/'runs'/run_id/'unattached-release-review.json'
    _atomic(target,source)
    request=str(uuid.uuid5(uuid.UUID(run_id),'independent-unattached-release'))
    record=backend.journal.reserve_command(run_id,request,'review_host_release',dict(binding_hash=binding.binding_hash))
    if record['created']:
        backend.journal.mark_dispatching(run_id,request)
        backend.journal.record_outcome(run_id,request,'released',dict(
            reason_code='unattached_host_native_entries_independently_verified',binding_hash=binding.binding_hash,
            host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'],native_release_verified=True,
            review_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    return dict(run_id=run_id,native_release_verified=True,review_file=str(target),native_writes=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True)
    args=parser.parse_args(argv);home=Path(os.environ['LOCALAPPDATA'])/'Tacticore'
    library=load_registration(home);store=ProfileStore(Path(library['library_path']),home/'desktop-runtime')
    backend=DesktopBackend(store)
    try:
        print(json.dumps(review(backend,args.run_id)));return 0
    finally:backend.close();store.close()


if __name__=='__main__':raise SystemExit(main())
