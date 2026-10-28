"""Read-only review of one actual host run; never loads credentials or game APIs."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

SAFE_FILES = (
    'session.json', 'attempt-scope.json', 'natural-production.json', 'persistent-production.jsonl',
    'persistent-production-status.json', 'battle-host/host-events.jsonl',
    'battle-host/plans.jsonl', 'battle-host/host-status.json',
    'battle-host/agent-state.json', 'battle-host/jobs.json',
    'battle-host/match-state.json', 'battle-host/result-native-state.json',
    'battle-host/dispatch-ledger.json',
)

def read_sources(run):
    sources, hashes, warnings = {}, {}, []
    for name in SAFE_FILES:
        path = run / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        hashes[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        try:
            text = raw.decode('utf-8-sig')
            if name.endswith('.jsonl'):
                rows = []
                for i, line in enumerate(text.splitlines()):
                    if not line.strip():
                        continue
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        warnings.append(f'{name}: ignored incomplete or invalid line {i+1}')
                sources[name] = rows
            else:
                sources[name] = json.loads(text)
        except (ValueError, UnicodeError):
            warnings.append(f'{name}: concurrent/incomplete JSON; missing for this review')
    return sources, hashes, warnings

def fully_proven(row):
    return (row.get('status') == 'completed' and row.get('accepted') is True
            and row.get('started') is True and row.get('completed') is True
            and row.get('paid_verified') is True and row.get('created') is True
            and row.get('completion_observed') is True and row.get('queue_preserved') is True
            and type(row.get('queue_id')) is int and row['queue_id'] > 0
            and type(row.get('object_id')) is int and row['object_id'] > 0
            and type(row.get('cost')) is int and row['cost'] > 0
            and row.get('paid') == row['cost'] and row.get('live_samples', 0) > 0
            and row.get('payment_error') == 0)

def intent(strategy):
    return {k: strategy.get(k) for k in ('stance', 'production_focus', 'economy_policy',
            'tech_policy', 'budget', 'objective_region')}


def task_outcomes(feedback):
    """Count ordered observations, preserving raw reports and ambiguous outcomes."""
    started, reported_completed, prestart_completed, prestart_failed = set(), set(), set(), set()
    terminals = {}
    for row in feedback:
        task, state = row['task_id'], row.get('status')
        if state == 'completed':
            reported_completed.add(task)
        if state == 'started':
            started.add(task)
        elif state in ('completed', 'failed', 'cancelled'):
            if task in started:
                terminals.setdefault(task, set()).add(state)
            elif state == 'completed':
                prestart_completed.add(task)
            elif state == 'failed':
                prestart_failed.add(task)
    conflicts = {task for task, states in terminals.items() if len(states) > 1}
    # A later start cannot retroactively certify an earlier completion. Likewise,
    # conflicting terminal feedback is neither a completed nor a failed outcome.
    completed = {task for task, states in terminals.items() if states == {'completed'}} - prestart_completed
    failed = {task for task, states in terminals.items() if states == {'failed'}}
    cancelled = {task for task, states in terminals.items() if states == {'cancelled'}}
    return dict(started=started, reported_completed=reported_completed, completed=completed,
                failed=failed, cancelled=cancelled, conflicts=conflicts,
                prestart_completed=prestart_completed, prestart_failed=prestart_failed,
                pending=started-set(terminals))


def review(sources, hashes=None, warnings=None):
    warnings = list(warnings or [])
    session = sources.get('session.json', {})
    status = sources.get('battle-host/host-status.json', {})
    agent = sources.get('battle-host/agent-state.json', {})
    plans = sources.get('battle-host/plans.jsonl', [])
    events = sources.get('battle-host/host-events.jsonl', [])
    binding = dict(session_id=session.get('session_id'),
                   player_id=status.get('binding', {}).get('player_id'),
                   commander_id=status.get('binding', {}).get('commander_id'))
    for name, rows in [('plans', plans), ('host-events', events)]:
        for row in rows:
            if any(row.get(k) != v for k, v in binding.items()):
                raise ValueError(f'{name}: event binding mismatch')
    if status and status.get('session_id') != session.get('session_id'):
        raise ValueError('host/session mismatch')
    if agent and any(agent.get('binding', {}).get(k) != v for k, v in binding.items()):
        raise ValueError('agent/session mismatch')
    metrics = status.get('metrics', {})
    accepted = metrics.get('accepted')
    rejected = metrics.get('rejected')
    denominator = (accepted + rejected) if accepted is not None and rejected is not None else 0
    times = [p['game_time_seconds'] for p in plans if isinstance(p.get('game_time_seconds'), (int, float))]
    retained = [x['accepted_strategy'] for x in agent.get('conversation_tail', []) if 'accepted_strategy' in x]
    retained_changes = sum(intent(a) != intent(b) for a, b in zip(retained, retained[1:]))
    # Engine counts initial activation as a plan change; disclose raw and corrected separately.
    raw_changes = metrics.get('plan_changes')
    transitions = max(0, raw_changes - 1) if type(raw_changes) is int else None
    observations = {}
    for task in agent.get('task_history', []) + agent.get('active_goals', []):
        observations[task['task_id']] = task
    task_statuses = Counter(t.get('status', 'unknown') for t in observations.values())
    feedback = [x for x in events if x.get('kind') == 'task_feedback']
    outcomes = task_outcomes(feedback)
    started_ids, completed_ids, failed_ids = (outcomes[k] for k in ('started', 'completed', 'failed'))
    if outcomes['prestart_completed']:
        warnings.append('Completion feedback without an earlier observed start is not a known started outcome.')
    if outcomes['conflicts']:
        warnings.append('Conflicting terminal task feedback is excluded from completed/failed outcomes.')
    pstatus = sources.get('persistent-production-status.json')
    audit = sources.get('persistent-production.jsonl')
    production = None
    if pstatus is not None or audit is not None:
        if pstatus is not None and any(pstatus.get(k) != v for k, v in binding.items()):
            raise ValueError('production/session mismatch')
        preflights = [x for x in (audit or []) if x.get('event') == 'attach_preflight']
        bound = any(x.get('session_id') == binding['session_id'] and x.get('commander_id') == binding['commander_id']
                    and x.get('package_sha256') == session.get('mod_sha256') for x in preflights)
        receipts = [x for x in (audit or []) if x.get('event') == 'execution_feedback']
        ledger = (pstatus or {}).get('ledger', [])
        commands = {}
        for row in audit or []:
            if row.get('event') == 'command_dispatch_pending':
                command = row.get('command', {})
                if any(command.get(k) != v for k, v in binding.items()):
                    raise ValueError('production command/session mismatch')
                commands[(command.get('command_id'), command.get('seq'))] = command
        proven = {}
        latest_receipts = {}
        for row in receipts + ledger:
            latest_receipts[(row.get('command_id'), row.get('seq'))] = row
            command = commands.get((row.get('command_id'), row.get('seq')))
            if fully_proven(row) and command and command.get('task_id') == row.get('task_id') and command.get('unit') == row.get('unit'):
                proven[(row.get('command_id'), row.get('seq'))] = row
        if proven and not bound:
            warnings.append('Production completion rows lack same-session attach preflight; not verified.')
        verified = list(proven.values()) if bound else []
        if len({x['object_id'] for x in verified}) != len(verified):
            raise ValueError('production object reused across commands')
        production = {'same_session_package_preflight': bound,
            'commands_dispatched_in_audit': len(commands),
            'native_spent_committed': (pstatus or {}).get('spent_committed'),
            'latest_command_statuses': dict(Counter(row.get('status','unknown') for key,row in latest_receipts.items() if key in commands)),
            'observed_paid_including_pending': sum(row.get('paid',0) for key,row in latest_receipts.items() if key in commands and type(row.get('paid')) is int),
            'fully_verified_units': len(verified),
            'verified_paid_credits': sum(x['paid'] for x in verified),
            'units': [{k: x.get(k) for k in ('task_id','command_id','seq','unit','queue_id','object_id','cost','paid','enqueue_frame','completion_frame')} for x in verified],
            'host_completed_tasks_with_production_proof': sorted(completed_ids & {x.get('task_id') for x in verified})}
    native = sources.get('battle-host/result-native-state.json', sources.get('battle-host/match-state.json', {}))
    candidates = [{k: x.get(k) for k in ('native_index', 'victory_frame', 'defeat_frame', 'quit_frame', 'outcome_evidence')}
                  for x in native.get('result_records', []) if x.get('victory_frame') or x.get('defeat_frame')]
    natural = sources.get('natural-production.json')
    first_request = next((p.get('game_time_seconds') for p in plans if p.get('event') == 'request'), None)
    entered_match = next((e.get('first_game_time_seconds') for e in events if e.get('kind') == 'entered_match'), None)
    trial_kind = 'actual_host_integration_trial_unclassified_start'
    if session.get('session_id') == '31ba9442-8c11-4ffe-bd10-be5e170c1c50':
        trial_kind = 'midgame_host_integration_trial'
    elif session.get('scenario', {}).get('host_prearmed') is True and isinstance(first_request, (int, float)) and first_request <= 2 and isinstance(entered_match, (int, float)) and entered_match <= 2:
        trial_kind = 'prearmed_whole_match_integration_candidate'
    return {'schema_version': 1, 'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_kind': 'live_game_host_artifact_review', 'binding': binding,
        'trial_kind': trial_kind, 'attempt_scope': sources.get('attempt-scope.json'),
        'opponent': session.get('scenario', {}).get('opponent'),
        'whole_match_acceptance_passed': False, 'personality_comparison_passed': False,
        'result_finalized': False,
        'host': {k: status.get(k) for k in ('host_pid','state','reason_code','execution')},
        'model': {'requests': metrics.get('requests'), 'accepted': accepted, 'rejected': rejected,
                  'invalid_policy_rate': rejected / denominator if denominator else None,
                  'timeouts': metrics.get('timeouts'), 'adapter_errors': metrics.get('adapter_errors'),
                  'held_decisions': sum(x.get('status') == 'held' for x in plans),
                  'transport': status.get('transport')},
        'strategy': {'engine_plan_changes_including_initial': raw_changes,
                     'intent_transitions_excluding_initial': transitions,
                     'retained_full_intent_observations': len(retained),
                     'retained_full_intent_transitions': retained_changes if retained else None,
                     'full_intent_history_complete': len(retained) == accepted if type(accepted) is int else False,
                     'first_host_match_game_seconds': entered_match,
                     'first_model_request_game_seconds': first_request,
                     'first_logged_game_seconds': min(times) if times else None,
                     'last_logged_game_seconds': max(times) if times else None,
                     'intent_transitions_per_observed_game_minute': transitions / ((max(times)-min(times))/60) if transitions is not None and times and max(times)>min(times) else None},
        'context': {'memory_metrics': agent.get('metrics'), 'compressed_history': agent.get('compressed_history'),
                    'retained_full_intents': retained,
                    'per_request_input_bytes': None,
                    'compaction_counter_semantics': 'One per older event folded into summary; not number of batch compression passes.',
                    'note': 'Only retained maxima and counters are logged; no per-request byte series or compression ratio can be reconstructed.'},
        'tasks': {'host_counters': status.get('task_counters'),
                  'unique_retained_tasks_by_status': dict(task_statuses),
                  'observed_started': len(started_ids), 'host_reported_completed': len(outcomes['reported_completed']),
                  'observed_started_completed': len(completed_ids),
                  'prestart_completions_not_completed_tasks': len(outcomes['prestart_completed']),
                  'started_without_terminal_feedback': len(outcomes['pending']),
                  'started_with_conflicting_terminal_feedback': len(outcomes['conflicts']),
                  'observed_started_cancelled': len(outcomes['cancelled']),
                  'observed_started_failed': len(failed_ids), 'prestart_rejections_not_failed_tasks': len(outcomes['prestart_failed']),
                  'completion_rate_known_started_outcomes': len(completed_ids) / (len(completed_ids) + len(failed_ids)) if completed_ids or failed_ids else None,
                  'note': 'Planned, unavailable, cancelled and pending tasks are not failures; host completion requires independent production correlation.'},
        'production': production,
        'natural_production': {'native_calls': natural.get('total_build_calls'), 'mutates_arguments': natural.get('mutates_arguments'),
                               'note': 'Passive native baseline observation is not model-dispatched spending or completion evidence.'} if natural else None,
        'outcome': {'native_candidates': candidates, 'native_verified_flag': native.get('match_ended_verified'),
                    'gui_confirmation': None, 'note': 'Await root native/GUI outcome evidence before finalizing. Host stopped/fault does not mean match ended.'},
        'sources': hashes or {}, 'warnings': warnings}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    allowed = Path(__file__).resolve().parent
    output = args.output.resolve()
    if not output.is_relative_to(allowed):
        raise ValueError('All review output must remain inside benchmark/')
    sources, hashes, warnings = read_sources(args.run.resolve())
    result = review(sources, hashes, warnings)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('trial_kind','host','model','strategy','production','outcome')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
