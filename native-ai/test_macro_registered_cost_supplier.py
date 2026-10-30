import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
import macro_registered_cost_supplier as r
from test_macro_cost_supplier import fixture as cost_fixture
from test_macro_registered_queue_observation import r as observation
from test_macro_payment_observation_v2 import prepare,queue_node
from host_runtime.contracts import ContractError


class SupplierTests(unittest.TestCase):
    def setUp(self):
        self.mem,self.p,self.binding,self.universe=cost_fixture();prepare(self.mem,self.p)
        for at,value in observation.PINS.items():self.mem.put(at,bytes.fromhex(value))
        self.mem.put(self.p['game']+0x144,b'\0')
    def supplier(self):
        return r.RegisteredCostSupplier(self.mem.read,session=self.binding,identity_reader=lambda:self.binding,
            universe=self.universe,product_scope=r.RESEARCH_SCOPE)
    def test_registered_only_producer_queue_retained_but_fact_stays_closed(self):
        self.mem.word(self.p['game']+0xb4,0);queue_node(self.mem,self.p,cost=1000,paid=500)
        supplier=self.supplier();value=supplier.observe('producesickle',game_seconds=100/15)
        self.assertEqual(value['production_queue_payment_commitment_upper_bound'],500)
        self.assertTrue(value['queue_commitments']['roster_union_scan_complete'])
        self.assertFalse(value['product_fact_eligible'])
        with self.assertRaises(ContractError):supplier('producesickle',{},100/15)
    def test_wrong_scope_rejected_before_reads(self):
        self.mem.reads.clear()
        with self.assertRaises(ValueError):r.RegisteredCostSupplier(self.mem.read,session=self.binding,
            identity_reader=lambda:self.binding,universe=self.universe,product_scope='unapproved')
        self.assertEqual(self.mem.reads,[])


if __name__=='__main__':unittest.main()
