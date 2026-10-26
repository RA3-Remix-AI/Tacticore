"""Trusted host adapter: evidence -> committed task -> native receipts -> memory."""
import asyncio,hashlib,importlib.util,json,sys,time,uuid
from pathlib import Path
from live_state import atomic_json
from continuous_contract import PROTOCOL,MAX_DURATION_FRAMES,mission_limits,progress_from_receipt
from continuous_evidence import terminal_facts,progress_evidence,pre_dispatch_facts,bound_report
from held_controller_receipts import DIRECTORIES as PAID_CONTROLLER_DIRECTORIES

ROOT=Path(__file__).resolve().parent

def air_scout_authorized(evidence):
 return bool(evidence and any(grant['module']=='raid' and grant['purpose']=='recon' and set(grant['stop_schema']['actor_roles'])=={'air'} for grant in evidence['grants']))

def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value

def verify_manifest(path,session,commander_id):
 value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
 if set(value)!={'schema_version','sources'} or value['schema_version']!=1 or not isinstance(value['sources'],list) or not 1<=len(value['sources'])<=6:raise ValueError('Invalid tactical evidence manifest')
 verifier=module(ROOT.parent/'tactical/evidence.py','host_tactical_evidence')
 grants=[];seen=set()
 for item in value['sources']:
  if set(item)!={'module','purpose','report'}:raise ValueError('Invalid tactical evidence entry')
  key=(item['module'],item['purpose'])
  if key in seen:raise ValueError('Duplicate tactical purpose')
  seen.add(key);grant=verifier.verify_purpose(*key,Path(item['report']),session,commander_id)
  if mission_limits(grant):
   assessment=grant.get('raw_assessment',{})
   if assessment.get('long_approach_verified') is not True or assessment.get('long_retreat_verified') is not True:raise ValueError('Continuous capability requires real long approach and retreat evidence')
  grants.append(grant)
 purposes=tuple((name,tuple(sorted(purpose for mod,purpose in seen if mod==name))) for name in sorted({mod for mod,_ in seen}))
 actor_roles=[]
 for grant in grants:
  roles=grant.get('stop_schema',{}).get('actor_roles')
  if not isinstance(roles,(tuple,list)) or not roles or len(roles)!=len(set(roles)) or any(role not in ('infantry','anti_air','air') for role in roles):raise ValueError('Tactical executor actor scope missing')
  actor_roles.append((grant['module'],grant['purpose'],tuple(roles)))
 digest=hashlib.sha256(json.dumps(grants,sort_keys=True).encode()).hexdigest()
 return dict(evidence_id=str(uuid.uuid5(uuid.NAMESPACE_URL,digest)),supported_purposes=purposes,actor_roles=tuple(actor_roles),grants=grants)

def execution_from_receipt(receipt,entry):
 value=receipt.get('execution') or {key:receipt.get(key) for key in ('formation_versions','issued_frame','expires_frame','command_source','interference','goal_observed','restoration_verified')}
 if set(value)!={'formation_versions','issued_frame','expires_frame','command_source','interference','goal_observed','restoration_verified'}:raise ValueError('Missing tactical execution evidence')
 if value['formation_versions']!=entry['formation_versions'] or value['command_source']!='game_thread_bridge':raise ValueError('Tactical execution binding mismatch')
 maximum=MAX_DURATION_FRAMES if entry.get('mission_protocol')==PROTOCOL else 900
 if type(value['issued_frame']) is not int or value['issued_frame']<=0 or type(value['expires_frame']) is not int or not value['issued_frame']<value['expires_frame']<=value['issued_frame']+maximum:raise ValueError('Tactical execution frame window')
 if value['expires_frame']!=entry['expires_frame']:raise ValueError('Tactical expiry changed')
 if value['interference'] not in ('none','native_ai_override','unknown') or type(value['goal_observed']) is not bool or type(value['restoration_verified']) is not bool:raise ValueError('Invalid tactical outcome')
 return dict(value,formation_versions=dict(value['formation_versions']))

class TacticalBridge:
 def __init__(self,host,evidence):
  self.host=host;self.evidence=evidence;self.executor=None;self.sent={};self.sequence=0;self.journal=host.output/'tactical-dispatch-ledger.json'
  if self.journal.exists() and json.loads(self.journal.read_text(encoding='utf-8-sig')):raise ValueError('Tactical dispatch requires explicit recovery')
  self.counters={name:dict(accepted=0,started=0,completed=0,failed=0,cancelled=0,rejected=0) for name,_ in evidence['supported_purposes']}

 async def connect(self):
  host=self.host
  if self.executor is not None or host.last_snapshot['paused'] or not host.natural_path.exists():return
  # Production's passive observer must finish and restore before any tactical attachment.
  if host.observer is not None and host.observer.poll() is None:return
  client=module(ROOT.parent/'tactical/client.py','host_tactical_client')
  executor=client.TacticalExecutor(host.args.session,host.natural_path,host.binding.commander_id,host.binding.player_id)
  await asyncio.to_thread(executor.start)
  try:
   for grant in self.evidence['grants']:await asyncio.to_thread(executor.grant_capability,grant['module'],grant['purpose'],grant['source_report'])
  except BaseException:
   await asyncio.to_thread(executor.stop);raise
  self.executor=executor;host.event('tactical_executor_connected',manifest=executor.manifest())

 def persist(self):atomic_json(self.journal,self.sent)

 def feedback(self,task,status,reason,execution=None):
  host=self.host;value=dict(session_id=host.binding.session_id,player_id=host.binding.player_id,commander_id=host.binding.commander_id,task_id=task,status=status,reason_code=reason,at_game_seconds=host.last_snapshot['game_time_seconds'],source='game_bridge')
  if execution is not None:value['execution']=execution
  host.agent.record_feedback(value)
  entry=self.sent[task];self.counters[entry['module']][status]+=1
  host.event('tactical_task_feedback',module=entry['module'],purpose=entry['purpose'],task_id=task,status=status,reason_code=reason,execution=execution)

 async def dispatch(self):
  host=self.host
  if self.executor is None or host.last_snapshot['paused'] or host.phase!='running':return
  if any(not entry['terminal'] for entry in self.sent.values()):return
  collector=host.collector
  contacts=host.last_snapshot.get('battlefield',{}).get('contacts',[])
  current={contact['contact_id'] for contact in contacts if contact.get('currently_visible') is True and contact.get('relation')=='enemy'}
  private_positions={ident:dict(xyz=list(target['xyz']),observed_frame=target['observed_frame']) for ident,target in getattr(collector,'private_targets',{}).items() if ident in current}
  context_args=[collector.private_formations,collector.private_regions,contacts,collector.visibility_proof_path,private_positions]
  if any(mission_limits(g) for g in self.evidence['grants']):context_args.append(getattr(collector,'mission_context',None))
  await asyncio.to_thread(self.executor.update_context,*context_args)
  for job in host.agent.jobs()['jobs']:
   if job['module']=='build' or not job.get('host_dispatch_candidate') or job['task_id'] in self.sent:continue
   versions=dict(job['formation_versions']);identifiers=list(job['formation_ids'])
   grant=next((g for g in self.evidence['grants'] if (g['module'],g['purpose'])==(job['module'],job['purpose'])),None)
   reserve=getattr(host,'reserve_controller',None)
   held=bool(grant and grant.get('executor_directory') in PAID_CONTROLLER_DIRECTORIES and reserve is not None and len(identifiers)==1 and reserve.owns_formation(identifiers[0]))
   if reserve is not None and reserve.owns_channel() and not held:continue
   if grant and grant.get('executor_directory') in PAID_CONTROLLER_DIRECTORIES and not held:continue
   if held:
    formation=reserve.formation(identifiers[0]);private=reserve.private_formation(identifiers[0])
    if formation.get('available') is not True or formation['version']!=versions.get(identifiers[0]):continue
    private_formations={identifiers[0]:private}
   else:private_formations=collector.private_formations
   if not identifiers or any(fid not in private_formations or private_formations[fid]['version']!=versions[fid] or fid in collector.formations.reserved for fid in identifiers):continue
   continuous=mission_limits(grant) if grant else None
   target=getattr(collector,'private_targets',{}).get(job.get('target_contact_id')) if continuous else None
   if continuous and (not isinstance(target,dict) or type(target.get('object_id')) is not int or target['object_id']<=0 or target.get('owner_player_id')==host.binding.player_id):continue
   frame=int(host.last_snapshot['game_time_seconds']*15);expiry=frame+continuous['duration_frames'] if continuous else int(job['expires_at_game_seconds']*15)
   if held:
    expiry=reserve.hard_deadline(identifiers[0])
    if not frame<expiry<=frame+MAX_DURATION_FRAMES:continue
   if not continuous and expiry-frame<300:
    # No queue or reservation exists yet; this is an explicit local preflight rejection.
    continue
   if not continuous and expiry-frame>900:expiry=frame+900
   self.sequence+=1;command=str(uuid.uuid4());task=job['task_id']
   allowed=sorted({oid for fid in identifiers for oid in private_formations[fid]['object_ids']})
   self.sent[task]=dict(task_id=task,command_id=command,seq=self.sequence,module=job['module'],purpose=job['purpose'],target_contact_id=job.get('target_contact_id'),formation_versions=versions,allowed_object_ids=allowed,object_ids=None,dispatch_frame=frame,expires_frame=expiry,started=False,terminal=False,queued=False)
   if continuous:self.sent[task].update(mission_protocol=PROTOCOL,executor_directory=grant['executor_directory'],retreat_region='home_base',target_object_id=target['object_id'],target_type_hash=target.get('type_hash'),target_owner_player_id=target.get('owner_player_id'),model_plan_id=job.get('plan_id'),model_plan_generation=job.get('generation'),model_plan_expires_game_seconds=job.get('expires_at_game_seconds'))
   if held:self.sent[task]['object_ids']=list(private['object_ids'])
   self.persist()
   if not held:collector.formations.reserve(identifiers)
   if continuous:host.agent.host_commit_task(task,mission_deadline_game_seconds=expiry/15,retreat_region='home_base')
   else:host.agent.host_commit_task(task)
   request=dict(job,command_id=command,seq=self.sequence,session_id=host.binding.session_id,player_id=host.binding.player_id,commander_id=host.binding.commander_id,expires_frame=expiry)
   if continuous:request.update(mission_id=str(uuid.UUID(task)),mission_deadline_game_seconds=expiry/15,retreat_region='home_base')
   try:
    if held:
     # Agent dataclasses retain tuples; the original public wire envelope is
     # JSON. Freeze that representation before hashing or Native validation.
     request=json.loads(json.dumps(request,allow_nan=False))
     source=host.output/('held-mission-'+command+'.json');atomic_json(source,request)
     self.sent[task].update(public_command_path=str(source),public_command_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),controller_id=reserve.config['controller_id'],lease_id=reserve.config['lease_id'],allocation_scope='prebound_paid_pair')
     self.persist()
     await reserve.commit(request,formation,collector.visibility_proof_path,public_command_source=source)
     from held_controller_receipts import receipt_for
     receipt=receipt_for(reserve,self.sent[task],host.binding)
    else:receipt=await asyncio.to_thread(self.executor.submit,request)
   except BaseException:
    host.event('tactical_dispatch_unknown',task_id=task,command_id=command);raise
   if receipt.get('accepted') is True and receipt.get('command_id')==command:
    allocation=receipt.get('object_ids')
    if not isinstance(allocation,list) or not allocation or len(allocation)!=len(set(allocation)) or any(type(oid) is not int or oid not in allowed for oid in allocation):raise ValueError('Invalid tactical allocation')
    if job['module']=='combined_arms' and len(allocation)<2:raise ValueError('Combined task lacks two actors')
    self.sent[task]['object_ids']=list(allocation)
    self.sent[task]['queued']=True;self.counters[job['module']]['accepted']+=1;host.event('tactical_dispatch_accepted',task_id=task,command_id=command,module=job['module'],purpose=job['purpose'])
   elif receipt.get('status')=='no_dispatch_rejected' and receipt.get('accepted') is False:
    if continuous:
     expected=dict(command_id=command,task_id=task,seq=self.sequence,session_id=host.binding.session_id,player_id=host.binding.player_id,commander_id=host.binding.commander_id)
     if any(receipt.get(key)!=value or type(receipt.get(key)) is not type(value) for key,value in expected.items()) or receipt.get('no_dispatch_verified') is not True or receipt.get('dispatch_attempted') is not False or receipt.get('started') is not False or receipt.get('completed') is not False:raise ValueError('Continuous rejection identity or no-dispatch evidence missing')
     self.sent[task]['rejection_receipt']=receipt;self.persist()
     host.agent.certify_mission_not_dispatched(task,evidence_sha256=hashlib.sha256(json.dumps(receipt,sort_keys=True,allow_nan=False).encode()).hexdigest())
    self.feedback(task,'cancelled','prerequisite_missing');collector.formations.release(identifiers);self.sent[task]['terminal']=True;self.counters[job['module']]['rejected']+=1
    host.event('tactical_preflight_rejected',task_id=task,executor_reason_code=receipt.get('reason_code'))
   else:raise RuntimeError('Tactical dispatch outcome unknown')
   self.persist();return

 def verify_completed(self,receipt,entry):
  host=self.host
  if receipt.get('status')!='completed' or receipt.get('completed') is not True or receipt.get('goal_observed') is not True or receipt.get('restoration_verified') is not True:raise ValueError('Tactical completion unproven')
  if entry.get('executor_directory') in PAID_CONTROLLER_DIRECTORIES:
   facts=terminal_facts(host,receipt,entry)
   if facts['qualification'].get('combined_arms_verified') is not True:raise ValueError('Paid pair lacks independently verified effects')
   return
  reports=receipt.get('unit_results',[])
  if not reports:raise ValueError('Tactical completion lacks raw reports')
  verifier=module(ROOT.parent/'tactical/evidence.py','host_tactical_completion_evidence')
  expected_allocation=entry.get('object_ids')
  if not expected_allocation or receipt.get('object_ids')!=expected_allocation:raise ValueError('Tactical allocation changed')
  covered=[];issued_frames=[]
  for result in reports:
   path=Path(result['report']).resolve()
   if not path.is_relative_to(Path(host.session['run_directory']).resolve()):raise ValueError('Completion report outside current match')
   raw=json.loads(path.read_text(encoding='utf-8-sig'))
   if raw.get('session_id')!=host.binding.session_id or raw.get('preflight',{}).get('pid')!=host.session['pid']:raise ValueError('Completion from another match')
   suffix='formation' if entry['module']=='combined_arms' else str(result.get('object_id'))
   if entry['module']=='combined_arms':
    actors=[actor.get('id') for actor in raw.get('units',[])]
    if actors!=expected_allocation or raw.get('request',{}).get('front_id')!=actors[0] or raw.get('request',{}).get('support_id')!=actors[1]:raise ValueError('Formation actor allocation mismatch')
    covered.extend(actors)
   else:
    actor=result.get('object_id')
    if type(actor) is not int or raw.get('preflight',{}).get('selected',{}).get('object_id')!=actor:raise ValueError('Attack actor mismatch')
    covered.append(actor)
   expected_command=str(uuid.uuid5(uuid.UUID(entry['command_id']),suffix))
   expected_task=str(uuid.uuid5(uuid.UUID(receipt['task_id']),suffix))
   if raw.get('request',{}).get('command_id')!=expected_command or raw.get('native',{}).get('command_id')!=expected_command:raise ValueError('Completion command mismatch')
   if raw.get('request',{}).get('task_id')!=expected_task or raw.get('native',{}).get('task_id')!=expected_task:raise ValueError('Completion task mismatch')
   native_seq=raw.get('native',{}).get('seq')
   if type(native_seq) is not int or native_seq<=0 or raw.get('request',{}).get('seq')!=native_seq:raise ValueError('Completion native sequence mismatch')
   issued=raw.get('native',{}).get('issued_frame');returned=raw.get('native',{}).get('returned_frame')
   if type(issued) is not int or type(returned) is not int or not entry['dispatch_frame']<=issued<=returned<=entry['expires_frame']:raise ValueError('Completion exceeds frozen task window')
   issued_frames.append(issued)
   verifier.verify_purpose(entry['module'],entry['purpose'],path,host.session,host.binding.commander_id)
  if len(covered)!=len(set(covered)) or set(covered)!=set(expected_allocation):raise ValueError('Incomplete tactical actor receipts')
  if min(issued_frames)!=execution_from_receipt(receipt,entry)['issued_frame']:raise ValueError('Completion issue frame differs from native trace')

 def verify_disposals(self,receipt,entry):
  """Disposal may release a failed lease; it cannot establish success or AI return."""
  results=receipt.get('unit_results',[])
  if not results:raise ValueError('Failed control release lacks raw evidence')
  for result in results:
   path=Path(result['report']).resolve();run=Path(self.host.session['run_directory']).resolve()
   if not path.is_relative_to(run):raise ValueError('Failure evidence outside current match')
   raw=json.loads(path.read_text(encoding='utf-8-sig'));native=raw.get('native',{})
   release=result.get('control_release',{})
   raw_loss=entry['module'] in ('attack','raid') and native.get('phase')==4 and native.get('error')==32 and native.get('return_verified')!=1
   if not raw_loss and not release.get('disposed_verified') and release.get('semantics')!='actor_id_disposed_exclusive_control_released' and not release.get('evidence_path'):continue
   host=self.host;actor=result.get('object_id')
   if receipt.get('status') not in ('failed','cancelled') or receipt.get('completed') is not False or receipt.get('goal_observed') is not False or release.get('disposed_verified') is not True or release.get('semantics')!='actor_id_disposed_exclusive_control_released' or release.get('restoration_verified') is not True or release.get('return_verified') is not False or execution_from_receipt(receipt,entry)['goal_observed'] is not False:raise ValueError('Disposal cannot claim success or pool return')
   if entry['module'] not in ('attack','raid') or entry.get('object_ids')!=[actor] or type(actor) is not int:raise ValueError('Disposed actor allocation mismatch')
   proof=Path(release['evidence_path']).resolve()
   if not path.is_relative_to(run) or not proof.is_relative_to(run):raise ValueError('Disposal evidence outside current match')
   raw=json.loads(path.read_text(encoding='utf-8-sig'));pre=raw.get('preflight',{});native=raw.get('native',{});request=raw.get('request',{})
   command=str(uuid.uuid5(uuid.UUID(entry['command_id']),str(actor)));task=str(uuid.uuid5(uuid.UUID(receipt['task_id']),str(actor)))
   if raw.get('session_id')!=host.binding.session_id or pre.get('pid')!=host.session['pid'] or pre.get('commander_id')!=host.binding.commander_id or pre.get('selected',{}).get('object_id')!=actor:raise ValueError('Disposal from another actor or match')
   if request.get('command_id')!=command or native.get('command_id')!=command or request.get('task_id')!=task or native.get('task_id')!=task or type(native.get('seq')) is not int or native['seq']<=0 or request.get('seq')!=native['seq']:raise ValueError('Disposal command binding mismatch')
   if not entry['dispatch_frame']<=native.get('issued_frame',0)<entry['expires_frame']:raise ValueError('Disposal issue window mismatch')
   if hashlib.sha256(proof.read_bytes()).hexdigest()!=release.get('evidence_sha256'):raise ValueError('Disposal evidence changed')
   reader={'mission-combat':'mission_readonly_disposal.py','mission-combat-v2':'mission_v2_readonly_disposal.py','mission-combat-v3':'mission_v3_readonly_disposal.py','mission-combat-v4':'mission_v4_readonly_disposal.py','mission-combat-v5':'mission_v5_readonly_disposal.py','mission-combat-v6':'mission_v6_readonly_disposal.py','mission-combat-v7':'mission_v7_readonly_disposal.py'}.get(entry.get('executor_directory'),'readonly_disposal.py')
   verifier=module(ROOT.parent/'tactical'/reader,'host_readonly_disposal_'+reader.replace('.','_'))
   verified=verifier.verify_path(proof,path)
   if verified.get('restoration_verified') is not True or verified.get('disposed_verified') is not True or verified.get('return_verified') is not False or verified.get('completion_claim') is not False:raise ValueError('Disposal control release unproven')

 def verify_scene_release(self,receipt,entry):
  """Scene closure can release a failed mission, never prove troop restoration."""
  results=receipt.get('unit_results',[])
  proofs=[r.get('scene_release') for r in results if r.get('scene_release')]
  if not proofs:
   if receipt.get('scene_disposed_control_release_verified'):raise ValueError('Scene release lacks independent proof')
   return None
  if len(results)!=1 or len(proofs)!=1 or receipt.get('scene_disposed_control_release_verified') is not True or receipt.get('status') not in ('failed','cancelled') or receipt.get('completed') is not False or receipt.get('goal_observed') is not False or receipt.get('restoration_verified') is not False or execution_from_receipt(receipt,entry)['goal_observed'] is not False or execution_from_receipt(receipt,entry)['restoration_verified'] is not False:raise ValueError('Scene release cannot claim goal or restoration')
  if entry.get('mission_protocol')!=PROTOCOL or entry.get('executor_directory') not in ('mission-combat-v7','mission-formation-v4','mission-formation-v5','mission-formation-v6','mission-formation-v7','mission-formation-v8','mission-formation-v9','mission-formation-v10','mission-formation-v12','mission-formation-v17','mission-formation-v18') or receipt.get('object_ids')!=entry.get('object_ids'):raise ValueError('Unapproved scene release scope')
  bound=bound_report(self.host,receipt,entry);proof=proofs[0];path=Path(proof['sidecar_path']).resolve();run=Path(self.host.session['run_directory']).resolve()
  if not path.is_relative_to(run) or hashlib.sha256(path.read_bytes()).hexdigest()!=proof.get('sidecar_sha256'):raise ValueError('Scene release sidecar outside match or changed')
  schema=module(ROOT.parent/'tactical/evidence.py','host_scene_release_schema').executor_schema(entry['executor_directory'])
  name=schema.get('scene_release_reader','scene_terminal_release.py')
  if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid trusted scene reader filename')
  reader_path=ROOT.parent/'tactical'/entry['executor_directory']/name if entry['executor_directory'] in ('mission-formation-v17','mission-formation-v18') else ROOT.parent/'tactical'/name
  reader=module(reader_path,'host_scene_terminal_release')
  verified=reader.verify_path(path,bound['path'])
  if verified.get('source_sha256')!=bound['sha256'] or verified.get('sidecar_sha256')!=proof.get('sidecar_sha256') or verified.get('scene_disposed_control_release') is not True or verified.get('semantics')!='scene_disposed_exclusive_control_released' or any(verified.get(k) is not False for k in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')):raise ValueError('Scene release actual proof failed')
  if entry['executor_directory'] in ('mission-formation-v17','mission-formation-v18'):
   report=bound['report'];config=report['controller_config'];actors=sorted(a['object_id'] for a in verified.get('actors',[]) if a.get('never_held') is False and a.get('released') is True)
   if verified.get('controller_id')!=config['controller_id'] or verified.get('lease_id')!=config['lease_id'] or verified.get('session_id')!=self.host.binding.session_id or verified.get('pid')!=self.host.session['pid'] or actors!=sorted(entry['object_ids']) or verified.get('scene_closed_verified') is not True:raise ValueError('Scene controller actors or lease changed')
  return verified

 async def request_mission_retreats(self):
  if self.executor is None:return
  for request in self.host.agent.pending_mission_retreats():
   entry=self.sent.get(request['task_id'])
   if not entry or entry['terminal'] or entry.get('retreat_request_sent'):continue
   result=await self.request_retreat(entry,request['reason'])
   if result.get('accepted') is True:
    entry['retreat_request_sent']=True;entry['retreat_request_reason']=request['reason'];self.persist()
    self.host.event('mission_retreat_requested',task_id=request['task_id'],reason_code=request['reason'])

 async def request_retreat(self,entry,reason):
  if entry.get('executor_directory') in PAID_CONTROLLER_DIRECTORIES:
   reserve=self.host.reserve_controller
   if reserve.runtime is None or reserve.closed:return dict(accepted=False)
   await asyncio.to_thread(reserve.runtime.request_retreat)
   return dict(accepted=True,task_id=entry['task_id'],reason=reason)
  return await asyncio.to_thread(self.executor.request_mission_retreat,entry['task_id'],reason)

 def observe_mission(self,receipt,entry):
  """Phase telemetry stays separate from independently qualified effects."""
  from battle_agent import MissionObservations
  scene=self.verify_scene_release(receipt,entry)
  if scene:
   self.host.agent.certify_mission_scene_closed(entry['task_id'],evidence_sha256=scene['sidecar_sha256'])
   entry['scene_release_evidence_sha256']=scene['sidecar_sha256']
   return True
  disposals=[unit.get('control_release',{}) for unit in receipt.get('unit_results',[]) if unit.get('control_release',{}).get('disposed_verified') is True]
  if disposals:
   self.verify_disposals(receipt,entry)
   digest=hashlib.sha256(Path(disposals[0]['evidence_path']).read_bytes()).hexdigest()
   self.host.agent.certify_mission_disposed(entry['task_id'],evidence_sha256=digest)
   entry['mission_disposal_evidence_sha256']=digest
   return True  # Preserve its last real phase; death is neither retreat nor return.
  terminal=receipt.get('status') in ('completed','failed','cancelled') and receipt.get('started')
  progress=progress_from_receipt(receipt,entry)
  if progress is None:
   if terminal:raise ValueError('Continuous mission terminal phase evidence missing')
   return True
  facts=terminal_facts(self.host,receipt,entry) if terminal else None
  if facts and facts.get('control_release',{}).get('disposed_verified') is True:
   if receipt.get('status') not in ('failed','cancelled'):raise ValueError('Continuous formation casualty cannot complete')
   self.host.agent.certify_mission_disposed(entry['task_id'],evidence_sha256=facts['sha256'])
   entry['mission_mixed_release_evidence_sha256']=facts['sha256']
   return True
  ceiling=int(self.host.last_snapshot['game_time_seconds']*15)
  if progress['observed_frame']>ceiling and not (terminal and getattr(self,'draining',False)):return False
  bound=progress_evidence(self.host,receipt,entry,progress)
  if bound is None:return False
  contacts=self.host.last_snapshot.get('battlefield',{}).get('contacts',[])
  visible=any(c['contact_id']==entry['target_contact_id'] and c.get('currently_visible') is True and c.get('relation')=='enemy' for c in contacts)
  observations=MissionObservations(target_currently_visible=visible,distance_to_goal=progress['approach_distance'],interference='unknown')
  if facts:
   result=facts['qualification']
   observations=MissionObservations(target_currently_visible=visible,approach_verified=result.get('approach_verified') is True,source_damage_amount=result.get('source_damage_amount',0) if result.get('effect_verified') is True else 0,coordination_verified=result.get('combined_arms_verified') is True,retreat_verified=result.get('retreat_verified') is True,restoration_verified=True,distance_to_goal=progress['approach_distance'],interference='none' if result.get('checks',{}).get('no_native_override') is True else 'unknown')
  # Repeated polls use exactly the same facts for a published native revision.
  if progress!=entry.get('last_mission_progress'):
   telemetry=observations if terminal and getattr(self,'draining',False) else MissionObservations(target_currently_visible=visible,distance_to_goal=progress['approach_distance'],interference='unknown')
   options=dict(observations=telemetry,evidence_sha256=bound['sha256'])
   if terminal and getattr(self,'draining',False):options['verified_terminal_clock']=progress['observed_frame']/15
   self.host.agent.record_mission_progress(entry['task_id'],progress,**options)
   entry['last_mission_progress']=progress
   self.host.event('mission_progress_observed',task_id=entry['task_id'],command_id=entry['command_id'],module=entry['module'],stage=progress['stage'],revision=progress['revision'],observed_frame=progress['observed_frame'],deadline_frame=progress['deadline_frame'],reason=progress['reason'],damage_telemetry=progress['damage'],source_sha256=bound['sha256'])
  if facts:
   self.host.agent.certify_mission_result(entry['task_id'],observations=observations,evidence_sha256=facts['sha256'])
   entry['mission_qualification']=dict(source_report=str(facts['path']),source_sha256=facts['sha256'],effect_verified=facts['qualification'].get('effect_verified') is True,approach_verified=facts['qualification'].get('approach_verified') is True,long_approach_verified=facts['qualification'].get('long_approach_verified') is True,retreat_verified=facts['qualification'].get('retreat_verified') is True,source_damage_amount=observations.source_damage_amount,combined_arms_verified=observations.coordination_verified)
  return True

 async def receive(self):
  if self.executor is None:return
  host=self.host;status=await asyncio.to_thread(self.executor.status)
  reserve=getattr(host,'reserve_controller',None)
  if reserve is not None:
   from held_controller_receipts import receipt_for
   status['ledger']=list(status.get('ledger',[]))+[receipt_for(reserve,e,host.binding) for e in self.sent.values() if e.get('executor_directory') in PAID_CONTROLLER_DIRECTORIES and not e['terminal']]
  await self.request_mission_retreats()
  for receipt in status.get('ledger',[]):
   task=receipt.get('task_id');entry=self.sent.get(task)
   if entry is None or entry['terminal']:continue
   if receipt.get('command_id')!=entry['command_id'] or receipt.get('seq')!=entry['seq'] or receipt.get('session_id')!=host.binding.session_id or receipt.get('commander_id')!=host.binding.commander_id or receipt.get('player_id')!=host.binding.player_id:raise ValueError('Tactical receipt binding mismatch')
   if receipt.get('module')!=entry['module'] or receipt.get('purpose')!=entry['purpose']:raise ValueError('Tactical receipt purpose mismatch')
   if receipt.get('object_ids')!=entry.get('object_ids'):raise ValueError('Tactical allocation changed')
   local_risk=receipt.get('local_risk',{}).get('request')
   if entry.get('executor_directory')=='mission-formation-v12' and local_risk and local_risk.get('request_written') is True and not entry.get('local_risk_recorded'):
    host.agent.request_mission_retreat(task,'target_lost')
    host.event('mission_local_risk_retreat_requested',task_id=task,observed_frame=local_risk.get('observed_frame'),request_frame=local_risk.get('request_frame'),monitor_sha256=local_risk.get('monitor_sha256'),native_acknowledged=False)
    entry['local_risk_recorded']=True
   if receipt.get('started'):
    execution=execution_from_receipt(receipt,entry)
    if execution['issued_frame']>int(host.last_snapshot['game_time_seconds']*15):
     if entry.get('mission_protocol')!=PROTOCOL or not getattr(self,'draining',False) or receipt.get('status') not in ('completed','failed','cancelled'):continue
     if receipt.get('scene_disposed_control_release_verified') is True:self.verify_scene_release(receipt,entry)
     elif any(unit.get('control_release',{}).get('disposed_verified') is True for unit in receipt.get('unit_results',[])):self.verify_disposals(receipt,entry)
     else:terminal_facts(host,receipt,entry)
    if not entry['started']:
     self.feedback(task,'started','ok',dict(execution,goal_observed=False,restoration_verified=False));entry['started']=True
   if entry.get('mission_protocol')==PROTOCOL and not self.observe_mission(receipt,entry):continue
   if receipt.get('status')=='completed':
    if not entry['started']:raise ValueError('Completed tactical task never issued')
    self.verify_completed(receipt,entry);execution=execution_from_receipt(receipt,entry)
    self.feedback(task,'completed','ok',execution);entry['terminal']=True;host.collector.formations.release(entry['formation_versions'])
   elif receipt.get('status') in ('failed','cancelled'):
    if entry['started']:
     scene=self.verify_scene_release(receipt,entry)
     if scene:
      execution=execution_from_receipt(receipt,entry);self.feedback(task,'failed','goal_unobserved',execution);entry['terminal']=True;host.collector.formations.release(entry['formation_versions']);host.event('mission_scene_closed_control_release',task_id=task,evidence_sha256=scene['sidecar_sha256'],restoration_verified=False,return_verified=False,goal_observed=False);continue
     execution=execution_from_receipt(receipt,entry);reason='goal_unobserved' if execution['restoration_verified'] else 'restoration_unverified'
     if execution['restoration_verified']:self.verify_disposals(receipt,entry)
     self.feedback(task,'failed',reason,execution);entry['terminal']=True
     if execution['restoration_verified']:host.collector.formations.release(entry['formation_versions'])
     else:
      self.persist();raise RuntimeError('Tactical restoration unverified')
    elif receipt.get('no_dispatch_verified') is True or receipt.get('dispatch_attempted') is False or entry.get('executor_directory') in PAID_CONTROLLER_DIRECTORIES:
     if entry.get('mission_protocol')==PROTOCOL:
      proof=pre_dispatch_facts(host,receipt,entry)
      entry['rejection_receipt']=receipt;self.persist();host.agent.certify_mission_not_dispatched(task,evidence_sha256=proof['sha256'])
     self.feedback(task,'cancelled','prerequisite_missing');entry['terminal']=True;host.collector.formations.release(entry['formation_versions'])
    else:raise RuntimeError('Tactical native outcome unknown')
   elif receipt.get('status')=='unknown':raise RuntimeError('Tactical native outcome unknown')
  self.persist()
  atomic_json(host.output/'tactical-status.json',dict(state=status.get('state'),counters=self.counters,manifest=status.get('manifest'),ledger=status.get('ledger')))

 async def stop(self):
  if self.executor is None:return dict(state='not_started')
  self.draining=True
  for entry in self.sent.values():
   if entry.get('mission_protocol')==PROTOCOL and not entry['terminal']:await self.request_retreat(entry,'host_stop')
  # Continuous withdrawal may traverse the verified outbound route in reverse.
  # Continue polling feedback while native logic owns the units; stop is final.
  deadline=time.monotonic()+(135 if any(e.get('mission_protocol')==PROTOCOL and not e['terminal'] for e in self.sent.values()) else 0)
  while any(e.get('mission_protocol')==PROTOCOL and not e['terminal'] for e in self.sent.values()) and time.monotonic()<deadline:
   reserve=getattr(self.host,'reserve_controller',None)
   if reserve is not None and reserve.runtime is not None and not reserve.closed:await reserve.poll()
   await self.receive();await asyncio.sleep(.2)
  reserve=getattr(self.host,'reserve_controller',None)
  if reserve is not None and reserve.runtime is not None and not reserve.closed:await reserve.stop()
  status=await asyncio.to_thread(self.executor.stop);deadline=time.monotonic()+35
  while status.get('state')=='return_pending' and time.monotonic()<deadline:
   await asyncio.sleep(.2);status=await asyncio.to_thread(self.executor.stop)
  await self.receive()
  if status.get('state')!='stopped':raise RuntimeError('Tactical restoration unverified')
  return status
