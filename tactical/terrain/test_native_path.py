"""Own-identity, typed path and changing-memory refusals; no game access."""
import struct
import unittest
from native_path import NativePathReader, CODE_PINS


class Memory:
    def __init__(self): self.bytes={}; self.mutate=None
    def put(self,address,raw): self.bytes.update((address+i,b) for i,b in enumerate(raw))
    def word(self,address,value): self.put(address,struct.pack('<I',value))
    def read(self,address,size):
        result=bytes(self.bytes[address+i] for i in range(size))
        if self.mutate:self.mutate(self,address,size)
        return result


def fixture():
    m=Memory(); t,u,owner,tpl,team,link,body,path,params,node=range(0x10000,0xb0000,0x10000)
    logic=0xb0000
    for a,r in CODE_PINS.items():m.put(a,r)
    for a,v in {0xcd8ce4:logic,logic:0xbeb630,logic+0x50:100,t:0xc4db60,t+4:tpl,
        t+0xdc:780,tpl+8:0x2c358c61,t+0x418:owner,t+0x374:u,u:0xc48670,
        u+0x24:0xc48528,u+8:t,t+0x414:team,t+0x33c:body,team+4:link,link+8:owner,
        t+0x238:0,u+0x150:path,u+0x1fc:0xc37620,u+0x210:1,tpl+0xc0:0,
        tpl+0xcc:0,t+0x98:0}.items():m.word(a,v)
    m.put(t+0x38,struct.pack('<3f',10,20,210));m.put(body+4,struct.pack('<f',100));m.put(t+0x80,bytes(28));m.word(t+0x98,0)
    header=[0]*19;header[0]=0xc18cd4;header[1]=1;header[2]=0xc18cc4
    header[4]=header[5]=header[9]=node;header[15]=params
    m.put(path,struct.pack('<19I',*header));m.put(params,struct.pack('<6I',0xc18ca0,0xc1893c,0,780,0,u+0x1fc))
    m.put(node,struct.pack('<3I3fI',0,0,0,30,40,210,1))
    row=dict(address=hex(t),ai_address=hex(u),owner_address=hex(owner),object_id=780,type_hash='0x2c358c61',xyz=[10,20,210])
    return m,row,path,params,node


class NativePathTests(unittest.TestCase):
    def test_complete_typed_chain_is_readonly_and_grants_nothing(self):
        m,row,*_=fixture();result=NativePathReader(m).sample(row,100)
        self.assertEqual([[30,40,210]],[n['xyz'] for n in result['nodes']])
        self.assertFalse(result['static_outer_yield_scan_gate'])
        self.assertFalse(result['route_or_target_permission_granted'])
        self.assertFalse(result['actor_borrow_qualified'])

    def test_initialized_object_zero_cannot_bind_a_unit(self):
        m,row,_,params,_=fixture();m.word(params+12,0)
        with self.assertRaisesRegex(ValueError,'parameters_actor'):NativePathReader(m).sample(row,100)

    def test_node_cycle_and_changed_tail_are_refused(self):
        for cycle in [True,False]:
            m,row,path,_,node=fixture();m.word(node+8,node) if cycle else m.word(path+0x14,node+4)
            with self.assertRaises(ValueError):NativePathReader(m).sample(row,100)

    def test_wrong_actor_or_mask_or_frame_cannot_produce_a_path_sample(self):
        for address,value in [(0x10000+0xdc,781),(0x20000+0x210,2),(0xb0000+0x50,101)]:
            m,row,*_=fixture();m.word(address,value)
            with self.assertRaises(ValueError):NativePathReader(m).sample(row,100)

    def test_node_changed_during_capture_is_not_a_paired_snapshot(self):
        m,row,_,_,node=fixture()
        def mutate(memory,address,size):
            if address==node:memory.word(node+0xc,0);memory.mutate=None
        m.mutate=mutate
        with self.assertRaisesRegex(ValueError,'paired_read_changed'):NativePathReader(m).sample(row,100)

    def test_nonzero_path_scan_flag_is_only_a_static_prerequisite(self):
        m,row,path,*_=fixture();m.put(path+0x1f,b'\1');result=NativePathReader(m).sample(row,100)
        self.assertTrue(result['static_outer_yield_scan_gate'])
        self.assertFalse(result['native_yield_source_verified'])


if __name__=='__main__':unittest.main()
