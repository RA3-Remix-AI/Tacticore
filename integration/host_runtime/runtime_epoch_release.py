"""Host-only, read-only native review across an exact closed epoch chain.

Preserves failed attach receipts. A new bound review can close only a proven
never-borrowed attach's ownership projection, never an unknown tactical lease.
No UI/model RPC, capability grant, game write, SDK call or command retry.
"""
from __future__ import annotations
import argparse
import ctypes as c
from dataclasses import replace
import hashlib,json,os,struct,uuid
from pathlib import Path

from .contracts import ContractError,SessionBinding,content_hash,identifier
from .desktop_backend import DesktopBackend,NativeHostSpawner,_module,_object
from .desktop_registry import load_registration
from .profile_store import ProfileStore
from .runtime_channel_capture import capture
from .runtime_rotation import assess_retirement,successor_actor_selection,_write_once
from .runtime_evidence import _layout,_decode,_values
from .idle_runtime_release import read_producer

ROOT_REVIEW='review_runtime_host_release'
ATTACH_REVIEW='review_runtime_channel_release'
REVIEWS={ROOT_REVIEW,ATTACH_REVIEW}
NATIVE={'reserve':1,'commit':2,'return':3,'stop':4,'query_status':5,'reconcile_release':6,'reconcile_return_home':7}
PHASES=('idle','borrowing','stance','braking','ready','moving','target_braking','holding','returning','home_braking','restoring','releasing','released','uncertain','return_braking')
ALLOWED={'host_start','host_stop','produce','stop','runtime_channel_attach','runtime_channel_retire',
    'runtime_channel_successor_authorize',*NATIVE,*REVIEWS}

def require(condition,name):
    if condition is not True:raise ContractError('epoch_release_'+name)

def family(journal,binding):
    result={}
    for row in journal._db.execute('SELECT run_id,binding FROM runs'):
        value=json.loads(row['binding'])
        if value.get('session_id')!=binding.session_id or value.get('player_id')!=binding.player_id:continue
        candidate=SessionBinding.from_dict(value)
        require(replace(candidate,host_id=binding.host_id)==binding,'session_binding_changed')
        result[row['run_id']]=candidate
    require(0<len(result)<=64,'epoch_count_invalid')
    return result

def command_snapshot(journal,bindings):
    return sorted([r for run in bindings for r in journal.commands_for_run(run)if r['operation']not in REVIEWS],key=lambda r:r['command_id'])

def owned_file(path,run):
    path=Path(path).resolve(strict=True)
    require(path.parent==run,'owned_epoch_file_required')
    return path

def inspect_chain(journal,root_id,binding,run,supervisor,session_path,*,capture_final):
    """Recompute every immutable epoch; final mapping comes from a fresh reader."""
    bindings=family(journal,binding);require(bindings.get(root_id)==binding,'root_binding_missing')
    snapshot=command_snapshot(journal,bindings);byrun={rid:[r for r in snapshot if r['run_id']==rid]for rid in bindings}
    require(all(r['operation']in ALLOWED for r in snapshot),'unsupported_operation')
    require(all(r['status']not in ('reserved','dispatching','accepted','started')for r in snapshot),'active_command')
    starts=[r for r in snapshot if r['operation']=='host_start']
    require(len(starts)==1 and starts[0]['run_id']==root_id and starts[0]['status']=='completed','host_start_not_terminal')
    require(supervisor['run_id']==root_id and supervisor['command_id']==starts[0]['command_id'],'supervisor_changed')
    files={};channels=[];seen=set();current=root_id;incoming=None;l=_layout()
    def load(path,digest=None):
        p=owned_file(path,run);obj,actual=_object(p,8*1024*1024)
        require(digest is None or digest==actual,'source_digest_changed')
        files[str(p)]=actual;return obj
    while current is not None:
        require(current in bindings and current not in seen,'unregistered_or_cyclic_epoch')
        seen.add(current);b=bindings[current];rows=byrun[current]
        report_path=run/('host-tactical-runtime.json'if current==root_id else 'host-tactical-runtime-'+current+'.json')
        report=load(report_path);require(report['binding']==b.public(),'epoch_report_binding_changed')
        require(report['native_layout']==l.inventory(),'epoch_native_layout_changed')
        boot=_decode(l.Bootstrap,report['bootstrap_hex']);actor=_decode(l.Actor,report['admitted_actor_hex'])
        attaches=[r for r in rows if r['operation']=='runtime_channel_attach']
        if incoming is None:require(not attaches,'root_attach_unexpected')
        else:
            require(len(attaches)==1,'successor_attach_missing_or_duplicate')
            attach=attaches[0];selection=successor_actor_selection(incoming)
            require(attach['status']in ('completed','uncertain')and attach['payload']['manifest_sha256']==incoming['_digest']
                and attach['payload']['binding_hash']==b.binding_hash
                and attach['payload']['persisted_sequence']==boot.persisted_sequence==incoming['persisted_sequence']
                and l.uuid_text(boot.producer.command)==selection['producer_command_id'],'successor_attach_identity_changed')
            if attach['status']=='completed':
                previous=_decode(l.Actor,incoming['facts']['previous_actor_hex'])
                previous_report=load(incoming['previous_report'],incoming['previous_report_sha256'])
                prior_boot=_decode(l.Bootstrap,previous_report['bootstrap_hex'])
                same=selection['mode']=='same_paid_actor'
                fields=('object_id','thing','template_ptr','update','owner','type_hash')
                matches=all(getattr(previous,k)==getattr(actor,k)for k in fields)if same else(
                    actor.object_id!=previous.object_id and actor.thing!=previous.thing and actor.update!=previous.update
                    and all(getattr(previous,k)==getattr(actor,k)for k in ('template_ptr','owner','type_hash'))
                    and boot.producer.sequence>prior_boot.producer.sequence and boot.producer.receipt_index>prior_boot.producer.receipt_index)
                receipt=attach['receipt']or{}
                require(matches and actor.born_frame>incoming['facts']['retirement_frame']
                    and receipt.get('producer_command_id')==l.uuid_text(boot.producer.command)
                    and receipt.get('object_id')==actor.object_id and receipt.get('generation')==actor.generation
                    and receipt.get('previous_manifest_sha256')==incoming['_digest'],'completed_successor_not_recomputed')
        retires=[r for r in rows if r['operation']=='runtime_channel_retire']
        require(len(retires)<=1,'multiple_retirements')
        retirement=None
        if retires:
            r=retires[0];require(r['status']=='completed','retirement_not_complete')
            receipt=r['receipt']or{};retirement=load(receipt['manifest'],receipt['manifest_sha256'])
            require(retirement['previous_run_id']==current and retirement['supervisor']==supervisor
                and all(retirement.get(k)==v for k,v in r['payload'].items()),'retirement_identity_changed')
            require(Path(retirement['previous_report']).resolve()==report_path.resolve()
                and retirement['previous_report_sha256']==files[str(report_path.resolve())],'retired_report_changed')
            captured=load(retirement['previous_capture'],retirement['previous_capture_sha256'])
        else:captured=capture_final(session_path,report_path)
        facts=assess_retirement(report,captured,b)
        if retirement is not None:require(facts==retirement['facts'],'retirement_facts_changed')
        header=_decode(l.SharedChannel,captured['header_before_hex'],l.SharedChannel.events.offset)
        require(header.command_generation==header.command_acknowledged and not(header.command_generation&1),'publication_not_quiescent')
        packets=[_decode(l.Command,r['wire_hex'])for r in report['commands']]
        require(header.command_generation==2*len(packets),'native_publication_count_changed')
        events=[_decode(l.WireEvent,r['raw_hex'])for r in report['events']]
        native_rows=[r for r in rows if r['operation']in NATIVE and not(r['operation']=='stop'and r['payload'].get('scope')=='host')]
        # Production shutdown has operation stop, but no tactical task/lease.
        native_rows=[r for r in native_rows if r['payload'].get('task_id')is not None]
        require({l.uuid_text(p.command)for p in packets}=={r['command_id']for r in native_rows},'native_command_inventory_changed')
        for p in packets:
            row=next(r for r in native_rows if r['command_id']==l.uuid_text(p.command))
            f=(row['receipt']or{}).get('facts',{})
            require(row['status']in ('completed','released','rejected','failed')and p.operation==NATIVE[row['operation']]
                and journal.get_native_sequence(current,row['command_id'])==p.sequence
                and row['payload'].get('task_id')==l.uuid_text(p.task)and row['payload'].get('lease_id')==l.uuid_text(p.lease)
                and f.get('command_id')==row['command_id']and f.get('seq')==p.sequence
                and f.get('binding_hash')==b.binding_hash,'native_journal_correlation_changed')
            matching=[e.receipt for e in events if tuple(e.receipt.command)==tuple(p.command)
                and e.receipt.sequence==p.sequence and tuple(e.receipt.task)==tuple(p.task)and tuple(e.receipt.lease)==tuple(p.lease)
                and e.receipt.frame==f.get('game_frame')and e.receipt.monotonic_ms==f.get('monotonic_ms')
                and e.receipt.phase<len(PHASES)and PHASES[e.receipt.phase]==f.get('phase')
                and all(type(f.get(k))is bool and f[k]==bool(getattr(e.receipt,k))for k in ('physical_home','control_released','stance_restored','held'))]
            require(f.get('source')=='native_tactical_runtime_v1'and bool(matching),'native_journal_receipt_not_in_original_events')
        uncertain=[r for r in rows if r['status']=='uncertain']
        require(all(r['operation']=='runtime_channel_attach'for r in uncertain),'unknown_tactical_command_requires_separate_recovery')
        if uncertain:
            require(len(uncertain)==1 and facts['no_control_acquired']is True and not packets and not report['events']
                and header.command_generation==0 and header.receipt.phase==0 and not header.receipt.held,'uncertain_attach_has_actual_control')
        channels.append(dict(run_id=current,binding=b.public(),report=str(report_path.resolve()),report_sha256=files[str(report_path.resolve())],
            capture=captured,facts=facts,uncertain_attach_ids=[r['command_id']for r in uncertain]))
        auth=[r for r in rows if r['operation']=='runtime_channel_successor_authorize']
        require(len(auth)<=1,'multiple_successor_authorizations')
        outgoing=None
        if auth:
            a=auth[0];require(retirement is not None and a['status']=='completed','successor_without_closed_retirement')
            receipt=a['receipt']or{};outgoing=load(receipt['manifest'],receipt['manifest_sha256'])
            require(outgoing['kind']=='closed_native_channel_new_binding_handoff'and outgoing['supervisor']==supervisor
                and outgoing['previous_run_id']==current and outgoing['facts']==facts
                and outgoing['retirement_manifest_sha256']==retires[0]['receipt']['manifest_sha256']
                and outgoing['next_run_id']==receipt['next_run_id']
                and outgoing['next_binding']==bindings[outgoing['next_run_id']].public(),'successor_authorization_changed')
            for name in ('previous_report','previous_capture'):
                require(outgoing[name]==retirement[name]and outgoing[name+'_sha256']==retirement[name+'_sha256'],'successor_sources_changed')
            outgoing['_digest']=receipt['manifest_sha256']
        elif retirement is not None and retirement['kind']=='closed_native_channel_new_binding_handoff':
            outgoing=dict(retirement,_digest=retires[0]['receipt']['manifest_sha256'])
            require(outgoing['next_binding']==bindings[outgoing['next_run_id']].public(),'immediate_successor_binding_changed')
        incoming=outgoing;current=outgoing['next_run_id']if outgoing is not None else None
    require(seen==set(bindings),'unlinked_session_epoch')
    return dict(channels=channels,files=files,command_snapshot_hash=content_hash(snapshot),epoch_ids=sorted(bindings))

def read_observer(pid):
    """The passive observer entry is also part of the final callback barrier."""
    k=c.WinDLL('kernel32',use_last_error=True)
    k.OpenFileMappingW.argtypes=[c.c_uint32,c.c_int,c.c_wchar_p];k.OpenFileMappingW.restype=c.c_void_p
    k.MapViewOfFile.argtypes=[c.c_void_p,c.c_uint32,c.c_uint32,c.c_uint32,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
    k.UnmapViewOfFile.argtypes=[c.c_void_p];k.CloseHandle.argtypes=[c.c_void_p]
    handle=k.OpenFileMappingW(4,False,f'Local\\RA3ProductionObserver_{pid}')
    if not handle:return dict(channel_absent=True)
    view=None
    try:
        view=k.MapViewOfFile(handle,4,0,0,68);require(bool(view),'observer_mapping_unreadable')
        before=c.string_at(view,68);after=c.string_at(view,68);h=struct.unpack('<17I',before)
        require(before==after and h[0]==0x50524f44 and h[1]==1 and h[2]==pid and 1<=h[3]<=30
            and h[4]>0 and h[4]==h[5]and h[9]==1 and h[10]==2 and h[11]==1 and h[12]==0 and h[15]==0 and h[16]==1,'passive_observer_not_closed')
        return dict(channel_absent=False,header_before_hex=before.hex(),header_after_hex=after.hex(),active_callbacks=0)
    finally:
        if view:k.UnmapViewOfFile(view)
        k.CloseHandle(handle)

def projection_verified(backend,run_id,binding,host_receipt):
    """Saved review pins all native sources and current non-review intents."""
    path=backend.state_dir/'runs'/run_id/'runtime-epochs-release-review.json'
    try:
        proof,digest=_object(path,8*1024*1024)
        require(proof['kind']=='runtime_epoch_host_release_review'and proof['binding']==binding.public()and proof['run_id']==run_id
            and proof['host_pid']==host_receipt.get('host_pid')and proof['host_start_time']==host_receipt.get('host_start_time')
            and proof['native_release_verified']is True and proof['mission_effect_granted']is False
            and proof['physical_home_claimed']is False and proof['natural_result_verified']is False,'saved_review_identity_changed')
        bindings=family(backend.journal,binding)
        require(sorted(bindings)==proof['epoch_ids']and content_hash(command_snapshot(backend.journal,bindings))==proof['command_snapshot_hash'],'saved_command_inventory_changed')
        require(not backend.journal.unresolved_for_session(binding.public()),'saved_review_unresolved_command')
        require(all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in proof['files'].items()),'saved_review_source_changed')
        reviews=backend.journal.commands_for_run(run_id,operation=ROOT_REVIEW)
        require(any(r['status']=='released'and(r['receipt']or{}).get('review_sha256')==digest
            and(r['receipt']or{}).get('binding_hash')==binding.binding_hash
            and(r['receipt']or{}).get('host_pid')==host_receipt.get('host_pid')
            and(r['receipt']or{}).get('host_start_time')==host_receipt.get('host_start_time')
            and(r['receipt']or{}).get('native_release_verified')is True
            and(r['receipt']or{}).get('mission_effect_granted')is False
            and(r['receipt']or{}).get('reason_code')=='runtime_epoch_host_native_entries_independently_verified'for r in reviews),'saved_review_receipt_missing')
        return True
    except (OSError,ValueError,TypeError,KeyError):return False

def review(backend,run_id):
    identifier(run_id);row=backend._launch(run_id);backend._status(row)
    binding=SessionBinding.from_dict(json.loads(row['binding_json']));launch=backend.journal.get_command(run_id,row['request_id'])
    receipt=launch['receipt']or{};require(NativeHostSpawner.identity(receipt.get('host_pid',0))is None,'host_still_alive')
    if projection_verified(backend,run_id,binding,receipt):return dict(run_id=run_id,native_release_verified=True,idempotent=True,native_writes=0)
    target=backend.state_dir/'runs'/run_id/'runtime-epochs-release-review.json'
    require(not target.exists(),'saved_review_incomplete_requires_explicit_audit')
    status,status_hash=_object(Path(row['output_path'])/'host-status.json',1024*1024)
    runtime=status.get('runtime_production')or{}
    require(launch['status']=='completed'and status['state']in ('fault','stopped','result_candidate')
        and status['host_pid']==receipt['host_pid']and status['host_start_time']==receipt['host_start_time']
        and status['session_id']==binding.session_id and status['pid']==binding.game_process_id
        and status['process_start']==binding.game_process_start and runtime.get('run_id')==run_id
        and runtime.get('binding_hash')==binding.binding_hash,'host_identity_changed')
    session,session_hash=_object(row['session_path']);run=Path(session['run_directory']).resolve(strict=True)
    require(session['session_id']==binding.session_id and session['pid']==binding.game_process_id
        and session['start_time']==binding.game_process_start,'session_changed')
    supervisor=dict(run_id=run_id,command_id=launch['command_id'],host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'])
    _module('live_state')  # Resolve the original reader before its local capture import.
    inspected=inspect_chain(backend.journal,run_id,binding,run,supervisor,Path(row['session_path']),capture_final=capture)
    first=inspected['channels'][0];l=_layout();report,_=_object(first['report'],8*1024*1024);boot=_decode(l.Bootstrap,report['bootstrap_hex'])
    commands=backend.journal.commands_for_run(run_id)
    stops=[r for r in commands if r['operation']=='stop'and r['status']=='released']
    require(any((r['receipt']or{}).get('facts',{}).get('production_release_verified')is True for r in stops),'production_stop_receipt_required')
    memory=_module('observe_production',Path(__file__).resolve().parents[2]/'production').Memory(binding.game_process_id,session)
    try:
        producer=read_producer(session,binding,[r for r in commands if r['operation']=='produce'],boot,memory)
        observer=read_observer(binding.game_process_id)
    finally:memory.close()
    files=inspected['files'];files[str(Path(row['output_path'])/'host-status.json')]=status_hash;files[str(Path(row['session_path']))]=session_hash
    require(all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in files.items())
        and NativeHostSpawner.identity(receipt['host_pid'])is None
        and content_hash(command_snapshot(backend.journal,family(backend.journal,binding)))==inspected['command_snapshot_hash'],'sources_changed_during_review')
    proof=dict(schema_version=1,kind='runtime_epoch_host_release_review',run_id=run_id,binding=binding.public(),
        host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'],**inspected,producer=producer,passive_observer=observer,
        native_release_verified=True,physical_home_claimed=False,mission_effect_granted=False,natural_result_verified=False,
        native_writes=0,sdk_game_calls=0,original_fault_preserved=True,
        reviewer_file=str(Path(__file__).resolve()),reviewer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target.parent.mkdir(parents=True,exist_ok=True);_write_once(target,proof);digest=hashlib.sha256(target.read_bytes()).hexdigest()
    # Each uncertain attach gets its own new journal record. No old outcome is
    # modified; partial persistence remains visibly incomplete, with no retry.
    for channel in inspected['channels']:
        b=SessionBinding.from_dict(channel['binding'])
        for prior in channel['uncertain_attach_ids']:
            request=str(uuid.uuid5(uuid.UUID(channel['run_id']),'independent-closed-attach:'+prior))
            intent=backend.journal.reserve_command(channel['run_id'],request,ATTACH_REVIEW,
                dict(recovery_of_command_id=prior,binding_hash=b.binding_hash))
            require(intent['created']is True,'attach_review_already_claimed')
            backend.journal.mark_dispatching(channel['run_id'],request)
            backend.journal.record_outcome(channel['run_id'],request,'released',dict(
                reason_code='runtime_attach_no_control_independently_closed',source='independent_runtime_epoch_release_review',
                reviewed_command_id=prior,binding_hash=b.binding_hash,review_sha256=digest,native_release_verified=True,
                channel_closed=True,no_control_acquired=True,mission_effect_granted=False))
    require(not backend.journal.unresolved_for_session(binding.public()),'ownership_not_independently_closed')
    request=str(uuid.uuid5(uuid.UUID(run_id),'independent-runtime-epochs-release'))
    intent=backend.journal.reserve_command(run_id,request,ROOT_REVIEW,dict(binding_hash=binding.binding_hash,epoch_ids=inspected['epoch_ids']))
    require(intent['created']is True,'host_review_already_claimed');backend.journal.mark_dispatching(run_id,request)
    backend.journal.record_outcome(run_id,request,'released',dict(reason_code='runtime_epoch_host_native_entries_independently_verified',
        binding_hash=binding.binding_hash,host_pid=receipt['host_pid'],host_start_time=receipt['host_start_time'],
        review_sha256=digest,native_release_verified=True,epochs=len(inspected['channels']),mission_effect_granted=False))
    require(projection_verified(backend,run_id,binding,receipt),'final_projection_not_verified')
    return dict(run_id=run_id,native_release_verified=True,epochs=len(inspected['channels']),review_file=str(target),native_writes=0)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);args=parser.parse_args(argv)
    home=Path(os.environ['LOCALAPPDATA'])/'Tacticore';library=load_registration(home)
    store=ProfileStore(Path(library['library_path']),home/'desktop-runtime');backend=DesktopBackend(store)
    try:print(json.dumps(review(backend,args.run_id)));return 0
    finally:backend.close();store.close()

if __name__=='__main__':raise SystemExit(main())
