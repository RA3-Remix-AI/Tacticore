"""Bounded tactical lease smoke. --readiness is read-only; --execute is parent-only.
Normal UNIT_AI_TRANSFER(false/true) returns to native common pool, not original squad.
"""
import argparse,ctypes as c,hashlib,json,math,os,struct,subprocess,sys,time,uuid
from ctypes import wintypes as w
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
sys.path[:0]=[str(BRIDGE/'production'),str(BRIDGE/'native-ai'),str(BRIDGE/'integration')]
from observe_production import Memory,k,EXPECTED
from session_package import verify_session_package
from natural_evidence import compatible_natural_calls
from read_selected_personality import inspect_player,resolve_registry
from own_candidates import own_candidates,load_catalog
U=c.c_uint32;L=c.c_int32
class Event(c.Structure):
 _fields_=[(x,U) for x in 'seq kind tag frame tick thread caller team owner source arg'.split()]+[(x,c.c_float) for x in 'x y z'.split()]+[(x,U) for x in 'sm sm_flags state state_id path path_node'.split()]+[('requested',c.c_float*3),('effective',c.c_float*3),('path_xy',c.c_float*2),('command_xyz',c.c_float*3),('argument_path',U),('argument_limit',c.c_float)]
HEADER='magic version pid thread owner ai personality personality_id player_template start_low start_high'.split()
TAIL='unit object_id type_hash update logic original_team script_team default_team lease_frames post_frames expires_frame'.split()
RESULT='error restore_mask callback_thread issued_frame returned_frame move_calls detach_calls return_calls arrival_samples native_move native_attack native_add native_remove owner_fail lifecycle_fail paused_samples overflow return_verified return_pending'.split()
class Tactical(c.Structure):
 _fields_=[(x,U) for x in HEADER]+[('session',U*4),('commander',U*4),('command',U*4),('task',U*4),('token',U),('seq',U)]+[(x,U) for x in TAIL]+[('target',c.c_float*3)]+[(x,L) for x in 'phase stop_requested active count'.split()]+[(x,U) for x in RESULT]+[(x,U) for x in 'stop_calls private_stop_calls private_stop_frame move_issued_frame stable_samples stop_gate_samples last_sample_frame last_arrival_frame'.split()]+[('stopped_xyz',c.c_float*3)]+[('events',Event*4096)]
def durable(path,record):
 temp=path.with_suffix(path.suffix+'.tmp')
 with temp.open('w',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
 for attempt in range(25):
  try:temp.replace(path);return
  except PermissionError:
   if attempt==24:raise
   time.sleep(.02)
def words(value):return struct.unpack('<4I',uuid.UUID(str(value)).bytes)
def event_record(event):
 invalid=[]
 def plain(value,path):
  if isinstance(value,c.Array):return [plain(x,path+'['+str(i)+']') for i,x in enumerate(value)]
  if isinstance(value,float) and not math.isfinite(value):invalid.append(path);return None
  return value
 result={name:plain(getattr(event,name),name) for name,_ in Event._fields_}
 if invalid:result['invalid_float_fields']=invalid
 return result
def known_point(path,object_id,pre,session,memory):
 raw=path.read_bytes();source=json.loads(raw.decode('utf-8-sig'))
 if source['session_id']!=session['session_id']:raise ValueError('known_point_other_session')
 if 'own_objects' in source:
  if source['pid']!=session['pid'] or source['player_id']!=3:raise ValueError('known_point_other_player')
  matches=[x for x in source['own_objects'] if x['object_id']==object_id and x['hp']>0]
  if len(matches)!=1:raise ValueError('known_point_object_not_unique')
  unit=matches[0];xyz=unit['xyz'];frame=source['logic_frame_candidate'];kind='read_only_own_snapshot'
 else:
  n=source['native'];unit=source['preflight']['selected']
  if source['preflight']['pid']!=session['pid'] or source['preflight']['player_id']!=3 or n['phase']!=3 or n['active']!=0 or not n['return_verified'] or not n['restore_mask']:raise ValueError('known_point_lease_not_clean')
  if object_id is not None and unit['object_id']!=object_id:raise ValueError('known_point_wrong_object')
  matches=[x for x in source['events'] if x['kind']==3 and n['issued_frame']<=x['frame']<=n['returned_frame'] and hex(x['owner'])==source['preflight']['owner']]
  if not matches:raise ValueError('known_point_no_owned_position')
  sample=matches[-1];xyz=[sample['x'],sample['y'],sample['z']];frame=sample['frame'];kind='clean_native_own_lease_position'
 if unit['type_hash'] not in ('0x19ab11af','0x2c358c61','0x33026fa1') or len(xyz)!=3 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in xyz):raise ValueError('known_point_not_ground_infantry')
 if not 0<frame<=pre['frame'] or abs(xyz[2]-pre['selected']['xyz'][2])>300:raise ValueError('known_point_height_or_time')
 snap=own_candidates(memory,3,load_catalog())
 occupied=[x['object_id'] for x in snap['candidates'] if x['object_id']!=pre['selected']['object_id'] and math.dist(x['xyz'][:2],xyz[:2])<30 and abs(x['xyz'][2]-xyz[2])<10]
 if occupied:raise ValueError('known_point_current_own_occupant:'+str(occupied))
 return dict(xyz=xyz,observed_frame=frame,source_object_id=unit['object_id'],source_kind=kind,source_path=str(path.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),current_own_occupants_within30=occupied,note='Previously occupied ground position, not proof of current path reachability.')
def capture_shared(report,shared):
 shared=Tactical.from_buffer_copy(c.string_at(c.addressof(shared),c.sizeof(Tactical)))
 report['events']=[]
 for index in range(max(0,min(shared.count,4096))):
  event=shared.events[index]
  if event.seq!=index+1:break
  report['events'].append(event_record(event))
 report['native']={x:getattr(shared,x) for x in RESULT+'stop_calls private_stop_calls private_stop_frame move_issued_frame stable_samples stop_gate_samples last_sample_frame last_arrival_frame'.split()+['phase','active','count']}
 report['native'].update(lease_frames=shared.lease_frames,expires_frame=shared.expires_frame,target=list(shared.target),session_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.session))),commander_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.commander))),command_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.command))),task_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.task))),seq=shared.seq)
 report['status']='finished' if shared.phase in (3,4) else 'running'
 return shared.phase in (3,4)
def window_thread(pid):
 user=c.WinDLL('user32',use_last_error=True);found=[];CB=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
 user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];user.GetWindowThreadProcessId.restype=w.DWORD
 @CB
 def callback(hwnd,_):
  owner=w.DWORD();thread=user.GetWindowThreadProcessId(hwnd,c.byref(owner))
  if owner.value==pid and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd,4):found.append(thread)
  return True
 user.EnumWindows(callback,0)
 if len(set(found))!=1:raise ValueError('game_window_thread_ambiguous')
 return found[0]
def readiness(session_path,object_id=None):
 raw=session_path.read_bytes();session=json.loads(raw.decode('utf-8-sig'));package=verify_session_package(session);memory=Memory(session['pid'],session)
 try:
  registry_path=Path(session['registry']);registry=json.loads(registry_path.read_text(encoding='utf-8-sig'))
  if registry['registry_revision']!=session['registry_revision']:raise ValueError('registry_revision_mismatch')
  snapshot=own_candidates(memory,3,load_catalog());owners={int(x['owner_address'],0) for x in snapshot['candidates']}
  if len(owners)!=1:raise ValueError('own_player_ambiguous')
  owner=owners.pop();native=inspect_player(memory.read,owner);binding=resolve_registry(native,registry,session)
  if not binding['personality_binding_verified'] or binding['commander_id']!=session['scenario']['commander_id']:raise ValueError('commander_binding_unverified')
  script=memory.u32(memory.u32(owner+0x8c)+0x10);default=memory.u32(owner+0xac)
  def team_owner(t):return memory.u32(memory.u32(t+4)+8)
  if script==default or team_owner(script)!=owner or team_owner(default)!=owner:raise ValueError('native_team_pool_identity')
  units=[]
  for candidate in snapshot['candidates']:
   if int(candidate['type_hash'],0) not in [0x19ab11af]:continue
   thing=int(candidate['address'],0);update=int(candidate['ai_address'],0)
   try:
    hp=memory.f32(memory.u32(thing+0x33c)+4);team=memory.u32(thing+0x414)
    status84=memory.u32(thing+0x84)
    valid=hp>0 and math.isfinite(hp) and not status84&(0x20000000|0x80000) and memory.u32(update+8)==thing and team_owner(team)==owner and team!=script
    candidate.update(hp=hp,status84=hex(status84),mobility_restriction_mask='0x20080000',team=hex(team),command_source=memory.u32(update+0x50),eligible=valid)
   except Exception as error:candidate.update(eligible=False,error=str(error))
   units.append(candidate)
  if object_id is not None:
   selected=[x for x in units if x['object_id']==object_id and x['eligible']]
   if len(selected)!=1:raise ValueError('selected_unit_not_eligible')
  else:selected=[x for x in units if x['eligible']][:1]
  if session_path.read_bytes()!=raw:raise ValueError('session_changed')
  thread=window_thread(session['pid']);logic=memory.u32(0xcd8ce4)
  result=dict(status='read_only_ready' if selected else 'no_eligible_unit',session_id=session['session_id'],pid=session['pid'],commander_id=binding['commander_id'],player_id=3,frame=memory.u32(logic+0x50),paused=memory.u32(logic+0x15c),owner=hex(owner),ai=native['ai_player'],personality=native['personality_wrapper'],personality_id=native['instance_id'],player_template=native['player_template'],logic=hex(logic),window_thread=thread,script_team=hex(script),default_team=hex(default),eligible_count=sum(x['eligible'] for x in units),units=units,selected=selected[0] if selected else None,restore_semantics='native_common_pool_not_original_squad',mutations=False)
  return result,session,raw,package,registry_path,hashlib.sha256(registry_path.read_bytes()).hexdigest(),memory
 except:memory.close();raise

def assessment(report):
 events=report.get('events',[]);owner=report['preflight']['owner'];native=report.get('native',{})
 manager=int(report['preflight']['ai'],0)+0x104
 issued=native.get('issued_frame',0);returned=native.get('returned_frame',0)
 leased=[x for x in events if x['kind']==3 and issued<=x['frame']<=returned]
 interference=[x for x in events if x['tag']==0 and x['kind'] in [10,12,14,16,18] and issued<=x['frame']<returned]
 checks=dict(stopped=native.get('phase')==3,hooks_restored=native.get('restore_mask')==255,no_active_callbacks=native.get('active')==0,no_native_error=native.get('error')==0,one_detach=native.get('detach_calls')==1,one_move=native.get('move_calls')==1,one_return=native.get('return_calls')==1,arrival=native.get('arrival_samples',0)>=3,owner_preserved=bool(events) and all(hex(x['owner'])==owner for x in events),remove_observed=sum(x['kind']==18 and x['tag']==1 and x['arg']==manager and x['caller']==0x838877 for x in events)==1 and sum(x['kind']==19 and x['tag']==1 for x in events)==1,add_observed=sum(x['kind']==16 and x['tag']==3 and x['arg']==manager and x['caller']==0x83885b for x in events)==1 and sum(x['kind']==17 and x['tag']==3 for x in events)==1,no_observed_lease_override=not interference,leased_team_preserved=bool(leased) and all(x['team']==int(report['preflight']['script_team'],0) for x in leased),return_pool_verified=bool(native.get('return_verified')),no_lifecycle_error=native.get('lifecycle_fail')==0,no_log_overflow=native.get('overflow')==0)
 post=[x for x in events if x['frame']>native.get('returned_frame',0)]
 native_recruited=any(x['kind']==3 and x['team']!=int(report['preflight']['default_team'],0) for x in post) or any(x['tag']==0 and x['kind'] in [10,12] for x in post)
 request=report.get('request',{});target=request.get('target',[]);native_target=native.get('target',[])
 thread=report['preflight']['window_thread'];sdk_events=[x for x in events if x['tag'] in [1,2,3,4]]
 checks['session_binding']=report.get('session_id')==report['preflight'].get('session_id')==native.get('session_id') and report['preflight'].get('commander_id')==native.get('commander_id')
 checks['command_binding']=request.get('command_id')==native.get('command_id') and request.get('task_id')==native.get('task_id') and request.get('seq')==native.get('seq')
 checks['thread_verified']=native.get('callback_thread')==thread and bool(sdk_events) and all(x['thread']==thread for x in sdk_events)
 checks['one_move_hook_chain']=sum(x['kind']==10 and x['tag']==2 for x in events)==1 and sum(x['kind']==11 and x['tag']==2 for x in events)==1
 checks['frame_window']=issued>0 and returned>=issued and returned-issued<=request.get('lease_frames',0)+5
 target_ok=len(target)==3 and len(native_target)==3 and all(math.isfinite(x) for x in target+native_target) and all(abs(a-b)<0.001 for a,b in zip(target,native_target))
 checks['target_binding']=target_ok
 return_seqs=[x['seq'] for x in events if x['kind']==14 and x['tag']==3]
 arrival=[x for x in events if target_ok and x['kind']==3 and issued<=x['frame']<=returned and (not return_seqs or x['seq']<min(return_seqs)) and math.hypot(x['x']-target[0],x['y']-target[1])<=request.get('arrival_radius',0)]
 checks['arrival_independent']=len(arrival)>=3 and len(arrival)==native.get('arrival_samples')
 stops=[x for x in events if x['kind']==23 and x['arg']==1 and x['caller']==0x787791 and issued<=x['frame']<=returned]
 gates=[x for x in events if x['kind']==24 and x['frame']==native.get('move_issued_frame') and not x['path'] and not (x['sm_flags']&0xffff) and x['source']==1]
 checks['stop_actual_hook_pair']=sum(x['kind']==22 and x['arg']==1 and x['caller']==0x787791 and issued<=x['frame']<=returned for x in events)==1 and len(stops)==1
 checks['one_normal_stop']=native.get('stop_calls')==1 and native.get('private_stop_calls')==1 and len(stops)==1 and sum(x['kind']==20 and x['tag']==4 and x['arg']==1 for x in events)==1 and sum(x['kind']==21 and x['tag']==4 for x in events)==1
 checks['deferred_stop_before_move']=len(gates)==1 and len(stops)==1 and gates[0]['frame']>stops[0]['frame'] and gates[0]['seq']>stops[0]['seq'] and native.get('stable_samples',0)>=3 and native.get('stop_gate_samples',0)>=3
 clean=[x for x in events if x['kind']==3 and len(stops)==1 and stops[0]['frame']<x['frame']<native.get('move_issued_frame',0) and not x['path'] and not(x['sm_flags']&0xffff) and x['source']==1]
 checks['clean_stop_samples']=len({x['frame'] for x in clean})>=2
 normal_in=[x for x in events if x['kind']==10 and x['tag']==2]
 normal_out=[x for x in events if x['kind']==11 and x['tag']==2]
 facade_in=[x for x in events if x['kind']==30 and x['tag']==2]
 facade_out=[x for x in events if x['kind']==31 and x['tag']==2]
 checks['normal_move_input_chain']=len(normal_in)==len(normal_out)==len(facade_in)==len(facade_out)==1 and all(x['arg']==1 and len(x.get('command_xyz',[]))==3 and all(abs(a-b)<.001 for a,b in zip(x['command_xyz'],target)) for x in normal_in+normal_out+facade_in+facade_out) and normal_in[0]['caller']==0x6d3b7d and normal_in[0]['argument_path']==0 and normal_in[0]['argument_limit']>3e38 and facade_in[0]['seq']<normal_in[0]['seq']<normal_out[0]['seq']<facade_out[0]['seq']
 checks['distinct_arrival_frames']=len({x['frame'] for x in arrival})>=3
 checks['original_expiry_preserved']=not request.get('expires_frame') or native.get('expires_frame')==request['expires_frame'] and returned<=request['expires_frame']
 checks['monotonic_frame_log']=all(a['frame']<=b['frame'] for a,b in zip(events,events[1:]))
 clean_gate=[x for x in events if x['kind'] in (3,24) and len(stops)==1 and stops[0]['seq']<x['seq']<=gates[0]['seq'] and x['source']==1 and not x['path'] and not(x['sm_flags']&0xffff)] if len(gates)==1 else []
 by_frame={x['frame']:x for x in clean_gate};tail=[by_frame[f] for f in sorted(by_frame)[-3:]]
 checks['raw_stable_stop']=len(tail)==3 and all(math.hypot(a['x']-b['x'],a['y']-b['y'])<=1 for a,b in zip(tail,tail[1:]))
 return dict(status='stop_move_and_return_primitive_verified' if all(checks.values()) else 'not_passed',checks=checks,native_recruitment_observed=native_recruited,raid_verified=False,attack_verified=False,combined_arms_verified=False,note='Arrival and normal pool return are primitive evidence; native recruitment and all tactical goals require separate assessment. No exact original squad restoration claimed.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--object-id',type=int);ap.add_argument('--execute',action='store_true');ap.add_argument('--readiness',action='store_true');ap.add_argument('--natural',type=Path);ap.add_argument('--dx',type=float,default=80);ap.add_argument('--dy',type=float,default=0);ap.add_argument('--lease-frames',type=int,default=180);ap.add_argument('--post-frames',type=int,default=90)
 ap.add_argument('--known-point-report',type=Path);ap.add_argument('--known-point-object-id',type=int);ap.add_argument('--expires-frame',type=int,default=0);ap.add_argument('--output',type=Path);ap.add_argument('--target-x',type=float);ap.add_argument('--target-y',type=float);ap.add_argument('--command-id',default=None);ap.add_argument('--task-id',default=None);ap.add_argument('--seq',type=int,required=False);args=ap.parse_args();pre,session,raw,package,registry_path,registry_digest,memory=readiness(args.session,args.object_id)
 if not args.execute:
  durable(HERE/'readiness.json',pre);print(json.dumps(pre,ensure_ascii=False));memory.close();return
 if not pre['selected']:raise ValueError('no_eligible_unit')
 if not args.known_point_report:raise ValueError('calibration_requires_actual_own_history_point')
 point=known_point(args.known_point_report,args.known_point_object_id,pre,session,memory)
 if args.target_x is not None or args.target_y is not None:raise ValueError('known_point_cannot_override_coordinates')
 args.target_x,args.target_y=point['xyz'][:2]
 if (args.target_x is None)!=(args.target_y is None):raise ValueError('both_target_coordinates_required')
 if args.target_x is not None:args.dx=args.target_x-pre['selected']['xyz'][0];args.dy=args.target_y-pre['selected']['xyz'][1]
 if not args.natural:raise ValueError('natural_thread_evidence_required')
 obs=json.loads(args.natural.read_text(encoding='utf-8-sig'));compatible_natural_calls(obs,session['pid'])
 if obs['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')
 if not all(math.isfinite(x) for x in [args.dx,args.dy]) or not 20<=math.hypot(args.dx,args.dy)<=600 or not 30<=args.lease_frames<=450 or not 30<=args.post_frames<=180:raise ValueError('lease_bounds')
 if args.expires_frame and not pre['frame']+args.lease_frames+2<=args.expires_frame<=pre['frame']+900:raise ValueError('native_original_expiry_bounds')
 layout=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
 if layout!={'event':c.sizeof(Event),'tactical':c.sizeof(Tactical),'events':Tactical.events.offset,'unused1':0,'unused2':0}:raise ValueError('layout_mismatch')
 command_id=str(uuid.UUID(args.command_id)) if args.command_id else str(uuid.uuid4());task_id=str(uuid.UUID(args.task_id)) if args.task_id else str(uuid.uuid4());token=int.from_bytes(os.urandom(4),'little') or 1;seq=args.seq if args.seq is not None else int(time.monotonic()*1000)&0xffffffff
 run=Path(session['run_directory']);target=args.output or run/('tactical-stop-move-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(token)+'.json');report=dict(session_id=session['session_id'],executable_sha256=EXPECTED,package_sha256=session['mod_sha256'],preflight=pre,status='preflight',events=[],native={},request=dict(command_id=command_id,task_id=task_id,seq=seq,token=token,dx=args.dx,dy=args.dy,lease_frames=args.lease_frames,post_frames=args.post_frames,target=[pre['selected']['xyz'][0]+args.dx,pre['selected']['xyz'][1]+args.dy,point['xyz'][2]],arrival_radius=15,object_id=pre['selected']['object_id'],expires_frame=args.expires_frame))
 report.update(known_point=point,native_source_sha256=hashlib.sha256((HERE/'lease.cpp').read_bytes()).hexdigest(),native_shared_sha256=hashlib.sha256((HERE/'shared.h').read_bytes()).hexdigest(),experimental_scope='calibration_ground_conscript_true_observed_height',native_binary_sha256=hashlib.sha256((HERE/'bin/TacticalGroundNormalTerrainAux.dll').read_bytes()).hexdigest(),native_host_sha256=hashlib.sha256((HERE/'bin/tactical_host.exe').read_bytes()).hexdigest(),wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());
 if target.exists():raise ValueError('existing_report_requires_recovery')
 durable(target,report);handle=None;view=None;host=None;shared=None;last=0
 try:
  k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
  handle=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Tactical),'Local\\RA3TacticalGroundNormalTerrainAux_'+str(session['pid'])+'_'+str(token))
  if not handle or c.get_last_error()==183:raise ValueError('tactical_lease_already_used_in_process')
  view=k.MapViewOfFile(handle,0xf001f,0,0,c.sizeof(Tactical))
  if not view:raise c.WinError(c.get_last_error())
  c.memset(view,0,c.sizeof(Tactical));shared=Tactical.from_address(view);s=shared;s.magic=0x47544e31;s.version=1;s.command[:]=words(command_id);s.task[:]=words(task_id);s.token=token;s.seq=seq;s.pid=session['pid'];s.thread=pre['window_thread'];s.owner=int(pre['owner'],0);s.ai=int(pre['ai'],0);s.personality=int(pre['personality'],0);s.personality_id=int(pre['personality_id'],0);s.player_template=int(pre['player_template'],0);s.logic=int(pre['logic'],0);s.script_team=int(pre['script_team'],0);s.default_team=int(pre['default_team'],0);s.unit=int(pre['selected']['address'],0);s.update=int(pre['selected']['ai_address'],0);s.object_id=pre['selected']['object_id'];s.type_hash=int(pre['selected']['type_hash'],0);s.lease_frames=args.lease_frames;s.post_frames=args.post_frames;s.expires_frame=args.expires_frame;s.session[:]=words(session['session_id']);s.commander[:]=words(pre['commander_id']);s.target[:]=[pre['selected']['xyz'][0]+args.dx,pre['selected']['xyz'][1]+args.dy,point['xyz'][2]]
  times=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(memory.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())
  s.start_low=times[0].dwLowDateTime;s.start_high=times[0].dwHighDateTime
  if args.session.read_bytes()!=raw or hashlib.sha256(package.read_bytes()).hexdigest()!=session['mod_sha256'] or hashlib.sha256(registry_path.read_bytes()).hexdigest()!=registry_digest:raise ValueError('binding_changed_before_dispatch')
  report['status']='dispatch_pending';durable(target,report)
  with target.with_suffix('.host.log').open('w',encoding='utf-8') as log:
   host=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=log,stderr=log);deadline=time.monotonic()+185
   while time.monotonic()<deadline:
    if args.session.read_bytes()!=raw or hashlib.sha256(registry_path.read_bytes()).hexdigest()!=registry_digest:shared.stop_requested=1
    count=min(shared.count,4096)
    while last<count:
     event=shared.events[last]
     if event.seq!=last+1:break
     report['events'].append(event_record(event));last+=1
    report['native']={x:getattr(shared,x) for x in RESULT+'stop_calls private_stop_calls private_stop_frame move_issued_frame stable_samples stop_gate_samples last_sample_frame last_arrival_frame'.split()+['phase','active','count']};report['native'].update(lease_frames=shared.lease_frames,expires_frame=shared.expires_frame);report['native']['target']=list(shared.target);report['native'].update(session_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.session))),commander_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.commander))),command_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.command))),task_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.task))),seq=shared.seq);report['status']='finished' if shared.phase in [3,4] else 'running';durable(target,report)
    if host.poll() is not None:break
    time.sleep(.1)
   if host.poll() is None:shared.stop_requested=1;report['status']='unknown_pending_native_return'
   capture_shared(report,shared)
   if host.poll() is None:report['status']='unknown_pending_native_return'
   report['host_exit']=host.poll();report['assessment']=assessment(report);durable(target,report);print(json.dumps(dict(report=str(target),assessment=report['assessment'],native=report['native']),ensure_ascii=False))
 except BaseException as error:
  if shared is not None:
   shared.stop_requested=1;deadline=time.monotonic()+10
   while not capture_shared(report,shared) and host and time.monotonic()<deadline:time.sleep(.1)
  report.update(status='dispatch_failed_native_terminal' if shared is not None and shared.phase in (3,4) else 'unknown_pending_native_return' if host else 'no_dispatch_rejected',error=str(error),host_exit=host.poll() if host else None);durable(target,report);raise
 finally:
  memory.close()
  if view:k.UnmapViewOfFile(view)
  if handle:k.CloseHandle(handle)
if __name__=='__main__':main()
