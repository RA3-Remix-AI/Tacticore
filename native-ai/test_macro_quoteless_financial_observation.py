import struct
import unittest
import macro_quoteless_financial_observation as q
import test_macro_guarded_cost_supplier as fixtures
from test_macro_payment_observation_v2 import queue_node


def native_profile(mem,p):
    ai,wrapper,data,store,vector,sides,side=0x800000,0x802000,0x803000,0x804000,0x805000,0x806000,0x807000
    mem.word(p['owner']+0x10,side);mem.word(p['owner']+0x90,ai)
    mem.zeros(ai,0x8b4);mem.word(ai,0xc60f60);mem.word(ai+8,p['owner']);mem.word(ai+0x8a8,p['owner']);mem.word(ai+0x8b0,wrapper)
    mem.zeros(wrapper,0x1c);mem.word(wrapper,data);mem.word(wrapper+0x18,0x799613e0)
    mem.zeros(data,0xf4);mem.word(data+0xec,1);mem.word(data+0xf0,sides);mem.word(sides,side)
    mem.zeros(store,0x2c);mem.word(store,0xc606b8);mem.word(0xce98ec,store)
    mem.word(store+0x24,vector);mem.word(store+0x28,vector+4);mem.word(vector,wrapper)
    mem.put(0x8d5727,bytes.fromhex('89beb0080000'));mem.put(0x844a3f,bytes.fromhex('898690000000'))

class QuotelessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.GuardedTests.setUpClass()
    def setUp(self):
        self.f=fixtures.GuardedTests();self.f.setUp();native_profile(self.f.mem,self.f.p)
    def observer(self,read=None):return q.QuotelessFinancialObserver(read or self.f.mem.read,session=self.f.binding,guard=self.f.guard)
    def test_no_legal_producer_type_no_quote_attribute_or_target_base_required(self):
        self.f.mem.word(self.f.p['templates'][0xd50c222e]+8,0x11223344)
        self.f.mem.word(self.f.p['thing']+0x36c,0xdeadbeef)
        self.f.mem.word(self.f.p['thing']+0x3b4,0xdeadbeef)
        observer=self.observer();self.f.mem.reads.clear();value=observer.observe()
        self.assertEqual(value['credits'],1235);self.assertEqual(value['production_upgrade_commitment_upper_bound'],0)
        self.assertFalse(value['unique_producer_required']);self.assertFalse(value['price_or_attribute_context_required'])
        for at in (self.f.p['thing']+0x36c,self.f.p['thing']+0x3b4,self.f.p['templates'][0x60f0b4e9]+0x304):
            self.assertFalse(any(a<=at<a+n for a,n in self.f.mem.reads))
        self.assertTrue(value['financial_collection']['exact_first_range_set_equals_final_range_set'])
        self.assertIsNotNone(observer.last_raw_manifest)
    def test_known_cash_shortfall_is_not_read_failure(self):
        queue_node(self.f.mem,self.f.p,cost=2800,paid=910)
        self.f.mem.word(self.f.p['account']+4,596);self.f.mem.word(self.f.p['account']+0x14,0)
        value=self.observer().observe();self.assertEqual((value['credits'],value['production_upgrade_commitment_upper_bound']),(596,1890))
        self.assertTrue(all(value['frame']<=f<=value['frame_after'] for f in value['component_frames']))
    def test_paid_change_between_queue_and_cash_still_rejects(self):
        node=queue_node(self.f.mem,self.f.p,cost=1000,paid=100);done=False
        def read(at,size):
            nonlocal done
            if at==self.f.p['account']+4 and not done:self.f.mem.word(node+0x68,101);done=True
            return self.f.mem.read(at,size)
        observer=self.observer(read)
        with self.assertRaisesRegex(ValueError,'sample_changed'):observer.observe()
        self.assertIsNone(observer.last_observation)
    def test_foreign_objects_read_only_owner_vtable_and_shared_next(self):
        enemy=0x950000;node=0x960000
        self.f.mem.word(enemy,q.readiness.THING_VTABLE);self.f.mem.word(enemy+0x418,0x21000);self.f.mem.word(enemy+0x7c,self.f.p['thing'])
        self.f.mem.put(node,struct.pack('<III',18,enemy,0));self.f.mem.word(self.f.p['node']+8,node)
        self.f.mem.word(self.f.p['game']+0xb4,enemy)
        observer=self.observer();self.f.mem.reads.clear();observer.observe()
        self.assertEqual({(a,n) for a,n in self.f.mem.reads if enemy<=a<enemy+0x474},
            {(enemy,4),(enemy+0x7c,4),(enemy+0x418,4)})
    def test_wrong_selected_personality_rejects_and_three_frame_still_rejects(self):
        self.f.mem.word(0x802000+0x18,123)
        with self.assertRaisesRegex(ValueError,'wrong_personality'):self.observer().observe()
        self.setUp();observer=self.observer();original=observer.payments.sample
        def late():
            value=original();self.f.mem.word(self.f.p['game']+0x50,103);return value
        observer.payments.sample=late
        with self.assertRaisesRegex(ValueError,'frame_span'):observer.observe()

if __name__=='__main__':unittest.main()
