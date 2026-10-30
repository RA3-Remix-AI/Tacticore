"""Artificial own queues only; no process access."""
import struct
import unittest

import macro_payment_observation as p
from test_macro_cost_observation import fixture as cost_fixture


def fixture():
    mem, state = cost_fixture()
    for at, value in p.PINS.items(): mem.put(at, bytes.fromhex(value))
    module = state['interface']-0x24
    mem.word(state['vector']+4, module); mem.word(state['vector']+8, 0)
    state['module'] = module
    return mem, state


def queue_node(mem, state, at=0x780000, *, cost=1000, paid=250, kind=1, module=None):
    module = state['module'] if module is None else module
    mem.zeros(at, 0x70); mem.word(at, p.QUEUE_NODE_VTABLE)
    mem.word(at+4, module); mem.word(at+8, 17); mem.word(at+0xc, kind)
    mem.word(at+0x18, 19); mem.word(at+0x30, cost); mem.word(at+0x68, paid)
    mem.word(module+0x34, at); mem.word(module+0x38, at)
    return at


class PaymentTests(unittest.TestCase):
    def setUp(self): self.mem, self.state=fixture()
    def observer(self, read=None):
        return p.PaymentCommitmentObserver(read or self.mem.read,self.state['owner'],
            executable_sha256=p.EXE_SHA256,expected_owner_index=3)
    def sample(self): return self.observer().sample()

    def test_all_own_queues_sum_real_cost_minus_paid_not_global_reservation(self):
        queue_node(self.mem,self.state)
        result=self.sample()
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],750)
        self.assertTrue(result['all_current_own_production_queues_enumerated'])
        self.assertIsNone(result['existing_native_payment_commitment_upper_bound'])
        self.assertFalse(result['existing_native_payment_commitment_upper_bound_verified'])
        self.assertFalse(result['queue_external_payment_obligations_covered'])
        self.assertFalse(result['future_autonomous_spending_controlled'])

    def test_observed_empty_all_module_queues_zero_is_scope_specific(self):
        result=self.sample()
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],0)
        self.assertIsNone(result['existing_native_payment_commitment_upper_bound'])
        self.assertEqual(len(result['queues']),1)

    def test_all_production_modules_not_just_primary_wrapper(self):
        extra=0x790000;self.mem.zeros(extra,0x138)
        self.mem.word(extra,p.PRODUCTION_MODULE_VTABLE)
        self.mem.word(extra+8,self.state['thing']);self.mem.word(extra+0x24,0xc3f8c8)
        self.mem.word(self.state['vector']+8,extra);self.mem.word(self.state['vector']+12,0)
        queue_node(self.mem,self.state)
        queue_node(self.mem,self.state,0x781000,cost=500,paid=100,kind=2,module=extra)
        result=self.sample()
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],1150)
        self.assertEqual(len(result['queues']),2)

    def test_upgrade_queue_cost_also_retained(self):
        queue_node(self.mem,self.state,cost=300,paid=0,kind=2)
        self.assertEqual(self.sample()['queues'][0]['nodes'][0]['kind'],2)

    def test_node_chain_total_and_partial_payment(self):
        first=queue_node(self.mem,self.state,cost=1000,paid=1000)
        second=queue_node(self.mem,self.state,0x781000,cost=700,paid=200)
        self.mem.word(self.state['module']+0x34,first)
        self.mem.word(first+0x54,second);self.mem.word(second+0x58,first)
        self.assertEqual(self.sample()['production_queue_payment_commitment_upper_bound'],500)

    def test_foreign_owner_rejected_before_module_and_money_reads(self):
        self.mem.word(self.state['thing']+0x418,0x21000)
        with self.assertRaisesRegex(ValueError,'foreign_thing'):self.sample()
        self.assertFalse(any(at==self.state['thing']+0x310 for at,_ in self.mem.reads))

    def test_unknown_queue_kind_is_not_ignored(self):
        queue_node(self.mem,self.state,kind=3)
        with self.assertRaisesRegex(ValueError,'kind_unknown'):self.sample()

    def test_unmapped_module_vector_is_not_empty_producer_set(self):
        self.mem.word(self.state['thing']+0x310,0)
        with self.assertRaises(ValueError):self.sample()

    def test_duplicate_module_and_node_cycle_rejected(self):
        self.mem.word(self.state['vector']+8,self.state['module'])
        with self.assertRaisesRegex(ValueError,'duplicate_module'):self.sample()
        self.mem.word(self.state['vector']+8,0)
        node=queue_node(self.mem,self.state);self.mem.word(node+0x54,node)
        with self.assertRaisesRegex(ValueError,'cycle_or_duplicate'):self.sample()

    def test_node_back_module_owner_and_tail_mismatch_rejected(self):
        for off,value in [(4,0x700000),(0x58,1)]:
            self.mem,self.state=fixture();node=queue_node(self.mem,self.state)
            self.mem.word(node+off,value)
            with self.assertRaisesRegex(ValueError,'node_binding'):self.sample()
        self.mem,self.state=fixture();queue_node(self.mem,self.state)
        self.mem.word(self.state['module']+0x38,0x781000)
        with self.assertRaisesRegex(ValueError,'tail_mismatch'):self.sample()

    def test_paid_above_cost_and_signed_negative_cost_rejected(self):
        for cost,paid in [(100,101),(0xffffffff,0)]:
            self.mem,self.state=fixture();queue_node(self.mem,self.state,cost=cost,paid=paid)
            with self.assertRaisesRegex(ValueError,'cost_paid_bounds'):self.sample()

    def test_signature_and_dynamic_mutation_rejected(self):
        self.mem.put(0x70f440,b'\x00')
        with self.assertRaisesRegex(ValueError,'payment_signature'):self.observer()
        self.mem,self.state=fixture();node=queue_node(self.mem,self.state);observer=self.observer();calls=0
        def changing(at,size):
            nonlocal calls
            if at==node:
                calls+=1
                if calls>1:
                    raw=bytearray(self.mem.read(at,size));struct.pack_into('<I',raw,0x68,251);return bytes(raw)
            return self.mem.read(at,size)
        observer.read=changing
        with self.assertRaisesRegex(ValueError,'sample_changed'):observer.sample()

    def test_remaining_upper_invariant_for_arbitrary_payment_steps(self):
        for total in [0,1,850,2800,65535]:
            paid=0
            for target_paid in [0,total//3,total//2,total]:
                self.assertLessEqual(target_paid-paid,p.remaining_queue_commitment(total,paid))
                paid=target_paid
            self.assertEqual(p.remaining_queue_commitment(total,paid),0)


if __name__=='__main__':unittest.main()
