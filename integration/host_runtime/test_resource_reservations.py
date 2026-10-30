"""Pure, synthetic cost/reservation facts; no native reader or real grant."""
from dataclasses import replace
import copy
import json
import unittest
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor

from .contracts import ContractError
from .resource_reservations import (NativeCostFact,ResourceSettlementFact,ResourceReservationStore,
    CurrentQueueBudgetFact,CURRENT_QUEUE_BUDGET_SOURCE,validate_cost,COST_SOURCE,SETTLEMENT_SOURCES)

IDENTITY=('0x10000','0x20000','0x30000')


def cost(session='session',action='buildpower',template='0xcf8d9f20',frame=1500):
    return NativeCostFact(session,3,action,template,COST_SOURCE,frame,1000,5000,500,IDENTITY,
        upper_cost_verified=True,credits_verified=True,existing_native_payment_commitment_upper_bound_verified=True)


def queue_cost(session='session'):
    return CurrentQueueBudgetFact(session,3,'buildpower','0xcf8d9f20',CURRENT_QUEUE_BUDGET_SOURCE,1500,1000,5000,500,
        IDENTITY,765,'0xc16ff13f',upper_cost_verified=True,credits_verified=True,
        production_upgrade_queue_payment_commitment_upper_bound_verified=True,all_owned_production_updates_observed=True,
        all_production_and_upgrade_nodes_observed=True,loaded_target_schema_verified=True,
        native_quote_context_verified=True,producer_definition_verified=True)


class ResourceReservationTests(unittest.TestCase):
    def setUp(self):
        self.command=str(uuid.uuid4());self.store=ResourceReservationStore('session');self.fact=cost()

    def validate(self,fact):
        return validate_cost(fact,session_id='session',player_id=3,action='buildpower',template_hash='0xcf8d9f20',
            game_identity=IDENTITY,game_seconds=100.,component_frames=(1500,1501))

    def start(self):
        self.store.reserve('plan',self.command,self.fact);self.store.delivery_started(self.command)
        self.store.acknowledged(self.command,1)

    def settlement(self,kind,**kwargs):
        return ResourceSettlementFact(str(uuid.uuid4()),'session',3,'plan',self.command,'buildpower','0xcf8d9f20',kind,
            SETTLEMENT_SOURCES[kind],1502,1,verified=True,**kwargs)

    def test_unknown_stale_foreign_partial_and_untyped_cost_facts_fail_closed(self):
        self.assertIs(self.validate(self.fact),self.fact)
        for change in (dict(session_id='foreign'),dict(player_id=2),dict(action='buildbarracks'),dict(template_hash='foreign'),
                dict(source='static_sdk_cost'),dict(frame=1441),dict(upper_cost=True),dict(credits=True),
                dict(upper_cost_verified=False),dict(credits_verified=None),dict(existing_native_payment_commitment_upper_bound_verified=False),
                dict(existing_native_payment_commitment_upper_bound=-1),dict(additional_count=2),dict(game_identity=('foreign',)*3)):
            with self.subTest(change=change),self.assertRaises(ContractError):self.validate(replace(self.fact,**change))
        with self.assertRaises(ContractError):self.validate(self.fact.__dict__)
        with self.assertRaisesRegex(ContractError,'insufficient'):self.validate(replace(self.fact,credits=1200,existing_native_payment_commitment_upper_bound=500))

    def test_one_pending_plan_and_command_idempotence(self):
        first=self.store.reserve('plan',self.command,self.fact)
        self.assertEqual(first,self.store.reserve('plan',self.command,self.fact))
        with self.assertRaisesRegex(ContractError,'id_conflict'):
            self.store.reserve('plan',self.command,replace(self.fact,upper_cost=999))
        with self.assertRaisesRegex(ContractError,'unresolved'):self.store.reserve('other',str(uuid.uuid4()),self.fact)
        self.store.delivery_started(self.command)
        with self.assertRaisesRegex(ContractError,'transition_refused'):self.store.delivery_started(self.command)

    def test_delivery_unknown_remains_held_despite_stop_clear_or_queue_fact(self):
        self.start();self.store.delivery_unknown(self.command)
        for fact in (self.settlement('preference_cleared',clear_seq=2),
                self.settlement('queue_accepted',queue_key=(12,3),native_cost=1000,paid_amount=0)):
            with self.assertRaisesRegex(ContractError,'settlement_unverified'):self.store.settle(fact)
        self.assertEqual(self.store.public(self.command)['held_reservation_amount'],1000)
        with self.assertRaises(ContractError):self.store.delivery_started(self.command)

    def test_native_ack_and_flag_clear_do_not_release_money_without_acceptance_audit(self):
        self.start();self.store.settle(self.settlement('preference_cleared',clear_seq=2))
        self.assertTrue(self.store.unresolved)
        self.assertEqual(self.store.public(self.command)['held_reservation_amount'],1000)
        self.store.settle(self.settlement('no_queue_accepted'))
        public=self.store.public(self.command)
        self.assertEqual(public['status'],'released_without_queue');self.assertEqual(public['held_reservation_amount'],0)
        self.assertFalse(public['budget_hard_cap_verified']);self.assertFalse(public['native_ai_autonomous_spending_controlled'])

    def test_raw_queue_paid_field_is_not_cash_attribution_or_reservation_release(self):
        self.start();self.store.settle(self.settlement('queue_accepted',queue_key=(12,3),native_cost=900,paid_amount=900))
        self.assertEqual(self.store.public(self.command)['actual_cash_payment_verified_amount'],0)
        with self.assertRaisesRegex(ContractError,'payment_attribution'):
            self.store.settle(self.settlement('payment_consumed',queue_key=(12,3),native_cost=900,paid_amount=900))
        self.store.settle(self.settlement('payment_consumed',queue_key=(12,3),native_cost=900,paid_amount=900,
            cash_attribution_verified=True))
        self.assertTrue(self.store.unresolved)
        self.store.settle(self.settlement('preference_cleared',clear_seq=2))
        self.assertEqual(self.store.public(self.command)['status'],'consumed')

    def test_partial_payment_monotonic_bound_and_queue_identity(self):
        self.start();self.store.settle(self.settlement('queue_accepted',queue_key=(12,3),native_cost=1000,paid_amount=0))
        self.store.settle(self.settlement('payment_consumed',queue_key=(12,3),native_cost=1000,paid_amount=100,
            cash_attribution_verified=True))
        for change in (dict(paid_amount=99),dict(native_cost=1100),dict(queue_key=(12,4)),dict(source='raw_paid_accumulator')):
            fact=self.settlement('payment_consumed',queue_key=(12,3),native_cost=1000,paid_amount=100,cash_attribution_verified=True)
            with self.subTest(change=change),self.assertRaises(ContractError):self.store.settle(replace(fact,**change))
        self.assertEqual(self.store.public(self.command)['held_reservation_amount'],1000)

    def test_cancel_and_refund_are_independent_cash_facts(self):
        self.start();self.store.settle(self.settlement('queue_accepted',queue_key=(12,3),native_cost=1000,paid_amount=100))
        self.store.settle(self.settlement('queue_cancelled',queue_key=(12,3),native_cost=1000,paid_amount=100,
            cash_attribution_verified=True))
        self.assertTrue(self.store.unresolved)
        self.store.settle(self.settlement('preference_cleared',clear_seq=2))
        public=self.store.public(self.command);self.assertEqual(public['status'],'cancelled');self.assertIsNone(public['refund_verified_amount'])
        self.store.settle(self.settlement('refund_observed',queue_key=(12,3),refund_amount=80,cash_attribution_verified=True))
        self.assertEqual(self.store.public(self.command)['refund_verified_amount'],80)

    def test_fact_idempotence_conflict_stale_or_foreign_receipts(self):
        self.start();fact=self.settlement('preference_cleared',clear_seq=2)
        first=self.store.settle(fact);self.assertEqual(first,self.store.settle(fact))
        with self.assertRaisesRegex(ContractError,'fact_id_conflict'):self.store.settle(replace(fact,frame=1503))
        for change in (dict(session_id='foreign'),dict(native_seq=2),dict(frame=1499),dict(source='model_asserted_clear')):
            with self.subTest(change=change),self.assertRaises(ContractError):self.store.settle(replace(fact,fact_id=str(uuid.uuid4()),**change))

    def test_snapshot_roundtrip_nonterminal_is_unknown_and_no_delivery_retry(self):
        self.start();snapshot=json.loads(json.dumps(self.store.snapshot()))
        restored=ResourceReservationStore.from_snapshot(snapshot)
        self.assertEqual(restored.public(self.command)['status'],'unknown')
        with self.assertRaises(ContractError):restored.delivery_started(self.command)
        with self.assertRaises(ContractError):restored.settle(self.settlement('preference_cleared',clear_seq=2))
        with self.assertRaises(ContractError):ResourceReservationStore.from_snapshot(dict(snapshot,schema_version=True))

    def test_ambiguous_v1_cost_facts_are_not_silently_promoted_to_v2(self):
        empty=dict(schema_version=1,session_id='session',rows={},fact_ids={})
        self.assertEqual(ResourceReservationStore.from_snapshot(empty).snapshot()['schema_version'],2)
        self.start();old=dict(self.store.snapshot(),schema_version=1)
        with self.assertRaisesRegex(ContractError,'legacy_cost_semantics_unverified'):ResourceReservationStore.from_snapshot(old)
        self.assertEqual(old['rows'][self.command]['status'],'acknowledged')
        with self.assertRaisesRegex(ContractError,'blocked_native_cost_reservation_unverified'):
            self.validate(replace(self.fact,source='native_read_only_target_upper_cost_and_player_resources_v1'))

    def test_persistence_failure_happens_before_state_or_native_delivery_can_advance(self):
        writes=[]
        def persist(value):writes.append(value);raise OSError('disk unavailable')
        store=ResourceReservationStore('session',persist=persist)
        with self.assertRaises(OSError):store.reserve('plan',self.command,self.fact)
        self.assertFalse(store.rows);self.assertEqual(len(writes),1)

    def test_concurrent_reservations_have_only_one_winner(self):
        barrier=threading.Barrier(2)
        def attempt(number):
            barrier.wait()
            try:self.store.reserve('plan'+str(number),str(uuid.uuid4()),self.fact);return True
            except ContractError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,(1,2)))
        self.assertEqual(results.count(True),1);self.assertEqual(len(self.store.rows),1)

    def test_persisted_terminal_receipts_restore_but_corrupted_resource_fields_do_not(self):
        self.start();self.store.settle(self.settlement('preference_cleared',clear_seq=2))
        fact=self.settlement('no_queue_accepted');self.store.settle(fact)
        snapshot=json.loads(json.dumps(self.store.snapshot()));restored=ResourceReservationStore.from_snapshot(snapshot)
        self.assertFalse(restored.unresolved);self.assertEqual(restored.settle(fact)['status'],'released_without_queue')
        for change in (dict(paid_amount=-1),dict(native_seq=True),dict(upper_cost=True),dict(unrecognized=True)):
            broken=copy.deepcopy(snapshot);broken['rows'][self.command].update(change)
            with self.subTest(change=change),self.assertRaises(ContractError):ResourceReservationStore.from_snapshot(broken)

    def test_public_projection_does_not_expose_private_ids_or_claim_total_spending_cap(self):
        from .resource_reservations import compact_reservation
        self.start();raw=dict(self.store.public(self.command),private_address='private',command_id=self.command,
            budget_hard_cap_verified=True,native_ai_autonomous_spending_controlled=True)
        value=compact_reservation(raw)
        self.assertNotIn('private',json.dumps(value));self.assertNotIn('command_id',value)
        self.assertFalse(value['budget_hard_cap_verified']);self.assertFalse(value['native_ai_autonomous_spending_controlled'])
        with self.assertRaises(ContractError):compact_reservation(dict(raw,held_reservation_amount=0))

    def test_no_queue_or_clear_fact_cannot_smuggle_a_queue_or_cash_claim(self):
        self.start()
        fact=self.settlement('preference_cleared',clear_seq=2,queue_key=(12,3))
        with self.assertRaisesRegex(ContractError,'settlement_shape'):self.store.settle(fact)
        self.assertFalse(self.store.public(self.command)['preference_release_independently_verified'])

    def test_narrow_queue_scope_is_distinct_and_does_not_grant_global_or_single_admission_cap(self):
        fact=queue_cost()
        validate_cost(fact,session_id='session',player_id=3,action='buildpower',template_hash='0xcf8d9f20',
            game_identity=IDENTITY,game_seconds=100.,producer_ids=(765,))
        self.store.reserve('plan',self.command,fact)
        public=self.store.public(self.command)
        self.assertEqual(public['funding_scope'],'current_owned_production_upgrade_queues')
        self.assertFalse(public['host_influenced_spending_cap_verified']);self.assertFalse(public['single_new_request_hard_limit_verified'])
        restored=ResourceReservationStore.from_snapshot(json.loads(json.dumps(self.store.snapshot())))
        self.assertEqual(restored.public(self.command)['status'],'unknown')
        with self.assertRaises(ContractError):self.validate(replace(self.fact,existing_native_payment_commitment_upper_bound_verified=False))

    def test_partial_queue_coverage_wrong_producer_or_premature_hard_cap_claim_is_refused(self):
        fact=queue_cost()
        for change in (dict(all_owned_production_updates_observed=False),dict(all_production_and_upgrade_nodes_observed=False),
                dict(loaded_target_schema_verified=False),dict(native_quote_context_verified=False),dict(producer_definition_verified=False),
                dict(producer_thing_id=900),dict(producer_type_hash='0xd50c222e'),dict(single_new_request_hard_limit_verified=True),
                dict(native_ai_autonomous_spending_covered=True),dict(source=COST_SOURCE),
                dict(production_upgrade_queue_payment_commitment_upper_bound_verified=False)):
            with self.subTest(change=change),self.assertRaises(ContractError):
                validate_cost(replace(fact,**change),session_id='session',player_id=3,action='buildpower',template_hash='0xcf8d9f20',
                    game_identity=IDENTITY,game_seconds=100.,producer_ids=(765,))

