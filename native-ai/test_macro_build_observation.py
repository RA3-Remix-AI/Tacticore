"""Corrupt/foreign builder data must not become native effect evidence."""
import struct
import unittest
from macro_build_observation import builder_rows,job_records,own_thing,macro_build_entries

class Memory:
    def __init__(self):self.data={}
    def put(self,at,raw):self.data.update((at+i,b) for i,b in enumerate(raw))
    def read(self,at,size):return bytes(self.data[at+i] for i in range(size))
    def words(self,at,*values):self.put(at,struct.pack('<'+'I'*len(values),*values))
    def thing(self,at,owner,ident):
        self.words(at,0xc4db60,at+0x1000);self.words(at+0x418,owner)
        self.words(at+0xdc,ident);self.words(at+0x1008,123);self.words(at+0x33c,at+0x2000)
        self.put(at+0x2004,struct.pack('<f',100))
    def registry(self,table,ident,value):
        self.words(table+4,0x700000,7);self.put(0x700000,bytes(32))
        self.words(0x700000+4*(ident%7),0x710000);self.words(0x710000,ident,value,0)

class NativeBuildObservationTests(unittest.TestCase):
    def test_foreign_thing_rejected_before_type_or_hp_reads(self):
        m=Memory();m.words(0x100000,0xc4db60);m.words(0x100418,0x900000)
        with self.assertRaisesRegex(ValueError,'foreign_thing'):own_thing(m.read,0x100000,0x800000)

    def builder(self):
        m=Memory();ai,owner,game=0x100000,0x200000,0x300000;factory=0x400000
        m.words(ai+0x3ec,0xc5f330);m.words(ai+0x3f8,0x500000,0x50000c)
        interface=0x600024;m.words(0x500000,interface,42,0x00010000);m.thing(factory,owner,42)
        m.words(interface,0xc3f8c8);m.words(interface-0x24,0xc3fad0,0x620000,factory)
        m.words(0xc3f8c8+0xac,0x6da6b0);m.words(0x620030,3);m.registry(game+0xbc,42,factory)
        m.words(0xc3f8c8+0x24,0x723f50);m.words(interface+0x10,0,0)
        return m,ai,owner,game,factory,interface

    def test_bound_builder_and_own_identity(self):
        m,ai,owner,game,factory,interface=self.builder();rows=builder_rows(m.read,ai,owner,game)
        self.assertEqual(rows[0]['factory']['thing_id'],42)
        self.assertEqual(rows[0]['factory_category_raw'],3)
        self.assertNotIn('created_thing',rows[0])

    def test_raw_category_does_not_grant_meaning_or_read_a_fake_thing_id(self):
        m,ai,owner,game,factory,interface=self.builder();m.words(0x620030,0xffffffff)
        row=builder_rows(m.read,ai,owner,game)[0]
        self.assertEqual(row['factory_category_raw'],0xffffffff)
        self.assertFalse(row['factory_category_semantics_verified'])

    def test_dead_registered_producer_does_not_supply_queue_feedback(self):
        m,ai,owner,game,factory,interface=self.builder();m.put(factory+0x2004,struct.pack('<f',0))
        row=builder_rows(m.read,ai,owner,game)[0]
        self.assertFalse(row['observation_available']);self.assertNotIn('queue_candidate',row)

    def test_builder_duplicate_cycle_or_invalid_header_refused(self):
        m=Memory();ai,owner,game=0x100000,0x200000,0x300000
        m.words(ai+0x3ec,0xc5f330);m.words(ai+0x3f8,0x500000,0x500001)
        with self.assertRaisesRegex(ValueError,'rows_bounds'):builder_rows(m.read,ai,owner,game)

    def jobs(self):
        m=Memory();ai,owner,game=0x100000,0x200000,0x300000;node,job=0x400000,0x500000
        m.put(ai+0x374,bytes(0x1c));m.words(ai+0x380,node)
        m.put(node,bytes(24));m.words(node+0x10,9,job)
        raw=bytearray(0x40)
        for at,value in {0:0xc60238,4:owner,0x10:123,0x18:3,0x2c:9}.items():struct.pack_into('<I',raw,at,value)
        m.put(job,raw);return m,ai,owner,game,node,job

    def test_native_job_map_owner_id_and_type(self):
        m,ai,owner,game,node,job=self.jobs();result=job_records(m.read,ai,owner,game)
        self.assertEqual(result['construction_jobs'][0]['target_type_hash_raw'],'0x7b')
        self.assertEqual(result['construction_jobs'][0]['native_job_id'],9)
        self.assertEqual(result['construction_jobs'][0]['factory_category_raw'],3)
        self.assertNotIn('created_thing',result['construction_jobs'][0])
        m.words(job+4,owner+4)
        with self.assertRaisesRegex(ValueError,'foreign_job'):job_records(m.read,ai,owner,game)

    def test_job_cycle_key_order_and_identity_refused(self):
        m,ai,owner,game,node,job=self.jobs();m.words(node,node)
        with self.assertRaisesRegex(ValueError,'cycle'):job_records(m.read,ai,owner,game)
        m.words(node,0);m.words(job+0x2c,10)
        with self.assertRaisesRegex(ValueError,'job_id'):job_records(m.read,ai,owner,game)

    def test_job_table_changed_during_read_refused(self):
        m,ai,owner,game,node,job=self.jobs();reads=0
        def read(at,size):
            nonlocal reads
            raw=m.read(at,size)
            if at==ai+0x374:
                reads+=1
                if reads>1:return bytes(size)
            return raw
        with self.assertRaisesRegex(ValueError,'tree_changed'):job_records(read,ai,owner,game)

if __name__=='__main__':unittest.main()
