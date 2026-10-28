"""Synthetic native-cache/runtime corruption checks; no process is opened."""
import struct
import unittest

from macro_observation import cache_scores, sample_runtime, registry_lookup, own_group_members, native_budget, GROUP_VTABLES, FLAG_HEURISTIC_VTABLE, SCOUT_RUNTIME_VTABLE,SIMPLE_ATTACK_RUNTIME_VTABLE


class Memory:
    def __init__(self):
        self.data={};self.ai=0x100000;self.start=0x200000
        self.put(self.ai+0x6e0,struct.pack('<II',self.start,self.start+24))
        self.flags=['/macro_build','/macro_scout']
        for i,flag in enumerate(self.flags):
            group=0x300000+i*0x100;node=0x400000+i*0x100;heuristic=0x500000+i*0x100;definition=0x600000+i*0x100
            self.put(self.start+12*i,struct.pack('<IfI',group,float(i),0))
            self.put(group,struct.pack('<III',sorted(GROUP_VTABLES)[i],node,node))
            self.put(node,struct.pack('<III',group+4,group+4,heuristic))
            self.put(heuristic,struct.pack('<II',FLAG_HEURISTIC_VTABLE,definition))
            # Deliberately unaligned serialized text.
            self.put(definition+8,struct.pack('<I',0x700001+i*0x100))
            self.put(0x700001+i*0x100,flag.encode()+b'\0')

    def put(self,address,raw):
        self.data.update((address+i,byte) for i,byte in enumerate(raw))

    def read(self,address,size):
        return bytes(self.data[address+i] for i in range(size))

    def runtime(self):
        address,owner,group=0x800000,0x900000,0x300100
        raw=bytearray(0xa4)
        for offset,value in {0:SCOUT_RUNTIME_VTABLE,4:0xa00000,8:0xa00004,0x2c:owner,0x50:group,
                0x58:0xc5fe94,0x5c:0xc5fe5c,0x60:0xb00000,0x64:0xb00000,0x94:address}.items():
            struct.pack_into('<I',raw,offset,value)
        raw[0x14]=1
        self.put(address,raw);self.put(0xa00000,struct.pack('<I',42));self.put(0xb00000,struct.pack('<II',address+0x60,address+0x60))
        return address,owner,{group}


class MacroObservationTests(unittest.TestCase):
    def test_simple_attack_distinct_native_type_uses_same_strict_owner_state_and_links(self):
        memory=Memory();args=memory.runtime();memory.put(args[0],struct.pack('<I',SIMPLE_ATTACK_RUNTIME_VTABLE))
        row=sample_runtime(memory.read,*args)
        self.assertEqual(row['native_tactic_family'],'simple_attack')
        self.assertTrue(row['native_execution_active'])
        memory.put(args[0]+0x2c,struct.pack('<I',args[1]+4))
        with self.assertRaisesRegex(ValueError,'runtime_binding'):sample_runtime(memory.read,*args)

    def test_budget_cache_reads_its_separate_native_header(self):
        m=Memory();m.put(m.ai+0xe8,struct.pack('<II',m.start,m.start+12))
        rows=cache_scores(m.read,m.ai,m.flags,0xe8,'budget')
        self.assertEqual(set(rows),{'/macro_build'});self.assertEqual(rows['/macro_build']['domain'],'budget')

    def budget(self):
        m=Memory();definition=0x1800000;m.put(0x300000+0x10,struct.pack('<I',definition))
        m.put(m.ai+0x100,struct.pack('<I',definition+0xc))
        for offset,value in zip([0x18,0x3c,0x60,0x84,0xa8,0xcc],[.4,0,.25,.1,.15,.1]):m.put(m.ai+offset,struct.pack('<f',value))
        rows={'/budget_economy':dict(domain='budget',group='0x300000')}
        return m,rows

    def test_selected_native_budget_and_actual_account_percentages(self):
        m,rows=self.budget();result=native_budget(m.read,m.ai,rows)
        self.assertEqual(result['selected_macro_flag'],'/budget_economy')
        self.assertAlmostEqual(result['account_shares']['investment'],.4)
        self.assertFalse(result['payment_attribution_verified'])
        m.put(m.ai+0x100,struct.pack('<I',0x190000c))
        self.assertIsNone(native_budget(m.read,m.ai,rows)['selected_macro_flag'])

    def test_budget_invalid_or_changing_snapshot_is_rejected(self):
        for value in [float('nan'),-.1,2,.8]:
            m,rows=self.budget();m.put(m.ai+0x18,struct.pack('<f',value))
            with self.assertRaisesRegex(ValueError,'share_bounds'):native_budget(m.read,m.ai,rows)
        m,rows=self.budget();count=0
        def read(address,size):
            nonlocal count
            raw=m.read(address,size)
            if address==m.ai+0x100:
                count+=1
                if count>1:return bytes(4)
            return raw
        with self.assertRaisesRegex(ValueError,'budget_changed'):native_budget(read,m.ai,rows)

    def registry(self,memory,table,ident,value):
        buckets=table+0x100;node=table+0x200
        memory.put(table+4,struct.pack('<II',buckets,7));memory.put(buckets,bytes(32))
        memory.put(buckets+4*(ident%7),struct.pack('<I',node))
        memory.put(node,struct.pack('<III',ident,value,0))
        return buckets,node

    def group(self):
        m=Memory();registry,game,group,team,thing,owner=0xc00000,0xd00000,0xe00000,0xf00000,0x1100000,0x1200000
        m.put(0xce8ca4,struct.pack('<I',registry));m.put(0xcd8ce4,struct.pack('<I',game))
        self.registry(m,registry+0x28,361,group);self.registry(m,game+0xbc,42,thing)
        m.put(group+0x39c,struct.pack('<I',8));m.put(group+0x10,struct.pack('<I',team))
        m.put(team+8,struct.pack('<II',0x1300000,0x1300004));m.put(0x1300000,struct.pack('<I',42))
        m.put(thing,struct.pack('<II',0xc4db60,0x1400000));m.put(thing+0xdc,struct.pack('<I',42))
        m.put(thing+0x418,struct.pack('<I',owner));m.put(thing+0x33c,struct.pack('<I',0x1500000))
        m.put(0x1400008,struct.pack('<I',123));m.put(0x1500004,struct.pack('<f',100))
        m.put(thing+0x38,struct.pack('<fff',1,2,3))
        return m,group,team,thing,owner

    def test_registry_absence_cycle_wrong_bucket_and_change(self):
        m=Memory();table=0x1600000;buckets,node=self.registry(m,table,42,0x1700000)
        self.assertEqual(registry_lookup(m.read,table,42),0x1700000)
        self.assertEqual(registry_lookup(m.read,table,49),0)
        m.put(node+8,struct.pack('<I',node))
        with self.assertRaisesRegex(ValueError,'cycle'):registry_lookup(m.read,table,49)
        m.put(node,struct.pack('<I',43))
        with self.assertRaisesRegex(ValueError,'wrong_bucket'):registry_lookup(m.read,table,49)
        m=Memory();self.registry(m,table,42,0x1700000);count=0
        def read(address,size):
            nonlocal count
            raw=m.read(address,size)
            if address==table+4:
                count+=1
                if count>1:return bytes(8)
            return raw
        with self.assertRaisesRegex(ValueError,'registry_changed'):registry_lookup(read,table,42)

    def test_native_group_authoritative_ids_resolve_own_members(self):
        m,group,team,thing,owner=self.group()
        row=own_group_members(m.read,361,owner)
        self.assertTrue(row['all_members_resolved']);self.assertEqual(row['members'][0]['thing_id'],42)
        self.assertEqual(row['members'][0]['xyz'],[1,2,3]);self.assertFalse(row['cache_refreshed'])
        # Team's cache fields are deliberately absent; they are never read.
        m.put(group+0x39c,struct.pack('<I',1))
        with self.assertRaisesRegex(ValueError,'not_native_group'):own_group_members(m.read,361,owner)

    def test_enemy_member_rejected_before_details(self):
        m,group,team,thing,owner=self.group();m.put(thing+0x418,struct.pack('<I',owner+4))
        forbidden={thing+4,thing+0x38,thing+0x33c}
        def read(address,size):
            if address in forbidden:raise AssertionError('enemy detail read')
            return m.read(address,size)
        with self.assertRaisesRegex(ValueError,'not_bound_owner'):own_group_members(read,361,owner)

    def test_current_cache_two_gates_and_unaligned_strings(self):
        memory=Memory();rows=cache_scores(memory.read,memory.ai,memory.flags)
        self.assertEqual([rows[name]['score'] for name in memory.flags],[0,1])
        self.assertEqual(rows['/macro_scout']['group'],'0x300100')

    def test_dirty_is_not_an_activation_or_completion(self):
        memory=Memory();memory.put(memory.start+8,b'\x01')
        row=cache_scores(memory.read,memory.ai,memory.flags)['/macro_build']
        self.assertTrue(row['dirty']);self.assertEqual(row['score'],0)
        self.assertNotIn('completed',row)

    def test_duplicate_gate_cache_entry_is_refused(self):
        memory=Memory();memory.put(memory.start+12,struct.pack('<IfI',0x300000,0,0))
        with self.assertRaisesRegex(ValueError,'duplicate_macro_state'):
            cache_scores(memory.read,memory.ai,memory.flags)

    def test_bad_score_bounds_cycle_and_back_link(self):
        for fault in ['score','bounds','cycle','back']:
            with self.subTest(fault=fault):
                memory=Memory()
                if fault=='score':memory.put(memory.start+4,struct.pack('<f',float('nan')))
                if fault=='bounds':memory.put(memory.ai+0x6e4,struct.pack('<I',memory.start+25))
                if fault=='cycle':memory.put(0x400000,struct.pack('<I',0x400000))
                if fault=='back':memory.put(0x400004,struct.pack('<I',0))
                with self.assertRaises(ValueError):cache_scores(memory.read,memory.ai,memory.flags)

    def test_cache_change_cannot_be_a_stable_sample(self):
        memory=Memory();count=0
        def read(address,size):
            nonlocal count
            raw=memory.read(address,size)
            if address==memory.ai+0x6e0:
                count+=1
                if count>1:return struct.pack('<II',memory.start,memory.start+12)
            return raw
        with self.assertRaisesRegex(ValueError,'cache_changed'):
            cache_scores(read,memory.ai,memory.flags)

    def test_construction_cache_uses_its_own_header(self):
        memory=Memory()
        memory.put(memory.ai+0x414,struct.pack('<II',memory.start,memory.start+12))
        rows=cache_scores(memory.read,memory.ai,memory.flags,0x414,'construction')
        self.assertEqual(set(rows),{'/macro_build'})
        self.assertEqual(rows['/macro_build']['domain'],'construction')
        with self.assertRaisesRegex(ValueError,'unsupported_macro_cache_domain'):
            cache_scores(memory.read,memory.ai,memory.flags,0x414,'strategic')

    def test_runtime_native_active_and_ids_are_not_mission_success(self):
        memory=Memory();args=memory.runtime();row=sample_runtime(memory.read,*args)
        self.assertTrue(row['native_execution_active'])
        self.assertEqual(row['native_owned_ids_raw'],[42])
        self.assertFalse(row['object_ids_resolved']);self.assertFalse(row['mission_complete_verified'])
        self.assertFalse(row['unit_movement_attributed'])

    def test_runtime_owner_definition_self_and_intrusive_links(self):
        for offset in [0x2c,0x50,0x94]:
            with self.subTest(offset=offset):
                memory=Memory();args=memory.runtime();memory.put(args[0]+offset,struct.pack('<I',0))
                with self.assertRaisesRegex(ValueError,'runtime_binding'):sample_runtime(memory.read,*args)
        memory=Memory();args=memory.runtime();memory.put(0xb00004,struct.pack('<I',0))
        with self.assertRaisesRegex(ValueError,'unlinked'):sample_runtime(memory.read,*args)


if __name__=='__main__':unittest.main()
