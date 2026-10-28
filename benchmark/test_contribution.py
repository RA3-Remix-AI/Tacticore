"""Synthetic attribution and adapter contracts. No game, model or credential IO."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from contribution import (AttributionError, adapt_host_diagnostics, adapt_host_events, canonical,
                          compare_runs, compare_style_decisions, load_json, main, summarize)


def fixture(origin='model', run='run-one', session='session-one'):
    binding = dict(run_id=run, session_id=session, player_id=3, commander_id='commander-one',
                   profile_revision=3, effective_hash='a'*64)
    conditions = dict(experiment_id='source-comparison-v1', map_id='industrial', faction='soviet',
                      opponent_id='medium-native', difficulty='medium', game_sha256='b'*64,
                      mod_sha256='c'*64, window_seconds=600, seed_control='uncontrolled', seed=None)
    value = dict(schema_version=1, binding=binding, conditions=conditions, provenance='synthetic', events=[])
    def add(kind, data):
        n = len(value['events']) + 1
        value['events'].append(dict(event_id=f'event-{n}', seq=n, game_seconds=n,
                                    binding=dict(binding), origin=origin, kind=kind,
                                    data=data, evidence_sha256=None))
    add('configuration_applied', {})
    if origin == 'model':
        add('model_consumed', dict(call_id='call-one', transport='injected_transport'))
    add('decision', dict(decision_id='decision-one', input_sha256='d'*64, intent_sha256='e'*64, style='steady'))
    add('execution_started', dict(task_id='task-one', decision_id='decision-one'))
    add('spend', dict(task_id='task-one', command_id='command-one', credits=85))
    add('effect', dict(task_id='task-one', effect_id='effect-one', effect_kind='damage', amount=12))
    add('returned_home', dict(task_id='task-one'))
    add('control_released', dict(task_id='task-one'))
    add('task_result', dict(task_id='task-one', status='completed'))
    add('settlement', dict(outcome='win', reason='natural'))
    return value


def diagnostics_fixture():
    base = fixture()
    full = dict(schema_version=1, session_id=base['binding']['session_id'], player_id=3,
                commander_id=base['binding']['commander_id'], host_id='host-one')
    common = {k: base['binding'][k] for k in ('session_id', 'player_id', 'commander_id')}
    profile = dict(profile_id=full['commander_id'], revision=3, effective_hash='a'*64)
    rows = [dict(seq=800, event_type='commander_profile_applied', facts=dict(common, profile_revision=3, effective_hash='a'*64)),
            dict(seq=803, event_type='commander_model_response_returned', game_frame=300,
                 facts=dict(common, profile_revision=3, effective_hash='a'*64, call_sequence=1,
                            transport_mode='provider_transport')),
            dict(seq=810, event_type='task_feedback', game_frame=315,
                 facts=dict(common, task_id='task-one', status='started'))]
    export = dict(schema_version=1, kind='tacticore_redacted_diagnostics', redacted=True,
                  run_id=base['binding']['run_id'], binding=full,
                  binding_hash=hashlib.sha256(canonical(full).encode()).hexdigest(),
                  effective_profile_available=True, effective_profile=profile,
                  timeline=rows, status=dict(run_id=base['binding']['run_id']),
                  events=dict(total_count=len(rows), exported_count=len(rows), truncated=False,
                              first_seq=800, last_seq=810, timeline_sha256=hashlib.sha256(canonical(rows).encode()).hexdigest()))
    return export, base['conditions']


class ContributionTests(unittest.TestCase):
    def assertCode(self, code, operation):
        with self.assertRaisesRegex(AttributionError, '^'+code+'$'):
            operation()

    def test_full_synthetic_layers_remain_non_authoritative(self):
        result = summarize(fixture())
        model = result['origins']['model']
        self.assertEqual(model['reported_spend_credits'], 85)
        self.assertEqual(model['reported_effect_amounts']['damage'], 12)
        self.assertEqual(model['fully_correlated_completed_assertions'], 1)
        self.assertTrue(all(state == 'provided' for state in model['coverage'].values()))
        self.assertEqual(result['semantic_status'], 'synthetic_only')
        self.assertFalse(result['game_effect_verified'])
        self.assertFalse(result['whole_match_acceptance_passed'])
        self.assertFalse(result['causal_advantage_established'])

    def test_missing_layers_have_null_denominators(self):
        value = fixture(); value['events'] = []
        origin = summarize(value)['origins']['model']
        self.assertIsNone(origin['reported_spend_credits'])
        self.assertIsNone(origin['reported_effect_amounts']['damage'])
        self.assertIsNone(origin['completion_rate_known_started_outcomes'])
        self.assertIsNone(origin['settlement'])
        self.assertEqual(origin['coverage']['effect'], 'missing')

    def test_recorded_hashes_do_not_establish_truth(self):
        value = fixture(); value['provenance'] = 'recorded_assertions'
        self.assertCode('invalid_sha256', lambda: summarize(value))
        for row in value['events']: row['evidence_sha256'] = 'f'*64
        result = summarize(value)
        self.assertEqual(result['semantic_status'], 'externally_unverified')
        self.assertFalse(result['whole_match_acceptance_passed'])

    def test_three_origins_are_distinct(self):
        for origin in ('native', 'script', 'model'):
            result = summarize(fixture(origin))
            self.assertEqual(result['origins'][origin]['started_tasks'], 1)
            for other in set(('native', 'script', 'model'))-{origin}:
                self.assertEqual(result['origins'][other]['started_tasks'], 0)

    def test_each_event_must_match_all_binding_fields(self):
        for key, changed in [('session_id', 'other'), ('player_id', 4), ('commander_id', 'other'),
                             ('profile_revision', 4), ('effective_hash', 'f'*64), ('run_id', 'other')]:
            value = fixture(); value['events'][2]['binding'][key] = changed
            self.assertCode('event_binding_mismatch', lambda: summarize(value))

    def test_duplicate_event_sequence_and_nonfinite_rejected(self):
        value = fixture(); value['events'][1]['event_id'] = value['events'][0]['event_id']
        self.assertCode('duplicate_event', lambda: summarize(value))
        value = fixture(); value['events'][1]['seq'] = 1
        self.assertCode('event_sequence', lambda: summarize(value))
        value = fixture(); value['events'][0]['game_seconds'] = float('nan')
        self.assertCode('invalid_number', lambda: summarize(value))

    def test_unknown_fields_and_origins_are_rejected_without_echo(self):
        secret = 'FAKE-SECRET-DO-NOT-EXPORT'
        value = fixture(); value['events'][0]['provider_payload'] = secret
        self.assertCode('event_fields', lambda: summarize(value))
        value = fixture(); value['events'][0]['origin'] = 'unknown'
        self.assertCode('event_origin', lambda: summarize(value))
        value = fixture(); value['events'][0]['kind'] = []
        self.assertCode('event_kind', lambda: summarize(value))

    def test_no_model_execution_without_owned_decision(self):
        value = fixture(); start = next(row for row in value['events'] if row['kind'] == 'execution_started')
        start['data']['decision_id'] = None
        self.assertCode('model_execution_requires_decision', lambda: summarize(value))
        start['data']['decision_id'] = 'missing'
        self.assertCode('decision_origin_or_order_mismatch', lambda: summarize(value))

    def test_cross_origin_task_spend_and_effect_rejected(self):
        for kind in ('spend', 'effect', 'returned_home', 'control_released', 'task_result'):
            value = fixture(); next(row for row in value['events'] if row['kind'] == kind)['origin'] = 'native'
            self.assertCode('task_origin_or_start_mismatch', lambda: summarize(value))

    def test_spend_and_effect_identity_cannot_be_counted_twice(self):
        for kind, code in [('spend', 'duplicate_spend_command'), ('effect', 'duplicate_effect')]:
            value = fixture(); row = copy.deepcopy(next(row for row in value['events'] if row['kind'] == kind))
            row.update(event_id='repeated', seq=100, game_seconds=100);value['events'].append(row)
            self.assertCode(code, lambda: summarize(value))

    def test_conflicting_outcomes_are_excluded_from_completion_rate(self):
        value = fixture(); row = copy.deepcopy(next(row for row in value['events'] if row['kind'] == 'task_result'))
        row.update(event_id='conflict', seq=100, game_seconds=100);row['data']['status'] = 'failed'; value['events'].append(row)
        model = summarize(value)['origins']['model']
        self.assertEqual(model['task_outcomes']['conflicting'], 1)
        self.assertEqual(model['fully_correlated_completed_assertions'], 0)
        self.assertIsNone(model['completion_rate_known_started_outcomes'])

    def test_late_release_does_not_retroactively_certify_completion(self):
        value = fixture()
        home = next(row for row in value['events'] if row['kind'] == 'returned_home')
        release = next(row for row in value['events'] if row['kind'] == 'control_released')
        value['events'].remove(home); value['events'].remove(release)
        for row in (home, release):
            row.update(seq=100+len(value['events']), game_seconds=100);value['events'].append(row)
        self.assertEqual(summarize(value)['origins']['model']['fully_correlated_completed_assertions'], 0)

    def test_game_clock_and_budget_window(self):
        value=fixture();value['events'][-1]['game_seconds']=0
        self.assertCode('event_clock', lambda: summarize(value))
        value=fixture();value['conditions']['window_seconds']=1
        self.assertCode('event_clock', lambda: summarize(value))

    def test_comparison_requires_same_conditions_and_profile(self):
        first, second = fixture(), fixture('native','run-two','session-two')
        self.assertFalse(compare_runs([first, second])['causal_advantage_established'])
        for field in ('map_id', 'difficulty'):
            changed=copy.deepcopy(second);changed['conditions'][field]='other'
            self.assertCode('comparison_conditions_changed', lambda: compare_runs([first, changed]))
        changed=copy.deepcopy(second);changed['binding']['profile_revision']=4
        for row in changed['events']:row['binding']['profile_revision']=4
        self.assertCode('comparison_profile_changed', lambda: compare_runs([first, changed]))

    def test_comparison_cannot_reuse_same_match_or_mix_synthetic_and_recorded(self):
        first, second = fixture(), fixture('script','run-two','session-one')
        self.assertCode('comparison_duplicate_run_or_session', lambda: compare_runs([first, second]))
        second=fixture('script','run-two','session-two');second['provenance']='recorded_assertions'
        for row in second['events']:row['evidence_sha256']='f'*64
        self.assertCode('comparison_provenance_mixed', lambda: compare_runs([first, second]))

    def test_three_way_comparison_reports_coverage_without_advantage(self):
        result=compare_runs([fixture(),fixture('native','run-two','session-two'),fixture('script','run-three','session-three')])
        self.assertTrue(result['three_origins_represented'])
        self.assertFalse(result['same_random_trajectory_established'])
        self.assertFalse(result['whole_match_acceptance_passed'])

    def test_unknown_comparison_conditions_cannot_establish_matching(self):
        first,second=fixture(),fixture('native','run-two','session-two')
        first['conditions']['map_id']=second['conditions']['map_id']='unrecorded'
        self.assertCode('comparison_conditions_incomplete', lambda:compare_runs([first,second]))

    def test_fixed_input_style_difference_separate_from_behavior(self):
        first, second=fixture(),fixture(run='run-two',session='session-two')
        choice=next(row for row in second['events'] if row['kind']=='decision')
        choice['data'].update(style='pressure',intent_sha256='f'*64)
        result=compare_style_decisions([first,second])
        self.assertEqual(result['same_input_multiple_styles'],1)
        self.assertTrue(result['comparisons'][0]['different_reported_intents'])
        self.assertFalse(result['execution_behavior_difference_verified'])
        self.assertFalse(result['style_causality_established'])

    def test_different_frozen_input_is_not_a_style_comparison_pair(self):
        first,second=fixture(),fixture(run='run-two',session='session-two')
        choice=next(row for row in second['events'] if row['kind']=='decision')
        choice['data'].update(style='pressure', input_sha256='f'*64)
        result=compare_style_decisions([first,second])
        self.assertEqual(result['same_input_multiple_styles'],0)
        self.assertTrue(all(row['different_reported_intents'] is None for row in result['comparisons']))

    def test_style_label_cannot_silently_change_effective_profile(self):
        first,second=fixture(),fixture(run='run-two',session='session-two')
        second['binding']['effective_hash']='f'*64
        for row in second['events']:row['binding']['effective_hash']='f'*64
        self.assertCode('style_profile_drift', lambda: compare_style_decisions([first,second]))

    def test_style_comparison_duplicate_record_rejected(self):
        self.assertCode('style_comparison_duplicate_run',lambda:compare_style_decisions([fixture(),fixture()]))

    def host_rows(self):
        value=fixture();common={k:value['binding'][k] for k in ('session_id','player_id','commander_id')}
        rows=[dict(common,kind='commander_profile_applied',profile_revision=3,effective_hash='a'*64),
              dict(common,kind='commander_model_response_returned',profile_revision=3,effective_hash='a'*64,
                   call_sequence=1,transport_mode='provider_transport'),
              dict(common,kind='plan_applied',plan_id='plan-one',plan=dict(stance='raid',production_focus='infantry',
                                                                       explanation='FAKE-SECRET-NOT-EXPORTED')),
              dict(common,kind='task_proposed',task_id='task-one',plan_id='plan-one'),
              dict(common,kind='task_feedback',task_id='task-one',status='started',at_game_seconds=10),
              dict(common,kind='task_feedback',task_id='task-one',status='completed',at_game_seconds=20)]
        return value,rows

    def test_host_adapter_requires_explicit_origin_and_captured_input(self):
        value, rows=self.host_rows()
        result=adapt_host_events(value['binding'],rows,origin='model',conditions=value['conditions'],evidence_sha256='f'*64)
        model=summarize(result['document'])['origins']['model']
        self.assertEqual(model['model_response_assertions'],1)
        self.assertEqual(model['decision_assertions'],0)
        self.assertEqual(model['started_tasks'],0)
        self.assertEqual(result['omitted_counts']['task_origin_unknown_or_other'],2)

    def test_host_adapter_explicit_links_produce_only_assertions(self):
        value,rows=self.host_rows()
        result=adapt_host_events(value['binding'],rows,origin='model',conditions=value['conditions'],evidence_sha256='f'*64,
                decision_inputs={'plan-one':dict(input_sha256='d'*64,style='steady')},
                plan_origins={'plan-one':'model'},task_origins={'task-one':'model'})
        model=summarize(result['document'])['origins']['model']
        self.assertEqual(model['decision_assertions'],1);self.assertEqual(model['started_tasks'],1)
        self.assertEqual(model['fully_correlated_completed_assertions'],0)
        self.assertNotIn('FAKE-SECRET',canonical(result))
        self.assertIsNone(model['settlement'])

    def test_host_adapter_refuses_cross_revision_before_counting(self):
        value,rows=self.host_rows();rows[0]['profile_revision']=4
        self.assertCode('host_profile_revision_changed', lambda: adapt_host_events(value['binding'],rows,
                        origin='model',conditions=value['conditions'],evidence_sha256='f'*64))

    def test_host_adapter_deduplicates_same_plan_refresh(self):
        value,rows=self.host_rows();rows.insert(3,copy.deepcopy(rows[2]))
        result=adapt_host_events(value['binding'],rows,origin='model',conditions=value['conditions'],evidence_sha256='f'*64,
                decision_inputs={'plan-one':dict(input_sha256='d'*64,style='steady')},
                plan_origins={'plan-one':'model'},task_origins={'task-one':'model'})
        self.assertEqual(result['omitted_counts']['repeated_plan'],1)
        self.assertEqual(summarize(result['document'])['origins']['model']['decision_assertions'],1)

    def test_diagnostics_sequence_gaps_are_valid_unknown_task_origin_excluded(self):
        export,conditions=diagnostics_fixture()
        result=adapt_host_diagnostics(export,conditions=conditions,evidence_sha256='f'*64)
        self.assertEqual(result['source_timeline_events'],3)
        self.assertEqual(result['summary']['origins']['model']['model_response_assertions'],1)
        self.assertEqual(result['summary']['origins']['model']['started_tasks'],0)
        self.assertFalse(result['summary']['whole_match_acceptance_passed'])

    def test_unprojected_diagnostics_are_excluded_without_claiming_coverage(self):
        export,conditions=diagnostics_fixture()
        export['timeline'].append(dict(seq=811,event_type='unprojected_event',payload_projected=False,payload_sha256='f'*64))
        export['events'].update(total_count=4,exported_count=4,last_seq=811,
                                timeline_sha256=hashlib.sha256(canonical(export['timeline']).encode()).hexdigest())
        result=adapt_host_diagnostics(export,conditions=conditions,evidence_sha256='f'*64)
        self.assertEqual(result['omitted_counts']['unprojected_event'],1)
        self.assertEqual(len(result['document']['events']),2)

    def test_diagnostics_hash_count_truncation_and_binding_checked(self):
        for mutate,code in [(lambda d:d['timeline'][0]['facts'].update(profile_revision=4),'host_diagnostics_timeline_hash'),
                            (lambda d:d['events'].update(truncated=True),'host_diagnostics_truncated_or_incomplete'),
                            (lambda d:d['events'].update(exported_count=4),'host_diagnostics_truncated_or_incomplete'),
                            (lambda d:d['binding'].update(player_id=4),'host_diagnostics_binding_hash')]:
            export,conditions=diagnostics_fixture();mutate(export)
            self.assertCode(code,lambda:adapt_host_diagnostics(export,conditions=conditions,evidence_sha256='f'*64))

    def test_strict_json_rejects_duplicate_keys_and_nan(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'input.json'
            for raw,code in [(' {"a":1,"a":2}', 'duplicate_json_key'),('{"a":NaN}','nonfinite_json')]:
                path.write_text(raw,encoding='utf-8');self.assertCode(code,lambda:load_json(path))

    def test_cli_writes_new_output_and_never_overwrites_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'input.json';out=Path(temp)/'summary.json'
            raw=json.dumps(fixture());path.write_text(raw,encoding='utf-8')
            self.assertEqual(main(['summarize',str(path),'--output',str(out)]),0)
            self.assertFalse(json.loads(out.read_text())['whole_match_acceptance_passed'])
            with self.assertRaises(FileExistsError):main(['summarize',str(path),'--output',str(path)])
            self.assertEqual(path.read_text(),raw)

    def test_cli_diagnostics_uses_exact_read_bytes_hash(self):
        export,conditions=diagnostics_fixture()
        with tempfile.TemporaryDirectory() as temp:
            path,condition_path,out=(Path(temp)/name for name in ('diagnostics.json','conditions.json','output.json'))
            raw=json.dumps(export).encode();path.write_bytes(raw)
            condition_path.write_text(json.dumps(conditions),encoding='utf-8')
            self.assertEqual(main(['diagnostics',str(path),'--conditions',str(condition_path),'--output',str(out)]),0)
            result=json.loads(out.read_text())
            self.assertEqual(result['source_file_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertFalse(result['summary']['game_effect_verified'])


if __name__ == '__main__':
    unittest.main()
