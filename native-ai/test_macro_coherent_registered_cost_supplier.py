from pathlib import Path
import struct
import unittest
import macro_coherent_registered_cost_supplier as c
import macro_queue_owner_coverage_contract as lifecycle
import test_macro_registered_cost_supplier as registered_fixture
import macro_cost_observation_v2 as quote_v2
from test_macro_payment_observation_v2 import queue_node


class CoherentSupplierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.exe=Path('E:/RedRar3/Data/RA3_1.12.game').read_bytes()
    def setUp(self):
        fixture=registered_fixture.SupplierTests();fixture.setUp()
        self.mem,self.p,self.binding,self.universe=fixture.mem,fixture.p,fixture.binding,fixture.universe
        for label,at,size,digest in lifecycle.BLOCKS:self.mem.put(at,self.exe[at-0x400000:at-0x400000+size])
        for at,raw in quote_v2.PINS.items():self.mem.put(at,bytes.fromhex(raw))
        self.identity=self.binding
    def supplier(self):
        return c.CoherentRegisteredCostSupplier(self.mem.read,session=self.binding,
            identity_reader=lambda:self.identity,universe=self.universe,product_scope=c.RESEARCH_SCOPE)
    def test_shared_snapshot_positive_still_not_product_fact(self):
        value=self.supplier().observe('producesickle',game_seconds=100/15)
        self.assertTrue(value['cross_stage_necessary_bytes_revalidated'])
        self.assertTrue(value['owner_lifecycle_contract']['static_normal_lifecycle_support'])
        self.assertFalse(value['product_fact_eligible']);self.assertGreater(value['shared_financial_cached_ranges'],0)
    def test_independent_review_same_frame_new_queue_after_payment_scan_rejects(self):
        supplier=self.supplier();original=supplier.costs.sample
        def insert(*args,**kwargs):queue_node(self.mem,self.p,cost=1000,paid=0);return original(*args,**kwargs)
        supplier.costs.sample=insert
        with self.assertRaisesRegex(ValueError,'shared_financial_bytes_changed'):
            supplier.observe('producesickle',game_seconds=100/15)
        self.assertIsNone(supplier.last_observation)
    def test_paid_producer_or_registry_change_between_stages_reject(self):
        for domain in ('paid','producer','registry'):
            self.setUp();node=queue_node(self.mem,self.p,cost=1000,paid=250)
            supplier=self.supplier();original=supplier.costs.sample
            def changed(*args,**kwargs):
                if domain=='paid':self.mem.word(node+0x68,251)
                elif domain=='producer':self.mem.word(self.p['thing']+0xdc,18)
                else:self.mem.word(self.p['game']+0xc4,2)
                return original(*args,**kwargs)
            supplier.costs.sample=changed
            with self.subTest(domain=domain),self.assertRaises(ValueError):supplier.observe('producesickle',game_seconds=100/15)
    def test_balance_after_quote_and_target_binding_changes_reject(self):
        for domain in ('balance','cost'):
            self.setUp();supplier=self.supplier();original=supplier.delegate._producer_definitions
            def changed(*args,**kwargs):
                result=original(*args,**kwargs)
                if domain=='balance':
                    quote_resource=supplier.costs.sample('producesickle',producer_thing_id=17)['current_payment_balance']
                    # Cost fixture resource bytes are published by the native quote.
                    resource=int(quote_resource['account'],0)
                    self.mem.word(resource+4,100)
                else:self.mem.put(self.p['templates'][0x60f0b4e9]+0x304,struct.pack('<H',851))
                return result
            supplier.delegate._producer_definitions=changed
            with self.subTest(domain=domain),self.assertRaises(ValueError):supplier.observe('producesickle',game_seconds=100/15)
    def test_frame_regression_and_identity_change_latch_epoch_invalid(self):
        supplier=self.supplier();supplier.observe('producesickle',game_seconds=100/15)
        self.mem.word(self.p['game']+0x50,99)
        with self.assertRaisesRegex(ValueError,'frame_regressed'):supplier.observe('producesickle',game_seconds=99/15)
        self.mem.word(self.p['game']+0x50,100)
        with self.assertRaisesRegex(ValueError,'epoch_invalidated'):supplier.observe('producesickle',game_seconds=100/15)
        supplier=self.supplier();self.identity=c.legacy.CostSessionBinding(**dict(self.binding.__dict__,pid=124))
        with self.assertRaisesRegex(ValueError,'session_changed'):supplier.observe('producesickle',game_seconds=100/15)
        self.identity=self.binding
        with self.assertRaisesRegex(ValueError,'epoch_invalidated'):supplier.observe('producesickle',game_seconds=100/15)
    def test_only_bounded_clock_scalar_can_advance(self):
        for advance in (1,2,3):
            self.setUp();supplier=self.supplier();original=supplier.costs.sample
            def clock(*args,**kwargs):
                self.mem.word(self.p['game']+0x50,100+advance)
                return original(*args,**kwargs)
            supplier.costs.sample=clock
            if advance<=2:
                row=supplier.observe('producesickle',game_seconds=100/15)
                self.assertEqual(row['financial_window_frame_after'],100+advance)
            else:
                with self.assertRaisesRegex(ValueError,'financial_frame_span'):
                    supplier.observe('producesickle',game_seconds=100/15)

    def test_lifecycle_contract_runtime_bytes_are_not_replaced_by_static_report(self):
        supplier=self.supplier();self.mem.put(0x7c1c90,b'\0')
        with self.assertRaisesRegex(ValueError,'queue_coverage_lifecycle_bytes_changed'):
            supplier.observe('producesickle',game_seconds=100/15)


if __name__=='__main__':unittest.main()
