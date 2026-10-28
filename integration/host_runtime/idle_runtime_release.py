"""Independent release review for a stopped, attached, never-borrowed Host.

No game writes, SDK calls, retries or capability grants. This cannot reconcile
an actual Reserve or unknown tactical command; those need their own evidence.
"""
from __future__ import annotations
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import uuid

from .contracts import ContractError,SessionBinding,identifier
from .desktop_backend import DesktopBackend,NativeHostSpawner,_object,_module
from .desktop_registry import load_registration
from .profile_store import ProfileStore
from .runtime_channel_capture import capture
from .runtime_evidence import _layout,_decode,_entry_signatures,_producer_types
from .runtime_rotation import assess_retirement
from .unattached_release import ENTRIES

def assess_idle(report,captured,binding):
    facts=assess_retirement(report,captured,binding)
    if (facts['no_control_acquired'] is not True or facts['previous_native_sequence']!=0
            or facts['control_released'] or report['commands'] or report['events']):
        raise ContractError('idle_review_actual_control_requires_separate_recovery')
    return facts

def assess_producer(before,after,ledger,binding,commands,bootstrap):
    l=_layout();Receipt,Header=_producer_types(l)
    h=_decode(Header,before.hex())
    if (before!=after or h.magic!=0x50434d44 or h.version!=1 or h.pid!=binding.game_process_id
            or l.uuid_text(h.session)!=binding.session_id or l.uuid_text(h.commander)!=binding.commander_id
            or h.phase!=2 or h.restore_mask!=31 or h.active or h.error or not h.stop_requested
            or not 1<=h.count<=1024 or h.count!=len(commands) or len(ledger)!=h.count*c.sizeof(Receipt)
            or h.owner!=bootstrap.native.owner or h.ai!=bootstrap.native.ai or h.thread!=bootstrap.binding.thread
            or h.personality!=bootstrap.native.personality or h.personality_id!=bootstrap.native.personality_id
            or h.player_template!=bootstrap.native.player_template
            or abs(((h.start_high<<32)|h.start_low)-bootstrap.binding.process_start)>9):
        raise ContractError('idle_review_producer_header_unverified')
    by_id={row['command_id']:row for row in commands};paid=0;sequences=[]
    if len(by_id)!=len(commands):raise ContractError('idle_review_duplicate_production_command')
    for i in range(h.count):
        r=Receipt.from_buffer_copy(ledger,i*c.sizeof(Receipt));key=l.uuid_text(r.command.id)
        row=by_id.pop(key,None)
        if (row is None or r.updates or r.command.hash!=0x19ab11af
                or l.uuid_text(r.command.session)!=binding.session_id or l.uuid_text(r.command.commander)!=binding.commander_id
                or l.uuid_text(r.command.task)!=row['payload'].get('task_id') or row['payload'].get('unit')!='conscript'):
            raise ContractError('idle_review_production_binding_unverified')
        if row['status']=='completed':
            if (r.state!=2 or r.error or r.cost!=85 or r.paid!=85 or not r.created or not r.completed
                    or r.payment_error or not r.live_samples or not r.queue_id or not r.preserved):
                raise ContractError('idle_review_completed_production_unverified')
        elif row['status']=='rejected':
            if r.state!=3 or not r.error or r.attempted or r.paid or r.created or r.completed:
                raise ContractError('idle_review_rejected_production_unverified')
        else:raise ContractError('idle_review_production_not_terminal')
        paid+=r.paid;sequences.append(r.command.seq)
    if by_id or sequences!=sorted(set(sequences)) or h.last_seq!=max(sequences) or paid!=h.spent:
        raise ContractError('idle_review_production_sequence_or_spend_unverified')
    return dict(header_before_hex=before.hex(),header_after_hex=after.hex(),ledger_hex=ledger.hex(),
        count=h.count,spent=h.spent,phase=h.phase,restore_mask=h.restore_mask,active_callbacks=h.active,native_error=h.error)

def read_producer(session,binding,commands,boot,memory):
    l=_layout();Receipt,Header=_producer_types(l)
    k=c.WinDLL('kernel32',use_last_error=True)
    k.OpenFileMappingW.argtypes=[c.c_uint32,c.c_int,c.c_wchar_p];k.OpenFileMappingW.restype=c.c_void_p
    k.MapViewOfFile.argtypes=[c.c_void_p,c.c_uint32,c.c_uint32,c.c_uint32,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
    k.UnmapViewOfFile.argtypes=[c.c_void_p];k.CloseHandle.argtypes=[c.c_void_p]
    handle=view=None
    try:
        handle=k.OpenFileMappingW(4,False,f'Local\\RA3ProductionPersistent_{binding.game_process_id}')
        if not handle:raise ContractError('idle_review_producer_mapping_missing')
        view=k.MapViewOfFile(handle,4,0,0,c.sizeof(Header)+1024*c.sizeof(Receipt))
        if not view:raise ContractError('idle_review_producer_view_missing')
        before=c.string_at(view,c.sizeof(Header));h=Header.from_buffer_copy(before)
        if not 1<=h.count<=1024:raise ContractError('idle_review_producer_count_invalid')
        ledger=c.string_at(view+c.sizeof(Header),h.count*c.sizeof(Receipt));after=c.string_at(view,c.sizeof(Header))
        if c.string_at(view+c.sizeof(Header),len(ledger))!=ledger:raise ContractError('idle_review_producer_ledger_changed')
        proof=assess_producer(before,after,ledger,binding,commands,boot)
        originals={**{hex(a):b for a,b in ENTRIES.items()},**_entry_signatures()}
        if len(originals)!=19:raise ContractError('idle_review_entry_inventory_changed')
        entries=[]
        for address,expected in originals.items():
            actual=memory.read(int(address,16),len(bytes.fromhex(expected))).hex()
            if actual!=expected:raise ContractError('idle_review_original_entry_unverified')
            entries.append(dict(address=address,expected=expected,actual=actual))
        proof['original_entries']=entries
        return proof
    finally:
        if view:k.UnmapViewOfFile(view)
        if handle:k.CloseHandle(handle)

def review(backend,run_id):
    identifier(run_id);row=backend._launch(run_id);backend._status(row)
    binding=SessionBinding.from_dict(json.loads(row['binding_json']))
    launch=backend.journal.get_command(run_id,row['request_id']);receipt=launch.get('receipt')or{}
    if NativeHostSpawner.identity(receipt.get('host_pid',0)) is not None:raise ContractError('host_still_alive')
    status_path=Path(row['output_path'])/'host-status.json';status,status_hash=_object(status_path,1024*1024)
    runtime=status.get('runtime_production')or{}
    if (launch['status']!='completed' or status.get('state') not in ('fault','stopped','result_candidate')
            or status.get('host_pid')!=receipt.get('host_pid') or status.get('host_start_time')!=receipt.get('host_start_time')
            or status.get('session_id')!=binding.session_id or status.get('pid')!=binding.game_process_id
            or status.get('process_start')!=binding.game_process_start or runtime.get('run_id')!=run_id
            or runtime.get('binding_hash')!=binding.binding_hash):raise ContractError('idle_review_host_identity_unverified')
    commands=backend.journal.commands_for_run(run_id)
    if (any(r['operation'] not in ('host_start','host_stop','produce','stop','review_idle_runtime_release')for r in commands)
            or backend.journal.unresolved(run_id)):
        raise ContractError('idle_review_actual_control_requires_separate_recovery')
    stop=[r for r in commands if r['operation']=='stop' and r['status']=='released']
    if not any((r.get('receipt')or{}).get('facts',{}).get('production_release_verified') is True for r in stop):
        raise ContractError('idle_review_producer_stop_receipt_required')
    target=backend.state_dir/'runs'/run_id/'idle-runtime-release-review.json'
    request=str(uuid.uuid5(uuid.UUID(run_id),'independent-idle-runtime-release'))
    existing=[r for r in commands if r['request_id']==request]
    if existing:
        saved=(existing[0].get('receipt')or{})
        if (existing[0]['status']!='released' or hashlib.sha256(target.read_bytes()).hexdigest()!=saved.get('review_sha256')):
            raise ContractError('idle_review_saved_evidence_changed')
        return dict(run_id=run_id,native_release_verified=True,review_file=str(target),idempotent=True,native_writes=0)
    session,session_hash=_object(row['session_path']);run=Path(session['run_directory']).resolve()
    if (session.get('session_id')!=binding.session_id or session.get('pid')!=binding.game_process_id
            or session.get('start_time')!=binding.game_process_start):raise ContractError('session_changed')
    report_path=run/'host-tactical-runtime.json';report,report_hash=_object(report_path,4*1024*1024)
    captured=capture(Path(row['session_path']),report_path)
    facts=assess_idle(report,captured,binding);l=_layout();boot=_decode(l.Bootstrap,report['bootstrap_hex'])
    win=_module('observe_production',Path(__file__).resolve().parents[2]/'production')
    memory=win.Memory(binding.game_process_id,session)
    try:producer=read_producer(session,binding,[r for r in commands if r['operation']=='produce'],boot,memory)
    finally:memory.close()
    if (_object(status_path,1024*1024)[1]!=status_hash or _object(row['session_path'])[1]!=session_hash
            or _object(report_path,4*1024*1024)[1]!=report_hash or NativeHostSpawner.identity(receipt['host_pid']) is not None):
        raise ContractError('idle_review_sources_changed')
    proof=dict(schema_version=1,kind='idle_runtime_host_release_review',binding=binding.public(),run_id=run_id,
        host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'],host_status_sha256=status_hash,
        report_sha256=report_hash,session_sha256=session_hash,capture=captured,retirement=facts,producer=producer,
        no_control_acquired=True,native_release_verified=True,physical_home_claimed=False,
        mission_effect_granted=False,natural_result_verified=False,native_writes=0,sdk_game_calls=0)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8')as stream:
        json.dump(proof,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    backend.journal.reserve_command(run_id,request,'review_idle_runtime_release',dict(binding_hash=binding.binding_hash))
    backend.journal.mark_dispatching(run_id,request)
    backend.journal.record_outcome(run_id,request,'released',dict(reason_code='idle_runtime_host_native_entries_independently_verified',
        binding_hash=binding.binding_hash,host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'],
        native_release_verified=True,no_control_acquired=True,review_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    return dict(run_id=run_id,native_release_verified=True,review_file=str(target),native_writes=0)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);args=parser.parse_args(argv)
    home=Path(os.environ['LOCALAPPDATA'])/'Tacticore';library=load_registration(home)
    store=ProfileStore(Path(library['library_path']),home/'desktop-runtime');backend=DesktopBackend(store)
    try:print(json.dumps(review(backend,args.run_id)));return 0
    finally:backend.close();store.close()

if __name__=='__main__':raise SystemExit(main())
