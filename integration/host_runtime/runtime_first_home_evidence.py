"""Fixed original-byte first-home recovery review. No game IO or input-selected code."""
import hashlib,json,math,struct,subprocess
from pathlib import Path,PurePosixPath
from .contracts import SessionBinding,ContractError,canonical_json,sha256
from .capabilities import VerifiedGrant
from .runtime_evidence import (_layout,_decode,_values,_point,verify_bootstrap_paid,
    verify_build_artifacts,qualify_runtime_report,verify_pinned_runtime,_entry_signatures,_producer_types,EvidenceError)
from .runtime_land_evidence import groups as land_groups,has_move_proof
from .runtime_home_evidence import groups as home_groups,has_return_proof,scalar


def qualify_first_home_recovery(data):
    """A successful data review alone grants no authority; registration is separate."""
    checks={}
    def check(name,value):
        checks[name]=value is True
        if not checks[name]:raise EvidenceError(name)
    try:return _review(data,checks,check)
    except (EvidenceError,OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError,subprocess.SubprocessError)as error:
        return dict(schema_version=1,status='not_passed',reason_code=str(error)if isinstance(error,EvidenceError)else'first_home_raw_evidence_invalid',checks=checks,ordinary_execution_granted=False,goal_effect_verified=False)


def _review(data,checks,check):
    trial,raw,cap=(data[k]for k in ('trial','native','capture'))
    l=_layout();binding=SessionBinding.from_dict(trial['binding'])
    hashes=verify_build_artifacts(raw['build_manifest'],l)
    check('current_build_artifacts_and_actual_abi',raw['executor_sha256']==hashes['TacticoreRuntime1.dll'] and raw['native_host_sha256']==hashes['runtime_host.exe'])
    check('explicit_owned_controlled_mode_no_natural_claim',raw['binding']==binding.public() and trial['controlled_native_move_experiment'] is True and raw['controlled_native_move_experiment'] is True and trial['fault_source']=='controlled_diagnostic_native_move' and trial['natural_AI_interference_claimed'] is False and raw['ordinary_execution_granted'] is False)
    boot,actor=verify_bootstrap_paid(raw,binding,l,check,expected_experimental_flags=2)
    h=_decode(l.SharedChannel,raw['header_before_hex'],l.SharedChannel.events.offset)
    check('native_header_binding_and_original_terminal_receipt',h.magic_word==l.MAGIC and h.protocol==l.VERSION and h.structure_size==l.inventory()['shared'] and h.token>0 and bytes(h.bootstrap)==bytes(boot) and _values(h.admitted_actor)==_values(actor) and h.callback_thread==boot.binding.thread and h.receipt.phase==12)
    check('native_closed_independent_paired_read',raw['header_before_hex']==raw['header_after_hex']==cap['header_before_hex']==cap['header_after_hex'] and raw['host_exit']==0 and h.state==3 and h.hooks_restored==8191 and h.active_callbacks==0 and cap['context_report_sha256']==data['_digests']['native'])
    check('complete_no_loss_raw_streams',raw['events_overwritten']==raw['traces_overwritten']==cap['events_overwritten']==cap['traces_overwritten']==0 and len(raw['events'])==len(cap['events'])==raw['events_written'] and 1<=len(raw['events'])<=l.CAPACITY and len(raw['hook_traces'])==len(cap['hook_traces'])==raw['traces_written'] and 1<=len(raw['hook_traces'])<=l.TRACE_CAPACITY and [r['raw_hex']for r in raw['events']]==[r['raw_hex']for r in cap['events']] and [r['raw_hex']for r in raw['hook_traces']]==[r['raw_hex']for r in cap['hook_traces']])
    events=[_decode(l.WireEvent,r['raw_hex'])for r in cap['events']];wires=[_decode(l.WireHookTrace,r['raw_hex'])for r in cap['hook_traces']];traces=[w.trace for w in wires]
    check('tickets_not_renumbered',all(e.ticket==i+1 for i,e in enumerate(events)) and all(w.ticket==i+1 for i,w in enumerate(wires)))
    check('original_stable_trace_counters',raw['trace_counters_before_hex']==raw['trace_counters_after_hex']==cap['trace_counters_before_hex']==cap['trace_counters_after_hex'] and struct.unpack('<ii',bytes.fromhex(raw['trace_counters_before_hex']))==(len(traces),0) and h.events_written==len(events))
    check('all_native_observations_bound_live_grounded',all(_values(e.observation.binding)==_values(boot.binding) and _values(e.observation.actor)==_values(actor) and e.observation.identity and e.observation.actor_birth_verified and e.observation.live_list_member and e.observation.grounded and not e.observation.paused and e.observation.current_thread==boot.binding.thread for e in events))
    check('monotonic_native_frames_and_clocks',all(a.observation.frame<=b.observation.frame and a.observation.monotonic_ms<=b.observation.monotonic_ms for a,b in zip(events,events[1:])))
    commands=[_decode(l.Command,r['wire_hex'])for r in raw['commands']];acks=[_decode(l.WireReceipt,r['acknowledged_hex'])for r in raw['commands']]
    check('four_distinct_accepted_packets_global1to4',len(commands)==len(acks)==4 and [c.operation for c in commands]==[1,2,8,7] and [c.sequence for c in commands]==[1,2,3,4] and boot.persisted_sequence==0 and h.native_last_sequence==4 and len({tuple(c.command)for c in commands})==4 and len({tuple(c.task)for c in commands})==len({tuple(c.lease)for c in commands})==1 and all(_values(c.actor)==_values(actor) and a.accepted==1 and a.sequence==c.sequence and tuple(a.command)==tuple(c.command) and tuple(a.task)==tuple(c.task) and tuple(a.lease)==tuple(c.lease)for c,a in zip(commands,acks)))
    operations={1:'reserve',2:'commit',8:'diagnostic_foreign_move',7:'reconcile_return_home'}
    check('wire_metadata_matches_original_binary',all(row['wire']['command_id']==l.uuid_text(c.command) and row['wire']['task_id']==l.uuid_text(c.task) and row['wire']['lease_id']==l.uuid_text(c.lease) and type(row['wire']['seq'])is int and row['wire']['seq']==c.sequence and row['wire']['operation']==operations[c.operation] and row['wire']['binding_hash']==binding.binding_hash and row['wire']['host_id']==binding.host_id and row['wire']['actor']==dict(object_id=actor.object_id,generation=actor.generation,born_frame=actor.born_frame) and row['wire']['payload']['expires_frame']==c.expires_frame and row['wire']['payload']['expires_monotonic_ms']==c.expires_monotonic_ms for row,c in zip(raw['commands'],commands)))
    packet={tuple(c.command):c for c in commands}
    check('terminal_identity_is_new_recovery_not_old_task',tuple(h.receipt.command)==tuple(commands[3].command) and tuple(h.receipt.task)==tuple(commands[3].task) and tuple(h.receipt.lease)==tuple(commands[3].lease))
    check('event_identities_never_rebound',all(tuple(e.receipt.command)in packet and e.receipt.sequence==packet[tuple(e.receipt.command)].sequence and tuple(e.receipt.task)==tuple(commands[0].task) and tuple(e.receipt.lease)==tuple(commands[0].lease)for e in events))
    unknown=[e for e in events if e.event_type==b'uncertain'];check('one_actual_guard_unknown_old_commit',len(unknown)==1 and unknown[0].receipt.sequence==2 and unknown[0].receipt.reason==b'unknown_native_command_observed' and unknown[0].receipt.held==1)
    failure=unknown[0];phases={e.receipt.phase:e for e in events if e.event_type==b'phase'}
    check('original_675_task_failed_not_reclassified',trial['status']=='failed_or_unknown' and trial['reason_code']=='runtime_calibration_native_result_uncertain' and commands[1].hold_frames==675 and 14 not in phases and 0<failure.observation.frame-phases[7].observation.frame<675)
    prior=data['prior']
    before=_decode(l.SharedChannel,prior['header_before_hex'],l.SharedChannel.events.offset)
    # The observation publishes last_sequence before the command slot is
    # processed. A stable old2 observation can coexist with acknowledged3.
    # Require that independent ack, not a fabricated combined old/new receipt.
    check('prior_unknown_and_independent_fault_ack_before_recovery',prior['header_before_hex']==prior['header_after_hex'] and before.native_last_sequence in (2,3) and bytes(before.bootstrap)==bytes(boot) and tuple(before.receipt.command)==tuple(commands[1].command) and before.receipt.sequence==2 and before.receipt.phase==13 and before.receipt.held==1 and before.receipt.physical_home==before.receipt.control_released==0 and list(before.receipt.sdk_calls)==[1,1,2,1,0,0] and before.command_generation==before.command_acknowledged==raw['commands'][2]['published_generation'] and before.command_receipt_generation>0 and not before.command_receipt_generation&1 and before.command.operation==8 and before.command.sequence==before.command_receipt.sequence==3 and tuple(before.command.command)==tuple(before.command_receipt.command)==tuple(commands[2].command) and before.command_receipt.accepted==1 and before.command_receipt.reason==b'controlled_native_move_sent')
    check('original_unknown_prefix_retained',len(prior['commands'])==3 and prior['commands']==raw['commands'][:3] and [r['raw_hex']for r in prior['events']]==[r['raw_hex']for r in cap['events'][:len(prior['events'])]] and [r['raw_hex']for r in prior['hook_traces']]==[r['raw_hex']for r in cap['hook_traces'][:len(prior['hook_traces'])]])
    for key,name,wire in (('controlled_fault_intent','controlled-fault-intent.json',trial['runtime_commands'][2]['wire']),('explicit_recovery_request_intent','recovery-return-intent.json',trial['explicit_recovery_request'])):
        role='fault_intent'if key=='controlled_fault_intent'else'home_intent';body=data[role];receipt=trial[key]
        check(name+'_immutable_intent_matches_wire',data['_digests'][role]==receipt['sha256'] and body['wire']==wire and body['ordinary_authority_granted'] is False and body['model_requests']==0)
    marker=[t for t in traces if t.kind==35]
    check('one_explicit_native_fault_marker',len(marker)==1 and marker[0].frame==failure.observation.frame and marker[0].scope==0 and marker[0].source==2 and marker[0].words[0]==1 and tuple(marker[0].words[1:5])==tuple(commands[2].command) and list(marker[0].words[5:8])==[3,0,2] and tuple(scalar(v)for v in marker[0].words[8:11])==_point(commands[2].target) and list(marker[0].words[11:15])==[actor.object_id,actor.thing,actor.update,2])
    foreign=[t for t in traces if 1<=t.kind<=10 and t.epoch_after>t.epoch_before]
    check('actual_external_facade_dispatch_private_move_epochs0to3',len(foreign)==3 and [t.kind for t in foreign]==[1,10,2] and [(t.epoch_before,t.epoch_after)for t in foreign]==[(0,1),(1,2),(2,3)] and all(t.frame==marker[0].frame and t.scope==0 and t.source==2 for t in foreign) and foreign[1].caller==0x571dcd and foreign[2].caller==0x6d3b7d)
    check('fault_ack_does_not_replace_old_control_identity',acks[2].reason==b'controlled_native_move_sent' and tuple(failure.receipt.command)==tuple(commands[1].command) and list(failure.receipt.sdk_calls)==[1,1,2,1,0,0])
    land=land_groups(traces,actor,boot.native.logic)
    check('fault_target_has_same_frame_native_ground_proof',land is not None and has_move_proof(land,commands[2].target,marker[0].frame))
    home=_point(next(e.observation.xyz for e in events if e.event_type==b'phase' and e.receipt.phase==1))
    intent_event=next(e for e in events if e.event_type==b'diagnostic_fault_intent')
    check('fault_actual_holding_stop_and_local_target_bounds',intent_event.receipt.phase==7 and intent_event.observation.settled and intent_event.observation.stance==2 and intent_event.observation.team==boot.native.script_team and intent_event.observation.foreign_epoch==0 and 30<=math.dist(_point(intent_event.observation.xyz)[:2],_point(commands[2].target)[:2])<=120 and 30<=math.dist(home[:2],_point(commands[2].target)[:2])<=300 and commands[2].lease_deadline_frame>intent_event.observation.frame)
    check('old_home_and_lease_fixed_no_retarget',_point(commands[3].target)==(0,0,0) and commands[3].hold_frames==0 and len({c.lease_deadline_frame for c in commands})==1 and commands[0].lease_deadline_frame-commands[0].expires_frame==780)
    q=trial['recovery_quiescent_frames'];quiet={s['frame']:s for s in trial['recovery_wait_observations']if s['frame']in q}
    check('four_new_independent_source2_stop_frames',len(q)==len(set(q))==len(quiet)==4 and min(q)>failure.observation.frame and max(q)<acks[3].frame and all(s['state_id']==94 and s['state_vtable']==0xc551a0 and s['command_source']==2 and s['stance']==2 and not s['path'] and not(s['state_flags']&0xffff) and s['foreign_epoch']==3 and s['team']==boot.native.script_team and s['identity'] is True and s['birth_verified'] is True for s in quiet.values()) and max(math.dist(s['xyz'][:2],next(iter(quiet.values()))['xyz'][:2])for s in quiet.values())<=1)
    for frame in q:
        slots=[t for t in traces if t.kind==16 and t.frame==frame];rows=[t for t in traces if t.kind==17 and t.frame==frame]
        check('native_paired_empty_slot_reverse_links_'+str(frame),len(slots)==len(rows)==1 and slots[0].self==actor.update+0x310 and slots[0].target==actor.thing and slots[0].words[0]==0xffffffff and rows[0].words[1]==actor.thing and rows[0].words[3]==rows[0].words[0] and list(rows[0].words[5:11])==[0xffffffff,2,0,2,94,0xc551a0] and rows[0].words[14]==rows[0].words[16]==boot.native.script_team and list(rows[0].words[17:23])==[actor.object_id,actor.thing,actor.template_ptr,actor.update,actor.owner,actor.type_hash] and rows[0].words[23]==1)
    check('new_operation7_accepted_after_original_unknown',acks[3].reason==b'new_explicit_first_home_recovery' and acks[3].frame>failure.observation.frame and list(acks[3].sdk_calls)==[1,1,2,1,0,0] and any(e.event_type==b'recovery_prior_unknown' and e.receipt.sequence==2 for e in events))
    ownmoves=[t for t in traces if t.kind==1 and t.scope==1];externalmoves=[t for t in traces if t.kind==1 and t.scope==0]
    check('two_owned_moves_plus_one_separate_injected_move',len(ownmoves)==2 and len(externalmoves)==1 and all(t.source==1 and t.operation==4 for t in ownmoves) and ownmoves[0].frame<failure.observation.frame<acks[3].frame<ownmoves[1].frame and tuple(scalar(v)for v in ownmoves[0].words[:3])==_point(commands[1].target) and tuple(scalar(v)for v in ownmoves[1].words[:3])==home and list(h.receipt.sdk_calls)==[1,1,4,2,1,1])
    stop=[t for t in traces if t.kind==3 and t.operation==3 and t.scope==t.source==1 and acks[3].frame<t.frame<ownmoves[1].frame]
    check('new_own_stop_before_first_home_move',len(stop)==1 and len({e.observation.frame for e in events if e.receipt.sequence==4 and stop[0].frame<e.observation.frame<=ownmoves[1].frame and e.observation.settled and e.observation.command_source==1 and e.observation.stance==2 and e.observation.team==boot.native.script_team})>=3)
    proofs=home_groups(traces,actor,boot.native.logic,boot.native.script_team)
    check('three_current_clear_home_stop_samples_and_same_frame_sdk',proofs is not None and has_return_proof(proofs,home,ownmoves[1].frame,[e.observation for e in events],boot.native.script_team))
    physical=phases[10];released=phases[12]
    home_stops=[t for t in traces if t.kind==3 and t.scope==t.source==1 and t.operation==3 and ownmoves[1].frame<t.frame<physical.observation.frame]
    distinct={e.observation.frame:e.observation for e in events if home_stops and home_stops[-1].frame<e.observation.frame<=physical.observation.frame}
    tail=list(distinct.values())[-3:]
    check('three_new_own_stopped_frames_at_actual_home',len(home_stops)==1 and len(tail)==3 and all(s.settled and s.command_source==1 and s.state_id==94 and s.state_vtable==0xc551a0 and not s.path and not(s.state_flags&0xffff) and s.team==boot.native.script_team and s.stance==2 and math.dist(_point(s.xyz)[:2],home[:2])<=15 for s in tail))
    check('actual_home_within15_after_single_first_home_move',physical.receipt.sequence==4 and physical.receipt.physical_home==1 and math.dist(_point(physical.observation.xyz)[:2],home[:2])<=15 and abs(physical.observation.xyz.z-home[2])<=2 and ownmoves[1].frame<physical.observation.frame<released.observation.frame)
    check('actual_native_pool_stance_and_control_return_no_goal_credit',h.receipt.sequence==4 and h.receipt.physical_home==h.receipt.control_released==h.receipt.stance_restored==1 and h.receipt.held==0 and released.observation.team==boot.native.default_team and released.observation.stance==0 and released.receipt.reason==b'native_control_release_without_goal_effect' and not any(e.receipt.phase==14 for e in events))
    check('bounded_recovery_without_later_foreign_or_attack',0<released.observation.monotonic_ms-acks[3].monotonic_ms<30000 and all(e.observation.foreign_epoch==3 for e in events if e.observation.frame>failure.observation.frame) and not any(t.kind==9 for t in traces))
    counters=[tuple(e.receipt.sdk_calls)for e in events]
    check('owned_sdk_counters_monotonic_and_terminal',all(all(x<=y for x,y in zip(a,b))for a,b in zip(counters,counters[1:])) and counters[-1]==tuple(h.receipt.sdk_calls))
    entries=_entry_signatures()
    check('13_native_hook_original_entry_bytes',len(raw['terminal_entries'])==13 and {r['address']for r in raw['terminal_entries']}==set(entries) and all(r['actual']==r['expected']==entries[r['address']]for r in raw['terminal_entries']))
    prod=data['cleanup']
    check('producer85_closed_and19_original_entries_readonly',prod['phase']==2 and prod['restore_mask']==31 and prod['active_callbacks']==prod['error']==0 and prod['spent']==prod['paid']==85 and prod['count']==len(trial['production_commands'])==1 and len(prod['entries'])==19 and all(r['actual']==r['expected']for r in prod['entries']) and prod['native_writes']==prod['sdk_game_calls']==0)
    Receipt,Header=_producer_types(l);producer=_decode(Header,prod['header_before_hex']);paid=_decode(Receipt,prod['receipt_hex'])
    entry_source={r['address']:r['expected']for r in data['entry_baseline']['entries']}
    check('raw_paired_producer_closure_and_pinned19_bytes',prod['header_before_hex']==prod['header_after_hex'] and producer.phase==2 and producer.restore_mask==31 and producer.active==producer.error==0 and producer.count==1 and producer.spent==85 and producer.pid==boot.binding.pid and tuple(producer.session)==tuple(boot.binding.session) and tuple(producer.commander)==tuple(boot.binding.commander) and (producer.start_low|(producer.start_high<<32))==boot.binding.process_start and paid.updates==paid.error==paid.payment_error==0 and paid.created==paid.completed==1 and paid.paid==paid.cost==85 and paid.object_id==actor.object_id and paid.object==actor.thing and prod['expected_source_sha256']==data['_digests']['entry_baseline'] and len(entry_source)==19 and {r['address']for r in prod['entries']}==set(entry_source) and all(r['actual']==r['expected']==entry_source[r['address']]for r in prod['entries']))
    ordinary=qualify_runtime_report(raw,binding)
    check('mode2_cannot_qualify_ordinary_runtime_scope',ordinary['status']=='not_passed' and ordinary['ordinary_execution_granted'] is False)
    check('no_model_no_natural_match_result_no_extra_recovery',trial['model_requests']==0 and trial['ordinary_execution_granted'] is False and 'failed_return_release_only_request'not in trial and data['fixture_end']['natural_result_verified'] is False)
    return dict(schema_version=1,status='passed',reason_code='ok',checks=checks,facts=dict(object_id=actor.object_id,born_frame=actor.born_frame,reserve_submission_sample_frame=commands[0].expires_frame-120,reserve_admitted_frame=next(e.observation.frame for e in events if e.event_type==b'phase' and e.receipt.phase==1),hold_started=phases[7].observation.frame,fault_and_unknown_frame=failure.observation.frame,foreign_epoch=3,quiescent_frames=q,recovery_accepted=acks[3].frame,first_home_move=ownmoves[1].frame,physical_home=physical.observation.frame,released=released.observation.frame,private_home=home,release_position=_point(released.observation.xyz),events=len(events),traces=len(traces),native_commands=[1,2,8,7],native_sequences=[1,2,3,4],owned_move_count=2,injected_move_count=1,final_sdk_calls=list(h.receipt.sdk_calls)),operation7_field_verified=True,operation8_field_verified=True,original_task_failed=True,goal_effect_verified=False,physical_home=True,control_released=True,ordinary_execution_granted=False,natural_AI_interference_claimed=False,natural_result_verified=False,full_goal_complete=False,native_writes=0,sdk_game_calls=0)


ROLES=frozenset(('baseline','native','trial','capture','prior','cleanup','fault_intent','home_intent',
    'fixture_end','session','snapshot','freeze','archive','entry_baseline'))


class _PinnedInputs:
    """Bounded immutable reads. No import or executable path comes from input."""
    def __init__(self):self.opened={};self.total=0
    @staticmethod
    def child(root,name):
        if (not isinstance(name,str) or not name or len(name)>512 or '\\'in name or ':'in name
                or PurePosixPath(name).is_absolute() or PurePosixPath(name).as_posix()!=name
                or any(p in ('..','.')for p in PurePosixPath(name).parts)):
            raise ContractError('first_home_evidence_path_invalid')
        result=(root/name).resolve(strict=True)
        if not result.is_relative_to(root.resolve()):raise ContractError('first_home_evidence_path_invalid')
        return result
    def bytes(self,path,expected,limit=8*1024*1024):
        sha256(expected)
        with path.open('rb')as stream:value=stream.read(limit+1)
        if len(value)>limit or hashlib.sha256(value).hexdigest()!=expected:
            raise ContractError('first_home_evidence_pin_mismatch')
        if path not in self.opened:self.total+=len(value)
        if self.total>128*1024*1024:raise ContractError('first_home_evidence_read_budget')
        self.opened[path]=expected
        return value
    def json(self,path,expected):
        def pairs(items):
            value={}
            for k,v in items:
                if k in value:raise ContractError('first_home_evidence_duplicate_key')
                value[k]=v
            return value
        return json.loads(self.bytes(path,expected).decode('utf-8-sig'),object_pairs_hook=pairs,
            parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite_json')))
    def unchanged(self):
        for path,digest in list(self.opened.items()):self.bytes(path,digest,limit=16*1024*1024)


def _load_bundle(path,digest):
    reader=_PinnedInputs();bundle=reader.json(path,digest)
    if (set(bundle)!= {'schema_version','protocol','inputs'} or type(bundle['schema_version'])is not int or bundle['schema_version']!=1
            or bundle['protocol']!='tactical_first_home_recovery_evidence_v1' or set(bundle['inputs'])!=ROLES):
        raise ContractError('first_home_evidence_bundle_invalid')
    data={'_digests':{}};paths={}
    for role,row in bundle['inputs'].items():
        if set(row)!={'file','sha256'}:raise ContractError('first_home_evidence_reference_invalid')
        paths[role]=reader.child(path.parent,row['file'])
        data[role]=reader.json(paths[role],row['sha256']);data['_digests'][role]=row['sha256']
    session,trial,raw=(data[k]for k in ('session','trial','native'))
    if (session['session_id']!=raw['binding']['session_id'] or session['pid']!=raw['binding']['game_process_id']
            or session['start_time']!=raw['binding']['game_process_start'] or trial['binding']!=raw['binding']
            or data['freeze']['session_sha256']!=data['_digests']['session']
            or data['freeze']['index_sha256']!=data['_digests']['snapshot'] or data['freeze']['commands_dispatched']!=0):
        raise ContractError('first_home_execution_provenance_invalid')
    if data['fixture_end']['session_id']!=session['session_id'] or data['fixture_end']['pid']!=session['pid']:
        raise ContractError('first_home_fixture_binding_invalid')
    frozen=paths['snapshot'].parent;rows=data['snapshot']['files']
    if not 32<=len(rows)<=256 or len({r['file']for r in rows})!=len(rows):
        raise ContractError('first_home_snapshot_invalid')
    pins={r['file']:r['sha256']for r in rows};source={}
    for name,pin in pins.items():
        value=reader.bytes(reader.child(frozen,name),pin,limit=16*1024*1024)
        if name in ('tactical/runtime/diagnose.py','tactical/runtime/controlled_fault.py'):source[name]=value.decode('utf-8')
    archive=data['archive'];outputs={r['file']for r in archive['build_manifest']['outputs']}
    if archive['build_manifest']!=raw['build_manifest'] or not 32<=len(archive['artifacts'])<=256:
        raise ContractError('first_home_archive_invalid')
    for row in archive['artifacts']:
        name=row['file'];original=row.get('source','tactical/runtime/'+('bin/'if name in outputs else'')+name)
        if pins.get(original)!=row['sha256']:raise ContractError('first_home_archive_source_changed')
        reader.bytes(reader.child(paths['archive'].parent,name),row['sha256'],limit=16*1024*1024)
    driver=source['tactical/runtime/diagnose.py'];helper=source['tactical/runtime/controlled_fault.py']
    if (driver.index("seal_owned_intent(output,'controlled-fault-intent.json'")>=driver.index('response = runtime.submit(wire)')
            or "path.open('xb')"not in helper or 'stream.flush();os.fsync(stream.fileno())'not in helper):
        raise ContractError('first_home_pre_effect_intent_unverified')
    return data,paths,reader


def verify_pinned_first_home(path,expected_sha256,binding,*,baseline_report=None,baseline_sha256=None):
    """Host-only opt-in: current flags0 baseline AND pinned raw flags2 recovery.

    The result permits operation7 for independently admitted old uncertainty.
    It does not grant diagnostic operation8, retreat of other units or combat.
    """
    sha256(expected_sha256)
    if not isinstance(path,Path) or not path.is_absolute() or not isinstance(binding,SessionBinding):
        raise ContractError('first_home_evidence_registration_required')
    try:
        data,paths,reader=_load_bundle(path,expected_sha256)
        if (baseline_report is None)!=(baseline_sha256 is None):raise ContractError('first_home_baseline_pin_required')
        if baseline_report is not None and (Path(baseline_report).resolve()!=paths['baseline'] or baseline_sha256!=data['_digests']['baseline']):
            raise ContractError('first_home_baseline_reference_mismatch')
        base=verify_pinned_runtime(paths['baseline'],data['_digests']['baseline'],binding)
        source=SessionBinding.from_dict(data['native']['binding'])
        if any(getattr(source,k)!=getattr(binding,k)for k in ('player_id','commander_id','game_sha256','mod_sha256')):
            raise ContractError('first_home_evidence_package_or_scope_mismatch')
        assessment=qualify_first_home_recovery(data)
        if assessment['status']!='passed' or not assessment['checks'] or not all(v is True for v in assessment['checks'].values()):
            raise ContractError('first_home_raw_evidence_unverified')
        native=data['native'];host=native['native_host_sha256'];executor=native['executor_sha256']
        if base.executor_sha256!=executor or base.public()['execution_constraints']['native_host_sha256']!=host:
            raise ContractError('first_home_baseline_binary_mismatch')
        reader.unchanged()
        constraints=dict(runtime_family='tactical',executor_directory='tactical/runtime',purpose='reconcile_return_home',
            module='runtime_first_home_recovery_v1',actor_roles=['infantry'],mission_protocol='tactical_runtime_v1',
            limits={'lease_frames':900},native_host_sha256=host,execution_ready=True,executor_sha256=executor,evidence_id=expected_sha256)
        return VerifiedGrant('tactics.reconcile_return_home',expected_sha256,expected_sha256,executor,
            'One paid Soviet Conscript; new first return to the original private home after old MoveHold uncertainty; no retry or goal credit',canonical_json(constraints))
    except ContractError:raise
    except (OSError,ValueError,KeyError,TypeError,AttributeError,UnicodeError,RecursionError,OverflowError):
        raise ContractError('first_home_evidence_registration_invalid')from None
