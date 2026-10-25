"""Actual 8192-byte read boundary with an inert synthetic large header."""
import copy,hashlib,json,struct,unittest,uuid
import test_scene_terminal_release as old
import test_scene_terminal_release_v2 as previous
import scene_terminal_release_v6 as reader

class BoundedMemory(old.Memory):
 def __init__(self):super().__init__();self.maximum=0
 def read(self,address,length):
  if length>0x2000:raise RuntimeError('Read bounds')
  self.maximum=max(self.maximum,length);return super().read(address,length)

def fixture(family='mission-formation-v5'):
 report,record=previous.fixture();p=reader.PROFILES[family]
 report['native']['restore_mask']=p['mask']
 report.update(native_binary_sha256=p['binary'],native_host_sha256=p['host'],native_source_sha256=p['cpp'],native_shared_sha256=p['shared'])
 record.update(directory=family,native_binary_sha256=p['binary'],source_sha256=hashlib.sha256(json.dumps(report).encode()).hexdigest())
 name,p=reader.profile(report);before=record['snapshots'][0];native=before['native_before'];native.update(magic=p['magic'],version=p['version'],restore_mask=p['mask']);memory=BoundedMemory();base=before['module_base'];ptr=before['shared_pointer'];block=bytearray(p['header'])
 for key,offset in reader.COMMON.items():
  if key in ('session','commander','command','task'):block[offset:offset+16]=uuid.UUID(native[key]).bytes
  else:struct.pack_into('<I',block,offset,native[key])
 for key,offset in [('thing',0),('id',4),('hash',8),('update',12),('detach_calls',20),('return_calls',24),('returned',28)]:struct.pack_into('<I',block,484+offset,native['support'][key])
 memory.put(ptr,block);memory.word(base+p['pointer_rva'],ptr);memory.word(base+p['timer_rva'],0)
 world=before['scene_before'];logic=native['logic'];owner=native['owner']
 for address,value in [(0xcd8ce4,logic),(logic,world['logic_vtable']),(logic+0x50,0),(logic+0xb4,0),(logic+0x148,9),(logic+0x15c,0),(owner,world['owner_vtable']),(owner+0x20,3),(owner+0x90,0)]:memory.word(address,value)
 for entry in reader.expected_entries(report):memory.put(entry['address'],bytes.fromhex(entry['expected']))
 snapshots=[reader.snapshot(memory,report,base),reader.snapshot(memory,report,base)]
 for i,sample in enumerate(snapshots):sample['observed_monotonic_ns']=1_000_000_000+i*150_000_000
 record.update(protocol=reader.PROTOCOL,reader_sha256=reader.sha(reader.__file__),snapshots=snapshots)
 return report,record,memory

class BoundedScene(unittest.TestCase):
 def test_complete_large_headers_are_reconstructed_without_unbounded_rpm(self):
  for family in ('mission-formation-v5','mission-formation-v6','mission-formation-v7','mission-formation-v8','mission-formation-v9'):
   r,e,m=fixture(family);self.assertEqual(m.maximum,8192)
   result=reader.verify(e,r,e['source_sha256']);self.assertTrue(result['scene_disposed_control_release'],result)
   self.assertFalse(result['restoration_verified']);self.assertFalse(result['return_verified'])
 def test_complete_raw_header_bytes_not_a_cached_boolean_are_required(self):
  for change in ('missing','changed_tail','decoded_lie'):
   r,e,m=fixture()
   if change=='missing':e['snapshots'][0].pop('header_before_hex')
   elif change=='changed_tail':e['snapshots'][0]['header_after_hex']=e['snapshots'][0]['header_after_hex'][:-2]+'01'
   else:e['snapshots'][0]['native_before']['seq']+=1;e['snapshots'][0]['native_after']['seq']+=1
   self.assertFalse(reader.verify(e,r,e['source_sha256'])['scene_disposed_control_release'],change)
 def test_legacy_direct_read_reproduces_observed_failure(self):
  r,e,m=fixture();ptr=e['snapshots'][0]['shared_pointer']
  with self.assertRaisesRegex(RuntimeError,'Read bounds'):m.read(ptr,27900)

if __name__=='__main__':unittest.main()
