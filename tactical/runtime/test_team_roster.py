import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from team_roster import capture,TeamRosterRecorder


class Memory:
    def __init__(self):self.data={};self.changed=None;self.calls={}
    def zero(self,p,n):self.data.update({p+i:0 for i in range(n)})
    def word(self,p,v):self.data.update({p+i:b for i,b in enumerate(struct.pack('<I',v))})
    def read(self,p,n):
        self.calls[p]=self.calls.get(p,0)+1
        if self.changed and p==self.changed and self.calls[p]>=2:self.word(p,999)
        return bytes(self.data[p+i] for i in range(n))


class TeamRosterTests(unittest.TestCase):
    def setUp(self):
        self.m=m=Memory();self.actor=NS(thing=0x50000,update=0x60000,template_ptr=0x80000,
            owner=0x20000,object_id=55,generation=1,type_hash=0x19ab11af)
        self.native=dict(identity=True,birth_verified=True,live=True,object_id=55,generation=1,frame=100,team=0x90000)
        for p,n in ((0x10000,0x200),(0x20000,0x100),(0x50000,0x41c),(0x51000,0x41c),
                    (0x52000,0x41c),(0x80000,0x10),(0x90000,0x30),(0x91000,0x10),
                    (0xa0000,0x20),(0xb0000,0x40)):
            m.zero(p,n)
        for p,v in ((0xcd8ce4,0x10000),(0x10000,0xbeb630),(0x10050,100),(0x100b4,0x50000),
                    (0x20000,0xc5bce0),(0x20020,3),(0x50004,0x80000),(0x50374,0x60000),
                    (0x80008,0x19ab11af),(0x90004,0x91000),(0x90010,0xa0000),(0x91008,0x20000),
                    (0xa0008,0xb0000),(0xa000c,0xb0008),(0xa0010,0xb0040),
                    (0xb0000,55),(0xb0004,77)):
            m.word(p,v)
        for p,oid,next_,team,owner in ((0x50000,55,0x51000,0x90000,0x20000),
                    (0x51000,77,0x52000,0x90000,0x20000),(0x52000,88,0,0,0)):
            for o,v in ((0,0xc4db60),(0xdc,oid),(0x7c,next_),(0x414,team),(0x418,owner)):m.word(p+o,v)

    def run_capture(self,**kw):return capture(self.m,self.actor,self.native,**kw)

    def test_original_order_and_stable_erase_are_not_formation_authority(self):
        r=self.run_capture();self.assertEqual([55,77],r['id_order']);self.assertEqual([77],r['stable_erase_prediction'])
        self.assertFalse(r['actor_is_last_member']);self.assertFalse(r['formation_slot_mapping_verified'])
        self.assertFalse(r['execution_authority_granted']);self.assertEqual(0,r['sdk_calls'])

    def test_last_member_is_only_a_roster_fact(self):
        self.m.word(0xb0000,77);self.m.word(0xb0004,55)
        self.assertTrue(self.run_capture()['actor_is_last_member'])

    def test_missing_own_member_or_duplicate_id_is_refused(self):
        self.m.word(0xa000c,0xb0004)
        with self.assertRaisesRegex(ValueError,'membership_mismatch'):self.run_capture()
        self.m.word(0xa000c,0xb0008);self.m.word(0xb0004,55)
        with self.assertRaisesRegex(ValueError,'duplicate'):self.run_capture()

    def test_paired_vector_change_is_refused(self):
        self.m.changed=0xb0000
        with self.assertRaisesRegex(ValueError,'paired_read_changed'):self.run_capture()

    def test_foreign_owner_and_native_generation_are_refused(self):
        self.m.word(0x91008,0x30000)
        with self.assertRaisesRegex(ValueError,'foreign_team'):self.run_capture()
        self.m.word(0x91008,0x20000);self.native['generation']=2
        with self.assertRaisesRegex(ValueError,'native_actor_context'):self.run_capture()

    def test_global_cycle_and_oversized_vector_are_refused(self):
        self.m.word(0x5207c,0x50000)
        with self.assertRaisesRegex(ValueError,'global_chain_bounds'):self.run_capture()
        self.m.word(0x5207c,0);self.m.word(0xa000c,0xb4000)
        with self.assertRaisesRegex(ValueError,'vector_bounds'):self.run_capture()

    def test_saved_source_team_can_be_observed_after_actor_left(self):
        self.m.word(0x50414,0xc0000);self.native['team']=0xc0000
        self.m.word(0xb0000,77);self.m.word(0xa000c,0xb0004)
        r=self.run_capture(source_team=0x90000)
        self.assertEqual([77],r['id_order']);self.assertIsNone(r['actor_index'])
        self.assertFalse(r['actor_is_last_member'])

    def test_recorder_failure_is_throttled_and_cannot_dispatch(self):
        outer=self
        class Runtime:
            def observe_actor(self,binding):return outer.native
            def submit(self,*a,**k):raise AssertionError('Diagnostic recorder cannot dispatch')
        record={};reader=TeamRosterRecorder(self.m,Runtime(),None,self.actor,record)
        with patch('team_roster.capture',side_effect=ValueError('unavailable')):
            reader.capture('before_reserve');reader.capture('before_reserve')
        self.assertEqual(1,len(record['source_team_order']['refusals']))
        self.assertEqual(0,len(record['source_team_order']['samples']))
        self.assertFalse(record['source_team_order']['execution_authority_granted'])

    def test_recorder_keeps_actual_pre_reserve_team_after_borrow(self):
        outer=self
        class Runtime:
            def observe_actor(self,binding):return outer.native
        record={};reader=TeamRosterRecorder(self.m,Runtime(),None,self.actor,record)
        reader.capture('before_reserve')
        self.m.word(0x50414,0xc0000);self.native.update(team=0xc0000,frame=101)
        self.m.word(0x10050,101);self.m.word(0xb0000,77);self.m.word(0xa000c,0xb0004)
        reader.capture('native_ready')
        self.assertEqual([55,77],record['source_team_order']['samples'][0]['id_order'])
        self.assertEqual([77],record['source_team_order']['samples'][1]['id_order'])
        self.assertTrue(record['source_team_order']['source_bound_before_reserve'])


if __name__=='__main__':unittest.main()
