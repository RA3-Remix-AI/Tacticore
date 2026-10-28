"""Catalogue facts cannot be used as actions or contradict their own filters."""
import struct
from types import SimpleNamespace
import unittest
from host_runtime.runtime_evidence import _layout,_catalogue_trace_valid

def bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]

class CatalogueTrace(unittest.TestCase):
    def setUp(self):
        self.l=_layout();self.actor=SimpleNamespace(update=0x6000,thing=0x5000)
    def point(self):
        t=self.l.HookTrace();t.kind=27;t.word_count=24;t.self=0x6000;t.target=0x5000
        values=[1,0,1,1,0,bits(80),0,0,0,0,0,bits(80),bits(100),1,bits(30),bits(120),bits(20),0,1]
        for i,value in enumerate(values):t.words[i]=value
        return t
    def test_available_and_short_distance_are_explained_without_relaxing_scope(self):
        t=self.point();self.assertTrue(_catalogue_trace_valid(t,self.actor))
        t.words[8]=bits(60);t.words[11]=bits(20);t.words[4]=2;t.words[18]=0
        self.assertTrue(_catalogue_trace_valid(t,self.actor))
        t.words[18]=1;self.assertFalse(_catalogue_trace_valid(t,self.actor))
    def test_forged_action_scope_actor_and_unknown_kind_are_rejected(self):
        for name,value in (('scope',1),('source',2),('operation',4),('caller',0x6939aa),('self',0x6024),('target',0x9999),('kind',28)):
            t=self.point();setattr(t,name,value)
            self.assertFalse(_catalogue_trace_valid(t,self.actor),name)
    def test_bad_distance_occupancy_and_reserved_payload_cannot_pass(self):
        for index,value in ((11,bits(79)),(12,bits(10)),(4,8),(17,bits(8)),(19,1),(5,bits(float('nan')))):
            t=self.point();t.words[index]=value
            self.assertFalse(_catalogue_trace_valid(t,self.actor),index)
    def test_summary_is_bounded_and_not_a_move_trace(self):
        t=self.l.HookTrace();t.kind=26;t.word_count=24;t.self=0x6000;t.target=0x5000
        for i,value in enumerate([1,3,1,1,8,bits(30),bits(120),bits(20),bits(2),1,bits(80),0,0]):t.words[i]=value
        self.assertTrue(_catalogue_trace_valid(t,self.actor))
        t.words[2]=4;self.assertFalse(_catalogue_trace_valid(t,self.actor))

if __name__=='__main__':unittest.main()
