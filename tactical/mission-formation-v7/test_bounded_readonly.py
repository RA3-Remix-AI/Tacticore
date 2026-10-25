"""Real Memory.read size contract with actual MF7 Header; pure fake RPM only."""
import ctypes as c
import importlib.util
from pathlib import Path
import struct
import unittest
import tempfile,hashlib,json,uuid
from types import SimpleNamespace
from unittest.mock import patch
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mf7_bounded_runtime',H/'lease.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)

class Memory:
 def __init__(self):self.data={};self.reads=[];self.change=None
 def put(self,address,block):self.data.update({address+i:v for i,v in enumerate(block)})
 def read(self,address,n):
  if not 0<n<=0x2000:raise RuntimeError('Read bounds')
  self.reads.append((address,n))
  if self.change:self.change(self,address,n)
  return bytes(self.data[address+i] for i in range(n))
 def u32(self,address):return struct.unpack('<I',self.read(address,4))[0]

class Bounded(unittest.TestCase):
 def fixture(self):
  m=Memory();base=0x100000;ptr=0x200000;layout=dict(shared_pointer_rva=4,timer_rva=8)
  m.put(base+4,struct.pack('<I',ptr));m.put(base+8,bytes(4));h=w.Header();h.magic=0x4d464d37;h.version=7;h.phase=4;h.restore_mask=8191
  m.put(ptr,bytes(h));return m,base,ptr,layout,h
 def test_true_memory_bound_rejects_old_full_read_but_new_header_exact(self):
  m,b,p,l,h=self.fixture()
  with self.assertRaisesRegex(RuntimeError,'Read bounds'):m.read(p,c.sizeof(h))
  value,pointer,timer=w.read_stable_header(m,b,l)
  self.assertEqual(bytes(value),bytes(h));self.assertEqual(pointer,p);self.assertEqual(timer,0)
  sizes=[n for a,n in m.reads if p<=a<p+c.sizeof(h)]
  self.assertEqual(sizes,[8192,8192,8192,3324]*2)
 def test_header_mutation_between_chunks_is_not_accepted(self):
  m,b,p,l,h=self.fixture();changed=False
  def change(m,a,n):
   nonlocal changed
   if a==p+8192 and not changed:m.put(p+w.Header.error.offset,struct.pack('<I',53));changed=True
  m.change=change
  with self.assertRaisesRegex(ValueError,'readonly_header_not_stable'):w.read_stable_header(m,b,l)
 def test_pointer_and_timer_must_stay_stable(self):
  for name,offset in [('pointer',4),('timer',8)]:
   with self.subTest(name=name):
    m,b,p,l,h=self.fixture();changed=False
    def change(m,a,n):
     nonlocal changed
     if a==p+24576 and not changed:m.put(b+offset,struct.pack('<I',p+4 if offset==4 else 1));changed=True
    m.change=change
    with self.assertRaisesRegex(ValueError,'readonly_header_not_stable'):w.read_stable_header(m,b,l)
 def test_short_read_invalid_size_or_overflow_never_fills_zeros(self):
  m,b,p,l,h=self.fixture()
  for address,size in [(p,0),(p,-1),(0,8),(True,8),(p,True),(2**32-1,8),(p,c.sizeof(h)+1)]:
   with self.subTest(address=address,size=size),self.assertRaises(ValueError):w.read_bounded_exact(m,address,size)
  with patch.object(m,'read',return_value=b''):
   with self.assertRaisesRegex(ValueError,'readonly_header_short_read'):w.read_bounded_exact(m,p,4)
 def terminal_fixture(self,directory):
  m,b,p,l,h=self.fixture();h.pid=1;h.token=9;h.seq=4;h.owner=0x9000;h.logic=0xa000;h.error=53;h.phase=3;h.return_verified=1;h.support.returned=1
  identities=[str(uuid.uuid4()) for _ in range(4)]
  for field,value in zip(('session','commander','command','task'),identities):getattr(h,field)[:]=struct.unpack('<4I',uuid.UUID(value).bytes)
  m.put(p,bytes(h));m.put(0xcd8ce4,struct.pack('<I',h.logic))
  dll=directory/'bin/TacticalMissionFormation7.dll';dll.parent.mkdir();dll.write_bytes(b'fake-native-boundary-only');digest=hashlib.sha256(dll.read_bytes()).hexdigest();l['dll_sha256']=digest;(directory/'inert-layout.json').write_text(json.dumps(l))
  entries=[]
  for index in range(13):
   address=0x500000+index*16;m.put(address,b'ABCD');entries.append(dict(address=hex(address),expected=b'ABCD'.hex()))
  report=dict(native_binary_sha256=digest,session_id=identities[0],preflight=dict(pid=1,commander_id=identities[1],owner=hex(h.owner),logic=hex(h.logic)),request=dict(command_id=identities[2],task_id=identities[3],seq=4,token=9),original_entries=entries)
  return m,b,p,l,h,report
 def test_full_terminal_reader_uses_bounded_header_and_all_thirteen_entries(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);m,b,p,l,h,r=self.terminal_fixture(directory)
   with patch.object(w,'HERE',directory),patch.object(w,'module',return_value=SimpleNamespace(module_base=lambda memory,path:b)):
    result=w.terminal_readonly(m,r)
   self.assertTrue(result['binding_verified']);self.assertEqual(result['timer'],0);self.assertEqual(len(result['entries']),13)
   self.assertTrue(all(x['restored'] for x in result['entries']));self.assertTrue(all(0<n<=8192 for _,n in m.reads))
 def test_terminal_entry_scan_cannot_accept_header_changed_after_binding(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);m,b,p,l,h,r=self.terminal_fixture(directory);changed=False
   def change(m,a,n):
    nonlocal changed
    if a==0x500000 and not changed:m.put(p+w.Header.error.offset,struct.pack('<I',54));changed=True
   m.change=change
   with patch.object(w,'HERE',directory),patch.object(w,'module',return_value=SimpleNamespace(module_base=lambda memory,path:b)):
    with self.assertRaisesRegex(ValueError,'readonly_header_changed_during_entries'):w.terminal_readonly(m,r)
 def test_terminal_identity_mismatch_stays_unverified(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);m,b,p,l,h,r=self.terminal_fixture(directory);r['request']['token']+=1
   with patch.object(w,'HERE',directory),patch.object(w,'module',return_value=SimpleNamespace(module_base=lambda memory,path:b)):
    result=w.terminal_readonly(m,r)
   self.assertFalse(result['binding_verified'])
 def test_wait_rebase_snapshot_is_raw_event_only_not_a_published_trail_point(self):
  shared=w.Tactical();shared.count=1;shared.events[0].seq=1;shared.events[0].kind=97;shared.events[0].breadcrumb.published_seq=0;shared.events[0].breadcrumb.index=0;shared.events[0].breadcrumb.xyz[:]=[1,2,3]
  report=dict(events=[],request=dict(task_id='00000000-0000-0000-0000-000000000001'))
  with patch.object(w,'progress',return_value=None):w.capture(report,shared)
  self.assertEqual(report['events'][0]['breadcrumb']['xyz'],[1,2,3]);self.assertEqual(report['events'][0]['breadcrumb']['published_seq'],0)
  self.assertEqual(report['native']['crumbs'],[[],[]])

if __name__=='__main__':unittest.main()
