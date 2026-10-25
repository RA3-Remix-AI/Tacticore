"""Read-only proof that a dead ordered-attack actor no longer owns a lease.

Never changes the original report, game memory, debug state or hooks. An absent
actor releases exclusivity only; it never creates a successful task or AI return.
"""
import argparse,ctypes as c,hashlib,importlib.util,json,struct,sys,time,uuid
from ctypes import wintypes as w
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'production'),str(HERE.parent/'integration')]
from observe_production import Memory
from session_package import verify_session_package
from ordered_qualification import EXE

MISSION_LAYOUT={'dll_sha256': 'ed17953bcc916a007ea30694af703984598e8d148269f8ec23db3e5243bbd130', 'timer_rva': 90784, 'shared_pointer_rva': 90800}
MISSION_LAYOUT_SHA='d0a582c7c42bd11ff9837b6ee0103986a7925a8652d1c339de44b0e0e150ebe8'

def profile(report):
 if report.get('native_binary_sha256')!=MISSION_LAYOUT['dll_sha256']:raise ValueError('unsupported_mission_disposal_binary')
 return dict(directory='mission-combat-v6',dll='TacticalMissionCombat6.dll',layout=MISSION_LAYOUT,layout_sha256=MISSION_LAYOUT_SHA,mask=16383,magic=0x4d435436,version=14,hook_count=14)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def trusted_entries(report=None):
 selected=profile(report or {});path=HERE/selected['directory']/'inert-layout.json'
 if sha(path)!=selected['layout_sha256']:raise ValueError('inert_layout_changed')
 return json.loads(path.read_text(encoding='utf-8'))['entries']
def uword(value):return int(value,0) if isinstance(value,str) else value
def pe_bytes(path,address,length):
 data=Path(path).read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];sections=struct.unpack_from('<H',data,pe+6)[0];size=struct.unpack_from('<H',data,pe+20)[0];optional=pe+24;base=struct.unpack_from('<I',data,optional+28)[0];rva=address-base
 for i in range(sections):
  at=optional+size+i*40;virtual_size,virtual,raw_size,raw=struct.unpack_from('<4I',data,at+8)
  if virtual<=rva and rva+length<=virtual+raw_size:return data[raw+rva-virtual:raw+rva-virtual+length]
 raise ValueError('entry_not_file_backed')

def runtime(directory='mission-combat-v6'):
 spec=importlib.util.spec_from_file_location('readonly_ordered_runtime',HERE/directory/'lease.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def module_base(memory,path):
 api=c.WinDLL('psapi',use_last_error=True);api.EnumProcessModulesEx.argtypes=[w.HANDLE,c.POINTER(w.HMODULE),w.DWORD,c.POINTER(w.DWORD),w.DWORD];api.EnumProcessModulesEx.restype=w.BOOL;api.GetModuleFileNameExW.argtypes=[w.HANDLE,w.HMODULE,w.LPWSTR,w.DWORD];api.GetModuleFileNameExW.restype=w.DWORD
 mods=(w.HMODULE*1024)();needed=w.DWORD()
 if not api.EnumProcessModulesEx(memory.handle,mods,c.sizeof(mods),c.byref(needed),3) or needed.value>c.sizeof(mods):raise ValueError('module_inventory_failed')
 found=[]
 for mod in mods[:needed.value//c.sizeof(w.HMODULE)]:
  text=c.create_unicode_buffer(32768)
  if not api.GetModuleFileNameExW(memory.handle,mod,text,len(text)):raise ValueError('module_path_failed')
  if Path(text.value).resolve()==path.resolve():found.append(int(mod))
 if len(found)!=1:raise ValueError('exact_loaded_dll_missing')
 return found[0]

def eligibility(report):
 selected=profile(report)
 n=report.get('native',{});pre=report.get('preflight',{});rq=report.get('request',{});owner=uword(pre.get('owner',0));manager=uword(pre.get('ai',0))+0x104;thread=pre.get('window_thread')
 binding=n.get('session_id')==report.get('session_id')==pre.get('session_id') and n.get('commander_id')==pre.get('commander_id') and n.get('command_id')==rq.get('command_id') and n.get('task_id')==rq.get('task_id') and type(rq.get('seq')) is int and rq['seq']>0 and n.get('seq')==rq['seq'] and n.get('callback_thread')==thread
 removed=all(any(e.get('kind')==kind and e.get('tag')==1 and e.get('arg')==manager and e.get('owner')==owner and e.get('thread')==thread and (kind!=18 or e.get('caller')==0x838877) for e in report.get('events',[])) for kind in [18,19])
 return bool(binding and removed and report.get('native_binary_sha256')==selected['layout']['dll_sha256'] and report.get('executable_sha256')==EXE and n.get('phase')==4 and n.get('error')==32 and n.get('restore_mask')==selected['mask'] and n.get('active')==0 and n.get('overflow')==0 and n.get('issued_frame',0)>0 and n.get('detach_calls')==1 and n.get('return_calls')==n.get('return_verified')==0)

def inert(memory,report,base,rt):
 selected=profile(report);layout=selected['layout'];pre=report['preflight'];rq=report['request'];ptr=memory.u32(base+layout['shared_pointer_rva']);timer=memory.u32(base+layout['timer_rva']);prefix=memory.read(ptr,rt.Tactical.events.offset);s=rt.Tactical();c.memmove(c.addressof(s),prefix,len(prefix))
 def ident(field):return str(uuid.UUID(bytes=struct.pack('<4I',*getattr(s,field))))
 checks=[timer==0,s.magic==selected['magic'],s.version==selected['version'],s.pid==pre['pid'],s.thread==pre['window_thread'],s.callback_thread==pre['window_thread'],s.token==rq['token'],s.seq==rq['seq'],ident('session')==report['session_id'],ident('commander')==pre['commander_id'],ident('command')==rq['command_id'],ident('task')==rq['task_id'],s.object_id==pre['selected']['object_id'],s.unit==uword(pre['selected']['address']),s.type_hash==uword(pre['selected']['type_hash']),s.owner==uword(pre['owner']),s.ai==uword(pre['ai']),s.personality==uword(pre['personality']),s.logic==uword(pre['logic']),s.phase==4,s.error==32,s.active==0,s.restore_mask==selected['mask'],s.detach_calls==1,s.return_calls==s.return_verified==0,s.overflow==0]
 entries=[]
 for hook in trusted_entries(report):
  address=hook['address'];expected=bytes.fromhex(hook['expected']);actual=memory.read(address,len(expected));entries.append(dict(address=address,expected=expected.hex(),actual=actual.hex()))
 if not all(checks) or len(entries)!=selected['hook_count'] or any(x['actual']!=x['expected'] for x in entries):raise ValueError('native_not_inert_or_binding_changed')
 return dict(timer=timer,phase=s.phase,error=s.error,restore_mask=s.restore_mask,active=s.active,shared_pointer=hex(ptr),module_base=hex(base),token=s.token,seq=s.seq,entries=entries,pid=s.pid,thread=s.thread,session_id=ident('session'),commander_id=ident('commander'),command_id=ident('command'),task_id=ident('task'),object_id=s.object_id,type_hash=hex(s.type_hash),owner=hex(s.owner))

def live_scan(memory,logic,actor):
 if memory.u32(0xcd8ce4)!=logic or memory.u32(logic)!=0xbeb630:raise ValueError('scene_changed')
 start=memory.u32(logic+0x50);head=memory.u32(logic+0xb4);pointer=head;seen=set();ids=[]
 while pointer:
  if pointer%4 or pointer in seen or len(seen)>=20000:raise ValueError('live_list_corrupt_or_bound')
  seen.add(pointer);block=memory.read(pointer,0xe0);vt=struct.unpack_from('<I',block)[0];oid=struct.unpack_from('<I',block,0xdc)[0]
  if vt!=0xc4db60 or not oid or oid in ids:raise ValueError('live_list_identity_invalid')
  if oid==actor:raise ValueError('actor_id_still_live')
  ids.append(oid);pointer=struct.unpack_from('<I',block,0x7c)[0]
 end=memory.u32(logic+0x50)
 if not ids or end!=start or memory.u32(logic+0xb4)!=head or memory.u32(0xcd8ce4)!=logic:raise ValueError('live_list_changed_during_scan')
 return dict(complete=True,logic=hex(logic),frame=start,end_frame=end,count=len(ids),ids=ids)

def verify(evidence,report,source_sha):
 selected=profile(report)
 scans=evidence.get('scans',[]);states=evidence.get('inert_snapshots',[]);oid=report.get('preflight',{}).get('selected',{}).get('object_id')
 checks=dict(source=eligibility(report) and evidence.get('source_sha256')==source_sha,session=evidence.get('session_id')==report.get('session_id') and evidence.get('pid')==report.get('preflight',{}).get('pid'),layout=evidence.get('layout')==selected['layout'],collection_no_error=not evidence.get('error'),failed_only=evidence.get('completed') is False and evidence.get('goal_observed') is False and evidence.get('return_verified') is False)
 checks['complete_absent_scans']=len(scans)==2 and all(s.get('complete') is True and s.get('logic')==report['preflight']['logic'] and type(s.get('frame')) is int and s['frame']==s.get('end_frame') and s['frame']>=report['native']['issued_frame'] and type(s.get('ids')) is list and 1<=len(s['ids'])==s.get('count')<=20000 and len(set(s['ids']))==len(s['ids']) and all(type(x) is int and x>0 for x in s['ids']) and oid not in s['ids'] for s in scans)
 checks['advancing_scans']=len(scans)==2 and scans[0].get('end_frame',0)<scans[1].get('frame',0)
 expected=trusted_entries(report)
 checks['inert_before_after']=len(states)==2 and all(s.get('timer')==s.get('active')==0 and s.get('phase')==4 and s.get('error')==32 and s.get('restore_mask')==selected['mask'] and s.get('token')==report['request']['token'] and s.get('seq')==report['request']['seq'] and [{k:x.get(k) for k in ['address','expected']} for x in s.get('entries',[])]==expected and all(x.get('expected')==x.get('actual') for x in s['entries']) for s in states) and states[0].get('shared_pointer')==states[1].get('shared_pointer') and states[0].get('module_base')==states[1].get('module_base')
 expected_binding=dict(pid=report['preflight']['pid'],thread=report['preflight']['window_thread'],session_id=report['session_id'],commander_id=report['preflight']['commander_id'],command_id=report['request']['command_id'],task_id=report['request']['task_id'],object_id=oid,type_hash=report['preflight']['selected']['type_hash'],owner=report['preflight']['owner'])
 checks['inert_actor_binding']=len(states)==2 and all(all(s.get(key)==value for key,value in expected_binding.items()) for s in states)
 okay=all(checks.values());return dict(control_release_verified=okay,restoration_verified=okay,disposed_verified=okay,return_verified=False,completion_claim=False,semantics='actor_id_disposed_exclusive_control_released' if okay else 'unknown',checks=checks)

def collect(report_path,session_path,output=None,timeout=12):
 report_path=Path(report_path);source=report_path.read_bytes();report=json.loads(source);session_path=Path(session_path);session_raw=session_path.read_bytes();session=json.loads(session_raw.decode('utf-8-sig'));output=Path(output) if output else report_path.with_suffix('.disposal.json')
 if output.exists():raise ValueError('existing_disposal_evidence_requires_recovery')
 if not eligibility(report):raise ValueError('not_an_unreturned_terminal_actor_loss')
 if session['session_id']!=report['session_id'] or session['pid']!=report['preflight']['pid']:raise ValueError('session_mismatch')
 selected=profile(report);package=verify_session_package(session);rt=runtime(selected['directory']);dll=HERE/selected['directory']/'bin'/selected['dll']
 if sha(dll)!=selected['layout']['dll_sha256']:raise ValueError('dll_revision_changed')
 memory=Memory(session['pid'],session);record=dict(schema=1,source_report=str(report_path.resolve()),source_sha256=hashlib.sha256(source).hexdigest(),session_id=session['session_id'],pid=session['pid'],start_time=session['start_time'],actor_id=report['preflight']['selected']['object_id'],completed=False,goal_observed=False,return_verified=False,mutations=False,layout=selected['layout'],scans=[],inert_snapshots=[],reader_sha256=sha(__file__))
 try:
  base=module_base(memory,dll);record['inert_snapshots'].append(inert(memory,report,base,rt));deadline=time.monotonic()+min(20,max(1,timeout));last_error=None
  while time.monotonic()<deadline and len(record['scans'])<2:
   if session_path.read_bytes()!=session_raw or report_path.read_bytes()!=source:raise ValueError('source_or_session_changed')
   pre=report['preflight'];owner=uword(pre['owner']);ai=uword(pre['ai']);person=uword(pre['personality'])
   if memory.u32(memory.u32(0xce8c9c)+0x30+3*4)!=owner or memory.u32(owner)!=0xc5bce0 or memory.u32(owner+0x20)!=3 or memory.u32(owner+0x90)!=ai or memory.u32(ai)!=0xc60f60 or memory.u32(ai+0x8b0)!=person or memory.u32(person+0x18)!=uword(pre['personality_id']):raise ValueError('player_or_commander_lifecycle_changed')
   try:
    scan=live_scan(memory,uword(pre['logic']),record['actor_id'])
    if not record['scans'] or scan['frame']>record['scans'][-1]['end_frame']:record['scans'].append(scan)
   except ValueError as error:last_error=str(error)
   if len(record['scans'])<2:time.sleep(.08)
  record['inert_snapshots'].append(inert(memory,report,base,rt))
  if session_path.read_bytes()!=session_raw or report_path.read_bytes()!=source or sha(package)!=session['mod_sha256']:raise ValueError('source_or_package_changed')
  record['last_scan_error']=last_error;record['assessment']=verify(record,report,record['source_sha256'])
 except Exception as error:
  record['error']=str(error);record['assessment']=verify(record,report,record['source_sha256'])
 finally:memory.close()
 rt.durable(output,record);return dict(record['assessment'],evidence_path=str(output.resolve()),evidence_sha256=sha(output))

def verify_path(evidence_path,source_report):
 """Host-side independent recheck of a failed receipt's disposal sidecar."""
 evidence_path=Path(evidence_path);source_report=Path(source_report);evidence=json.loads(evidence_path.read_text(encoding='utf-8'));source=source_report.read_bytes();report=json.loads(source.decode('utf-8-sig'))
 if Path(evidence.get('source_report','')).resolve()!=source_report.resolve() or evidence.get('reader_sha256')!=sha(__file__):raise ValueError('disposal_source_or_reader_changed')
 result=verify(evidence,report,hashlib.sha256(source).hexdigest());return dict(result,evidence_path=str(evidence_path.resolve()),evidence_sha256=sha(evidence_path))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path);parser.add_argument('--timeout',type=float,default=12);args=parser.parse_args();print(json.dumps(collect(args.report,args.session,args.output,args.timeout),indent=2))
