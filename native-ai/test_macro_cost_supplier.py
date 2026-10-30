"""Strict binding tests using artificial native state and backend identity."""
import struct
import unittest
import sys
from pathlib import Path

# Match the actual macro_host.py import namespace, not integration.host_runtime.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))

import macro_cost_supplier as s
from test_macro_payment_observation import fixture as payment_fixture,queue_node
from test_macro_cost_upper_contract import inventory


def fixture():
    mem,p=payment_fixture()
    for i,(key,template) in enumerate(p['templates'].items()):
        definition=p['definitions'][key];transaction=0x7a0000+0x40*i;array=transaction+8
        mem.put(template+0x304,struct.pack('<H',850));mem.word(definition+0x198,transaction)
        mem.put(transaction,struct.pack('<4I',1,array,0,850))
        mem.put(definition+0x88,struct.pack('<f',10 if key in (0x60f0b4e9,0x522bcb61) else 0))
    session=s.CostSessionBinding('artificial-session',123,456,s.cost.EXE_SHA256,
        s.assets.PACKAGE_SHA256,3,(hex(p['game']),hex(p['owner']),hex(p['factory'])))
    mem.word(p['definition']+0x30,2)
    return mem,p,session,s.CompiledCostUniverse(inventory())


class SupplierTests(unittest.TestCase):
    def setUp(self):self.mem,self.p,self.session,self.universe=fixture()
    def supplier(self,identity_reader=None):
        return s.StrictNativeCostSupplier(self.mem.read,session=self.session,
            identity_reader=identity_reader or (lambda:self.session),universe=self.universe)
    def test_loaded_money_fields_base_balance_and_all_queue_debt_bound(self):
        queue_node(self.mem,self.p,cost=1000,paid=500)
        result=self.supplier().observe('producesickle',game_seconds=100/15)
        self.assertTrue(result['loaded_target_binding']['loaded_target_cost_fields_match_audited_asset'])
        self.assertEqual(result['loaded_target_binding']['native_amount'],850)
        self.assertEqual(result['credits'],1235)
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],500)
        self.assertEqual(result['current_balance_after_accepted_production_queues'],735)
        self.assertFalse(result['current_balance_covers_one_conditional_queue'])
        self.assertIsNone(result['existing_native_payment_commitment_upper_bound'])
        self.assertFalse(result['existing_native_payment_commitment_upper_bound_verified'])
        self.assertFalse(result['host_influence_total_spend_hard_cap_verified'])
    def test_native_price_drift_and_resource_account_change_rejected(self):
        template=self.p['templates'][0x60f0b4e9]
        self.mem.put(template+0x304,struct.pack('<H',851))
        with self.assertRaisesRegex(ValueError,'native_cost_drift'):
            self.supplier().observe('producesickle',game_seconds=100/15)
        self.mem.put(template+0x304,struct.pack('<H',850))
        definition=self.p['definitions'][0x60f0b4e9]
        transaction=s.cost._word(self.mem.read,definition+0x198)
        self.mem.word(transaction+8,1)
        with self.assertRaisesRegex(ValueError,'native_cost_drift'):
            self.supplier().observe('producesickle',game_seconds=100/15)
    def test_multiple_transaction_not_silently_first_entry_only(self):
        definition=self.p['definitions'][0x60f0b4e9]
        transaction=s.cost._word(self.mem.read,definition+0x198);self.mem.word(transaction,2)
        with self.assertRaisesRegex(ValueError,'single_resource'):
            self.supplier().observe('producesickle',game_seconds=100/15)
    def test_wrong_pid_creation_session_package_and_player_identity_rejected(self):
        for key,value in [('pid',124),('process_creation_filetime',457),('session_id','other')]:
            changed=s.CostSessionBinding(**dict(self.session.__dict__,**{key:value}))
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError,'process_or_session'):
                    self.supplier(lambda:changed)
        changed=s.CostSessionBinding(**dict(self.session.__dict__,package_sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'exact_session'):self.supplier(lambda:changed)
    def test_dictionary_cannot_replace_backend_identity_or_universe(self):
        with self.assertRaisesRegex(ValueError,'exact_session'):
            self.supplier(lambda:dict(self.session.__dict__))
        with self.assertRaisesRegex(ValueError,'trusted_dependencies'):
            s.StrictNativeCostSupplier(self.mem.read,session=self.session,
                identity_reader=lambda:self.session,universe=inventory())
    def test_stale_component_and_clock_rejected(self):
        for seconds,frames in [(100/15,(84,)),(100/15,(116,)),(0,())]:
            with self.subTest(seconds=seconds,frames=frames):
                with self.assertRaisesRegex(ValueError,'stale_or_incoherent'):
                    self.supplier().observe('producesickle',game_seconds=seconds,component_frames=frames)
    def test_building_requires_zero_buildtime_soviet_unpack_branch(self):
        self.mem.word(self.p['thing']+4,self.p['templates'][0xc16ff13f])
        self.mem.word(self.p['definition']+0x30,1)
        result=self.supplier().observe('buildrefinery',game_seconds=100/15)
        self.assertEqual(result['loaded_target_binding']['native_build_time'],0)
        self.mem.put(self.p['definitions'][0xc45aaeab]+0x88,struct.pack('<f',1))
        with self.assertRaisesRegex(ValueError,'unpack_payment_context'):
            self.supplier().observe('buildrefinery',game_seconds=100/15)
    def test_missing_producer_not_filled_from_caller_sample(self):
        self.mem.word(self.p['thing']+4,self.p['templates'][0xcf8d9f20])
        with self.assertRaisesRegex(ValueError,'unique_current_producer'):
            self.supplier().observe('producesickle',game_seconds=100/15)
    def test_v2_global_supplier_rejects_queue_only_even_empty_queue(self):
        from host_runtime.contracts import ContractError
        with self.assertRaisesRegex(ContractError,'blocked_native_cost_reservation_unverified'):
            self.supplier()('producesickle',{},100/15)

    def test_v3_fact_is_separate_explicit_scope_and_never_claims_hard_count_cap(self):
        from host_runtime.resource_reservations import CurrentQueueBudgetFact,validate_cost
        # Artificial-memory backend fixture replaces the offline archive audit.
        # No production caller can get verified archives from a model dictionary.
        self.universe._archives_verified=True
        reader=s.StrictNativeCostSupplier(self.mem.read,session=self.session,
            identity_reader=lambda:self.session,universe=self.universe,
            product_scope='current_owned_production_upgrade_queues_v3')
        fact=reader('producesickle',{},100/15)
        self.assertIs(type(fact),CurrentQueueBudgetFact)
        self.assertFalse(fact.single_new_request_hard_limit_verified)
        self.assertFalse(fact.repair_and_ability_spending_covered)
        self.assertFalse(fact.native_ai_autonomous_spending_covered)
        self.assertEqual(fact.production_upgrade_queue_payment_commitment_upper_bound,0)
        self.assertIs(validate_cost(fact,session_id=self.session.session_id,player_id=3,
            action='producesickle',template_hash='0x60f0b4e9',game_identity=self.session.game_identity,
            game_seconds=100/15,producer_ids=(17,)),fact)

    def test_unverified_archive_dictionary_cannot_enable_v3(self):
        from host_runtime.contracts import ContractError
        reader=s.StrictNativeCostSupplier(self.mem.read,session=self.session,
            identity_reader=lambda:self.session,universe=self.universe,
            product_scope='current_owned_production_upgrade_queues_v3')
        with self.assertRaisesRegex(ContractError,'blocked_native_cost_reservation_unverified'):
            reader('producesickle',{},100/15)

    def test_actual_host_namespace_and_native_sample_component_names(self):
        from host_runtime.resource_reservations import CurrentQueueBudgetFact,validate_cost
        self.assertEqual(CurrentQueueBudgetFact.__module__,'host_runtime.resource_reservations')
        self.universe._archives_verified=True
        reader=s.StrictNativeCostSupplier(self.mem.read,session=self.session,
            identity_reader=lambda:self.session,universe=self.universe,
            product_scope='current_owned_production_upgrade_queues_v3')
        native=dict(observation=dict(frame=100,construction_feedback=dict(frame=100)),
            build_observation=dict(frame=100),dependency=dict(frame=100),readiness=dict(frame=100))
        fact=reader('producesickle',native,100/15)
        self.assertIs(type(fact),CurrentQueueBudgetFact)
        validate_cost(fact,session_id=self.session.session_id,player_id=3,action='producesickle',
            template_hash='0x60f0b4e9',game_identity=self.session.game_identity,game_seconds=100/15,
            component_frames=(100,100,100,100,100),producer_ids=(17,))
        native['observation']['construction_feedback']['frame']=84
        with self.assertRaisesRegex(ValueError,'stale_or_incoherent'):
            reader('producesickle',native,100/15)


if __name__=='__main__':unittest.main()
