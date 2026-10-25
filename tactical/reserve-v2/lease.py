"""Bounded normal-SDK stance primitive. No model, Move, Attack, or Source grant."""
import argparse,ctypes as c,hashlib,importlib.util,json,math,re,secrets,struct,subprocess,sys,time,uuid
from ctypes import wintypes as w
from pathlib import Path
HERE=Path(__file__).resolve().parent
def local_module(name,filename):
 spec=importlib.util.spec_from_file_location(name,HERE/filename);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
layout_module=local_module('rsv2_bound_native_layout','native_layout.py')
preflight=local_module('rsv2_bound_readonly_preflight','preflight.py')
birth_helper=local_module('rsv2_bound_paid_birth','birth_source.py')
rally_helper=local_module('rsv2_bound_own_rally','rally_source.py')
Probe=layout_module.Probe;Header=layout_module.Header;Event=layout_module.Event;U=c.c_uint32
DLL='TacticalReserve2.dll'
EXECUTE_ENABLED=True  # Joint review permits one bounded rally reserve primitive.

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def words(value):return struct.unpack('<4I',uuid.UUID(str(value)).bytes)

def plain(value,bad=None,path=''):
 bad=[] if bad is None else bad
 if isinstance(value,c.Structure):return {name:plain(getattr(value,name),bad,path+'.'+name) for name,_ in value._fields_}
 if isinstance(value,c.Array):return [plain(v,bad,path+'['+str(i)+']') for i,v in enumerate(value)]
 if isinstance(value,float) and not math.isfinite(value):bad.append(path);return None
 return value

def capture(report,shared):
 header=Header.from_buffer_copy(c.string_at(c.addressof(shared),c.sizeof(Header)));n=plain(header)
 for key in ('session','commander','command','task'):
  n[key+'_id']=str(uuid.UUID(bytes=struct.pack('<4I',*n[key])))
 events=report.setdefault('events',[])
 if header.count<len(events):raise ValueError('probe_published_prefix_regressed')
 for index in range(len(events),max(0,min(header.count,1024))):
  ptr=c.addressof(shared)+Probe.events.offset+index*c.sizeof(Event)
  if U.from_address(ptr).value!=index+1:break
  event=Event.from_buffer_copy(c.string_at(ptr,c.sizeof(Event)))
  if event.seq!=index+1 or U.from_address(ptr).value!=index+1:break
  bad=[];row=plain(event,bad,'event')
  if bad:row['invalid_float_fields']=bad
  events.append(row)
 report['native']=n
 terminal=header.phase in (3,4) and header.active==0
 report['status']='finished' if terminal else 'running'
 return terminal

def qualifier():return preflight.module('rsv2_independent_q',HERE/'reserve_qualification.py')

def source_record():
 q=qualifier();revision=json.loads((HERE/'revision.json').read_text());names={'native_binary_sha256':HERE/'bin'/DLL,'native_host_sha256':HERE/'bin/tactical_host.exe','native_source_sha256':HERE/'lease.cpp','native_shared_sha256':HERE/'shared.h'}
 for key,path in names.items():
  if sha(path)!=revision[key]:raise ValueError('probe_compiled_source_revision_changed')
 includes={p.name:sha(p) for p in HERE.glob('*.cpp.inc')}
 if includes!=revision['native_includes_sha256']:raise ValueError('probe_native_include_bundle_changed')
 actual=json.loads(subprocess.check_output([str(names['native_host_sha256']),'--layout'],text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
 if actual!=layout_module.layout():raise ValueError('probe_actual_host_abi_mismatch')
 return dict(**{k:sha(v) for k,v in names.items()},native_revision_sha256=sha(HERE/'revision.json'),native_includes_sha256=includes,wrapper_sha256=sha(__file__),native_layout_sha256=sha(HERE/'native_layout.py'),supplemental_sources={p.name:sha(p) for p in q.source_paths()},external_sources={p.relative_to(preflight.BRIDGE).as_posix():sha(p) for p in q.external_source_paths()},actual_host_abi=actual)

def unchanged_sources(record):
 try:
  q=qualifier();paths={'native_binary_sha256':HERE/'bin'/DLL,'native_host_sha256':HERE/'bin/tactical_host.exe','native_source_sha256':HERE/'lease.cpp','native_shared_sha256':HERE/'shared.h','native_revision_sha256':HERE/'revision.json','wrapper_sha256':Path(__file__),'native_layout_sha256':HERE/'native_layout.py'}
  return all(record.get(k)==sha(p) for k,p in paths.items()) and record['native_includes_sha256']=={p.name:sha(p) for p in HERE.glob('*.cpp.inc')} and record['supplemental_sources']=={p.name:sha(p) for p in q.source_paths()} and record['external_sources']=={p.relative_to(preflight.BRIDGE).as_posix():sha(p) for p in q.external_source_paths()}
 except (OSError,ValueError,KeyError):return False

def trusted_entries():
 text=(HERE/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
 rows=[dict(address=hex(int(a,0)),expected=b.replace('\\x','')) for a,b in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',text)]
 if len(rows)!=8 or len({r['address'] for r in rows})!=8:raise ValueError('probe_exact_hook_set')
 return rows

def module_base(memory):
 api=c.WinDLL('psapi',use_last_error=True);api.EnumProcessModulesEx.argtypes=[w.HANDLE,c.POINTER(w.HMODULE),w.DWORD,c.POINTER(w.DWORD),w.DWORD];api.EnumProcessModulesEx.restype=w.BOOL;api.GetModuleFileNameExW.argtypes=[w.HANDLE,w.HMODULE,w.LPWSTR,w.DWORD];api.GetModuleFileNameExW.restype=w.DWORD
 mods=(w.HMODULE*1024)();needed=w.DWORD()
 if not api.EnumProcessModulesEx(memory.handle,mods,c.sizeof(mods),c.byref(needed),3) or needed.value>c.sizeof(mods):raise ValueError('probe_module_inventory')
 found=[]
 for mod in mods[:needed.value//c.sizeof(w.HMODULE)]:
  path=c.create_unicode_buffer(32768)
  if not api.GetModuleFileNameExW(memory.handle,mod,path,len(path)):raise ValueError('probe_module_path')
  if Path(path.value).resolve()==(HERE/'bin'/DLL).resolve():found.append(int(mod))
 if len(found)!=1:raise ValueError('probe_exact_loaded_module')
 return found[0]

def terminal_readonly(memory,report):
 inert=json.loads((HERE/'inert-layout.json').read_text())
 if inert['dll_sha256']!=report['native_binary_sha256']:raise ValueError('probe_terminal_layout_revision')
 base=module_base(memory);pointer=memory.u32(base+inert['shared_pointer_rva']);before=memory.read(pointer,c.sizeof(Header));n=plain(Header.from_buffer_copy(before));rows=trusted_entries()
 for row in rows:row['actual']=memory.read(int(row['address'],0),len(bytes.fromhex(row['expected']))).hex()
 timer=memory.u32(base+inert['timer_rva']);after=memory.read(pointer,c.sizeof(Header))
 def identity(key):return str(uuid.UUID(bytes=struct.pack('<4I',*n[key])))
 thing=n['thing'];roster=preflight.module('rsv2_terminal_own_roster',preflight.BRIDGE/'integration/own_candidates.py');actual=roster.own_candidates(memory,3,roster.load_catalog());matches=[u for u in actual['candidates'] if u['object_id']==n['object_id'] and int(u['address'],0)==thing]
 if len(matches)==1:live_actor=dict(thing=thing,vtable=memory.u32(thing),object_id=memory.u32(thing+0xdc),owner=memory.u32(thing+0x418),template_ptr=memory.u32(thing+4),update=memory.u32(thing+0x374),team=memory.u32(thing+0x414),stance_module=memory.u32(thing+0x380),hp=memory.f32(memory.u32(thing+0x33c)+4),roster_frame=actual['frame_start'])
 else:live_actor=dict(status='not_present_in_current_owned_roster',old_address_not_read=True,roster_frame=actual['frame_start'])
 return dict(pid=n['pid'],session_id=identity('session'),commander_id=identity('commander'),command_id=identity('command'),task_id=identity('task'),seq=n['seq'],token=n['token'],owner=hex(n['owner']),logic=hex(n['logic']),native_binary_sha256=report['native_binary_sha256'],mutations=False,timer=timer,active=n['active'],phase=n['phase'],error=n['error'],restore_mask=n['restore_mask'],layout=inert,entries=rows,module_base=base,shared_pointer=pointer,shared_pointer_after=memory.u32(base+inert['shared_pointer_rva']),timer_after=memory.u32(base+inert['timer_rva']),header_before_hex=before.hex(),header_after_hex=after.hex(),live_actor=live_actor,binding_verified=before==after and n['pid']==report['preflight']['pid'] and all(identity(key)==report['native'][key+'_id'] for key in ('session','commander','command','task')))

def prepare_kernel(k):
 k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE
 k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
 k.UnmapViewOfFile.argtypes=[c.c_void_p];k.UnmapViewOfFile.restype=w.BOOL

def parse_args(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--commander',required=True);p.add_argument('--birth-report',type=Path,required=True);p.add_argument('--actor-id',type=int);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--seq',type=int,default=1);p.add_argument('--command-id',default=None);p.add_argument('--task-id',default=None)
 a=p.parse_args(argv);a.commander=str(uuid.UUID(a.commander));a.command_id=str(uuid.UUID(a.command_id)) if a.command_id else str(uuid.uuid4());a.task_id=str(uuid.UUID(a.task_id)) if a.task_id else str(uuid.uuid4())
 if not 1<=a.seq<=0xffffffff or a.actor_id is not None and not 1<=a.actor_id<=0xffffffff:raise ValueError('probe_positive_identity_required')
 a.session=a.session.resolve();a.output=a.output.resolve()
 if a.output.exists() or not a.output.parent.is_dir():raise ValueError('probe_requires_fresh_output_in_existing_run')
 return a

def main(argv=None):
 a=parse_args(argv)
 if a.execute and not EXECUTE_ENABLED:raise ValueError('reserve_probe_candidate_locked_pending_joint_review')
 session_input=json.loads(a.session.read_text(encoding='utf-8-sig'));birth=birth_helper.select_source(a.birth_report,session_input,a.actor_id);a.actor_id=birth['receipt']['object_id']
 b,pre,session,raw,package,registry,registry_sha,memory=preflight.current_selection(a.session,a.commander,a.actor_id);shared=None;view=handle=host=None;report=None;intent=False
 try:
  if a.output.parent!=Path(session['run_directory']).resolve() or session.get('scenario',{}).get('model_requests_enabled') is not False:raise ValueError('reserve_probe_requires_owned_non_model_calibration_run')
  actor=pre['selected'];birth['production_readonly']=birth_helper.production_readonly(memory,session,birth);producer=birth['production_readonly']
  if producer['owner']!=pre['owner'] or producer['window_thread']!=pre['window_thread'] or int(actor['type_hash'],0)!=birth_helper.UNITS[birth['receipt']['unit']]:raise ValueError('reserve_birth_owner_thread_type_changed')
  rally=rally_helper.capture(memory,session,birth)
  report=dict(rally_source=rally,session_source=dict(path=str(a.session.resolve()),sha256=sha(a.session)),birth_source=birth,protocol='reserve_probe_v2',source='game_bridge',session_id=session['session_id'],executable_sha256=b.EXPECTED,package_sha256=session['mod_sha256'],preflight=pre,request=dict(command_id=a.command_id,task_id=a.task_id,seq=a.seq,test_stance=2,explicit_sdk_max=8,settle_frames=60,hold_frames=90,total_frames=300,wall_seconds=30),status='read_only_ready',native={},events=[],tactical_source_granted=False,effect_verified=False,completion_claim=False,model_requests=0)
  ft=[w.FILETIME() for _ in range(4)]
  if not b.k.GetProcessTimes(memory.handle,*[c.byref(x) for x in ft]):raise c.WinError(c.get_last_error())
  pre.update(start_low=ft[0].dwLowDateTime,start_high=ft[0].dwHighDateTime)
  if producer['start_low']!=pre['start_low'] or producer['start_high']!=pre['start_high']:raise ValueError('reserve_birth_process_start_changed')
  if not a.execute:b.durable(a.output,report);print(json.dumps(dict(status=report['status'],actor_id=actor['object_id'],sdk_calls=0)));return
  report.update(source_record());prepare_kernel(b.k);token=secrets.randbits(32) or 1;rq=report['request'];rq.update(token=token,expires_frame=pre['frame']+300)
  handle=b.k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Probe),f"Local\\RA3TacticalReserve2_{session['pid']}_{token}")
  if not handle:raise c.WinError(c.get_last_error())
  if c.get_last_error()==183:raise ValueError('probe_mapping_already_exists')
  view=b.k.MapViewOfFile(handle,0xf001f,0,0,c.sizeof(Probe))
  if not view:raise c.WinError(c.get_last_error())
  c.memset(view,0,c.sizeof(Probe));shared=Probe.from_address(view);s=shared;s.magic=0x52535632;s.version=2;s.pid=session['pid'];s.thread=pre['window_thread'];s.start_low=pre['start_low'];s.start_high=pre['start_high']
  for name,value in [('session',session['session_id']),('commander',a.commander),('command',a.command_id),('task',a.task_id)]:getattr(s,name)[:]=words(value)
  s.seq=a.seq;s.token=token
  for name in ('logic','owner','ai','personality','personality_id','player_template','script_team','default_team'):setattr(s,name,int(pre[name],0))
  s.thing=int(actor['address'],0);s.object_id=actor['object_id'];s.type_hash=int(actor['type_hash'],0);s.template_ptr=memory.u32(s.thing+4);s.update=int(actor['ai_address'],0);s.stance_module=int(actor['stance']['module'],0);s.original_team=int(actor['team'],0);s.observed_frame=actor['admission']['frame'];s.threat_frame=0;s.threat_clear=0;s.expires_frame=rq['expires_frame'];s.test_stance=2;s.heartbeat_tick=int(b.k.GetTickCount())&0xffffffff
  s.production_command[:]=words(birth['command']['command_id']);s.production_task[:]=words(birth['command']['task_id']);s.production_seq=birth['command']['seq'];s.production_queue_id=birth['receipt']['queue_id'];s.production_birth_frame=birth['receipt']['completion_frame'];s.production_paid=birth['receipt']['paid'];s.production_receipt_sha256[:]=struct.unpack('<8I',bytes.fromhex(birth['receipt_sha256']))
  for name,key in [('factory_address','factory_address'),('factory_id','factory_id'),('factory_owner','factory_owner'),('factory_template','factory_template'),('factory_type_hash','factory_hash'),('factory_source_frame','source_frame'),('factory_x_bits','factory_x_bits'),('factory_y_bits','factory_y_bits')]:
   value=rally[key];setattr(s.rally,name,int(value,0) if isinstance(value,str) else value)
  # Every descriptor is persisted before the process that can install hooks.
  if a.session.read_bytes()!=raw or sha(registry)!=registry_sha or sha(package)!=session['mod_sha256'] or not unchanged_sources(report) or sha(birth['path'])!=birth['sha256']:raise ValueError('probe_binding_changed_before_intent')
  report['native_launch_intent_persisted']=True;b.durable(a.output,report);intent=True
  with a.output.with_suffix('.host.log').open('w',encoding='utf-8') as log:
   host=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));end=time.monotonic()+42;written=depcheck=0
   while time.monotonic()<end:
    shared.heartbeat_tick=int(b.k.GetTickCount())&0xffffffff;now=time.monotonic()
    if now-depcheck>=1:
     if a.session.read_bytes()!=raw or sha(registry)!=registry_sha or not unchanged_sources(report) or sha(birth['path'])!=birth['sha256']:shared.stop_requested=1
     depcheck=now
    terminal=capture(report,shared)
    if terminal or now-written>=.25:b.durable(a.output,report);written=now
    if host.poll() is not None:
     if not terminal:shared.stop_requested=1;raise RuntimeError('reserve_host_exited_before_terminal')
     break
    time.sleep(.02)
   if host.poll() is None:
    shared.stop_requested=1;end=time.monotonic()+12
    while time.monotonic()<end:
     shared.heartbeat_tick=int(b.k.GetTickCount())&0xffffffff;capture(report,shared)
     if shared.phase in (3,4) and host.poll() is not None:break
     time.sleep(.02)
   capture(report,shared);report['host_exit']=host.poll()
   if shared.phase in (3,4) and shared.active==0 and host.poll() is not None:report['terminal_readonly']=terminal_readonly(memory,report)
   else:report['status']='unknown_pending_stance_restore_and_return'
   report['assessment']=qualifier().qualify(report);b.durable(a.output,report);print(json.dumps(dict(report=str(a.output),status=report['status'],assessment=report['assessment'].get('status'),tactical_source_granted=False)))
 except BaseException as error:
  if report is not None:
   if intent and shared is not None:
    shared.stop_requested=1;end=time.monotonic()+12
    while host and time.monotonic()<end:
     shared.heartbeat_tick=int(b.k.GetTickCount())&0xffffffff;done=capture(report,shared)
     if done and host.poll() is not None:break
     time.sleep(.02)
    if shared.phase in (3,4) and shared.active==0:
     try:report['terminal_readonly']=terminal_readonly(memory,report)
     except (OSError,RuntimeError,ValueError) as failure:report['terminal_readonly_error']=type(failure).__name__
   report.update(status='dispatch_failed_native_terminal' if shared is not None and shared.phase in (3,4) else 'unknown_pending_stance_restore_and_return' if intent else 'no_dispatch_rejected',error_type=type(error).__name__,error_reason=str(error),host_exit=host.poll() if host else None);b.durable(a.output,report)
  raise
 finally:
  memory.close()
  if view:b.k.UnmapViewOfFile(view)
  if handle:b.k.CloseHandle(handle)

if __name__=='__main__':main()
