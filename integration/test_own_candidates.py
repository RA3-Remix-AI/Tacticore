import struct
import unittest
from unittest.mock import patch
import own_candidates as module

class Memory:
    def __init__(self):
        self.words={0xcd8ce4:0x1000,0x1000:0xbeb630,0x1050:100,0xce8c9c:0x2000,0x203c:0x3000,0x3000:0xc5bce0,0x3020:3}
        self.positions={}
    def u32(self,address):return self.words.get(address,0)
    def read(self,address,size):return self.positions[address]
    def thing(self,address,owner,ident,type_hash=123):
        self.words.update({address+0x418:owner,address+0xdc:ident,address+4:address+0x1000,address+0x1008:type_hash})
        self.positions[address+0x38]=struct.pack('<fff',1,2,3)

class OwnCandidatesTests(unittest.TestCase):
    def setUp(self):self.mem=Memory()
    def sample(self,things):
        with patch.object(module,'walk_live_things',return_value=iter(things)):
            return module.own_candidates(self.mem,3,{123:{'template':'provisional_label'}})
    def test_foreign_object_never_exported_or_dereferenced(self):
        self.mem.thing(0x4000,0x3000,7)
        self.mem.words[0x5000+0x418]=0x6000
        result=self.sample([0x4000,0x5000])
        self.assertEqual(len(result['candidates']),1)
        self.assertEqual(result['candidates'][0]['object_id'],7)
    def test_duplicate_live_identity_rejected(self):
        self.mem.thing(0x4000,0x3000,7);self.mem.thing(0x5000,0x3000,7)
        with self.assertRaises(ValueError):self.sample([0x4000,0x5000])
    def test_invalid_own_position_rejected(self):
        self.mem.thing(0x4000,0x3000,7)
        self.mem.positions[0x4038]=struct.pack('<fff',float('nan'),0,0)
        with self.assertRaises(ValueError):self.sample([0x4000])
    def test_changed_player_slot_rejected(self):
        def walking(*args):
            yield from ()
            self.mem.words[0x203c]=0x5000
        with patch.object(module,'walk_live_things',side_effect=walking):
            with self.assertRaises(ValueError):module.own_candidates(self.mem,3,{})

if __name__=='__main__':unittest.main()
