import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid

from .contracts import ContractError
from .macro_policy_runtime import BudgetScope,COMMANDER,verify_budget_scope
from .macro_production_runtime import MacroProductionController,ProductionPreferenceScope,verify_production_preference_scope
from .test_macro_production_feedback import sample

ROOT=Path(__file__).resolve().parents[2]


class ProductionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.sid=str(uuid.uuid4());self.calls=[];self.events=[]
        budget=BudgetScope('a'*64,{},('private',),dict(budgetarmy='private-army',budgeteconomy='private-economy'),{})
        self.scope=ProductionPreferenceScope(budget,'private-flak',{})
        def apply(actions,duration,ident):self.calls.append((actions,duration,ident));return dict(seq=len(self.calls))
        self.native=SimpleNamespace(session=dict(session_id=self.sid,mod_sha256='a'*64),apply=apply,close=lambda:None)
        self.controller=MacroProductionController(self.native,self.scope,self.sid,'b'*64,lambda kind,**facts:self.events.append((kind,facts)))
        self.plan=SimpleNamespace(origin='model',session_id=self.sid,commander_id=COMMANDER,player_id=3,
            based_on_game_time_seconds=100.,expires_at_game_seconds=150.,tactical_tasks=(),runtime_task=None,
            macro_actions=('produceflak','budgetarmy'),macro_production=SimpleNamespace(action='produceflak',additional_count=2),plan_id='plan1')
        self.refresh(1500)

    def refresh(self,frame,queues=(),units=(),alive=True):
        builder,census=sample(frame,queues,units,alive)
        self.controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)))

    def dispatch(self):return self.controller.dispatch(self.plan,100.,effective_hash='b'*64)

    def test_duplicate_plan_never_creates_more_production_or_extends_deadline(self):
        first=self.dispatch();self.assertEqual(self.dispatch(),first)
        self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0][1],600)
        self.assertEqual(self.controller.available_actions(100.),())
        self.assertFalse(first['native_effect_verified'])

    def test_queue_target_releases_preferences_without_unit_commands(self):
        self.dispatch();self.refresh(1510,[(18,220)],units=[926]);self.controller.tick(1510/15)
        self.assertEqual(len(self.calls),1)
        self.refresh(1520,[(19,3)],units=[926]);self.controller.tick(1520/15)
        self.assertEqual(self.calls[1][:2],([],1));self.assertFalse(self.controller.busy)
        feedback=self.controller.production_feedback()
        self.assertEqual(feedback['observed_new_queue_count'],2)
        self.assertEqual(feedback['new_own_unit_observations'],1);self.assertFalse(feedback['completed_units_verified'])
        self.controller.tick(1600/15);self.assertEqual(len(self.calls),2)
        self.assertNotIn('private',json.dumps(self.events))

    def test_producer_loss_releases_partial_goal_and_does_not_reissue(self):
        self.dispatch();self.refresh(1510,[(18,150)])
        self.refresh(1520,alive=False);self.controller.tick(1520/15)
        feedback=self.controller.production_feedback()
        self.assertEqual(feedback['release_reason'],'producer_unavailable')
        self.assertEqual(feedback['incomplete_queues_with_unavailable_producer'],1)
        self.assertFalse(feedback['automatic_retry_allowed']);self.assertEqual(len(self.calls),2)
        self.assertNotIn('produceflak',self.controller.available_actions(1520/15))

    def test_existing_target_queue_and_stale_samples_cannot_authorize_new_goal(self):
        self.refresh(1500,[(18,3)])
        with self.assertRaisesRegex(ContractError,'not_currently_available'):self.dispatch()
        self.refresh(1400)
        with self.assertRaisesRegex(ContractError,'not_currently_available'):self.dispatch()
        self.assertEqual(self.calls,[])

    def test_sequential_read_one_frame_ahead_is_fresh_but_future_samples_are_bounded(self):
        self.refresh(1501)
        self.assertIn('produceflak',self.controller.available_actions(100.))
        self.dispatch();self.assertEqual(self.calls[0][0],['produceflak','budgetarmy'])
        self.setUp();self.refresh(1516)
        self.assertNotIn('produceflak',self.controller.available_actions(100.))
        with self.assertRaisesRegex(ContractError,'not_currently_available'):self.dispatch()
        self.assertEqual(self.calls,[])

    def test_second_producer_revokes_active_single_producer_scope(self):
        self.dispatch();builder,census=sample(1510)
        other=json.loads(json.dumps(builder['builders'][0]));other['factory']['thing_id']=766
        builder['builders'].append(other);census['own_objects'].append(dict(thing_id=766,type_hash='0x80d4ea1e'))
        self.controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)))
        self.controller.tick(1510/15)
        self.assertEqual(self.calls[1][0],[])
        self.assertEqual(self.controller.production_feedback()['release_reason'],'scope_changed')

    def test_queues_observed_after_release_are_not_added_to_original_goal(self):
        self.dispatch();self.refresh(1510,[(18,220)]);self.refresh(1520,[(19,220)])
        self.controller.tick(1520/15)
        self.refresh(1600,[(20,3)])
        feedback=self.controller.production_feedback()
        self.assertEqual(feedback['observed_new_queue_count'],2)
        self.assertEqual(feedback['additional_queue_observations_after_release'],1)
        self.assertFalse(feedback['queue_target_overshot'])

    def test_unqualified_counts_wrong_profile_and_unit_tasks_refused(self):
        self.plan.macro_production.additional_count=3
        with self.assertRaisesRegex(ContractError,'not_qualified'):self.dispatch()
        self.plan.macro_production.additional_count=2;self.plan.runtime_task=object()
        with self.assertRaisesRegex(ContractError,'plan_binding'):self.dispatch()
        self.plan.runtime_task=None
        with self.assertRaisesRegex(ContractError,'plan_binding'):
            self.controller.dispatch(self.plan,100.,effective_hash='c'*64)
        self.assertEqual(self.calls,[])

    def test_expiry_releases_once_and_delivery_unknown_is_terminal(self):
        self.dispatch();self.controller.tick(140.)
        self.assertEqual(self.controller.production_feedback()['release_reason'],'expired')
        self.assertEqual(len(self.calls),2)
        self.setUp()
        def fail(*args):self.calls.append('unknown');raise RuntimeError('private diagnostic')
        self.native.apply=fail
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
        with self.assertRaisesRegex(ContractError,'stopped'):self.dispatch()
        self.assertEqual(self.calls,['unknown'])


class ProductionFieldQualificationTests(unittest.TestCase):
    def test_actual_two_queue_field_qualifies_only_observed_preference_count(self):
        budget=verify_budget_scope(ROOT/'reports/macro-policy-budget-73924-20261028-v3',
            ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',ROOT/'reports/macro-policy-expiry-71320-20261028-v1',
            ROOT/'native-ai/macro-policy-runtime/bin/policy-v16-desktop-feedback-20261028')
        scope=verify_production_preference_scope(budget,ROOT/'reports/macro-production-count-69152-20261028-v1',
            ROOT/'reports/macro-builder-static-20261028-v2')
        self.assertEqual(scope.available_counts,(2,));self.assertEqual(scope.available_actions,('budgeteconomy','budgetarmy','produceflak'))
        self.assertFalse(scope.public()['completed_units_guaranteed']);self.assertFalse(scope.public()['construction_granted'])

    def test_original_field_replay_releases_after_two_queues_and_preserves_producer_loss(self):
        test=ProductionRuntimeTests();test.setUp();controller=test.controller
        rows=[json.loads(line) for line in (ROOT/'reports/macro-production-count-69152-20261028-v1/transport/policy-probe.jsonl').read_text().splitlines()]
        census=None;started=False
        for row in rows:
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']!='native_builder_observation' or 'observation' not in row or not census:continue
            builder=row['observation'];at=builder['frame']/15
            controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)))
            if not started:
                test.plan.based_on_game_time_seconds=at;test.plan.expires_at_game_seconds=at+60
                controller.dispatch(test.plan,at,effective_hash='b'*64);started=True
            controller.tick(at)
        self.assertEqual(len(test.calls),2);self.assertEqual(test.calls[1][0],[])
        public=controller.production_feedback()
        self.assertEqual(public['observed_new_queue_count'],2);self.assertEqual(public['new_own_unit_observations'],1)
        self.assertEqual(public['incomplete_queues_with_unavailable_producer'],1);self.assertEqual(public['release_reason'],'queue_target_observed')


if __name__=='__main__':unittest.main()
