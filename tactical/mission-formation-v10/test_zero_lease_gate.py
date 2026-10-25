"""Fake RPM on actual MF10 Header layout, never a live no-lease certificate."""
import copy
import ctypes as c
import importlib.util
import struct
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

H=Path(__file__).resolve().parent
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
w=load('mf10_zero_runtime_test',H/'lease.py')
g=load('mf10_zero_gate_test',H.parent/'mission_formation_v10_gate_no_lease.py')


class Memory:
    def __init__(self):self.bytes={}
    def put(self,address,block):self.bytes.update({address+i:x for i,x in enumerate(block)})
    def u32(self,address):return struct.unpack('<I',self.read(address,4))[0]
    def read(self,address,n):
        if not 0<n<=0x2000:raise RuntimeError('Read bounds')
        return bytes(self.bytes[address+i] for i in range(n))


class Gate(unittest.TestCase):
    def fixture(self):
        session,commander,command,task=[str(uuid.uuid4()) for _ in range(4)]
        pre=dict(pid=1,window_thread=99,session_id=session,commander_id=commander,owner='0x9000',ai='0xa000',logic='0xb000',selected=dict(address='0x7000',object_id=7),support=dict(address='0x8000',object_id=8))
        request=dict(command_id=command,task_id=task,seq=1,token=17)
        n={key:0 for key in g.FRONT};n.update(phase=4,error=34,restore_mask=65535,active=0,overflow=0,support={key:0 for key in g.SUPPORT})
        report=dict(session_id=session,preflight=pre,request=request,native=n,events=[],host_exit=9)
        header=w.Header();header.magic=0x4d463130;header.version=10;header.pid=1;header.thread=header.callback_thread=99;header.owner=0x9000;header.ai=0xa000;header.logic=0xb000;header.unit=0x7000;header.object_id=7;header.support.thing=0x8000;header.support.id=8;header.token=17;header.seq=1;header.phase=4;header.error=34;header.restore_mask=65535
        for name,value in [('session',session),('commander',commander),('command',command),('task',task)]:getattr(header,name)[:]=struct.unpack('<4I',uuid.UUID(value).bytes)
        profile=dict(path=H,magic=0x4d463130,version=10,layout=dict(shared_pointer_rva=4,timer_rva=8))
        memory=Memory();base=0x100000;pointer=0x200000;memory.put(base+4,struct.pack('<I',pointer));memory.put(base+8,struct.pack('<I',0));memory.put(pointer,c.string_at(c.addressof(header),c.sizeof(header)))
        with patch.object(g,'profile',return_value=profile):
            for e in g.entries(report):memory.put(e['address'],bytes.fromhex(e['expected']))
            snapshot=g.snapshot(memory,report,base,w)
        evidence=dict(protocol=g.PROTOCOL,source_sha256='a'*64,native_host_exit=9,completed=False,return_verified=False,restoration_verified=False,mutations=False,snapshots=[snapshot,copy.deepcopy(snapshot)],**{key:(pre[key] if key in pre else request[key]) for key in ('pid','session_id','commander_id','command_id','task_id','seq','token')})
        return profile,report,evidence

    def verify(self,profile,report,evidence):
        with patch.object(g,'profile',return_value=profile):return g.verify(evidence,report,'a'*64)

    def test_real_prefix_and_thirteen_signature_set_support_release_only(self):
        p,r,e=self.fixture();result=self.verify(p,r,e)
        self.assertTrue(result['no_actor_lease_verified'],result)
        self.assertFalse(result['restoration_verified']);self.assertFalse(result['return_verified']);self.assertFalse(result['completion_claim'])

    def test_new_native_motion_counters_prevent_a_fake_zero_lease(self):
        for key in ('leader_move_count','follow_move_count','regroup_count','hold_repair_count'):
            p,r,e=self.fixture();r['native'][key]=1
            self.assertFalse(self.verify(p,r,e)['no_actor_lease_verified'],key)
            p,r,e=self.fixture();e['snapshots'][0]['front'][key]=1
            self.assertFalse(self.verify(p,r,e)['no_actor_lease_verified'],key)

    def test_active_timer_missing_hook_or_duplicate_actor_proof_refuses(self):
        for mode in ('timer','active','hook','duplicate','owner','command'):
            p,r,e=self.fixture();s=e['snapshots'][0]
            if mode=='timer':s['timer']=1
            elif mode=='active':s['active']=1
            elif mode=='hook':s['entries'][0]['actual']='00'
            elif mode=='duplicate':s['entries']=[s['entries'][0]]*13
            elif mode=='owner':s['owner']='0x9999'
            else:s['command_id']=str(uuid.uuid4())
            self.assertFalse(self.verify(p,r,e)['no_actor_lease_verified'],mode)

    def test_mask_zero_early_install_failure_stays_unproved(self):
        p,r,e=self.fixture();r['native']['restore_mask']=0
        for s in e['snapshots']:s['restore_mask']=0
        self.assertFalse(self.verify(p,r,e)['no_actor_lease_verified'])


if __name__=='__main__':unittest.main()
