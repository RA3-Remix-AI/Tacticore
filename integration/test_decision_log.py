"""decisions.jsonl writer, reader, paging and RPC exposure (offline, synthetic events)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
for folder in ('strategy', 'integration'):
    if str(ROOT / folder) not in sys.path:
        sys.path.insert(0, str(ROOT / folder))

from host_runtime.decision_log import (
    DecisionLogWriter, FILE_NAME, decisions_page, match_end_record, read_decisions, read_run_log,
    situation_from_context,
)
from engine import Decision, Plan

RUN = '11111111-1111-4111-8111-111111111111'


def context(game_time=120.0, credits=3000, army=None, buildings=None, defeated=()):
    """A public strategic request context with the sections the host really sends."""
    roles = army or dict(infantry=6, armor=4)
    return dict(
        game_time_seconds=game_time, player_id=3,
        working_memory=dict(
            economy=dict(credits=credits, power_balance=20),
            match_state=dict(opponent_player_ids=[4, 5], defeated_opponent_ids=list(defeated)),
            battlefield=dict(contact_groups=[
                dict(region_id='region_7_2', role='armor', relation='enemy', currently_visible=True,
                     observations=3, oldest_game_seconds=110, newest_game_seconds=game_time, owner_player_id=4),
                dict(region_id='region_9_9', role='structure', relation='enemy', currently_visible=False,
                     observations=2, oldest_game_seconds=40, newest_game_seconds=60, owner_player_id=5),
            ]),
            own_combat_change=dict(since_game_seconds=90, previous_count=12, current_count=10, net_change=-2)),
        own_forces=dict(mobile_role_counts=roles, building_presence_counts=buildings or dict(barracks=1, refinery=2),
                        economic_unit_presence_counts=dict(ore_collector=3)),
        battlefield_summary=dict(nearby_home_enemy_mobile_observations=3, mining_regions=[
            dict(region_id='region_6_1', nearby_enemy_mobile_observations=0)]),
    )


def plan(actions=('attackenemy', 'budgetarmy'), reasoning='Enemy army is away; hit their base now.'):
    return Plan(str(uuid.uuid4()), 'c', 's', 3, 1, 120.0, 180.0, 'pressure', 'native_baseline', 'stabilize',
                'hold_current_tier', (('army', .5), ('economy', .25), ('reserve', .25), ('tech', 0.)), None,
                'balanced_default', 'model', macro_actions=tuple(actions),
                macro_strategy=dict(objective='pressure'), reasoning=reasoning)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.clock = Clock()
        self.response = None
        self.log = DecisionLogWriter(self.dir, RUN, prompt_version='v2', provider='DeepSeek', model='m1',
                                     map_id='map_mp_2_feasel6', opponent_difficulty='brutal',
                                     response_supplier=lambda: self.response, monotonic=self.clock)
        self.log.start()

    def lines(self):
        return [json.loads(line) for line in (self.dir / FILE_NAME).read_text(encoding='utf-8').splitlines()]

    def request(self, value, latency=2.5, receipt=True):
        self.log.observe_event('model_macro_request_context', dict(sequence=1, context=value, context_bytes=9000))
        self.log.observe_event('commander_model_call_started', dict(call_sequence=1))
        self.clock.now += latency
        facts = dict(transport_receipt=dict(request_bytes=15000, response_bytes=700)) if receipt else {}
        self.log.observe_event('commander_model_response_returned', facts)

    def apply(self, accepted_plan):
        self.log.decided(Decision('accepted', 'valid_policy', accepted_plan))
        self.log.observe_event('macro_policy_acknowledged', dict(plan_id=accepted_plan.plan_id,
                                                                 native_gate_acknowledged=True))
        self.log.observe_event('plan_applied', dict(plan_id=accepted_plan.plan_id))

    def test_applied_cycle_has_situation_decision_outcome_and_model(self):
        self.request(context())
        self.apply(plan())
        start, record = self.lines()
        self.assertEqual(start['kind'], 'run_start')
        self.assertEqual((start['prompt_version'], start['map_id'], start['opponent_difficulty']),
                         ('v2', 'map_mp_2_feasel6', 'brutal'))
        self.assertEqual(record['kind'], 'decision')
        self.assertEqual((record['seq'], record['run_id'], record['game_time_s']), (1, RUN, 120.0))
        own = record['situation']['own']
        self.assertEqual((own['credits'], own['army_count'], own['building_count']), (3000, 10, 3))
        self.assertEqual(own['income_hint'], '3 ore collectors')
        enemies = {row['player_id']: row for row in record['situation']['enemies']}
        self.assertEqual((enemies[4]['last_seen_s'], enemies[4]['visible_count']), (120.0, 3))
        self.assertEqual((enemies[5]['last_seen_s'], enemies[5]['visible_count']), (60, 0))
        self.assertIn('3 enemy units near home', record['situation']['threats'])
        self.assertIn('own army shrank by 2 since 90s', record['situation']['threats'])
        decision = record['decision']
        self.assertEqual(decision['intents'], ['attackenemy', 'budgetarmy'])
        self.assertEqual((decision['objective'], decision['valid_for_s']), ('pressure', 60.0))
        self.assertEqual(decision['reasoning'], 'Enemy army is away; hit their base now.')
        self.assertEqual(record['outcome'], dict(status='applied', reason_code='plan_applied',
                                                 native_accepted=True, observed_effects=[]))
        self.assertEqual(record['model'], dict(provider='DeepSeek', model='m1', latency_ms=2500,
                                               input_bytes=15000, output_bytes=700, error=None))

    def test_effects_are_appended_and_folded_by_the_reader(self):
        self.request(context())
        accepted = plan()
        self.apply(accepted)
        feedback = dict(observed_frame=125 * 15, observations=[
            dict(action='attackenemy', status='native_task_active', movement_observed=True),
            dict(action='expand', status='native_task_active', movement_observed=False)])
        self.log.observe_event('macro_unified_feedback', feedback)
        self.log.observe_event('macro_unified_feedback', feedback)  # unchanged: no new line
        self.log.observe_event('macro_native_feedback', dict(status='native_budget_adopted',
                                                             selected_policy='budgetarmy', observed_frame=126 * 15))
        self.assertEqual([line['kind'] for line in self.lines()], ['run_start', 'decision', 'effects', 'effects'])
        first = read_decisions(self.dir)[0]
        self.assertFalse(first['final'])
        self.assertEqual(first['outcome']['observed_effects'],
                         ['attackenemy: native task active, units moving',
                          'budgetarmy: native spending weights adopted'])
        # The next decision closes the first one with own/enemy changes.
        self.request(context(game_time=150.0, army=dict(infantry=9, armor=6), defeated=[4]))
        records = read_decisions(self.dir)
        self.assertTrue(records[0]['final'])
        self.assertIn('own army 10 -> 15 (by 150.0s)', records[0]['outcome']['observed_effects'])
        self.assertIn('enemy player 4 defeated (by 150.0s)', records[0]['outcome']['observed_effects'])

    def test_feedback_after_expiry_is_not_attributed(self):
        self.request(context())
        self.apply(plan())
        self.log.observe_event('macro_unified_feedback', dict(observed_frame=200 * 15, observations=[
            dict(action='attackenemy', status='native_task_active', movement_observed=True)]))
        self.assertEqual(read_decisions(self.dir)[0]['outcome']['observed_effects'], [])

    def test_rejected_policy_keeps_the_unvalidated_response_summary(self):
        self.request(context())
        self.response = dict(macro_actions=['attackenemy', 'focusenemy9'], reasoning='Go.',
                             macro_strategy=dict(objective='pressure'), valid_for_game_seconds=45)
        self.log.observe_event('commander_model_response_returned', {})
        self.log.decided(Decision('local_fallback', 'unsupported_macro_action', None))
        record = read_decisions(self.dir)[0]
        self.assertEqual(record['outcome']['status'], 'rejected')
        self.assertEqual(record['outcome']['reason_code'], 'unsupported_macro_action')
        self.assertFalse(record['outcome']['native_accepted'])
        self.assertEqual(record['decision']['source'], 'unvalidated_response')
        self.assertEqual(record['decision']['intents'], ['attackenemy', 'focusenemy9'])

    def test_timeout_failure_and_expiry_statuses(self):
        self.request(context(), receipt=False)
        self.log.decided(Decision('local_fallback', 'model_timeout', None))
        self.log.observe_event('model_macro_request_context', dict(context=context(130.0), context_bytes=10))
        self.log.observe_event('commander_model_call_failed', dict(backend_diagnostics=dict(error_code='http_status_429')))
        self.log.decided(Decision('local_fallback', 'adapter_error', None))
        self.request(context(140.0))
        late = plan()
        self.log.decided(Decision('accepted', 'valid_policy', late))
        self.log.observe_event('macro_plan_not_dispatched', dict(plan_id=late.plan_id, reason_code='expired_or_paused'))
        records = read_decisions(self.dir)
        self.assertEqual([r['outcome']['status'] for r in records], ['rejected', 'rejected', 'expired'])
        self.assertEqual([r['model']['error'] for r in records], ['model_timeout', 'http_status_429', None])
        self.assertIsNone(records[0]['model']['output_bytes'])

    def test_undispatched_and_unknown_plans_are_never_reported_applied(self):
        self.request(context())
        self.log.decided(Decision('accepted', 'valid_policy', plan()))
        self.request(context(140.0))  # a new request means the old plan was never sent
        self.log.decided(Decision('accepted', 'valid_policy', plan()))
        self.log.finish(match_result=None, game_time_s=150.0, reason_code='macro_dispatch_outcome_unknown')
        records = read_decisions(self.dir)
        self.assertEqual([(r['outcome']['status'], r['outcome']['native_accepted']) for r in records],
                         [('rejected', False), ('unknown', None)])
        self.assertEqual(records[1]['outcome']['reason_code'], 'macro_dispatch_outcome_unknown')

    def test_user_stop_before_dispatch_is_a_known_non_delivery(self):
        self.request(context())
        self.log.decided(Decision('accepted', 'valid_policy', plan()))
        self.log.finish(match_result=None, game_time_s=130.0, reason_code='user_stop')
        record = read_decisions(self.dir)[0]
        self.assertEqual((record['outcome']['status'], record['outcome']['reason_code']),
                         ('rejected', 'host_stopped_before_dispatch'))

    def test_finish_writes_match_end_once_and_stops_writing(self):
        result = dict(terminal=True, controlled_outcome='victory', remaining_opponents=0,
                      all_opponents_defeated=True, players={
                          '3': dict(outcome='victory'), '4': dict(outcome='defeat'), '5': dict(outcome='defeat')})
        self.log.finish(match_result=result, game_time_s=900.5, reason_code='native_result_requires_visual_confirmation')
        self.log.finish(match_result=None, game_time_s=1.0)
        self.log.observe_event('model_macro_request_context', dict(context=context()))
        log = read_run_log(self.dir)
        self.assertEqual(log['match_end']['result'], 'victory')
        self.assertEqual(log['match_end']['duration_s'], 900.5)
        self.assertEqual(log['match_end']['players']['3'], dict(outcome='victory', role='self'))
        self.assertFalse(log['match_end']['visually_confirmed'])
        self.assertEqual([line['kind'] for line in self.lines()], ['run_start', 'match_end'])

    def test_writer_never_raises_into_the_host(self):
        broken = DecisionLogWriter(self.dir / 'missing' / 'dir', RUN)
        broken.start()
        broken.observe_event('model_macro_request_context', dict(context=context()))
        broken.decided(Decision('accepted', 'valid_policy', plan()))
        broken.observe_event('plan_applied', dict(plan_id='x'))
        broken.finish()
        self.assertGreater(broken.errors, 0)


class MatchEndTests(unittest.TestCase):
    def test_only_terminal_native_victory_or_defeat_is_a_result(self):
        self.assertEqual(match_end_record(RUN, None)['result'], 'unknown')
        ongoing = dict(terminal=False, controlled_outcome='ongoing', players={})
        self.assertEqual(match_end_record(RUN, ongoing)['result'], 'unknown')
        quit_ = dict(terminal=True, controlled_outcome='quit', players={})
        self.assertEqual(match_end_record(RUN, quit_)['result'], 'unknown')
        self.assertEqual(match_end_record(RUN, quit_)['native_outcome'], 'quit')
        lost = dict(terminal=True, controlled_outcome='defeat', players={'3': dict(outcome='defeat')})
        self.assertEqual(match_end_record(RUN, lost, game_time_s=300)['result'], 'defeat')


class SituationTests(unittest.TestCase):
    def test_real_packed_request_context_is_summarized(self):
        from tactical_fixtures import tactical_snapshot
        from battle_agent import BattleAgent
        from engine import Binding, StrategyEngine
        from fixtures import SESSION, CONNECTION
        from macro_policy import project_strategy_defaults
        from host_runtime.macro_policy_runtime import COMMANDER
        from host_runtime.macro_delegation_boundary_v1 import restrict_snapshot, restrict_context
        raw = tactical_snapshot()
        raw['macro_control'] = dict(mode='macro_native', available_actions=['budgetarmy'])
        binding = Binding(SESSION, 3, COMMANDER, 'Test', CONNECTION)
        agent = BattleAgent(StrategyEngine(binding))
        agent.observe(restrict_snapshot(raw))
        packed = project_strategy_defaults(restrict_context(agent.context(agent.latest.model_context(binding),
                                                                          commit=False)))
        situation = situation_from_context(packed)
        self.assertEqual(situation['own']['credits'], 4000.0)
        self.assertEqual(situation['enemies'][0]['player_id'], 4)
        self.assertIsNone(situation['own']['building_count'])

    def test_missing_sections_stay_null(self):
        situation = situation_from_context({})
        self.assertEqual(situation['own']['credits'], None)
        self.assertEqual(situation['enemies'], [])
        self.assertEqual(situation_from_context(None)['threats'], [])


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        (self.run / 'battle-host').mkdir()
        self.log = DecisionLogWriter(self.run / 'battle-host', RUN, prompt_version='v1')
        self.log.start()
        for index in range(30):
            self.log.observe_event('model_macro_request_context', dict(context=context(100.0 + index)))
            self.log.decided(Decision('local_fallback', 'model_timeout', None))

    def test_run_directory_and_partial_trailing_line(self):
        path = self.run / 'battle-host' / FILE_NAME
        with path.open('a', encoding='utf-8') as stream:
            stream.write('{"schema_version":1,"kind":"decision","seq":31,"situ')
        log = read_run_log(self.run)
        self.assertEqual(len(log['decisions']), 30)
        self.assertEqual(log['invalid_lines'], 1)
        self.assertEqual(log['run']['prompt_version'], 'v1')
        self.assertEqual(read_decisions(self.run / 'nowhere'), [])

    def test_pages_are_bounded_and_resume_from_since_seq(self):
        first = decisions_page(self.run, since_seq=0, max_records=100, max_bytes=8000)
        self.assertTrue(first['has_more'])
        self.assertLess(len(first['decisions']), 30)
        self.assertEqual(first['last_seq'], 30)
        self.assertEqual(first['open_seq'], 30)
        second = decisions_page(self.run, since_seq=first['next_since_seq'])
        seqs = [r['seq'] for r in first['decisions'] + second['decisions']]
        self.assertEqual(seqs, list(range(1, 31)))
        self.assertFalse(second['has_more'])
        self.assertFalse(second['complete'])
        self.log.finish(match_result=None, game_time_s=200.0)
        done = decisions_page(self.run, since_seq=30)
        self.assertEqual(done['decisions'], [])
        self.assertTrue(done['complete'])
        self.assertIsNone(done['open_seq'])
        self.assertEqual(done['match_end']['result'], 'unknown')


class RpcTests(unittest.TestCase):
    def setUp(self):
        from host_runtime.profile_store import ProfileStore
        from test_host_runtime_profile_store import library
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'library.v2.json').write_text(json.dumps(library(), ensure_ascii=False), encoding='utf-8')
        self.store = ProfileStore(root / 'library.v2.json', root / 'state')
        self.addCleanup(self.store.close)
        self.output = root / 'battle-host'
        self.output.mkdir()
        writer = DecisionLogWriter(self.output, RUN, prompt_version='v2', provider='DeepSeek', model='m1')
        writer.start()
        for index in range(60):
            writer.observe_event('model_macro_request_context', dict(context=context(100.0 + index)))
            writer.observe_event('commander_model_response_returned', {})
            writer.decided(Decision('accepted', 'valid_policy', plan(reasoning='因为敌军主力远离，' * 30)))
            writer.observe_event('plan_applied', dict(plan_id=writer._cycle['plan'].plan_id))

    def backend(self):
        from host_runtime.desktop_backend import DesktopBackend
        backend = DesktopBackend.__new__(DesktopBackend)
        output = self.output

        def launch(run_id):
            from host_runtime.contracts import ContractError
            if run_id != RUN:
                raise ContractError('run_not_found')
            return dict(run_id=run_id, output_path=str(output))
        backend._launch = launch
        return backend

    def call(self, service, args):
        from host_runtime.bridge_service import canonical_json
        request = dict(schema_version=1, request_id=str(uuid.uuid4()), operation='run.decisions', args=args)
        response = service.handle(request)
        self.assertLess(len(canonical_json(response).encode('utf-8')), 65536)
        return response

    def test_bridge_pages_decisions_within_one_line(self):
        from host_runtime.bridge_service import BridgeService
        service = BridgeService(self.store, self.backend())
        seen, since = [], 0
        while True:
            response = self.call(service, dict(run_id=RUN, since_seq=since, limit=200))
            self.assertTrue(response['ok'], response)
            result = response['result']
            self.assertEqual(result['run_id'], RUN)
            seen += [record['seq'] for record in result['decisions']]
            since = result['next_since_seq']
            if not result['has_more']:
                break
        self.assertEqual(seen, list(range(1, 61)))
        self.assertTrue(self.call(service, dict(run_id=RUN))['ok'])

    def test_bridge_refuses_bad_arguments_and_unknown_runs(self):
        from host_runtime.bridge_service import BridgeService
        service = BridgeService(self.store, self.backend())
        for args, code in ((dict(run_id=RUN, since_seq=-1), 'invalid_since_seq'),
                           (dict(run_id=RUN, since_seq=True), 'invalid_since_seq'),
                           (dict(run_id=RUN, limit=0), 'invalid_limit'),
                           (dict(run_id=RUN, path='C:/x'), 'unexpected_fields'),
                           (dict(run_id=str(uuid.uuid4())), 'run_not_found')):
            with self.subTest(args=args):
                response = self.call(service, args)
                self.assertEqual(response['error']['code'], code)
        self.assertEqual(self.call(BridgeService(self.store), dict(run_id=RUN))['error']['code'], 'adapter_unavailable')

    def test_control_only_service_admits_the_read_only_operation(self):
        from host_runtime.control_only_server_v1 import CONTROL_OPERATIONS, ExistingRunControlV1
        self.assertIn('run.decisions', CONTROL_OPERATIONS)
        control = ExistingRunControlV1(Path(self.temp.name) / 'state')
        control.backend = self.backend()
        self.assertEqual(control.run_decisions(dict(run_id=RUN), 'r')['last_seq'], 60)


if __name__ == '__main__':
    unittest.main()
