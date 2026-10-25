import struct,unittest
from observe_production import decode_this_adjustor,queue_candidate

class FakeMemory:
    def __init__(self):self.blocks={}
    def read(self,a,n):
        for base,raw in self.blocks.items():
            if base<=a and a+n<=base+len(raw):return bytes(raw[a-base:a-base+n])
        raise RuntimeError('Read unavailable')
    def u32(self,a):return struct.unpack('<I',self.read(a,4))[0]
    def module(self,head=0,tail=0):
        raw=bytearray(0x60);struct.pack_into('<I',raw,0,0xc50000);struct.pack_into('<II',raw,0x34,head,tail);self.blocks[0x10000]=raw
    def node(self,address,kind=1,next=0,previous=0):
        raw=bytearray(0x70);struct.pack_into('<I',raw,4,0x10000);struct.pack_into('<I',raw,0xc,kind);struct.pack_into('<I',raw,0x10 if kind==1 else 0x14,0x30000);struct.pack_into('<II',raw,0x54,next,previous);self.blocks[address]=raw
        template=bytearray(16);struct.pack_into('<I',template,8,0x12345678);self.blocks[0x30000]=template

class ObservationGuardTests(unittest.TestCase):
    def test_literal_this_adjustor(self):
        self.assertEqual(decode_this_adjustor(b'\x83\xe9\x14\xe9'+struct.pack('<i',0x20),0x770000),(-20,0x770028))
    def test_unknown_code_never_assumes_base_object(self):self.assertIsNone(decode_this_adjustor(b'\x55\x8b\xec'+b'\0'*13,0x770000))
    def test_empty_is_not_production_success(self):
        m=FakeMemory();m.module();r=queue_candidate(m,0x10000);self.assertEqual(r['nodes'],[]);self.assertFalse(r['semantics_verified_by_live_production'])
    def test_linked_unit_template_observation(self):
        m=FakeMemory();m.module(0x20000,0x20100);m.node(0x20000,next=0x20100);m.node(0x20100,previous=0x20000)
        r=queue_candidate(m,0x10000);self.assertEqual([n['template_hash'] for n in r['nodes']],['0x12345678']*2)
    def test_cycle_rejected(self):
        m=FakeMemory();m.module(0x20000,0x20000);m.node(0x20000,next=0x20000)
        with self.assertRaisesRegex(RuntimeError,'cycle'):queue_candidate(m,0x10000)
    def test_bad_backlink_rejected(self):
        m=FakeMemory();m.module(0x20000,0x20100);m.node(0x20000,next=0x20100);m.node(0x20100,previous=0x20200)
        with self.assertRaisesRegex(RuntimeError,'back-link'):queue_candidate(m,0x10000)
    def test_unknown_kind_rejected(self):
        m=FakeMemory();m.module(0x20000,0x20000);m.node(0x20000,kind=3)
        with self.assertRaisesRegex(RuntimeError,'kind'):queue_candidate(m,0x10000)
    def test_missing_endpoint_rejected(self):
        m=FakeMemory();m.module(0x20000,0)
        with self.assertRaisesRegex(RuntimeError,'endpoints'):queue_candidate(m,0x10000)
    def test_wrong_tail_rejected(self):
        m=FakeMemory();m.module(0x20000,0x20100);m.node(0x20000)
        with self.assertRaisesRegex(RuntimeError,'tail'):queue_candidate(m,0x10000)

if __name__=='__main__':unittest.main(verbosity=2)
