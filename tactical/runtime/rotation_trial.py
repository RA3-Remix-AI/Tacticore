"""Three real bounded channels in one game, with explicit durable epoch links."""
from pathlib import Path
import hashlib
import json
import time
import uuid

from host_runtime.journal import CommandJournal
from host_runtime.runtime_rotation import retire_channel,assess_retirement,_write_once
from host_runtime.runtime_channel_capture import capture
from journaled_trial import run_trials,verified_catalog
from preborrow import HomeWindow,PlanningUnavailable
from live_state import atomic_json,own_candidates


def wait_retired_gap(memory,player_id,actor,seconds,record,output,*,require_previous_actor=True):
    """Read-only real-game interval after closure, before any successor attach."""
    if type(seconds) is not int or not 0<=seconds<=120:raise ValueError('retired_gap_budget_invalid')
    gap=dict(requested_wall_seconds=seconds,source='own_live_list_only_no_command_authority',
        game_commands=0,native_channel_held=False,previous_actor_required=require_previous_actor,samples=[])
    record.setdefault('retired_channel_intervals',[]).append(gap)
    started=time.monotonic();deadline=started+seconds
    while time.monotonic()<deadline:
        census=own_candidates(memory,player_id,{})
        if census['frame_start']==census['frame_end']:
            row=next((r for r in census['candidates'] if r['object_id']==actor.object_id),None)
            same=(row is not None and int(row['address'],0)==actor.thing and int(row['ai_address'],0)==actor.update
                and int(row['owner_address'],0)==actor.owner and int(row['type_hash'],0)==actor.type_hash)
            gap['samples'].append(dict(frame_start=census['frame_start'],frame_end=census['frame_end'],
                monotonic_ms=int(time.monotonic()*1000),actor_present=bool(same)))
            if not same and require_previous_actor:
                gap['status']='actor_unavailable_no_successor_attach';atomic_json(output,record)
                raise ValueError('retired_actor_unavailable_no_successor_attach')
        atomic_json(output,record)
        time.sleep(min(1,max(0,deadline-time.monotonic())))
    gap['elapsed_wall_seconds']=time.monotonic()-started
    samples=gap['samples']
    if seconds and (len(samples)<2 or samples[-1]['frame_end']<=samples[0]['frame_start']):
        gap['status']='no_verified_game_progress_no_successor_attach';atomic_json(output,record)
        raise ValueError('retired_gap_no_verified_game_progress')
    gap['status']='completed_read_only_no_control_held';atomic_json(output,record)


def produce_successor_actor(producer,handoff,command_id,record,output,memory):
    """One journaled bounded calibration purchase; original payment is rechecked natively."""
    binding=handoff.binding;journal=handoff.journal
    frame=memory.u32(memory.u32(0xcd8ce4)+0x50)
    command=dict(session_id=binding.session_id,player_id=binding.player_id,commander_id=binding.commander_id,
        command_id=command_id,task_id=str(uuid.uuid4()),seq=int(producer.shared.last_seq)+1,
        unit='conscript',budget=85,reserve=producer.reserve_floor,expires_frame=frame+450)
    request=str(uuid.uuid5(uuid.UUID(handoff.run_id),'single_paid_successor:'+command_id))
    intent=journal.reserve_command(handoff.run_id,request,'runtime_successor_produce',command)
    if not intent['created']:raise ValueError('successor_production_intent_already_used')
    journal.mark_dispatching(handoff.run_id,request)
    entry=dict(command=command,status='dispatch_intent_committed',journal_request_id=request)
    record['production_commands'].append(entry);atomic_json(output,record)
    try:
        receipt=producer.submit(command);entry['receipt']=receipt;atomic_json(output,record)
        if receipt.get('accepted') is not True:raise ValueError('successor_paid_production_not_accepted_no_retry')
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            status=producer.status();entry['production_status']=status
            paid=next((r for r in status['ledger'] if r.get('command_id')==command_id),None)
            if paid and paid.get('completed') is True and paid.get('paid_verified') is True and paid.get('paid')==paid.get('cost')==85 and paid.get('created') is True:
                entry['status']='completed_paid_native_birth';entry['completed_receipt']=paid
                journal.record_outcome(handoff.run_id,request,'completed',dict(source='bounded_original_native_calibration_producer',
                    producer_command_id=command_id,object_id=paid['object_id'],paid=85,mission_effect_verified=False))
                atomic_json(output,record);return
            if paid and paid.get('status') in ('unknown','failed','rejected'):raise ValueError('successor_paid_birth_failed_or_unknown')
            time.sleep(.1)
        raise TimeoutError('successor_paid_birth_timeout_no_retry')
    except BaseException:
        if journal.get_command(handoff.run_id,request)['status']=='dispatching':
            journal.record_outcome(handoff.run_id,request,'uncertain',dict(reason_code='successor_production_unknown_no_retry'))
        entry['status']='failed_or_unknown_no_retry';atomic_json(output,record);raise


def run_rotation_trials(client_module,runtime,actor,binding,catalog,record,output,*,memory,session_path,state,observe_environment=None,gap_seconds=0,fresh_paid_actors=False,epochs=3,hold_frames=15,lease_frames=750):
    if type(epochs) is not int or not 2<=epochs<=4 or (fresh_paid_actors and epochs>3):
        raise ValueError('rotation_epoch_or_paid_budget_invalid')
    run=Path(output).parent;path=run/'rotated-runtime.sqlite3'
    if path.exists():raise ValueError('rotation_experiment_requires_new_journal')
    journal=CommandJournal(path);channels=record['rotation_channels']=[];run_id=str(uuid.uuid4())
    state.update(runtime=runtime,binding=binding,raw_path=runtime.output,closed_verified=False)
    record.update(protocol='experimental_native_channel_rotation_v1',status='real_channel_rotation_running',
        rotation_journal=str(path),requested_epochs=epochs,requested_hold_frames=hold_frames,requested_lease_frames=lease_frames,
        scope=f'{epochs} explicitly bound ordinary native epochs in one unchanged game/producer; preserve all retired streams, sequence and failures')
    record['successor_actor_policy']='new_paid_conscript' if fresh_paid_actors else 'same_paid_actor'
    try:
        for ordinal in range(1,epochs+1):
            trial_path=run/(Path(output).stem+f'-channel{ordinal}.json')
            trial=dict(schema_version=1,protocol='journaled_single_actor_runtime_trial_v1',
                session_id=binding.session_id,binding=binding.public(),field_source_granted=False,
                native_report=str(runtime.output),model_requests=0,runtime_evidence=record['runtime_evidence'],
                runtime_evidence_sha256=record['runtime_evidence_sha256'],status='preparing')
            channel=dict(ordinal=ordinal,trial=str(trial_path),native_report=str(runtime.output),
                binding=binding.public(),journal_run_id=run_id)
            channels.append(channel);atomic_json(output,record)
            private_actor=client_module.layout.Actor.from_buffer_copy(runtime.actor_bytes)
            home=HomeWindow(memory,binding.player_id,private_actor);owner_state={}
            planning_unavailable=False
            try:
                run_trials(runtime,actor,binding,catalog,trial,trial_path,home_window=home,
                    observe_environment=observe_environment,journal=journal,run_id=run_id,
                    single_task=True,owner_state=owner_state,hold_frames=hold_frames,lease_frames=lease_frames)
                channel['task_effect_reported']=True
            except PlanningUnavailable:
                # A new binding cannot make this same actor/endpoint eligible.
                # Close this channel; retain earlier task evidence and stop the
                # experiment without spending further attach intents.
                planning_unavailable=True
                channel.update(task_effect_reported=False,not_dispatched=True)
                if trial.get('status')!='planning_unavailable_no_new_task_dispatched':raise
            except Exception as error:
                trial.update(status='failed_or_unknown',reason_code=str(error) if isinstance(error,(ValueError,TimeoutError)) else type(error).__name__)
                channel['task_effect_reported']=False
                if 'explicit_recovery_request' in trial:
                    record['explicit_recovery_request']=trial['explicit_recovery_request']
                atomic_json(trial_path,trial)
                # Continue only after the new journaled recovery actually closed
                # control. A failed task remains failed in its original file.
                if journal.unresolved_for_session(binding.public()):raise
            owner=owner_state.get('owner')
            if owner is None:raise ValueError('rotation_original_owner_missing')
            if journal.unresolved_for_session(binding.public()):raise ValueError('rotation_control_not_released')
            state['terminal']=runtime.poll()
            capture_path=run/(Path(output).stem+f'-channel{ordinal}-retired-readonly.json')
            if ordinal<epochs and not planning_unavailable:
                manifest=run/(Path(output).stem+f'-handoff{ordinal}.json')
                next_paid=str(uuid.uuid4()) if fresh_paid_actors else runtime.producer_command_id
                handoff=retire_channel(owner,session_path=session_path,capture_path=capture_path,manifest_path=manifest,
                    successor_producer_command_id=next_paid)
                channel.update(retired_capture=str(capture_path),handoff=str(manifest),
                    handoff_sha256=handoff.manifest_sha256,native_report_sha256=hashlib.sha256(runtime.output.read_bytes()).hexdigest(),closed=True)
                state['closed_verified']=True
                atomic_json(output,record)
                wait_retired_gap(memory,binding.player_id,private_actor,gap_seconds,record,output,
                    require_previous_actor=not fresh_paid_actors)
                if fresh_paid_actors:
                    produce_successor_actor(runtime.producer,handoff,next_paid,record,output,memory)
                next_binding=handoff.binding
                next_catalog=verified_catalog(next_binding,record['runtime_evidence'],record['runtime_evidence_sha256'])
                successor=client_module.NativeRuntimeClient(session_path,next_binding,runtime.producer,
                    next_paid,run/(Path(output).stem+f'-channel{ordinal+1}-native.json'),handoff=handoff)
                state.update(runtime=successor,binding=next_binding,raw_path=successor.output,closed_verified=False)
                actor=successor.attach(capabilities=next_catalog)
                runtime,binding,catalog,run_id=successor,next_binding,next_catalog,handoff.run_id
                record['native_report']=str(runtime.output)
            else:
                owner.shutdown()
                captured=capture(Path(session_path),runtime.output)
                raw=json.loads(runtime.output.read_text(encoding='utf-8'))
                closure=assess_retirement(raw,captured,binding)
                _write_once(capture_path,captured)
                channel.update(retired_capture=str(capture_path),closure=closure,
                    native_report_sha256=hashlib.sha256(runtime.output.read_bytes()).hexdigest(),closed=True)
                state['closed_verified']=True
            atomic_json(output,record)
            if planning_unavailable:
                record.update(status='rotation_planning_unavailable_requires_review',
                    reason_code=trial['reason_code'],unused_epochs=epochs-ordinal,
                    stopped_without_successor_attach=True)
                return
        record['status']='journaled_rotation_native_terminal_requires_independent_review'
    finally:
        record['rotation_journal_events']={ch['journal_run_id']:journal.events(ch['journal_run_id']) for ch in channels}
        record['rotation_unresolved']=journal.unresolved_for_session(binding.public())
        journal.close();atomic_json(output,record)
