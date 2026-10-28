"""Trusted retirement and one-use new-binding handoff of bounded native IO.

No capability is created here. Each successor still needs the independently
pinned movement scope, original paid producer and target-side fresh admission.
Old channels, command IDs and failures keep their original evidence identities.
"""
from dataclasses import dataclass, field, replace
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import struct
import uuid

from .contracts import ContractError, SessionBinding
from .journal import CommandJournal
from .host_supervisor import LiveHostSupervisor,pending_native_commands,verify_supervisor
from .runtime_evidence import (_layout,_decode,_values,_entry_signatures,
    verify_bootstrap_paid,verify_build_artifacts,_producer_types)

_SEAL=object()


def _write_once(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())


def assess_retirement(report,capture,binding):
    """Read-only byte-level closure check, without claiming mission success."""
    def check(name,value):
        if value is not True:raise ContractError('rotation_'+name)
    l=_layout();hashes=verify_build_artifacts(report['build_manifest'],l)
    check('ordinary_current_scope',report['binding']==binding.public() and report['diagnostic'] is False
        and report.get('field_scope_admitted') is True and report.get('field_evidence_id')
        and report['executor_sha256']==hashes['TacticoreRuntime1.dll']
        and report['native_host_sha256']==hashes['runtime_host.exe'])
    boot,actor=verify_bootstrap_paid(report,binding,l,check)
    check('paired_original_header',capture['header_before_hex']==capture['header_after_hex']
        ==report['header_before_hex']==report['header_after_hex']
        and capture['native_writes']==capture['sdk_game_calls']==0)
    h=_decode(l.SharedChannel,capture['header_before_hex'],l.SharedChannel.events.offset)
    check('native_closed',h.magic_word==l.MAGIC and h.protocol==l.VERSION
        and h.structure_size==c.sizeof(l.SharedChannel) and h.token>0 and h.state==3
        and h.hooks_restored==8191 and h.active_callbacks==0 and h.callback_thread==boot.binding.thread
        and h.receipt.held==0 and report['host_exit']==0
        and bytes(h.bootstrap)==bytes(boot) and _values(h.admitted_actor)==_values(actor))
    events=[_decode(l.WireEvent,r['raw_hex']) for r in capture['events']]
    traces=[_decode(l.WireHookTrace,r['raw_hex']) for r in capture['hook_traces']]
    check('complete_event_stream',0<=len(events)==h.events_written==report['events_written']<=l.CAPACITY
        and h.events_overwritten==report['events_overwritten']==0
        and all(e.ticket==r['ticket']==i+1 for i,(e,r) in enumerate(zip(events,capture['events'])))
        and [r['raw_hex'] for r in capture['events']]==[r['raw_hex'] for r in report['events']])
    check('complete_trace_stream',capture['trace_counters_before_hex']==capture['trace_counters_after_hex']
        ==report['trace_counters_before_hex']==report['trace_counters_after_hex']
        and struct.unpack('<ii',bytes.fromhex(capture['trace_counters_before_hex']))==(len(traces),0)
        and len(traces)==capture['traces_written']==report['traces_written']<=l.TRACE_CAPACITY and report['traces_overwritten']==0
        and all(t.ticket==r['ticket']==i+1 for i,(t,r) in enumerate(zip(traces,capture['hook_traces'])))
        and [r['raw_hex'] for r in capture['hook_traces']]==[r['raw_hex'] for r in report['hook_traces']])
    check('native_samples_bound',all(_values(e.observation.binding)==_values(boot.binding)
        and _values(e.observation.actor)==_values(actor) and e.observation.identity
        and e.observation.actor_birth_verified for e in events))
    commands=[_decode(l.Command,r['wire_hex']) for r in report['commands']]
    check('sequence_high_water',h.native_last_sequence==max([boot.persisted_sequence]+[p.sequence for p in commands])
        and all(a.sequence<b.sequence for a,b in zip(commands,commands[1:])))
    if commands:
        final=[e for e in events if bytes(e.receipt)==bytes(h.receipt)]
        check('actual_native_control_release',h.receipt.phase==12 and h.receipt.control_released==h.receipt.stance_restored==1
            and len(final)>0 and final[-1].observation.team==boot.native.default_team
            and final[-1].observation.stance==0 and tuple(h.receipt.command)==tuple(commands[-1].command))
    else:
        check('idle_without_control_transfer',h.receipt.phase==0 and h.receipt.accepted==0 and not events)
    originals=_entry_signatures();entries=report.get('terminal_entries') or []
    check('original_tactical_entries',len(entries)==len(originals)==13
        and {r['address'] for r in entries}==set(originals)
        and all(r['actual']==r['expected']==originals[r['address']] for r in entries))
    return dict(previous_binding=binding.public(),previous_token=h.token,
        previous_native_sequence=int(h.native_last_sequence),previous_actor_hex=bytes(actor).hex(),
        producer_command_id=l.uuid_text(boot.producer.command),
        retirement_frame=max(h.current_observation.frame,h.receipt.frame),
        original_events=len(events),original_traces=len(traces),control_released=bool(h.receipt.control_released),
        no_control_acquired=not commands,mission_effect_granted=False)


@dataclass(frozen=True)
class RuntimeHandoff:
    binding: SessionBinding
    run_id: str
    persisted_sequence: int
    manifest_path: Path
    manifest_sha256: str
    journal: CommandJournal=field(repr=False,compare=False)
    _seal: object=field(repr=False,compare=False)
    supervisor: LiveHostSupervisor | None=field(default=None,repr=False,compare=False)


def _closed_channel(owner,*,session_path,capture_path,manifest_path,supervisor=None):
    from .host_tactical import HostTactical
    from .runtime_channel_capture import capture
    if not isinstance(owner,HostTactical) or owner.adapter.test_only:
        raise ContractError('rotation_original_owner_required')
    journal=owner.journal;binding=owner.binding
    if pending_native_commands(journal,binding,supervisor):
        raise ContractError('rotation_prior_commands_unresolved')
    snapshot=owner.snapshot()
    if any(t['control'] is None or t['control']['state']!='released' for t in snapshot['tasks']):
        raise ContractError('rotation_prior_control_not_released')
    runtime=owner.transport;report_path=runtime.output
    if (Path(session_path).resolve()!=runtime.session_path or any(Path(p).resolve().parent!=report_path.parent
            for p in (capture_path,manifest_path))):
        raise ContractError('rotation_owned_run_paths_required')
    owner.shutdown()
    if not runtime._stopped or runtime.host.poll()!=0:
        raise ContractError('rotation_previous_native_host_not_closed')
    report_bytes=report_path.read_bytes();report=json.loads(report_bytes)
    captured=capture(Path(session_path),report_path)
    digest=hashlib.sha256(report_bytes).hexdigest()
    if captured['context_report_sha256']!=digest:
        raise ContractError('rotation_original_report_changed')
    facts=assess_retirement(report,captured,binding)
    return journal,binding,report_path,report_bytes,captured,digest,facts


def retire_channel(owner,*,session_path,capture_path,manifest_path,supervisor=None,successor_producer_command_id=None):
    """Retire a live known owner before authorizing exactly one successor."""
    journal,binding,report_path,report_bytes,captured,digest,facts=_closed_channel(owner,
        session_path=session_path,capture_path=capture_path,manifest_path=manifest_path,supervisor=supervisor)
    selected=(facts['producer_command_id'] if successor_producer_command_id is None else successor_producer_command_id)
    try:
        if str(uuid.UUID(selected))!=selected or not uuid.UUID(selected).int:raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise ContractError('rotation_successor_paid_command_invalid') from None
    selection=dict(mode='same_paid_actor' if selected==facts['producer_command_id'] else 'new_paid_conscript',
        producer_command_id=selected)
    high=journal.native_sequence_high_water(binding.public())
    if high<facts['previous_native_sequence']:
        raise ContractError('rotation_durable_sequence_behind_native')
    successor=replace(binding,host_id=str(uuid.uuid4()));run_id=str(uuid.uuid4())
    record=dict(schema_version=1,kind='closed_native_channel_new_binding_handoff',
        previous_run_id=owner.run_id,next_run_id=run_id,next_binding=successor.public(),
        persisted_sequence=high,previous_report=str(report_path),previous_report_sha256=digest,
        previous_capture=str(Path(capture_path).resolve()),facts=facts,
        successor_actor=selection,
        supervisor=supervisor.public() if supervisor is not None else None,
        actor_scope='Fresh independently admitted incarnation in a new host binding; old task/lease authority revoked')
    request=str(uuid.uuid5(uuid.UUID(owner.run_id),'retire_native_channel:'+digest))
    intent=journal.reserve_command(owner.run_id,request,'runtime_channel_retire',record)
    if intent['created'] is not True:raise ContractError('rotation_channel_already_retired')
    journal.mark_dispatching(owner.run_id,request)
    try:
        _write_once(capture_path,captured)
        record['previous_capture_sha256']=hashlib.sha256(Path(capture_path).read_bytes()).hexdigest()
        _write_once(manifest_path,record)
        manifest_path=Path(manifest_path).resolve();manifest_hash=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        journal.record_outcome(owner.run_id,request,'completed',dict(reason_code='native_channel_retired',
            manifest_sha256=manifest_hash,manifest=str(manifest_path),native_sequence=high))
        journal.register_run(run_id,successor.public())
        journal.append_event(run_id,'native_channel_successor_authorized',dict(previous_run_id=owner.run_id,
            manifest_sha256=manifest_hash,persisted_sequence=high))
    except BaseException:
        # No attach may follow an incomplete durable retirement.
        if journal.get_command(owner.run_id,request)['status']=='dispatching':
            journal.record_outcome(owner.run_id,request,'uncertain',dict(reason_code='native_retirement_persistence_unknown'))
        raise
    return RuntimeHandoff(successor,run_id,high,manifest_path,manifest_hash,journal,_SEAL,supervisor)


@dataclass(frozen=True)
class RuntimeRetirement:
    """Closed evidence only. It grants no next channel, actor or incarnation."""
    binding: SessionBinding
    run_id: str
    manifest_path: Path
    manifest_sha256: str
    journal: CommandJournal=field(repr=False,compare=False)
    _seal: object=field(repr=False,compare=False)
    supervisor: LiveHostSupervisor | None=field(default=None,repr=False,compare=False)


def retire_for_later(owner,*,session_path,capture_path,manifest_path,supervisor=None):
    journal,binding,report_path,report_bytes,captured,digest,facts=_closed_channel(owner,
        session_path=session_path,capture_path=capture_path,manifest_path=manifest_path,supervisor=supervisor)
    high=journal.native_sequence_high_water(binding.public())
    if high<facts['previous_native_sequence']:raise ContractError('rotation_durable_sequence_behind_native')
    record=dict(schema_version=1,kind='closed_native_channel_waiting_successor',previous_run_id=owner.run_id,
        previous_binding=binding.public(),persisted_sequence=high,previous_report=str(report_path),
        previous_report_sha256=digest,previous_capture=str(Path(capture_path).resolve()),facts=facts,
        supervisor=supervisor.public() if supervisor is not None else None,successor_authorized=False)
    request=str(uuid.uuid5(uuid.UUID(owner.run_id),'retire_native_channel:'+digest))
    intent=journal.reserve_command(owner.run_id,request,'runtime_channel_retire',record)
    if intent['created'] is not True:raise ContractError('rotation_channel_already_retired')
    journal.mark_dispatching(owner.run_id,request)
    try:
        _write_once(capture_path,captured)
        record['previous_capture_sha256']=hashlib.sha256(Path(capture_path).read_bytes()).hexdigest()
        _write_once(manifest_path,record);manifest_path=Path(manifest_path).resolve()
        digest=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        journal.record_outcome(owner.run_id,request,'completed',dict(reason_code='native_channel_retired_waiting_successor',
            manifest_sha256=digest,manifest=str(manifest_path),native_sequence=high,successor_authorized=False))
    except BaseException:
        if journal.get_command(owner.run_id,request)['status']=='dispatching':
            journal.record_outcome(owner.run_id,request,'uncertain',dict(reason_code='native_retirement_persistence_unknown'))
        raise
    return RuntimeRetirement(binding,owner.run_id,manifest_path,digest,journal,_SEAL,supervisor)


def validate_retirement(retirement):
    if not isinstance(retirement,RuntimeRetirement) or retirement._seal is not _SEAL:
        raise ContractError('rotation_sealed_retirement_required')
    raw=retirement.manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=retirement.manifest_sha256:
        raise ContractError('rotation_retirement_manifest_changed')
    record=json.loads(raw)
    if (record['kind']!='closed_native_channel_waiting_successor' or record['successor_authorized'] is not False
            or record['previous_binding']!=retirement.binding.public() or record['previous_run_id']!=retirement.run_id):
        raise ContractError('rotation_retirement_binding_changed')
    if retirement.supervisor is not None:
        verify_supervisor(retirement.journal,retirement.binding,retirement.supervisor)
        if record['supervisor']!=retirement.supervisor.public():raise ContractError('rotation_supervisor_changed')
    for name in ('previous_report','previous_capture'):
        if hashlib.sha256(Path(record[name]).read_bytes()).hexdigest()!=record[name+'_sha256']:
            raise ContractError('rotation_retired_evidence_changed')
    facts=assess_retirement(json.loads(Path(record['previous_report']).read_bytes()),
        json.loads(Path(record['previous_capture']).read_bytes()),retirement.binding)
    if facts!=record['facts']:raise ContractError('rotation_retirement_facts_changed')
    rows=retirement.journal.commands_for_run(retirement.run_id,operation='runtime_channel_retire')
    if not any(r['status']=='completed' and (r.get('receipt')or{}).get('manifest_sha256')==retirement.manifest_sha256 for r in rows):
        raise ContractError('rotation_durable_retirement_required')
    return record


def authorize_deferred_successor(retirement,*,producer_command_id,manifest_path):
    """One later fixed actor choice after read-only preparation; never retries."""
    record=validate_retirement(retirement);journal=retirement.journal;binding=retirement.binding
    if pending_native_commands(journal,binding,retirement.supervisor):raise ContractError('rotation_prior_commands_unresolved')
    selected=dict(mode='same_paid_actor' if producer_command_id==record['facts']['producer_command_id'] else 'new_paid_conscript',
        producer_command_id=producer_command_id)
    successor_actor_selection(dict(facts=record['facts'],successor_actor=selected))
    path=Path(manifest_path).resolve()
    if path.parent!=Path(record['previous_report']).parent:raise ContractError('rotation_owned_run_paths_required')
    high=journal.native_sequence_high_water(binding.public())
    if high<max(record['persisted_sequence'],record['facts']['previous_native_sequence']):raise ContractError('rotation_durable_sequence_regressed')
    successor=replace(binding,host_id=str(uuid.uuid4()));run_id=str(uuid.uuid4())
    payload=dict(schema_version=1,kind='closed_native_channel_new_binding_handoff',
        previous_run_id=retirement.run_id,next_run_id=run_id,next_binding=successor.public(),persisted_sequence=high,
        **{k:record[k]for k in ('previous_report','previous_report_sha256','previous_capture','previous_capture_sha256','facts','supervisor')},
        successor_actor=selected,retirement_manifest_sha256=retirement.manifest_sha256,
        actor_scope='Fixed paid actor selected after independently closed channel; native admission remains mandatory')
    request=str(uuid.uuid5(uuid.UUID(retirement.run_id),'authorize_deferred_successor:'+retirement.manifest_sha256))
    intent=journal.reserve_command(retirement.run_id,request,'runtime_channel_successor_authorize',
        dict(retirement_manifest_sha256=retirement.manifest_sha256,producer_command_id=producer_command_id))
    if intent['created'] is not True:raise ContractError('rotation_successor_already_authorized')
    journal.mark_dispatching(retirement.run_id,request)
    try:
        _write_once(path,payload);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        journal.record_outcome(retirement.run_id,request,'completed',dict(reason_code='native_successor_authorized_after_wait',
            manifest_sha256=digest,manifest=str(path),next_run_id=run_id,persisted_sequence=high))
        journal.register_run(run_id,successor.public())
        journal.append_event(run_id,'native_channel_successor_authorized',dict(previous_run_id=retirement.run_id,
            manifest_sha256=digest,persisted_sequence=high))
    except BaseException:
        if journal.get_command(retirement.run_id,request)['status']=='dispatching':
            journal.record_outcome(retirement.run_id,request,'uncertain',dict(reason_code='native_successor_authorization_unknown'))
        raise
    return RuntimeHandoff(successor,run_id,high,path,digest,journal,_SEAL,retirement.supervisor)


def successor_actor_selection(record):
    """A trusted immutable choice; target admission must still prove payment."""
    previous=record['facts']['producer_command_id']
    selected=record.get('successor_actor')
    if selected is None:return dict(mode='same_paid_actor',producer_command_id=previous)
    try:
        valid=(type(selected) is dict and set(selected)=={'mode','producer_command_id'}
            and str(uuid.UUID(selected['producer_command_id']))==selected['producer_command_id']
            and uuid.UUID(selected['producer_command_id']).int!=0
            and ((selected['mode']=='same_paid_actor' and selected['producer_command_id']==previous)
                or (selected['mode']=='new_paid_conscript' and selected['producer_command_id']!=previous)))
    except (ValueError,TypeError,AttributeError):valid=False
    if not valid:raise ContractError('rotation_successor_paid_selection_invalid')
    return selected


def validate_handoff(handoff,binding,producer_command_id):
    if not isinstance(handoff,RuntimeHandoff) or handoff._seal is not _SEAL or handoff.binding!=binding:
        raise ContractError('rotation_sealed_handoff_required')
    raw=handoff.manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=handoff.manifest_sha256:
        raise ContractError('rotation_handoff_manifest_changed')
    record=json.loads(raw)
    selected=successor_actor_selection(record)
    if handoff.supervisor is not None:
        verify_supervisor(handoff.journal,binding,handoff.supervisor)
        if record.get('supervisor')!=handoff.supervisor.public():raise ContractError('rotation_supervisor_changed')
    previous=SessionBinding.from_dict(record['facts']['previous_binding'])
    if (record['next_binding']!=binding.public() or previous.host_id==binding.host_id
            or replace(previous,host_id=binding.host_id)!=binding
            or selected['producer_command_id']!=producer_command_id
            or record['persisted_sequence']!=handoff.persisted_sequence
            or record['next_run_id']!=handoff.run_id):
        raise ContractError('rotation_handoff_binding_or_paid_actor_changed')
    for name in ('previous_report','previous_capture'):
        if hashlib.sha256(Path(record[name]).read_bytes()).hexdigest()!=record[name+'_sha256']:
            raise ContractError('rotation_retired_evidence_changed')
    return record


def claim_handoff(handoff,binding,producer_command_id):
    record=validate_handoff(handoff,binding,producer_command_id)
    journal=handoff.journal
    if pending_native_commands(journal,binding,handoff.supervisor):
        raise ContractError('rotation_prior_commands_unresolved')
    if journal.native_sequence_high_water(binding.public())<handoff.persisted_sequence:
        raise ContractError('rotation_durable_sequence_regressed')
    request=str(uuid.uuid5(uuid.UUID(handoff.run_id),'attach_retired_native_successor'))
    intent=journal.reserve_command(handoff.run_id,request,'runtime_channel_attach',dict(
        manifest_sha256=handoff.manifest_sha256,binding_hash=binding.binding_hash,
        persisted_sequence=handoff.persisted_sequence))
    if intent['created'] is not True:raise ContractError('rotation_handoff_already_claimed')
    journal.mark_dispatching(handoff.run_id,request)
    return request,record


def finish_handoff(handoff,request,runtime,actor):
    record=validate_handoff(handoff,runtime.binding,runtime.producer_command_id)
    l=_layout();previous=_decode(l.Actor,record['facts']['previous_actor_hex'])
    current=l.Actor.from_buffer_copy(runtime.actor_bytes)
    fields=('object_id','thing','template_ptr','update','owner','type_hash')
    selection=successor_actor_selection(record)
    same=selection['mode']=='same_paid_actor'
    actor_matches=(all(getattr(previous,k)==getattr(current,k) for k in fields) if same else
        current.object_id!=previous.object_id and current.thing!=previous.thing and current.update!=previous.update
        and all(getattr(previous,k)==getattr(current,k) for k in ('template_ptr','owner','type_hash')))
    if (runtime.token==record['facts']['previous_token']
            or not actor_matches
            or current.born_frame<=record['facts']['retirement_frame']
            or actor.identity.object_id!=current.object_id
            or runtime.shared.bootstrap.persisted_sequence!=handoff.persisted_sequence):
        raise ContractError('rotation_new_native_incarnation_unverified')
    if not same:
        # The selected command is not a birth grant. Recompute original raw
        # payment/creation proof and the producer's monotone ledger/budget.
        proof=dict(bootstrap_hex=runtime.bootstrap_bytes.hex(),admitted_actor_hex=runtime.actor_bytes.hex(),
            producer_receipt=runtime.producer_receipt)
        def check(name,value):
            if value is not True:raise ContractError('rotation_new_paid_'+name)
        boot,_=verify_bootstrap_paid(proof,runtime.binding,l,check)
        before=json.loads(Path(record['previous_report']).read_text(encoding='utf-8'))
        prior_boot=_decode(l.Bootstrap,before['bootstrap_hex'])
        _,Header=_producer_types(l)
        prior_header=_decode(Header,before['producer_receipt']['native_header_hex'])
        header=_decode(Header,runtime.producer_receipt['native_header_hex'])
        check('producer_sequence_and_budget',boot.producer.sequence>prior_boot.producer.sequence
            and boot.producer.receipt_index>prior_boot.producer.receipt_index
            and header.count>prior_header.count and header.spent>=prior_header.spent+85
            and header.total_budget==prior_header.total_budget and header.reserve_floor==prior_header.reserve_floor
            and header.spent<=header.total_budget)
    handoff.journal.record_outcome(handoff.run_id,request,'completed',dict(
        reason_code='new_bound_native_channel_admitted',previous_manifest_sha256=handoff.manifest_sha256,
        binding_hash=runtime.binding.binding_hash,channel_nonce=runtime.token,persisted_sequence=handoff.persisted_sequence,
        object_id=current.object_id,generation=current.generation,first_stable_observation_frame=current.born_frame,
        producer_command_id=runtime.producer_command_id,actor_selection_mode=selection['mode'],
        source_reference=runtime.output.name,mission_effect_verified=False))
