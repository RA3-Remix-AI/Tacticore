"""Owned, explicitly injected Host recovery experiment. No ordinary fault API."""
import json,time,uuid
from pathlib import Path
from host_runtime.host_tactical import HostTactical
from host_runtime.journal import CommandJournal
from live_state import atomic_json
from preborrow import choose_target,choose_commit_target
from journaled_trial import await_outcome
from controlled_fault import choose_fault_point,seal_owned_intent


def inject_once(runtime,actor,binding,journal,run_id,state,record,output):
    if (runtime.diagnostic is not True or runtime.controlled_fault_experiment is not True
            or runtime.reconcile_return_experiment is not True):raise ValueError('owned_host_fault_mode_required')
    if record.get('controlled_fault_attempted')is True:raise ValueError('owned_host_fault_already_attempted')
    record['controlled_fault_attempted']=True
    point,selection=choose_fault_point(runtime,binding,state)
    if point is None:raise ValueError('host_fault_no_native_endpoint_no_injection')
    snap=runtime.admit(binding)
    payload=dict(task_id=state['task_id'],generation=1,lease_id=state['lease_id'],target_point_id=point,
        expires_frame=min(snap.game_frame+120,runtime.lease_deadline_frame),expires_monotonic_ms=snap.monotonic_ms+5000,
        deadline_frame=runtime.lease_deadline_frame)
    request_id=str(uuid.uuid4())
    reserved=journal.reserve_command(run_id,request_id,'diagnostic_foreign_move',payload)
    sequence=journal.reserve_native_sequence(run_id,reserved['command_id'],snap.last_sequence)
    wire=dict(protocol='tactical_runtime_v1',command_id=reserved['command_id'],task_id=state['task_id'],lease_id=state['lease_id'],
        seq=sequence,operation='diagnostic_foreign_move',binding_hash=binding.binding_hash,host_id=binding.host_id,
        actor=dict(object_id=actor.identity.object_id,generation=actor.identity.generation,born_frame=actor.born_frame),payload=payload)
    record['controlled_fault_selection']=selection
    record['controlled_fault_request_id']=request_id;record['controlled_fault_wire']=wire
    record['controlled_fault_intent']=seal_owned_intent(output,'controlled-fault-intent.json',wire,selection)
    journal.append_event(run_id,'owned_controlled_fault_intent_sealed',dict(wire=wire,intent=record['controlled_fault_intent'],
        natural_AI_interference_claimed=False),command_id=reserved['command_id'],game_frame=snap.game_frame)
    atomic_json(output,record)
    journal.mark_dispatching(run_id,request_id)
    try:
        ack=runtime.submit(wire)
        accepted=(ack.get('command_id')==reserved['command_id'] and ack.get('seq')==sequence
            and ack.get('reason_code')=='controlled_native_move_sent' and ack.get('status')not in ('uncertain','rejected'))
        status='completed'if accepted else'rejected'if ack.get('status')=='rejected'else'uncertain'
        row=journal.record_outcome(run_id,request_id,status,dict(reason_code='owned_fault_delivery_acknowledged'if accepted else'owned_fault_not_verified',
            facts=dict(native_ack=ack,mission_effect_verified=False,natural_AI_interference_claimed=False)))
        record['controlled_fault_ack']=ack;record['controlled_fault_journal']=row;atomic_json(output,record)
        if not accepted:raise ValueError('host_controlled_fault_not_accepted')
        return row
    except BaseException:
        current=journal.get_command(run_id,request_id)
        if current['status']=='dispatching':journal.record_outcome(run_id,request_id,'uncertain',dict(reason_code='owned_fault_delivery_unknown_no_retry'))
        raise


def recover_once(owner,runtime,journal,run_id,failed,record,output,observe_environment=None):
    if 'journaled_recovery'in record:raise ValueError('owned_host_recovery_already_attempted')
    raw=Path(record['native_report']);prior=raw.with_name(raw.stem+'-pre-host-recovery.json')
    with prior.open('xb')as stream:stream.write(raw.read_bytes())
    recovery=record['journaled_recovery']=dict(original_receipt=failed,original_native_report=str(prior),status='preparing_first_home')
    record['explicit_recovery_request']=dict(dispatcher='HostTactical',task_id=failed['payload']['task_id'],recovery_of_command_id=failed['command_id'])
    atomic_json(output,record)
    try:
        sent=owner.reconcile_return_home(failed['payload']['task_id'],uncertain_command_id=failed['command_id'])
        recovery['request']=sent;atomic_json(output,record)
        done=await_outcome(owner,recovery,'released',35,observe_environment)
        if done['receipt']['facts'].get('physical_home')is not True:raise ValueError('host_recovery_no_physical_home')
        recovery['released']=done;recovery['status']='first_home_released_old_task_still_failed'
    except Exception as error:
        recovery['first_home_error']=str(error)if isinstance(error,(ValueError,TimeoutError))else type(error).__name__
        # One NEW release-only intent, after the Host's NEW quiescent window.
        # No repeated home, including when the first-home command was refused.
        latest=owner.poll()
        if latest is not None and latest['status']=='uncertain':
            record['failed_return_release_only_request']=dict(dispatcher='HostTactical',recovery_of_command_id=latest['command_id'])
            atomic_json(output,record)
            release=owner.reconcile_release(latest['payload']['task_id'],uncertain_command_id=latest['command_id'])
            recovery['release_only_request']=release
            recovery['release_only_terminal']=await_outcome(owner,recovery,'released',10,observe_environment)
            recovery['status']='released_only_first_home_failed'
        raise
    original=journal.get_command(run_id,failed['request_id'])
    if original!=failed:raise ValueError('host_recovery_rewrote_original_unknown')
    before=dict(sequence=int(runtime.shared.native_last_sequence),native_commands=len(runtime.command_rows))
    duplicate=owner.reconcile_return_home(failed['payload']['task_id'],uncertain_command_id=failed['command_id'])
    after=dict(sequence=int(runtime.shared.native_last_sequence),native_commands=len(runtime.command_rows))
    recovery['original_after']=original
    recovery['idempotent_replay']=dict(before=before,after=after,same_command=duplicate['command_id']==done['command_id'])
    if before!=after or duplicate['command_id']!=done['command_id']:raise ValueError('host_recovery_replay_dispatched')
    if journal.unresolved(run_id):raise ValueError('host_recovery_unresolved_control')
    atomic_json(output,record)


def run_trial(runtime,actor,binding,catalog,record,output,*,home_window,observe_environment=None):
    if (runtime.diagnostic is not True or runtime.controlled_fault_experiment is not True
            or runtime.reconcile_return_experiment is not True or runtime.test_only):raise ValueError('owned_host_recovery_experiment_required')
    catalog.require('tactics.move_hold_return',binding);catalog.require('tactics.reconcile_return_home',binding)
    # Even in the explicitly injected bootstrap mode, operation7 must exercise
    # the ordinary verified transport gate; diagnostic mode is only for8.
    runtime._field_admission(catalog)
    path=Path(output).parent/'first-home-runtime.sqlite3'
    if path.exists():raise ValueError('new_host_recovery_journal_required')
    run_id=str(uuid.uuid4());owner=None
    with CommandJournal(path)as journal:
        record.update(journal_run_id=run_id,journal_path=str(path),status='journaled_first_home_running',
            original_task_failed=False,ordinary_execution_granted=False,host_recovery_owns_cleanup=True,
            host_runtime_catalog=catalog.describe())
        try:
            owner=HostTactical(journal,run_id,binding,catalog,transport=runtime)
            target=choose_target(runtime,binding,record,home_window,observe_environment)
            task=str(uuid.uuid4());record['host_task_id']=task
            record['host_reserve']=owner.reserve(task,object_id=actor.identity.object_id,actor_generation=actor.identity.generation,lease_frames=900)
            await_outcome(owner,record,'completed',10,observe_environment)
            lease=record['host_reserve']['payload']['lease_id']
            target=choose_commit_target(runtime,binding,record,task,lease,target,observe_environment)
            record['target_point_id']=target;record['host_commit']=owner.commit(task,target_point_id=target,hold_frames=675)
            atomic_json(output,record)
            until=time.monotonic()+30;holding=None;injected=False;failed=None
            while time.monotonic()<until:
                current=owner.poll();state=runtime.poll()
                if observe_environment is not None:observe_environment('host_recovery_'+state['phase'])
                if current['status']=='uncertain':
                    failed=current;break
                if current['status']in ('released','rejected','failed'):raise ValueError('host_work_terminal_before_controlled_unknown')
                if state['phase']=='holding':
                    if holding is None:holding=state['game_frame']
                    if not injected and state['game_frame']>=holding+20:
                        # Set before any call: exceptions never retry the fault.
                        injected=True;inject_once(runtime,actor,binding,journal,run_id,state,record,output)
                time.sleep(.04)
            if failed is None:raise TimeoutError('host_controlled_unknown_not_observed')
            record['original_task_failed']=True;record['original_task_failure']=failed
            recover_once(owner,runtime,journal,run_id,failed,record,output,observe_environment)
            if not injected:raise ValueError('natural_unknown_recovered_but_controlled_branch_not_exercised')
            record['status']='journaled_first_home_recovery_requires_independent_review'
        except Exception as error:
            record['status']='failed_or_unknown';record['host_trial_error']=str(error)if isinstance(error,(ValueError,TimeoutError))else type(error).__name__
            # An unplanned early native unknown still uses the same Host safety
            # path once; it cannot be relabelled as the planned injected case.
            if owner is not None and 'journaled_recovery'not in record:
                try:
                    current=owner.poll()
                    if current is not None and current['status']=='uncertain':
                        record['original_task_failed']=True;record['original_task_failure']=current
                        recover_once(owner,runtime,journal,run_id,current,record,output,observe_environment)
                except Exception as cleanup_error:
                    record['host_recovery_error']=str(cleanup_error)if isinstance(cleanup_error,(ValueError,TimeoutError))else type(cleanup_error).__name__
            raise
        finally:
            if owner is not None:record['journaled_owner_snapshot']=owner.snapshot()
            record['journal_events']=journal.events(run_id);record['journal_unresolved']=journal.unresolved(run_id)
            atomic_json(output,record)
