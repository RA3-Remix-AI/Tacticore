"""Scene-release pure tests: no game collection or SDK. Saved RO facts only seed fixtures."""
import copy,hashlib,importlib.util,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import scene_terminal_release as s
P=Path(__file__).resolve().parent;RUN=P.parent/'acceptance/runs'
class Memory:
 def __init__(self):self.values={}
 def put(self,address,data):
  for i,v in enumerate(data):self.values[address+i]=v
 def u32(self,address):return struct.unpack('<I',self.read(address,4))[0]
 def read(self,address,n):return bytes(self.values[address+i] for i in range(n))
 def word(self,address,value):self.put(address,struct.pack('<I',value))
def fixture(family='mission-combat-v7'):
 if family=='mission-combat-v7':directory=RUN/'20261025-161545-commander';file='main-mct7-01.json'
 else:directory=RUN/'20261025-154511-commander';file='coord-mf4-02.json'
 r=json.loads((directory/file).read_text(encoding='utf-8-sig'));session=json.loads((directory/'session.json').read_text(encoding='utf-8-sig'));r['native'].update(phase=4,error=31,active=0,overflow=0);name,p=s.profile(r);pre=r['preflight'];rq=r['request'];n=r['native'];memory=Memory();base=0x20000000;ptr=0x30000000;block=bytearray(p['header'])
 values=dict(magic=p['magic'],version=p['version'],pid=pre['pid'],thread=pre['window_thread'],callback_thread=pre['window_thread'],owner=s.num(pre['owner']),ai=s.num(pre['ai']),logic=s.num(pre['logic']),personality=s.num(pre['personality']),personality_id=s.num(pre['personality_id']),unit=s.num(pre['selected']['address']),object_id=pre['selected']['object_id'],type_hash=s.num(pre['selected']['type_hash']),update=s.num(pre['selected']['ai_address']),token=rq['token'],seq=rq['seq'],phase=4,error=31,active=0,restore_mask=p['mask'],overflow=0)
 values.update({k:n[k] for k in ['issued_frame','returned_frame','detach_calls','return_calls','return_verified']});values['player_template']=s.num(pre['player_template'])
 ticks=int(round(s.datetime.fromisoformat(session['start_time']).timestamp()*1e7))+116444736000000000;values.update(start_low=ticks&0xffffffff,start_high=ticks>>32)
 for k,value in values.items():struct.pack_into('<I',block,s.COMMON[k],value)
 import uuid
 for k,value in [('session',r['session_id']),('commander',pre['commander_id']),('command',rq['command_id']),('task',rq['task_id'])]:block[s.COMMON[k]:s.COMMON[k]+16]=uuid.UUID(value).bytes
 if family=='mission-formation-v4':
  support=pre['support'];row=dict(thing=s.num(support['address']),id=support['object_id'],hash=s.num(support['type_hash']),update=s.num(support['ai_address']),**{k:n['support'][k] for k in ['detach_calls','return_calls','returned']})
  for k,offset in [('thing',0),('id',4),('hash',8),('update',12),('detach_calls',20),('return_calls',24),('returned',28)]:struct.pack_into('<I',block,484+offset,row[k])
 memory.put(ptr,block);memory.word(base+p['pointer_rva'],ptr);memory.word(base+p['timer_rva'],0);logic=s.num(pre['logic']);owner=s.num(pre['owner']);memory.word(0xcd8ce4,logic)
 for address,value in [(logic,0xbeb630),(logic+0x50,0),(logic+0xb4,0),(logic+0x148,9),(logic+0x15c,0),(owner,0xc5bce0),(owner+0x20,3),(owner+0x90,0)]:memory.word(address,value)
 for entry in s.expected_entries(r):memory.put(entry['address'],bytes.fromhex(entry['expected']))
 first=s.snapshot(memory,r,base);second=s.snapshot(memory,r,base);first['observed_monotonic_ns']=1000000000;second['observed_monotonic_ns']=1150000000
 raw=json.dumps(r).encode();record=dict(protocol=s.PROTOCOL,directory=family,source_sha256=hashlib.sha256(raw).hexdigest(),native_binary_sha256=p['binary'],reader_sha256=s.sha(s.__file__),session=session,session_start_time=session['start_time'],session_id=session['session_id'],pid=session['pid'],process_executable_sha256=s.EXE,process_start_filetime=ticks,return_verified=False,completed=False,goal_observed=False,mutations=False,snapshots=[first,second]);return r,record
class SceneRelease(unittest.TestCase):
 def test_both_profiles_fake_rpm_positive_is_release_only(self):
  for family in s.PROFILES:
   r,e=fixture(family);a=s.verify(e,r,e['source_sha256']);self.assertTrue(a['scene_disposed_verified'],(family,a));self.assertTrue(a['control_release_verified']);self.assertEqual(a['semantics'],'scene_disposed_exclusive_control_released')
   for field in ['return_verified','physical_retreat_verified','completed','goal_observed','completion_claim','restoration_verified']:self.assertIs(a[field],False)
 def test_each_scene_positive_fact_is_required(self):
  for key,value in [('global_logic',1),('logic_vtable',0),('frame',10),('live_head',0x1111),('mode',2),('owner_vtable',0),('owner_index',4),('owner_ai',0x444444)]:
   r,e=fixture()
   for sample in e['snapshots']:sample['scene_before'][key]=value;sample['scene_after'][key]=value
   self.assertFalse(s.verify(e,r,e['source_sha256'])['scene_disposed_verified'],key)
 def test_live_pause_is_not_closed_scene(self):
  r,e=fixture()
  for sample in e['snapshots']:
   for world in [sample['scene_before'],sample['scene_after']]:world.update(paused_raw=3,frame=2700,live_head=0x22222,mode=2,owner_ai=s.num(r['preflight']['ai']))
  self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'])
 def test_native_identity_corruption_for_both_profiles(self):
  for family in s.PROFILES:
   for key in ['token','seq','owner','ai','unit','object_id','logic','pid','thread','callback_thread','start_low','type_hash','update','player_template']:
    r,e=fixture(family)
    for sample in e['snapshots']:sample['native_before'][key]+=1;sample['native_after'][key]+=1
    self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'],(family,key))
 def test_formation_second_actor_cannot_be_omitted_or_replaced(self):
  for field in ['thing','id','hash','update']:
   r,e=fixture('mission-formation-v4')
   for sample in e['snapshots']:sample['native_before']['support'][field]+=1;sample['native_after']['support'][field]+=1
   self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'],field)
 def test_exact_hook_set_and_bytes_not_counts_or_booleans(self):
  for change in ['duplicate','actual','expected','missing']:
   r,e=fixture()
   for sample in e['snapshots']:
    if change=='duplicate':sample['entries']=[copy.deepcopy(sample['entries'][0]) for _ in sample['entries']]
    if change=='actual':sample['entries'][0]['actual']='00'
    if change=='expected':sample['entries'][0]['expected']='00'
    if change=='missing':sample['entries'].pop()
   self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'],change)
 def test_timer_active_or_nonterminal_cannot_release(self):
  for key,value in [('timer',1),('timer_after',1),('shared_pointer_after',1)]:
   r,e=fixture();e['snapshots'][0][key]=value;self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'],key)
  for key,value in [('active',1),('phase',1),('error',32),('restore_mask',31)]:
   r,e=fixture();e['snapshots'][0]['native_before'][key]=value;e['snapshots'][0]['native_after'][key]=value;self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'],key)
 def test_second_read_and_two_distinct_samples_required(self):
  for change in ['single','time','samepointer','unstableworld','unstableheader']:
   r,e=fixture()
   if change=='single':e['snapshots'].pop()
   if change=='time':e['snapshots'][1]['observed_monotonic_ns']=e['snapshots'][0]['observed_monotonic_ns']
   if change=='samepointer':e['snapshots'][1]['shared_pointer']=1
   if change=='unstableworld':e['snapshots'][0]['scene_after']['owner_ai']=1
   if change=='unstableheader':e['snapshots'][0]['native_after']['seq']+=1
   self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'],change)
 def test_raw_sha_reader_sha_cached_assessment_never_substitutes(self):
  r,e=fixture();e['assessment']={'control_release_verified':True};e['snapshots'][0]['timer']=1;self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'])
  r,e=fixture();self.assertFalse(s.verify(e,r,'0'*64)['control_release_verified']);e['reader_sha256']='0'*64;self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'])
 def test_dead_actor_error32_not_scene_release(self):
  r,e=fixture();r['native']['error']=32;self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'])
 def test_malformed_unsupported_fails_closed(self):
  for value in [None,{},{'snapshots':[None,None]}]:self.assertFalse(s.verify(value,{},'x')['control_release_verified'])
 def test_existing_scene_ro_facts_are_not_two_complete_snapshots(self):
  r,e=fixture();old=json.loads((RUN/'20261025-161545-commander/main-mct7-01-scene-terminal-readonly.json').read_text());e['snapshots']=[old];self.assertFalse(s.verify(e,r,e['source_sha256'])['control_release_verified'])
 def test_real_current_success_rejected_before_process_open(self):
  raw=RUN/'20261025-164701-commander/continuous-paid-mct7-01-combat-v7.json';session=raw.with_name('session.json')
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaisesRegex(ValueError,'not_this_ended_scene_request'):s.collect(raw,session,Path(folder)/'not-written.json')
   self.assertFalse((Path(folder)/'not-written.json').exists())
 def test_layout_offsets_match_real_frozen_ctypes_both_profiles(self):
  for family,file in [('mission-combat-v7','lease.py'),('mission-formation-v4','lease_ready_v2.py')]:
   sp=importlib.util.spec_from_file_location('scene_test_layout_'+family.replace('-','_'),P/family/file);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
   for key,offset in s.COMMON.items():self.assertEqual(getattr(m.Tactical,key).offset,offset,(family,key))
   self.assertEqual(m.Tactical.events.offset,s.PROFILES[family]['header'])
if __name__=='__main__':unittest.main()
