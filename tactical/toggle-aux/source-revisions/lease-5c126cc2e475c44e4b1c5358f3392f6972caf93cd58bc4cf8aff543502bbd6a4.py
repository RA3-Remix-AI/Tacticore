"""One ordinary Script CommandButton toggle. Calibration only; no model grant."""
import argparse,ctypes as c,hashlib,importlib.util,json,math,os,struct,subprocess,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
b=load('toggle_baseline',HERE.parent/'stop-move/lease.py')
resolver=load('toggle_button_resolver',HERE.parent/'recon/read_own_command_buttons.py')
from mobility_guard import mobility_status
from inspect_own_weapons import active_weapon
from stop_sequence import settled_stop
from restoration import single_control_release
EXTRA='button button_schema command_set initial_weapon_asset initial_weapon_entry toggle_calls toggle_hook_calls toggle_frame ak_samples last_ak_frame observed_weapon_asset observed_weapon_entry observed_ammo cash_before cash_after button_result post_actor_disposed'.split()
EVENT_EXTRA='weapon_entry weapon_asset weapon_ammo status84'.split()
class Event(c.Structure):_fields_=b.Event._fields_+[(x,b.U) for x in EVENT_EXTRA]+[('cash',b.L)]
class Tactical(c.Structure):_fields_=b.Tactical._fields_[:-1]+[(x,b.U) for x in EXTRA]+[('events',Event*4096)]
k=b.k;w=b.w;durable=b.durable
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def plain(value):
 if isinstance(value,c.Array):return [plain(x) for x in value]
 if isinstance(value,float) and not math.isfinite(value):return None
 return value
def capture(report,shared):
 snapshot=Tactical.from_buffer_copy(c.string_at(c.addressof(shared),c.sizeof(Tactical)));native={name:plain(getattr(snapshot,name)) for name in b.RESULT+'phase active count stop_calls private_stop_calls private_stop_frame move_issued_frame stable_samples stop_gate_samples last_sample_frame'.split()+EXTRA}
 for field,key in [('session','session_id'),('commander','commander_id'),('command','command_id'),('task','task_id')]:native[key]=str(uuid.UUID(bytes=struct.pack('<4I',*getattr(snapshot,field))))
 native['seq']=snapshot.seq;events=[]
 for i in range(min(max(0,snapshot.count),4096)):
  event=snapshot.events[i]
  if event.seq!=i+1:break
  row={key:plain(getattr(event,key)) for key,_ in Event._fields_};row['invalid_float_fields']=[key for key,_ in Event._fields_ if isinstance(getattr(event,key),float) and not math.isfinite(getattr(event,key))];events.append(row)
 report.update(native=native,events=events,status='finished' if snapshot.phase in [3,4] else 'running')
 return snapshot.phase in [3,4]

def assessment(report):
 n=report.get('native',{});rq=report['request'];pre=report['preflight'];ev=report.get('events',[]);toggle=n.get('toggle_frame',0);returned=n.get('returned_frame',0);thread=pre['window_thread'];owner=int(pre['owner'],0)
 chain=[e for e in ev if e['kind'] in [32,33] and e['tag']==5];gates=[e for e in ev if e['kind']==24];hits=[e for e in ev if e['kind']==31];ak=[e for e in ev if e['kind']==3 and toggle+15<=e['frame']<=returned and e['weapon_asset']==0x447ea26e and not e['status84']&0x20080000]
 stops=settled_stop([dict(e,kind=23 if e['kind']==23 else 24 if e['kind']==24 else e['kind']) for e in ev if e['kind'] in [3,23,24] and e['frame']<=toggle])
 checks=dict(terminal=report.get('status')=='finished' and report.get('host_exit')==0,clean=n.get('phase')==3 and n.get('error')==0 and n.get('restore_mask')==255 and n.get('active')==0 and not n.get('overflow'),bindings=n.get('session_id')==report['session_id']==pre['session_id'] and n.get('commander_id')==pre['commander_id'] and n.get('command_id')==rq['command_id'] and n.get('task_id')==rq['task_id'] and n.get('seq')==rq['seq'],thread=n.get('callback_thread')==thread and all(e['thread']==thread for e in ev),owner=all(e['owner']==owner for e in ev if n.get('issued_frame',0)<=e['frame']<=returned),one_ordinary_button=n.get('toggle_calls')==n.get('toggle_hook_calls')==1 and len(chain)==2 and chain[0]['kind']==32 and chain[1]['kind']==33 and chain[0]['arg']==int(rq['button']['toggle']['entry'],0),real_molotov_to_ak=n.get('initial_weapon_asset')==0x41872ecc and n.get('observed_weapon_asset')==0x447ea26e and n.get('initial_weapon_entry')!=n.get('observed_weapon_entry'),pack_and_distinct_ak=len({e['frame'] for e in ak})>=3 and len(hits)==1 and returned>=toggle+15 and n.get('ak_samples',0)>=3,normal_stop=stops['verified'] and n.get('stop_calls')==n.get('private_stop_calls')==1 and len(gates)==1 and gates[0]['seq']<chain[0]['seq'] if chain else False,no_move_attack=n.get('move_calls')==0 and not any(e['kind'] in [10,12] and e['tag'] for e in ev),no_native_interference=not any(e['tag']==0 and e['kind'] in [10,12,14,16,18,20,32] and n.get('issued_frame',0)<=e['frame']<returned for e in ev),monotonic=all(e['seq']==i+1 for i,e in enumerate(ev)) and all(a['frame']<=d['frame'] and ((d['tick']-a['tick'])&0xffffffff)<0x80000000 for a,d in zip(ev,ev[1:])),bounded=0<n.get('issued_frame',0)<=toggle<=returned<=n.get('issued_frame',0)+rq['lease_frames'],native_pool_return=single_control_release(report,255)['return_verified'])
 return dict(status='ordinary_weapon_toggle_and_return_verified' if all(checks.values()) else 'not_passed',checks=checks,model_eligible=False,completion_claim=False,scope='conscript_molotov_to_ak_calibration_only',normal_burst_allowed=False,money_note='Cash observations include native income/spending and are not transaction attribution. No price, ammo or status is written by the bridge.')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--session',type=Path,required=True);parser.add_argument('--object-id',type=int,required=True);parser.add_argument('--natural',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--seq',type=int);args=parser.parse_args()
 pre,session,raw,package,registry,registry_sha,m=b.readiness(args.session,args.object_id)
 try:
  actor=int(pre['selected']['address'],0)
  if pre['selected']['type_hash']!='0x19ab11af' or not mobility_status(m,actor)['independently_movable'] or m.u32(actor+0x26c):raise ValueError('free_idle_conscript_required')
  button=resolver.inspect(m,actor);weapon=active_weapon(m,actor)
  if (weapon.get('selected') or {}).get('template_id')!='0x41872ecc':raise ValueError('initial_molotov_required_no_double_toggle')
  natural=json.loads(args.natural.read_text(encoding='utf-8-sig'));b.compatible_natural_calls(natural,session['pid'])
  if natural['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')
  layout=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
  if layout!={'event':c.sizeof(Event),'tactical':c.sizeof(Tactical),'events':Tactical.events.offset,'unused1':0,'unused2':0}:raise ValueError('layout_mismatch')
  report=dict(session_id=session['session_id'],executable_sha256=b.EXPECTED,package_sha256=session['mod_sha256'],preflight=pre,status='read_only_ready',events=[],native={},model_eligible=False,initial_weapon=weapon,native_binary_sha256=digest(HERE/'bin/TacticalWeaponToggle.dll'),native_host_sha256=digest(HERE/'bin/tactical_host.exe'),wrapper_sha256=digest(__file__))
  command,task=str(uuid.uuid4()),str(uuid.uuid4());token=int.from_bytes(os.urandom(4),'little') or 1;seq=args.seq or int(time.monotonic()*1000)&0x7fffffff
  report['request']=dict(command_id=command,task_id=task,seq=seq,token=token,lease_frames=90,post_frames=30,button=button,source=1,third_flag=0,normal_pack_seconds=1.,reload_all_weapons_on_toggle=False)
  if args.output.exists():raise ValueError('existing_report_requires_recovery')
  durable(args.output,report)
  if not args.execute:print(json.dumps(report,ensure_ascii=False));return
  k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
  handle=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Tactical),'Local\\RA3TacticalWeaponToggle_'+str(session['pid'])+'_'+str(token));view=None;host=None;shared=None
  if not handle or c.get_last_error()==183:raise ValueError('mapping_not_unique')
  try:
   view=k.MapViewOfFile(handle,0xf001f,0,0,c.sizeof(Tactical))
   if not view:raise c.WinError(c.get_last_error())
   c.memset(view,0,c.sizeof(Tactical));shared=Tactical.from_address(view);s=shared;s.magic=0x57544731;s.version=1;s.pid=session['pid'];s.thread=pre['window_thread'];s.owner=int(pre['owner'],0);s.ai=int(pre['ai'],0);s.personality=int(pre['personality'],0);s.personality_id=int(pre['personality_id'],0);s.player_template=int(pre['player_template'],0);s.logic=int(pre['logic'],0);s.script_team=int(pre['script_team'],0);s.default_team=int(pre['default_team'],0);s.unit=actor;s.object_id=args.object_id;s.type_hash=0x19ab11af;s.update=int(pre['selected']['ai_address'],0);s.lease_frames=90;s.post_frames=30;s.session[:]=b.words(session['session_id']);s.commander[:]=b.words(pre['commander_id']);s.command[:]=b.words(command);s.task[:]=b.words(task);s.token=token;s.seq=seq;s.button=int(button['toggle']['entry'],0);s.button_schema=int(button['toggle']['schema'],0);s.command_set=int(button['command_set_hash'],0);s.target[:]=pre['selected']['xyz']
   times=[w.FILETIME() for _ in range(4)]
   if not k.GetProcessTimes(m.handle,*[c.byref(t) for t in times]):raise c.WinError(c.get_last_error())
   s.start_low=times[0].dwLowDateTime;s.start_high=times[0].dwHighDateTime
   if args.session.read_bytes()!=raw or digest(package)!=session['mod_sha256'] or digest(registry)!=registry_sha:raise ValueError('session_changed_before_dispatch')
   with args.output.with_suffix('.host.log').open('w',encoding='utf-8') as log:
    host=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=log,stderr=log);deadline=time.monotonic()+150
    while time.monotonic()<deadline:
     if args.session.read_bytes()!=raw:shared.stop_requested=1
     capture(report,shared);durable(args.output,report)
     if host.poll() is not None:break
     time.sleep(.1)
    if host.poll() is None:shared.stop_requested=1
    capture(report,shared);report['host_exit']=host.poll();report['assessment']=assessment(report);durable(args.output,report)
  except BaseException as error:
   if shared is not None:
    shared.stop_requested=1;deadline=time.monotonic()+10
    while time.monotonic()<deadline:
     if capture(report,shared):break
     time.sleep(.1)
   report['error']=str(error);report['host_exit']=host.poll() if host else None;durable(args.output,report);raise
  finally:
   if view:k.UnmapViewOfFile(view)
   k.CloseHandle(handle)
  print(json.dumps(dict(report=str(args.output),native=report['native'],assessment=report['assessment']),ensure_ascii=False))
 finally:m.close()
if __name__=='__main__':main()
