"""Artificial registered objects, including a non-live owner; no process I/O."""
import struct
import unittest
import macro_registered_queue_observation as r
from test_macro_payment_observation_v2 import fixture as payment_fixture,queue_node


def fixture():
    mem,p=payment_fixture()
    for at,value in r.PINS.items():mem.put(at,bytes.fromhex(value))
    mem.put(p['game']+0x144,b'\0')
    return mem,p


class RegisteredQueueTests(unittest.TestCase):
    def setUp(self):self.mem,self.p=fixture()
    def observer(self,read=None):
        return r.RegisteredQueueCommitmentObserver(read or self.mem.read,self.p['owner'],
            executable_sha256=r.EXE_SHA256,expected_owner_index=3)
    def test_registered_owner_removed_from_live_list_is_still_scanned(self):
        self.mem.word(self.p['game']+0xb4,0);queue_node(self.mem,self.p)
        result=self.observer().sample()
        self.assertEqual(result['own_object_count'],1)
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],750)
        self.assertTrue(result['registered_roster_scan_complete'])
        self.assertFalse(result['registry_scan']['live_list_membership_required'])
        self.assertFalse(result['unregistered_owners_payment_obligations_covered'])
        self.assertFalse(result['all_current_own_production_queues_enumerated'])
    def test_full_bucket_vector_is_chunked_within_adapter_bound(self):
        buckets=0x920000;count=4097;self.mem.zeros(buckets,4*(count+1))
        self.mem.word(self.p['game']+0xc0,buckets);self.mem.word(self.p['game']+0xc4,count)
        self.mem.word(buckets+4*17,self.p['node']);self.mem.reads.clear()
        result=self.observer().sample()
        self.assertEqual(result['registry_scan']['bucket_count'],count)
        self.assertTrue(all(n<=8192 for at,n in self.mem.reads))
        self.assertEqual(result['own_object_count'],1)
    def test_live_owner_temporarily_absent_from_registry_still_counts_queue(self):
        self.mem.word(self.p['buckets'],0);queue_node(self.mem,self.p)
        result=self.observer().sample()
        self.assertEqual(result['registry_scan']['registry_node_count'],0)
        self.assertEqual(result['registry_scan']['live_only_owned_ids'],[17])
        self.assertEqual(result['production_queue_payment_commitment_upper_bound'],750)
        self.assertTrue(result['roster_union_scan_complete']);self.assertFalse(result['product_fact_eligible'])
    def test_nonowned_registered_value_has_no_detail_access(self):
        enemy,node=0x950000,0x960000
        self.mem.word(enemy,r.readiness.THING_VTABLE);self.mem.word(enemy+0x418,0x21000)
        self.mem.put(node,struct.pack('<III',18,enemy,0));self.mem.word(self.p['node']+8,node)
        self.mem.reads.clear();result=self.observer().sample()
        self.assertEqual(result['registry_scan']['foreign_owner_skipped_count'],1)
        reads={(at,n) for at,n in self.mem.reads if enemy<=at<enemy+0x474}
        self.assertEqual(reads,{(enemy,4),(enemy+0x418,4)})
    def test_registry_header_and_chains_remain_strict_stability_dependencies(self):
        calls=0
        def changing(at,size):
            nonlocal calls
            if at==self.p['game']+0xc0:
                calls+=1
                if calls>1:return struct.pack('<II',self.p['buckets'],2)
            return self.mem.read(at,size)
        with self.assertRaisesRegex(ValueError,'necessary_bytes_changed'):self.observer(changing).sample()
    def test_bucket_mismatch_cycle_and_owned_id_mismatch_reject(self):
        self.mem.word(self.p['game']+0xc4,2);self.mem.word(self.p['buckets']+8,0)
        with self.assertRaisesRegex(ValueError,'id_bucket'):self.observer().sample()
        self.mem,self.p=fixture();self.mem.word(self.p['node']+8,self.p['node'])
        with self.assertRaisesRegex(ValueError,'cycle_duplicate'):self.observer().sample()
        self.mem,self.p=fixture();self.mem.word(self.p['thing']+0xdc,18)
        with self.assertRaisesRegex(ValueError,'owned_id_mismatch'):self.observer().sample()
    def test_paid_change_remains_rejected_and_progress_unread(self):
        node=queue_node(self.mem,self.p);paid_reads=0
        def read(at,size):
            nonlocal paid_reads
            if at in (node+0x1c,node+0x24):raise AssertionError('unused_progress_read')
            if at==node+0x68:
                paid_reads+=1
                if paid_reads>1:return struct.pack('<I',251)
            return self.mem.read(at,size)
        with self.assertRaisesRegex(ValueError,'necessary_bytes_changed'):self.observer(read).sample()
    def test_native_deletion_batch_active_or_changes_reject(self):
        self.mem.put(self.p['game']+0x144,b'\1')
        with self.assertRaisesRegex(ValueError,'deletion_batch_active_or_unknown'):self.observer().sample()
        self.mem.put(self.p['game']+0x144,b'\0');calls=0
        def read(at,size):
            nonlocal calls
            if at==self.p['game']+0x144:
                calls+=1
                if calls>1:return b'\1'
            return self.mem.read(at,size)
        with self.assertRaisesRegex(ValueError,'necessary_bytes_changed'):self.observer(read).sample()


if __name__=='__main__':unittest.main()
