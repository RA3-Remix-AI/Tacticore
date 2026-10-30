"""Artificial complete live roster, no native/process work."""
import struct
import unittest
import macro_payment_observation_v2 as v2
from test_macro_payment_observation import fixture as baseline_fixture,queue_node as old_node


def prepare(mem,p):
    for at,value in v2.PINS.items():mem.put(at,bytes.fromhex(value))
    mem.word(p['game']+0xb4,p['thing']);mem.word(p['thing']+0x7c,0)
    return mem,p


def fixture():return prepare(*baseline_fixture())


def queue_node(mem,p,*args,**kwargs):
    at=old_node(mem,p,*args,**kwargs);kind=kwargs.get('kind',1)
    mem.word(at+(0x10 if kind==1 else 0x14),p['templates'][0x60f0b4e9]);return at


class PaymentV2Tests(unittest.TestCase):
    def setUp(self):self.mem,self.p=fixture()
    def observer(self,read=None):
        return v2.PaymentCommitmentObserverV2(read or self.mem.read,self.p['owner'],
            executable_sha256=v2.EXE_SHA256,expected_owner_index=3)
    def sample(self):return self.observer().sample()
    def test_scan_sum_does_not_claim_field_coverage_or_global_obligations(self):
        queue_node(self.mem,self.p);result=self.sample()
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],750)
        self.assertTrue(result['roster_scan_complete']);self.assertTrue(result['queue_scan_complete'])
        self.assertFalse(result['all_current_own_production_queues_enumerated'])
        self.assertFalse(result['field_qualified_complete_queue_coverage'])
        self.assertFalse(result['removed_live_list_owners_payment_obligations_covered'])
        self.assertIsNone(result['existing_native_payment_commitment_upper_bound'])
    def test_empty_queues_zero_is_read_fact_not_static_default(self):
        result=self.sample();self.assertEqual(result['production_queue_payment_commitment_upper_bound'],0)
        self.assertEqual(result['own_object_count'],1);self.assertEqual(len(result['queues']),1)
    def test_zero_hp_is_not_read_or_excluded(self):
        queue_node(self.mem,self.p);self.mem.put(self.p['body']+4,struct.pack('<f',0))
        self.mem.reads.clear();result=self.sample()
        self.assertEqual(result['own_object_count'],1)
        self.assertFalse(any(at==self.p['body']+4 for at,n in self.mem.reads))
        self.assertFalse(any(at==self.p['thing']+0x38 for at,n in self.mem.reads))
    def test_foreign_thing_has_only_topology_vtable_owner_access(self):
        enemy=0x8a0000
        self.mem.word(enemy,v2.readiness.THING_VTABLE);self.mem.word(enemy+0x7c,self.p['thing'])
        self.mem.word(enemy+0x418,0x21000);self.mem.word(self.p['game']+0xb4,enemy)
        self.mem.reads.clear();result=self.sample()
        self.assertEqual(result['foreign_owner_skipped_count'],1)
        foreign_reads={(at,n) for at,n in self.mem.reads if enemy<=at<enemy+0x474}
        self.assertEqual(foreign_reads,{(enemy,4),(enemy+0x7c,4),(enemy+0x418,4)})
    def test_own_mobile_module_outside_player_vector_is_included(self):
        thing,registry,vector,module,template=0x850000,0x860000,0x870000,0x880000,0x890000
        self.mem.zeros(thing,0x474);self.mem.word(thing,v2.readiness.THING_VTABLE)
        self.mem.word(thing+0x418,self.p['owner']);self.mem.word(thing+0xdc,18)
        self.mem.word(thing+4,template);self.mem.zeros(template,12);self.mem.word(template+8,0xa08aabd3)
        self.mem.zeros(registry,12);self.mem.put(registry,struct.pack('<III',18,thing,0))
        self.mem.word(self.p['node']+8,registry)
        self.mem.word(self.p['thing']+0x7c,thing);self.mem.word(thing+0x310,vector)
        self.mem.zeros(vector,8);self.mem.word(vector,module);self.mem.zeros(module,0x138)
        self.mem.word(module,v2.baseline.PRODUCTION_MODULE_VTABLE);self.mem.word(module+8,thing)
        self.mem.word(module+0x24,v2.readiness.PRODUCTION_INTERFACE_VTABLE)
        queue_node(self.mem,self.p,cost=1000,paid=250)
        at=queue_node(self.mem,self.p,0x781000,cost=400,paid=50,module=module)
        self.mem.word(at+8,18)
        result=self.sample();self.assertEqual(result['own_object_count'],2)
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],1100)
        self.assertEqual(len(result['queues']),2)
    def test_progress_and_tick_are_not_read_or_stability_dependencies(self):
        at=queue_node(self.mem,self.p);reads=[]
        def read(address,size):
            reads.append((address,size))
            if address in (at+0x1c,at+0x20,at+0x24):raise AssertionError('unused_progress_read')
            return self.mem.read(address,size)
        result=self.observer(read).sample();self.assertTrue(result['necessary_fields_stable'])
        self.assertFalse(any(address==at and size==0x70 for address,size in reads))
    def test_paid_change_still_rejects_without_min_paid_fallback(self):
        at=queue_node(self.mem,self.p);count=0
        def read(address,size):
            nonlocal count
            if address==at+0x68:
                count+=1
                if count>1:return struct.pack('<I',251)
            return self.mem.read(address,size)
        with self.assertRaisesRegex(ValueError,'payment_v2_necessary_bytes_changed'):self.observer(read).sample()
    def test_cost_queue_link_and_roster_changes_reject(self):
        for off in (0x30,0x54,0x58):
            self.mem,self.p=fixture();at=queue_node(self.mem,self.p);count=0
            def read(address,size):
                nonlocal count
                if address==at+off:
                    count+=1
                    if count>1:return struct.pack('<I',123)
                return self.mem.read(address,size)
            with self.subTest(off=off),self.assertRaisesRegex(ValueError,'necessary_bytes_changed'):self.observer(read).sample()
        self.mem,self.p=fixture();count=0
        def roster_change(address,size):
            nonlocal count
            if address==self.p['game']+0xb4:
                count+=1
                if count>1:return struct.pack('<I',0)
            return self.mem.read(address,size)
        with self.assertRaisesRegex(ValueError,'necessary_bytes_changed'):self.observer(roster_change).sample()
    def test_upgrade_and_corrupt_kind_owner_registry_are_explicit(self):
        at=queue_node(self.mem,self.p,kind=2);self.assertEqual(self.sample()['queues'][0]['nodes'][0]['kind'],2)
        for off,value in [(0xc,3),(8,99),(4,0x123000)]:
            self.mem,self.p=fixture();at=queue_node(self.mem,self.p);self.mem.word(at+off,value)
            with self.subTest(off=off),self.assertRaises(ValueError):self.sample()
    def test_two_frame_limit_and_signature_are_not_relaxed(self):
        count=0
        def slow(address,size):
            nonlocal count
            if address==self.p['game']+0x50:
                count+=1
                return struct.pack('<I',100 if count==1 else 103)
            return self.mem.read(address,size)
        with self.assertRaisesRegex(ValueError,'session_or_frame_changed'):self.observer(slow).sample()
        self.mem.put(0x4e9c0b,b'\0')
        with self.assertRaisesRegex(ValueError,'live_list_signature_changed'):self.observer()


if __name__=='__main__':unittest.main()
