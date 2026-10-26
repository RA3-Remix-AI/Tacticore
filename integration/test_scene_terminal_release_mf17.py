"""Synthetic complete-header fixtures; no field qualification or game access."""
import copy
import ctypes
import importlib.util
import json
import struct
import sys
import tempfile
import types
import unittest
import uuid
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
R=module('test_mf17_scene_reader',ROOT/'tactical/mission-formation-v17/scene_terminal_release.py')
L=module('test_mf17_scene_layout',ROOT/'tactical/mission-formation-v17/native_layout.py')
def uid(i):return str(uuid.UUID(int=i))
def words(i):return struct.unpack('<4I',uuid.UUID(uid(i)).bytes)

class Scene17(unittest.TestCase):
 def fixture(self,borrowed=True):
  h=L.Header();h.magic=0x4d463137;h.version=17;h.pid=123;h.thread=h.callback_thread=7
  for i,key in enumerate(('owner','ai','logic','personality','personality_id','player_template'),1):setattr(h,key,0x10000+i*0x1000)
  h.session[:]=words(1);h.commander[:]=words(2);h.command[:]=words(3);h.task[:]=words(4);h.seq=1;h.token=42
  start_time='2026-10-26T00:00:00+00:00';start=int(datetime.fromisoformat(start_time).timestamp()*1e7)+116444736000000000;h.start_low=start&0xffffffff;h.start_high=start>>32
  h.phase=4;h.error=31;h.restore_mask=131071;ci=h.controller_input;ci.controller[:]=words(3);ci.lease[:]=words(4);ci.formation[:]=words(5);ci.reserve_duration_frames=450;ci.lease_duration_frames=4500;ci.slot_count=2
  config=dict(controller_id=uid(3),lease_id=uid(4),formation_uuid=uid(5),slots=[])
  claims=[]
  for role in (0,1):
   inp=ci.slots[role];inp.role=role;inp.seq=role+1;inp.command[:]=words(10+role);inp.task[:]=words(20+role);inp.expected_cost=(85,220)[role];inp.unit_hash=(0x19ab11af,0x2c358c61)[role]
   config['slots'].append(dict(seq=role+1,command_id=uid(10+role),task_id=uid(20+role),cost=(85,220)[role]))
   if borrowed:
    slot=h.slots[role];slot.id=800+role;slot.thing=0x20000+role*0x1000;slot.update=0x30000+role*0x1000;slot.borrow_frame=100+role*20
    claims.append(dict(role=role,verified=True,object_id=slot.id,thing=slot.thing,update=slot.update,borrow_frame=slot.borrow_frame))
    if role==0:h.object_id=slot.id;h.unit=slot.thing;h.update=slot.update;h.detach_calls=1
    else:h.support.id=slot.id;h.support.thing=slot.thing;h.support.update=slot.update;h.support.detach_calls=1
  if borrowed:h.controller.reserve_start_frame=100;h.controller.reserve_deadline_frame=550;h.controller.hard_deadline_frame=4600;h.controller.held_mask=3;h.controller.channel_claimed=1
  native=R.plain(h);native['crumbs']=[[],[]]
  pre=dict(session_id=uid(1),pid=123,commander_id=uid(2),window_thread=7,**{key:hex(getattr(h,key)) for key in ('owner','ai','logic','personality','personality_id','player_template')})
  report=dict(status='finished',host_exit=9,session_id=uid(1),package_sha256='a'*64,executable_sha256=R.EXE,native=native,preflight=pre,request=dict(command_id=uid(3),task_id=uid(4),seq=1,token=42),controller_input=R.plain(ci),controller_config=config)
  entries=[dict(address=0x400000+i*16,expected='558bec') for i in range(17)]
  profile=dict(Header=L.Header,header_size=ctypes.sizeof(L.Header),layout_sha256='d'*64,entries=entries,claim_facts=dict(clock=dict(verified=borrowed,start=100,reserve_deadline=550,hard_deadline=4600),claims=claims),commit_verified=True)
  world=dict(global_logic=h.logic,logic_vtable=0xbeb630,frame=0,live_head=0,mode=9,owner_vtable=0xc5bce0,owner_index=3,owner_ai=0)
  sample=dict(module_base=0x10000000,shared_pointer=0x20000000,shared_pointer_after=0x20000000,timer=0,timer_after=0,header_before_hex=bytes(h).hex(),header_after_hex=bytes(h).hex(),scene_before=world,scene_after=copy.deepcopy(world),entries=[dict(e,actual=e['expected']) for e in entries],observed_monotonic_ns=1_000_000_000)
  other=copy.deepcopy(sample);other['observed_monotonic_ns']+=150_000_000
  session=dict(session_id=uid(1),pid=123,mod_sha256='a'*64,start_time=start_time)
  record=dict(protocol=R.PROTOCOL,source_sha256='b'*64,reader_sha256=R.sha(R.__file__),layout_sha256='d'*64,mutations=False,pid=123,session=session,process_executable_sha256=R.EXE,process_start_filetime=start,snapshots=[sample,other],**{k:False for k in R.FALSE_FLAGS})
  return record,report,profile
 def check(self,record,report,profile):
  with patch.object(R,'source_profile',return_value=profile),patch.object(ctypes,'WinDLL',side_effect=AssertionError('no process access')):return R.verify(record,report,'b'*64)
 def test_actual_complete_header_scene_fixture_only_releases_exclusivity(self):
  record,report,profile=self.fixture();original=json.dumps(report,sort_keys=True);result=self.check(record,report,profile)
  self.assertTrue(result['control_release_verified']);self.assertTrue(result['scene_closed_verified'])
  self.assertEqual([a['object_id'] for a in result['actors']],[800,801]);self.assertTrue(all(a['released'] and not a['returned'] and not a['disposed'] for a in result['actors']))
  for key in R.FALSE_FLAGS:self.assertIs(result[key],False)
  self.assertEqual(json.dumps(report,sort_keys=True),original)
 def test_never_borrowed_zero_slots_can_close_channel_without_actor_claim(self):
  record,report,profile=self.fixture(False);result=self.check(record,report,profile)
  self.assertTrue(result['control_release_verified']);self.assertTrue(all(a['never_held'] and a['object_id'] is None for a in result['actors']))
 def test_live_pause_empty_or_partial_scene_and_changed_hook_never_release(self):
  for key,value in (('frame',100),('live_head',0x99900),('mode',8),('owner_ai',0x123000),('owner_index',4)):
   record,report,profile=self.fixture();record['snapshots'][0]['scene_before'][key]=value;record['snapshots'][0]['scene_after'][key]=value
   with self.subTest(key=key):self.assertFalse(self.check(record,report,profile)['control_release_verified'])
  for change in ('timer','hook','pointer','delay','missing'):
   record,report,profile=self.fixture()
   if change=='timer':record['snapshots'][0]['timer']=1
   if change=='hook':record['snapshots'][0]['entries'][0]['actual']='909090'
   if change=='pointer':record['snapshots'][1]['shared_pointer']+=4
   if change=='delay':record['snapshots'][1]['observed_monotonic_ns']=record['snapshots'][0]['observed_monotonic_ns']
   if change=='missing':record['snapshots'].pop()
   with self.subTest(change=change):self.assertFalse(self.check(record,report,profile)['control_release_verified'])
 def test_complete_header_binding_rejects_changed_slot_lease_commit_or_clock(self):
  for field in ('controller','slot','commit','clock','start','halfheader'):
   record,report,profile=self.fixture();sample=record['snapshots'][0];h=L.Header.from_buffer_copy(bytes.fromhex(sample['header_before_hex']))
   if field=='controller':h.controller_input.lease[0]+=1
   if field=='slot':h.slots[1].id+=1
   if field=='commit':h.mission_commit.body.target_id=999
   if field=='clock':h.controller.hard_deadline_frame+=1
   if field=='start':h.start_low+=1
   sample['header_before_hex']=sample['header_after_hex']=bytes(h).hex()
   if field=='halfheader':sample['header_after_hex']=sample['header_after_hex'][:-8]
   with self.subTest(field=field):self.assertFalse(self.check(record,report,profile)['control_release_verified'])
 def test_exact_report_metadata_cannot_replace_physical_identity_or_historical_claims(self):
  for change in ('claim','clock','commit','source','process','package','reader','normal_return','error32','host'):
   record,report,profile=self.fixture()
   if change=='claim':profile['claim_facts']['claims'][0]['verified']=False
   if change=='clock':profile['claim_facts']['clock']['verified']=False
   if change=='commit':profile['commit_verified']=False
   if change=='source':record['source_sha256']='c'*64
   if change=='process':record['process_start_filetime']+=100_000
   if change=='package':record['session']['mod_sha256']='e'*64
   if change=='reader':record['reader_sha256']='e'*64
   if change=='normal_return':record['return_verified']=True
   if change=='host':report['host_exit']=None
   if change=='error32':report['native']['error']=32
   with self.subTest(change=change):self.assertFalse(self.check(record,report,profile)['control_release_verified'])
 def test_source_pin_failure_cannot_be_cached_as_success(self):
  record,report,profile=self.fixture()
  with patch.object(R,'source_profile',side_effect=ValueError('source changed')):self.assertFalse(R.verify(record,report,'b'*64)['control_release_verified'])
 def test_scene_failure_requires_actual_host_exit_nine_not_success_or_unknown(self):
  for code in (None,0,1,8,10,True,'9'):
   record,report,profile=self.fixture();report['host_exit']=code
   with self.subTest(code=code):self.assertFalse(self.check(record,report,profile)['control_release_verified'])
 def test_short_reads_rejected_and_large_header_read_in_bounded_pages(self):
  class Memory:
   def __init__(self):self.sizes=[]
   def read(self,address,size):self.sizes.append(size);return b'x'*size
  m=Memory();self.assertEqual(len(R.exact_read(m,0x10000,ctypes.sizeof(L.Header))),ctypes.sizeof(L.Header));self.assertTrue(all(n<=0x2000 for n in m.sizes))
  with patch.object(m,'read',return_value=b''):
   with self.assertRaises(ValueError):R.exact_read(m,0x10000,4)
 def test_real_historical_auditor_keeps_exact_terminal_reset_without_changing_raw(self):
  # Reuse historical actual payload bytes as a SOFTWARE fixture only. Namespace
  # and arm-reader metadata below are explicitly adapted; this is not Source17.
  folder=ROOT/'tactical/mission-formation-v17';q=module('test_scene17_original_history',folder/'reserve_controller_audit.py')
  path=ROOT/'acceptance/runs/20261026-082848-commander/paid-pair16-v2-01-controller.json';before=path.read_bytes();r=json.loads(before.decode('utf-8-sig'))
  r['native'].update(magic=0x4d463137,version=17,phase=4,error=31,active=0,restore_mask=131071,count=len(r['events']));r['host_exit']=9
  r['events'][-1].update(kind=4,frame=0,native_error=31,seq=len(r['events']))
  r['producer_readonly_at_arm'].update(protocol='mf17_running_producer_readonly_at_arm_v1',reader_sha256=R.sha(folder/'producer_binding.py'))
  frozen=json.dumps(r,sort_keys=True);facts=q.historical_borrow_facts(r)
  self.assertTrue(facts['clock']['verified']);self.assertEqual([a['object_id'] for a in facts['claims']],[801,804]);self.assertFalse(facts['ready']['verified'])
  for flag in ('scene_closed_verified','control_release_verified','return_verified','physical_retreat_verified','completed'):self.assertIs(facts[flag],False)
  self.assertFalse(q.live_facts(r)['verified']);self.assertEqual(json.dumps(r,sort_keys=True),frozen);self.assertEqual(path.read_bytes(),before)
  for change in ('middle_reset','other_terminal','twice_terminal','host','count'):
   bad=copy.deepcopy(r)
   if change=='middle_reset':bad['events'][100]['frame']=0
   if change=='other_terminal':bad['events'][-1]['native_error']=32
   if change=='twice_terminal':bad['events'][-2]['kind']=4
   if change=='host':bad['host_exit']=0
   if change=='count':bad['native']['count']-=1
   with self.subTest(change=change):self.assertFalse(q.historical_borrow_facts(bad)['verified'])
 def test_transition_wait_and_failed_attempt_sibling_preserve_original(self):
  record,report,profile=self.fixture();start=record['process_start_filetime'];reader_sha=R.sha
  class Memory:
   handle=1;path=Path('FAKE-EXE-FOR-SOFTWARE-TEST')
   def __init__(self,*args):pass
   def close(self):pass
  def process_times(handle,*values):
   values[0]._obj.dwHighDateTime=start>>32;values[0]._obj.dwLowDateTime=start&0xffffffff;return True
  fake=types.SimpleNamespace(Memory=Memory,k=types.SimpleNamespace(GetProcessTimes=process_times))
  sha=lambda path:R.EXE if Path(path)==Memory.path else reader_sha(path)
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);raw=root/'controller.json';raw.write_text(json.dumps(report),encoding='utf-8');session=root/'session.json';session.write_text(json.dumps(record['session']),encoding='utf-8');output=root/'scene.json'
   bad=copy.deepcopy(record['snapshots']);bad[0]['scene_before']['mode']=bad[0]['scene_after']['mode']=8
   with patch.dict(sys.modules,{'observe_production':fake,'session_package':types.SimpleNamespace(verify_session_package=lambda session:None)}),patch.object(R,'source_profile',return_value=profile),patch.object(R,'sha',side_effect=sha),patch.object(R,'module_base',return_value=0x10000000),patch.object(R.time,'sleep'),patch.object(R.time,'monotonic',side_effect=[0,3]),patch.object(R,'snapshot',side_effect=bad):
    first=R.collect(raw,session,output)
   self.assertFalse(first['control_release_verified']);old=output.read_bytes()
   # Second attempt starts during transition, then obtains two actual closed
   # fixture samples. It uses a fresh sibling rather than rewriting failure.
   samples=bad+copy.deepcopy(record['snapshots'])
   with patch.dict(sys.modules,{'observe_production':fake,'session_package':types.SimpleNamespace(verify_session_package=lambda session:None)}),patch.object(R,'source_profile',return_value=profile),patch.object(R,'sha',side_effect=sha),patch.object(R,'module_base',return_value=0x10000000),patch.object(R.time,'sleep'),patch.object(R.time,'monotonic',side_effect=[0,.1]),patch.object(R,'snapshot',side_effect=samples):
    second=R.collect(raw,session,output)
   self.assertTrue(second['control_release_verified']);self.assertEqual(second['scene_release']['sidecar_path'],str(root/'scene-attempt2.json'));self.assertEqual(output.read_bytes(),old)

if __name__=='__main__':unittest.main()
