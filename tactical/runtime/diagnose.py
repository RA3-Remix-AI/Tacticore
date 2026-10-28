"""One bounded, non-model, paid single-actor calibration; never grants scope."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import shutil
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'integration'))
from live_state import Memory, own_candidates, load_catalog, atomic_json
from session_package import verify_session_package
from host_runtime.contracts import SessionBinding


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def cleanup_runtime(runtime, record, binding, raw_path, output, *, _after_stop=False,_after_return=False):
    """Diagnostic read failure must not prevent the independent safety stop."""
    try:
        current = runtime.poll()
        request_key='failed_return_release_only_request' if _after_return else 'explicit_recovery_request'
        if current['phase'] == 'uncertain' and current['held'] and runtime._actor is not None and request_key not in record and not record.get('host_recovery_owns_cleanup',False):
            suffix='-pre-failed-return-release.json' if _after_return else '-pre-recovery.json'
            prior = raw_path.with_name(raw_path.stem + suffix)
            if not prior.exists():
                with prior.open('xb') as stream:stream.write(raw_path.read_bytes())
            prefix='failed_return_release' if _after_return else 'recovery'
            record[prefix+'_prior_raw'] = str(prior)
            record[prefix+'_of_command_id'] = current['command_id']
            frames = set()
            previous = None
            observations = record.setdefault(prefix+'_wait_observations', [])
            until = time.monotonic() + 8
            while len(frames) < 4 and time.monotonic() < until:
                runtime.poll()
                sample = runtime.observe_actor(binding)
                observations.append(sample)
                idle = (sample['state_id'], sample['state_vtable'], sample['command_source']) == (16, 0xc55130, 2) and sample['stance'] in (0, 2)
                stopped = (sample['state_id'], sample['state_vtable'], sample['stance']) == (94, 0xc551a0, 2) and sample['command_source'] in (1, 2)
                quiet = (idle or stopped) and sample['path'] == 0 and not sample['state_flags'] & 0xffff and sample['team'] == sample['script_team']
                if previous is not None:
                    quiet = quiet and sample['foreign_epoch'] == previous['foreign_epoch'] and math.dist(sample['xyz'][:2], previous['xyz'][:2]) <= 1 and abs(sample['xyz'][2]-previous['xyz'][2]) <= .5
                if quiet:
                    frames.add(sample['frame'])
                else:
                    frames.clear()
                previous = sample
                time.sleep(.06)
            record[prefix+'_quiescent_frames'] = sorted(frames)
            if len(frames) < 4:
                raise ValueError('runtime_recovery_no_quiescent_window')
            snap = runtime.admit(binding)
            actor = runtime._actor
            return_home=record.get('reconcile_return_home_experiment') is True and not _after_return
            sequence=max([snap.last_sequence]+[r['wire']['seq']for r in getattr(runtime,'command_rows',[])])+1
            recovery = dict(protocol='tactical_runtime_v1', command_id=str(uuid.uuid4()), task_id=current['task_id'],
                            lease_id=current['lease_id'], seq=sequence, operation='reconcile_return_home' if return_home else 'reconcile_release',
                            binding_hash=binding.binding_hash, host_id=binding.host_id,
                            actor=dict(object_id=actor.identity.object_id, generation=actor.identity.generation, born_frame=actor.born_frame),
                            payload=dict(task_id=current['task_id'], generation=1, lease_id=current['lease_id'],
                                         expires_frame=snap.game_frame + 120, expires_monotonic_ms=snap.monotonic_ms + 5000,
                                         deadline_frame=runtime.lease_deadline_frame))
            record[request_key] = recovery
            if return_home or _after_return:
                from controlled_fault import seal_owned_intent
                name='failed-return-release-intent.json'if _after_return else'recovery-return-intent.json'
                record[request_key+'_intent']=seal_owned_intent(output,name,recovery,dict(prior_unknown_command_id=current['command_id'],quiescent_frames=sorted(frames)))
            atomic_json(output, record)
            response = runtime.submit(recovery)
            ack_key='failed_return_release_only_ack' if _after_return else 'explicit_recovery_ack'
            terminal_key='failed_return_release_only_terminal' if _after_return else 'explicit_recovery_terminal'
            record[ack_key] = response
            until = time.monotonic() + (35 if return_home else 10)
            while response['status'] != 'rejected' and response['phase'] not in ('released', 'uncertain') and time.monotonic() < until:
                response = runtime.poll()
                time.sleep(.05)
            record[terminal_key] = response
            atomic_json(output, record)
            if return_home and response.get('phase')!='released':
                # A NEW release-only command, after a NEW quiescent window,
                # names the current unknown after the attempt. Never retry Move.
                record['recovery_return_not_completed']=True
                cleanup_runtime(runtime,record,binding,raw_path,output,_after_stop=True,_after_return=True)
                return
    except BaseException as error:
        record['runtime_recovery_unknown'] = type(error).__name__
    # stop() publishes the idempotent native safety-stop flag before reading
    # diagnostics, and retains a failed/unknown result if release is unproven.
    try:
        record['runtime_stop'] = runtime.stop()
        runtime.close()
    except BaseException as error:
        record['runtime_release_unknown'] = type(error).__name__
        # A return may stall *during* stop(). Preserve that failure, then allow
        # one newly admitted release-only reconciliation from fresh quiescence.
        # Never retry an already published reconciliation or a failed read.
        if not _after_stop and 'explicit_recovery_request' not in record and not record.get('host_recovery_owns_cleanup',False):
            try:
                current=runtime.poll()
                recoverable=current['phase']=='uncertain' and current['held'] and runtime._actor is not None
            except BaseException:
                recoverable=False
            if recoverable:
                record['post_stop_recovery_attempted']=True
                atomic_json(output,record)
                cleanup_runtime(runtime,record,binding,raw_path,output,_after_stop=True)


def wait_reserved_yield(runtime, binding, record, output, observe_environment=None, ready_tick=None):
    """One bounded Ready dwell; no Commit, extra unit, pulse replay or grant."""
    start = runtime.observe_actor(binding)['frame']
    wait = record['reserved_yield_wait'] = dict(start_frame=start, frame_budget=300,
        wall_budget_seconds=40, commit_permitted=False, observations=[])
    record['status'] = 'waiting_reserved_native_yield'
    atomic_json(output, record)
    deadline = time.monotonic() + wait['wall_budget_seconds']
    while time.monotonic() < deadline:
        state = runtime.poll()
        sample = runtime.observe_actor(binding)
        rows = wait['observations']
        if not rows or (rows[-1]['frame'], rows[-1]['phase']) != (sample['frame'], state['phase']):
            if len(rows) >= 1024:
                raise ValueError('reserved_yield_observation_capacity_exceeded')
            rows.append(dict(frame=sample['frame'], phase=state['phase'], xyz=sample['xyz']))
        if observe_environment is not None:
            observe_environment('reserved_yield_' + state['phase'])
        if state['phase'] == 'uncertain':
            raise ValueError('reserved_yield_native_result_uncertain')
        if state['phase'] == 'released':
            record['native_terminal'] = state
            record['status'] = 'native_terminal_requires_independent_review'
            atomic_json(output, record)
            return
        if sample['frame'] < start:
            raise ValueError('reserved_yield_frame_regressed')
        # Once return begins, let it reach its own terminal state within the
        # wall budget. A Ready dwell never extends the native lease.
        if state['phase'] == 'ready' and sample['frame'] - start >= wait['frame_budget']:
            raise ValueError('reserved_yield_not_observed_no_commit')
        if ready_tick is not None:
            ready_tick(state,sample)
        time.sleep(.04)
    raise ValueError('reserved_yield_wait_timeout_no_commit')


def wait_source_team_order(runtime,binding,record,output,observe_environment=None):
    start=runtime.observe_actor(binding)['frame']
    record['source_team_order_wait']=dict(start_frame=start,frame_budget=30,wall_budget_seconds=5,goal_commit_permitted=False)
    until=time.monotonic()+5
    while time.monotonic()<until:
        state=runtime.poll();sample=runtime.observe_actor(binding)
        if observe_environment is not None:observe_environment('source_team_ready_observation')
        if state['phase']!='ready':raise ValueError('source_team_order_ready_state_changed')
        if sample['frame']<start:raise ValueError('source_team_order_clock_regressed')
        if sample['frame']-start>=30:
            record['status']='source_team_order_observed_no_commit';atomic_json(output,record);return
        time.sleep(.04)
    raise ValueError('source_team_order_observation_timeout_no_commit')


def run_direct_trial(runtime, actor, binding, record, output, *, home_window, observe_environment=None, yield_abort_experiment=False, home_first_preparation=False, yield_ready_wait=False, ready_tick=None,yield_egress_intercept=False,source_team_order_experiment=False,reconcile_return_experiment=False,controlled_fault_experiment=False):
    if controlled_fault_experiment and not reconcile_return_experiment:raise ValueError('controlled_fault_requires_recovery_experiment')
    if source_team_order_experiment and (not home_first_preparation or yield_abort_experiment or yield_ready_wait or yield_egress_intercept or ready_tick is not None):
        raise ValueError('source_team_order_requires_separate_home_first_no_commit_experiment')
    if yield_ready_wait and not (yield_abort_experiment and home_first_preparation):
        raise ValueError('reserved_yield_requires_explicit_experiment_and_stationary_home')
    if yield_egress_intercept and (not (yield_abort_experiment and home_first_preparation) or yield_ready_wait):
        raise ValueError('egress_intercept_requires_explicit_move_yield_experiment')
    if ready_tick is not None and not (yield_ready_wait or yield_egress_intercept):
        raise ValueError('native_neighbor_requires_reserved_yield_experiment')
    # No actor has been borrowed here. Wait for native squads to vacate a
    # physically demonstrated stop point, without extending any lease.
    from preborrow import choose_target, choose_commit_target
    chosen = choose_target(runtime, binding, record, home_window, observe_environment, home_first=home_first_preparation)
    task, lease = str(uuid.uuid4()), str(uuid.uuid4())
    chosen_xyz = list(runtime.approved_target(chosen)) if chosen is not None else None
    record['preborrow_target_point_id'] = chosen
    sequence = 0
    lease_deadline = None

    def send(operation, **extras):
        nonlocal sequence, lease_deadline
        snap = runtime.admit(binding)
        sequence += 1
        if operation == 'reserve':
            lease_deadline = snap.game_frame + (900 if reconcile_return_experiment else 750)
            extras['deadline_frame'] = lease_deadline
        payload = dict(task_id=task, generation=1, lease_id=lease, expires_frame=min(snap.game_frame + 120, lease_deadline),
                       expires_monotonic_ms=snap.monotonic_ms + 5000, **extras)
        wire = dict(protocol='tactical_runtime_v1', command_id=str(uuid.uuid4()), task_id=task, lease_id=lease, seq=sequence,
                    operation=operation, binding_hash=binding.binding_hash, host_id=binding.host_id,
                    actor=dict(object_id=actor.identity.object_id, generation=actor.identity.generation, born_frame=actor.born_frame), payload=payload)
        if operation=='diagnostic_foreign_move':
            from controlled_fault import seal_owned_intent
            record['controlled_fault_intent']=seal_owned_intent(output,'controlled-fault-intent.json',wire,record['controlled_fault_selection'])
            atomic_json(output,record)
        response = runtime.submit(wire)
        record.setdefault('runtime_commands', []).append(dict(wire=wire, response=response))
        atomic_json(output, record)
        if response.get('status') in ('uncertain', 'rejected'):
            raise ValueError('runtime_calibration_command_refused_or_unknown')

    if observe_environment is not None:
        observe_environment('before_reserve', chosen_xyz)
    send('reserve', purpose='move_hold_return', actor=dict(object_id=actor.identity.object_id, generation=actor.identity.generation))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = runtime.poll()
        if observe_environment is not None:
            observe_environment('native_' + state['phase'], chosen_xyz)
        if state['phase'] == 'ready':
            break
        if state['phase'] in ('uncertain', 'released'):
            raise ValueError('runtime_calibration_did_not_become_ready')
        time.sleep(.04)
    else:
        raise ValueError('runtime_calibration_ready_timeout')
    if source_team_order_experiment:
        wait_source_team_order(runtime,binding,record,output,observe_environment)
        return
    if yield_ready_wait:
        wait_reserved_yield(runtime, binding, record, output, observe_environment, ready_tick)
        return
    # Re-read the native endpoint list after stopping; stale UI coordinates
    # and a point no longer in the native registry are never submitted.
    chosen = choose_commit_target(runtime, binding, record, task, lease, chosen, observe_environment)
    if yield_egress_intercept:
        from egress_intercept import select_egress_target
        chosen=select_egress_target(runtime,binding,record,home_window.actor,chosen)
    chosen_xyz = list(runtime.approved_target(chosen))
    record['target_point_id'] = chosen
    send('commit', purpose='move_hold_return', target_point_id=chosen, hold_frames=675 if reconcile_return_experiment else 300 if yield_abort_experiment else 15)
    record['status'] = 'running_move_hold_return'
    atomic_json(output, record)
    deadline = time.monotonic() + (80 if reconcile_return_experiment else 60)
    fault_started=None;fault_sent=False
    while time.monotonic() < deadline:
        state = runtime.poll()
        if observe_environment is not None:
            observe_environment('native_' + state['phase'], chosen_xyz)
        if state['phase'] == 'released':
            break
        if state['phase'] == 'uncertain':
            raise ValueError('runtime_calibration_native_result_uncertain')
        if controlled_fault_experiment and not fault_sent and state['phase']=='holding':
            if fault_started is None:fault_started=state['game_frame']
            if state['game_frame']>=fault_started+20:
                from controlled_fault import choose_fault_point
                fault_point,selection=choose_fault_point(runtime,binding,state)
                if fault_point is None:
                    if state['game_frame']>=fault_started+75:raise ValueError('controlled_fault_no_current_endpoint_no_injection')
                else:
                    record['controlled_fault_selection']=selection;fault_sent=True
                    send('diagnostic_foreign_move',target_point_id=fault_point)
        if ready_tick is not None:
            ready_tick(state,runtime.observe_actor(binding))
        time.sleep(.04)
    else:
        raise ValueError('runtime_calibration_task_timeout')
    record['native_terminal'] = state
    record['status'] = 'native_terminal_requires_independent_review'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--reconcile-return-home-experiment', action='store_true')
    parser.add_argument('--controlled-native-move', action='store_true')
    parser.add_argument('--journaled-repeat', action='store_true')
    parser.add_argument('--journaled-first-home-experiment',action='store_true')
    parser.add_argument('--runtime-recovery-evidence',type=Path)
    parser.add_argument('--runtime-recovery-sha256')
    parser.add_argument('--journaled-budget-recovery-experiment', action='store_true')
    parser.add_argument('--journaled-rotation-experiment', action='store_true')
    parser.add_argument('--rotation-gap-seconds', type=int,default=0)
    parser.add_argument('--rotation-fresh-paid-actors', action='store_true')
    parser.add_argument('--rotation-epochs', type=int,default=3)
    parser.add_argument('--rotation-hold-frames', type=int,default=15)
    parser.add_argument('--rotation-lease-frames', type=int,default=750)
    parser.add_argument('--yield-abort-experiment', action='store_true')
    parser.add_argument('--ordinary-yield-admission', action='store_true')
    parser.add_argument('--home-first-preparation', action='store_true')
    parser.add_argument('--yield-ready-wait', action='store_true')
    parser.add_argument('--yield-neighbor-flak', action='store_true')
    parser.add_argument('--yield-egress-intercept', action='store_true')
    parser.add_argument('--source-team-order-experiment', action='store_true')
    parser.add_argument('--runtime-evidence', type=Path)
    parser.add_argument('--runtime-sha256')
    args = parser.parse_args()
    if args.journaled_first_home_experiment and (not(args.execute and args.controlled_native_move and args.reconcile_return_home_experiment)
            or args.journaled_repeat or args.journaled_rotation_experiment or args.journaled_budget_recovery_experiment
            or not(args.runtime_recovery_evidence and args.runtime_recovery_sha256)):
        parser.error('--journaled-first-home-experiment requires separate owned --execute --controlled-native-move --reconcile-return-home-experiment and both recovery pins; no repeat/rotation/budget mode')
    if not args.journaled_first_home_experiment and (args.runtime_recovery_evidence or args.runtime_recovery_sha256):
        parser.error('Recovery evidence is only consumed by the explicit owned --journaled-first-home-experiment')
    if args.controlled_native_move and not (args.execute and args.reconcile_return_home_experiment):
        parser.error('--controlled-native-move requires owned --execute --reconcile-return-home-experiment')
    if args.reconcile_return_home_experiment and (not args.execute or args.journaled_repeat or args.yield_abort_experiment or args.home_first_preparation or args.yield_ready_wait or args.yield_neighbor_flak or args.yield_egress_intercept or args.source_team_order_experiment):
        parser.error('--reconcile-return-home-experiment requires a separate owned direct --execute; no ordinary Host/model or other experiments')
    if args.journaled_budget_recovery_experiment and not (args.execute and args.journaled_repeat):
        parser.error('--journaled-budget-recovery-experiment requires owned --execute and --journaled-repeat')
    if args.journaled_rotation_experiment and (not (args.execute and args.journaled_repeat) or args.journaled_budget_recovery_experiment):
        parser.error('--journaled-rotation-experiment requires a separate owned --execute --journaled-repeat without budget exhaustion experiment')
    if not 0<=args.rotation_gap_seconds<=120 or (args.rotation_gap_seconds and not args.journaled_rotation_experiment):
        parser.error('--rotation-gap-seconds requires the explicit owned rotation experiment and a 0..120 second budget')
    if args.rotation_fresh_paid_actors and not args.journaled_rotation_experiment:
        parser.error('--rotation-fresh-paid-actors requires the explicit owned rotation experiment; up to three paid85 actors within the305 total budget')
    if (not 2<=args.rotation_epochs<=4 or not 0<=args.rotation_hold_frames<=675
            or not 150<=args.rotation_lease_frames<=900 or args.rotation_hold_frames+120>args.rotation_lease_frames
            or (args.rotation_fresh_paid_actors and args.rotation_epochs>3)
            or ((args.rotation_epochs,args.rotation_hold_frames,args.rotation_lease_frames)!=(3,15,750)
                and not args.journaled_rotation_experiment)):
        parser.error('Rotation settings require an owned rotation experiment: 2..4 epochs, hold0..675 plus120 setup/return frames within a150..900 lease; at most3 paid actors')
    if args.ordinary_yield_admission and not args.yield_abort_experiment:
        parser.error('--ordinary-yield-admission requires the explicit owned --yield-abort-experiment; it changes only the bootstrap policy marker to flags0')
    if args.source_team_order_experiment and (not args.execute or not args.home_first_preparation
            or args.journaled_repeat or args.yield_abort_experiment or args.yield_ready_wait
            or args.yield_neighbor_flak or args.yield_egress_intercept):
        parser.error('--source-team-order-experiment requires a separate direct --execute --home-first-preparation without yield/neighbor/commit experiments')
    if args.yield_abort_experiment and (not args.execute or args.journaled_repeat):
        parser.error('--yield-abort-experiment requires --execute and a direct owned diagnostic')
    if args.home_first_preparation and (not args.execute or args.journaled_repeat):
        parser.error('--home-first-preparation requires --execute and a direct owned diagnostic')
    if args.yield_ready_wait and not (args.yield_abort_experiment and args.home_first_preparation):
        parser.error('--yield-ready-wait requires --yield-abort-experiment and --home-first-preparation')
    if args.yield_neighbor_flak and not (args.yield_ready_wait or args.yield_egress_intercept):
        parser.error('--yield-neighbor-flak requires --yield-ready-wait or --yield-egress-intercept')
    if args.yield_egress_intercept and (not args.yield_abort_experiment
            or not args.home_first_preparation or args.yield_ready_wait):
        parser.error('--yield-egress-intercept requires the explicit yield/home-first experiment without --yield-ready-wait; a paid neighbor is optional')
    if (args.journaled_repeat or args.journaled_first_home_experiment) != bool(args.runtime_evidence and args.runtime_sha256):
        parser.error('Journaled repeat or first-home experiment requires both --runtime-evidence and --runtime-sha256')
    if not (args.journaled_repeat or args.journaled_first_home_experiment) and (args.runtime_evidence or args.runtime_sha256):
        parser.error('Runtime evidence is only consumed by a journaled experiment')
    client_module = load('tacticore_runtime_original_client', HERE / 'client.py')
    client_module.verify_build()
    if not args.execute:
        print(json.dumps(dict(ready_for_owned_diagnostic=True, commands_dispatched=0, field_granted=False)))
        return 0
    session_path = args.session.resolve()
    original = session_path.read_bytes()
    session = json.loads(original.decode('utf-8-sig'))
    scenario = session.get('scenario', {})
    run = Path(session['run_directory']).resolve()
    output = args.output.resolve()
    if output.parent != run or output.exists() or scenario.get('model_requests_enabled') is not False or scenario.get('trial_kind') != 'tactical_runtime_single_actor_calibration':
        raise ValueError('new_owned_runtime_diagnostic_session_required')
    verify_session_package(session)
    commander = scenario['commander_id']
    binding = SessionBinding(1, session['session_id'], 3, commander, session['pid'], session['start_time'], str(uuid.uuid4()),
                             hashlib.sha256(Path(session['game']).read_bytes()).hexdigest(), session['mod_sha256'])
    capabilities = None
    if args.journaled_repeat or args.journaled_first_home_experiment:
        from journaled_trial import verified_catalog
        capabilities = verified_catalog(binding, args.runtime_evidence, args.runtime_sha256,
            recovery_source=args.runtime_recovery_evidence,recovery_digest=args.runtime_recovery_sha256)
    record = dict(schema_version=1, protocol='single_actor_runtime_calibration_v1', session_id=session['session_id'],
                  binding=binding.public(), model_requests=0, native_scope='paid_conscript_move_hold_return_max120',
                  status='preparing', production_commands=[], field_source_granted=False)
    if args.journaled_repeat:
        record.update(protocol='journaled_single_actor_runtime_trial_v1', runtime_evidence=str(args.runtime_evidence.resolve()), runtime_evidence_sha256=args.runtime_sha256)
    if args.reconcile_return_home_experiment:
        record.update(protocol='experimental_first_home_recovery_trial_v1',reconcile_return_home_experiment=True,
            requested_hold_frames=675,requested_lease_frames=900,ordinary_execution_granted=False,
            experiment_outcome='original_task_failure_retained_new_first_home_move_requires_independent_review')
    if args.controlled_native_move:
        record.update(controlled_native_move_experiment=True,fault_source='controlled_diagnostic_native_move',
            natural_AI_interference_claimed=False)
    if args.journaled_first_home_experiment:
        record.update(protocol='journaled_first_home_recovery_trial_v1',journaled_first_home_experiment=True,
            runtime_evidence=str(args.runtime_evidence.resolve()),runtime_evidence_sha256=args.runtime_sha256,
            runtime_recovery_evidence=str(args.runtime_recovery_evidence.resolve()),runtime_recovery_sha256=args.runtime_recovery_sha256)
    if args.yield_abort_experiment:
        record.update(protocol='experimental_native_yield_abort_trial_v1', yield_abort_experiment=True,
                      requested_hold_frames=300, ordinary_execution_granted=False,
                      experiment_outcome='requires_fresh_native_yield_source_and_state26_proof')
        record['native_yield_policy']='ordinary_proven_flak_source_only' if args.ordinary_yield_admission else 'explicit_diagnostic_source_families'
    if args.yield_ready_wait:
        record.update(experiment_mode='reserve_only_stationary_ready_wait', requested_hold_frames=0,
                      requested_ready_wait_frames=300)
    if args.yield_neighbor_flak:
        record['experiment_mode']='reserve_only_ready_wait_with_one_paid_native_flak'
    if args.yield_egress_intercept:
        record['experiment_mode']='native_egress_intercept_move_hold_with_one_paid_native_flak'
    atomic_json(output, record)
    producer = runtime = memory = None
    rotation_state=None
    started = time.monotonic()
    try:
        artifact_dir = run / 'runtime-build'
        artifact_dir.mkdir()
        manifest, _ = client_module.verify_build()
        artifacts = []
        for row in manifest['inputs'] + manifest['outputs']:
            source = HERE / row['file'] if row in manifest['inputs'] else HERE / 'bin' / row['file']
            target = artifact_dir / row['file']
            shutil.copyfile(source, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('runtime_artifact_archive_hash_changed')
            artifacts.append(dict(file=target.name, sha256=row['sha256']))
        for name in ('client.py', 'layout.py', 'diagnose.py', 'journaled_trial.py', 'environment.py', 'preborrow.py',
                     'native_neighbor.py','egress_intercept.py','team_roster.py','rotation_trial.py','controlled_fault.py','host_recovery_trial.py'):
            shutil.copyfile(HERE / name, artifact_dir / name)
            artifacts.append(dict(file=name, sha256=hashlib.sha256((artifact_dir / name).read_bytes()).hexdigest()))
        support=artifact_dir/'support';support.mkdir()
        for source in (ROOT/'tactical/terrain/native_path.py',ROOT/'production/persistent/client.py'):
            name='native_path.py' if source.parent.name=='terrain' else 'production_client.py'
            target=support/name;shutil.copyfile(source,target)
            artifacts.append(dict(file='support/'+name,source=source.relative_to(ROOT).as_posix(),
                                  sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        if args.journaled_repeat or args.journaled_first_home_experiment:
            host_archive=support/'host_runtime';host_archive.mkdir()
            for source in sorted((ROOT/'integration/host_runtime').glob('*.py')):
                target=host_archive/source.name;shutil.copyfile(source,target)
                artifacts.append(dict(file='support/host_runtime/'+source.name,
                    source=source.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        atomic_json(artifact_dir / 'artifacts.json', dict(build_manifest=manifest, artifacts=artifacts))
        record['runtime_artifacts'] = str(artifact_dir / 'artifacts.json')
        record['runtime_artifacts_sha256'] = hashlib.sha256((artifact_dir / 'artifacts.json').read_bytes()).hexdigest()
        atomic_json(output, record)
        memory = Memory(session['pid'], session)
        factory = None
        while time.monotonic() - started < 120:
            if session_path.read_bytes() != original:
                raise ValueError('runtime_calibration_session_changed')
            if memory.u32(memory.u32(0xcd8ce4) + 0x15c):
                raise ValueError('runtime_calibration_game_paused')
            snapshot = own_candidates(memory, 3, load_catalog())
            factories = [row for row in snapshot['candidates'] if row['type_hash'] == '0x80d4ea1e' and memory.f32(memory.u32(int(row['address'], 0) + 0x33c) + 4) > 0]
            if len(factories) == 1:
                factory = factories[0]
                break
            time.sleep(.25)
        if factory is None:
            raise ValueError('runtime_calibration_no_unique_barracks')
        natural = run / 'natural-production.json'
        if natural.exists():
            raise ValueError('runtime_calibration_requires_unobserved_new_session')
        # The original observer allows ten seconds to attach, then thirty
        # seconds of sampling plus five seconds of cooperative cleanup. A
        # parent timeout must never kill it while it can still own a hook.
        observer = subprocess.Popen([str(ROOT / 'production/bin/observe_build.exe'), str(session['pid']), '30'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        record['observer_pid'] = observer.pid
        atomic_json(output, record)
        observed, observer_error = observer.communicate(timeout=50)
        if observer.returncode:
            raise ValueError('runtime_calibration_natural_observer_refused:' + observer_error.strip())
        natural.write_text(observed, encoding='utf-8')
        snapshot_path = output.with_name(output.stem + '-owned.json')
        atomic_json(snapshot_path, dict(snapshot, pid=session['pid'], sha256=binding.game_sha256))
        original_producer = load('tacticore_runtime_original_production', ROOT / 'production/persistent/client.py')
        producer = original_producer.ProductionExecutor(session_path, snapshot_path, factory['address'], commander,
                                                       natural, total_budget=305, reserve_floor=1000, min_interval_frames=150)
        producer.start()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            status = producer.status()
            if status.get('native_phase') == 1:
                break
            if status.get('native_error'):
                raise ValueError('runtime_calibration_producer_start_refused')
            time.sleep(.05)
        else:
            raise ValueError('runtime_calibration_producer_start_timeout')
        frame = memory.u32(memory.u32(0xcd8ce4) + 0x50)
        command = dict(session_id=session['session_id'], player_id=3, commander_id=commander, command_id=str(uuid.uuid4()),
                       task_id=str(uuid.uuid4()), seq=1, unit='conscript', budget=85, reserve=1000, expires_frame=frame + 450)
        receipt = producer.submit(command)
        record['production_commands'].append(dict(command=command, receipt=receipt))
        record['status'] = 'waiting_paid_birth'
        atomic_json(output, record)
        if receipt.get('accepted') is not True:
            raise ValueError('runtime_calibration_production_not_accepted')
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            status = producer.status()
            record['production_status'] = status
            born = next((row for row in status.get('ledger', []) if row.get('command_id') == command['command_id']), None)
            if born and born.get('completed') and born.get('paid_verified') and born.get('paid') == 85 and born.get('created'):
                break
            if born and born.get('status') in ('rejected', 'failed', 'unknown'):
                raise ValueError('runtime_calibration_birth_failed_or_unknown')
            time.sleep(.1)
        else:
            raise ValueError('runtime_calibration_birth_timeout')
        raw_path = output.with_name(output.stem + '-native.json')
        runtime = client_module.NativeRuntimeClient(session_path, binding, producer, command['command_id'], raw_path,
                                                    diagnostic=not args.journaled_repeat,
                                                    yield_abort_experiment=args.yield_abort_experiment and not args.ordinary_yield_admission,
                                                    reconcile_return_experiment=args.reconcile_return_home_experiment,
                                                    controlled_fault_experiment=args.controlled_native_move)
        actor = runtime.attach(capabilities=capabilities)
        record['native_report'] = str(raw_path)
        record['status'] = 'waiting_native_endpoint'
        atomic_json(output, record)
        from environment import OwnEnvironmentRecorder
        from preborrow import HomeWindow
        environment = OwnEnvironmentRecorder(memory, binding.player_id, load_catalog(), actor.identity.object_id, record)
        observe_context=environment.capture
        if args.source_team_order_experiment or args.yield_ready_wait or args.yield_egress_intercept:
            from team_roster import TeamRosterRecorder
            team_context=TeamRosterRecorder(memory,runtime,binding,client_module.layout.Actor.from_buffer_copy(runtime.actor_bytes),record)
            def observe_context(stage,target=None):
                environment.capture(stage,target)
                team_context.capture(stage)
        home_window = HomeWindow(memory, binding.player_id, client_module.layout.Actor.from_buffer_copy(runtime.actor_bytes))
        ready_tick=None
        if args.yield_neighbor_flak:
            from native_neighbor import PaidNativeNeighbor
            ready_tick=PaidNativeNeighbor(producer,memory,binding,record,output,
                eligible_phase='holding' if args.yield_egress_intercept else 'ready')
        if args.journaled_first_home_experiment:
            from host_recovery_trial import run_trial
            run_trial(runtime,actor,binding,capabilities,record,output,home_window=home_window,observe_environment=environment.capture)
        elif args.journaled_rotation_experiment:
            from rotation_trial import run_rotation_trials
            rotation_state={}
            run_rotation_trials(client_module,runtime,actor,binding,capabilities,record,output,
                memory=memory,session_path=session_path,state=rotation_state,observe_environment=environment.capture,
                gap_seconds=args.rotation_gap_seconds,fresh_paid_actors=args.rotation_fresh_paid_actors,
                epochs=args.rotation_epochs,hold_frames=args.rotation_hold_frames,lease_frames=args.rotation_lease_frames)
        elif args.journaled_repeat:
            from journaled_trial import run_trials
            run_trials(runtime, actor, binding, capabilities, record, output, home_window=home_window,
                observe_environment=environment.capture,budget_recovery_experiment=args.journaled_budget_recovery_experiment)
        else:
            run_direct_trial(runtime, actor, binding, record, output, home_window=home_window, observe_environment=observe_context,
                             yield_abort_experiment=args.yield_abort_experiment, home_first_preparation=args.home_first_preparation,
                             yield_ready_wait=args.yield_ready_wait,ready_tick=ready_tick,
                             yield_egress_intercept=args.yield_egress_intercept,source_team_order_experiment=args.source_team_order_experiment,
                             reconcile_return_experiment=args.reconcile_return_home_experiment,
                             controlled_fault_experiment=args.controlled_native_move)
    except BaseException as error:
        record['status'] = 'failed_or_unknown'
        record['reason_code'] = str(error) if isinstance(error, (ValueError, TimeoutError)) else type(error).__name__
        record['local_exception'] = traceback.format_exc()
    finally:
        if rotation_state:
            runtime,binding,raw_path=(rotation_state[k] for k in ('runtime','binding','raw_path'))
        if runtime is not None:
            if rotation_state and rotation_state.get('closed_verified'):
                record['runtime_stop']=rotation_state['terminal']
                record['rotation_cleanup']='all_admitted_channels_closed_and_independently_captured'
            else:cleanup_runtime(runtime, record, binding, raw_path, output)
        if producer is not None:
            try:record['production_stopped'] = producer.stop()
            except BaseException as error:record['production_stop_unknown'] = type(error).__name__
        if memory is not None:
            memory.close()
        record['elapsed_wall_seconds'] = time.monotonic() - started
        atomic_json(output, record)
    print(json.dumps(dict(status=record['status'], report=str(output), field_granted=False)))
    return 0 if record['status'] in ('native_terminal_requires_independent_review', 'journaled_native_terminal_requires_independent_review',
        'experimental_three_leases_native_terminal_requires_independent_review','journaled_rotation_native_terminal_requires_independent_review',
        'journaled_first_home_recovery_requires_independent_review') else 1


if __name__ == '__main__':
    raise SystemExit(main())
