"""Offline source attribution of bounded assertions; no game, credentials or model IO.

This validates correlation and provenance declarations, not the truth of a game
observation. Even recorded assertions with file hashes remain externally unverified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

ORIGINS = ('native', 'script', 'model')
PROVENANCE = ('synthetic', 'recorded_assertions')
BINDING = {'run_id', 'session_id', 'player_id', 'commander_id', 'profile_revision', 'effective_hash'}
CONDITIONS = {'experiment_id', 'map_id', 'faction', 'opponent_id', 'difficulty',
              'game_sha256', 'mod_sha256', 'window_seconds', 'seed_control', 'seed'}
EVENT = {'event_id', 'seq', 'game_seconds', 'binding', 'origin', 'kind', 'data', 'evidence_sha256'}
DATA = {
    'configuration_applied': set(),
    'model_consumed': {'call_id', 'transport'},
    'decision': {'decision_id', 'input_sha256', 'intent_sha256', 'style'},
    'execution_started': {'task_id', 'decision_id'},
    'spend': {'task_id', 'command_id', 'credits'},
    'effect': {'task_id', 'effect_id', 'effect_kind', 'amount'},
    'returned_home': {'task_id'},
    'control_released': {'task_id'},
    'task_result': {'task_id', 'status'},
    'settlement': {'outcome', 'reason'},
}
MAX_BYTES, MAX_EVENTS = 8 * 1024 * 1024, 20000
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')


class AttributionError(ValueError):
    """A fixed error code, never raw event or external exception text."""


def require(condition, code):
    if not condition:
        raise AttributionError(code)


def fields(value, expected, code):
    require(type(value) is dict and set(value) == expected, code)


def ident(value):
    require(type(value) is str and _ID.fullmatch(value) is not None, 'invalid_identifier')
    return value


def sha(value):
    require(type(value) is str and _SHA.fullmatch(value) is not None, 'invalid_sha256')
    return value


def number(value, *, positive=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (0 < value <= 1e12 if positive else 0 <= value <= 1e12), 'invalid_number')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def validate_binding(binding):
    fields(binding, BINDING, 'binding_fields')
    for key in ('run_id', 'session_id', 'commander_id'):
        ident(binding[key])
    require(type(binding['player_id']) is int and 0 <= binding['player_id'] <= 15, 'player_id')
    require(type(binding['profile_revision']) is int and binding['profile_revision'] >= 1, 'profile_revision')
    sha(binding['effective_hash'])


def validate_conditions(conditions):
    fields(conditions, CONDITIONS, 'condition_fields')
    for key in ('experiment_id', 'map_id', 'faction', 'opponent_id', 'difficulty'):
        ident(conditions[key])
    for key in ('game_sha256', 'mod_sha256'):
        sha(conditions[key])
    number(conditions['window_seconds'], positive=True)
    require(conditions['seed_control'] in ('controlled', 'uncontrolled'), 'seed_control')
    if conditions['seed_control'] == 'controlled':
        require(type(conditions['seed']) is int and 0 <= conditions['seed'] < 2**64, 'seed')
    else:
        require(conditions['seed'] is None, 'uncontrolled_seed_must_be_null')


def _validate_data(kind, data):
    require(type(kind) is str and kind in DATA, 'event_kind')
    fields(data, DATA[kind], 'event_data_fields')
    for key in ('task_id', 'command_id', 'effect_id', 'style'):
        if key in data:
            ident(data[key])
    if 'decision_id' in data and data['decision_id'] is not None:
        ident(data['decision_id'])
    if kind == 'decision':
        ident(data['decision_id'])
        sha(data['input_sha256']); sha(data['intent_sha256'])
    if kind == 'model_consumed':
        ident(data['call_id'])
        require(data['transport'] in ('provider_transport', 'injected_transport', 'unknown'), 'transport')
    if kind == 'spend':
        number(data['credits'], positive=True)
    if kind == 'effect':
        require(data['effect_kind'] in ('damage', 'production', 'economic_disruption', 'coordination'), 'effect_kind')
        number(data['amount'])
    if kind == 'task_result':
        require(data['status'] in ('completed', 'failed', 'cancelled', 'unknown'), 'task_status')
    if kind == 'settlement':
        require(data['outcome'] in ('win', 'loss', 'draw', 'unknown'), 'outcome')
        require(data['reason'] in ('natural', 'user_stop', 'fault', 'unknown'), 'settlement_reason')


def validate_document(document):
    fields(document, {'schema_version', 'binding', 'conditions', 'provenance', 'events'}, 'document_fields')
    require(type(document['schema_version']) is int and document['schema_version'] == 1, 'schema_version')
    validate_binding(document['binding']); validate_conditions(document['conditions'])
    require(document['provenance'] in PROVENANCE, 'provenance')
    rows = document['events']
    require(type(rows) is list and len(rows) <= MAX_EVENTS, 'event_limit')
    ids, last_seq, last_time = set(), 0, -1
    for row in rows:
        fields(row, EVENT, 'event_fields')
        ident(row['event_id'])
        require(row['event_id'] not in ids, 'duplicate_event')
        ids.add(row['event_id'])
        require(type(row['seq']) is int and row['seq'] > last_seq, 'event_sequence')
        last_seq = row['seq']
        current = number(row['game_seconds'])
        require(current >= last_time and current <= document['conditions']['window_seconds'], 'event_clock')
        last_time = current
        validate_binding(row['binding'])
        require(row['binding'] == document['binding'], 'event_binding_mismatch')
        require(row['origin'] in ORIGINS, 'event_origin')
        _validate_data(row['kind'], row['data'])
        if document['provenance'] == 'recorded_assertions' or row['evidence_sha256'] is not None:
            sha(row['evidence_sha256'])
    return document


def summarize(document):
    """Return only whitelist metrics; raw inputs or provider payloads never echo."""
    validate_document(document)
    counts = {origin: Counter() for origin in ORIGINS}
    effect_amounts = {origin: Counter() for origin in ORIGINS}
    spent = Counter()
    decisions, tasks, command_ids, effect_ids, settlements, calls = {}, {}, set(), set(), {}, set()
    for row in document['events']:
        origin, kind, data = row['origin'], row['kind'], row['data']
        counts[origin][kind] += 1
        if kind == 'model_consumed':
            require(origin == 'model' and data['call_id'] not in calls, 'model_call_origin_or_duplicate')
            calls.add(data['call_id'])
        elif kind == 'decision':
            key = data['decision_id']
            require(key not in decisions, 'duplicate_decision')
            decisions[key] = origin
        elif kind == 'execution_started':
            key, decision = data['task_id'], data['decision_id']
            require(key not in tasks, 'duplicate_or_reused_task')
            if decision is None:
                require(origin != 'model', 'model_execution_requires_decision')
            else:
                require(decisions.get(decision) == origin, 'decision_origin_or_order_mismatch')
            tasks[key] = dict(origin=origin, terminals=set(), home=False, released=False,
                              effect=False, correlated_at_completion=False)
        elif kind in ('spend', 'effect', 'returned_home', 'control_released', 'task_result'):
            task = tasks.get(data['task_id'])
            require(task is not None and task['origin'] == origin, 'task_origin_or_start_mismatch')
            if kind == 'spend':
                require(data['command_id'] not in command_ids, 'duplicate_spend_command')
                command_ids.add(data['command_id']); spent[origin] += data['credits']
            elif kind == 'effect':
                require(data['effect_id'] not in effect_ids, 'duplicate_effect')
                effect_ids.add(data['effect_id']); effect_amounts[origin][data['effect_kind']] += data['amount']
                task['effect'] |= data['amount'] > 0
            elif kind == 'returned_home':
                require(not task['home'], 'duplicate_home_assertion')
                task['home'] = True
            elif kind == 'control_released':
                require(not task['released'], 'duplicate_release_assertion')
                task['released'] = True
            else:
                state = data['status']
                require(state not in task['terminals'], 'duplicate_terminal_assertion')
                if state == 'completed':
                    task['correlated_at_completion'] = task['effect'] and task['home'] and task['released']
                task['terminals'].add(state)
        elif kind == 'settlement':
            require(origin not in settlements, 'duplicate_settlement')
            settlements[origin] = dict(data)
    groups = {}
    for origin in ORIGINS:
        own = [task for task in tasks.values() if task['origin'] == origin]
        states = Counter(next(iter(t['terminals'])) if len(t['terminals']) == 1 else
                         ('conflicting' if t['terminals'] else 'pending') for t in own)
        denominator = states['completed'] + states['failed']
        groups[origin] = dict(
            configuration_assertions=counts[origin]['configuration_applied'],
            model_response_assertions=counts[origin]['model_consumed'],
            decision_assertions=counts[origin]['decision'], started_tasks=len(own),
            spend_commands=counts[origin]['spend'], reported_spend_credits=spent[origin] if counts[origin]['spend'] else None,
            effect_assertions=counts[origin]['effect'],
            reported_effect_amounts={kind: effect_amounts[origin][kind] if kind in effect_amounts[origin] else None
                                     for kind in ('damage', 'production', 'economic_disruption', 'coordination')},
            home_assertions=counts[origin]['returned_home'], release_assertions=counts[origin]['control_released'],
            task_outcomes={state: states[state] for state in ('completed', 'failed', 'cancelled', 'unknown', 'conflicting', 'pending')},
            completion_rate_known_started_outcomes=states['completed'] / denominator if denominator else None,
            fully_correlated_completed_assertions=sum(t['terminals'] == {'completed'} and t['correlated_at_completion'] for t in own),
            settlement=settlements.get(origin),
            coverage={layer: 'provided' if counts[origin][kind] else 'missing' for layer, kind in (
                ('configuration', 'configuration_applied'), ('model_consumption', 'model_consumed'),
                ('decision', 'decision'), ('execution', 'execution_started'),
                ('spend', 'spend'), ('effect', 'effect'), ('physical_home', 'returned_home'),
                ('control_release', 'control_released'), ('settlement', 'settlement'))})
    return dict(schema_version=1, kind='contribution_assertion_review', binding=document['binding'],
                conditions=document['conditions'], provenance=document['provenance'],
                input_sha256=hashlib.sha256(canonical(document).encode()).hexdigest(),
                event_count=len(document['events']), origins=groups,
                semantic_status='synthetic_only' if document['provenance'] == 'synthetic' else 'externally_unverified',
                game_effect_verified=False, whole_match_acceptance_passed=False, causal_advantage_established=False,
                note='Counts are correlated assertions. Hashes and provenance labels do not prove damage, release, natural settlement or model advantage.')


def compare_runs(documents):
    """Compare matched-condition records without inventing causal or win-rate claims."""
    require(type(documents) is list and len(documents) >= 2, 'comparison_requires_two_runs')
    reports = [summarize(value) for value in documents]
    first, seen_runs, seen_sessions = reports[0], set(), set()
    require(not any(first['conditions'][key] in ('unknown', 'unrecorded', 'unspecified')
                    for key in ('experiment_id', 'map_id', 'faction', 'opponent_id', 'difficulty')),
            'comparison_conditions_incomplete')
    for report in reports:
        require(report['conditions'] == first['conditions'], 'comparison_conditions_changed')
        require(report['provenance'] == first['provenance'], 'comparison_provenance_mixed')
        binding = report['binding']
        require(all(binding[k] == first['binding'][k] for k in
                    ('player_id', 'commander_id', 'profile_revision', 'effective_hash')), 'comparison_profile_changed')
        require(binding['run_id'] not in seen_runs and binding['session_id'] not in seen_sessions, 'comparison_duplicate_run_or_session')
        seen_runs.add(binding['run_id']); seen_sessions.add(binding['session_id'])
    represented = {origin: sum(report['origins'][origin]['started_tasks'] > 0 for report in reports) for origin in ORIGINS}
    return dict(schema_version=1, kind='matched_contribution_records', conditions=first['conditions'],
                provenance=first['provenance'], runs=reports, runs_with_executions_by_origin=represented,
                three_origins_represented=all(represented.values()), causal_advantage_established=False,
                same_random_trajectory_established=False, whole_match_acceptance_passed=False)


def compare_style_decisions(documents):
    """Compare reported intent hashes under identical frozen input, separately from game outcomes."""
    require(type(documents) is list and len(documents) >= 2, 'style_comparison_requires_two_records')
    first = documents[0]
    groups, profiles, seen_runs = defaultdict(lambda: defaultdict(list)), {}, set()
    for document in documents:
        summarize(document)
        require(document['binding']['run_id'] not in seen_runs, 'style_comparison_duplicate_run')
        seen_runs.add(document['binding']['run_id'])
        require(document['conditions'] == first['conditions'], 'comparison_conditions_changed')
        require(document['provenance'] == first['provenance'], 'comparison_provenance_mixed')
        require(document['binding']['commander_id'] == first['binding']['commander_id']
                and document['binding']['player_id'] == first['binding']['player_id'], 'style_comparison_binding_changed')
        for row in document['events']:
            if row['kind'] != 'decision' or row['origin'] != 'model':
                continue
            data = row['data']; style = data['style']
            profile = (document['binding']['profile_revision'], document['binding']['effective_hash'])
            require(style not in profiles or profiles[style] == profile, 'style_profile_drift')
            profiles[style] = profile
            groups[data['input_sha256']][style].append(data['intent_sha256'])
    comparisons = []
    for input_sha, styles in sorted(groups.items()):
        distinct = {digest for values in styles.values() for digest in values}
        comparisons.append(dict(input_sha256=input_sha, samples_by_style={k: len(v) for k, v in sorted(styles.items())},
                                intent_hashes_by_style={k: sorted(set(v)) for k, v in sorted(styles.items())},
                                different_reported_intents=len(distinct) > 1 if len(styles) >= 2 else None,
                                within_style_variation={k: len(set(v)) > 1 for k, v in sorted(styles.items())}))
    return dict(schema_version=1, kind='fixed_input_style_decision_review', comparisons=comparisons,
                same_input_multiple_styles=sum(len(group) >= 2 for group in groups.values()),
                execution_behavior_difference_verified=False, outcome_difference_verified=False,
                style_causality_established=False, whole_match_acceptance_passed=False)


def adapt_host_events(binding, rows, *, origin, conditions, evidence_sha256,
                      decision_inputs=None, plan_origins=None, task_origins=None):
    """Whitelist adapter for battle_host.event JSONL; never infer damage or settlement.

    decision_inputs maps plan_id to {input_sha256, style}. A captured input hash is
    required; raw plan text alone cannot establish a fixed-input comparison.
    Production/native effect collectors must add their separately correlated events.
    """
    validate_binding(binding); validate_conditions(conditions); sha(evidence_sha256)
    require(origin in ORIGINS, 'event_origin')
    require(type(rows) is list and len(rows) <= MAX_EVENTS, 'event_limit')
    links, task_plans, mapped, omitted = decision_inputs or {}, {}, [], Counter()
    plan_origins, task_origins = plan_origins or {}, task_origins or {}
    require(all(type(value) is dict for value in (links, plan_origins, task_origins)), 'adapter_link_maps')
    decisions, tasks, terminals, calls, time = set(), set(), set(), set(), 0.
    def emit(kind, data):
        seq = row.get('_source_seq', position + 1)
        require(type(seq) is int and seq >= 1, 'host_event_sequence')
        mapped.append(dict(event_id=f'host-{seq}', seq=seq, game_seconds=time, binding=dict(binding),
                           origin=origin, kind=kind, data=data, evidence_sha256=evidence_sha256))
    for position, row in enumerate(rows):
        require(type(row) is dict and all(row.get(k) == binding[k] for k in
                    ('session_id', 'player_id', 'commander_id')), 'host_event_binding_mismatch')
        if 'profile_revision' in row:
            require(row['profile_revision'] == binding['profile_revision'], 'host_profile_revision_changed')
        if 'effective_hash' in row:
            require(row['effective_hash'] == binding['effective_hash'], 'host_effective_hash_changed')
        raw_time = row.get('at_game_seconds', row.get('game_time_seconds'))
        if raw_time is not None:
            current = number(raw_time)
            require(current >= time, 'host_event_clock')
            time = current
        kind = row.get('kind')
        if kind == 'commander_profile_applied':
            if origin != 'model':
                omitted['other_origin_event'] += 1; continue
            require(row.get('profile_revision') == binding['profile_revision']
                    and row.get('effective_hash') == binding['effective_hash'], 'host_profile_application_unbound')
            emit('configuration_applied', {})
        elif kind == 'commander_model_response_returned':
            if origin != 'model':
                omitted['other_origin_event'] += 1; continue
            sequence = row.get('call_sequence')
            require(type(sequence) is int and sequence > 0, 'host_call_sequence')
            require(row.get('profile_revision') == binding['profile_revision']
                    and row.get('effective_hash') == binding['effective_hash'], 'host_model_consumption_unbound')
            if sequence in calls:
                omitted['repeated_model_response'] += 1; continue
            calls.add(sequence)
            emit('model_consumed', dict(call_id=f'call-{sequence}', transport=row.get('transport_mode', 'unknown')))
        elif kind == 'plan_applied':
            plan_id = ident(row.get('plan_id'))
            if row.get('origin', plan_origins.get(plan_id)) != origin:
                omitted['plan_origin_unknown_or_other'] += 1; continue
            if plan_id not in links:
                omitted['plan_without_captured_input_hash'] += 1; continue
            if plan_id in decisions:
                omitted['repeated_plan'] += 1; continue
            link = links[plan_id]; fields(link, {'input_sha256', 'style'}, 'decision_link_fields')
            plan = row.get('plan'); require(type(plan) is dict, 'host_plan_missing')
            # IDs, timestamps, prose and provider payloads are not intent changes.
            intent = {k: plan[k] for k in ('stance', 'production_focus', 'economy_policy', 'tech_policy',
                                          'budget', 'objective_region', 'tactical_tasks') if k in plan}
            require(bool(intent), 'host_plan_intent_missing')
            emit('decision', dict(decision_id=plan_id, input_sha256=link['input_sha256'],
                                  intent_sha256=hashlib.sha256(canonical(intent).encode()).hexdigest(), style=link['style']))
            decisions.add(plan_id)
        elif kind == 'task_proposed':
            proposed = row.get('plan_id')
            if proposed is not None:
                ident(proposed)
            task_plans[ident(row.get('task_id'))] = proposed
        elif kind == 'task_feedback':
            task_id, state = ident(row.get('task_id')), row.get('status')
            if row.get('origin', task_origins.get(task_id)) != origin:
                omitted['task_origin_unknown_or_other'] += 1; continue
            if state == 'started':
                decision = task_plans.get(task_id)
                if origin == 'model' and decision not in decisions:
                    omitted['start_without_captured_decision'] += 1; continue
                if task_id in tasks:
                    omitted['repeated_start'] += 1; continue
                emit('execution_started', dict(task_id=task_id, decision_id=decision if decision in decisions else None))
                tasks.add(task_id)
            elif state in ('completed', 'failed', 'cancelled', 'unknown') and task_id in tasks:
                if (task_id, state) in terminals:
                    omitted['repeated_terminal_feedback'] += 1; continue
                terminals.add((task_id, state))
                emit('task_result', dict(task_id=task_id, status=state))
            else:
                omitted['feedback_without_mapped_start_or_supported_status'] += 1
        else:
            omitted['unmapped_host_event'] += 1
    document = dict(schema_version=1, binding=dict(binding), conditions=dict(conditions),
                    provenance='recorded_assertions', events=mapped)
    summarize(document)
    return dict(document=document, omitted_counts=dict(omitted),
                authority='externally_unverified', automatic_damage_or_release_or_settlement_inference=False)


def adapt_host_diagnostics(export, *, conditions, evidence_sha256, decision_inputs=None,
                           plan_origins=None, task_origins=None):
    """Adapt the existing redacted diagnostics v1; unknown origins stay excluded.

    The caller supplies matched experimental conditions and the frozen file hash.
    This checks projected JSON integrity, not original SQLite or native semantics.
    """
    require(type(export) is dict and export.get('schema_version') == 1
            and export.get('kind') == 'tacticore_redacted_diagnostics' and export.get('redacted') is True,
            'host_diagnostics_format')
    validate_conditions(conditions); sha(evidence_sha256)
    native_binding, profile = export.get('binding'), export.get('effective_profile')
    require(type(native_binding) is dict and type(profile) is dict, 'host_diagnostics_binding_missing')
    require(export.get('effective_profile_available') is True
            and profile.get('profile_id') == native_binding.get('commander_id'), 'host_diagnostics_profile_missing')
    binding = dict(run_id=export.get('run_id'), session_id=native_binding.get('session_id'),
                   player_id=native_binding.get('player_id'), commander_id=native_binding.get('commander_id'),
                   profile_revision=profile.get('revision'), effective_hash=profile.get('effective_hash'))
    validate_binding(binding)
    require(hashlib.sha256(canonical(native_binding).encode()).hexdigest() == export.get('binding_hash'), 'host_diagnostics_binding_hash')
    rows, metadata = export.get('timeline'), export.get('events')
    require(type(rows) is list and len(rows) <= MAX_EVENTS and type(metadata) is dict, 'host_diagnostics_events')
    require(metadata.get('truncated') is False and metadata.get('total_count') == metadata.get('exported_count') == len(rows),
            'host_diagnostics_truncated_or_incomplete')
    require(hashlib.sha256(canonical(rows).encode()).hexdigest() == metadata.get('timeline_sha256'), 'host_diagnostics_timeline_hash')
    status = export.get('status')
    if type(status) is dict:
        for key in ('run_id', 'profile_revision', 'effective_hash'):
            if key in status:
                require(status[key] == binding[key], 'host_diagnostics_status_binding')
    host_rows, omitted, last_seq, last_frame = [], Counter(), 0, 0
    for row in rows:
        require(type(row) is dict and type(row.get('seq')) is int and row['seq'] > last_seq,
                'host_diagnostics_event_sequence')
        last_seq = row['seq']
        facts = row.get('facts')
        if row.get('event_type') == 'unprojected_event' and row.get('payload_projected') is False and facts is None:
            omitted['unprojected_event'] += 1; continue
        require(type(facts) is dict, 'host_diagnostics_event_facts')
        for key in ('session_id', 'player_id', 'commander_id', 'profile_revision', 'effective_hash'):
            if key in facts:
                require(facts[key] == binding[key], 'host_diagnostics_event_binding')
        if type(row.get('game_frame')) is int:
            require(row['game_frame'] >= last_frame, 'host_diagnostics_frame_regressed')
            last_frame = row['game_frame']
        if not all(facts.get(key) == binding[key] for key in ('session_id', 'player_id', 'commander_id')):
            omitted['event_without_complete_binding'] += 1; continue
        record = dict(facts, kind=row.get('event_type'), game_time_seconds=last_frame / 15, _source_seq=row['seq'])
        # at_game_seconds is a model/task's historical basis, not necessarily the
        # current journal sampling frame. Preserve journal order without upgrading it.
        record.pop('at_game_seconds', None)
        host_rows.append(record)
    if rows:
        require(metadata.get('first_seq') == rows[0]['seq'] and metadata.get('last_seq') == rows[-1]['seq'],
                'host_diagnostics_sequence_window')
    adapted = [adapt_host_events(binding, host_rows, origin=origin, conditions=conditions,
                evidence_sha256=evidence_sha256, decision_inputs=decision_inputs,
                plan_origins=plan_origins, task_origins=task_origins) for origin in ORIGINS]
    events = sorted((row for item in adapted for row in item['document']['events']), key=lambda row: row['seq'])
    document = dict(schema_version=1, binding=binding, conditions=dict(conditions), provenance='recorded_assertions', events=events)
    result = summarize(document)
    return dict(kind='host_diagnostics_attribution_adapter', document=document, summary=result, omitted_counts=dict(omitted),
                omitted_counts_by_origin={origin: item['omitted_counts'] for origin, item in zip(ORIGINS, adapted)},
                source_file_sha256=evidence_sha256,
                source_timeline_events=len(rows), source_sequence_gaps_allowed=True,
                authority='externally_unverified', automatic_damage_or_release_or_settlement_inference=False)


def load_json(path, *, return_sha256=False):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), 'input_file_required')
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, 'input_too_large')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def constant(_):
        raise AttributionError('nonfinite_json')
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=constant)
        return (value, hashlib.sha256(raw).hexdigest()) if return_sha256 else value
    except (UnicodeError, json.JSONDecodeError):
        raise AttributionError('invalid_json') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('summarize', 'compare', 'styles', 'diagnostics'))
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--conditions', type=Path, help='Explicit matched-condition JSON for diagnostics adaptation.')
    args = parser.parse_args(argv)
    loaded = [load_json(path, return_sha256=True) for path in args.inputs]
    documents = [value for value, _ in loaded]
    if args.mode == 'summarize':
        require(len(documents) == 1, 'summary_requires_one_input')
        result = summarize(documents[0])
    elif args.mode == 'diagnostics':
        require(len(documents) == 1 and args.conditions is not None, 'diagnostics_requires_input_and_conditions')
        result = adapt_host_diagnostics(documents[0], conditions=load_json(args.conditions), evidence_sha256=loaded[0][1])
    else:
        result = (compare_runs if args.mode == 'compare' else compare_style_decisions)(documents)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(canonical(dict(kind=result['kind'], whole_match_acceptance_passed=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
