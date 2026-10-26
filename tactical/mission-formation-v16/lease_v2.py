"""MF16 paid-pair controller runtime. Import never attaches or starts SDK work."""
import argparse,ctypes as c,hashlib,importlib.util,json,math,os,re,secrets,struct,subprocess,sys,threading,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
EXECUTE_ENABLED=True

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
layout_module=module('mf16_actual_native_layout',HERE/'native_layout.py')
contract=module('mf16_controller_contract',HERE/'controller_contract.py')
Tactical=layout_module.Tactical;Header=layout_module.Header;Event=layout_module.Event
U=c.c_uint32;L=c.c_int32

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def plain(value,path='',bad=None):
 bad=[] if bad is None else bad
 if isinstance(value,c.Structure):return {name:plain(getattr(value,name),path+'.'+name,bad) for name,_ in value._fields_}
 if isinstance(value,c.Array):return [plain(v,path+'['+str(i)+']',bad) for i,v in enumerate(value)]
 if isinstance(value,float) and not math.isfinite(value):bad.append(path);return None
 return value

def event_record(event):
 bad=[];lineage=event.kind in range(110,121) or any(bytes(event.lineage))
 row={name:plain(getattr(event,name),'event.'+name,bad) for name,_ in event._fields_ if name!='lineage' or lineage}
 if bad:row['invalid_float_fields']=bad
 return row

def capture(report,shared):
 header=Header.from_buffer_copy(c.string_at(c.addressof(shared),c.sizeof(Header)));events=report.setdefault('events',[])
 if header.count<len(events):raise ValueError('mf16_published_prefix_regressed')
 for index in range(len(events),min(header.count,8192)):
  address=c.addressof(shared)+Tactical.events.offset+index*c.sizeof(Event)
  if U.from_address(address).value!=index+1:break
  event=Event.from_buffer_copy(c.string_at(address,c.sizeof(Event)))
  if event.seq!=index+1 or U.from_address(address).value!=index+1:break
  events.append(event_record(event))
 bad=[];native=plain(header,'native',bad)
 for key in ('session','commander','command','task'):native[key+'_id']=str(uuid.UUID(bytes=struct.pack('<4I',*native[key])))
 native['crumbs']=[[plain(header.crumbs[role][i],'crumbs',bad) for i in range(min(128,header.crumb_count[role]))] for role in (0,1)]
 if bad:native['invalid_float_fields']=bad
 report['native']=native;report['capture_metadata']=dict(published_prefix_count=len(events),header_count=header.count,incremental_decode=True)
 report['status']='finished' if header.phase in (3,4) and header.active==0 else 'running'
 return header.phase in (3,4) and header.active==0

def original_entries(memory):
 source=(HERE/'lease.cpp').read_text();block=source.split('static Hook hooks[]={',1)[1].split(';',1)[0];rows=[]
 for address,escaped,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block):
  expected=bytes.fromhex(escaped.replace('\\x',''));actual=memory.read(int(address,0),int(length));rows.append(dict(address=address,expected=expected.hex(),actual=actual.hex()))
 if len(rows)!=17 or any(x['expected']!=x['actual'] for x in rows):raise ValueError('another_native_channel_active_or_signature_changed')
 return rows

def read_bounded_exact(memory,address,size):
 # Memory.read enforces n<=0x2000. Header6 spans multiple pages; terminal and
 # no-lease readers must respect that bound without inventing missing bytes.
 if type(address) is not int or type(size) is not int or not 0<address<2**32 or not 0<size<=c.sizeof(Header) or address+size>2**32:raise ValueError('readonly_header_bounds')
 blocks=[]
 for offset in range(0,size,0x2000):
  length=min(0x2000,size-offset);block=memory.read(address+offset,length)
  if not isinstance(block,bytes) or len(block)!=length:raise ValueError('readonly_header_short_read')
  blocks.append(block)
 return b''.join(blocks)

def read_stable_header(memory,base,layout):
 pointer_address=base+layout['shared_pointer_rva'];timer_address=base+layout['timer_rva']
 pointer=memory.u32(pointer_address);timer=memory.u32(timer_address)
 block=read_bounded_exact(memory,pointer,c.sizeof(Header))
 confirmation=read_bounded_exact(memory,pointer,c.sizeof(Header))
 if block!=confirmation or memory.u32(pointer_address)!=pointer or memory.u32(timer_address)!=timer:raise ValueError('readonly_header_not_stable')
 return Header.from_buffer_copy(block),pointer,timer

def terminal_readonly(memory,report):
 layout=json.loads((HERE/'inert-layout.json').read_text())
 if layout['dll_sha256']!=report['native_binary_sha256']:raise ValueError('inert_layout_dll_mismatch')
 # Module enumeration and RPM only; no native function or debug-register calls.
 helper=module('formation_terminal_module_lookup',HERE.parent/'readonly_disposal.py')
 base=helper.module_base(memory,HERE/'bin/TacticalMissionFormation16.dll');snapshot,ptr,timer=read_stable_header(memory,base,layout)
 def ident(field):return str(uuid.UUID(bytes=struct.pack('<4I',*getattr(snapshot,field))))
 binding=snapshot.magic==0x4d463136 and snapshot.version==16 and snapshot.pid==report['preflight']['pid'] and snapshot.token==report['request']['token'] and snapshot.seq==report['request']['seq'] and ident('session')==report['session_id'] and ident('command')==report['request']['command_id'] and ident('task')==report['request']['task_id'] and ident('commander')==report['preflight']['commander_id'] and hex(snapshot.owner)==report['preflight']['owner'] and snapshot.logic==memory.u32(0xcd8ce4)==int(report['preflight']['logic'],0)
 entries=[]
 for row in report['original_entries']:
  actual=memory.read(int(row['address'],0),len(bytes.fromhex(row['expected'])));entries.append(dict(address=row['address'],expected=row['expected'],actual=actual.hex(),restored=actual.hex()==row['expected']))
 confirmation,final_pointer,final_timer=read_stable_header(memory,base,layout)
 if final_pointer!=ptr or final_timer!=timer or bytes(confirmation)!=bytes(snapshot):raise ValueError('readonly_header_changed_during_entries')
 return dict(pid=snapshot.pid,session_id=ident('session'),commander_id=ident('commander'),command_id=ident('command'),task_id=ident('task'),seq=snapshot.seq,token=snapshot.token,owner=hex(snapshot.owner),logic=hex(snapshot.logic),native_binary_sha256=report['native_binary_sha256'],module_base=hex(base),shared_pointer=hex(ptr),layout=layout,timer=timer,binding_verified=bool(binding),phase=snapshot.phase,error=snapshot.error,active=snapshot.active,restore_mask=snapshot.restore_mask,front_return_verified=snapshot.return_verified,support_return_verified=snapshot.support.returned,entries=entries,header_before_hex=bytes(snapshot).hex(),header_after_hex=bytes(confirmation).hex(),mutations=False)

def require_live_host_or_terminal(host,shared):
 # A dead controller must not leave a fresh Python heartbeat extending a live
 # native mission. The existing exception path requests stop and drains safely.
 if host is not None and host.poll() is not None and shared.phase not in (3,4):
  shared.stop_requested=1
  raise RuntimeError('native_host_exited_before_terminal')

def qualifier():return module('mf16_independent_qualifier',HERE/'formation_mission_qualification_v2.py')

def capture_disposal(memory,report):
 helper=module('mf16_actual_disposal_readonly',HERE.parent/'readonly_disposal.py');result={};n=report['native']
 if n.get('phase')!=4:return result
 for role,slot in enumerate(n.get('slots',[])):
  if not slot.get('borrow_frame') or (n.get('return_verified') if role==0 else n.get('support',{}).get('returned')):continue
  actor=slot['id'];terminal=terminal_readonly(memory,report)
  if not terminal['binding_verified'] or memory.pid!=report['preflight']['pid']:raise ValueError('mf16_disposal_memory_binding')
  binding={key:terminal[key] for key in ('pid','session_id','commander_id','command_id','task_id','seq','token','owner','logic','native_binary_sha256')}
  canonical=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  record=dict(binding,object_id=actor,role=role,source_session_id=report['session_id'],source_request_sha256=canonical(report['request']),source_preflight_sha256=canonical(report['preflight']),scans=[],terminal_before=terminal,mutations=False)
  last=None;end=time.monotonic()+3
  while time.monotonic()<end and len(record['scans'])<2:
   try:
    sample=helper.live_scan(memory,int(report['preflight']['logic'],0),actor)
    if last is None or sample['frame']>last:record['scans'].append(sample);last=sample['frame']
   except ValueError as error:record['error']=str(error)
   time.sleep(.05)
  record['terminal_after']=terminal_readonly(memory,report);result[str(role)]=record
 return result

def supplemental():
 paths=qualifier().source_paths()
 if len({p.name for p in paths})!=len(paths):raise ValueError('mf16_supplemental_name_collision')
 return {p.name:sha(p) for p in paths}

def source_record():
 revision=json.loads((HERE/'revision.json').read_text());files={'native_binary_sha256':HERE/'bin/TacticalMissionFormation16.dll','native_host_sha256':HERE/'bin/tactical_host.exe','native_source_sha256':HERE/'lease.cpp','native_shared_sha256':HERE/'shared.h'}
 values={key:sha(path) for key,path in files.items()};includes={p.name:sha(p) for p in HERE.glob('*.cpp.inc')}
 if any(revision.get(k)!=v for k,v in values.items()) or revision.get('native_includes_sha256')!=includes:raise ValueError('mf16_compiled_source_changed')
 if values['native_shared_sha256']!=layout_module.SHARED_SHA256:raise ValueError('mf16_static_layout_source_changed')
 for flag,expected in [('--layout',layout_module.layout()),('--controller-layout',layout_module.controller_layout())]:
  actual=json.loads(subprocess.check_output([str(files['native_host_sha256']),flag],text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
  if actual!=expected:raise ValueError('mf16_actual_host_abi_changed')
 return dict(values,native_revision_sha256=sha(HERE/'revision.json'),native_includes_sha256=includes,wrapper_sha256=sha(__file__),native_layout_sha256=sha(HERE/'native_layout.py'),controller_contract_sha256=sha(HERE/'controller_contract.py'),supplemental_sources=supplemental())

def frozen_sources_match(report):
 try:
  paths={'native_binary_sha256':HERE/'bin/TacticalMissionFormation16.dll','native_host_sha256':HERE/'bin/tactical_host.exe','native_source_sha256':HERE/'lease.cpp','native_shared_sha256':HERE/'shared.h','native_revision_sha256':HERE/'revision.json','wrapper_sha256':Path(__file__),'native_layout_sha256':HERE/'native_layout.py','controller_contract_sha256':HERE/'controller_contract.py'}
  return all(report.get(k)==sha(p) for k,p in paths.items()) and report.get('native_includes_sha256')=={p.name:sha(p) for p in HERE.glob('*.cpp.inc')} and report.get('supplemental_sources')==supplemental()
 except (OSError,KeyError,ValueError):return False

def mission_dependencies_match(report):
 mission=report.get('mission_request')
 if mission is None:return True
 try:
  return all(sha(mission[path])==mission[digest] for path,digest in (('public_command_path','public_command_sha256'),('visibility_proof_path','visibility_proof_sha256'),('safety_path','safety_sha256')))
 except (OSError,KeyError,TypeError,ValueError):return False

def kernel_mapping(k,w):
 k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE
 k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
 k.UnmapViewOfFile.argtypes=[c.c_void_p];k.UnmapViewOfFile.restype=w.BOOL

def public_status(report):
 native=report.get('native',{});return dict(status=report.get('status'),controller=native.get('controller',{}),slots=[{k:slot.get(k) for k in ('stage','error','id','borrow_frame','ready_frame','hold_samples','hold_max_gap','hold_failed','restore_verified','return_verified')} for slot in native.get('slots',[])],mission_commit={k:native.get('mission_commit',{}).get(k) for k in ('generation','status','reason','ack_frame')},effect_verified=False,completion_claim=False)

class ControllerRuntime:
 def __init__(self,session_path,config,output,natural_path):
  self.session_path=Path(session_path).resolve();self.config=config;self.output=Path(output).resolve();self.natural_path=Path(natural_path).resolve();self.host=None;self.handle=None;self.view=None;self.shared=None;self.memory=None;self.report=None;self.intent=False;self.log=None;self.last_write=0;self.last_source_check=0;self.heartbeat_stop=threading.Event();self.heartbeat_thread=None;self.heartbeat_error=None
 def arm(self):
  if not EXECUTE_ENABLED:raise ValueError('mf16_candidate_locked_pending_joint_review')
  if self.report is not None or self.output.exists():raise ValueError('mf16_fresh_controller_required')
  self.backend=module('mf16_frozen_own_backend',HERE.parent/'ordered-combo/lease.py');b=self.backend
  pre,session,raw,package,registry,registry_sha,memory=b.readiness(self.session_path);self.memory=memory
  try:
   if pre['paused']:raise ValueError('mf16_requires_running_game')
   if not self.output.is_relative_to(Path(session['run_directory']).resolve()):raise ValueError('mf16_output_outside_bound_run')
   cfg=contract.validate_controller(self.config,pre['frame']);self.config=cfg
   ft=[b.w.FILETIME() for _ in range(4)]
   if not b.k.GetProcessTimes(memory.handle,*[c.byref(x) for x in ft]):raise c.WinError(c.get_last_error())
   pre.update(start_low=ft[0].dwLowDateTime,start_high=ft[0].dwHighDateTime,actor_selection_used=False)
   natural_raw=self.natural_path.read_bytes();natural=json.loads(natural_raw.decode('utf-8-sig'));b.compatible_natural_calls(natural,session['pid'])
   if natural['window_thread']!=pre['window_thread']:raise ValueError('mf16_natural_thread')
   factory_reader=module('mf16_factory_ro',BRIDGE/'production/observe_production.py');owned=b.own_candidates(memory,3,b.load_catalog());factories=[]
   for slot in cfg['slots']:
    found=[u for u in owned['candidates'] if int(u['address'],0)==slot['factory'] and u['object_id']==slot['factory_id'] and u['type_hash']=='0x80d4ea1e']
    if len(found)!=1:raise ValueError('mf16_current_owned_barracks_required')
    actor=found[0];factory=factory_reader.read_factory(memory,actor,int(pre['owner'],0))
    if not factory['production_interface_available'] or int(factory['interface'],0)!=slot['iface']:raise ValueError('mf16_factory_interface')
    factories.append(dict(actor=actor,readonly=factory,template_ptr=memory.u32(slot['factory']+4)))
   producer=module('mf16_producer_binding_ro',HERE/'producer_binding.py').collect(memory,session,pre,cfg['slots'][0]);entries=original_entries(memory);sources=source_record()
   current_frame=memory.u32(int(pre['logic'],0)+0x50)
   if current_frame>=cfg['startup_deadline_frame'] or memory.u32(int(pre['logic'],0)+0x15c):raise ValueError('mf16_late_startup_or_pause')
   self.session=session;self.session_raw=raw;self.package=package;self.registry=registry;self.registry_sha=registry_sha;self.natural_raw=natural_raw
   token=secrets.randbits(32) or 1;request=dict(command_id=cfg['controller_id'],task_id=cfg['lease_id'],seq=cfg['seq'],token=token,allocation_scope='prebound_paid_pair',startup_deadline_frame=cfg['startup_deadline_frame'],startup_wall_ms=cfg['startup_wall_ms'],reserve_duration_frames=450,lease_duration_frames=4500,total_paid_max=305,reserve_floor=1000)
   report=dict(session_id=session['session_id'],executable_sha256=b.EXPECTED,package_sha256=session['mod_sha256'],preflight=pre,request=request,mission_request=None,private_target=None,original_entries=entries,producer_readonly_at_arm=producer,factory_readonly=factories,session_source=dict(path=str(self.session_path),sha256=sha(self.session_path)),natural_source=dict(path=str(self.natural_path),sha256=sha(self.natural_path)),status='preflight',events=[],native={},model_requests=0,native_launch_intent_persisted=False,wrapper_revision='mf16_running_paid_pair_controller_v2',wrapper_filename='lease_v2.py',**sources)
   kernel_mapping(b.k,b.w);self.handle=b.k.CreateFileMappingW(b.w.HANDLE(-1),None,4,0,c.sizeof(Tactical),f"Local\\RA3TacticalMissionFormation16_{session['pid']}_{token}")
   if not self.handle or c.get_last_error()==183:raise ValueError('mf16_mapping_already_exists')
   self.view=b.k.MapViewOfFile(self.handle,0xf001f,0,0,c.sizeof(Tactical))
   if not self.view:raise c.WinError(c.get_last_error())
   c.memset(self.view,0,c.sizeof(Tactical));self.shared=Tactical.from_address(self.view);s=self.shared;s.magic=0x4d463136;s.version=16;s.pid=session['pid'];s.thread=pre['window_thread'];s.start_low=pre['start_low'];s.start_high=pre['start_high'];s.seq=cfg['seq'];s.token=token
   for key,value in [('session',session['session_id']),('commander',pre['commander_id']),('command',cfg['controller_id']),('task',cfg['lease_id'])]:getattr(s,key)[:]=contract.words(value)
   for key in ('owner','ai','personality','personality_id','player_template','logic','script_team','default_team'):setattr(s,key,int(pre[key],0))
   s.lease_frames=4500;s.post_frames=30;s.memory_ttl_frames=900;s.approach_limit=2100;s.retreat_limit=1800;s.hold_timeout_frames=60;s.heartbeat_tick=int(b.k.GetTickCount())&0xffffffff
   ci=s.controller_input;ci.schema=1;ci.controller[:]=contract.words(cfg['controller_id']);ci.lease[:]=contract.words(cfg['lease_id']);ci.formation[:]=contract.words(cfg['formation_uuid']);ci.formation_version=1;ci.startup_deadline_frame=cfg['startup_deadline_frame'];ci.startup_wall_ms=cfg['startup_wall_ms'];ci.reserve_duration_frames=450;ci.lease_duration_frames=4500
   for dest,key in [('producer_pid','pid'),('producer_thread','thread'),('producer_start_low','start_low'),('producer_start_high','start_high'),('producer_owner','owner'),('producer_ai','ai'),('producer_personality','personality'),('producer_personality_id','personality_id'),('producer_player_template','player_template')]:setattr(ci,dest,producer['expected'][key])
   ci.producer_session[:]=contract.words(session['session_id']);ci.producer_commander[:]=contract.words(pre['commander_id']);ci.reserve_floor=1000;ci.total_paid_max=305;ci.slot_count=2;ci.allocation_scope=1;ci.force_numerator=ci.force_denominator=1
   for role,slot in enumerate(cfg['slots']):
    out=ci.slots[role];out.role=role;out.command[:]=contract.words(slot['command_id']);out.task[:]=contract.words(slot['task_id']);out.seq=slot['seq'];out.unit_hash=slot['unit_hash'];out.expected_cost=slot['cost'];out.factory=slot['factory'];out.factory_id=slot['factory_id'];out.factory_template=factories[role]['template_ptr'];out.factory_hash=0x80d4ea1e;out.iface=slot['iface']
   report['controller_input']=plain(ci);report['controller_config']=cfg;self.report=report
   if self.session_path.read_bytes()!=raw or sha(registry)!=registry_sha or sha(package)!=session['mod_sha256'] or self.natural_path.read_bytes()!=natural_raw or not frozen_sources_match(report):raise ValueError('mf16_binding_changed_before_intent')
   self.output.parent.mkdir(parents=True,exist_ok=True)
   with self.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,allow_nan=False,indent=2)
   self.report['native_launch_intent_persisted']=True;b.durable(self.output,self.report);self.intent=True
   self.log=self.output.with_suffix('.host.log').open('w',encoding='utf-8');self.host=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=self.log,stderr=self.log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   self.heartbeat_thread=threading.Thread(target=self._heartbeat,daemon=True,name='mf16-controller-heartbeat');self.heartbeat_thread.start()
   return public_status(self.report)
  except BaseException:
   if self.intent:self.stop()
   else:self.close()
   raise
 def _heartbeat(self):
  # Runs while the Host awaits a provider or a production receipt. No SDK.
  try:
   check_at=0
   while not self.heartbeat_stop.wait(.05):
    if self.shared is None:return
    if self.host is not None and self.host.poll() is not None:
     if self.shared.phase not in (3,4):self.shared.stop_requested=1
     return
    self.shared.heartbeat_tick=int(self.backend.k.GetTickCount())&0xffffffff
    now=time.monotonic()
    if now-check_at>=1:
     if self.session_path.read_bytes()!=self.session_raw or sha(self.registry)!=self.registry_sha or sha(self.package)!=self.session['mod_sha256'] or self.natural_path.read_bytes()!=self.natural_raw or not frozen_sources_match(self.report) or not mission_dependencies_match(self.report):self.shared.stop_requested=1;return
     check_at=now
  except BaseException as failure:
   self.heartbeat_error=type(failure).__name__
   if self.shared is not None:self.shared.stop_requested=1
 def _stop_heartbeat(self):
  self.heartbeat_stop.set()
  if self.heartbeat_thread is not None and self.heartbeat_thread is not threading.current_thread():
   self.heartbeat_thread.join(timeout=2)
   if self.heartbeat_thread.is_alive():raise RuntimeError('mf16_heartbeat_did_not_stop')
 def poll(self,*,persist=False):
  if self.shared is None or self.report is None:raise ValueError('mf16_not_armed')
  b=self.backend;now=time.monotonic()
  if now-self.last_source_check>=1:
   if self.session_path.read_bytes()!=self.session_raw or sha(self.registry)!=self.registry_sha or sha(self.package)!=self.session['mod_sha256'] or self.natural_path.read_bytes()!=self.natural_raw or not frozen_sources_match(self.report) or not mission_dependencies_match(self.report):self.shared.stop_requested=1
   self.last_source_check=now
  terminal=capture(self.report,self.shared);self.report['host_exit']=self.host.poll()
  self._capture_weapon_binding()
  if self.report.get('mission_request') and self.report['native']['mission_commit']['status']==1:self.report['progress']=qualifier().progress(self.report,self.report['mission_request']['parent_task_id'])
  else:self.report['progress']=None
  if self.host.poll() is not None and not terminal:raise RuntimeError('mf16_host_exited_without_terminal')
  if terminal and self.host.poll() is not None:
   self._stop_heartbeat();capture(self.report,self.shared)
   if 'terminal_readonly' not in self.report:self.report['terminal_readonly']=terminal_readonly(self.memory,self.report)
   if 'disposal_readonly' not in self.report:self.report['disposal_readonly']=capture_disposal(self.memory,self.report)
   self.report['assessment']=qualifier().qualify(self.report)
  if terminal or persist or now-self.last_write>=.5:b.durable(self.output,self.report);self.last_write=now
  return public_status(self.report)
 def _capture_weapon_binding(self):
  n=self.report['native'];entry=n.get('weapon_entry',0);template=n.get('weapon_template',0)
  if not entry or not template:return
  old=self.report.get('weapon_asset_binding')
  if old:
   if old['reported_entry']!=hex(entry) or old['reported_template']!=hex(template):raise ValueError('mf16_weapon_binding_changed')
   return
  memory=self.memory;logic=int(self.report['preflight']['logic'],0);before=memory.u32(logic+0x50)
  own=self.backend.own_candidates(memory,3,self.backend.load_catalog())
  if own['frame_start']!=own['frame_end']:return
  matches=[a for a in own['candidates'] if a['object_id']==n['object_id'] and int(a['address'],0)==n['unit'] and a['type_hash']=='0x19ab11af']
  if len(matches)!=1:return  # Never inspect a stale actor's weapon entry.
  hp_bits=memory.u32(memory.u32(n['unit']+0x33c)+4);hp=struct.unpack('<f',struct.pack('<I',hp_bits))[0]
  if not math.isfinite(hp) or hp<=0 or int(matches[0]['owner_address'],0)!=n['owner']:return
  def identity():return [self.shared.unit,self.shared.object_id,self.shared.owner,self.shared.weapon_entry,self.shared.weapon_template,self.shared.weapon_slot]
  expected=[n['unit'],n['object_id'],n['owner'],entry,template,n['weapon_slot']]
  if identity()!=expected:return
  vt=memory.u32(template);schema=memory.u32(template+4);header=memory.u32(schema);asset_type=memory.u32(header);asset_id=memory.u32(header+4)
  first=[vt,schema,header,asset_type,asset_id]
  second=[memory.u32(template),memory.u32(template+4),memory.u32(schema),memory.u32(header),memory.u32(header+4)];after=memory.u32(logic+0x50)
  if first!=second or vt!=0xc37534 or asset_type!=0x94d4d96e or asset_id!=0x447ea26e or identity()!=expected or not 0<=after-before<=4:raise ValueError('mf16_actual_weapon_asset_unstable')
  self.report['weapon_asset_binding']=dict(session_id=self.report['session_id'],pid=self.report['preflight']['pid'],reported_entry=hex(entry),reported_template=hex(template),template_schema=hex(schema),asset_header=hex(header),asset_type=hex(asset_type),asset_id=hex(asset_id),method='reported_template_plus4_to_schema_to_asset_header',observed_frame=after,observed_frame_start=before,mutations=False,raw_before=first,raw_after=second,native_binding_before=expected,native_binding_after=identity(),current_own_actor=matches[0],own_hp_bits=hp_bits,own_frame_start=own['frame_start'],own_frame_end=own['frame_end'],entry_memory_read=False)
 def verified_no_launch(self):
  # Certificate about this code path only; no claim about another controller.
  empty_report=self.report is None or (not self.report.get('native_launch_intent_persisted') and not self.report.get('events') and not self.report.get('native'))
  if self.intent or self.host is not None or self.heartbeat_thread is not None or self.view is not None or self.handle is not None or self.shared is not None or not empty_report:raise ValueError('mf16_no_launch_not_proven')
  raw=self.session_path.read_bytes();session=json.loads(raw.decode('utf-8-sig'));controller=contract.uid(self.config['controller_id']);lease=contract.uid(self.config['lease_id'])
  if not self.output.is_relative_to(Path(session['run_directory']).resolve()):raise ValueError('mf16_no_launch_output_outside_run')
  record=dict(protocol='mf16_verified_no_launch_v1',session_id=session['session_id'],pid=session['pid'],commander_id=session['scenario']['commander_id'],controller_id=controller,lease_id=lease,verified=True,never_attached=True,native_launch_intent_persisted=False,native_host_created=False,mapping_closed=True,heartbeat_started=False,sdk_calls=0,game_memory_writes=False,physical_capability_granted=False,scope='only_this_unlaunched_controller_code_path',wrapper_sha256=sha(__file__),controller_config_sha256=hashlib.sha256(json.dumps(self.config,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),session_source=dict(path=str(self.session_path),sha256=hashlib.sha256(raw).hexdigest()))
  path=self.output.with_name(self.output.stem+'-no-launch.json');path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists():
   if json.loads(path.read_text(encoding='utf-8'))!=record:raise ValueError('mf16_no_launch_record_changed')
  else:
   with path.open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2,allow_nan=False)
  return dict(record,source_report=str(path),source_sha256=sha(path))
 def verified_facts(self):
  self.poll(persist=True);q=qualifier()
  if not q.source_pins(self.report):raise ValueError('mf16_live_facts_source_changed')
  facts=q.controller.live_facts(self.report)
  facts['source_report']=str(self.output);facts['source_sha256']=sha(self.output)
  return facts
 def verified_release(self):
  self.poll(persist=True);q=qualifier()
  if not q.source_pins(self.report):raise ValueError('mf16_release_source_changed')
  result=q.control_release(self.report)
  result['source_report']=str(self.output);result['source_sha256']=sha(self.output)
  return result
 def request_retreat(self):
  if self.shared is None:raise ValueError('mf16_not_armed')
  self.shared.retreat_requested=1
 def stop(self,max_seconds=12):
  if self.shared is None:return None
  self.shared.stop_requested=1;end=time.monotonic()+max_seconds
  while self.host is not None and time.monotonic()<end:
   state=self.poll(persist=True)
   if self.shared.phase in (3,4) and self.host.poll() is not None:return state
   time.sleep(.02)
  if self.report is not None:self.report['status']='unknown_pending_native_release';self.backend.durable(self.output,self.report)
  return public_status(self.report or {})
 def close(self):
  if self.host is not None and self.host.poll() is None:raise ValueError('mf16_live_controller_cannot_unmap')
  self._stop_heartbeat()
  if self.view is not None:self.backend.k.UnmapViewOfFile(self.view);self.view=None;self.shared=None
  if self.handle is not None:self.backend.k.CloseHandle(self.handle);self.handle=None
  if self.memory is not None:self.memory.close();self.memory=None
  if self.log is not None:self.log.close();self.log=None
 def commit(self,public_command,formation,visibility_proof_path,*,public_command_source=None,combat_frames=60):
  if self.report is None or self.shared is None:raise ValueError('mf16_not_armed')
  self.poll(persist=True);n=self.report['native'];ctl=n['controller'];cfg=self.config
  command=dict(public_command);parent_command=contract.uid(command['command_id']);parent_task=contract.uid(command['task_id']);seq=contract.uint(command['seq'])
  native_formation,fid=contract.formation_ids(cfg['controller_id'])
  identity=dict(session_id=self.session['session_id'],player_id=3,commander_id=self.report['preflight']['commander_id'],module='combined_arms',purpose='coordinate_force',target_contact_id=command.get('target_contact_id'))
  if any(command.get(k)!=v for k,v in identity.items()) or not isinstance(command.get('target_contact_id'),str) or not command['target_contact_id']:raise ValueError('mf16_public_command_binding')
  if command.get('formation_ids')!=[fid] or dict(command.get('formation_versions',[]))!={fid:1} or set(command.get('required_roles',[]))!={'infantry','anti_air'} or type(command.get('force_fraction')) not in (int,float) or command['force_fraction']!=1:raise ValueError('mf16_exact_paid_pair_request')
  if type(formation) is not dict or set(formation)!={'formation_id','version','roles','region_id','available'} or formation['formation_id']!=fid or type(formation['version']) is not int or formation['version']!=1 or formation['roles']!={'infantry':1,'anti_air':1} or any(type(v) is not int for v in formation['roles'].values()) or formation['available'] is not True:raise ValueError('mf16_public_pair_formation')
  previous=self.report.get('mission_request')
  if previous is not None:
   if previous['public_command']!=command or previous['formation']!=formation:raise ValueError('mf16_write_once_mission_conflict')
   return public_status(self.report)
  if self.host.poll() is not None or self.shared.stop_requested or n['phase']!=1 or ctl['stage']!=2 or ctl['held_mask']!=3 or ctl['ready_mask']!=3 or not ctl['clock_frozen'] or n['mission_commit']['generation']!=0:raise ValueError('mf16_pair_not_commit_eligible')
  parent_expiry=command.get('expires_frame')
  if parent_expiry is None:
   seconds=command.get('expires_at_game_seconds')
   if type(seconds) not in (int,float) or not math.isfinite(seconds) or abs(seconds*15-round(seconds*15))>1e-5:raise ValueError('mf16_parent_expiry')
   parent_expiry=round(seconds*15)
  if type(parent_expiry) is not int or parent_expiry!=ctl['hard_deadline_frame']:raise ValueError('mf16_parent_expiry_must_equal_original_lease_cap')
  if type(combat_frames) is not int or not 30<=combat_frames<=300:raise ValueError('mf16_combat_limit')
  proof_path=Path(visibility_proof_path).resolve();proof_raw=proof_path.read_bytes();proof=json.loads(proof_raw.decode('utf-8-sig'));safety_path=BRIDGE/'visibility/template-safety-2d7873e1.json';safety_raw=safety_path.read_bytes();safety=json.loads(safety_raw)
  sys.path.insert(0,str(BRIDGE/'visibility'));projection_module=module('mf16_visibility_projection',BRIDGE/'visibility/projection.py');collector_module=module('mf16_visibility_collector',BRIDGE/'visibility/collector.py')
  projection=projection_module.VisibilityProjection(self.session['session_id'],3,self.session['mod_sha256'],proof,safety)
  if not projection.verified():raise ValueError('mf16_visibility_source_unverified')
  m=self.memory;logic=int(self.report['preflight']['logic'],0);frame=m.u32(logic+0x50)
  if m.u32(logic+0x15c) or frame>=ctl['reserve_deadline_frame'] or ctl['hard_deadline_frame']!=ctl['reserve_start_frame']+4500:raise ValueError('mf16_commit_clock_or_pause')
  reader=collector_module.VisibilityCollector(m,self.session,3,projection);reader.collect(frame/15);target=reader.private_targets.get(command['target_contact_id'])
  if not target or len(reader.private_targets)>=64:raise ValueError('mf16_contact_not_currently_visible')
  target_role=safety['templates'].get(target['type_hash'],{}).get('role')
  if target_role not in ('infantry','armor','structure','economy') or target_role=='economy' and target['type_hash']!='0xc45aaeab':raise ValueError('mf16_ground_target_scope')
  actor_helper=module('mf16_commit_actual_actor',HERE/'actor_binding.py');front=actor_helper.actor(self.report,0);support=actor_helper.actor(self.report,1)
  owned_snapshot=self.backend.own_candidates(m,3,self.backend.load_catalog());owned=owned_snapshot['candidates'];owned_ids={u['object_id']:u for u in owned}
  for actor in (front,support):
   actual=owned_ids.get(actor['object_id'])
   if not actual or actual['address']!=actor['address'] or actual['type_hash']!=actor['type_hash'] or m.u32(int(actor['address'],0)+0x414)!=self.shared.script_team:raise ValueError('mf16_current_held_roster_changed')
  origin_points=[list(owned_ids[a['object_id']]['xyz']) for a in (front,support)]
  visible_observations=[dict(object_id=t['object_id'],type_hash=t['type_hash'],owner_player_id=t.get('owner_player_id'),observed_frame=t['observed_frame'],xyz=list(t['xyz'])) for t in reader.private_targets.values()]
  near=[t['object_id'] for t in visible_observations if any(math.dist(t['xyz'][:2],point[:2])<350 for point in origin_points)]
  if near:raise ValueError('mf16_ready_origin_has_visible_enemy_within350')
  origin_safety=dict(viewer_player_id=3,observed_frame=frame,own_frame_start=owned_snapshot['frame_start'],own_frame_end=owned_snapshot['frame_end'],actor_ids=[front['object_id'],support['object_id']],actual_owned_positions=origin_points,authorized_visible_observations=visible_observations,currently_visible_enemy_threats_within350=near,semantics='current_own_positions_without_currently_authorized_visible_enemy_within350_not_omniscient_safe')
  button=module('mf16_commit_own_button',HERE.parent/'recon/read_own_command_buttons.py').inspect(m,int(front['address'],0))
  if not button.get('toggle'):raise ValueError('mf16_exact_toggle_button_missing')
  target=dict(target,template=m.u32(target['address']+4));validated=m.u32(logic+0x50)
  if not frame<=target['observed_frame']<=validated<=frame+4 or validated>=ctl['reserve_deadline_frame'] or m.u32(logic+0x15c):raise ValueError('mf16_commit_observation_expired')
  body=layout_module.MissionCommitBody13()
  ids={'controller':cfg['controller_id'],'lease':cfg['lease_id'],'parent_command':parent_command,'parent_task':parent_task,'command':str(uuid.uuid5(uuid.UUID(parent_command),'formation')),'task':str(uuid.uuid5(uuid.UUID(parent_task),'formation')),'formation':native_formation}
  for key,value in ids.items():getattr(body,key)[:]=contract.words(value)
  body.seq=seq;body.formation_version=1;body.front_id=front['object_id'];body.support_id=support['object_id'];body.module=body.purpose=body.allocation_scope=body.force_numerator=body.force_denominator=1
  body.target_unit=target['address'];body.target_id=target['object_id'];body.target_hash=int(target['type_hash'],0);body.target_owner=target['owner'];body.target_template=target['template'];body.target_observed_frame=target['observed_frame'];body.visible_target[:]=target['xyz'];body.visibility_proof_sha256[:]=struct.unpack('<8I',hashlib.sha256(proof_raw).digest());body.threat_clear=1;body.threat_frame=frame
  body.reserve_start_frame=ctl['reserve_start_frame'];body.reserve_deadline_frame=ctl['reserve_deadline_frame'];body.hard_deadline_frame=ctl['hard_deadline_frame'];body.combat_frames=combat_frames;body.button=int(button['toggle']['entry'],0);body.button_schema=int(button['toggle']['schema'],0);body.command_set=int(button['command_set_hash'],0)
  seal=contract.seal_body(body)
  if public_command_source is None:
   source=self.output.with_name(self.output.stem+'-public-command.json')
   with source.open('x',encoding='utf-8') as stream:json.dump(command,stream,ensure_ascii=False,allow_nan=False,indent=2)
  else:source=Path(public_command_source).resolve()
  source_raw=source.read_bytes()
  if not source.is_relative_to(Path(self.session['run_directory']).resolve()) or json.loads(source_raw.decode('utf-8-sig'))!=command:raise ValueError('mf16_original_public_command_file')
  mission=dict(parent_command_id=parent_command,parent_task_id=parent_task,child_command_id=ids['command'],child_task_id=ids['task'],seq=seq,public_command=command,public_command_path=str(source),public_command_sha256=hashlib.sha256(source_raw).hexdigest(),formation=dict(formation),native_formation_uuid=native_formation,contact_id=command['target_contact_id'],visibility_proof_path=str(proof_path),visibility_proof_sha256=hashlib.sha256(proof_raw).hexdigest(),safety_path=str(safety_path.resolve()),safety_sha256=hashlib.sha256(safety_raw).hexdigest(),button=button,target_role=target_role,validated_frame=validated,combat_frames=combat_frames,origin_safety=origin_safety,**seal)
  if self.session_path.read_bytes()!=self.session_raw or proof_path.read_bytes()!=proof_raw or safety_path.read_bytes()!=safety_raw or not frozen_sources_match(self.report) or self.shared.mission_commit.generation!=0 or self.shared.stop_requested:raise ValueError('mf16_commit_binding_changed')
  self.report['mission_request']=mission;self.report['private_target']=target;self.backend.durable(self.output,self.report)
  self.shared.mission_commit.body=body
  if bytes(self.shared.mission_commit.body)!=bytes(body):self.shared.stop_requested=1;raise ValueError('mf16_commit_body_store_changed')
  published=subprocess.run([str(HERE/'bin/tactical_host.exe'),'--publish-commit',str(self.session['pid']),str(self.report['request']['token'])],capture_output=True,text=True,encoding='utf-8',timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  self.report['mission_publication']=dict(exit_code=published.returncode,stdout=published.stdout.strip(),stderr=published.stderr.strip(),publication_only=True,sdk_calls=0)
  self.backend.durable(self.output,self.report)
  if published.returncode!=0 or self.shared.mission_commit.generation!=2:raise ValueError('mf16_commit_publication_refused')
  return public_status(self.report)

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',type=Path,required=True);parser.add_argument('--controller-file',type=Path,required=True);parser.add_argument('--natural',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--command-file',type=Path);parser.add_argument('--formation-file',type=Path);parser.add_argument('--proof-file',type=Path);parser.add_argument('--max-wall-seconds',type=int,default=420)
 args=parser.parse_args(argv)
 if args.execute and not EXECUTE_ENABLED:raise ValueError('mf16_candidate_locked_pending_joint_review')
 if not 30<=args.max_wall_seconds<=420 or bool(args.command_file)!=bool(args.formation_file) or bool(args.command_file)!=bool(args.proof_file):raise ValueError('mf16_cli_bounds')
 config_raw=args.controller_file.read_bytes();config=json.loads(config_raw.decode('utf-8-sig'))
 if not args.execute:print(json.dumps(dict(status='read_only_configuration',sdk_calls=0,controller_id=config.get('controller_id'),execution_enabled=EXECUTE_ENABLED)));return
 runtime=ControllerRuntime(args.session,config,args.output,args.natural)
 try:
  runtime.arm();end=time.monotonic()+args.max_wall_seconds;last=None
  while time.monotonic()<end:
   state=runtime.poll();signature=(state['status'],state['controller'].get('stage'),state['controller'].get('error'),state['mission_commit'].get('status'))
   if signature!=last:print(json.dumps(state),flush=True);last=signature
   if args.controller_file.read_bytes()!=config_raw:runtime.shared.stop_requested=1
   if args.command_file and runtime.report.get('mission_request') is None and state['controller'].get('stage')==2 and args.command_file.exists() and args.formation_file.exists():
    runtime.commit(json.loads(args.command_file.read_text(encoding='utf-8-sig')),json.loads(args.formation_file.read_text(encoding='utf-8-sig')),args.proof_file,public_command_source=args.command_file)
   if runtime.shared.phase in (3,4) and runtime.host.poll() is not None:break
   time.sleep(.02)
  if runtime.host.poll() is None:runtime.stop()
 finally:
  if runtime.host is not None and runtime.host.poll() is None:runtime.stop()
  if runtime.host is None or runtime.host.poll() is not None:runtime.close()

if __name__=='__main__':main()
