"""Independent, file-only review of the fixed pre-constructor macro fault.

This version accepts only the independently reviewed frozen Host control-flow
site. It never turns a missing report, preflight marker or absent mutex into a
release. Raw capture and original journal receipts remain untouched.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import uuid

from .contracts import ContractError,SessionBinding,canonical_json,content_hash,identifier

ROOT=Path(__file__).resolve().parents[2]
CAPTURE_SHA='4513cfa7ce3eb47dcad7f61fc95424d06dc81e21bdc1e3647e9731298f06c6a2'
PRESENCE_SHA='319260a505ba15e8a0a9c6d72b156430883d65a3ab4c511e9ecd21e3b8dd5aa7'
HOST_SHA='bf4fbd2f8eded6767f7131e0789374d5deb7f57d9d0a2c82fcb686553b782540'
KIND='macro_before_attach_independent_release_review'
OPERATION='review_macro_before_attach_release'


def fail(code='macro_before_attach_unverified'):raise ContractError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def capture_module():
    path=ROOT/'acceptance/capture_macro_before_attach_v5.py'
    if sha(path)!=CAPTURE_SHA or sha(ROOT/'integration/host_runtime/macro_native_presence.py')!=PRESENCE_SHA:fail('macro_before_attach_reviewer_source_changed')
    spec=importlib.util.spec_from_file_location('_trusted_macro_beforeattach_v5',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def original_history(backend,run_id):
    """Read only. Review's own metadata entry never changes original history."""
    row=dict(backend._launch(run_id));commands=backend.journal.commands_for_run(run_id)
    reviews=[command for command in commands if command['operation']==OPERATION]
    if len(reviews)>1:fail()
    review_ids={row['command_id'] for row in reviews}
    original=[command for command in commands if command['operation']!=OPERATION]
    events=[backend.journal._read_event(event) for event in backend.journal._db.execute('SELECT * FROM events WHERE run_id=? ORDER BY seq',(run_id,))
        if event['command_id'] not in review_ids]
    if len(events)>10000:fail()
    run_row=backend.journal._db.execute('SELECT binding FROM runs WHERE run_id=?',(run_id,)).fetchone()
    if run_row is None:fail()
    return dict(launch=row,journal_run_binding=json.loads(run_row['binding']),commands=original,events=events,
        unresolved=[command for command in backend.journal.unresolved(run_id) if command['command_id'] not in review_ids])


def check_history(history,binding,status,run,run_id):
    launch=history['launch'];commands=history['commands']
    if (launch['run_id']!=run_id or SessionBinding.from_dict(json.loads(launch['binding_json']))!=binding
            or history.get('journal_run_binding')!=binding.public()
            or Path(launch['output_path']).resolve()!=(run/'battle-host').resolve() or history['unresolved']
            or type(commands) is not list or not commands
            or any(row.get('operation') not in ('host_start','host_stop') for row in commands)
            or any(row.get('status') not in ('completed','cancelled','rejected') for row in commands)):fail('macro_before_attach_native_history_unknown')
    starts=[row for row in commands if row['operation']=='host_start']
    if len(starts)!=1:fail()
    start=starts[0];receipt=start.get('receipt')or{};caps=(start.get('payload')or{}).get('capabilities')or{}
    if (start.get('run_id')!=run_id or start.get('request_id')!=launch['request_id'] or start.get('status')!='completed'
            or caps.get('native_macro') is not True or caps.get('control_mode')!='macro_native'
            or receipt.get('reason_code')!='host_process_ended' or receipt.get('final_host_state')!='fault'
            or any(receipt.get(key)!=status.get(key) for key in ('host_pid','host_start_time'))):fail('macro_before_attach_host_history_unverified')
    for row in commands:
        if row.get('run_id')!=run_id:fail()
        if row['operation']=='host_stop' and row['status']=='completed':
            evidence=row.get('receipt')or{}
            if evidence.get('native_release_verified') is True:fail() # unrelated claim cannot supply this proof
    return start


def check_events(host,binding,status):
    path=host/'host-events.jsonl';raw=path.read_bytes()
    if not raw.endswith(b'\n'):fail('macro_before_attach_events_incomplete')
    events=[json.loads(line) for line in raw.splitlines()]
    required=['macro_cost_adapter_boot','macro_cost_adapter_quarantined','commander_model_backend_constructed',
        'host_fault','macro_host_stop_started','host_stopped']
    if [event.get('kind') for event in events]!=required:fail('macro_before_attach_control_flow_unverified')
    prior=-1
    for event in events:
        wall=event.get('wall_seconds')
        if (event.get('session_id')!=binding.session_id or event.get('player_id')!=binding.player_id
                or event.get('commander_id')!=binding.commander_id or type(wall) not in (int,float) or wall<prior):fail()
        prior=wall
    fault=events[3]
    expected=[dict(file='integration\\macro_host.py',line=425,function='run'),
        dict(file='integration\\macro_host.py',line=287,function='observe_current'),
        dict(file='strategy\\battle_agent.py',line=299,function='observe')]
    if (fault.get('source_frames')!=expected or fault.get('error_type')!='ContractError'
            or any(event.get('reason_code')!='unseen_contact_history' for event in events[3:])
            or status.get('reason_code')!='unseen_contact_history' or status.get('metrics',{}).get('requests')!=0
            or status.get('profile_consumption',{}).get('calls_started')!=0
            or status.get('profile_consumption',{}).get('responses_returned')!=0
            or status.get('task_counters',{}).get('dispatches')!=0):fail('macro_before_attach_control_flow_unverified')
    return events


def check_journal_events(history,binding,events):
    rows=history.get('events')
    expected=['run_registered','command_reserved','dispatch_intent_committed','command_outcome']+[event['kind'] for event in events]+['command_outcome']
    if type(rows) is not list or [row.get('event_type') for row in rows]!=expected:fail('macro_before_attach_journal_events_unverified')
    start=history['commands'][0];command_id=start['command_id']
    if len(history['commands'])!=1 or start['operation']!='host_start':fail()
    if rows[0].get('payload')!=binding.public():fail()
    if (rows[1].get('payload')!={key:start[key] for key in ('fingerprint','operation','request_id')}
            or rows[2].get('payload')!={} or rows[3].get('payload',{}).get('status')!='started'
            or rows[-1].get('payload')!=dict(status='completed',receipt=start['receipt'])):fail()
    for position,row in enumerate(rows):
        if (row.get('run_id')!=start['run_id'] or type(row.get('seq')) is not int
                or position and row['seq']<=rows[position-1]['seq']):fail()
        should_command=position in (1,2,3,len(rows)-1)
        if row.get('command_id')!=(command_id if should_command else None):fail()
    for row,event in zip(rows[4:-1],events):
        if row.get('payload')!={key:value for key,value in event.items() if key!='kind'}:fail('macro_before_attach_host_journal_disagree')
    first=rows[3]['payload'].get('receipt')or{}
    last=start['receipt']
    if first.get('reason_code')!='host_process_spawned' or any(first.get(key)!=last.get(key) for key in ('host_pid','host_start_time')):fail()


def check_primitives(value,manifest,binding,session,status):
    if (value.get('kind')!='macro_before_attach_passive_capture' or value.get('schema_version')!=5
            or value.get('completed') is not True or value.get('binding')!=binding.public()
            or value.get('native_release_verified') is not False
            or any(type(value.get(key)) is not int or value[key]!=0 for key in ('native_writes','sdk_game_calls','lease_acquire_or_release_calls','model_calls'))
            or value.get('credentials_accessed') is not False):fail('macro_before_attach_capture_incomplete')
    identity=value.get('identity_before')
    if (type(identity) is not dict or identity!=value.get('identity_after')
            or identity.get('pid')!=binding.game_process_id or identity.get('process_creation_filetime')!=session.get('process_creation_filetime')
            or identity.get('image_sha256')!=binding.game_sha256 or Path(identity['image_path']).resolve()!=Path(session['game']).resolve()
            or value.get('expected_process_creation_filetime')!=session['process_creation_filetime']):fail('macro_before_attach_identity_unverified')
    for key in ('host_state_before','host_state_after'):
        row=value.get(key)or{}
        if row.get('pid')!=status['host_pid'] or row.get('original_incarnation_ended') is not True:fail('macro_before_attach_host_alive_or_unknown')
    for key in ('objects_before','objects_after'):
        row=value.get(key)or{}
        if (row.get('source')!='win32_read_only_macro_channel_and_semaphore_v1'
                or row.get('mapping_name')!=manifest['mapping_prefix']+str(binding.game_process_id)
                or row.get('semaphore_name')!='Local\\RA3MacroPolicyLease_'+str(binding.game_process_id)
                or row.get('mapping_status')!='absent' or row.get('mapping_open_error')!=2
                or row.get('native_writes')!=0 or row.get('acquire_or_wait_calls')!=0):fail('macro_before_attach_channel_unverified')
        if row.get('semaphore_status')=='absent':
            if row.get('semaphore_open_error')!=2:fail()
        elif row.get('semaphore_status')=='free':
            if (row.get('semaphore_current_count')!=1 or row.get('semaphore_maximum_count')!=1
                    or row.get('semaphore_double_read')!=[[1,1],[1,1]]):fail()
        else:fail('macro_before_attach_lease_held_or_unknown')
    modules=value.get('modules_before')
    if (type(modules) is not list or not modules or modules!=value.get('modules_after') or len(modules)>1024
            or len({row['base'] for row in modules})!=len(modules)):fail('macro_before_attach_module_inventory_unverified')
    for key in ('modules_before_api','modules_after_api'):
        api=value.get(key)or{}
        if (api.get('snapshot_flags')!=0x18 or api.get('python_pointer_bits')!=64 or api.get('wchar_bytes')!=2
                or api.get('dword_bytes')!=4 or api.get('module_entry_size')!=1080 or api.get('dwSize')!=1080
                or api.get('process_machine')!=0x14c or api.get('native_machine')!=0x8664
                or api.get('terminal_error')!=18 or api.get('complete_rows')!=len(modules)):fail('macro_before_attach_module_inventory_unverified')
        raw=api.get('raw_rows')
        if type(raw) is not list or not raw or api.get('raw_row_count')!=len(raw):fail()
        unique,duplicates=capture_module().unique_modules(raw)
        if unique!=modules or api.get('exact_duplicate_rows')!=duplicates or api.get('exact_duplicate_count')!=len(duplicates):fail()
    for row in modules:
        bits=row.get('image_bits');base=int(row['base'],0);size=row['size']
        if (row.get('pid')!=binding.game_process_id or (row.get('machine'),row.get('optional_magic'),bits)
                not in (('0x14c','0x10b',32),('0x8664','0x20b',64))
                or row.get('reviewed_x86_hook_eligible') is not (bits==32)
                or not 0x10000<=base<base+size<= (0x100000000 if bits==32 else 0x0000800000000000)
                or type(row.get('export_count')) is not int or not 0<=row['export_count']<=65536
                or row.get('path')!=row.get('mapped_backing_path')
                or not isinstance(row.get('mapped_device_path'),str) or not isinstance(row.get('mapped_device_prefix'),str)
                or not row['mapped_device_path'].casefold().startswith((row['mapped_device_prefix']+'\\').casefold())
                or not Path(row.get('toolhelp_path','')).is_absolute()
                or sha(row['path'])!=row.get('file_sha256') or row.get('file_sha256')=='aaca067e003a603c3df7f30615de3dda2f0b2ab6beb241b2905fa5a610610c62'
                or bits==32 and (row.get('control_exports')!=[] or 'macropolicy' in row['name'].lower())):fail('macro_before_attach_control_module_or_unverified')
    main=[row for row in modules if int(row['base'],0)==0x400000]
    if (len(main)!=1 or main[0]['image_bits']!=32 or main[0]['file_sha256']!=identity['image_sha256']
            or Path(main[0]['mapped_backing_path'])!=Path(identity['image_path'])):fail()
    flags=value.get('flags_before')
    if flags!=value.get('flags_after') or type(flags) is not dict or type(flags.get('flags')) is not list:fail()
    if ([row.get('name') for row in flags['flags']]!=manifest['flags']
            or any(type(row.get('present')) is not bool or row['present'] and row.get('value') is not False for row in flags['flags'])):fail('macro_before_attach_flags_not_clear')


def inspect(run,capture_dir,run_id,history):
    identifier(run_id);run=Path(run).resolve();capture_dir=Path(capture_dir).resolve();module=capture_module()
    session,binding,status,manifest,manifest_path,evidence=module.inputs(run,run_id)
    index=load(run/'battle-host/sources.json');host_copy=run/'battle-host/source'/index['sources'][0]['copy']
    if sha(host_copy)!=HOST_SHA:fail('macro_before_attach_frozen_host_not_reviewed')
    if (sha(capture_dir/'source/capture_macro_before_attach_v5.py')!=CAPTURE_SHA
            or sha(capture_dir/'source/macro_native_presence.py')!=PRESENCE_SHA):fail('macro_before_attach_capture_source_unverified')
    value=load(capture_dir/'capture.json')
    if (value.get('run_id')!=run_id or value.get('input_sha256')!=evidence
            or value.get('native_manifest_sha256')!=sha(manifest_path)
            or value.get('reviewed_native_source_sha256')!=module.NATIVE_SHA or value.get('reviewed_dll_sha256')!=module.DLL_SHA
            or any(value.get(key)!=status.get(key) for key in ('host_pid','host_start_time'))):fail('macro_before_attach_source_binding_unverified')
    check_history(history,binding,status,run,run_id);events=check_events(run/'battle-host',binding,status)
    check_journal_events(history,binding,events)
    check_primitives(value,manifest,binding,session,status)
    return dict(schema_version=1,kind=KIND,run_id=run_id,binding=binding.public(),host_pid=status['host_pid'],host_start_time=status['host_start_time'],
        process_creation_filetime=session['process_creation_filetime'],native_release_verified=True,no_control_acquired=True,
        native_delivery_attempted=False,hook_scope='reviewed_MacroPolicyControl_only_not_arbitrary_system_hooks',
        preflight_attach_marker_used_as_proof=False,missing_report_used_as_proof=False,mutex_absence_used_as_proof=False,
        before_constructor_source_sha256=HOST_SHA,source_control_flow='run.observe_current:425_before_MacroPolicyProbe_constructor:428',
        capture_path=str(capture_dir/'capture.json'),capture_sha256=sha(capture_dir/'capture.json'),original_evidence=evidence,
        original_history_sha256=content_hash(history),original_events_sha256=content_hash(events),
        reviewer_sha256=sha(__file__),capture_source_sha256=CAPTURE_SHA,presence_source_sha256=PRESENCE_SHA,
        game_access=False,credentials_accessed=False,native_writes=0,model_calls=0,physical_home_claimed=False,
        mission_effect_granted=False,payment_effect_granted=False,original_receipts_preserved=True)


def proof_path(backend,run_id):return Path(backend.state_dir)/'runs'/run_id/'macro-before-attach-release-review.json'


def validate_review(backend,run_id):
    path=proof_path(backend,run_id);value=load(path);history=original_history(backend,run_id)
    run=Path(history['launch']['output_path']).resolve().parent
    expected=inspect(run,Path(value['capture_path']).parent,run_id,history)
    if canonical_json(value)!=canonical_json(expected):fail('macro_before_attach_review_changed')
    return value,sha(path)


def projection_verified(backend,run_id,binding,host_receipt):
    if not callable(getattr(backend.journal,'commands_for_run',None)):return False
    reviews=backend.journal.commands_for_run(run_id,operation=OPERATION)
    if len(reviews)!=1:return False
    command=reviews[0];receipt=command.get('receipt')or{}
    if (command.get('status')!='released' or receipt.get('reason_code')!='macro_before_attach_independently_verified'
            or receipt.get('binding_hash')!=binding.binding_hash or receipt.get('native_release_verified') is not True
            or receipt.get('no_control_acquired') is not True
            or any(receipt.get(key)!=host_receipt.get(key) for key in ('host_pid','host_start_time'))):return False
    value,digest=validate_review(backend,run_id)
    return (digest==receipt.get('review_sha256') and value.get('binding')==binding.public()
        and all(value.get(key)==host_receipt.get(key) for key in ('host_pid','host_start_time')))


def install_review(backend,run_id,review_file):
    """Explicit trusted metadata write; original Host outcome is never edited."""
    from .session_discovery_native import _local_path
    identifier(run_id);source=_local_path(Path(review_file));value=load(source)
    history=original_history(backend,run_id);run=Path(history['launch']['output_path']).resolve().parent
    expected=inspect(run,Path(value['capture_path']).parent,run_id,history)
    if canonical_json(value)!=canonical_json(expected):fail('macro_before_attach_review_changed')
    existing=backend.journal.commands_for_run(run_id,operation=OPERATION)
    if existing:
        binding=SessionBinding.from_dict(value['binding'])
        if not projection_verified(backend,run_id,binding,history['commands'][0]['receipt']):fail('macro_before_attach_review_install_unknown')
        return dict(installed=True,idempotent=True,native_release_verified=True,original_receipts_preserved=True)
    target=proof_path(backend,run_id);target.parent.mkdir(parents=True,exist_ok=True);_local_path(target.parent,directory=True)
    if target.exists():
        if target.read_bytes()!=source.read_bytes():fail('macro_before_attach_review_path_conflict')
    else:
        with target.open('xb') as stream:stream.write(source.read_bytes());stream.flush();os.fsync(stream.fileno())
    if original_history(backend,run_id)!=history or validate_review(backend,run_id)[0]!=value:fail('macro_before_attach_history_changed')
    request=str(uuid.uuid5(uuid.UUID(run_id),'independent-macro-beforeattach-release-v1'))
    record=backend.journal.reserve_command(run_id,request,OPERATION,dict(binding_hash=SessionBinding.from_dict(value['binding']).binding_hash))
    if not record['created']:fail('macro_before_attach_review_install_unknown')
    backend.journal.mark_dispatching(run_id,request)
    # Only the new review command is excluded; any newly appearing native or
    # unknown original command invalidates the proof before the release entry.
    if original_history(backend,run_id)!=history:fail('macro_before_attach_history_changed')
    backend.journal.record_outcome(run_id,request,'released',dict(reason_code='macro_before_attach_independently_verified',
        binding_hash=SessionBinding.from_dict(value['binding']).binding_hash,host_pid=value['host_pid'],host_start_time=value['host_start_time'],
        native_release_verified=True,no_control_acquired=True,review_sha256=sha(target)))
    return dict(installed=True,idempotent=False,native_release_verified=True,original_receipts_preserved=True,review_file=str(target))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,required=True);parser.add_argument('--run-directory',type=Path,required=True)
    parser.add_argument('--capture-directory',type=Path,required=True);parser.add_argument('--run-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv);backend=None
    try:
        if args.output.exists() or not args.output.resolve().is_relative_to(ROOT/'reports'):fail('fresh_local_review_required')
        from .session_history_review import open_offline_backend
        backend=open_offline_backend(args.state_dir);history=original_history(backend,args.run_id)
        result=inspect(args.run_directory,args.capture_directory,args.run_id,history)
        if original_history(backend,args.run_id)!=history:fail('macro_before_attach_history_changed')
        args.output.mkdir(parents=True)
        (args.output/'history.json').write_text(canonical_json(history),encoding='utf8')
        (args.output/'review.json').write_text(canonical_json(result),encoding='utf8')
        print(json.dumps(dict(reviewed=True,native_release_verified=True,registered=False,review_file=str(args.output/'review.json'))));return 0
    finally:
        if backend is not None:backend.close()


if __name__=='__main__':raise SystemExit(main())
