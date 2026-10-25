"""Independent recon calibration. plan is read-only; root alone executes run.
Uses one own unit and a player-view frontier, never hidden enemy targets.
"""
import argparse,ctypes as c,hashlib,importlib.util,json,math,os,struct,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BRIDGE=ROOT.parent.parent
sys.path[:0]=[str(ROOT),str(BRIDGE/'visibility'),str(BRIDGE/'production')]
from capability import bind_session,load
from native_read import ShroudReader,vision_grid_snapshot
from logic import choose,digest_json,idle_report,assessment,planning_diagnostics
spec=importlib.util.spec_from_file_location('recon_native_backend',ROOT/'lease.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
def write(path,data):path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);b.durable(path,data)
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def region_for(i,grid):
 x=grid.origin[0]+(i%grid.width+.5)/grid.scale;y=grid.origin[1]+(i//grid.width+.5)/grid.scale
 def slug(v):return 'm'+str(-v) if v<0 else str(v)
 return 'region_'+slug(math.floor(x/512))+'_'+slug(math.floor(y/512))
def cell_for(point,grid):
 x=int((point[0]-grid.origin[0])*grid.scale);y=int((point[1]-grid.origin[1])*grid.scale)
 if not 0<=x<grid.width or not 0<=y<grid.height:raise ValueError('Target outside grid')
 return y*grid.width+x

def frontier_candidates(grid,clear,viewer=3):
 # Every candidate is adjacent to this player's own CLEAR cells; no object list.
 candidates=set()
 for i in clear:
  x,y=i%grid.width,i//grid.width
  neighbors=([i-1] if x else [])+([i+1] if x+1<grid.width else [])+([i-grid.width] if y else [])+([i+grid.width] if y+1<grid.height else [])
  candidates.update(n for n in neighbors if n not in clear)
 points=[]
 for i in sorted(candidates):
  x=grid.origin[0]+(i%grid.width+.5)/grid.scale;y=grid.origin[1]+(i//grid.width+.5)/grid.scale
  if grid.query(viewer,[x,y])==0:points.append((region_for(i,grid),[x,y,0.0]))
 return points

def refresh_own_unit(memory,unit,owner,script_team):
 thing=int(unit['address'],0);update=int(unit['ai_address'],0)
 if memory.u32(thing)!=0xc4db60 or memory.u32(thing+0xdc)!=unit['object_id'] or memory.u32(thing+0x418)!=owner or memory.u32(memory.u32(thing+4)+8)!=int(unit['type_hash'],0) or memory.u32(thing+0x374)!=update or memory.u32(update+8)!=thing:raise ValueError('Own unit identity changed')
 team=memory.u32(thing+0x414)
 if not team or team==script_team or memory.u32(memory.u32(team+4)+8)!=owner:raise ValueError('Own unit not in native AI pool')
 result=dict(unit);result['xyz']=list(struct.unpack('<fff',memory.read(thing+0x38,12)));result['hp']=memory.f32(memory.u32(thing+0x33c)+4)
 if not all(math.isfinite(x) for x in result['xyz']) or not math.isfinite(result['hp']) or result['hp']<=0:raise ValueError('Own unit not alive/finite')
 result.update(eligible=True,team=hex(team));return result

def plan_command(a):
 pre,s,raw,package,registry,d,m=b.readiness(a.session)
 try:
  proof,safety=bind_session(m,s,3);grid=ShroudReader(m);frame=m.u32(int(pre['logic'],0)+0x50)
  metrics,clear,frontiers=vision_grid_snapshot(m,grid,3,frame,max_frontiers=12)
  fresh=[]
  for candidate in pre['units']:
   try:fresh.append(refresh_own_unit(m,candidate,int(pre['owner'],0),int(pre['script_team'],0)))
   except (RuntimeError,ValueError):pass
  if getattr(a,'unit_id',None) is not None:fresh=[u for u in fresh if u['object_id']==a.unit_id]
  candidates=frontier_candidates(grid,clear)
  excluded=set(getattr(a,'exclude_region',[]) or [])
  candidates=[(rid,point) for rid,point in candidates if rid not in excluded]
  diagnostics=planning_diagnostics(fresh,candidates);diagnostics['excluded_regions']=sorted(excluded)
  diagnostic_record={'session_id':s['session_id'],'frame':m.u32(int(pre['logic'],0)+0x50),'paused':bool(m.u32(int(pre['logic'],0)+0x15c)),'commands_dispatched':0,'model_eligible':False,**diagnostics}
  diagnostic_path=a.output.with_name(a.output.stem+'-diagnostics.json');write(diagnostic_path,diagnostic_record)
  max_distance=getattr(a,'max_plan_distance',550)
  if not 40<=max_distance<=590:raise ValueError('planning_distance_bounds')
  diagnostics['planning_distance_bound']=[40,max_distance]
  try:unit,region,target,distance=choose(fresh,candidates,max_distance=max_distance)
  except ValueError:
   print(json.dumps({'status':'no_suitable_candidate','diagnostics':str(diagnostic_path),'commands_dispatched':0,**diagnostics}));return
  frame=m.u32(int(pre['logic'],0)+0x50)
  if grid.query(3,target)!=0:raise ValueError('Selected frontier no longer fogged')
  report={'schema_version':1,'kind':'independent_recon_calibration','plan_id':str(uuid.uuid4()),'session_id':s['session_id'],'session_sha256':hashlib.sha256(raw).hexdigest(),'pid':s['pid'],'process_start':s['start_time'],'package_sha256':s['mod_sha256'],'visibility_build_id':proof['build_id'],'commander_id':pre['commander_id'],'player_id':3,'created_frame':frame,'paused':bool(m.u32(int(pre['logic'],0)+0x15c)),'max_age_frames':90,'unit':unit,'target':{'region_id':region,'xyz':target,'grid_cell':cell_for(target,grid),'source':'player3_clear_adjacent_fog_grid_only','initial_distance':distance},'bounds':{'max_distance':600,'lease_frames':450,'post_frames':90,'one_move_only':True},'planning_diagnostics':diagnostics,'planning_vision_metrics':metrics,'native_binary_sha256':{n:file_sha(ROOT/'bin'/n) for n in ['TacticalReconProbe.dll','tactical_host.exe']},'source_sha256':{n:file_sha(ROOT/n) for n in ['lease.cpp','shared.h','host.cpp','lease.py','logic.py','probe.py']},'model_eligible':False,'commands_dispatched':0}
  report['plan_sha256']=digest_json(report);write(a.output,report);print(json.dumps({'plan':str(a.output),'session_id':s['session_id'],'frame':frame,'unit_id':unit['object_id'],'target_region':region,'distance':distance,'commands_dispatched':0}))
 finally:m.close()

def stop_mapping(report_path,pid):
 try:
  report=load(report_path);token=report['request']['token'];k=b.k;w=b.w;k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
  h=k.OpenFileMappingW(0xf001f,False,'Local\\RA3ReconProbe_'+str(pid)+'_'+str(token))
  if not h:return
  v=k.MapViewOfFile(h,0xf001f,0,0,c.sizeof(b.Tactical))
  if v:
   obj=b.Tactical.from_address(v)
   if obj.pid==pid and obj.token==token:obj.stop_requested=1
   k.UnmapViewOfFile(v)
  k.CloseHandle(h)
 except (OSError,KeyError,ValueError):pass

def shared_snapshot(pid,token):
 # Read-only view of actual native state; never uses JSON as a terminal truth.
 k=b.k;w=b.w;k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
 h=k.OpenFileMappingW(4,False,'Local\\RA3ReconProbe_'+str(pid)+'_'+str(token))
 if not h:return None
 v=k.MapViewOfFile(h,4,0,0,c.sizeof(b.Tactical))
 try:
  if not v:return None
  obj=b.Tactical.from_buffer_copy(c.string_at(v,c.sizeof(b.Tactical)))
  if obj.pid!=pid or obj.token!=token:return None
  n={x:getattr(obj,x) for x in b.RESULT+['phase','active','count']};n.update(target=list(obj.target),seq=obj.seq)
  for field in ['session','commander','command','task']:n[field+'_id' if field!='commander' else 'commander_id']=str(uuid.UUID(bytes=struct.pack('<4I',*getattr(obj,field))))
  return n
 finally:
  if v:k.UnmapViewOfFile(v)
  k.CloseHandle(h)

def verify_original_entries(memory):
 signatures={0x6eff70:'568bf18b4e3c8b018b5038ffd2',0x76e690:'837c24040055568bf18b6e08',0x838820:'8b818c00000085c0744f568bb190000000',0x8d8880:'83ec24568b74242c8b4604',0x8cd630:'83ec3453578b7c24408b4704'}
 for va,expected in signatures.items():
  if memory.read(va,len(bytes.fromhex(expected))).hex()!=expected:raise ValueError('Tactical hook entry is not original: '+hex(va))
 return {hex(k):v for k,v in signatures.items()}

def execute_command(a):
 if not a.execute:raise ValueError('run requires --execute; root must serialize native hooks')
 plan=load(a.plan);unsigned={k:v for k,v in plan.items() if k!='plan_sha256'}
 if digest_json(unsigned)!=plan.get('plan_sha256'):raise ValueError('Plan changed')
 pre,s,raw,package,registry,d,m=b.readiness(a.session,plan['unit']['object_id']);native_path=a.output.with_name(a.output.stem+'-native.json');child=None;report={'session_id':s['session_id'],'plan':plan,'samples':[],'native':{},'native_report':{},'error':None,'commands_dispatched':0,'model_eligible':False}
 try:
  if a.output.exists() or native_path.exists():raise ValueError('Use new output path; no native replay')
  with a.output.with_suffix('.reservation').open('x',encoding='utf-8') as f:f.write(plan['plan_id'])
  if s['session_id']!=plan['session_id'] or s['pid']!=plan['pid'] or s['mod_sha256']!=plan['package_sha256'] or hashlib.sha256(raw).hexdigest()!=plan['session_sha256']:raise ValueError('Recon session changed')
  for name,digest in plan['native_binary_sha256'].items():
   if file_sha(ROOT/'bin'/name)!=digest:raise ValueError('Native binary changed')
  for name,digest in plan['source_sha256'].items():
   if file_sha(ROOT/name)!=digest:raise ValueError('Probe source changed')
  if not a.after_report and not a.no_prior_lease:raise ValueError('Need prior report or --no-prior-lease entry-byte proof')
  if a.after_report and a.no_prior_lease:raise ValueError('Choose only one serial-idle proof source')
  report['original_entry_signatures']=verify_original_entries(m)
  report['serial_predecessors']=[]
  for path in (a.after_report or []):idle_report(load(path),s['session_id']);report['serial_predecessors'].append({'path':str(path.resolve()),'sha256':file_sha(path)})
  proof,safety=bind_session(m,s,3)
  if proof['build_id']!=plan['visibility_build_id']:raise ValueError('Visibility capability changed')
  logic=int(pre['logic'],0);frame=m.u32(logic+0x50)
  if m.u32(logic+0x15c):raise ValueError('Game paused; resume before run')
  if not plan['created_frame']<=frame<=plan['created_frame']+plan['max_age_frames']:raise ValueError('Plan stale; plan again')
  unit=refresh_own_unit(m,pre['selected'],int(pre['owner'],0),int(pre['script_team'],0));pre['selected']=unit;thing=int(unit['address'],0);initial=unit['xyz'];target=plan['target']['xyz']
  if thing!=int(plan['unit']['address'],0) or unit['type_hash']!=plan['unit']['type_hash']:raise ValueError('Own unit identity differs from plan')
  distance=math.hypot(initial[0]-target[0],initial[1]-target[1])
  if not 20<=distance<=600 or abs(initial[2]-target[2])>2:raise ValueError('Recon range/height no longer valid')
  grid=ShroudReader(m);metrics,baseline,frontiers=vision_grid_snapshot(m,grid,3,frame)
  if grid.query(3,target)!=0 or cell_for(target,grid)!=plan['target']['grid_cell']:raise ValueError('Target already revealed or grid changed')
  # Reconfirm target cell remains adjacent to own CLEAR terrain, not enemy truth.
  cell=plan['target']['grid_cell'];x,y=cell%grid.width,cell//grid.width;neighbors=([cell-1] if x else [])+([cell+1] if x+1<grid.width else [])+([cell-grid.width] if y else [])+([cell+grid.width] if y+1<grid.height else [])
  if not any(n in baseline for n in neighbors):raise ValueError('Target no longer a player-view frontier')
  report['original_entry_signatures_before_dispatch']=verify_original_entries(m)
  obs=load(a.natural);b.compatible_natural_calls(obs,s['pid'])
  if obs['window_thread']!=pre['window_thread']:raise ValueError('Natural thread mismatch')
  report.update(status='prepared',preflight=pre,proof=proof,baseline={'frame':frame,'target_terrain_status':0,'clear_cells':sorted(baseline),'vision_metrics':metrics},request={'command_id':str(uuid.uuid4()),'task_id':str(uuid.uuid4()),'seq':int(time.monotonic()*1000)&0x7fffffff,'target':target})
  write(a.output,report)
  args=[sys.executable,str(ROOT/'lease.py'),'--session',str(a.session),'--execute','--object-id',str(unit['object_id']),'--target-x',str(target[0]),'--target-y',str(target[1]),'--lease-frames','450','--post-frames','90','--natural',str(a.natural),'--command-id',report['request']['command_id'],'--task-id',report['request']['task_id'],'--seq',str(report['request']['seq']),'--output',str(native_path)]
  with native_path.with_suffix('.driver.log').open('w',encoding='utf-8') as log:
   child=subprocess.Popen(args,stdout=log,stderr=log);report['commands_dispatched']=1;deadline=time.monotonic()+190;last_frame=-1;native_token=None
   while child.poll() is None and time.monotonic()<deadline:
    if a.session.read_bytes()!=raw:raise ValueError('Session changed during recon')
    frame=m.u32(logic+0x50)
    if frame<report['baseline']['frame'] or m.u32(0xcd8ce4)!=logic:raise ValueError('Match reset during recon')
    if frame!=last_frame:
     identity=(m.u32(thing)==0xc4db60 and m.u32(thing+0xdc)==unit['object_id'] and m.u32(thing+0x418)==int(pre['owner'],0) and m.u32(m.u32(thing+4)+8)==int(unit['type_hash'],0))
     if not identity:raise ValueError('Own recon unit identity changed')
     xyz=list(struct.unpack('<fff',m.read(thing+0x38,12)));current=ShroudReader(m);v,clear,_=vision_grid_snapshot(m,current,3,frame);new=clear-baseline
     if current.impl!=grid.impl or current.cells!=grid.cells:raise ValueError('Shroud grid changed')
     sample={'frame':frame,'own_identity_verified':True,'own_xyz':xyz,'distance_to_goal':math.hypot(xyz[0]-target[0],xyz[1]-target[1]),'new_clear_cells':len(new),'new_clear_cells_in_target_region':sum(region_for(i,grid)==plan['target']['region_id'] for i in new),'target_cell_newly_clear':cell in new,'clear_cell_count':len(clear)}
     report['samples'].append(sample);last_frame=frame
    if native_token is None and native_path.exists():
     try:native_token=load(native_path)['request']['token']
     except (OSError,ValueError,KeyError):pass
    if native_token is not None:
     live=shared_snapshot(s['pid'],native_token)
     if live:report['native']=live;report['native_status']='shared_mapping_live'
    report['status']='running';write(a.output,report);time.sleep(.1)
   if child.poll() is None:stop_mapping(native_path,s['pid']);raise ValueError('Native return still pending after bounded wait')
  native=load(native_path);n=native.get('native',{});rq=native.get('request',{})
  recovery_token=rq.get('token');live=shared_snapshot(s['pid'],recovery_token) if recovery_token else None
  if child.returncode!=0 or native.get('host_exit') is None or not live or live.get('phase') not in (3,4) or live.get('restore_mask')!=31 or live.get('active')!=0:
   stop_mapping(native_path,s['pid']);recovery_deadline=time.monotonic()+15
   while time.monotonic()<recovery_deadline:
    live=shared_snapshot(s['pid'],recovery_token) if recovery_token else None
    if live and live.get('phase') in (3,4) and live.get('restore_mask')==31 and live.get('active')==0:break
    time.sleep(.05)
   terminal=bool(live and live.get('phase') in (3,4) and live.get('restore_mask')==31 and live.get('active')==0)
   report.update(status='finished_with_error' if terminal else 'return_pending',error='native_child_failed_or_report_not_terminal',native=live or n,native_report=native,native_child_exit=child.returncode,native_recovery_required=not terminal)
   write(a.output,report);print(json.dumps({'report':str(a.output),'status':report['status'],'native':report['native'],'error':report['error']}));return
  if n.get('phase')!=live.get('phase') or n.get('restore_mask')!=live.get('restore_mask') or n.get('active')!=live.get('active'):raise ValueError('Native file differs from live terminal mapping')
  if native.get('session_id')!=s['session_id'] or rq.get('command_id')!=report['request']['command_id'] or n.get('command_id')!=rq.get('command_id') or n.get('task_id')!=report['request']['task_id'] or n.get('seq')!=report['request']['seq'] or native.get('preflight',{}).get('selected',{}).get('object_id')!=unit['object_id']:raise ValueError('Native child report binding mismatch')
  report.update(status='finished' if n.get('phase')==3 and n.get('error')==0 else 'finished_with_error',error=None if n.get('phase')==3 and n.get('error')==0 else 'native_error_'+str(n.get('error')),native=n,native_report=native,native_report_path=str(native_path.resolve()),native_report_sha256=file_sha(native_path));report['assessment']=assessment(report);write(a.output,report);print(json.dumps({'report':str(a.output),'assessment':report['assessment']},ensure_ascii=False))
 except BaseException as e:
  if child and child.poll() is None:stop_mapping(native_path,s['pid'])
  report.update(status='return_pending' if child and child.poll() is None else 'no_dispatch_rejected' if not child else 'failed',error=str(e));write(a.output,report);raise
 finally:m.close()

def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='mode',required=True)
 p=sub.add_parser('plan');p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--exclude-region',action='append',default=[]);p.add_argument('--unit-id',type=int);p.add_argument('--max-plan-distance',type=float,default=550)
 r=sub.add_parser('run');r.add_argument('--session',type=Path,required=True);r.add_argument('--plan',type=Path,required=True);r.add_argument('--natural',type=Path,required=True);r.add_argument('--after-report',type=Path,action='append');r.add_argument('--no-prior-lease',action='store_true');r.add_argument('--output',type=Path,required=True);r.add_argument('--execute',action='store_true')
 a=ap.parse_args();plan_command(a) if a.mode=='plan' else execute_command(a)
if __name__=='__main__':main()
