"""Real producer loss, conservative counts and public model feedback regression checks."""
import copy
import json
from pathlib import Path
import sys
import unittest

from .contracts import ContractError
from .macro_production_feedback import ProductionFeedback

ROOT=Path(__file__).resolve().parents[2]


def sample(frame=100,queues=(),units=(),alive=True):
    nodes=[dict(kind_raw=1,template_hash='0x2c358c61',production_id_raw=ident,
        native_cost_plus_30=220,paid_accumulator_plus_68=paid) for ident,paid in queues]
    builder=dict(source='native_macro_builder_read_only',process_writes=0,native_calls=0,frame=frame,
        builders=[dict(factory=dict(thing_id=765,type_hash='0x80d4ea1e',hp=1000.),observation_available=True,
            queue_candidate=dict(nodes=nodes))] if alive else [])
    census=dict(frame=frame,enemy_details_read=False,own_objects=(
        [dict(thing_id=765,type_hash='0x80d4ea1e',hp=1000.)] if alive else [])+
        [dict(thing_id=ident,type_hash='0x2c358c61') for ident in units])
    return builder,census


class ProductionFeedbackTests(unittest.TestCase):
    def tracker(self,**kwargs):return ProductionFeedback('produceflak',2,*sample(**kwargs))

    def test_existing_queue_and_unit_do_not_count_as_new(self):
        tracker=self.tracker(queues=[(18,10)],units=[926])
        tracker.observe(*sample(101,[(18,20)],units=[926]))
        self.assertEqual(tracker.public()['observed_new_queue_count'],0)
        self.assertEqual(tracker.public()['new_own_unit_observations'],0)
        self.assertFalse(tracker.release_required)

    def test_repeated_queue_samples_count_once_and_do_not_claim_unit_callback(self):
        tracker=self.tracker()
        tracker.observe(*sample(101,[(18,220)],units=[926]))
        tracker.observe(*sample(102,[(18,220)],units=[926]))
        tracker.observe(*sample(103,[(19,3)],units=[926]))
        self.assertTrue(tracker.release_required)
        public=tracker.public()
        self.assertEqual(public['observed_new_queue_count'],2)
        self.assertEqual(public['new_own_unit_observations'],1)
        self.assertEqual(public['fully_paid_queue_observations'],1)
        for field in ('completed_units_verified','payment_verified','exact_queue_to_unit_link_verified'):
            self.assertFalse(public[field])

    def test_producer_loss_keeps_partial_work_and_revokes_only_existing_grant(self):
        tracker=self.tracker();tracker.observe(*sample(101,[(18,220)]))
        tracker.observe(*sample(102,[(19,150)],units=[926]))
        tracker.mark_policy_released('queue_target_observed')
        public=tracker.observe(*sample(103,units=[926],alive=False))
        self.assertEqual(public['status'],'native_production_partial_producer_unavailable')
        self.assertEqual(public['incomplete_queues_with_unavailable_producer'],1)
        self.assertFalse(public['automatic_retry_allowed'])
        self.assertEqual(tracker.available_actions(['produceflak','budgetarmy']),('budgetarmy',))
        self.assertEqual(tracker.available_actions([]),())
        tracker.observe(*sample(104,units=[926],alive=True))
        self.assertTrue(tracker.public()['policy_released'])
        self.assertFalse(tracker.release_required)

    def test_loss_before_target_requires_releasing_preference(self):
        tracker=self.tracker();tracker.observe(*sample(101,[(18,150)]))
        tracker.observe(*sample(102,alive=False))
        self.assertTrue(tracker.release_required)
        self.assertFalse(tracker.public()['queue_target_observed'])

    def test_invalid_or_regressed_samples_never_mutate_tracker(self):
        tracker=self.tracker();tracker.observe(*sample(101,[(18,150)]));old=tracker.public()
        cases=[sample(99),sample(102,[(18,100)])]
        bad=sample(102);bad[1]['frame']=80;cases.append(bad)
        bad=sample(102);bad[0]['source']='model';cases.append(bad)
        bad=sample(102,[(19,250)]);cases.append(bad)
        for pair in cases:
            with self.subTest(pair=pair),self.assertRaises(ContractError):tracker.observe(*pair)
            self.assertEqual(tracker.public(),old)

    def test_no_live_factory_refuses_start_and_no_factory_enum_is_trusted(self):
        with self.assertRaisesRegex(ContractError,'no_available_producer'):self.tracker(alive=False)
        builder,census=sample();builder['builders'][0]['factory_category_raw']=4294967295
        self.assertEqual(ProductionFeedback('produceflak',2,builder,census).public()['available_producer_count'],1)

    def test_public_feedback_excludes_native_authority_and_ids(self):
        tracker=self.tracker();tracker.observe(*sample(101,[(18,150)]))
        encoded=json.dumps(tracker.public())
        for forbidden in ['thing_id','production_id','0x','765','address','template_hash']:
            self.assertNotIn(forbidden,encoded)

    def test_actual_field_replay_retains_one_unit_and_lost_incomplete_queue(self):
        from acceptance.assess_macro_production_feedback import replay
        events=[]
        result=replay(ROOT/'reports/macro-production-count-69152-20261028-v1/transport',events.append)
        feedback=result['feedback']
        self.assertEqual(result['discarded'],0)
        self.assertEqual(feedback['observed_new_queue_count'],2)
        self.assertEqual(feedback['new_own_unit_observations'],1)
        self.assertEqual(feedback['fully_paid_queue_observations'],1)
        self.assertEqual(feedback['incomplete_queues_with_unavailable_producer'],1)
        self.assertTrue(feedback['policy_released']);self.assertTrue(result['original_cleanup_verified'])
        self.assertFalse(feedback['completed_units_verified']);self.assertFalse(result['new_live_execution'])

    def test_partial_feedback_reaches_next_normal_agent_context_without_unit_jobs(self):
        sys.path.insert(0,str(ROOT/'strategy'))
        from engine import Snapshot,StrategyEngine
        from fixtures import snapshot,binding
        from battle_agent import BattleAgent
        tracker=self.tracker();tracker.observe(*sample(101,[(18,150)]))
        tracker.observe(*sample(102,alive=False))
        raw=snapshot();raw['macro_control']=dict(mode='macro_native',available_actions=list(
            tracker.available_actions(['produceflak','budgetarmy'])))
        snap=Snapshot.from_dict(raw);agent=BattleAgent(StrategyEngine(binding()))
        agent.observe(raw);agent.feedback.append(tracker.public())
        context=agent.context(snap.model_context(binding()))
        feedback=context['working_memory']['recent_execution_feedback']
        self.assertEqual(feedback[-1]['status'],'native_production_partial_producer_unavailable')
        self.assertNotIn('produceflak',context['allowed_macro_actions'])
        self.assertEqual(agent.jobs()['jobs'],[])


if __name__=='__main__':unittest.main()
