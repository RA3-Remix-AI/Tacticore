import unittest
from unittest.mock import Mock
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from macro_host import request_telemetry_ready,MacroHost
from host_runtime.contracts import ContractError
from host_runtime.macro_policy_runtime import MacroRequestAudit
from host_runtime.macro_production_runtime import MacroProductionController
from battle_agent import BattleAgent
from engine import StrategyEngine,ContractError as StrategyContractError
from fixtures import binding
from tactical_fixtures import tactical_snapshot


class SamplingBoundaryTests(unittest.TestCase):
    def test_slow_pair_crossing_expiry_does_not_attribute_later_native_queues(self):
        from host_runtime.test_macro_production_runtime import ProductionRuntimeTests
        from host_runtime.test_macro_production_feedback import sample
        fixture=ProductionRuntimeTests();fixture.setUp();fixture.dispatch()
        builder,census=sample(2110,[(18,0),(19,0)])
        for row in census['own_objects']:row['hp']=100.
        host=MacroHost.__new__(MacroHost);host.controller=fixture.controller;host.event=Mock()
        host.sampler=SimpleNamespace(scope=fixture.scope);host.latest=dict(game_time_seconds=139.4)
        self.assertTrue(host.production_tick(dict(build_observation=builder,observation=dict(construction_feedback=census))))
        value=host.last_production_feedback
        self.assertEqual(value['release_reason'],'expired')
        self.assertEqual(value['observed_new_queue_count'],0)
        self.assertEqual(value['additional_queue_observations_after_release'],2)
        self.assertEqual([c[0] for c in fixture.calls],[['produceflak','budgetarmy'],[]])

    def test_goal_observed_before_native_expiry_still_releases_at_queue_target(self):
        from host_runtime.test_macro_production_runtime import ProductionRuntimeTests
        from host_runtime.test_macro_production_feedback import sample
        fixture=ProductionRuntimeTests();fixture.setUp();fixture.dispatch()
        builder,census=sample(2090,[(18,0),(19,0)])
        for row in census['own_objects']:row['hp']=100.
        host=MacroHost.__new__(MacroHost);host.controller=fixture.controller;host.event=Mock()
        host.sampler=SimpleNamespace(scope=fixture.scope);host.latest=dict(game_time_seconds=130.)
        self.assertTrue(host.production_tick(dict(build_observation=builder,observation=dict(construction_feedback=census))))
        self.assertEqual(host.last_production_feedback['release_reason'],'queue_target_observed')
        self.assertEqual(host.last_production_feedback['observed_new_queue_count'],2)
        self.assertEqual([c[0] for c in fixture.calls],[['produceflak','budgetarmy'],[]])

    def test_strategy_consumes_valid_first_queue_before_automatic_release(self):
        from host_runtime.test_macro_production_runtime import ProductionRuntimeTests
        from host_runtime.test_macro_production_feedback import sample
        fixture=ProductionRuntimeTests();fixture.setUp();fixture.dispatch()
        builder,census=sample(2090,[(18,0),(19,0)])
        for row in census['own_objects']:row['hp']=100.
        host=MacroHost.__new__(MacroHost);host.controller=fixture.controller;host.event=Mock()
        host.sampler=SimpleNamespace(scope=fixture.scope);host.latest=dict(game_time_seconds=130.)
        host.transport=SimpleNamespace(native_status=lambda:dict(last_frame=2090))
        captured=[]
        host.strategy_runtime=SimpleNamespace(observe=lambda controller,native,at:captured.append(
            (controller.production_feedback()['policy_released'],controller.production_feedback()['observed_new_queue_count'],at)))
        self.assertTrue(host.production_tick(dict(build_observation=builder,observation=dict(construction_feedback=census))))
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0][:2],(False,2))
        self.assertTrue(host.controller.production_feedback()['policy_released'])

    def test_discarded_builder_pair_still_delivers_lawful_visibility_to_memory(self):
        first=tactical_snapshot(1,100);visible=tactical_snapshot(2,101);hidden=tactical_snapshot(3,102)
        visible['battlefield']['contacts'][0]['region_id']='north_expansion'
        visible['battlefield']['regions'][1]['region_id']='north_expansion'
        hidden['battlefield']['contacts'][0].update(region_id='north_expansion',observed_at_game_seconds=101,currently_visible=False)
        hidden['battlefield']['regions'][1].update(region_id='north_expansion',observed_at_game_seconds=101,currently_visible=False,role_counts={})
        # The same hidden update without its preceding visible observation must
        # still fail; no visibility protection is relaxed by this fix.
        guard=BattleAgent(StrategyEngine(binding()));guard.observe(first)
        with self.assertRaisesRegex(StrategyContractError,'hidden_contact_updated'):guard.observe(hidden)
        with tempfile.TemporaryDirectory() as temp:
            host=MacroHost.__new__(MacroHost);host.output=Path(temp);host.agent=BattleAgent(StrategyEngine(binding()))
            host.production_tick=Mock(side_effect=[True,False,True]);host.latest=first
            self.assertTrue(host.consume_observation({}));host.latest=visible
            self.assertFalse(host.consume_observation({}));host.latest=hidden
            self.assertTrue(host.consume_observation({}))
            fact=host.agent.contact_facts['contact_ore']
            self.assertEqual(fact['region_id'],'north_expansion');self.assertEqual(fact['observed_at_game_seconds'],101)
            self.assertFalse(fact['currently_visible']);self.assertEqual(host.agent.engine.metrics['requests'],0)
            self.assertEqual(len((host.output/'macro-snapshots.jsonl').read_text().splitlines()),3)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'reports/macro-desktop-e35c5ee5-c2e5-4c55-90a4-52b9ab0d9f94/policy-probe.jsonl').is_file(),
                         'requires the local historical telemetry archive; not distributed with source')
    def test_actual_failed_native_pair_is_discarded_before_controller_refresh_or_any_send(self):
        root=Path(__file__).resolve().parents[1]
        rows=[json.loads(s) for s in (root/'reports/macro-desktop-e35c5ee5-c2e5-4c55-90a4-52b9ab0d9f94/policy-probe.jsonl').read_text().splitlines()]
        census=next(r['observation'] for r in reversed(rows) if r['kind']=='macro_observation' and 'observation' in r)
        builder=next(r['observation'] for r in reversed(rows) if r['kind']=='native_builder_observation' and 'observation' in r)
        self.assertGreater(abs(builder['frame']-census['construction_feedback']['frame']),15)
        host=MacroHost.__new__(MacroHost);host.controller=MacroProductionController.__new__(MacroProductionController)
        host.controller.refresh=Mock();host.controller.tick=Mock();host.controller.transport=Mock();host.event=Mock()
        self.assertFalse(host.production_tick(dict(observation=census,build_observation=builder)))
        host.controller.refresh.assert_not_called();host.controller.tick.assert_not_called()
        self.assertEqual(host.controller.transport.mock_calls,[])
        host.event.assert_called_once_with('macro_sample_deferred',reason_code='macro_production_observations_too_far_apart')

    def test_stale_native_pair_defers_without_issuing_any_provider_request(self):
        audit=Mock();audit.fresh_for_game_seconds.return_value=False;event=Mock()
        self.assertFalse(request_telemetry_ready(audit,dict(game_time_seconds=100),event))
        event.assert_called_once_with('macro_decision_deferred',reason_code='macro_telemetry_frame_mismatch')
        self.assertEqual([c[0] for c in audit.mock_calls],['fresh_for_game_seconds'])
        audit.fresh_for_game_seconds.return_value=True
        self.assertTrue(request_telemetry_ready(audit,dict(game_time_seconds=101),event))

    def test_invalid_telemetry_is_not_silently_deferred(self):
        audit=MacroRequestAudit(None,Mock(),feedback_supplier=lambda:dict(observed_frame=1500),
            infrastructure_supplier=lambda:dict(source='invalid',builder_frame=1500,own_census_frame=1500))
        self.assertTrue(request_telemetry_ready(audit,dict(game_time_seconds=100),Mock()))
        with self.assertRaises(ContractError):audit.prepare(dict(game_time_seconds=100))

    def test_actual_failed_live_pair_is_deferred_for_production_not_just_infrastructure(self):
        budget=dict(observed_frame=2370)
        audit=MacroRequestAudit(None,Mock(),feedback_supplier=lambda:budget,
            production_supplier=lambda:dict(builder_frame=2436,own_census_frame=2436))
        self.assertFalse(request_telemetry_ready(audit,dict(game_time_seconds=2369/15),Mock()))
        self.assertFalse(audit.fresh_for_game_seconds(2500/15))
        budget['observed_frame']=2436
        self.assertTrue(audit.fresh_for_game_seconds(2436/15))

    def test_all_optional_feedback_frames_are_checked_in_both_directions(self):
        for name,keys in (('production_supplier',('builder_frame','own_census_frame')),
                ('construction_supplier',('builder_frame','own_census_frame')),
                ('infrastructure_supplier',('builder_frame','own_census_frame')),
                ('scouting_supplier',('observed_frame','view_frame')),
                ('regional_supplier',('observed_frame','view_frame'))):
            for frame in (1469,1516):
                audit=MacroRequestAudit(None,Mock(),**{name:lambda:dict.fromkeys(keys,frame)})
                self.assertFalse(audit.fresh_for_game_seconds(100),name)

    def test_region_availability_change_rejects_before_native_send_without_host_fault(self):
        host=MacroHost.__new__(MacroHost);host.latest=dict(paused=False,game_time_seconds=100)
        host.controller=Mock();host.controller.dispatch.side_effect=ContractError('macro_region_not_currently_available')
        host.event=Mock();host.expected_hash='hash';host.last_plan=None
        plan=Mock(expires_at_game_seconds=110,plan_id='plan')
        self.assertFalse(host.dispatch_plan(plan))
        self.assertIsNone(host.last_plan)
        host.event.assert_called_once_with('macro_plan_not_dispatched',plan_id='plan',reason_code='macro_region_not_currently_available')


if __name__=='__main__':unittest.main()
