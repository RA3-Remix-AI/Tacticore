"""Persistent battle coordinator; a trusted host owns native execution authorization."""
from __future__ import annotations
import argparse,asyncio,ctypes,hashlib,json,math,os,subprocess,sys,time,traceback,uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for part in ('strategy','production','production/persistent'):
 sys.path.insert(0,str(ROOT.parent/part))
from engine import Binding,StrategyEngine,ContractError
from battle_agent import BattleAgent,BuildEvidence,TacticalEvidence,MissionEvidence
from http_adapter import load_profile,AdapterError
from model_backend import BACKENDS,DEFAULT_BACKEND,RuntimeAdapterError,check_backend_available,create_backend
from service import player_lease
from assess_trace import assess
from live_state import LiveBattleState,atomic_json,RetryableSample
from observe_production import k,w
from observe_production import Memory
from read_match_state import snapshot as native_match_snapshot
from tactical_bridge import TacticalBridge,verify_manifest,air_scout_authorized,module as load_path_module
from continuous_contract import mission_limits

def production_executor_type():
 return load_path_module(ROOT.parent/'production/persistent/client.py','host_bound_production_executor').ProductionExecutor

def capability_evidence(path,session):
 path=Path(path).resolve();allowed=(ROOT.parent/'acceptance/runs').resolve()
 if not path.is_relative_to(allowed):raise ValueError('Evidence must belong to recorded acceptance runs')
 report=json.loads(path.read_text(encoding='utf-8-sig'))
 if report.get('mod_sha256')!=session['mod_sha256']:raise ValueError('Capability package differs')
 stream=Path(report['stream']).resolve()
 if stream.parent!=path.parent:raise ValueError('Evidence stream is outside its run')
 records=[json.loads(line) for line in stream.read_text(encoding='utf-8-sig').splitlines()]
 result=assess(report,records)
 if result.get('production_primitive_verified') is not True or not all(result['checks'].values()):raise ValueError('Production evidence incomplete')
 return dict(evidence_id=str(uuid.uuid5(uuid.NAMESPACE_URL,hashlib.sha256(path.read_bytes()+stream.read_bytes()).hexdigest())),supported_foci=('anti_air',),assessment=result,source_report=str(path),report_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def default_library():return Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'Tacticore/library.v2.json'

def mission_admission_filename(tactical):
 grants=[g for g in tactical['grants'] if mission_limits(g)] if tactical else []
 # Shared public cohorts must be admissible to every enabled continuous
 # executor. Mixed older families keep the conservative original reader.
 return 'mission_actor_admission_v2.py' if grants and all(g['stop_schema'].get('actor_admission_filename')=='mission_actor_admission_v2.py' for g in grants) else 'mission_actor_admission.py'

def own_process_identity():
 times=[w.FILETIME() for _ in range(4)];k.GetCurrentProcess.restype=w.HANDLE
 if not k.GetProcessTimes(k.GetCurrentProcess(),*[ctypes.byref(x) for x in times]):raise OSError('Host process identity unavailable')
 ticks=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
 return ticks,datetime.fromtimestamp((ticks-116444736000000000)/10000000,timezone.utc).isoformat()

def verified_completion(receipt,entry):
 return (receipt.get('status')=='completed' and receipt.get('command_id')==entry.get('command_id') and receipt.get('seq')==entry.get('seq')
  and receipt.get('queue_id')==entry.get('queue_id') and type(receipt.get('queue_id')) is int and receipt['queue_id']>0
  and receipt.get('completed') is True and receipt.get('accepted') is True and receipt.get('paid_verified') is True and receipt.get('created') is True
  and receipt.get('completion_observed') is True and receipt.get('queue_preserved') is True and type(receipt.get('cost')) is int and receipt['cost']>0
  and receipt.get('paid')==receipt['cost'] and type(receipt.get('object_id')) is int and receipt['object_id']>0
  and receipt.get('live_samples',0)>0 and receipt.get('payment_error')==0)

def conscript_evidence(path,session):
 path=Path(path).resolve()
 if not path.is_relative_to((ROOT.parent/'acceptance/runs').resolve()):raise ValueError('Persistent evidence outside acceptance runs')
 state=json.loads(path.read_text(encoding='utf-8-sig'));audit=path.with_name('persistent-production.jsonl')
 records=[json.loads(line) for line in audit.read_text(encoding='utf-8-sig').splitlines()]
 if not any(x.get('event')=='attach_preflight' and x.get('package_sha256')==session['mod_sha256'] and x.get('session_id')==state.get('session_id') for x in records):raise ValueError('Persistent package evidence mismatch')
 if state.get('native_phase')!=2 or state.get('restore_mask')!=31 or state.get('active_callbacks')!=0 or state.get('native_error')!=0 or state.get('local_error') is not None:raise ValueError('Persistent stop evidence incomplete')
 proven=[x for x in state['ledger'] if x.get('unit')=='conscript' and x.get('completed') is True and x.get('paid_verified') is True and x.get('paid')==x.get('cost') and x.get('cost',0)>0 and x.get('created') is True and x.get('completion_observed') is True and x.get('live_samples',0)>0 and x.get('payment_error')==0 and x.get('queue_preserved') is True]
 if not proven:raise ValueError('Conscript production evidence incomplete')
 return dict(status_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),audit_sha256=hashlib.sha256(audit.read_bytes()).hexdigest(),source=str(path),supported_foci=('infantry','balanced'))

class Host:
 def __init__(self,args):
  self.args=args;self.session=json.loads(args.session.read_text(encoding='utf-8-sig'))
  self.profile=load_profile(args.library,args.commander)
  self.evidence=capability_evidence(args.evidence,self.session) if args.evidence else None
  if args.persistent_evidence:
   if self.evidence is None:raise ValueError('Persistent evidence requires base production evidence')
   extra=conscript_evidence(args.persistent_evidence,self.session);self.evidence['supported_foci']+=extra['supported_foci'];self.evidence['persistent']=extra
  if args.execute and self.evidence is None:raise ValueError('Execution requires verified production evidence')
  foci=('native_baseline',)+tuple(self.evidence['supported_foci'] if self.evidence else ())
  self.output=Path(self.session['run_directory'])/'battle-host';self.output.mkdir(parents=True,exist_ok=True)
  prior=self.output/'dispatch-ledger.json'
  if args.execute and prior.exists() and json.loads(prior.read_text(encoding='utf-8-sig')):raise ValueError('Dispatched session requires explicit recovery; refusing replay')
  tactical=verify_manifest(args.tactical_evidence,self.session,args.commander) if getattr(args,'tactical_evidence',None) else None
  if tactical and not args.execute:raise ValueError('Tactical execution requires trusted execution host')
  self.collector=LiveBattleState(args.session,args.commander,args.player,foci=foci,output=self.output,visibility=bool(getattr(args,'with_visibility',False) or tactical),air_scout=air_scout_authorized(tactical),mission_history=bool(tactical and any(mission_limits(g) for g in tactical['grants'])),mission_admission_filename=mission_admission_filename(tactical))
  self.binding=Binding(self.session['session_id'],args.player,args.commander,self.profile.commander_name,self.profile.connection_id)
  self.engine=StrategyEngine(self.binding,timeout_seconds=args.model_timeout+.5,max_response_age_seconds=20,min_hold_game_seconds=15,audit_path=self.output/'plans.jsonl',status_path=self.output/'strategy-status.json',provenance_description='Validated computer-perspective bridge; unknown power and unseen enemies remain unknown. Only listed purpose-level capabilities may execute. Tactical tasks need at least 20 game seconds left after model response, up to 60 seconds. Prefer 45-second plans. Force fractions are budget ceilings; the host allocates at most half of eligible infantry. coordinate_force is a local two-role staged advance, not a whole-map formation order. Only supplied currently visible enemy contacts may be attacked.')
  evidence=BuildEvidence(self.evidence['evidence_id'],self.session['session_id'],args.player,'game_bridge',supported_foci=self.evidence['supported_foci']) if args.execute else None
  tactical_assertion=TacticalEvidence(tactical['evidence_id'],self.session['session_id'],args.player,'game_bridge',supported_purposes=tactical['supported_purposes'],actor_roles=tactical['actor_roles']) if tactical else None
  mission_grants=[g for g in tactical['grants'] if mission_limits(g)] if tactical else []
  if mission_grants:self.engine.provenance_description='Validated player-perspective observations; unseen positions and unknown power remain unknown. Strategy plans refresh independently of committed continuous missions. A verified mission keeps its target, formation reservation and hard deadline of at most 300 game seconds through approach, preparation, engagement and withdrawal. New intent may request withdrawal; it cannot silently retarget or release actors. Attack orders require current verified visibility. Coordinates, private own route history and native calls stay in the trusted local executor. Only raw-qualified effects, physical retreat and verified control release count as completion.'
  mission_purposes=tuple((name,tuple(sorted(g['purpose'] for g in mission_grants if g['module']==name))) for name in sorted({g['module'] for g in mission_grants}))
  mission_assertion=MissionEvidence(tactical['evidence_id'],self.session['session_id'],args.player,args.commander,'game_bridge',mission_purposes,max(mission_limits(g)['duration_frames'] for g in mission_grants)/15) if mission_grants else None
  self.agent=BattleAgent(self.engine,event_capacity=16,context_budget_bytes=8192,build_evidence=evidence,tactical_evidence=tactical_assertion,mission_evidence=mission_assertion,memory_path=self.output/'agent-state.json',jobs_path=self.output/'jobs.json')
  self.adapter=create_backend(self.profile,backend=getattr(args,"model_backend",DEFAULT_BACKEND),max_inflight=1,timeout=args.model_timeout,max_input_bytes=16384,max_tokens=1536)
  self.executor=None;self.executor_ready=False;self.pending=None;self.sent={};self.sequence=0;self.last_snapshot=None;self.last_result=None;self.phase='initializing';self.reason='not_started'
  self.started=time.monotonic();self.counters=dict(dispatches=0,started=0,completed=0,failed=0,blocked=0)
  self.stop_path=self.output/'stop.json';self.journal=self.output/'host-events.jsonl'
  self.host_creation_filetime,self.host_start_time=own_process_identity()
  self.observer=None;self.observer_output=None
  self.route_process=None;self.route_log=None
  self.remaining_budget=args.total_budget
  self.natural_path=args.natural_observation or Path(self.session['run_directory'])/'natural-production.json'
  self.tactical=TacticalBridge(self,tactical) if tactical else None
  self.reserve_controller=None
  pair_grants=[g for g in tactical['grants'] if g.get('executor_directory') in ('mission-formation-v13','mission-formation-v14','mission-formation-v15','mission-formation-v16') and (g.get('module'),g.get('purpose'))==('combined_arms','coordinate_force')] if tactical else []
  if pair_grants:
   if len(pair_grants)!=1:raise ValueError('one_paid_pair_controller_scope_required')
   from reserve_controller import ReserveController
   self.reserve_controller=ReserveController(self,pair_grants[0])

 def event(self,kind,**fields):
  value=dict(kind=kind,session_id=self.binding.session_id,player_id=self.binding.player_id,commander_id=self.binding.commander_id,wall_seconds=round(time.monotonic()-self.started,3),**fields)
  with self.journal.open('a',encoding='utf-8') as out:out.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');out.flush()

 def publish(self):
  status=dict(schema_version=1,kind='battle_host_v1',source='game_bridge',session_id=self.binding.session_id,pid=self.session['pid'],process_start=self.session['start_time'],mod_sha256=self.session['mod_sha256'],registry_revision=self.session['registry_revision'],host_pid=os.getpid(),host_start_time=self.host_start_time,host_creation_filetime=self.host_creation_filetime,binding=dict(player_id=self.binding.player_id,commander_id=self.binding.commander_id,commander_name=self.binding.commander_name,connection_id=self.binding.connection_id,computer_verified=self.collector.owner is not None),state=self.phase,reason_code=self.reason,
   execution=dict(enabled=self.executor_ready and self.phase=='running',dry_run=not self.args.execute,executor_connected=self.executor_ready,remaining_budget=self.remaining_budget),
   model_backend=getattr(self.adapter,'backend_name','unknown'),current_plan=self.engine.current.public() if self.engine.current else None,last_result=self.last_result,metrics=dict(self.engine.metrics),transport=dict(self.adapter.metrics),memory=dict(self.agent.metrics),task_counters=dict(self.counters),jobs=self.agent.jobs()['jobs'],latest_snapshot=dict(snapshot_id=self.last_snapshot['snapshot_id'],game_time_seconds=self.last_snapshot['game_time_seconds'],paused=self.last_snapshot['paused'],resources=self.last_snapshot['resources']) if self.last_snapshot else None)
  if getattr(self,'reserve_controller',None) is not None:status['paid_pair_controller']=self.reserve_controller.public_status()
  if getattr(self,'tactical',None) is not None:status['tactical']=dict(connected=self.tactical.executor is not None,counters=self.tactical.counters)
  if hasattr(self.agent,'missions'):status['missions']=self.agent.missions.public()
  if self.last_snapshot and self.last_snapshot.get('battlefield') is not None:
   battlefield=self.last_snapshot['battlefield'];status['visibility']=dict(viewer_player_id=battlefield['viewer_player_id'],verified=battlefield['visibility_verified'],currently_visible=sum(c['currently_visible'] for c in battlefield['contacts']),last_seen=sum(not c['currently_visible'] for c in battlefield['contacts']),formations=len(battlefield['formations']))
  atomic_json(self.output/'host-status.json',status)

 def stop_requested(self):
  if not self.stop_path.exists():return False
  try:return json.loads(self.stop_path.read_text(encoding='utf-8-sig')).get('session_id')==self.binding.session_id
  except (ValueError,OSError):return False

 def start_route_recorder(self):
  if not getattr(self.collector,'mission_history',False):return
  self.route_log=(self.output/'own-route-recorder.log').open('w',encoding='utf-8')
  self.route_process=subprocess.Popen([sys.executable,str(ROOT/'record_own_routes.py'),'--session',str(self.args.session.resolve()),'--commander',self.binding.commander_id,'--max-wall-seconds',str(min(7200,self.args.max_wall_seconds+180))],stdout=self.route_log,stderr=self.route_log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  self.event('own_route_recorder_started',observer_pid=self.route_process.pid,source='own_ground_only',game_commands=0)

 async def stop_route_recorder(self):
  process=getattr(self,'route_process',None)
  if process is not None and process.poll() is None:
   atomic_json(self.output/'route-recorder-stop.json',dict(session_id=self.binding.session_id))
   try:await asyncio.to_thread(process.wait,3)
   except subprocess.TimeoutExpired:
    process.terminate();await asyncio.to_thread(process.wait,3)
  if getattr(self,'route_log',None) is not None:self.route_log.close()

 async def connect_executor(self):
  if not self.args.execute or self.executor is not None:return
  if self.last_snapshot['paused']:self.reason='waiting_for_game_resume';return
  own=json.loads((self.output/'own-state.json').read_text(encoding='utf-8'))
  candidates=[x for x in own['factories'] if x.get('template')=='SovietBarracks' and x.get('production_interface_available')]
  if not candidates:self.reason='waiting_for_barracks';return
  candidate=min(candidates,key=lambda value:int(value['address'],0))
  if not self.natural_path.exists() and self.observer is None:
   self.observer_output=self.natural_path.open('w',encoding='utf-8')
   self.observer=subprocess.Popen([str(ROOT.parent/'production/bin/observe_build.exe'),str(self.session['pid']),'30'],stdout=self.observer_output,stderr=subprocess.DEVNULL,text=True)
   self.event('natural_observer_started')
  if self.observer is not None:
   if self.observer.poll() is None:self.reason='waiting_for_native_production_observation';return
   if self.observer_output is not None:self.observer_output.close();self.observer_output=None
   if self.observer.returncode!=0:raise RuntimeError('native_observer_failed')
  if not self.natural_path.exists():self.reason='waiting_for_native_production_observation';return
  ProductionExecutor=production_executor_type()
  self.executor=ProductionExecutor(self.args.session,self.collector.latest_snapshot_path,candidate['address'],self.binding.commander_id,self.natural_path,total_budget=self.args.total_budget,reserve_floor=self.args.reserve,min_interval_frames=150)
  result=await asyncio.to_thread(self.executor.start)
  # The actual native handshake, not presence of a JSON file, authorizes dispatch.
  if not isinstance(result,dict) or result.get('state')!='running' or result.get('native_phase')!=1 or result.get('native_error')!=0 or result.get('personality_binding_verified') is not True:raise RuntimeError('executor_handshake_failed')
  self.executor_ready=True;self.event('executor_connected')

 def feedback(self,task_id,status,reason,at):
  self.agent.record_feedback(dict(session_id=self.binding.session_id,player_id=self.binding.player_id,commander_id=self.binding.commander_id,task_id=task_id,status=status,reason_code=reason,at_game_seconds=at,source='game_bridge'))
  if status in self.counters:self.counters[status]+=1
  self.event('task_feedback',task_id=task_id,status=status,reason_code=reason,at_game_seconds=at)

 async def receive_receipts(self,allow_stopped=False):
  if not self.executor_ready:return
  status=await asyncio.to_thread(self.executor.status)
  terminal_restored=allow_stopped and status.get('native_phase')==2 and status.get('restore_mask')==31 and status.get('active_callbacks')==0 and status.get('native_error')==0
  if not terminal_restored and (status.get('native_phase')!=1 or status.get('native_error')!=0 or status.get('local_error') is not None):raise RuntimeError('executor_lost')
  # Client normalization provides completed only after native node/payment/create correlation.
  for receipt in status.get('ledger',[]):
   task_id=receipt.get('task_id');entry=self.sent.get(task_id)
   if entry is None or entry.get('terminal'):continue
   phase=receipt.get('status')
   if verified_completion(receipt,entry):
    self.feedback(task_id,'completed','ok',self.last_snapshot['game_time_seconds']);entry['terminal']=True
   elif phase in ('failed','rejected','no_dispatch_rejected'):
    self.feedback(task_id,'failed','execution_error',self.last_snapshot['game_time_seconds']);entry['terminal']=True
  self.remaining_budget=max(0,self.args.total_budget-status.get('spent_committed',0))
  if not any(task.status=='active' for task in self.agent.goals.tasks):
   foci=[focus for focus in self.evidence['supported_foci'] if self.remaining_budget>=(220 if focus=='anti_air' else 85)]
   self.collector.foci=('native_baseline',)+tuple(foci)

 async def dispatch(self):
  if not self.executor_ready or self.last_snapshot['paused']:return
  reserve=getattr(self,'reserve_controller',None)
  if reserve is not None:
   if await reserve.maybe_prepare() or reserve.blocks_build():return
  own_path=self.output/'own-state.json'
  if own_path.exists():
   own=json.loads(own_path.read_text(encoding='utf-8'))
   address=getattr(self.executor,'factory_address',None)
   for factory in own.get('factories',[]):
    if address is not None and int(factory['address'],0)!=address:continue
    nodes=factory.get('queue_candidate',{}).get('nodes')
    if isinstance(nodes,list) and len(nodes)>2:return
  for task in self.agent.jobs()['jobs']:
   if not task.get('host_dispatch_candidate') or task['task_id'] in self.sent:continue
   if task.get('module')!='build' or task.get('focus') not in self.evidence['supported_foci']:continue
   focus=task['focus'];own=self.last_snapshot['production']['own_roles']
   unit='flak' if focus=='anti_air' or (focus=='balanced' and own.get('anti_air',0)<max(1,own.get('infantry',0)//3)) else 'conscript'
   now=self.last_snapshot['game_time_seconds']
   if now>=task['expires_at_game_seconds']:continue
   budget=min(1000,self.remaining_budget,int(self.last_snapshot['resources']['credits']*task['budget']['fraction']))
   if budget<(220 if unit=='flak' else 85):self.feedback(task['task_id'],'blocked','insufficient_funds',now);continue
   self.sequence+=1
   command=dict(session_id=self.binding.session_id,player_id=self.binding.player_id,commander_id=self.binding.commander_id,command_id=str(uuid.uuid4()),task_id=task['task_id'],seq=self.sequence,unit=unit,budget=budget,reserve=self.args.reserve,expires_frame=int(task['expires_at_game_seconds']*15))
   self.sent[task['task_id']]=dict(command_id=command['command_id'],seq=self.sequence,queue_id=None,terminal=False)
   atomic_json(self.output/'dispatch-ledger.json',self.sent)
   self.event('dispatch_pending',task_id=task['task_id'],command_id=command['command_id'],seq=self.sequence)
   receipt=await asyncio.to_thread(self.executor.submit,command)
   self.counters['dispatches']+=1
   if receipt.get('status') in ('accepted','queued','started','completed') and receipt.get('accepted') is True:
    self.sent[task['task_id']]['queue_id']=receipt['queue_id']
    self.feedback(task['task_id'],'started','ok',now)
   else:
    # Outcomes lacking a definitive pre-dispatch refusal are never retried.
    self.feedback(task['task_id'],'failed','execution_error',now);self.sent[task['task_id']]['terminal']=True
    if receipt.get('status')=='unknown':
     self.phase='fault';self.reason='dispatch_outcome_unknown';self.event('dispatch_unknown',task_id=task['task_id']);raise RuntimeError('dispatch_outcome_unknown')
   atomic_json(self.output/'dispatch-ledger.json',self.sent)

 async def urgent_controller_decision(self):
  reserve=getattr(self,'reserve_controller',None)
  if reserve is None:return False
  epoch=reserve.urgent_ready_epoch()
  if epoch is None or not self.engine.request_urgent_capability(epoch):return False
  # Cancel the obsolete outer decision and await its actual transport before
  # starting another request. No provider overlap or implicit urgent retries.
  if self.pending is not None:
   if not self.pending.done():self.pending.cancel()
   await asyncio.gather(self.pending,return_exceptions=True)
   self.pending=None
  await self.engine.drain_obsolete_request()
  self.event('paid_pair_ready_reassessment',epoch=epoch,game_time_seconds=self.last_snapshot['game_time_seconds'])
  return True

 def has_result_candidate(self,state):
  rows=state.get('result_records',[])
  return any(row.get('victory_frame') for row in rows) or (self.session.get('scenario',{}).get('participant_count')==2 and any(row.get('defeat_frame') for row in rows))

 async def read_result_candidate(self):
  def read():
   memory=Memory(self.session['pid'],self.session)
   try:return native_match_snapshot(memory.read)
   finally:memory.close()
  try:
   state=await asyncio.to_thread(read)
   atomic_json(self.output/'result-native-state.json',state)
   if self.has_result_candidate(state):self.collector.native=state;return True
   if self.last_snapshot is not None and self.last_snapshot['game_time_seconds']>0 and state.get('simulation_frame')==0 and state.get('mode_raw')==9:
    self.collector.native=state;self.result_candidate_reason='native_lifecycle_transition_requires_visual_confirmation';return True
  except Exception:pass
  return False

 async def run(self):
  sampling_failures=0
  with player_lease(ROOT/'control-leases',self.binding):
   self.event('host_started',execution_requested=self.args.execute)
   try:
    self.start_route_recorder()
    while time.monotonic()-self.started<self.args.max_wall_seconds:
     if self.stop_requested():self.reason='user_stop';break
     try:
      if getattr(self,'reserve_controller',None) is not None and self.reserve_controller.runtime is not None:await self.reserve_controller.poll()
      if hasattr(self.collector,'required_regions'):self.collector.required_regions={job['target_region'] for job in self.agent.jobs()['jobs'] if job.get('target_region') and job.get('status') in ('dispatch_pending','active','planned')}
      snapshot=await asyncio.to_thread(self.collector.collect)
     except Exception as sampling_error:
      if self.last_snapshot is None and getattr(self.args,'wait_for_match',False) and time.monotonic()-self.started<180:
       self.phase='waiting_game';self.reason='waiting_for_selected_commander_match';self.publish();await asyncio.sleep(1);continue
      if await self.read_result_candidate():
       self.phase='result_candidate';self.reason=getattr(self,'result_candidate_reason','native_result_requires_visual_confirmation');self.event('native_result_candidate_after_cleanup')
      elif isinstance(sampling_error,RetryableSample) and sampling_failures<5:
       sampling_failures+=1;self.collector.private_targets={};self.phase='sampling_wait';self.reason='non_atomic_sample_discarded';self.event('sample_retry',consecutive=sampling_failures);self.publish();await asyncio.sleep(.2);continue
      else:self.phase='fault';self.reason='game_lifecycle_unavailable';self.event('sampling_failed')
      break
     sampling_failures=0
     self.last_snapshot=snapshot
     if getattr(self,'reserve_controller',None) is not None:self.reserve_controller.update_scope()
     self.agent.observe(snapshot)
     if snapshot['snapshot_id']==1:self.event('entered_match',first_game_time_seconds=snapshot['game_time_seconds'])
     if self.has_result_candidate(self.collector.native):
      self.phase='result_candidate';self.reason='native_result_requires_visual_confirmation';self.event('native_result_candidate');break
     self.phase='paused' if snapshot['paused'] else 'running';self.reason='game_paused' if snapshot['paused'] else 'observing'
     if self.pending is not None and self.pending.done():
      result=self.pending.result();self.pending=None;self.last_result=dict(status=result.status,reason_code=result.reason_code)
      self.event('decision',**self.last_result)
     await self.connect_executor()
     if getattr(self,'tactical',None) is not None:await self.tactical.connect()
     await self.receive_receipts()
     if getattr(self,'tactical',None) is not None:await self.tactical.receive()
     await self.dispatch()
     if getattr(self,'tactical',None) is not None:await self.tactical.dispatch()
     await self.urgent_controller_decision()
     if self.pending is None:self.pending=asyncio.create_task(self.agent.decide(self.last_snapshot,self.adapter))
     self.publish()
     await asyncio.sleep(self.args.interval)
    else:self.reason='host_time_limit'
   except Exception as error:
    self.phase='fault'
    fixed={'natural_thread_missing','natural_evidence_mismatch','executor_handshake_failed','executor_lost','native_observer_failed','factory_not_unique','commander_binding_unverified','factory_interface_unavailable','native_shared_layout_mismatch'}
    if self.reason!='dispatch_outcome_unknown':self.reason=str(error) if str(error) in fixed else 'host_runtime_error'
    # Source locations only: no exception text, local values or transport body.
    frames=[]
    for frame in traceback.extract_tb(error.__traceback__):
     path=Path(frame.filename)
     frames.append(dict(file=str(path.relative_to(ROOT.parent)) if path.is_relative_to(ROOT.parent) else path.name,line=frame.lineno,function=frame.name))
    self.event('host_fault',error_type=type(error).__name__,reason_code=self.reason,source_frames=frames)
   finally:
    if self.pending is not None and not self.pending.done():
     self.pending.cancel();await asyncio.gather(self.pending,return_exceptions=True)
    elif self.pending is not None:await asyncio.gather(self.pending,return_exceptions=True)
    if self.executor_ready:
     try:await self.receive_receipts(allow_stopped=True)
     except Exception as error:self.event('terminal_feedback_incomplete',error_type=type(error).__name__)
    if getattr(self,'tactical',None) is not None:
     try:await self.tactical.stop()
     except Exception as error:self.phase='fault';self.reason='tactical_restoration_unverified';self.event('tactical_restoration_unverified',error_type=type(error).__name__)
    if getattr(self,'reserve_controller',None) is not None:
     try:await self.reserve_controller.stop()
     except Exception as error:self.phase='fault';self.reason='reserve_control_release_unverified';self.event('reserve_control_release_unverified',error_type=type(error).__name__)
    self.agent.stop()
    if self.executor is not None:

     stopped=await asyncio.to_thread(self.executor.stop)
     if stopped.get('native_phase') is not None and (stopped.get('native_phase')!=2 or stopped.get('restore_mask')!=31 or stopped.get('active_callbacks')!=0):
      self.phase='fault';self.reason='executor_restoration_unverified';self.event('executor_restoration_unverified')
    if self.observer is not None and self.observer.poll() is None:
     try:await asyncio.to_thread(self.observer.wait,35)
     except subprocess.TimeoutExpired:self.phase='fault';self.reason='observer_restoration_unverified'
    if self.observer_output is not None:self.observer_output.close()
    await self.stop_route_recorder()
    self.executor_ready=False
    if self.phase not in ('fault','result_candidate'):self.phase='stopped'
    self.publish();self.event('host_stopped',reason_code=self.reason)
  return dict(state=self.phase,reason_code=self.reason,metrics=self.engine.metrics,task_counters=self.counters,runtime=str(self.output))

def parser():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--session',type=Path,required=True);p.add_argument('--commander',required=True);p.add_argument('--player',type=int,default=3);p.add_argument('--library',type=Path,default=default_library())
 p.add_argument('--evidence',type=Path);p.add_argument('--persistent-evidence',type=Path);p.add_argument('--natural-observation',type=Path);p.add_argument('--execute',action='store_true')
 p.add_argument('--check',action='store_true',help='Read-only readiness check; makes no HTTP request or native call')
 p.add_argument('--wait-for-match',action='store_true',help='Arm the host before game start; no model/native calls until actual UUID binding')
 p.add_argument('--with-visibility',action='store_true',help='Require exact-build visibility evidence and per-match computer-perspective handshake')
 p.add_argument('--tactical-evidence',type=Path,help='Purpose-level raw evidence manifest; independently reassessed before any tactical capability is exposed')
 p.add_argument('--total-budget',type=int,default=2000);p.add_argument('--reserve',type=int,default=1500)
 p.add_argument('--model-backend',choices=BACKENDS,default=DEFAULT_BACKEND,help='pydantic default; legacy explicit rollback')
 p.add_argument('--model-timeout',type=float,default=12);p.add_argument('--interval',type=float,default=3);p.add_argument('--max-wall-seconds',type=int,default=1200)
 return p

def main():
 args=parser().parse_args()
 if not 0<=args.player<=15 or not 220<=args.total_budget<=10000 or not 500<=args.reserve<=10000 or not 2<=args.model_timeout<=30 or not 1<=args.interval<=10 or not 10<=args.max_wall_seconds<=3600:raise ValueError('Invalid host bounds')
 try:
  check_backend_available(args.model_backend)
  host=Host(args)
  if args.check:
   snapshot=host.collector.collect()
   k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE
   mapping=k.OpenFileMappingW(4,False,'Local\\RA3ProductionPersistent_'+str(host.session['pid']))
   if mapping:k.CloseHandle(mapping)
   binaries=all(path.exists() for path in [ROOT.parent/'production/persistent/bin-v2/persistent_host.exe',ROOT.parent/'production/persistent/bin-v2/ProductionPersistent.dll',ROOT.parent/'production/bin/observe_build.exe'])
   result=dict(can_start=bool(args.execute and host.evidence and binaries and not mapping),session_id=host.binding.session_id,player_id=host.binding.player_id,commander_id=host.binding.commander_id,computer_verified=True,package_verified=True,production_evidence_verified=host.evidence is not None,paused=snapshot['paused'],reason_code='fresh_process_required' if mapping else 'ready' if binaries else 'executor_binaries_missing')
   print(json.dumps(result,ensure_ascii=False));return 0 if result['can_start'] else 2
  print(json.dumps(asyncio.run(host.run()),ensure_ascii=False))
 except KeyboardInterrupt:print(json.dumps(dict(state='stopped',reason_code='keyboard_interrupt')))
 except RuntimeAdapterError as error:
  print(json.dumps(dict(can_start=False,state='fault',reason_code=str(error))));return 1
 except Exception as error:
  if args.check:print(json.dumps(dict(can_start=False,state='fault',reason_code='waiting_for_active_match' if isinstance(error,ValueError) else type(error).__name__)))
  else:print(json.dumps(dict(state='fault',reason_code=type(error).__name__)))
  return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
