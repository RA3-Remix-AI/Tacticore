"""Bounded real HostTactical repetition; accepts only independently pinned scope.

This is a trusted calibration driver, not model or WebView authority. It owns no
game transport: diagnose.py owns the original paid producer, native client and
final cleanup. Journal uncertainty is retained even if separate safety cleanup
later succeeds.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import time
import uuid

from host_runtime.capabilities import CapabilityCatalog
from host_runtime.host_tactical import HostTactical
from host_runtime.journal import CommandJournal
from host_runtime.runtime_evidence import verify_pinned_runtime
from live_state import atomic_json
from preborrow import choose_target, choose_commit_target, PlanningUnavailable


def verified_catalog(binding, source, digest, *, recovery_source=None,recovery_digest=None):
    source = Path(source).resolve(strict=True)
    if (recovery_source is None)!=(recovery_digest is None):raise ValueError('journaled_recovery_pin_required')
    grants=[verify_pinned_runtime(source,digest,binding)]
    if recovery_source is not None:
        from host_runtime.runtime_first_home_evidence import verify_pinned_first_home
        grants.append(verify_pinned_first_home(Path(recovery_source).resolve(strict=True),recovery_digest,binding,
            baseline_report=source,baseline_sha256=digest))
    return CapabilityCatalog.verify(binding,grants,lambda candidate,current:candidate)


def await_outcome(owner, task_record, expected, timeout, observe_environment=None):
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        result = owner.poll()
        if result is None:
            raise ValueError('journaled_trial_missing_bound_observation')
        task_record['last_journal_record'] = result
        phase = (result.get('receipt') or {}).get('facts', {}).get('phase')
        if observe_environment is not None:
            observe_environment('waiting_' + str(phase), task_record.get('target_xyz'))
        key = result['command_id'], result['status'], phase
        if key != previous:
            task_record.setdefault('observed_transitions', []).append(dict(
                command_id=result['command_id'], status=result['status'], phase=phase))
            previous = key
        if result['status'] == expected:
            return result
        if result['status'] in ('uncertain', 'rejected', 'failed', 'released'):
            raise ValueError('journaled_trial_unexpected_terminal_' + result['status'])
        time.sleep(.04)
    raise TimeoutError('journaled_trial_native_outcome_timeout')


def run_trials(runtime, actor, binding, catalog, record, output, *, home_window, observe_environment=None,
               budget_recovery_experiment=False, journal=None, run_id=None, single_task=False, owner_state=None,
               hold_frames=15,lease_frames=750):
    if (type(hold_frames) is not int or type(lease_frames) is not int or not 0<=hold_frames<=675
            or not 150<=lease_frames<=900 or hold_frames+120>lease_frames):
        raise ValueError('journaled_trial_hold_or_lease_budget_invalid')
    if runtime.diagnostic or runtime.test_only:
        raise ValueError('journaled_trial_requires_admitted_original_native_client')
    if type(budget_recovery_experiment) is not bool:
        raise ValueError('journaled_budget_experiment_requires_explicit_bool')
    if type(single_task) is not bool or (single_task and (journal is None or budget_recovery_experiment)):
        raise ValueError('journaled_single_task_requires_explicit_shared_rotation_journal')
    run = Path(output).parent
    owns_journal=journal is None
    if owns_journal:
        journal_path=run/'journaled-runtime.sqlite3'
        if journal_path.exists():raise ValueError('journaled_trial_requires_new_journal')
        journal=CommandJournal(journal_path)
    else:
        if not isinstance(journal,CommandJournal):raise ValueError('journaled_original_journal_required')
        journal_path=run/'rotated-runtime.sqlite3'
    run_id = run_id or str(uuid.uuid4())
    owner = None
    record.update(status='journaled_repetition_running', journal_run_id=run_id,
        journal_path=str(journal_path), journaled_tasks=[], existing_field_scope_used=True,
        requested_hold_frames=hold_frames,requested_lease_frames=lease_frames,
        scope='Two real sequential local Move/Hold/home/return tasks through HostTactical and the authoritative journal')
    if budget_recovery_experiment:
        record.update(journaled_budget_recovery_experiment=True,
            scope='Up to three real sequential local tasks; bounded native proof-budget failure and one new journaled release-only recovery; no long-match grant')
    if single_task:record['scope']='One real local task in an explicitly bound native-channel epoch; no long-match or combat grant'
    try:
        owner = HostTactical(journal, run_id, binding, catalog, transport=runtime)
        for ordinal in ((1,) if single_task else (1,2,3) if budget_recovery_experiment else (1,2)):
            if ordinal==3 and int(runtime.shared.traces_written)>2800:
                raise ValueError('journaled_third_lease_not_started_trace_headroom_insufficient')
            task_id = str(uuid.uuid4())
            trial = dict(ordinal=ordinal, task_id=task_id, status='selecting_before_borrow',
                object_id=actor.identity.object_id, actor_generation=actor.identity.generation)
            record['journaled_tasks'].append(trial)
            atomic_json(output, record)
            planning_before=dict(sequence=int(runtime.shared.native_last_sequence),native_commands=len(runtime.command_rows))
            try:
                target = choose_target(runtime, binding, trial, home_window, observe_environment)
            except PlanningUnavailable:
                planning_after=dict(sequence=int(runtime.shared.native_last_sequence),native_commands=len(runtime.command_rows))
                # Only the local planning window can produce this classification.
                # Any concurrent dispatch or durable command keeps the failure path.
                if planning_before!=planning_after or any(row['payload'].get('task_id')==task_id for row in journal.commands_for_run(run_id)):
                    raise ValueError('planning_refusal_dispatch_state_changed')
                trial.update(status='not_dispatched',planning_dispatch_guard=dict(before=planning_before,after=planning_after))
                record.update(status='planning_unavailable_no_new_task_dispatched',reason_code=trial['planning_outcome']['reason_code'])
                journal.append_event(run_id,'tactical_planning_not_dispatched',dict(task_id=task_id,
                    object_id=actor.identity.object_id,actor_generation=actor.identity.generation,
                    reason_code=trial['planning_outcome']['reason_code'],native_sequence=planning_after['sequence'],
                    new_tactical_commands=0,mission_effect_verified=False))
                raise
            trial['preborrow_target_point_id'] = target
            trial['target_xyz'] = list(runtime.approved_target(target))
            trial['reserve'] = owner.reserve(task_id, object_id=actor.identity.object_id,
                actor_generation=actor.identity.generation, lease_frames=lease_frames)
            trial['status'] = 'waiting_ready'
            atomic_json(output, record)
            if trial['reserve']['status'] not in ('accepted', 'started', 'completed'):
                raise ValueError('journaled_trial_reserve_not_accepted')
            ready = await_outcome(owner, trial, 'completed', 10, observe_environment)
            if ready['receipt']['facts'].get('phase') != 'ready':
                raise ValueError('journaled_trial_ready_not_observed')
            target = choose_commit_target(runtime, binding, trial, task_id, ready['receipt']['facts']['lease_id'], target, observe_environment)
            trial['target_point_id'] = target
            trial['target_xyz'] = list(runtime.approved_target(target))
            trial['commit'] = owner.commit(task_id, target_point_id=target, hold_frames=hold_frames)
            trial['status'] = 'waiting_release'
            atomic_json(output, record)
            done = await_outcome(owner, trial, 'released', max(60,hold_frames/15+30), observe_environment)
            facts = done['receipt']['facts']
            if any(facts.get(key) is not True for key in
                   ('mission_effect_verified', 'physical_home', 'control_released', 'stance_restored')):
                raise ValueError('journaled_trial_effect_or_home_unverified')
            trial['released'] = done
            before = dict(sequence=int(runtime.shared.native_last_sequence), native_commands=len(runtime.command_rows))
            duplicate = owner.commit(task_id, target_point_id=target, hold_frames=hold_frames)
            repeated_reserve = owner.reserve(task_id, object_id=actor.identity.object_id,
                actor_generation=actor.identity.generation, lease_frames=lease_frames)
            after = dict(sequence=int(runtime.shared.native_last_sequence), native_commands=len(runtime.command_rows))
            trial['idempotent_replay'] = dict(before=before, after=after,
                same_commit=duplicate['command_id'] == done['command_id'],
                same_reserve=repeated_reserve['command_id'] == trial['reserve']['command_id'])
            if before != after or not all(trial['idempotent_replay'][k] for k in ('same_commit', 'same_reserve')):
                raise ValueError('journaled_trial_duplicate_dispatched')
            trial['status'] = 'released_requires_independent_review'
            atomic_json(output, record)
        if journal.unresolved(run_id):
            raise ValueError('journaled_trial_unresolved_commands')
        record['status'] = ('journaled_single_task_native_terminal_requires_independent_review' if single_task
            else 'experimental_three_leases_native_terminal_requires_independent_review'
            if budget_recovery_experiment else 'journaled_native_terminal_requires_independent_review')
    except Exception:
        # The original task remains failed. Route one NEW release-only command
        # through the same owner, gateway, sequence allocator and durable ledger.
        # A separately successful release never changes the old uncertain row.
        if owner is not None:
            try:
                current=owner.poll()
                if current is not None and current['status']=='uncertain':
                    prior_path=Path(record['native_report'])
                    saved=prior_path.with_name(prior_path.stem+'-pre-journaled-recovery.json')
                    shutil.copyfile(prior_path,saved)
                    recovery=record['journaled_recovery']=dict(recovery_of_command_id=current['command_id'],
                        original_request_id=current['request_id'],original_receipt=current,
                        original_native_report=str(saved),status='preparing_new_release_only')
                    # Suppress an unrelated direct-driver reconciliation even
                    # when delivery of this journaled recovery becomes unknown.
                    record['explicit_recovery_request']=dict(dispatcher='HostTactical',
                        task_id=current['payload']['task_id'],recovery_of_command_id=current['command_id'])
                    atomic_json(output,record)
                    sent=owner.reconcile_release(current['payload']['task_id'],uncertain_command_id=current['command_id'])
                    recovery['request']=sent
                    atomic_json(output,record)
                    done=await_outcome(owner,recovery,'released',10,observe_environment)
                    recovery['released']=done
                    recovery['original_after']=journal.get_command(run_id,current['request_id'])
                    before=dict(sequence=int(runtime.shared.native_last_sequence),native_commands=len(runtime.command_rows))
                    replay=owner.reconcile_release(current['payload']['task_id'],uncertain_command_id=current['command_id'])
                    after=dict(sequence=int(runtime.shared.native_last_sequence),native_commands=len(runtime.command_rows))
                    recovery['idempotent_replay']=dict(before=before,after=after,same_command=replay['command_id']==done['command_id'])
                    if before!=after or replay['command_id']!=done['command_id']:
                        raise ValueError('journaled_recovery_duplicate_dispatched')
                    recovery['status']='released_original_task_failure_retained_requires_review'
            except Exception as error:
                record['journaled_recovery_error']=str(error) if isinstance(error,(ValueError,TimeoutError)) else type(error).__name__
        raise
    finally:
        if owner is not None:
            record['journaled_owner_snapshot'] = owner.snapshot()
            record['journal_events'] = journal.events(run_id)
            record['journal_unresolved'] = journal.unresolved(run_id)
        if owner_state is not None:owner_state['owner']=owner
        if owns_journal:journal.close()
        atomic_json(output, record)
