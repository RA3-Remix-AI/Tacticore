"""Two-role staged advance, diagnostic only. Parent alone executes --execute."""
import argparse,ctypes as c,hashlib,json,math,os,struct,subprocess,sys,time,uuid
from pathlib import Path
import importlib.util
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
spec=importlib.util.spec_from_file_location('formation_read_backend',HERE.parent/'reusable/lease.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
U=c.c_uint32;L=c.c_int32
class Unit(c.Structure):
 _fields_=[(x,U) for x in 'thing id hash update original_team'.split()]+[(x,c.c_float*3) for x in 'initial goal hold'.split()]+[(x,U) for x in 'detach_calls move_calls return_calls arrivals returned native_move native_attack native_add native_remove'.split()]
class Event(c.Structure):
 _fields_=[(x,U) for x in 'seq kind tag stage frame tick thread caller unit_id team owner source arg'.split()]+[(x,c.c_float) for x in 'x y z'.split()]
RESULT='error restore_mask callback_thread issued_frame returned_frame stage stage_frame goal_samples support_hold_samples front_arrival_frame support_issued_frame overflow paused_samples return_pending'.split()
class Tactical(c.Structure):
 _fields_=[(x,U) for x in 'magic version pid thread owner ai personality personality_id player_template start_low start_high'.split()]+[(x,U*4) for x in ['session','commander','command','task']]+[(x,U) for x in 'token seq logic script_team default_team lease_frames post_frames'.split()]+[('units',Unit*2)]+[(x,L) for x in 'phase stop_requested active count'.split()]+[(x,U) for x in RESULT]+[('min_spacing',c.c_float),('max_spacing',c.c_float),('events',Event*4096)]
def unit_view(u):return {x:list(getattr(u,x)) if x in ['initial','goal','hold'] else getattr(u,x) for x,_ in Unit._fields_}
def assessment(r):
 n=r.get('native',{});units=r.get('units',[]);events=r.get('events',[]);pre=r['preflight'];request=r['request'];thread=pre['window_thread'];owner=int(pre['owner'],0);manager=int(pre['ai'],0)+0x104;checks={}
 checks.update(clean_stop=n.get('phase')==3 and n.get('error')==0 and n.get('restore_mask')==31 and n.get('active')==0,roles=len(units)==2 and units[0]['hash']==0x19ab11af and units[1]['hash']==0x2c358c61 and units[0]['id']!=units[1]['id'],stage_goal=n.get('stage')==3 and n.get('goal_samples',0)>=3,stage_order=0<n.get('issued_frame',0)<=n.get('front_arrival_frame',0)==n.get('support_issued_frame',0)<=n.get('returned_frame',0),bounded=n.get('returned_frame',0)-n.get('issued_frame',0)<=request['lease_frames']+5,thread=n.get('callback_thread')==thread and all(e['thread']==thread for e in events),binding=n.get('session_id')==r['session_id']==pre['session_id'] and n.get('command_id')==request['command_id'] and n.get('task_id')==request['task_id'] and n.get('commander_id')==pre.get('commander_id') and n.get('seq')==request.get('seq'),no_overflow=n.get('overflow')==0)
 if len(units)==2:
  checks['bounded_commands']=units[0]['move_calls']==1 and units[1]['move_calls']==2
  for i,u in enumerate(units):
   ev=[e for e in events if e['unit_id']==u['id']];checks['unit_'+str(i)+'_returned']=u['detach_calls']==u['return_calls']==u['returned']==1 and any(e['kind']==18 and e['tag']==1 and e['arg']==manager and e['caller']==0x838877 for e in ev) and any(e['kind']==16 and e['tag']==3 and e['arg']==manager and e['caller']==0x83885b for e in ev)
   checks['unit_'+str(i)+'_owner']=bool(ev) and all(e['owner']==owner for e in ev)
   checks['unit_'+str(i)+'_no_override']=not any(e['tag']==0 and e['kind'] in [10,12,14,16,18] and n['issued_frame']<=e['frame']<n['returned_frame'] for e in ev)
   checks['unit_'+str(i)+'_move_chain']=sum(e['kind']==10 and e['tag']==2 for e in ev)==u['move_calls'] and sum(e['kind']==11 and e['tag']==2 for e in ev)==u['move_calls']
  # Pair consecutive same-tick timer samples; never join positions from different frames.
  pairs=[]
  for i,e in enumerate(events[:-1]):
   f=events[i+1]
   if e['kind']==f['kind']==3 and e['stage']==f['stage'] and n.get('issued_frame',0)<=e['frame']<=n.get('returned_frame',0) and e['unit_id']==units[0]['id'] and f['unit_id']==units[1]['id'] and e['tick']==f['tick'] and e['frame']==f['frame']:pairs.append((e,f))
  good=[];holds=[];ready=[];run=0;max_run=0;run_ready=0;max_ready=0
  for front,support in pairs:
   held=front['stage']==1 and front['frame']<=n.get('support_issued_frame',0) and math.hypot(support['x']-units[1]['hold'][0],support['y']-units[1]['hold'][1])<=15
   if held:holds.append(front['frame'])
   df=math.hypot(front['x']-units[0]['goal'][0],front['y']-units[0]['goal'][1]);ds=math.hypot(support['x']-units[1]['goal'][0],support['y']-units[1]['goal'][1]);spacing=math.hypot(front['x']-support['x'],front['y']-support['y']);v=[units[0]['goal'][j]-units[0]['initial'][j] for j in [0,1]];forward=(front['x']-support['x'])*v[0]+(front['y']-support['y'])*v[1]
   if held and df<=15:run_ready+=1;max_ready=max(max_ready,run_ready)
   else:run_ready=0
   if front['stage']==2 and front['frame']>=n.get('support_issued_frame',0) and df<=20 and ds<=15 and request['min_spacing']<=spacing<=request['max_spacing'] and forward>0:good.append(dict(frame=front['frame'],spacing=spacing,front_distance=df,support_distance=ds));run+=1;max_run=max(max_run,run)
   else:run=0
  checks['support_held_before_release']=len(holds)>=3 and max_ready>=3
  checks['independent_pair_geometry']=len(good)>=3 and max_run>=3
  goals=[request.get('front_goal'),request.get('support_goal')]
  checks['requested_goals_bound']=all(isinstance(g,list) and len(g)==3 and len(u['goal'])==3 and all(math.isfinite(a) and math.isfinite(b) and abs(a-b)<.001 for a,b in zip(g,u['goal'])) for g,u in zip(goals,units))
 else:good=[]
 return dict(status='two_role_staged_advance_primitive_verified' if all(checks.values()) else 'not_passed',checks=checks,paired_geometry=good,raid_verified=False,attack_verified=False,combined_arms_verified=False,note='Two role staged movement only; role/task capability is still subject to host review.')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--natural',type=Path);ap.add_argument('--execute',action='store_true');ap.add_argument('--front-id',type=int,required=True);ap.add_argument('--support-id',type=int,required=True);ap.add_argument('--dx',type=float,default=80);ap.add_argument('--dy',type=float,default=0);ap.add_argument('--rear-spacing',type=float,default=60);ap.add_argument('--seq',type=int,required=True);ap.add_argument('--command-id');ap.add_argument('--task-id');ap.add_argument('--output',type=Path)
 args=ap.parse_args();pre,session,raw,package,registry_path,digest,m=b.readiness(args.session,args.front_id);candidates={u['object_id']:u for u in pre['units'] if u['eligible']};front=candidates[args.front_id];support=candidates.get(args.support_id)
 if int(front['type_hash'],0)!=0x19ab11af or not support or int(support['type_hash'],0)!=0x2c358c61 or args.front_id==args.support_id:raise ValueError('requires_distinct_conscript_front_flak_support')
 length=math.hypot(args.dx,args.dy)
 if not 40<=length<=100 or not 40<=args.rear_spacing<=100:raise ValueError('staged_move_bounds')
 fg=[front['xyz'][0]+args.dx,front['xyz'][1]+args.dy,front['xyz'][2]];sg=[fg[0]-args.dx/length*args.rear_spacing,fg[1]-args.dy/length*args.rear_spacing,support['xyz'][2]]
 for u,g in [(front,fg),(support,sg)]:
  if not 20<=math.hypot(u['xyz'][0]-g[0],u['xyz'][1]-g[1])<=120:raise ValueError('role_target_bounds')
 if not args.execute:print(json.dumps(dict(preflight=pre,front_goal=fg,support_goal=sg)));m.close();return
 if not args.natural:raise ValueError('natural_thread_evidence_required')
 obs=json.loads(args.natural.read_text(encoding='utf-8-sig'));b.compatible_natural_calls(obs,session['pid'])
 if obs['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')
 layout=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
 if layout!={'event':c.sizeof(Event),'tactical':c.sizeof(Tactical),'events':Tactical.events.offset,'unused1':0,'unused2':0}:raise ValueError('layout_mismatch')
 command=str(uuid.UUID(args.command_id)) if args.command_id else str(uuid.uuid4());task=str(uuid.UUID(args.task_id)) if args.task_id else str(uuid.uuid4());token=int.from_bytes(os.urandom(4),'little') or 1;run=Path(session['run_directory']);path=args.output or run/('tactical-formation-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(token)+'.json');report=dict(session_id=session['session_id'],executable_sha256=b.EXPECTED,package_sha256=session['mod_sha256'],native_binary_sha256=hashlib.sha256((HERE/'bin'/'TacticalFormation.dll').read_bytes()).hexdigest(),native_host_sha256=hashlib.sha256((HERE/'bin/tactical_host.exe').read_bytes()).hexdigest(),wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_source_sha256=hashlib.sha256((HERE/'lease.cpp').read_bytes()).hexdigest(),native_shared_sha256=hashlib.sha256((HERE/'shared.h').read_bytes()).hexdigest(),preflight=pre,request=dict(command_id=command,task_id=task,seq=args.seq,token=token,front_id=args.front_id,support_id=args.support_id,front_goal=fg,support_goal=sg,lease_frames=180,min_spacing=40,max_spacing=100),events=[],units=[],native={},status='preflight');b.durable(path,report)
 k=b.k;w=b.w;k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
 h=None;v=None;shared=None;child=None;last=0
 try:
  h=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Tactical),'Local\\RA3TacticalFormation_'+str(session['pid'])+'_'+str(token))
  if not h or c.get_last_error()==183:raise ValueError('mapping_already_used')
  v=k.MapViewOfFile(h,0xf001f,0,0,c.sizeof(Tactical))
  if not v:raise c.WinError(c.get_last_error())
  c.memset(v,0,c.sizeof(Tactical));shared=Tactical.from_address(v);s=shared;s.magic=0x464f5231;s.version=1;s.pid=session['pid'];s.thread=pre['window_thread'];s.owner=int(pre['owner'],0);s.ai=int(pre['ai'],0);s.personality=int(pre['personality'],0);s.personality_id=int(pre['personality_id'],0);s.player_template=int(pre['player_template'],0);s.logic=int(pre['logic'],0);s.script_team=int(pre['script_team'],0);s.default_team=int(pre['default_team'],0);s.session[:]=b.words(session['session_id']);s.commander[:]=b.words(pre['commander_id']);s.command[:]=b.words(command);s.task[:]=b.words(task);s.token=token;s.seq=args.seq;s.lease_frames=180;s.post_frames=90;s.min_spacing=40;s.max_spacing=100
  for i,(candidate,goal) in enumerate([(front,fg),(support,sg)]):
   u=s.units[i];u.thing=int(candidate['address'],0);u.id=candidate['object_id'];u.hash=int(candidate['type_hash'],0);u.update=int(candidate['ai_address'],0);u.goal[:]=goal
  ft=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(m.handle,*[c.byref(x) for x in ft]):raise c.WinError(c.get_last_error())
  s.start_low=ft[0].dwLowDateTime;s.start_high=ft[0].dwHighDateTime
  if args.session.read_bytes()!=raw or hashlib.sha256(package.read_bytes()).hexdigest()!=session['mod_sha256'] or hashlib.sha256(registry_path.read_bytes()).hexdigest()!=digest:raise ValueError('binding_changed')
  report['status']='dispatch_pending';b.durable(path,report)
  with path.with_suffix('.host.log').open('w',encoding='utf-8') as log:
   child=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=log,stderr=log);deadline=time.monotonic()+185
   while time.monotonic()<deadline:
    if args.session.read_bytes()!=raw:shared.stop_requested=1
    count=min(s.count,4096)
    while last<count:
     e=s.events[last]
     if e.seq!=last+1:break
     report['events'].append({name:getattr(e,name) for name,_ in Event._fields_});last+=1
    report['units']=[unit_view(u) for u in s.units];report['native']={x:getattr(s,x) for x in RESULT+['phase','active','count']};report['native'].update(session_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.session))),command_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.command))),task_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.task))),commander_id=str(uuid.UUID(bytes=struct.pack('<4I',*s.commander))),seq=s.seq);report['status']='finished' if s.phase in [3,4] else 'running';b.durable(path,report)
    if child.poll() is not None:break
    time.sleep(.1)
   if child.poll() is None:s.stop_requested=1;report['status']='unknown_return_pending'
   report['host_exit']=child.poll();report['assessment']=assessment(report);b.durable(path,report);print(json.dumps(dict(report=str(path),assessment=report['assessment'],native=report['native'])))
 except BaseException as error:
  if shared is not None:shared.stop_requested=1
  report.update(status='unknown' if child else 'no_dispatch_rejected',error=str(error));b.durable(path,report);raise
 finally:
  m.close()
  if v:k.UnmapViewOfFile(v)
  if h:k.CloseHandle(h)
if __name__=='__main__':main()
