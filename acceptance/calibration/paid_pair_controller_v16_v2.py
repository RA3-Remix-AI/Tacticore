"""One real paid Cons/Flak pair in one MF16 controller against active native AI.

Calibration only: no model calls, game-memory edits, spawning or producer rearm.
Production stays running during the tactical lease and is stopped only afterward.
"""
import argparse,hashlib,importlib.util,json,math,struct,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];NATIVE=ROOT/'tactical/mission-formation-v16'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def patch_state(raw,expected,address,base,image_size):
 if raw==expected:return 'original'
 if len(raw)!=len(expected) or len(raw)<5 or raw[0]!=0xe9 or raw[5:]!=expected[5:]:raise ValueError('producer_startup_unknown_entry_bytes')
 target=(address+5+struct.unpack('<i',raw[1:5])[0])&0xffffffff
 if not base<=target<base+image_size:raise ValueError('producer_startup_foreign_jump')
 return 'installed'

def wait_producer_installed(memory,producer,output,*,timeout=2,clock=time.monotonic,sleep=time.sleep):
 """Only observe installation; phase1 precedes all five EnableHook calls."""
 if type(timeout) not in (int,float) or not 0<timeout<=2:raise ValueError('producer_startup_wait_bound')
 binding=load('mf16_original_producer_binding',NATIVE/'producer_binding.py')
 helper=load('mf16_startup_module_lookup',ROOT/'tactical/readonly_disposal.py');dll=ROOT/'production/persistent/bin-v2/ProductionPersistent.dll';base=helper.module_base(memory,dll)
 nt=memory.u32(base+0x3c)
 if memory.read(base,2)!=b'MZ' or not 0x40<=nt<=0x1000 or memory.read(base+nt,4)!=b'PE\0\0' or memory.read(base+nt+24,2)!=b'\x0b\x01':raise ValueError('producer_startup_pe32')
 size=memory.u32(base+nt+24+56)
 if not 0x1000<=size<=0x10000000:raise ValueError('producer_startup_image_size')
 rows=binding.entries();begin=clock();last=None;record=dict(protocol='producer_install_barrier_readonly_v2',mutations=False,sdk_calls=0,game_memory_writes=False,reader_sha256=hashlib.sha256((NATIVE/'producer_binding.py').read_bytes()).hexdigest(),module_base=hex(base),image_size=size,samples=[],ready=False)
 try:
  while clock()-begin<timeout:
   shared=producer.shared
   if (shared.phase,shared.error,shared.stop_requested)!=(1,0,0):raise ValueError('producer_startup_not_running')
   samples=[dict(row,actual=memory.read(int(row['address'],0),row['length']).hex()) for row in rows]
   sample=dict(elapsed_seconds=clock()-begin,phase=shared.phase,error=shared.error,stop_requested=shared.stop_requested,entries=samples);record['samples'].append(sample)
   states=[patch_state(bytes.fromhex(r['actual']),bytes.fromhex(r['expected']),int(r['address'],0),base,size) for r in samples];sample['states']=states
   current=[r['actual'] for r in samples]
   if states==['installed']*5 and current==last:
    # Reuse the original strict validator; no substitute proof is fed to MF16.
    record['original_loaded_entries']=binding.loaded_entries(memory);record['ready']=True;return record
   last=current if states==['installed']*5 else None;sleep(.02)
  raise ValueError('producer_startup_complete_detours_timeout')
 except BaseException as error:
  record['error_type']=type(error).__name__;record['reason_code']=str(error);raise
 finally:
  output=Path(output)
  with output.open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2,allow_nan=False)

def select_target(targets,safety,anchors):
 rows=[]
 for contact,target in targets.items():
  definition=safety['templates'].get(target['type_hash'],{});role=definition.get('role');distance=min(math.dist(target['xyz'][:2],p[:2]) for p in anchors)
  if role not in ('structure','economy') or role=='economy' and target['type_hash']!='0xc45aaeab' or not 450<=distance<=2000 or target.get('hp',0)<600:continue
  name=definition.get('template','')
  if any(word in name for word in ('BaseDefense','Turret','Wall')):continue
  # All candidates come from the current own-FOV projection. Prefer a local
  # skirmish, with a penalty for currently observed nearby armour/defences.
  pressure=0
  for other in targets.values():
   if other['object_id']==target['object_id'] or math.dist(other['xyz'][:2],target['xyz'][:2])>350:continue
   info=safety['templates'].get(other['type_hash'],{});other_name=info.get('template','')
   if info.get('role') in ('armor','air') or any(word in other_name for word in ('BaseDefense','Turret')):pressure+=1
  rows.append((distance+400*pressure,distance,contact,target))
 return min(rows,default=None,key=lambda x:x[:3])

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--max-seconds',type=int,default=600);parser.add_argument('--wait-opportunity-seconds',type=int,default=180);args=parser.parse_args()
 runtime_module=load('mf16_calibration_runtime',NATIVE/'lease_v2.py')
 if not runtime_module.EXECUTE_ENABLED:raise ValueError('mf16_candidate_locked')
 if args.output.exists() or not 120<=args.max_seconds<=780 or not 0<=args.wait_opportunity_seconds<=180:raise ValueError('mf16_calibration_bounds')
 args.session=args.session.resolve();args.output=args.output.resolve();raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));run=Path(session['run_directory']).resolve()
 if args.output.parent!=run or session['scenario'].get('model_requests_enabled') is not False:raise ValueError('mf16_owned_nonmodel_calibration_required')
 common=load('mf16_paid_calibration_helpers',Path(__file__).with_name('continuous_paid_margin12_static.py'));production_module=load('mf16_paid_original_producer',ROOT/'production/persistent/client.py')
 memory=common.Memory(session['pid'],session);factory=None;producer=None;controller=None;status=None;report=None
 try:
  end=time.monotonic()+args.max_seconds
  while time.monotonic()<end:
   owned=common.own_candidates(memory,3,common.load_catalog());factories=[u for u in owned['candidates'] if u['type_hash']=='0x80d4ea1e' and memory.f32(memory.u32(int(u['address'],0)+0x33c)+4)>0]
   if len(factories)==1:factory=factories[0];break
   time.sleep(.1)
  if factory is None:raise ValueError('mf16_no_unique_live_owned_barracks')
  sys.path.insert(0,str(ROOT/'visibility'));cap=load('mf16_field_visibility_capability',ROOT/'visibility/capability.py');projection=load('mf16_field_projection',ROOT/'visibility/projection.py');collector=load('mf16_field_collector',ROOT/'visibility/collector.py')
  proof,safety=cap.bind_session(memory,session,3);proof_path=args.output.with_name(args.output.stem+'-visibility.json')
  with proof_path.open('x',encoding='utf-8') as f:json.dump(proof,f,indent=2)
  reader=collector.VisibilityCollector(memory,session,3,projection.VisibilityProjection(session['session_id'],3,session['mod_sha256'],proof,safety))
  # Wait only before arming/borrowing; no tactical lifetime is renewed here.
  opportunity_end=min(end,time.monotonic()+args.wait_opportunity_seconds)
  while time.monotonic()<opportunity_end:
   frame=memory.u32(memory.u32(0xcd8ce4)+0x50);reader.collect(frame/15)
   if select_target(reader.private_targets,safety,[factory['xyz']]) is not None:break
   time.sleep(.2)
  natural=run/'natural-production.json'
  if not natural.exists():
   observed=subprocess.run([str(ROOT/'production/bin/observe_build.exe'),str(session['pid']),'30'],capture_output=True,text=True,check=True)
   with natural.open('x',encoding='utf-8') as f:f.write(observed.stdout)
  snapshot=args.output.with_name(args.output.stem+'-owned-supply.json');common.durable(snapshot,dict(common.own_candidates(memory,3,common.load_catalog()),pid=session['pid'],sha256=common.EXPECTED))
  producer=production_module.ProductionExecutor(args.session,snapshot,factory['address'],session['scenario']['commander_id'],natural,total_budget=5000,reserve_floor=1000,min_interval_frames=150);producer.start()
  wait_producer_installed(memory,producer,args.output.with_name(args.output.stem+'-producer-startup-readonly.json'))
  factory_info=production_module.read_factory(memory,factory,int(factory['owner_address'],0));frame=memory.u32(memory.u32(0xcd8ce4)+0x50);controller_id=str(uuid.uuid4());lease_id=str(uuid.uuid4());native_formation,fid=runtime_module.contract.formation_ids(controller_id)
  commands=[];slots=[]
  for role,(unit,cost) in enumerate((('conscript',85),('flak',220))):
   command=dict(session_id=session['session_id'],player_id=3,commander_id=session['scenario']['commander_id'],command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=role+1,unit=unit,budget=cost,reserve=1000,expires_frame=frame+850);commands.append(command)
   slots.append(dict(role=role,command_id=command['command_id'],task_id=command['task_id'],seq=role+1,unit=unit,cost=cost,factory=factory['address'],factory_id=factory['object_id'],iface=factory_info['interface']))
  config=dict(schema_version=1,controller_id=controller_id,lease_id=lease_id,formation_uuid=native_formation,formation_version=1,seq=(int(time.monotonic()*1000)&0x7fffffff) or 1,startup_deadline_frame=frame+900,startup_wall_ms=60000,slots=slots)
  config_path=args.output.with_name(args.output.stem+'-controller-input.json')
  with config_path.open('x',encoding='utf-8') as f:json.dump(config,f,indent=2)
  tactical_path=args.output.with_name(args.output.stem+'-controller.json');controller=runtime_module.ControllerRuntime(args.session,config,tactical_path,natural)
  report=dict(protocol='running_paid_pair_controller16_calibration_v2',target_selection_profile='static_ground_target_current_fov_v2',session_id=session['session_id'],pid=session['pid'],model_requests=0,controller_file=str(config_path),controller_report=str(tactical_path),driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),production_commands=[],production_budget=5000,pair_spend_limit=305,reserve_floor=1000,status='starting',tactical_native_attempts=1)
  common.durable(args.output,report);controller.arm();submitted=0;first_enqueue=None;next_target=0
  while time.monotonic()<end:
   if args.session.read_bytes()!=raw:raise ValueError('mf16_session_changed')
   state=controller.poll();native=controller.report['native'];frame=memory.u32(memory.u32(0xcd8ce4)+0x50)
   controller_accepting=native.get('phase')==1 and not native.get('error') and not state['controller'].get('error') and not controller.shared.stop_requested and state['controller'].get('stage',0)<3
   if controller_accepting and submitted<2 and (submitted==0 or first_enqueue is not None and frame>=first_enqueue+150):
    receipt=producer.submit(commands[submitted]);report['production_commands'].append(dict(command=commands[submitted],receipt=receipt));submitted+=1;common.durable(args.output,report)
    if receipt.get('accepted') is not True:raise ValueError('mf16_pair_production_refused_'+str(receipt.get('reason_code')))
    if first_enqueue is None:first_enqueue=receipt.get('enqueue_frame',frame)
   if controller_accepting and state['controller'].get('stage')==2 and controller.report.get('mission_request') is None and time.monotonic()>=next_target:
    reader.collect(frame/15);anchors=[slot['anchor'] for slot in native['slots']];chosen=select_target(reader.private_targets,safety,anchors);next_target=time.monotonic()+.15
    if chosen is not None:
     _,_,contact,target=chosen;task=str(uuid.uuid4());command=str(uuid.uuid4())
     public=dict(session_id=session['session_id'],player_id=3,commander_id=session['scenario']['commander_id'],command_id=command,task_id=task,seq=1,module='combined_arms',purpose='coordinate_force',formation_ids=[fid],formation_versions=[[fid,1]],required_roles=['infantry','anti_air'],force_fraction=1,target_contact_id=contact,target_region=None,expires_frame=native['controller']['hard_deadline_frame'],plan_id='nonmodel_calibration',generation=0)
     form=dict(formation_id=fid,version=1,roles={'infantry':1,'anti_air':1},region_id='home_base',available=True)
     try:controller.commit(public,form,proof_path,combat_frames=60)
     except ValueError as failure:
      if controller.report.get('mission_request') is not None:raise
      report.setdefault('readonly_commit_refusals',[]).append(dict(frame=frame,reason=str(failure)));common.durable(args.output,report)
   report['production_status']=producer.status();report['current_controller']=state;report['status']='running';common.durable(args.output,report)
   if controller.shared.phase in (3,4) and controller.host.poll() is not None:break
   time.sleep(.02)
  if controller.host.poll() is None:controller.stop()
  report['status']='controller_terminal' if controller.host.poll() is not None else 'unknown_controller_release';report['controller_final']=controller.report.get('assessment');report['controller_release']=controller.verified_release();common.durable(args.output,report)
 finally:
  if controller is not None and controller.host is not None and controller.host.poll() is None:controller.stop()
  if producer is not None:
   status=producer.stop()
   if report is not None:report['production_stopped']=status;report['paid_orders_verified']=common.paid_orders_verified(report['production_commands'],status);report['production_after_entries']=common.entry_proof(memory);common.durable(args.output,report)
  if controller is not None and (controller.host is None or controller.host.poll() is not None):controller.close()
  memory.close()
if __name__=='__main__':main()
