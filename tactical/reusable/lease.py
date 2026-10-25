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
 _fields_=[(x,U) for x in 'seq kind tag frame tick thread caller team owner source arg'.split()]+[(x,c.c_float) for x in 'x y z'.split()]
HEADER='magic version pid thread owner ai personality personality_id player_template start_low start_high'.split()
TAIL='unit object_id type_hash update logic original_team script_team default_team lease_frames post_frames'.split()
RESULT='error restore_mask callback_thread issued_frame returned_frame move_calls detach_calls return_calls arrival_samples native_move native_attack native_add native_remove owner_fail lifecycle_fail paused_samples overflow return_verified return_pending'.split()
class Tactical(c.Structure):
 _fields_=[(x,U) for x in HEADER]+[('session',U*4),('commander',U*4),('command',U*4),('task',U*4),('token',U),('seq',U)]+[(x,U) for x in TAIL]+[('target',c.c_float*3)]+[(x,L) for x in 'phase stop_requested active count'.split()]+[(x,U) for x in RESULT]+[('events',Event*4096)]
def durable(path,record):
 temp=path.with_suffix(path.suffix+'.tmp')
 with temp.open('w',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
 for attempt in range(25):
  try:temp.replace(path);return
  except PermissionError:
   if attempt==24:raise
   time.sleep(.02)
def words(value):return struct.unpack('<4I',uuid.UUID(str(value)).bytes)
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
   if int(candidate['type_hash'],0) not in [0x19ab11af,0x2c358c61]:continue
   thing=int(candidate['address'],0);update=int(candidate['ai_address'],0)
   try:
    hp=memory.f32(memory.u32(thing+0x33c)+4);team=memory.u32(thing+0x414)
    valid=hp>0 and math.isfinite(hp) and memory.u32(update+8)==thing and team_owner(team)==owner and team!=script
    candidate.update(hp=hp,team=hex(team),command_source=memory.u32(update+0x50),eligible=valid)
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
 checks=dict(stopped=native.get('phase')==3,hooks_restored=native.get('restore_mask')==31,no_active_callbacks=native.get('active')==0,no_native_error=native.get('error')==0,one_detach=native.get('detach_calls')==1,one_move=native.get('move_calls')==1,one_return=native.get('return_calls')==1,arrival=native.get('arrival_samples',0)>=3,owner_preserved=bool(events) and all(hex(x['owner'])==owner for x in events),remove_observed=sum(x['kind']==18 and x['tag']==1 and x['arg']==manager and x['caller']==0x838877 for x in events)==1 and sum(x['kind']==19 and x['tag']==1 for x in events)==1,add_observed=sum(x['kind']==16 and x['tag']==3 and x['arg']==manager and x['caller']==0x83885b for x in events)==1 and sum(x['kind']==17 and x['tag']==3 for x in events)==1,no_observed_lease_override=not interference,leased_team_preserved=bool(leased) and all(x['team']==int(report['preflight']['script_team'],0) for x in leased),return_pool_verified=bool(native.get('return_verified')),no_lifecycle_error=native.get('lifecycle_fail')==0,no_log_overflow=native.get('overflow')==0)
 post=[x for x in events if x['frame']>native.get('returned_frame',0)]
 native_recruited=any(x['kind']==3 and x['team']!=int(report['preflight']['default_team'],0) for x in post) or any(x['tag']==0 and x['kind'] in [10,12] for x in post)
 request=report.get('request',{});target=request.get('target',[]);native_target=native.get('target',[])
 thread=report['preflight']['window_thread'];sdk_events=[x for x in events if x['tag'] in [1,2,3]]
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
 return dict(status='move_and_return_primitive_verified' if all(checks.values()) else 'not_passed',checks=checks,native_recruitment_observed=native_recruited,raid_verified=False,attack_verified=False,combined_arms_verified=False,note='Arrival and normal pool return are primitive evidence; native recruitment and all tactical goals require separate assessment. No exact original squad restoration claimed.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--object-id',type=int);ap.add_argument('--execute',action='store_true');ap.add_argument('--readiness',action='store_true');ap.add_argument('--natural',type=Path);ap.add_argument('--dx',type=float,default=80);ap.add_argument('--dy',type=float,default=0);ap.add_argument('--lease-frames',type=int,default=180);ap.add_argument('--post-frames',type=int,default=90)
 ap.add_argument('--output',type=Path);ap.add_argument('--target-x',type=float);ap.add_argument('--target-y',type=float);ap.add_argument('--command-id',default=None);ap.add_argument('--task-id',default=None);ap.add_argument('--seq',type=int,required=False);args=ap.parse_args();pre,session,raw,package,registry_path,registry_digest,memory=readiness(args.session,args.object_id)
 if not args.execute:
  durable(HERE/'readiness.json',pre);print(json.dumps(pre,ensure_ascii=False));memory.close();return
 if not pre['selected']:raise ValueError('no_eligible_unit')
 if (args.target_x is None)!=(args.target_y is None):raise ValueError('both_target_coordinates_required')
 if args.target_x is not None:args.dx=args.target_x-pre['selected']['xyz'][0];args.dy=args.target_y-pre['selected']['xyz'][1]
 if not args.natural:raise ValueError('natural_thread_evidence_required')
 obs=json.loads(args.natural.read_text(encoding='utf-8-sig'));compatible_natural_calls(obs,session['pid'])
 if obs['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')
 if not all(math.isfinite(x) for x in [args.dx,args.dy]) or not 20<=math.hypot(args.dx,args.dy)<=120 or not 30<=args.lease_frames<=180 or not 30<=args.post_frames<=180:raise ValueError('lease_bounds')
 layout=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
 if layout!={'event':c.sizeof(Event),'tactical':c.sizeof(Tactical),'events':Tactical.events.offset,'unused1':0,'unused2':0}:raise ValueError('layout_mismatch')
 command_id=str(uuid.UUID(args.command_id)) if args.command_id else str(uuid.uuid4());task_id=str(uuid.UUID(args.task_id)) if args.task_id else str(uuid.uuid4());token=int.from_bytes(os.urandom(4),'little') or 1;seq=args.seq if args.seq is not None else int(time.monotonic()*1000)&0xffffffff
 run=Path(session['run_directory']);target=args.output or run/('tactical-reusable-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(token)+'.json');report=dict(session_id=session['session_id'],executable_sha256=EXPECTED,package_sha256=session['mod_sha256'],preflight=pre,status='preflight',events=[],native={},request=dict(command_id=command_id,task_id=task_id,seq=seq,token=token,dx=args.dx,dy=args.dy,lease_frames=args.lease_frames,post_frames=args.post_frames,target=[pre['selected']['xyz'][0]+args.dx,pre['selected']['xyz'][1]+args.dy,pre['selected']['xyz'][2]],arrival_radius=15))
 durable(target,report);handle=None;view=None;host=None;shared=None;last=0
 try:
  k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
  handle=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Tactical),'Local\\RA3TacticalReusable_'+str(session['pid'])+'_'+str(token))
  if not handle or c.get_last_error()==183:raise ValueError('tactical_lease_already_used_in_process')
  view=k.MapViewOfFile(handle,0xf001f,0,0,c.sizeof(Tactical))
  if not view:raise c.WinError(c.get_last_error())
  c.memset(view,0,c.sizeof(Tactical));shared=Tactical.from_address(view);s=shared;s.magic=0x54414331;s.version=2;s.command[:]=words(command_id);s.task[:]=words(task_id);s.token=token;s.seq=seq;s.pid=session['pid'];s.thread=pre['window_thread'];s.owner=int(pre['owner'],0);s.ai=int(pre['ai'],0);s.personality=int(pre['personality'],0);s.personality_id=int(pre['personality_id'],0);s.player_template=int(pre['player_template'],0);s.logic=int(pre['logic'],0);s.script_team=int(pre['script_team'],0);s.default_team=int(pre['default_team'],0);s.unit=int(pre['selected']['address'],0);s.update=int(pre['selected']['ai_address'],0);s.object_id=pre['selected']['object_id'];s.type_hash=int(pre['selected']['type_hash'],0);s.lease_frames=args.lease_frames;s.post_frames=args.post_frames;s.session[:]=words(session['session_id']);s.commander[:]=words(pre['commander_id']);s.target[:]=[pre['selected']['xyz'][0]+args.dx,pre['selected']['xyz'][1]+args.dy,pre['selected']['xyz'][2]]
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
     report['events'].append({name:getattr(event,name) for name,_ in Event._fields_});last+=1
    report['native']={x:getattr(shared,x) for x in RESULT+['phase','active','count']};report['native']['target']=list(shared.target);report['native'].update(session_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.session))),commander_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.commander))),command_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.command))),task_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.task))),seq=shared.seq);report['status']='finished' if shared.phase in [3,4] else 'running';durable(target,report)
    if host.poll() is not None:break
    time.sleep(.1)
   if host.poll() is None:shared.stop_requested=1;report['status']='unknown_pending_native_return'
   report['host_exit']=host.poll();report['assessment']=assessment(report);durable(target,report);print(json.dumps(dict(report=str(target),assessment=report['assessment'],native=report['native']),ensure_ascii=False))
 except BaseException as error:
  if shared is not None:shared.stop_requested=1
  report.update(status='unknown' if host else 'no_dispatch_rejected',error=str(error));durable(target,report);raise
 finally:
  memory.close()
  if view:k.UnmapViewOfFile(view)
  if handle:k.CloseHandle(handle)
if __name__=='__main__':main()
