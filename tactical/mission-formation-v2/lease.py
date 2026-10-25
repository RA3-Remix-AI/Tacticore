"""One bounded, continuous Conscript/front + Flak/position-support mission.

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
U=c.c_uint32;L=c.c_int32
class Event(c.Structure):
 _fields_=b.Event._fields_+[(x,U) for x in 'unit_id role mission_stage route_index nav_step target_visible mission_deadline_frame mission_reason native_error'.split()]+[('own_hp',c.c_float),('front_goal',c.c_float*3),('support_goal',c.c_float*3),('command_xyz',c.c_float*3),('visible_target_xyz',c.c_float*3),('argument_path',U),('argument_limit',c.c_float)]
class Support(c.Structure):
 _fields_=[(x,U) for x in 'thing id hash update original_team detach_calls return_calls returned move_calls native_move native_attack native_add native_remove native_stop stop_calls private_stop_calls private_stop_frame stable_samples gate_samples last_sample_frame disposed_verified absence_samples last_absence_frame'.split()]+[('stopped_xyz',c.c_float*3)]
MISSION='route_count mission_stage route_index nav_step nav_frame nav_arrivals nav_paired nav_last_frame approach_completed retreat_completed combat_started retreat_started mission_deadline_frame combat_frames retreat_reason native_stop front_retreat_arrivals support_retreat_arrivals combat_geometry_samples retreat_requested heartbeat_tick front_disposed_verified front_absence_samples front_last_absence_frame cleanup_started cleanup_front_stopped cleanup_support_stopped'.split()
class Tactical(c.Structure):
 _fields_=b.Tactical._fields_[:-1]+[('support',Support)]+[(x,U) for x in MISSION]+[('route',(c.c_float*3)*16)]+[(x,c.c_float*3) for x in 'safe_front safe_support front_goal support_goal front_hold support_hold'.split()]+[('events',Event*8192)]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def supplemental():
 files=list(HERE.glob('*.cpp.inc'))+[HERE/'prepare_sources.py',HERE/'formation_mission_qualification.py',HERE/'mission_route.py',HERE/'inert-layout.json',HERE.parent/'mobility_guard.py']
 return {p.name:sha(p) for p in files}
def progress(report,mission_id):
 return module('formation_mission_progress',HERE/'formation_mission_qualification.py').progress(report,mission_id)
def assess_canonical(report):return module('formation_mission_qualifier',HERE/'formation_mission_qualification.py').qualify(json.loads(json.dumps(report,allow_nan=False)))

def finite_xyz(x):return isinstance(x,list) and len(x)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in x)
def actor_health_eligible(hp):return type(hp) in (int,float) and math.isfinite(hp) and hp>=50
def initial_pair_eligible(gap):return type(gap) in (int,float) and math.isfinite(gap) and 25<=gap<=180

def plain(value,path='',bad=None):
 bad=[] if bad is None else bad
 if isinstance(value,c.Array):return [plain(v,path+'['+str(i)+']',bad) for i,v in enumerate(value)]
 if isinstance(value,float) and not math.isfinite(value):bad.append(path);return None
 return value
def event_record(e):
 bad=[];result={name:plain(getattr(e,name),name,bad) for name,_ in Event._fields_}
 if bad:result['invalid_float_fields']=bad
 return result
def capture(report,shared):
 s=Tactical.from_buffer_copy(c.string_at(c.addressof(shared),c.sizeof(Tactical)));events=[]
 for i in range(max(0,min(s.count,8192))):
  if s.events[i].seq!=i+1:break
  events.append(event_record(s.events[i]))
 report['events']=events
 scalar=[name for name,kind in Tactical._fields_ if kind in (U,L)]
 report['native']={name:getattr(s,name) for name in scalar if name not in ('magic','version','start_low','start_high','unit','update','owner','ai','personality','player_template','target_unit','target_owner','target_template','script_team','default_team')}
 n=report['native'];n.update(session_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.session))),commander_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.commander))),command_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.command))),task_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.task))),target=list(s.target),damage_total=s.damage_total)
 n['support']={name:plain(getattr(s.support,name)) for name,_ in Support._fields_}
 for name in 'safe_front safe_support front_goal support_goal front_hold support_hold'.split():n[name]=list(getattr(s,name))
 report['progress']=progress(report,report['request']['task_id'])
 report['status']='finished' if s.phase in (3,4) else 'running'
 return s.phase in (3,4)

def original_entries(memory):
 source=(HERE/'lease.cpp').read_text();block=source.split('static Hook hooks[]={',1)[1].split(';',1)[0];rows=[]
 for address,escaped,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block):
  expected=bytes.fromhex(escaped.replace('\\x',''));actual=memory.read(int(address,0),int(length));rows.append(dict(address=address,expected=expected.hex(),actual=actual.hex()))
 if len(rows)!=13 or any(x['expected']!=x['actual'] for x in rows):raise ValueError('another_native_channel_active_or_signature_changed')
 return rows

def terminal_readonly(memory,report):
 layout=json.loads((HERE/'inert-layout.json').read_text())
 if layout['dll_sha256']!=report['native_binary_sha256']:raise ValueError('inert_layout_dll_mismatch')
 # Module enumeration and RPM only; no native function or debug-register calls.
 helper=module('formation_terminal_module_lookup',HERE.parent/'readonly_disposal.py')
 base=helper.module_base(memory,HERE/'bin/TacticalMissionFormation2.dll');timer=memory.u32(base+layout['timer_rva']);ptr=memory.u32(base+layout['shared_pointer_rva']);snapshot=Tactical();block=memory.read(ptr,Tactical.events.offset);c.memmove(c.addressof(snapshot),block,len(block))
 def ident(field):return str(uuid.UUID(bytes=struct.pack('<4I',*getattr(snapshot,field))))
 binding=snapshot.magic==0x4d464d32 and snapshot.version==2 and snapshot.pid==report['preflight']['pid'] and snapshot.token==report['request']['token'] and snapshot.seq==report['request']['seq'] and ident('session')==report['session_id'] and ident('command')==report['request']['command_id'] and ident('task')==report['request']['task_id'] and ident('commander')==report['preflight']['commander_id'] and hex(snapshot.owner)==report['preflight']['owner'] and snapshot.logic==memory.u32(0xcd8ce4)==int(report['preflight']['logic'],0)
 entries=[]
 for row in report['original_entries']:
  actual=memory.read(int(row['address'],0),len(bytes.fromhex(row['expected'])));entries.append(dict(address=row['address'],expected=row['expected'],actual=actual.hex(),restored=actual.hex()==row['expected']))
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

def route_points(plan,pre,session,memory,front,support):
 if plan.get('schema_version')!=1 or plan.get('session_id')!=session['session_id'] or plan.get('player_id')!=3 or plan.get('front_id')!=front['object_id'] or plan.get('support_id')!=support['object_id']:raise ValueError('mission_route_binding')
 route=plan.get('route',[])
 if not 2<=len(route)<=16:raise ValueError('route_count')
 current=front['xyz'];result=[];owned=b.own_candidates(memory,3,b.load_catalog())['candidates']
 for point in route:
  source_path=Path(point['own_source_path']);raw=source_path.read_bytes();source=json.loads(raw.decode('utf-8-sig'))
  if sha(source_path)!=point['own_source_sha256'] or source.get('session_id')!=session['session_id'] or source.get('pid')!=session['pid'] or source.get('player_id')!=3 or not 0<source.get('logic_frame_candidate',0)<=pre['frame']:raise ValueError('route_source_identity')
  records=[x for x in source.get('own_objects',[]) if x.get('object_id')==point['own_source_object_id'] and x.get('type_hash') in ('0x19ab11af','0x2c358c61','0x33026fa1') and x.get('hp',0)>0 and finite_xyz(x.get('xyz'))]
  if len(records)!=1 or not finite_xyz(point.get('xyz')) or any(abs(a-z)>.01 for a,z in zip(records[0]['xyz'],point['xyz'])):raise ValueError('route_source_position')
  record=records[0]
  if record['type_hash']!='0x33026fa1' and ('status84' not in record or int(record['status84'],0)&0x20080000):raise ValueError('route_source_not_independently_movable')
  xyz=point['xyz'];d=math.dist(current[:2],xyz[:2])
  if not 30<=d<=175 or abs(current[2]-xyz[2])>100:raise ValueError('formation_leg_bounds')
  if any(x['object_id'] not in (front['object_id'],support['object_id']) and math.dist(x['xyz'][:2],xyz[:2])<20 and abs(x['xyz'][2]-xyz[2])<10 for x in owned):raise ValueError('route_current_own_occupant')
  result.append(dict(xyz=list(xyz),own_source_path=str(source_path.resolve()),own_source_sha256=hashlib.sha256(raw).hexdigest(),own_source_object_id=record['object_id'],observed_frame=source['logic_frame_candidate']));current=xyz
 if sum(math.dist(a[:2],z[:2]) for a,z in zip([front['xyz']]+[p['xyz'] for p in result[:-1]],[p['xyz'] for p in result]))<=120:raise ValueError('not_longer_than_old_primitive')
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

def main():
 global ARGS,OWNED_REPORT,NATIVE_LAUNCH_INTENT
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--natural',type=Path);ap.add_argument('--front-id',type=int,required=True);ap.add_argument('--support-id',type=int,required=True);ap.add_argument('--mission-file',type=Path);ap.add_argument('--proof-file',type=Path);ap.add_argument('--contact-id');ap.add_argument('--expires-frame',type=int);ap.add_argument('--lease-frames',type=int,default=4500);ap.add_argument('--combat-frames',type=int,default=300);ap.add_argument('--post-frames',type=int,default=30);ap.add_argument('--command-id');ap.add_argument('--task-id');ap.add_argument('--seq',type=int);ap.add_argument('--output',type=Path);ap.add_argument('--execute',action='store_true');a=ap.parse_args()
 ARGS=a
 pre,session,raw,package,registry_path,registry_digest,memory=b.readiness(a.session,a.front_id);report=None;handle=view=shared=host=None;target=None
 try:
  front=pre['selected'];supports=[u for u in pre['units'] if u['object_id']==a.support_id and u['eligible'] and u['type_hash']=='0x2c358c61']
  if front['type_hash']!='0x19ab11af' or len(supports)!=1 or a.front_id==a.support_id:raise ValueError('distinct_conscript_front_flak_support_required')
  support=supports[0];pre['support']=support
  if not a.execute:print(json.dumps(pre,ensure_ascii=False));return
  if not a.natural or not a.proof_file or not a.contact_id or not a.mission_file or a.expires_frame is None:raise ValueError('explicit_mission_contact_proof_deadline_required')
  sys.path[:0]=[str(BRIDGE/'visibility'),str(HERE.parent)]
  from projection import VisibilityProjection
  from collector import VisibilityCollector
  from mobility_guard import mobility_status
  proof_raw=a.proof_file.read_bytes();proof=json.loads(proof_raw.decode('utf-8-sig'));safety_path=BRIDGE/'visibility/template-safety-2d7873e1.json';safety_raw=safety_path.read_bytes();safety=json.loads(safety_raw);projection=VisibilityProjection(session['session_id'],3,session['mod_sha256'],proof,safety)
  if not projection.verified():raise ValueError('visibility_capability_unverified')
  reader=VisibilityCollector(memory,session,3,projection);reader.collect(pre['frame']/15);contact=reader.private_targets.get(a.contact_id)
  if not contact:raise ValueError('explicit_contact_not_currently_visible')
  if safety['templates'][contact['type_hash']]['role'] not in ('infantry','armor','structure','economy'):raise ValueError('ground_target_scope')
  for u in (front,support):
   if not mobility_status(memory,int(u['address'],0))['independently_movable'] or not actor_health_eligible(u['hp']):raise ValueError('actor_not_healthy_independently_movable')
  origin_safety=mission_safety(pre,memory,reader,front,support)
  plan_raw=a.mission_file.read_bytes();plan=json.loads(plan_raw.decode('utf-8-sig'))
  if 'route' not in plan:
   history=plan.get('formation_history_dir')
   if not isinstance(history,str):raise ValueError('formation_history_dir_or_explicit_route_required')
   planner=module('formation_mission_own_route_planner',HERE/'mission_route.py');plan=planner.plan_from_history(history,pre,session,front,support,contact['xyz'],b.own_candidates(memory,3,b.load_catalog())['candidates'])
  points=route_points(plan,pre,session,memory,front,support)
  if math.dist(points[-1]['xyz'][:2],contact['xyz'][:2])>300:raise ValueError('last_known_waypoint_not_near_current_visible_target')
  obs=json.loads(a.natural.read_text(encoding='utf-8-sig'));b.compatible_natural_calls(obs,session['pid'])
  if obs['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')
  button=module('mission_formation_button',HERE.parent/'recon/read_own_command_buttons.py').inspect(memory,int(front['address'],0))
  layout=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
  if layout!={'event':c.sizeof(Event),'tactical':c.sizeof(Tactical),'events':Tactical.events.offset,'unused1':0,'unused2':0}:raise ValueError('layout_mismatch')
  frame=memory.u32(int(pre['logic'],0)+0x50)
  if memory.u32(int(pre['logic'],0)+0x15c) or not 120<=a.expires_frame-frame<=4500 or not 120<=a.lease_frames<=4500 or not 30<=a.combat_frames<=300 or not 30<=a.post_frames<=180:raise ValueError('mission_deadline_or_pause_bounds')
  entries=original_entries(memory);original_entries(memory)
  command=str(uuid.UUID(a.command_id)) if a.command_id else str(uuid.uuid4());task=str(uuid.UUID(a.task_id)) if a.task_id else str(uuid.uuid4());seq=a.seq if a.seq is not None else int(time.monotonic()*1000)&0x7fffffff;token=int.from_bytes(os.urandom(4),'little') or 1
  target=a.output or Path(session['run_directory'])/('mission-formation-'+str(token)+'.json')
  if target.exists():raise ValueError('existing_report_do_not_reuse_order')
  req=dict(command_id=command,task_id=task,seq=seq,token=token,front_id=a.front_id,support_id=a.support_id,target_contact_id=a.contact_id,target_object_id=contact['object_id'],target_role=safety['templates'][contact['type_hash']]['role'],target=contact['xyz'],expires_frame=a.expires_frame,lease_frames=min(a.lease_frames,a.expires_frame-frame),combat_frames=a.combat_frames,post_frames=a.post_frames,route=points,safe_origin=origin_safety,visibility_proof_sha256=hashlib.sha256(proof_raw).hexdigest(),safety_sha256=hashlib.sha256(safety_raw).hexdigest(),mission_source_path=str(a.mission_file.resolve()),mission_source_sha256=hashlib.sha256(plan_raw).hexdigest(),button=button)
  contact=dict(contact,template=memory.u32(contact['address']+4));report=dict(session_id=session['session_id'],executable_sha256=b.EXPECTED,package_sha256=session['mod_sha256'],native_binary_sha256=sha(HERE/'bin/TacticalMissionFormation2.dll'),native_host_sha256=sha(HERE/'bin/tactical_host.exe'),wrapper_sha256=sha(__file__),native_source_sha256=sha(HERE/'lease.cpp'),native_shared_sha256=sha(HERE/'shared.h'),supplemental_sources=supplemental(),preflight=pre,private_target=contact,request=req,original_entries=entries,status='preflight',events=[],native={},model_requests=0)
  report['pre_dispatch_helper_sha256']=sha(HERE.parent/'pre_dispatch_formation_v2_contract.py');report['native_launch_intent_persisted']=False
  b.durable(target,report);OWNED_REPORT=True;k=b.k;w=b.w;k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
  handle=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Tactical),'Local\\RA3TacticalMissionFormation2_'+str(session['pid'])+'_'+str(token))
  if not handle or c.get_last_error()==183:raise ValueError('mapping_token_reused')
  view=k.MapViewOfFile(handle,0xf001f,0,0,c.sizeof(Tactical))
  if not view:raise c.WinError(c.get_last_error())
  c.memset(view,0,c.sizeof(Tactical));shared=Tactical.from_address(view);s=shared;s.magic=0x4d464d32;s.version=2;s.pid=session['pid'];s.thread=pre['window_thread'];s.session[:]=b.words(session['session_id']);s.commander[:]=b.words(pre['commander_id']);s.command[:]=b.words(command);s.task[:]=b.words(task);s.seq=seq;s.token=token
  for name in ('owner','ai','personality','personality_id','player_template','logic','script_team','default_team'):setattr(s,name,int(pre[name],0))
  s.unit=int(front['address'],0);s.object_id=front['object_id'];s.type_hash=int(front['type_hash'],0);s.update=int(front['ai_address'],0);s.support.thing=int(support['address'],0);s.support.id=support['object_id'];s.support.hash=int(support['type_hash'],0);s.support.update=int(support['ai_address'],0)
  s.button=int(button['toggle']['entry'],0);s.button_schema=int(button['toggle']['schema'],0);s.command_set=int(button['command_set_hash'],0);s.lease_frames=req['lease_frames'];s.post_frames=a.post_frames;s.mission_deadline_frame=a.expires_frame;s.combat_frames=a.combat_frames;s.route_count=len(points);s.heartbeat_tick=int(k.GetTickCount())&0xffffffff
  for i,point in enumerate(points):s.route[i][:]=point['xyz']
  s.target[:]=contact['xyz'];s.target_unit=contact['address'];s.target_id=contact['object_id'];s.target_hash=int(contact['type_hash'],0);s.target_owner=contact['owner'];s.target_template=contact['template'];s.target_observed_frame=contact['observed_frame']
  ft=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(memory.handle,*[c.byref(v) for v in ft]):raise c.WinError(c.get_last_error())
  s.start_low=ft[0].dwLowDateTime;s.start_high=ft[0].dwHighDateTime
  if a.session.read_bytes()!=raw or sha(package)!=session['mod_sha256'] or sha(registry_path)!=registry_digest or a.mission_file.read_bytes()!=plan_raw:raise ValueError('binding_changed_before_dispatch')
  report['status']='dispatch_pending';b.durable(target,report)
  with target.with_suffix('.host.log').open('w',encoding='utf-8') as log:
   NATIVE_LAUNCH_INTENT=True;report['native_launch_intent_persisted']=True;b.durable(target,report)
   host=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=log,stderr=log);end=time.monotonic()+335
   while time.monotonic()<end:
    if a.session.read_bytes()!=raw or sha(registry_path)!=registry_digest or a.proof_file.read_bytes()!=proof_raw or safety_path.read_bytes()!=safety_raw or supplemental()!=report['supplemental_sources']:shared.stop_requested=1
    shared.heartbeat_tick=int(k.GetTickCount())&0xffffffff
    capture(report,shared);b.capture_weapon_binding(report,memory);b.durable(target,report)
    if host.poll() is not None:break
    time.sleep(.4)
   if host.poll() is None:shared.stop_requested=1
   capture(report,shared);b.capture_weapon_binding(report,memory);report['host_exit']=host.poll()
   if shared.phase in (3,4) and host.poll() is not None:
    report['terminal_readonly']=terminal_readonly(memory,report);report['disposal_readonly']=capture_disposal(memory,report)
   if host.poll() is None:report['status']='unknown_pending_native_return'
   report['assessment']=assess_canonical(report);b.durable(target,report);print(json.dumps(dict(report=str(target),status=report['status'],native=report['native'],assessment=report['assessment']),ensure_ascii=False))
 except BaseException as error:
  if report is not None:
   if shared is not None:
    shared.stop_requested=1;end=time.monotonic()+12
    while not capture(report,shared) and host and time.monotonic()<end:time.sleep(.1)
   report.update(status='dispatch_failed_native_terminal' if shared is not None and shared.phase in (3,4) else 'unknown_pending_native_return' if NATIVE_LAUNCH_INTENT else 'no_dispatch_rejected',error=str(error),host_exit=host.poll() if host else None);b.durable(target,report)
  raise
 finally:
  memory.close()
  if view:b.k.UnmapViewOfFile(view)
  if handle:b.k.CloseHandle(handle)
if __name__=='__main__':
 try:main()
 except Exception as error:
  if ARGS is not None and ARGS.execute and not NATIVE_LAUNCH_INTENT:
   try:
    helper=module('formation_pre_dispatch_contract',HERE.parent/'pre_dispatch_formation_v2_contract.py');record=helper.rejection(ARGS,HERE,error,owned=OWNED_REPORT);print(json.dumps(dict(status=record['status'],reason=record['pre_dispatch']['reason_code'])));raise SystemExit(64)
   except SystemExit:raise
   except Exception:pass
  raise
