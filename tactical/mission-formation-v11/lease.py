"""MF11 continuous native leader and actual-breadcrumb follower mission.

This isolated revision has no capability until raw effect/retreat/return evidence
passes its independent qualifier. No model/API calls or background target choice.
"""
import argparse,ctypes as c,hashlib,importlib.util,json,math,os,re,struct,subprocess,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
NATIVE_LAUNCH_INTENT=False
OWNED_REPORT=False
ARGS=None
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
b=module('formation_mission_frozen_primitives',HERE.parent/'ordered-combo/lease.py')
layout_module=module("mfm11_native_layout",HERE/"native_layout.py")
Event=layout_module.Event;Support=layout_module.Support;Breadcrumb=layout_module.Breadcrumb;MoveLineage=layout_module.MoveLineage;Tactical=layout_module.Tactical
U=c.c_uint32;L=c.c_int32
class Header(c.Structure):
 _fields_=Tactical._fields_[:-1]
QUALIFIER=None

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def supplemental():
 files=list(HERE.glob('*.cpp.inc'))+[HERE/'native_layout.py',HERE/'mission_contract.py',HERE/'formation_mission_qualification.py',HERE/'wait_anchor_replan.py',HERE/'retreat_departure.py',HERE/'pending_lineage.py',HERE/'inert-layout.json',HERE.parent/'mobility_guard.py',HERE.parent/'mission_actor_admission_v2.py',HERE.parent/'mission_actor_admission.py',HERE.parent/'grounded_status_v2.py',HERE.parent/'grounded_status.py',HERE.parent/'ordered-combo/lease.py',HERE.parent/'ordered_qualification.py',HERE.parent/'combo_qualification.py',HERE.parent/'stop_sequence.py',HERE.parent/'readonly_disposal.py',HERE.parent/'recon/read_own_command_buttons.py']
 if len({p.name for p in files})!=len(files):raise ValueError('supplemental_key_collision')
 return {p.name:sha(p) for p in files}

def qualifier():
 global QUALIFIER
 if QUALIFIER is None:QUALIFIER=module('mfm11_qualification',HERE/'formation_mission_qualification.py')
 return QUALIFIER

def progress(report,mission_id):return qualifier().progress(report,mission_id)
def assess_canonical(report):return qualifier().qualify(json.loads(json.dumps(report,allow_nan=False)))
def frozen_sources_match(report):
 files={'native_binary_sha256':HERE/'bin/TacticalMissionFormation11.dll','native_host_sha256':HERE/'bin/tactical_host.exe','native_source_sha256':HERE/'lease.cpp','native_shared_sha256':HERE/'shared.h','wrapper_sha256':Path(__file__),'native_revision_sha256':HERE/'revision.json'}
 return all(report.get(k)==sha(path) for k,path in files.items()) and report.get('supplemental_sources')==supplemental()
def finite_xyz(x):return isinstance(x,list) and len(x)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in x)
def actor_health_eligible(hp):return type(hp) in (int,float) and math.isfinite(hp) and hp>=50
def initial_pair_eligible(gap):return type(gap) in (int,float) and math.isfinite(gap) and 25<=gap<=180

def plain(value,path='',bad=None):
 bad=[] if bad is None else bad
 if isinstance(value,c.Structure):return {name:plain(getattr(value,name),path+'.'+name,bad) for name,_ in value._fields_}
 if isinstance(value,c.Array):return [plain(v,path+'['+str(i)+']',bad) for i,v in enumerate(value)]
 if isinstance(value,float) and not math.isfinite(value):bad.append(path);return None
 return value

LINEAGE_PROOF_KINDS=frozenset(range(110,121))

def event_record(e):
 # Preserve every typed proof, including malformed zero proof events. Ordinary
 # zero tails need not become repeated 118-word JSON arrays on each sample.
 include_lineage=e.kind in LINEAGE_PROOF_KINDS or any(bytes(e.lineage))
 bad=[];result={name:plain(getattr(e,name),'event.'+name,bad) for name,_ in e._fields_ if name!='lineage' or include_lineage}
 if bad:result['invalid_float_fields']=bad
 return result

def capture(report,shared):
 # Native publishes seq last with MemoryBarrier+InterlockedExchange. Completed
 # entries are immutable. Decode only the new contiguous published prefix.
 base=c.addressof(shared);s=Header.from_buffer_copy(c.string_at(base,c.sizeof(Header)))
 events=report.setdefault('events',[])
 if s.count<len(events):raise ValueError('published_event_prefix_regressed')
 for i in range(len(events),max(0,min(s.count,8192))):
  address=base+Tactical.events.offset+i*c.sizeof(Event)
  if U.from_address(address).value!=i+1:break
  e=Event.from_buffer_copy(c.string_at(address,c.sizeof(Event)))
  if e.seq!=i+1 or U.from_address(address).value!=i+1:break
  events.append(event_record(e))
 bad=[];n={}
 for name,_ in Header._fields_:
  if name in ('session','commander','command','task','crumbs'):continue
  n[name]=plain(getattr(s,name),name,bad)
 for field,label in [('session','session_id'),('commander','commander_id'),('command','command_id'),('task','task_id')]:n[label]=str(uuid.UUID(bytes=struct.pack('<4I',*getattr(s,field))))
 n['crumbs']=[[plain(s.crumbs[role][i],'crumbs['+str(role)+']['+str(i)+']',bad) for i in range(min(128,s.crumb_count[role]))] for role in (0,1)]
 if bad:n['invalid_float_fields']=bad
 report['native']=n;report['progress']=progress(report,report['request']['task_id'])
 report['capture_metadata']=dict(published_prefix_count=len(events),header_count=s.count,incremental_decode=True)
 report['status']='finished' if s.phase in (3,4) else 'running'
 return s.phase in (3,4)

def original_entries(memory):
 source=(HERE/'lease.cpp').read_text();block=source.split('static Hook hooks[]={',1)[1].split(';',1)[0];rows=[]
 for address,escaped,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block):
  expected=bytes.fromhex(escaped.replace('\\x',''));actual=memory.read(int(address,0),int(length));rows.append(dict(address=address,expected=expected.hex(),actual=actual.hex()))
 if len(rows)!=16 or any(x['expected']!=x['actual'] for x in rows):raise ValueError('another_native_channel_active_or_signature_changed')
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
 base=helper.module_base(memory,HERE/'bin/TacticalMissionFormation11.dll');snapshot,ptr,timer=read_stable_header(memory,base,layout)
 def ident(field):return str(uuid.UUID(bytes=struct.pack('<4I',*getattr(snapshot,field))))
 binding=snapshot.magic==0x4d463131 and snapshot.version==11 and snapshot.pid==report['preflight']['pid'] and snapshot.token==report['request']['token'] and snapshot.seq==report['request']['seq'] and ident('session')==report['session_id'] and ident('command')==report['request']['command_id'] and ident('task')==report['request']['task_id'] and ident('commander')==report['preflight']['commander_id'] and hex(snapshot.owner)==report['preflight']['owner'] and snapshot.logic==memory.u32(0xcd8ce4)==int(report['preflight']['logic'],0)
 entries=[]
 for row in report['original_entries']:
  actual=memory.read(int(row['address'],0),len(bytes.fromhex(row['expected'])));entries.append(dict(address=row['address'],expected=row['expected'],actual=actual.hex(),restored=actual.hex()==row['expected']))
 confirmation,final_pointer,final_timer=read_stable_header(memory,base,layout)
 if final_pointer!=ptr or final_timer!=timer or bytes(confirmation)!=bytes(snapshot):raise ValueError('readonly_header_changed_during_entries')
 return dict(pid=snapshot.pid,session_id=ident('session'),commander_id=ident('commander'),command_id=ident('command'),task_id=ident('task'),seq=snapshot.seq,token=snapshot.token,owner=hex(snapshot.owner),logic=hex(snapshot.logic),native_binary_sha256=report['native_binary_sha256'],module_base=hex(base),shared_pointer=hex(ptr),layout=layout,timer=timer,binding_verified=bool(binding),phase=snapshot.phase,error=snapshot.error,active=snapshot.active,restore_mask=snapshot.restore_mask,front_return_verified=snapshot.return_verified,support_return_verified=snapshot.support.returned,entries=entries,mutations=False)

def capture_disposal(memory,report):
 helper=module('formation_disposal_readonly',HERE.parent/'readonly_disposal.py');result={};n=report['native']
 for role,dead in [(0,n.get('front_disposed_verified')),(1,n.get('support',{}).get('disposed_verified'))]:
  if not dead:continue
  actor=report['preflight']['support' if role else 'selected']['object_id'];terminal=terminal_readonly(memory,report)
  if not terminal['binding_verified'] or memory.pid!=report['preflight']['pid']:raise ValueError('disposal_source_memory_binding')
  binding={key:terminal[key] for key in ['pid','session_id','commander_id','command_id','task_id','seq','token','owner','logic','native_binary_sha256']}
  record=dict(binding,object_id=actor,role=role,source_session_id=report['session_id'],source_request_sha256=hashlib.sha256(json.dumps(report['request'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),source_preflight_sha256=hashlib.sha256(json.dumps(report['preflight'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),scans=[],terminal_before=terminal,mutations=False);last=None;end=time.monotonic()+3
  while time.monotonic()<end and len(record['scans'])<2:
   try:
    sample=helper.live_scan(memory,int(report['preflight']['logic'],0),actor)
    if last is None or sample['frame']>last:record['scans'].append(sample);last=sample['frame']
   except ValueError as error:record['error']=str(error)
   time.sleep(.05)
  record['terminal_after']=terminal_readonly(memory,report)
  result[str(role)]=record
 return result

def mission_safety(pre,memory,reader,front,support):
 gap=math.dist(front['xyz'][:2],support['xyz'][:2])
 if not initial_pair_eligible(gap):raise ValueError('initial_pair_spacing')
 own=b.own_candidates(memory,3,b.load_catalog())['candidates'];anchors=[x for x in own if x['type_hash'] in ('0xc16ff13f','0x80d4ea1e','0xc45aaeab')]
 mobility=module('formation_origin_mobility',HERE.parent/'mobility_guard.py')
 for actor in (front,support):
  if not actor.get('eligible') or not mobility.mobility_status(memory,int(actor['address'],0))['independently_movable']:raise ValueError('origin_actor_not_independently_movable')
 anchor_distances=[dict(object_id=x['object_id'],type_hash=x['type_hash'],xyz=x['xyz'],front_distance=math.dist(x['xyz'][:2],front['xyz'][:2]),support_distance=math.dist(x['xyz'][:2],support['xyz'][:2])) for x in anchors]
 anchor_distances.sort(key=lambda x:max(x['front_distance'],x['support_distance']))
 near=[t['object_id'] for t in reader.private_targets.values() if any(math.dist(t['xyz'][:2],u['xyz'][:2])<350 for u in (front,support))]
 if near:raise ValueError('retreat_origin_has_observed_enemy_threat')
 return dict(front_id=front['object_id'],support_id=support['object_id'],viewer_player_id=3,observed_frame=pre['frame'],front_initial=front['xyz'],support_initial=support['xyz'],anchor_distances_diagnostic=anchor_distances,currently_visible_enemy_threats_within350=near,origin_method='current_verified_owned_movable_positions',semantics='observed_own_origin_without_currently_visible_enemy_within350_not_omniscient_safe')



def initial_admission(memory,pre,front,support,reader,contact_id,expected_target):
 admission=module('mfm11_initial_admission',HERE.parent/'mission_actor_admission_v2.py');attempts=[];deadline=time.monotonic()+2
 for attempt in range(1,4):
  if time.monotonic()>=deadline:raise ValueError('initial_admission_budget')
  records=[]
  for actor in (front,support):
   r=admission.actor_admission(memory,int(actor['address'],0));g=r.get('grounded_status',{})
   if not admission.verify_evidence(r)['verified'] or not actor_health_eligible(g.get('hp')) or g.get('object_id')!=actor['object_id'] or g.get('address')!=actor['address'] or g.get('type_hash')!=actor['type_hash'] or g.get('owner')!=pre['owner'] or r['state_snapshot']['update']!=actor['ai_address']:raise ValueError('initial_actor_admission_rejected')
   records.append(r)
  frame=memory.u32(int(pre['logic'],0)+0x50)
  if any(frame<r['frame'] for r in records):raise ValueError('initial_clock_rollback')
  matched=all(r['frame']==frame for r in records)
  attempts.append(dict(attempt=attempt,frame=frame,records=records,matched=matched))
  if not matched:continue
  reader.collect(frame/15);target=reader.private_targets.get(contact_id)
  if not target or len(reader.private_targets)>=64:raise ValueError('initial_current_visibility_or_capacity')
  if any(target.get(k)!=expected_target.get(k) for k in ('object_id','address','owner','type_hash')):raise ValueError('initial_target_identity_changed')
  validated=memory.u32(int(pre['logic'],0)+0x50)
  if not frame<=target['observed_frame']<=validated<=frame+4 or memory.u32(int(pre['logic'],0)+0x15c) or time.monotonic()>=deadline:raise ValueError('initial_admission_expired_or_paused')
  f,s=(r['grounded_status']['xyz'] for r in records)
  if sum((target['xyz'][i]-f[i])*(f[i]-s[i]) for i in (0,1))<0:raise ValueError('initial_pair_not_ahead_target')
  return dict(frame=frame,validated_frame=validated,front=records[0],support=records[1],target=target,attempts=attempts,mutations=False)
 raise ValueError('initial_actor_pair_not_same_frame')


def require_live_host_or_terminal(host,shared):
 # A dead controller must not leave a fresh Python heartbeat extending a live
 # native mission. The existing exception path requests stop and drains safely.
 if host is not None and host.poll() is not None and shared.phase not in (3,4):
  shared.stop_requested=1
  raise RuntimeError('native_host_exited_before_terminal')


def main():
 global ARGS,OWNED_REPORT,NATIVE_LAUNCH_INTENT
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--natural',type=Path);ap.add_argument('--front-id',type=int,required=True);ap.add_argument('--support-id',type=int,required=True);ap.add_argument('--mission-file',type=Path);ap.add_argument('--proof-file',type=Path);ap.add_argument('--contact-id');ap.add_argument('--expires-frame',type=int);ap.add_argument('--lease-frames',type=int,default=4500);ap.add_argument('--combat-frames',type=int,default=300);ap.add_argument('--post-frames',type=int,default=30);ap.add_argument('--command-id');ap.add_argument('--task-id');ap.add_argument('--seq',type=int);ap.add_argument('--output',type=Path);ap.add_argument('--execute',action='store_true');a=ap.parse_args();ARGS=a
 pre,session,raw,package,registry_path,registry_digest,memory=b.readiness(a.session,a.front_id);report=None;handle=view=shared=host=None;target=None
 try:
  front=pre['selected'];supports=[u for u in pre['units'] if u['object_id']==a.support_id and u['eligible'] and u['type_hash']=='0x2c358c61']
  if front['type_hash']!='0x19ab11af' or len(supports)!=1 or a.front_id==a.support_id:raise ValueError('distinct_conscript_front_flak_support_required')
  support=supports[0];pre['support']=support
  if not a.execute:print(json.dumps(pre,ensure_ascii=False));return
  if not a.natural or not a.proof_file or not a.contact_id or not a.mission_file or a.expires_frame is None:raise ValueError('explicit_mission_contact_proof_deadline_required')
  if type(a.seq) is not int or a.seq<1 or not a.command_id or not a.task_id or not a.output:raise ValueError('explicit_order_output_binding_required')
  if not 30<=a.combat_frames<=300 or not 30<=a.post_frames<=180:raise ValueError('mission_combat_post_bounds')
  if sha(HERE/'shared.h')!=layout_module.SHARED_SHA256:raise ValueError('ctypes_shared_definition_drift')
  qualifier();sys.path[:0]=[str(BRIDGE/'visibility'),str(HERE.parent)]
  from projection import VisibilityProjection
  from collector import VisibilityCollector
  proof_raw=a.proof_file.read_bytes();proof=json.loads(proof_raw.decode('utf-8-sig'));safety_path=BRIDGE/'visibility/template-safety-2d7873e1.json';safety_raw=safety_path.read_bytes();safety=json.loads(safety_raw);projection=VisibilityProjection(session['session_id'],3,session['mod_sha256'],proof,safety)
  if not projection.verified():raise ValueError('visibility_capability_unverified')
  reader=VisibilityCollector(memory,session,3,projection);reader.collect(pre['frame']/15);contact=reader.private_targets.get(a.contact_id)
  if not contact or len(reader.private_targets)>=64:raise ValueError('explicit_contact_not_currently_visible')
  if safety['templates'][contact['type_hash']]['role'] not in ('infantry','armor','structure','economy'):raise ValueError('ground_target_scope')
  plan_raw=a.mission_file.read_bytes();plan=json.loads(plan_raw.decode('utf-8-sig'));frame=memory.u32(int(pre['logic'],0)+0x50)
  contract=module('mfm11_mission_input',HERE/'mission_contract.py');mission=contract.validate_mission(plan,session,a.front_id,a.support_id,target_contact_id=a.contact_id,now_frame=frame,expires_frame=a.expires_frame,lease_frames=a.lease_frames)
  if memory.u32(int(pre['logic'],0)+0x15c):raise ValueError('mission_paused')
  natural=json.loads(a.natural.read_text(encoding='utf-8-sig'));b.compatible_natural_calls(natural,session['pid'])
  if natural['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')
  layout=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
  if layout!=layout_module.layout():raise ValueError('layout_mismatch')
  button=module('mfm11_owned_button',HERE.parent/'recon/read_own_command_buttons.py').inspect(memory,int(front['address'],0))
  if button.get('toggle') is None:raise ValueError('exact_molotov_button_missing')
  entries=original_entries(memory);original_entries(memory)
  command=str(uuid.UUID(a.command_id));task=str(uuid.UUID(a.task_id));token=int.from_bytes(os.urandom(4),'little') or 1;target=a.output
  if target.exists():raise ValueError('existing_report_do_not_reuse_order')
  origin=mission_safety(pre,memory,reader,front,support)
  req=dict(command_id=command,task_id=task,seq=a.seq,token=token,front_id=a.front_id,support_id=a.support_id,target_contact_id=a.contact_id,target_object_id=contact['object_id'],target_role=safety['templates'][contact['type_hash']]['role'],target=contact['xyz'],expires_frame=a.expires_frame,lease_frames=mission['lease_frames'],combat_frames=a.combat_frames,post_frames=a.post_frames,safe_origin=origin,navigation_mode=mission['navigation_mode'],visibility_proof_sha256=hashlib.sha256(proof_raw).hexdigest(),safety_sha256=hashlib.sha256(safety_raw).hexdigest(),mission_source_path=str(a.mission_file.resolve()),mission_source_sha256=hashlib.sha256(plan_raw).hexdigest(),mission=dict(plan),button=button)
  contact=dict(contact,template=memory.u32(contact['address']+4));report=dict(session_id=session['session_id'],executable_sha256=b.EXPECTED,package_sha256=session['mod_sha256'],native_binary_sha256=sha(HERE/'bin/TacticalMissionFormation11.dll'),native_host_sha256=sha(HERE/'bin/tactical_host.exe'),wrapper_sha256=sha(__file__),native_source_sha256=sha(HERE/'lease.cpp'),native_shared_sha256=sha(HERE/'shared.h'),native_revision_sha256=sha(HERE/'revision.json'),native_includes_sha256={p.name:sha(p) for p in HERE.glob('*.cpp.inc')},supplemental_sources=supplemental(),mission_contract_sha256=sha(HERE/'mission_contract.py'),native_layout_sha256=sha(HERE/'native_layout.py'),preflight=pre,private_target=contact,request=req,original_entries=entries,status='preflight',events=[],native={},model_requests=0,native_launch_intent_persisted=False,pre_dispatch_helper_sha256=sha(HERE.parent/'pre_dispatch_formation_v11_contract.py'),wrapper_revision='mfm11_dynamic_breadcrumb_v1',wrapper_filename='lease.py',pre_dispatch_helper='pre_dispatch_formation_v11_contract.py',initial_preflight=json.loads(json.dumps(pre)),initial_safe_origin=origin)
  if qualifier().source_pins(report) is not True:raise ValueError('compiled_source_bundle_unverified')
  b.durable(target,report);OWNED_REPORT=True;k=b.k;w=b.w;k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
  handle=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Tactical),'Local\\RA3TacticalMissionFormation11_'+str(session['pid'])+'_'+str(token))
  if not handle or c.get_last_error()==183:raise ValueError('mapping_token_reused')
  view=k.MapViewOfFile(handle,0xf001f,0,0,c.sizeof(Tactical))
  if not view:raise c.WinError(c.get_last_error())
  c.memset(view,0,c.sizeof(Tactical));shared=Tactical.from_address(view);s=shared;s.magic=0x4d463131;s.version=11;s.pid=session['pid'];s.thread=pre['window_thread'];s.session[:]=b.words(session['session_id']);s.commander[:]=b.words(pre['commander_id']);s.command[:]=b.words(command);s.task[:]=b.words(task);s.seq=a.seq;s.token=token
  for name in ('owner','ai','personality','personality_id','player_template','logic','script_team','default_team'):setattr(s,name,int(pre[name],0))
  s.unit=int(front['address'],0);s.object_id=front['object_id'];s.type_hash=int(front['type_hash'],0);s.update=int(front['ai_address'],0);s.support.thing=int(support['address'],0);s.support.id=support['object_id'];s.support.hash=int(support['type_hash'],0);s.support.update=int(support['ai_address'],0)
  s.button=int(button['toggle']['entry'],0);s.button_schema=int(button['toggle']['schema'],0);s.command_set=int(button['command_set_hash'],0);s.lease_frames=req['lease_frames'];s.post_frames=a.post_frames;s.mission_deadline_frame=a.expires_frame;s.combat_frames=a.combat_frames;s.memory_ttl_frames=900;s.approach_limit=2100;s.retreat_limit=1800;s.hold_timeout_frames=60;s.route_count=s.route_ready=s.route_generation=0;s.pulse_requested=s.pulse_acknowledged=0;s.planning_threat_clear=1;s.heartbeat_tick=int(k.GetTickCount())&0xffffffff
  ft=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(memory.handle,*[c.byref(x) for x in ft]):raise c.WinError(c.get_last_error())
  s.start_low=ft[0].dwLowDateTime;s.start_high=ft[0].dwHighDateTime
  if a.session.read_bytes()!=raw or sha(package)!=session['mod_sha256'] or sha(registry_path)!=registry_digest or a.mission_file.read_bytes()!=plan_raw:raise ValueError('binding_changed_before_dispatch')
  late=initial_admission(memory,pre,front,support,reader,a.contact_id,contact);report['initial_admission']=late
  front.update(xyz=late['front']['grounded_status']['xyz'],hp=late['front']['grounded_status']['hp'],mission_admission=late['front']);support.update(xyz=late['support']['grounded_status']['xyz'],hp=late['support']['grounded_status']['hp'],mission_admission=late['support']);pre['frame']=late['frame']
  contract.validate_mission(plan,session,a.front_id,a.support_id,target_contact_id=a.contact_id,now_frame=late['validated_frame'],expires_frame=a.expires_frame,lease_frames=a.lease_frames)
  req['safe_origin']=mission_safety(pre,memory,reader,front,support);req['target']=late['target']['xyz'];report['private_target']=dict(late['target'],template=contact['template']);s.safe_front[:]=front['xyz'];s.safe_support[:]=support['xyz'];s.target[:]=late['target']['xyz'];s.target_unit=contact['address'];s.target_id=contact['object_id'];s.target_hash=int(contact['type_hash'],0);s.target_owner=contact['owner'];s.target_template=contact['template'];s.target_observed_frame=late['target']['observed_frame'];s.planning_threat_frame=late['target']['observed_frame']
  if a.session.read_bytes()!=raw or a.proof_file.read_bytes()!=proof_raw or a.mission_file.read_bytes()!=plan_raw or sha(package)!=session['mod_sha256'] or sha(registry_path)!=registry_digest or not frozen_sources_match(report):raise ValueError('binding_changed_at_launch_intent')
  report['native_launch_intent_persisted']=True;b.durable(target,report);NATIVE_LAUNCH_INTENT=True
  with target.with_suffix('.host.log').open('w',encoding='utf-8') as log:
   host=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=log,stderr=log);end=time.monotonic()+335;written=0;depcheck=0
   while time.monotonic()<end:
    shared.heartbeat_tick=int(k.GetTickCount())&0xffffffff
    now=time.monotonic()
    if now-depcheck>=1:
     if a.session.read_bytes()!=raw or sha(registry_path)!=registry_digest or a.proof_file.read_bytes()!=proof_raw or safety_path.read_bytes()!=safety_raw or not frozen_sources_match(report):shared.stop_requested=1
     depcheck=now
    terminal=capture(report,shared)
    if report['native'].get('weapon_template') and not report.get('weapon_asset_binding'):b.capture_weapon_binding(report,memory)
    if terminal or now-written>=1:b.durable(target,report);written=now
    if host.poll() is not None:
     require_live_host_or_terminal(host,shared)
     break
    time.sleep(.1)
   if host.poll() is None:shared.stop_requested=1
   capture(report,shared);b.capture_weapon_binding(report,memory);report['host_exit']=host.poll()
   if shared.phase in (3,4) and host.poll() is not None:report['terminal_readonly']=terminal_readonly(memory,report);report['disposal_readonly']=capture_disposal(memory,report)
   if host.poll() is None:report['status']='unknown_pending_native_return'
   report['assessment']=assess_canonical(report);b.durable(target,report);print(json.dumps(dict(report=str(target),status=report['status'],assessment=report['assessment'].get('status'))))
 except BaseException as error:
  if report is not None:
   if shared is not None and NATIVE_LAUNCH_INTENT:
    shared.stop_requested=1;end=time.monotonic()+12
    while host and time.monotonic()<end:
     shared.heartbeat_tick=int(b.k.GetTickCount())&0xffffffff
     terminal=capture(report,shared)
     if terminal and host.poll() is not None:break
     time.sleep(.1)
   report.update(status='dispatch_failed_native_terminal' if NATIVE_LAUNCH_INTENT and shared is not None and shared.phase in (3,4) else 'unknown_pending_native_return' if NATIVE_LAUNCH_INTENT else 'no_dispatch_rejected',error=type(error).__name__,host_exit=host.poll() if host else None);b.durable(target,report)
  raise
 finally:
  memory.close()
  if view:b.k.UnmapViewOfFile(view)
  if handle:b.k.CloseHandle(handle)

if __name__=='__main__':
 try:main()
 except Exception as error:
  if ARGS is not None and ARGS.execute and not NATIVE_LAUNCH_INTENT:
   helper=module('mfm11_pre_dispatch',HERE.parent/'pre_dispatch_formation_v11_contract.py');record=helper.rejection(ARGS,HERE,error,owned=OWNED_REPORT);print(json.dumps(dict(status=record['status'],reason=record['pre_dispatch']['reason_code'])));raise SystemExit(64)
  raise
