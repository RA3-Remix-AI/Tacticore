"""MF18 scene closure releases exclusivity, never return/home/effect.

Only explicit collect() opens a read-only process handle. verify()/verify_path()
use saved bytes; import never attaches. Native masks are never rewritten.
"""
import ctypes as c
import hashlib
import importlib.util
import json
import math
import struct
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
PROTOCOL='mf18_scene_terminal_release_v1'
EXE='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
EXE_PATH=Path('E:/RedRar3/Data/RA3_1.12.game')
FALSE_FLAGS=('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def number(value):return int(value,0) if type(value) is str else value
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def plain(value):
 if isinstance(value,c.Structure):return {key:plain(getattr(value,key)) for key,_ in value._fields_}
 if isinstance(value,c.Array):return [plain(item) for item in value]
 if type(value) is float and not math.isfinite(value):raise ValueError('scene_nonfinite_header')
 return value
def ident(words):return str(uuid.UUID(bytes=struct.pack('<4I',*words)))
def pe_bytes(path,address,length):
 data=Path(path).read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];count=struct.unpack_from('<H',data,pe+6)[0];optional=pe+24;size=struct.unpack_from('<H',data,pe+20)[0];rva=address-struct.unpack_from('<I',data,optional+28)[0]
 for i in range(count):
  at=optional+size+i*40;_,virtual,raw_size,raw=struct.unpack_from('<4I',data,at+8)
  if virtual<=rva and rva+length<=virtual+raw_size:return data[raw+rva-virtual:raw+rva-virtual+length]
 raise ValueError('scene_hook_not_file_backed')

def source_profile(report):
 q=load('mf18_scene_source_qualifier',HERE/'formation_mission_qualification.py')
 if not q.source_pins(report):raise ValueError('scene_source_pins')
 supplements=report.get('supplemental_sources',{})
 for name in ('scene_terminal_release.py','inert-layout.json'):
  if supplements.get(name)!=sha(HERE/name):raise ValueError('scene_reader_layout_not_source_pinned')
 layout=json.loads((HERE/'inert-layout.json').read_text(encoding='utf-8-sig'))
 if set(layout)!={'dll_sha256','timer_rva','shared_pointer_rva'} or layout['dll_sha256']!=report.get('native_binary_sha256') or any(type(layout[k]) is not int or not 0<layout[k]<0x1000000 or layout[k]%4 for k in ('timer_rva','shared_pointer_rva')):raise ValueError('scene_exact_inert_layout')
 L=load('mf18_scene_exact_native_layout',HERE/'native_layout.py')
 if report.get('native_layout_sha256')!=sha(HERE/'native_layout.py') or c.sizeof(L.Header)!=L.Tactical.events.offset:raise ValueError('scene_header_layout')
 source=(HERE/'lease.cpp').read_text();block=source.split('static Hook hooks[]={',1)[1].split(';',1)[0]
 import re
 entries=[dict(address=int(a,0),expected=b.replace('\\x','')) for a,b in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',block)]
 if len(entries)!=17 or len({e['address'] for e in entries})!=17:raise ValueError('scene_exact_seventeen_hooks')
 if sha(EXE_PATH)!=EXE or any(pe_bytes(EXE_PATH,e['address'],len(bytes.fromhex(e['expected']))).hex()!=e['expected'] for e in entries):raise ValueError('scene_pristine_executable_entries')
 records=[q.controller.reserve_record(e) for e in report.get('events',[]) if e.get('kind') in q.controller.RS_KINDS]
 committed=report.get('native',{}).get('mission_commit',{}).get('generation')==2
 return dict(layout=layout,layout_sha256=sha(HERE/'inert-layout.json'),header_size=c.sizeof(L.Header),Header=L.Header,entries=entries,claim_facts=q.controller.historical_borrow_facts(report),commit_verified=not committed or q.controller.commit_audit(report,records).get('verified') is True)

def header_binding(block,report,profile):
 if len(block)!=profile['header_size']:raise ValueError('scene_header_size')
 h=plain(profile['Header'].from_buffer_copy(block));n=report['native'];pre=report['preflight'];rq=report['request']
 # Every saved field must describe the actual complete header. The normal
 # wrapper publishes only the used prefix of each fixed-size crumb array.
 expected=dict(h)
 if 'crumbs' in h:expected['crumbs']=[h['crumbs'][r][:min(128,h['crumb_count'][r])] for r in (0,1)]
 if any(n.get(k)!=v for k,v in expected.items()):raise ValueError('scene_report_actual_header_mismatch')
 if h['magic']!=0x4d463138 or h['version']!=18 or h['pid']!=pre['pid'] or h['thread']!=pre['window_thread'] or h['callback_thread']!=pre['window_thread']:raise ValueError('scene_native_identity')
 for key in ('owner','ai','logic','personality','personality_id','player_template'):
  if h[key]!=number(pre[key]):raise ValueError('scene_owner_identity')
 for key in ('session','commander','command','task'):
  actual=ident(h[key]);wanted=report['session_id'] if key=='session' else pre['commander_id'] if key=='commander' else rq[key+'_id']
  if actual!=str(uuid.UUID(wanted)):raise ValueError('scene_uuid_binding')
 if h['seq']!=rq['seq'] or h['token']!=rq['token'] or type(h['seq']) is not int or h['seq']<=0 or h['token']<=0:raise ValueError('scene_outer_request')
 ci=h['controller_input'];config=report['controller_config']
 if ci!=report['controller_input'] or ident(ci['controller'])!=str(uuid.UUID(config['controller_id'])) or ident(ci['lease'])!=str(uuid.UUID(config['lease_id'])) or ident(ci['formation'])!=str(uuid.UUID(config['formation_uuid'])):raise ValueError('scene_controller_lease_binding')
 if ident(h['command'])!=ident(ci['controller']) or ident(h['task'])!=ident(ci['lease']):raise ValueError('scene_outer_controller_binding')
 if ci['reserve_duration_frames']!=450 or ci['lease_duration_frames']!=4500 or ci['slot_count']!=2:raise ValueError('scene_clock_policy')
 if h['mission_commit']['generation'] not in (0,2) or profile.get('commit_verified') is not True:raise ValueError('scene_write_once_commit_binding')
 actors=[]
 for role,s in enumerate(h['slots']):
  inp=ci['slots'][role];given=config['slots'][role]
  if inp['role']!=role or inp['seq']!=given['seq'] or ident(inp['command'])!=str(uuid.UUID(given['command_id'])) or ident(inp['task'])!=str(uuid.UUID(given['task_id'])) or inp['expected_cost']!=given['cost'] or inp['expected_cost']!=(85,220)[role] or inp['unit_hash']!=(0x19ab11af,0x2c358c61)[role]:raise ValueError('scene_child_identity')
  borrowed=bool(s['borrow_frame'])
  if not borrowed and (h['controller']['held_mask']&(1<<role) or (h['support']['detach_calls'] if role else h['detach_calls'])):raise ValueError('scene_never_held_conflict')
  if borrowed and (not s['id'] or not s['thing'] or not s['update']):raise ValueError('scene_borrow_actor')
  if borrowed:
   facts=profile['claim_facts'];clock=facts.get('clock',{});claims=[a for a in facts.get('claims',[]) if a.get('role')==role and a.get('verified') is True]
   if clock.get('verified') is not True or len(claims)!=1 or any(claims[0].get(k)!=v for k,v in dict(object_id=s['id'],thing=s['thing'],update=s['update'],borrow_frame=s['borrow_frame']).items()):raise ValueError('scene_original_borrow_not_independently_verified')
   ctl=h['controller']
   if (ctl['reserve_start_frame'],ctl['reserve_deadline_frame'],ctl['hard_deadline_frame'])!=(clock['start'],clock['start']+450,clock['start']+4500) or clock['reserve_deadline']!=ctl['reserve_deadline_frame'] or clock['hard_deadline']!=ctl['hard_deadline_frame']:raise ValueError('scene_original_deadlines')
  if role==0 and borrowed and (s['id']!=h['object_id'] or s['thing']!=h['unit'] or s['update']!=h['update']):raise ValueError('scene_front_identity')
  if role==1 and borrowed and (s['id']!=h['support']['id'] or s['thing']!=h['support']['thing'] or s['update']!=h['support']['update']):raise ValueError('scene_support_identity')
  actors.append(dict(role=role,object_id=s['id'] if borrowed else None,never_held=not borrowed,released=True,returned=False,disposed=False))
 if h['phase']!=4 or h['error']!=31 or h['active']!=0 or h['overflow']!=0 or h['restore_mask']!=(1<<17)-1:raise ValueError('scene_not_inert_error31')
 ids=[a['object_id'] for a in actors if not a['never_held']]
 if len(ids)!=len(set(ids)):raise ValueError('scene_roles_alias_actor')
 return h,actors

def world(memory,logic,owner):
 return dict(global_logic=memory.u32(0xcd8ce4),logic_vtable=memory.u32(logic),frame=memory.u32(logic+0x50),live_head=memory.u32(logic+0xb4),mode=memory.u32(logic+0x148),owner_vtable=memory.u32(owner),owner_index=memory.u32(owner+0x20),owner_ai=memory.u32(owner+0x90))
def exact_read(memory,address,length):
 if type(address) is not int or address<0x10000 or address+length>2**32:raise ValueError('scene_read_bounds')
 blocks=[]
 for offset in range(0,length,0x2000):
  size=min(0x2000,length-offset);part=memory.read(address+offset,size)
  if type(part) is not bytes or len(part)!=size:raise ValueError('scene_short_read')
  blocks.append(part)
 return b''.join(blocks)
def snapshot(memory,report,base,profile):
 layout=profile['layout'];pointer=memory.u32(base+layout['shared_pointer_rva']);timer=memory.u32(base+layout['timer_rva']);pre=report['preflight'];logic=number(pre['logic']);owner=number(pre['owner'])
 a=exact_read(memory,pointer,profile['header_size']);before=world(memory,logic,owner)
 entries=[dict(e,actual=memory.read(e['address'],len(bytes.fromhex(e['expected']))).hex()) for e in profile['entries']]
 after=world(memory,logic,owner);b=exact_read(memory,pointer,profile['header_size'])
 return dict(module_base=base,shared_pointer=pointer,shared_pointer_after=memory.u32(base+layout['shared_pointer_rva']),timer=timer,timer_after=memory.u32(base+layout['timer_rva']),header_before_hex=a.hex(),header_after_hex=b.hex(),scene_before=before,scene_after=after,entries=entries,observed_monotonic_ns=time.monotonic_ns())

def _verify(record,report,source_sha256):
 profile=source_profile(report);pre=report['preflight'];session=record['session'];samples=record['snapshots'];checks={}
 checks['source_reader_layout']=record.get('protocol')==PROTOCOL and record.get('source_sha256')==source_sha256 and record.get('reader_sha256')==sha(__file__) and record.get('layout_sha256')==profile['layout_sha256'] and record.get('mutations') is False
 # host.cpp returns 9 for a cleaned phase4 failure; only phase3 success is 0.
 checks['finished_original_host']=report.get('status')=='finished' and type(report.get('host_exit')) is int and report['host_exit']==9
 checks['original_session_package']=session.get('session_id')==report['session_id']==pre['session_id'] and session.get('pid')==pre['pid']==record.get('pid') and session.get('mod_sha256')==report.get('package_sha256') and record.get('process_executable_sha256')==report.get('executable_sha256')==EXE
 start=record['process_start_filetime'];checks['original_process_start']=type(start) is int and abs((start-116444736000000000)/1e7-datetime.fromisoformat(session['start_time']).timestamp())<.001
 checks['two_distinct_samples']=len(samples)==2 and all(type(s.get('observed_monotonic_ns')) is int for s in samples) and 100_000_000<=samples[1]['observed_monotonic_ns']-samples[0]['observed_monotonic_ns']<=5_000_000_000
 checks['collection_complete']=not record.get('collection_error_type')
 checks['same_module_pointer']=len(samples)==2 and samples[0].get('module_base')==samples[1].get('module_base') and type(samples[0].get('module_base')) is int and samples[0]['module_base']>=0x10000 and samples[0].get('shared_pointer')==samples[1].get('shared_pointer')
 checks['same_complete_inert_header']=len(samples)==2 and samples[0].get('header_before_hex')==samples[1].get('header_before_hex')
 checks['closed_scene_inert_bytes']=len(samples)==2;actors=[];h=None
 for sample in samples:
  a=bytes.fromhex(sample['header_before_hex']);b=bytes.fromhex(sample['header_after_hex']);h,actors=header_binding(a,report,profile)
  expected_world=dict(global_logic=number(pre['logic']),logic_vtable=0xbeb630,frame=0,live_head=0,mode=9,owner_vtable=0xc5bce0,owner_index=3,owner_ai=0)
  expected_entries={e['address']:e['expected'] for e in profile['entries']};rows=sample['entries']
  checks['closed_scene_inert_bytes'] &= a==b and sample['shared_pointer']==sample['shared_pointer_after'] and sample['timer']==sample['timer_after']==0 and sample['scene_before']==sample['scene_after']==expected_world and len(rows)==len({e['address'] for e in rows})==17 and {e['address']:e['actual'] for e in rows}==expected_entries and all(e['expected']==expected_entries[e['address']] for e in rows)
 if h is None:raise ValueError('scene_no_header')
 checks['same_process_header_start']=((h['start_high']<<32)|h['start_low'])==start
 checks['no_return_or_effect_claim']=all(record.get(k) is False for k in FALSE_FLAGS)
 ok=all(v is True for v in checks.values())
 return dict(protocol=PROTOCOL,status='scene_disposed_exclusive_control_released' if ok else 'not_verified',checks=checks,scene_closed_verified=ok,scene_disposed_control_release=ok,control_release_verified=ok,controller_id=ident(h['controller_input']['controller']),lease_id=ident(h['controller_input']['lease']),session_id=report['session_id'],pid=pre['pid'],actors=actors if ok else [],semantics='scene_disposed_exclusive_control_released' if ok else 'unknown',**{k:False for k in FALSE_FLAGS})
def verify(record,report,source_sha256):
 try:return _verify(record,report,source_sha256)
 except (OSError,ValueError,TypeError,KeyError,OverflowError,AttributeError,IndexError):return dict(protocol=PROTOCOL,status='not_verified',checks={'well_formed_source_pinned_scene':False},scene_closed_verified=False,scene_disposed_control_release=False,control_release_verified=False,actors=[],semantics='unknown',**{k:False for k in FALSE_FLAGS})

def module_base(memory,path):
 from ctypes import wintypes as w
 api=c.WinDLL('psapi',use_last_error=True);api.EnumProcessModulesEx.argtypes=[w.HANDLE,c.POINTER(w.HMODULE),w.DWORD,c.POINTER(w.DWORD),w.DWORD];api.EnumProcessModulesEx.restype=w.BOOL;api.GetModuleFileNameExW.argtypes=[w.HANDLE,w.HMODULE,w.LPWSTR,w.DWORD];api.GetModuleFileNameExW.restype=w.DWORD
 mods=(w.HMODULE*1024)();needed=w.DWORD()
 if not api.EnumProcessModulesEx(memory.handle,mods,c.sizeof(mods),c.byref(needed),3) or needed.value>c.sizeof(mods):raise ValueError('scene_module_inventory')
 found=[]
 for mod in mods[:needed.value//c.sizeof(w.HMODULE)]:
  name=c.create_unicode_buffer(32768)
  if not api.GetModuleFileNameExW(memory.handle,mod,name,len(name)):raise ValueError('scene_module_path')
  if Path(name.value).resolve()==path.resolve():found.append(int(mod))
 if len(found)!=1:raise ValueError('scene_exact_module')
 return found[0]
def collect(report_path,session_path,output=None):
 sys.path.insert(0,str(HERE.parent.parent/'production'))
 from observe_production import Memory,k
 from session_package import verify_session_package
 from ctypes import wintypes as w
 report_path=Path(report_path).resolve();raw=report_path.read_bytes();report=json.loads(raw.decode('utf-8-sig'));profile=source_profile(report);session=json.loads(Path(session_path).read_text(encoding='utf-8-sig'))
 if session.get('session_id')!=report['session_id'] or session.get('pid')!=report['preflight']['pid']:raise ValueError('scene_session_mismatch')
 verify_session_package(session);output=Path(output) if output else report_path.with_name(report_path.stem+'-scene-release-mf18.json')
 # Preserve every failed attempt. A transition sample must not permanently
 # occupy the only certificate filename; cap independent attempts at three.
 candidates=[output]+[output.with_name(output.stem+'-attempt'+str(i)+output.suffix) for i in (2,3)]
 for candidate in candidates:
  if not candidate.exists():output=candidate;break
  result=verify_path(candidate,report_path)
  if result['control_release_verified']:return dict(result,scene_release=dict(result))
 else:return dict(result,scene_release=dict(result))
 record=dict(protocol=PROTOCOL,source_report=str(report_path),source_sha256=hashlib.sha256(raw).hexdigest(),reader_sha256=sha(__file__),layout_sha256=profile['layout_sha256'],session=session,pid=session['pid'],mutations=False,snapshots=[],**{k:False for k in FALSE_FLAGS})
 memory=Memory(session['pid'],session)
 try:
  record['process_executable_sha256']=sha(memory.path);times=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(memory.handle,*[c.byref(t) for t in times]):raise ValueError('scene_process_start')
  record['process_start_filetime']=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime;base=module_base(memory,HERE/'bin/TacticalMissionFormation18.dll')
  deadline=time.monotonic()+2
  while True:
   record['snapshots']=[];record.pop('collection_error_type',None)
   try:
    record['snapshots'].append(snapshot(memory,report,base,profile));time.sleep(.15);record['snapshots'].append(snapshot(memory,report,base,profile))
   except Exception as error:record['collection_error_type']=type(error).__name__
   if verify(record,report,record['source_sha256'])['control_release_verified'] or time.monotonic()>=deadline:break
   time.sleep(.02)
 except Exception as error:record['collection_error_type']=type(error).__name__
 finally:memory.close()
 if report_path.read_bytes()!=raw:raise ValueError('scene_original_report_changed')
 record['assessment']=verify(record,report,record['source_sha256'])
 with output.open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2,allow_nan=False)
 result=verify_path(output,report_path);return dict(result,scene_release=dict(result))
def verify_path(sidecar_path,report_path):
 sidecar_path=Path(sidecar_path);report_path=Path(report_path);raw=report_path.read_bytes();record=json.loads(sidecar_path.read_text(encoding='utf-8-sig'));result=verify(record,json.loads(raw.decode('utf-8-sig')),hashlib.sha256(raw).hexdigest())
 return dict(result,sidecar_path=str(sidecar_path.resolve()),sidecar_sha256=sha(sidecar_path),source_sha256=hashlib.sha256(raw).hexdigest())
