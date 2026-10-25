"""Trusted async tactical host facade. Model tasks remain locked pending evidence.
No attach/calls on import or start. All native actions go through reviewed serial
lease subprocesses; an enqueue acknowledgement never means a completed task.
"""
import ctypes as c,hashlib,json,math,queue,subprocess,sys,threading,time,uuid
from pathlib import Path
import importlib.util
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from mobility_guard import mobility_status
spec=importlib.util.spec_from_file_location('tactical_reusable_backend',HERE/'reusable/lease.py');backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
def trusted_executor(directory):
 spec=importlib.util.spec_from_file_location('tactical_executor_scopes',HERE/'evidence.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.executor_schema(directory)

def trusted_filename(schema,key,default):
 name=schema.get(key,default)
 if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.py') or name=='.py':raise ValueError('invalid_trusted_executor_filename')
 return name

def runtime_backend(directory):
 schema=trusted_executor(directory);name=trusted_filename(schema,'wrapper_filename','lease.py');spec=importlib.util.spec_from_file_location('tactical_runtime_'+directory.replace('-','_'),HERE/directory/name);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return schema,module

def combat_qualifier_path(directory,schema):
 if directory in ['mission-combat-v6','mission-combat-v7']:
  return HERE/trusted_filename(schema,'runtime_qualifier_filename',directory.replace('-','_')+'_qualification.py')
 names={'mission-combat-v5':'mission_combat_v5_qualification_v2.py','mission-combat-v4':'mission_combat_v4_qualification.py','mission-combat-v3':'mission_combat_v3_qualification.py','mission-combat-v2':'mission_combat_v2_qualification.py'}
 return HERE/names.get(directory,'mission_combat_qualification.py')

def formation_qualifier(directory,schema):
 name=trusted_filename(schema,'qualifier_filename','formation_mission_qualification.py');spec=importlib.util.spec_from_file_location('trusted_formation_mission_qualification',HERE/directory/name);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class TacticalExecutor:
 def __init__(self,session_path,natural_observation_path,commander_id,player_id=3):
  if player_id!=3:raise ValueError('only_bound_player3_verified')
  self.session_path=Path(session_path);self.natural_path=Path(natural_observation_path);self.commander_id=str(uuid.UUID(str(commander_id)));self.player_id=player_id
  self.lock=threading.RLock();self.pending=queue.Queue();self.stopping=threading.Event();self.ledger={};self.command_ids={};self.task_ids={};self.last_seq=0;self.native_seq=0;self.active=None;self.worker=None;self.formations={};self.regions={};self.capabilities={};self.capability_grants={};self.public_fingerprints={};self.reserved_units=set();self.contacts={};self.private_visible_positions={};self.visibility_proof_path=None;self.mission_context=None;self.state='not_started'
 def _audit(self,event):
  if not hasattr(self,'audit'):return
  with self.audit.open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n');f.flush();__import__('os').fsync(f.fileno())
 def _binding(self):
  if self.session_path.read_bytes()!=self.session_raw:raise ValueError('session_changed')
  if hashlib.sha256(self.registry_path.read_bytes()).hexdigest()!=self.registry_digest:raise ValueError('registry_changed')
  if hashlib.sha256(self.package.read_bytes()).hexdigest()!=self.session['mod_sha256']:raise ValueError('package_changed')
 def start(self):
  with self.lock:
   if self.state!='not_started':raise ValueError('already_started')
   pre,self.session,self.session_raw,self.package,self.registry_path,self.registry_digest,m=backend.readiness(self.session_path)
   try:
    if pre['commander_id']!=self.commander_id:raise ValueError('commander_binding_mismatch')
    self.logic=int(pre['logic'],0);self.owner=int(pre['owner'],0);self.native_personality=pre['personality']
   finally:m.close()
   obs=json.loads(self.natural_path.read_text(encoding='utf-8-sig'));backend.compatible_natural_calls(obs,self.session['pid'])
   if obs['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')
   self.native_seq=int(time.monotonic()*1000)&0x7fffffff;self.run=Path(self.session['run_directory']);self.audit=self.run/'tactical-executor.jsonl';self.state='running';self.worker=threading.Thread(target=self._work,daemon=True);self.worker.start();self._audit(dict(event='started',session_id=self.session['session_id'],capabilities=self.capabilities));return self.status()
 def update_context(self,formations,regions,contacts=None,visibility_proof_path=None,private_visible_positions=None,mission_context=None):
  """Trusted host only: own ObjectID rosters/version and known region points.
  No pointer, enemy memory or model supplied target point is admitted here.
  """
  with self.lock:
   self._binding();checked={}
   for ident,f in formations.items():
    if not isinstance(ident,str) or not ident or set(f)!={'version','object_ids','role'}:raise ValueError('formation_fields')
    if type(f['version']) is not int or f['version']<1 or not isinstance(f['role'],str) or not 1<=len(f['object_ids'])<=8 or any(type(x) is not int or x<1 for x in f['object_ids']) or len(set(f['object_ids']))!=len(f['object_ids']):raise ValueError('formation_invalid')
    checked[ident]=dict(f,object_ids=list(f['object_ids']))
   points={}
   for ident,r in regions.items():
    if not isinstance(ident,str) or set(r)!={'xyz','observed_frame'} or len(r['xyz'])!=3 or not all(type(v) in [int,float] and math.isfinite(v) for v in r['xyz']):raise ValueError('region_invalid')
    points[ident]=dict(r,xyz=list(r['xyz']))
   self.formations=checked;self.regions=points
   if mission_context is not None and (not isinstance(mission_context,dict) or mission_context.get('schema_version')!=1):raise ValueError('mission_context_schema')
   self.mission_context=json.loads(json.dumps(mission_context,allow_nan=False))
   if contacts is not None:self.contacts={x['contact_id']:dict(x) for x in contacts if x.get('currently_visible') is True and x.get('relation')=='enemy'}
   if private_visible_positions is not None:
    checked_positions={}
    for ident,value in private_visible_positions.items():
     if ident not in self.contacts or set(value)!={'xyz','observed_frame'} or type(value['observed_frame']) is not int or value['observed_frame']<0 or not isinstance(value['xyz'],(list,tuple)) or len(value['xyz'])!=3 or not all(type(v) in [int,float] and math.isfinite(v) for v in value['xyz']):raise ValueError('private_visible_position_invalid')
     checked_positions[ident]=dict(xyz=list(value['xyz']),observed_frame=value['observed_frame'])
    self.private_visible_positions=checked_positions
   if visibility_proof_path is not None:self.visibility_proof_path=str(Path(visibility_proof_path).resolve())
 def manifest(self):
  result=dict(schema_version=1,source='game_bridge',player_id=3,force_fraction=dict(request_min=.01,request_max=1.,allocation_cap=.5,denominator='all_live_verified_controllable_conscript_flak_and_proven_twinblade_union',rounding='floor',minimum_units=dict(main_attack=1,harass_economy=1,coordinate_force=2)),expiry=dict(min_remaining_frames=300,max_remaining_frames=900,logical_fps=15),lease_max_frames=180,return_observation_frames=90,coordinate_force=dict(roles=['infantry','anti_air'],unit_count=2,stages=['support_hold_front_advance','support_advance_behind_front'],max_move_calls=2 if self.capability_grants.get(('combined_arms','coordinate_force'),{}).get('executor_directory')=='formation-stop-v2' else 3,max_stop_calls=2 if self.capability_grants.get(('combined_arms','coordinate_force'),{}).get('executor_directory')=='formation-stop-v2' else 0,advance_distance=80,rear_spacing=80,support_target='front_initial_position'),attack=dict(unit_count=1,max_attack_orders=1,native_burst=True,weapon_mode='Conscript_normal_button_prepares_AK_when_required' if any(g.get('executor_directory')=='ordered-combo' for g in self.capability_grants.values()) else 'Conscript_AK47_current_getter_required',lease_frames=180,stop_before_and_after=True,target='current_verified_visible_ground_contact') if any(g.get('executor_directory') in ['ordered-attack','ordered-combo'] for g in self.capability_grants.values()) else dict(unit_count=1,max_shots=1,target='current_verified_visible_contact'),purpose_actor_roles={module:{purpose:grant['stop_schema']['actor_roles'] for (registered_module,purpose),grant in self.capability_grants.items() if registered_module==module} for module in self.capabilities},supported_purposes={k:list(v) for k,v in self.capabilities.items()},evidence=[{key:value for key,value in g.items() if key!='raw_assessment'} for g in self.capability_grants.values()])
  mission_grants=[g for g in self.capability_grants.values() if g.get('stop_schema',{}).get('mission_protocol')=='continuous_tactical_v1']
  if mission_grants:
   result.update(mission_protocol='continuous_tactical_v1',mission_duration_frames=4500,lease_max_frames=4500,expiry=dict(min_remaining_frames=300,max_remaining_frames=4500,logical_fps=15),mission_stages=['approach','prepare','engage','retreat','restored'],retreat_point_source='trusted_own_base_adjacent_sample_or_actor_origin')
   if any(g.get('executor_directory') in ['mission-combat','mission-combat-v2','mission-combat-v3','mission-combat-v4','mission-combat-v5','mission-combat-v6','mission-combat-v7'] for g in mission_grants):result['attack']=dict(unit_count=1,max_attack_orders=1,native_burst=True,weapon_mode='normal_conscript_button_prepares_AK',approach_frames=2100,engage_frames=300,retreat_frames=1800,max_approach_moves=12,max_retreat_moves=3 if any(g.get('executor_directory') in ['mission-combat-v3','mission-combat-v4','mission-combat-v5','mission-combat-v6','mission-combat-v7'] for g in mission_grants) else 24,target='current_verified_visible_ground_contact')
  if any(g.get('executor_directory')=='mission-combat-v6' for g in mission_grants):result['attack'].update(pre_approach_loadout='normal_button_AK',engage_frames_is_limit=True,engage_min_frames=180,engage_max_frames=300,engagement_policy='bounded_single_order_native_burst',damage_goal_cap=150.,damage_goal_fraction=.2,engagement_distance_policy=150.,range_and_los='native_order_plus_observed_source_damage')
  if any(g.get('executor_directory')=='mission-combat-v7' for g in mission_grants):result['attack'].update(pre_approach_loadout='normal_button_AK',engage_frames=60,engage_frames_is_limit=True,engage_min_frames=60,engage_max_frames=60,engagement_policy='brief_raid_single_order_native_burst',damage_goal_cap=30.,damage_goal_fraction=.2,retreat_hp_fraction=.8,engagement_distance_policy=150.,range_and_los='native_order_plus_observed_source_damage')
  if any(g.get('executor_directory') in ('mission-formation-v5','mission-formation-v6') for g in mission_grants):result['coordinate_force']=dict(roles=['infantry','anti_air'],unit_count=2,navigation_mode='native_leader_actual_breadcrumbs',stages=['approach_together','prepare','engage','retreat','restore'],follower_goal_source='verified_actual_owned_breadcrumbs',retreat_goal_source='each_actor_actual_origin',target='current_verified_visible_ground_contact',mission_duration_frames=4500,physical_arrival_samples=3,arrival_distance=15)
  return result
 def grant_capability(self,module,purpose,source_report):
  """Trusted host only; evidence is independently recomputed and revision pinned."""
  with self.lock:
   self._binding();spec=importlib.util.spec_from_file_location('tactical_evidence',HERE/'evidence.py');verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier);grant=verifier.verify_purpose(module,purpose,source_report,self.session,self.commander_id)
   self.capability_grants[(module,purpose)]=grant;self.capabilities[module]=tuple(sorted(set(self.capabilities.get(module,()))|{purpose}));self._audit(dict(event='capability_granted',grant=grant));return grant
 def submit(self,task):
  """Purpose-scoped model task. Resolves only trusted own formation/contact IDs."""
  with self.lock:
   command=None;original_task=task.get('task_id');seq=task.get('seq');prior_commands=set(self.ledger)
   try:
    if self.state!='running':raise ValueError('executor_stopped')
    self._binding();module,purpose=task.get('module'),task.get('purpose')
    if purpose not in self.capabilities.get(module,()):raise ValueError('tactical_capability_not_verified')
    original_task=task['task_id'];task_id=str(uuid.UUID(str(original_task)));generation=task.get('generation',0);plan=str(task.get('plan_id',''));command=str(uuid.UUID(str(task['command_id']))) if task.get('command_id') else str(uuid.uuid5(uuid.UUID(task_id),plan+':'+str(generation)))
    immutable={key:task.get(key) for key in ['module','purpose','target_region','target_contact_id','formation_ids','formation_versions','required_roles','force_fraction','plan_id','generation','expires_at_game_seconds','expires_frame','seq','mission_id','mission_deadline_game_seconds','retreat_region']};fingerprint=json.dumps(immutable,sort_keys=True)
    if command in self.public_fingerprints:
     if self.public_fingerprints[command]!=fingerprint:raise ValueError('command_id_conflict')
     return dict(self.ledger[command])
    for key,value in [('session_id',self.session['session_id']),('player_id',3),('commander_id',self.commander_id)]:
     if key in task and task[key]!=value:raise ValueError('task_binding_mismatch')
    ids=task.get('formation_ids',());versions=dict(task.get('formation_versions',()));required_roles=set(task.get('required_roles',()))
    if not 1<=len(ids)<=3 or len(set(ids))!=len(ids) or set(versions)!=set(ids):raise ValueError('formation_binding_missing')
    roster=[]
    for ident in ids:
     formation=self.formations.get(ident)
     if not formation or type(versions[ident]) is not int or versions[ident]!=formation['version']:raise ValueError('formation_version_changed')
     roster.extend(formation['object_ids'])
    if len(roster)!=len(set(roster)) or self.reserved_units.intersection(roster):raise ValueError('formation_overlap_or_inflight')
    fraction=task.get('force_fraction')
    if type(fraction) not in [int,float] or isinstance(fraction,bool) or not math.isfinite(fraction) or not .01<=fraction<=1.:raise ValueError('force_fraction_bounds')
    pre,ss,raw,package,rp,d,m=backend.readiness(self.session_path)
    try:
     now=m.u32(self.logic+0x50)
     if m.u32(self.logic+0x15c):raise ValueError('game_paused')
     expiry_frame=task.get('expires_frame')
     if expiry_frame is None:
      expiry=task.get('expires_at_game_seconds')
      if type(expiry) not in [int,float] or isinstance(expiry,bool) or not math.isfinite(expiry):raise ValueError('task_expiry_bounds')
      expiry_frame=int(expiry*15)
     grant=self.capability_grants.get((module,purpose),{});mission_schema=grant.get('stop_schema',{});continuous=mission_schema.get('mission_protocol')=='continuous_tactical_v1';max_duration=mission_schema.get('mission_duration_frames',0) if continuous else 900
     if type(expiry_frame) is not int or not 300<=expiry_frame-now<=max_duration:raise ValueError('task_expiry_bounds')
     all_live=[u for u in pre['units'] if u['eligible'] and mobility_status(m,int(u['address'],0))['independently_movable']]
     if continuous and grant.get('executor_directory') in ['mission-combat-v5','mission-combat-v6','mission-combat-v7','mission-formation-v3','mission-formation-v4','mission-formation-v5','mission-formation-v6']:
      admission_name=trusted_filename(trusted_executor(grant['executor_directory']),'actor_admission_filename','mission_actor_admission.py')
      all_live=self._surface_ground_candidates(m,all_live,pre['owner']) if admission_name=='mission_actor_admission.py' else self._surface_ground_candidates(m,all_live,pre['owner'],admission_name)
      if not all_live:raise ValueError('native_ground_surface_evidence_unavailable_not_no_army')
     candidates={u['object_id']:u for u in all_live if u['object_id'] in roster};allocation_cap=min(.5,float(fraction));budget=int(len(all_live)*allocation_cap)
     if budget<1:raise ValueError('force_budget_too_small')
     seq=task.get('seq',self.last_seq+1)
     region_id=task.get('target_region');region=self.regions.get(region_id)
     if not region or now-region['observed_frame']>60 or now<region['observed_frame']:raise ValueError('target_region_not_current_known')
     region_xyz=region['xyz'];receipt=None
     if (module,purpose) in [('attack','main_attack'),('raid','harass_economy')]:
      contact=self.contacts.get(task.get('target_contact_id'))
      if not contact or contact.get('region_id')!=region_id or purpose=='harass_economy' and contact.get('role')!='economy' or not self.visibility_proof_path:raise ValueError('current_visible_target_required')
      if len(required_roles)!=1 or not required_roles.issubset({'infantry','anti_air'}):raise ValueError('single_actor_role_required')
      requested_role=next(iter(required_roles));roles={0x19ab11af:'infantry',0x2c358c61:'anti_air'}
      if contact.get('role')=='air' and requested_role!='anti_air':raise ValueError('air_target_requires_anti_air')
      candidates={oid:u for oid,u in candidates.items() if roles.get(int(u['type_hash'],0))==requested_role}
      if self.capability_grants.get((module,purpose),{}).get('executor_directory') in ['ordered-attack','ordered-combo','mission-combat','mission-combat-v2','mission-combat-v3','mission-combat-v4','mission-combat-v5','mission-combat-v6','mission-combat-v7']:
       if contact.get('role') not in ['infantry','armor','structure','economy']:raise ValueError('ordered_ground_target_scope_required')
       sys.path.insert(0,str(HERE));from inspect_own_weapons import active_weapon
       ak_candidates={}
       for oid,u in candidates.items():
        try:
         weapon=active_weapon(m,int(u['address'],0)).get('selected')
         if weapon and (weapon.get('template_id')=='0x447ea26e' and type(weapon.get('ammo')) is int and 1<=weapon['ammo']<=3 or weapon.get('template_id')=='0x41872ecc' and self.capability_grants.get((module,purpose),{}).get('executor_directory') in ['ordered-combo','mission-combat','mission-combat-v2','mission-combat-v3','mission-combat-v4','mission-combat-v5','mission-combat-v6','mission-combat-v7']):ak_candidates[oid]=u
        except (ValueError,RuntimeError,KeyError):pass
       candidates=ak_candidates
      if not candidates:raise ValueError('required_role_ground_surface_or_weapon_evidence_unavailable' if continuous and grant.get('executor_directory') in ['mission-combat-v5','mission-combat-v6','mission-combat-v7'] else 'no_live_actor_for_required_role_or_verified_weapon')
      private_position=self.private_visible_positions.get(contact['contact_id']);selection_point=region_xyz;selection_basis='region_centroid_fallback'
      if private_position and 0<=now-private_position['observed_frame']<=15:selection_point=private_position['xyz'];selection_basis='fresh_private_visible_contact'
      selected=min(candidates.values(),key=lambda u:math.hypot(u['xyz'][0]-selection_point[0],u['xyz'][1]-selection_point[1]));mission_input=None
      if continuous:
       mission_input=dict(self.mission_context or {'schema_version':1},expires_frame=expiry_frame)
       cs=importlib.util.spec_from_file_location('trusted_combat_mission_contract',HERE/grant['executor_directory']/'mission_contract.py');cm=importlib.util.module_from_spec(cs);cs.loader.exec_module(cm);mission_input=cm.validate_mission(mission_input,dict(pre,selected=selected),m,expiry_frame)
      receipt=self.submit_attack_probe(command_id=command,task_id=task_id,seq=seq,object_id=selected['object_id'],target_contact_id=contact['contact_id'],visibility_proof_path=self.visibility_proof_path,mission_input=mission_input)
     elif (module,purpose)==('combined_arms','coordinate_force'):
      if continuous:
       if budget<2 or required_roles!={'infantry','anti_air'}:raise ValueError('two_roles_force_budget_required')
       contact=self.contacts.get(task.get('target_contact_id'))
       if not contact or contact.get('region_id')!=region_id or contact.get('role') not in ['infantry','armor','structure','economy'] or not self.visibility_proof_path:raise ValueError('current_visible_ground_target_required')
       context=self.mission_context or {}
       if grant.get('executor_directory') not in ('mission-formation-v5','mission-formation-v6') and (not isinstance(context.get('formation_history_dir'),str) or not Path(context['formation_history_dir']).is_dir()):raise ValueError('private_formation_history_required')
       fronts=[u for u in candidates.values() if int(u['type_hash'],0)==0x19ab11af and u.get('hp',0)>=50];supports=[u for u in candidates.values() if int(u['type_hash'],0)==0x2c358c61 and u.get('hp',0)>=50]
       private_position=self.private_visible_positions.get(contact['contact_id']);point=private_position['xyz'] if private_position and 0<=now-private_position['observed_frame']<=15 else region_xyz
       pairs=[(math.hypot(front['xyz'][0]-point[0],front['xyz'][1]-point[1]),front,support) for front in fronts for support in supports if 25<=math.hypot(front['xyz'][0]-support['xyz'][0],front['xyz'][1]-support['xyz'][1])<=180]
       if not pairs:raise ValueError('no_mission_two_role_pair')
       mission_input=dict(context,schema_version=1,expires_frame=expiry_frame)
       if grant.get('executor_directory') in ('mission-formation-v4','mission-formation-v5','mission-formation-v6'):
        # The wrapper plans from the positions proven stopped by the native
        # lease. A route made here would age while actors still follow AI.
        mission_input.pop('route',None)
        _,front,support=min(pairs,key=lambda pair:self._planning_pair_priority(pair,point))
        if grant.get('executor_directory') in ('mission-formation-v5','mission-formation-v6'):
         mission_input=dict(schema_version=1,session_id=self.session['session_id'],pid=self.session['pid'],player_id=3,front_id=front['object_id'],support_id=support['object_id'],target_contact_id=contact['contact_id'],navigation_mode='native_leader_actual_breadcrumbs',expires_frame=expiry_frame)
       elif grant.get('executor_directory')=='mission-formation-v3':
        _,front,support,route_plan=self._role_route_pair(context,pre,point,all_live,pairs);mission_input['route']=route_plan['route'];mission_input['route_planner']='positive_ground_own_positions_role_aware';mission_input['route_planner_sha256']=hashlib.sha256((HERE/'mission-formation-v3/role_route_planner.py').read_bytes()).hexdigest()
       else:_,front,support=min(pairs,key=lambda x:x[0])
       receipt=self.submit_formation_probe(command_id=command,task_id=task_id,seq=seq,front_id=front['object_id'],support_id=support['object_id'],dx=80,dy=0,rear_spacing=80,formation_versions=versions,mission_input=mission_input,target_contact_id=contact['contact_id'],visibility_proof_path=self.visibility_proof_path)
      else:
       if budget<2 or len(required_roles)<2 or not {'infantry','anti_air'}.issubset(required_roles):raise ValueError('two_roles_force_budget_required')
       fronts=[u for u in candidates.values() if int(u['type_hash'],0)==0x19ab11af];supports=[u for u in candidates.values() if int(u['type_hash'],0)==0x2c358c61];plans=[]
       for front in fronts:
        vx=region_xyz[0]-front['xyz'][0];vy=region_xyz[1]-front['xyz'][1];length=math.hypot(vx,vy)
        if length<40:continue
        dx=vx/length*80;dy=vy/length*80;goal=[front['xyz'][0],front['xyz'][1]]
        for support in supports:
         distance=math.hypot(support['xyz'][0]-goal[0],support['xyz'][1]-goal[1])
         if 20<=distance<=120 and abs(front['xyz'][2]-support['xyz'][2])<=2:plans.append((distance,front,support,dx,dy))
       if not plans:raise ValueError('no_bounded_two_role_advance')
       _,front,support,dx,dy=min(plans,key=lambda p:p[0]);receipt=self.submit_formation_probe(command_id=command,task_id=task_id,seq=seq,front_id=front['object_id'],support_id=support['object_id'],dx=dx,dy=dy,rear_spacing=80,formation_versions=versions)
     else:raise ValueError('unsupported_verified_purpose')
     if receipt.get('accepted'):
      live=self.ledger[command];live['selection_basis']=selection_basis if (module,purpose) in [('attack','main_attack'),('raid','harass_economy')] else 'trusted_region_direction';live['executor_directory']=self.capability_grants.get((module,purpose),{}).get('executor_directory','formation' if live.get('kind')=='formation' else 'combat-finite');live.update(task_id=original_task,module=module,purpose=purpose,formation_versions=versions,target_region=region_id,expires_frame=expiry_frame,plan_id=plan,generation=generation,requested_force_fraction=fraction,allocation_cap_fraction=allocation_cap,allocated_force_fraction=len(live['object_ids'])/len(all_live),actual_roles=[roles.get(int(candidates[oid]['type_hash'],0)) for oid in live['object_ids']] if (module,purpose) in [('attack','main_attack'),('raid','harass_economy')] else ['infantry','anti_air']);self.reserved_units.update(live['object_ids']);self.public_fingerprints[command]=fingerprint;receipt=dict(live)
     if not receipt.get('accepted'):return self._public_rejection(task,command,original_task,seq,receipt.get('reason_code','task_rejected_before_enqueue'),prior_commands)
     return receipt
    finally:m.close()
   except Exception as error:return self._public_rejection(task,command,original_task,seq,str(error),prior_commands)
 def _surface_ground_candidates(self,memory,units,owner,admission_filename='mission_actor_admission.py'):
  spec=importlib.util.spec_from_file_location('trusted_tactical_actor_admission_v1',HERE/trusted_filename({'actor_admission_filename':admission_filename},'actor_admission_filename','mission_actor_admission.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);result=[]
  for unit in units:
   evidence=module.actor_admission(memory,int(unit['address'],0));ground=evidence.get('grounded_status',{})
   if module.verify_evidence(evidence)['verified'] and evidence.get('object_id')==unit['object_id'] and evidence.get('type_hash')==unit['type_hash'] and evidence.get('address')==unit['address'] and evidence.get('owner')==owner:result.append(dict(unit,xyz=list(ground['xyz']),hp=ground['hp'],grounded_status=ground,actor_admission=evidence))
  return result
 @staticmethod
 def _planning_pair_priority(pair,point):
  distance,front,support=pair;f,s=front['xyz'],support['xyz']
  dot=(f[0]-s[0])*(point[0]-f[0])+(f[1]-s[1])*(point[1]-f[1])
  return (dot<0,distance,front['object_id'],support['object_id'])
 def _role_route_pair(self,context,pre,point,all_live,pairs):
  deadline=time.monotonic()+2.;spec=importlib.util.spec_from_file_location('trusted_tactical_role_route_planner',HERE/'mission-formation-v3/role_route_planner.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  def priority(pair):
   distance,front,support=pair;f,s=front['xyz'],support['xyz'];dot=(f[0]-s[0])*(point[0]-f[0])+(f[1]-s[1])*(point[1]-f[1]);return (dot<0,distance)
  for distance,front,support in sorted(pairs,key=priority):
   if time.monotonic()>=deadline:raise ValueError('role_route_planning_total_budget_exhausted')
   try:plan=module.plan_from_history(context['formation_history_dir'],pre,self.session,front,support,point,all_live,planning_deadline=deadline)
   except ValueError:continue
   if time.monotonic()>deadline:raise ValueError('role_route_planning_total_budget_exhausted')
   if plan.get('front_id')!=front['object_id'] or plan.get('support_id')!=support['object_id'] or plan.get('session_id')!=self.session['session_id'] or plan.get('pid')!=self.session['pid'] or not isinstance(plan.get('route'),list) or not 2<=len(plan['route'])<=16:raise ValueError('role_route_planner_binding')
   return distance,front,support,plan
  raise ValueError('no_role_safe_verified_ground_route_for_any_eligible_pair')
 def _public_rejection(self,task,command,original_task,seq,reason,prior_commands):
  """A public refusal is certified only if this command never entered a queue."""
  if command is None:
   try:command=str(uuid.UUID(str(task['command_id']))) if task.get('command_id') else str(uuid.uuid5(uuid.UUID(str(original_task)),str(task.get('plan_id',''))+':'+str(task.get('generation',0))))
   except (ValueError,KeyError,TypeError):command=None
  existing=self.ledger.get(command);never_queued=command is not None and command not in self.ledger and command not in self.command_ids
  valid_identity=command is not None and isinstance(original_task,str) and type(seq) is int and seq>0
  try:uuid.UUID(str(original_task))
  except (ValueError,TypeError):valid_identity=False
  safe=bool(never_queued and valid_identity)
  if existing is not None and command not in prior_commands and not existing.get('dispatch_attempted'):
   # The worker is waiting on this lock. Prevent an incomplete public request
   # from falling back to a calibration backend, but retain unknown ownership.
   existing.update(status='cancelled',reason_code='public_submit_metadata_fault',no_dispatch_verified=False);self.reserved_units.update(existing.get('object_ids',[]))
  return dict(status='no_dispatch_rejected' if safe else 'unknown',accepted=False,started=bool(existing and existing.get('started')),completed=False,reason_code=reason,command_id=command,task_id=original_task,seq=seq,session_id=getattr(self,'session',{}).get('session_id'),player_id=self.player_id,commander_id=self.commander_id,no_dispatch_verified=safe,dispatch_attempted=bool(existing and existing.get('dispatch_attempted')),pre_dispatch=dict(protocol='public_submit_rejection_v1',ledger_entry_created=False,pending_entry_created=False) if safe else None)
 def submit_move_probe(self,*,command_id,task_id,seq,object_ids,target_xyz):
  """Explicit developer calibration API; never used as raid/attack/combined_arms."""
  with self.lock:
   try:
    if self.state!='running':raise ValueError('executor_stopped')
    self._binding();command=str(uuid.UUID(str(command_id)));task=str(uuid.UUID(str(task_id)))
    if type(seq) is not int or seq<1:raise ValueError('sequence_invalid')
    if not 1<=len(object_ids)<=4 or len(set(object_ids))!=len(object_ids) or any(type(x) is not int or x<1 for x in object_ids):raise ValueError('object_ids_invalid')
    if len(target_xyz)!=3 or not all(type(x) in [int,float] and math.isfinite(x) for x in target_xyz):raise ValueError('target_invalid')
    fingerprint=json.dumps(dict(task_id=task,seq=seq,object_ids=object_ids,target_xyz=target_xyz),sort_keys=True)
    if command in self.command_ids:
     if self.command_ids[command]!=fingerprint:raise ValueError('command_id_conflict')
     return dict(self.ledger[command])
    if task in self.task_ids:raise ValueError('task_already_used')
    if seq<=self.last_seq:raise ValueError('sequence_not_increasing')
    pre,s,raw,package,r,d,m=backend.readiness(self.session_path)
    try:
     if m.u32(self.logic+0x15c):raise ValueError('game_paused')
     candidates={x['object_id']:x for x in pre['units'] if x['eligible']}
     if pre['owner']!=hex(self.owner) or pre['personality']!=self.native_personality:raise ValueError('player_lifecycle_changed')
     for oid in object_ids:
      if oid not in candidates:raise ValueError('unit_not_live_own_eligible')
      if not mobility_status(m,int(candidates[oid]['address'],0))['independently_movable']:raise ValueError('unit_garrisoned_or_immobile')
      xyz=candidates[oid]['xyz']
      if not 20<=math.hypot(xyz[0]-target_xyz[0],xyz[1]-target_xyz[1])<=120 or abs(xyz[2]-target_xyz[2])>2:raise ValueError('probe_target_bounds')
    finally:m.close()
    self.last_seq=seq;self.command_ids[command]=fingerprint;self.task_ids[task]=command
    receipt=dict(command_id=command,task_id=task,seq=seq,session_id=self.session['session_id'],commander_id=self.commander_id,player_id=3,module='calibration',purpose='short_move_probe',status='queued',accepted=True,started=False,completed=False,object_ids=list(object_ids),target_xyz=list(target_xyz),unit_results=[],restoration_verified=False,goal_observed=False,issued_frame=0,expires_frame=pre['frame']+900,command_source='game_thread_bridge',interference='unknown',dispatch_attempted=False,wrapper_attempted=False,no_dispatch_verified=False)
    self.ledger[command]=receipt;self.pending.put(command);self._audit(dict(event='probe_queued',receipt=receipt));return dict(receipt)
   except Exception as error:return dict(status='no_dispatch_rejected',accepted=False,started=False,completed=False,reason_code=str(error),task_id=task_id)
 def submit_attack_probe(self,*,command_id,task_id,seq,object_id,target_contact_id,visibility_proof_path,mission_input=None):
  """Trusted developer API for a currently visible contact; no raw target address."""
  with self.lock:
   try:
    if self.state!='running':raise ValueError('executor_stopped')
    self._binding();command=str(uuid.UUID(str(command_id)));task=str(uuid.UUID(str(task_id)))
    if type(seq) is not int or seq<1 or type(object_id) is not int or object_id<1 or not isinstance(target_contact_id,str) or not target_contact_id.startswith('contact_'):raise ValueError('attack_request_invalid')
    proof=Path(visibility_proof_path).resolve()
    if not proof.is_file():raise ValueError('visibility_proof_required')
    fingerprint=json.dumps(dict(task_id=task,seq=seq,object_id=object_id,target_contact_id=target_contact_id,proof=str(proof),mission_input=mission_input),sort_keys=True)
    if command in self.command_ids:
     if self.command_ids[command]!=fingerprint:raise ValueError('command_id_conflict')
     return dict(self.ledger[command])
    if task in self.task_ids:raise ValueError('task_already_used')
    if seq<=self.last_seq:raise ValueError('sequence_not_increasing')
    pre,s,raw,package,r,d,m=backend.readiness(self.session_path,object_id)
    try:
     if m.u32(self.logic+0x15c):raise ValueError('game_paused')
     if pre['owner']!=hex(self.owner) or pre['personality']!=self.native_personality:raise ValueError('player_lifecycle_changed')
     if not mobility_status(m,int(pre['selected']['address'],0))['independently_movable']:raise ValueError('unit_garrisoned_or_immobile')
    finally:m.close()
    self.last_seq=seq;self.command_ids[command]=fingerprint;self.task_ids[task]=command
    receipt=dict(kind='attack',command_id=command,task_id=task,seq=seq,session_id=self.session['session_id'],commander_id=self.commander_id,player_id=3,module='calibration',purpose='visible_attack_probe',status='queued',accepted=True,started=False,completed=False,object_ids=[object_id],target_contact_id=target_contact_id,visibility_proof_path=str(proof),unit_results=[],restoration_verified=False,goal_observed=False,issued_frame=0,expires_frame=pre['frame']+900,command_source='game_thread_bridge',interference='unknown',dispatch_attempted=False,wrapper_attempted=False,no_dispatch_verified=False)
    if mission_input is not None:receipt.update(mission_input=mission_input,expires_frame=mission_input['expires_frame'],mission=None)
    self.ledger[command]=receipt;self.pending.put(command);self._audit(dict(event='attack_probe_queued',receipt=receipt));return dict(receipt)
   except Exception as error:return dict(status='no_dispatch_rejected',accepted=False,started=False,completed=False,reason_code=str(error),task_id=task_id)
 def submit_formation_probe(self,*,command_id,task_id,seq,front_id,support_id,dx,dy,rear_spacing=60,formation_versions=None,mission_input=None,target_contact_id=None,visibility_proof_path=None):
  """Trusted two-role calibration. Holds both leases in one native operation."""
  with self.lock:
   try:
    if self.state!='running':raise ValueError('executor_stopped')
    self._binding();command=str(uuid.UUID(str(command_id)));task=str(uuid.UUID(str(task_id)))
    if type(seq) is not int or seq<1 or type(front_id) is not int or type(support_id) is not int or front_id==support_id:raise ValueError('formation_request_invalid')
    if not all(type(x) in [int,float] and math.isfinite(x) for x in [dx,dy,rear_spacing]) or not 40<=math.hypot(dx,dy)<=100 or not 40<=rear_spacing<=100:raise ValueError('formation_bounds')
    pre,ss,rr,pp,rp,dd,mm=backend.readiness(self.session_path,front_id)
    try:
     selected={u['object_id']:u for u in pre['units'] if u['eligible']}
     if support_id not in selected or int(selected[front_id]['type_hash'],0)!=0x19ab11af or int(selected[support_id]['type_hash'],0)!=0x2c358c61:raise ValueError('two_role_roster_unavailable')
     if not all(mobility_status(mm,int(selected[oid]['address'],0))['independently_movable'] for oid in [front_id,support_id]):raise ValueError('unit_garrisoned_or_immobile')
     if mm.u32(self.logic+0x15c):raise ValueError('game_paused')
     for ident,version in (formation_versions or {}).items():
      if type(version) is not int or ident not in self.formations or self.formations[ident]['version']!=version or not {front_id,support_id}.intersection(self.formations[ident]['object_ids']):raise ValueError('formation_version_binding')
    finally:mm.close()
    fingerprint=json.dumps(dict(task_id=task,seq=seq,front_id=front_id,support_id=support_id,dx=dx,dy=dy,rear_spacing=rear_spacing,formation_versions=dict(formation_versions or {}),mission_input=mission_input,target_contact_id=target_contact_id,visibility_proof_path=visibility_proof_path),sort_keys=True)
    if command in self.command_ids:
     if self.command_ids[command]!=fingerprint:raise ValueError('command_id_conflict')
     return dict(self.ledger[command])
    if task in self.task_ids:raise ValueError('task_already_used')
    if seq<=self.last_seq:raise ValueError('sequence_not_increasing')
    self.last_seq=seq;self.command_ids[command]=fingerprint;self.task_ids[task]=command
    receipt=dict(kind='formation',command_id=command,task_id=task,seq=seq,session_id=self.session['session_id'],commander_id=self.commander_id,player_id=3,module='calibration',purpose='two_role_staged_probe',status='queued',accepted=True,started=False,completed=False,object_ids=[front_id,support_id],dx=dx,dy=dy,rear_spacing=rear_spacing,formation_versions=dict(formation_versions or {}),unit_results=[],restoration_verified=False,goal_observed=False,issued_frame=0,expires_frame=pre['frame']+900,command_source='game_thread_bridge',interference='unknown',dispatch_attempted=False,wrapper_attempted=False,no_dispatch_verified=False)
    if mission_input is not None:receipt.update(mission_input=json.loads(json.dumps(mission_input,allow_nan=False)),target_contact_id=target_contact_id,visibility_proof_path=visibility_proof_path,expires_frame=mission_input['expires_frame'],mission=None)
    self.ledger[command]=receipt;self.pending.put(command);self._audit(dict(event='formation_probe_queued',receipt=receipt));return dict(receipt)
   except Exception as error:return dict(status='no_dispatch_rejected',accepted=False,started=False,completed=False,reason_code=str(error),task_id=task_id)
 def _record_pre_native_rejection(self,r,report,path,child_exit_code,child_command,child_task,seq,directory):
  default='pre_dispatch_formation_v3_contract.py' if directory=='mission-formation-v3' else 'pre_dispatch_formation_v2_contract.py' if directory=='mission-formation-v2' else 'pre_dispatch_v7_contract.py' if directory=='mission-combat-v7' else 'pre_dispatch_v6_contract.py' if directory=='mission-combat-v6' else 'pre_dispatch_v5_contract.py' if directory=='mission-combat-v5' else 'pre_dispatch_v4_contract.py' if directory=='mission-combat-v4' else 'pre_dispatch_v3_contract.py' if directory=='mission-combat-v3' else 'pre_dispatch_v2_contract.py' if directory=='mission-combat-v2' else 'pre_dispatch_contract.py';module_path=HERE/trusted_filename(trusted_executor(directory),'pre_dispatch_helper',default);ps=importlib.util.spec_from_file_location('trusted_no_dispatch_'+directory.replace('-','_'),module_path);pm=importlib.util.module_from_spec(ps);ps.loader.exec_module(pm);verify_no_dispatch=pm.verify_no_dispatch
  proof=verify_no_dispatch(report,child_exit_code=child_exit_code,session=self.session,commander_id=self.commander_id,command_id=child_command,task_id=child_task,seq=seq,object_ids=r['object_ids'],directory=directory,target_contact_id=r.get('target_contact_id'))
  if not proof.get('no_dispatch_verified'):return False
  r.update(no_dispatch_verified=True,dispatch_attempted=False,wrapper_attempted=True,started=False,issued_frame=0,completed=False,goal_observed=False,mission=None)
  r['unit_results'].append(dict(report=str(path),assessment=dict(status='no_dispatch_rejected',checks=proof['checks']),pre_dispatch=proof,child_exit_code=child_exit_code,native={},status='no_dispatch_rejected',expected_restore_mask=trusted_executor(directory)['restore_mask'],control_release=dict(restoration_verified=False,exclusive_control_never_held=True),batch_restoration=dict(restoration_verified=False,exclusive_control_never_held=True)))
  self._audit(dict(event='mission_no_dispatch_verified',command_id=r['command_id'],report=str(path),child_exit_code=child_exit_code,proof=proof));return True
 def _certify_queue_rejection(self,r,reason):
  """Trusted executor entry was accepted but no wrapper could have started."""
  if r.get('wrapper_attempted') is not False or r.get('dispatch_attempted') is not False or r.get('active_report') or r.get('unit_results') or r.get('issued_frame') or r.get('started'):return False
  if self.ledger.get(r.get('command_id')) is not r or r.get('session_id')!=self.session['session_id'] or r.get('commander_id')!=self.commander_id or r.get('player_id')!=self.player_id or type(r.get('seq')) is not int or r['seq']<1 or not r.get('object_ids'):return False
  certificate={key:r[key] for key in ['command_id','task_id','seq','session_id','commander_id','player_id']};certificate['object_ids']=list(r['object_ids']);certificate.update(protocol='executor_queue_rejection_v1',stage='queued_before_wrapper',wrapper_attempted=False,dispatch_attempted=False,native_launch_intent_persisted=False,active_report=None,client_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),reason_code=reason)
  r.update(no_dispatch_verified=True,started=False,completed=False,goal_observed=False,issued_frame=0,mission=None,pre_dispatch=certificate)
  r['execution']=dict(formation_versions=r.get('formation_versions',{}),issued_frame=0,expires_frame=r.get('expires_frame',0),command_source='game_thread_bridge',interference='none',goal_observed=False,restoration_verified=False);self._audit(dict(event='queued_before_wrapper_rejected',certificate=certificate));return True
 def _formation_native_gate(self,directory,report,path):
  """Only a live, independent RPM sidecar can certify a launched zero lease."""
  n=report.get('native',{})
  if directory not in ['mission-formation-v2','mission-formation-v3','mission-formation-v4','mission-formation-v5','mission-formation-v6'] or n.get('phase')!=4 or n.get('issued_frame'):return None
  try:
   name=trusted_filename(trusted_executor(directory),'gate_reader','mission_formation_v3_gate_no_lease.py');spec=importlib.util.spec_from_file_location('trusted_formation_native_gate',HERE/name);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   return module.collect(path,self.session_path)
  except Exception as error:return dict(no_dispatch_verified=False,no_actor_lease_verified=False,error_type=type(error).__name__)
 def _scene_release(self,directory,report,path):
  n=report.get('native',{})
  if directory not in ('mission-combat-v7','mission-formation-v4','mission-formation-v5','mission-formation-v6') or n.get('phase')!=4 or n.get('error')!=31 or not n.get('issued_frame'):return None
  try:
   name=trusted_filename(trusted_executor(directory),'scene_release_reader','scene_terminal_release.py');spec=importlib.util.spec_from_file_location('tactical_scene_release_reader',HERE/name);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
   return reader.collect(path,self.session_path)
  except Exception as error:return dict(scene_disposed_control_release=False,return_verified=False,completed=False,error_type=type(error).__name__)
 def _execute_formation_mission(self,command,r):
  self._validate_task_dispatch(r);self.native_seq+=1;seq=self.native_seq;child_command=str(uuid.uuid5(uuid.UUID(command),'formation'));child_task=str(uuid.uuid5(uuid.UUID(str(r['task_id'])),'formation'));path=self.run/('tactical-task-'+child_command+'.json');r['active_report']=str(path)
  if path.exists():raise ValueError('existing_report_requires_recovery')
  directory=r['executor_directory'];schema,runtime=runtime_backend(directory);qm=formation_qualifier(directory,schema);mission_file=path.with_suffix('.mission.json')
  if mission_file.exists():raise ValueError('existing_mission_input_requires_recovery')
  with mission_file.open('x',encoding='utf-8') as f:json.dump(r['mission_input'],f,allow_nan=False);f.flush();__import__('os').fsync(f.fileno())
  def bound(report):
   rq=report.get('request',{});n=report.get('native',{});pre=report.get('preflight',{})
   return report.get('session_id')==self.session['session_id'] and pre.get('pid')==self.session['pid'] and pre.get('commander_id')==self.commander_id and n.get('commander_id')==self.commander_id and n.get('session_id')==self.session['session_id'] and all(n.get(k)==rq.get(k)==v for k,v in [('command_id',child_command),('task_id',child_task),('seq',seq)]) and rq.get('target_contact_id')==r['target_contact_id'] and rq.get('front_id')==pre.get('selected',{}).get('object_id')==r['object_ids'][0] and rq.get('support_id')==pre.get('support',{}).get('object_id')==n.get('support',{}).get('id')==r['object_ids'][1]
  args=[sys.executable,str(HERE/directory/trusted_filename(schema,'wrapper_filename','lease.py')),'--session',str(self.session_path),'--execute','--front-id',str(r['object_ids'][0]),'--support-id',str(r['object_ids'][1]),'--mission-file',str(mission_file),'--proof-file',r['visibility_proof_path'],'--contact-id',r['target_contact_id'],'--expires-frame',str(r['expires_frame']),'--post-frames','30','--natural',str(self.natural_path),'--command-id',child_command,'--task-id',child_task,'--seq',str(seq),'--output',str(path)]
  with path.with_suffix('.wrapper.log').open('w',encoding='utf-8') as log:
   r['wrapper_attempted']=True;r['dispatch_attempted']=True;child=subprocess.Popen(args,stdout=log,stderr=log)
   while child.poll() is None:
    if self.stopping.wait(.1):self._request_native_stop(path)
    try:self._binding()
    except Exception:self.stopping.set();self._request_native_stop(path)
    if path.exists():
     try:
      current=json.loads(path.read_text(encoding='utf-8'));cn=current.get('native',{})
      if bound(current) and cn.get('issued_frame'):
       with self.lock:r.update(started=True,status='started',issued_frame=r.get('issued_frame') or cn['issued_frame'],mission=qm.progress(current,str(uuid.UUID(str(r['task_id'])))))
     except (ValueError,OSError):pass
  if not path.exists():raise ValueError('child_no_dispatch_report')
  report=json.loads(path.read_text(encoding='utf-8'));n=report.get('native',{})
  if self._record_pre_native_rejection(r,report,path,child.returncode,child_command,child_task,seq,directory):raise ValueError(report['pre_dispatch']['reason_code'])
  if not bound(report):raise ValueError('formation_mission_report_binding_mismatch')
  if n.get('issued_frame'):r.update(started=True,issued_frame=r.get('issued_frame') or n['issued_frame'])
  r['mission']=qm.progress(report,str(uuid.UUID(str(r['task_id']))));assessment=qm.qualify(report)
  restoration=qm.control_release(report) if hasattr(qm,'control_release') else dict(restoration_verified=assessment.get('restoration_verified',False),semantics='native_pool_return_if_raw_verified')
  gate_proof=self._formation_native_gate(directory,report,path);r['no_dispatch_verified']=bool(gate_proof and gate_proof.get('no_actor_lease_verified'))
  scene_release=self._scene_release(directory,report,path);r['scene_disposed_control_release_verified']=bool(scene_release and scene_release.get('scene_disposed_control_release') is True)
  result=dict(report=str(path),assessment=assessment,native=n,expected_restore_mask=8191,batch_restoration=restoration,scene_release=scene_release,native_gate_no_lease=gate_proof,child_exit_code=child.returncode);r['unit_results'].append(result);self._audit(dict(event='formation_mission_feedback',command_id=command,**result))
  if child.returncode!=0 or assessment.get('status')!=schema['success'] or not restoration.get('restoration_verified'):raise ValueError('formation_mission_not_verified')
  r.update(status='completed',completed=True,goal_observed=True,restoration_verified=True)
 def _execute_formation(self,command,r):
  if r.get('executor_directory') in ['mission-formation','mission-formation-v2','mission-formation-v3','mission-formation-v4','mission-formation-v5','mission-formation-v6']:return self._execute_formation_mission(command,r)
  self._validate_task_dispatch(r);self.native_seq+=1;unit_command=uuid.uuid5(uuid.UUID(command),'formation');unit_task=uuid.uuid5(uuid.UUID(r['task_id']),'formation');path=self.run/('tactical-task-'+str(unit_command)+'.json');r['active_report']=str(path)
  if path.exists():raise ValueError('existing_report_requires_recovery')
  directory=r.get('executor_directory','formation');schema,runtime=runtime_backend(directory)
  if schema['kind']!='formation':raise ValueError('executor_kind_mismatch')
  mask=schema['restore_mask']
  args=[sys.executable,str(HERE/directory/trusted_filename(schema,'wrapper_filename','lease.py')),'--session',str(self.session_path),'--execute','--front-id',str(r['object_ids'][0]),'--support-id',str(r['object_ids'][1]),'--dx',str(r['dx']),'--dy',str(r['dy']),'--rear-spacing',str(r['rear_spacing']),'--natural',str(self.natural_path),'--command-id',str(unit_command),'--task-id',str(unit_task),'--seq',str(self.native_seq),'--output',str(path)]
  with path.with_suffix('.wrapper.log').open('w',encoding='utf-8') as log:
   r['wrapper_attempted']=True;r['dispatch_attempted']=True;child=subprocess.Popen(args,stdout=log,stderr=log)
   while child.poll() is None:
    if self.stopping.wait(.1):self._request_native_stop(path);time.sleep(.1)
    try:self._binding()
    except Exception:self.stopping.set();self._request_native_stop(path)
    if path.exists():
     try:
      current=json.loads(path.read_text(encoding='utf-8'));cn=current.get('native',{});rq=current.get('request',{})
      if cn.get('issued_frame',0) and cn.get('seq')==self.native_seq and cn.get('commander_id')==self.commander_id and cn.get('session_id')==self.session['session_id'] and cn.get('command_id')==str(unit_command) and cn.get('task_id')==str(unit_task) and current.get('session_id')==self.session['session_id'] and rq.get('front_id')==r['object_ids'][0] and rq.get('support_id')==r['object_ids'][1]:
       with self.lock:r['started']=True;r['status']='started';r['issued_frame']=r.get('issued_frame') or cn['issued_frame']
     except (ValueError,OSError):pass
  if not path.exists():raise ValueError('child_no_dispatch_report')
  report=json.loads(path.read_text(encoding='utf-8'));n=report.get('native',{});rq=report.get('request',{});units=report.get('units',[])
  if report.get('session_id')!=self.session['session_id'] or report.get('preflight',{}).get('pid')!=self.session['pid'] or report.get('preflight',{}).get('commander_id')!=self.commander_id or rq.get('command_id')!=str(unit_command) or rq.get('task_id')!=str(unit_task) or rq.get('seq')!=self.native_seq or n.get('command_id')!=str(unit_command) or n.get('task_id')!=str(unit_task) or n.get('seq')!=self.native_seq or [x.get('id') for x in units]!=r['object_ids']:raise ValueError('formation_report_binding_mismatch')
  if n.get('issued_frame',0):r['started']=True;r['issued_frame']=r.get('issued_frame') or n['issued_frame']
  spec=importlib.util.spec_from_file_location('tactical_restoration',HERE/'restoration.py');restore_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(restore_module);restoration=restore_module.formation_restoration(report,mask)
  r['no_dispatch_verified']=n.get('phase') in [3,4] and n.get('restore_mask')==mask and n.get('active')==0 and not n.get('issued_frame') and all(all(not u.get(key,0) for key in ['detach_calls','return_calls','move_calls','stop_calls']) for u in units) and not any(e.get('kind')==14 and e.get('arg')==0 for e in report.get('events',[]))
  result=dict(report=str(path),assessment=runtime.assessment(report),native=n,units=units,expected_restore_mask=mask,batch_restoration=restoration);r['unit_results'].append(result)
  if child.returncode!=0 or result['assessment'].get('status')!=schema['success'] or n.get('phase')!=3 or n.get('error')!=0 or n.get('restore_mask')!=mask or n.get('active')!=0 or len(units)!=2 or not all(x.get('returned')==x.get('return_calls')==1 for x in units):raise ValueError('formation_not_verified')
  r.update(status='completed',completed=True,goal_observed=True,restoration_verified=True)
 def _validate_task_dispatch(self,r):
  self._binding()
  if self.stopping.is_set():raise ValueError('stopped_before_dispatch')
  directory=r.get('executor_directory')
  if directory:
   schema=trusted_executor(directory)
   if r.get('module')!='calibration':
    grant=self.capability_grants.get((r.get('module'),r.get('purpose')))
    if not grant or grant.get('executor_directory')!=directory:raise ValueError('executor_grant_binding_changed')
    if hashlib.sha256((HERE/directory/'bin'/schema['dll']).read_bytes()).hexdigest()!=grant.get('native_binary_sha256') or hashlib.sha256((HERE/directory/'bin/tactical_host.exe').read_bytes()).hexdigest()!=grant.get('native_host_sha256'):raise ValueError('executor_revision_changed')
    if schema.get('mission_protocol'):
     for key,path in [('current_wrapper_sha256',HERE/directory/trusted_filename(schema,'wrapper_filename','lease.py')),('current_native_cpp_sha256',HERE/directory/'lease.cpp')]:
      if grant.get(key) and hashlib.sha256(path.read_bytes()).hexdigest()!=grant[key]:raise ValueError('executor_source_revision_changed')
     for source in grant.get('supplemental_sources',[]):
      if not isinstance(source.get('path'),str) or not source.get('sha256') or hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('executor_supplemental_revision_changed')
  for ident,version in r.get('formation_versions',{}).items():
   if ident not in self.formations or self.formations[ident]['version']!=version:raise ValueError('formation_version_changed')
  if r.get('expires_frame'):
   memory=backend.Memory(self.session['pid'],self.session)
   try:
    if memory.u32(self.logic+0x50)+280>r['expires_frame']:raise ValueError('task_expired_before_dispatch')
   finally:memory.close()
 def _work(self):
  while not self.stopping.is_set():
   try:command=self.pending.get(timeout=.2)
   except queue.Empty:continue
   with self.lock:
    r=self.ledger[command]
    if r.get('status')=='cancelled' and not r.get('dispatch_attempted'):
     self.pending.task_done();continue
    r['status']='dispatching';self.active=command
   try:
    if r.get('kind')=='formation':
     self._execute_formation(command,r)
     continue
    for oid in r['object_ids']:
     if self.stopping.is_set():raise ValueError('stopped_before_dispatch')
     self._validate_task_dispatch(r);self.native_seq+=1;unit_command=uuid.uuid5(uuid.UUID(command),str(oid));unit_task=uuid.uuid5(uuid.UUID(r['task_id']),str(oid));path=self.run/('tactical-task-'+str(unit_command)+'.json');r['active_report']=str(path)
     if path.exists():raise ValueError('existing_report_requires_recovery')
     combat=r.get('kind')=='attack';directory=r.get('executor_directory','combat-finite' if combat else 'reusable');schema,runtime=runtime_backend(directory);mask=schema['restore_mask'];native_script=HERE/directory/trusted_filename(schema,'wrapper_filename','lease.py')
     if schema['kind']!=('attack' if combat else 'move'):raise ValueError('executor_kind_mismatch')
     args=[sys.executable,str(native_script),'--session',str(self.session_path),'--execute','--object-id',str(oid),'--natural',str(self.natural_path),'--command-id',str(unit_command),'--task-id',str(unit_task),'--seq',str(self.native_seq),'--output',str(path)]
     args+=['--proof-file',r['visibility_proof_path'],'--contact-id',r['target_contact_id']] if combat else ['--target-x',str(r['target_xyz'][0]),'--target-y',str(r['target_xyz'][1])]
     if schema.get('mission_protocol'):
      mission_file=path.with_suffix('.mission.json')
      if mission_file.exists():raise ValueError('existing_mission_input_requires_recovery')
      with mission_file.open('x',encoding='utf-8') as f:json.dump(r['mission_input'],f,allow_nan=False);f.flush();__import__('os').fsync(f.fileno())
      args+=['--mission-file',str(mission_file),'--expires-frame',str(r['expires_frame']),'--post-frames','30']
     with path.with_suffix('.wrapper.log').open('w',encoding='utf-8') as log:
      r['wrapper_attempted']=True;r['dispatch_attempted']=True;child=subprocess.Popen(args,stdout=log,stderr=log)
      while child.poll() is None:
       if path.exists():
        try:
         current=json.loads(path.read_text(encoding='utf-8'))
         cn=current.get('native',{});cr=current.get('request',{});cp=current.get('preflight',{})
         if cn.get('issued_frame',0) and cn.get('command_id')==str(unit_command) and cn.get('task_id')==str(unit_task) and cn.get('seq')==self.native_seq and cr.get('command_id')==str(unit_command) and current.get('session_id')==self.session['session_id'] and cp.get('selected',{}).get('object_id')==oid:
          with self.lock:r['started']=True;r['status']='started';r['issued_frame']=r.get('issued_frame') or cn['issued_frame']
          if schema.get('mission_protocol'):
           progress_file=combat_qualifier_path(directory,schema);ps=importlib.util.spec_from_file_location('active_progress_'+directory.replace('-','_'),progress_file);pm=importlib.util.module_from_spec(ps);ps.loader.exec_module(pm)
           with self.lock:r['mission']=pm.progress(current,str(uuid.UUID(str(r['task_id']))))
        except (OSError,ValueError):pass
       if self.stopping.wait(.1):self._request_native_stop(path);time.sleep(.1)
       try:self._binding()
       except Exception:self.stopping.set();self._request_native_stop(path)
      if not path.exists():raise ValueError('child_no_dispatch_report')
     report=json.loads(path.read_text(encoding='utf-8'));nr=report.get('native',{});rq=report.get('request',{})
     if schema.get('mission_protocol') and self._record_pre_native_rejection(r,report,path,child.returncode,str(unit_command),str(unit_task),self.native_seq,directory):raise ValueError(report['pre_dispatch']['reason_code'])
     if report.get('session_id')!=self.session['session_id'] or report.get('preflight',{}).get('pid')!=self.session['pid'] or report.get('preflight',{}).get('commander_id')!=self.commander_id or report.get('preflight',{}).get('selected',{}).get('object_id')!=oid or rq.get('command_id')!=str(unit_command) or rq.get('task_id')!=str(unit_task) or rq.get('seq')!=self.native_seq or nr.get('command_id')!=str(unit_command) or nr.get('task_id')!=str(unit_task) or nr.get('seq')!=self.native_seq:raise ValueError('child_report_binding_mismatch')
     if nr.get('issued_frame',0):r['started']=True;r['issued_frame']=r.get('issued_frame') or nr['issued_frame']
     r['no_dispatch_verified']=not nr.get('issued_frame',0) and not nr.get('detach_calls',0) and not nr.get('move_calls',0) and not nr.get('attack_calls',0) and nr.get('active')==0 and nr.get('restore_mask')==mask
     spec_release=importlib.util.spec_from_file_location('tactical_single_release',HERE/'restoration.py');release_module=importlib.util.module_from_spec(spec_release);spec_release.loader.exec_module(release_module);control_release=release_module.single_control_release(report,mask)
     mission_assessment=None
     if directory in ['mission-combat','mission-combat-v2','mission-combat-v3','mission-combat-v4','mission-combat-v5','mission-combat-v6','mission-combat-v7']:
      module_path=combat_qualifier_path(directory,schema);qs=importlib.util.spec_from_file_location('trusted_mission_'+directory.replace('-','_'),module_path);qm=importlib.util.module_from_spec(qs);qs.loader.exec_module(qm);control_release=qm.control_release(report);r['mission']=qm.progress(report,str(uuid.UUID(str(r['task_id']))));mission_assessment=qm.qualify(report) if directory in ['mission-combat-v5','mission-combat-v6','mission-combat-v7'] else None
     if directory in ['ordered-attack','ordered-combo','mission-combat','mission-combat-v2','mission-combat-v3','mission-combat-v4','mission-combat-v5','mission-combat-v6','mission-combat-v7'] and not control_release['restoration_verified'] and nr.get('phase')==4 and nr.get('error')==32:
      try:
       spec_disposal=importlib.util.spec_from_file_location('tactical_readonly_disposal',HERE/('mission_v7_readonly_disposal.py' if directory=='mission-combat-v7' else 'mission_v6_readonly_disposal.py' if directory=='mission-combat-v6' else 'mission_v5_readonly_disposal.py' if directory=='mission-combat-v5' else 'mission_v4_readonly_disposal.py' if directory=='mission-combat-v4' else 'mission_v3_readonly_disposal.py' if directory=='mission-combat-v3' else 'mission_v2_readonly_disposal.py' if directory=='mission-combat-v2' else 'mission_readonly_disposal.py' if directory=='mission-combat' else 'readonly_disposal.py'));disposal_module=importlib.util.module_from_spec(spec_disposal);spec_disposal.loader.exec_module(disposal_module)
       control_release=disposal_module.collect(path,self.session_path,timeout=12)
      except Exception as disposal_error:control_release.update(disposal_error=str(disposal_error))
     gate_proof=None
     if directory in ['mission-combat-v3','mission-combat-v4','mission-combat-v5','mission-combat-v6','mission-combat-v7'] and nr.get('phase')==4 and not nr.get('issued_frame'):
      try:
       gs=importlib.util.spec_from_file_location('mct3_gate_no_lease_reader',HERE/('mission_v7_gate_no_lease.py' if directory=='mission-combat-v7' else 'mission_v6_gate_no_lease.py' if directory=='mission-combat-v6' else 'mission_v5_gate_no_lease.py' if directory=='mission-combat-v5' else 'mission_v4_gate_no_lease.py' if directory=='mission-combat-v4' else 'mission_v3_gate_no_lease.py'));gm=importlib.util.module_from_spec(gs);gs.loader.exec_module(gm);gate_proof=gm.collect(path,self.session_path)
      except Exception as gate_error:gate_proof=dict(no_dispatch_verified=False,error_type=type(gate_error).__name__)
      r['no_dispatch_verified']=gate_proof.get('no_actor_lease_verified',False)
     scene_release=self._scene_release(directory,report,path);r['scene_disposed_control_release_verified']=bool(scene_release and scene_release.get('scene_disposed_control_release') is True)
     result=dict(control_release=control_release,scene_release=scene_release,expected_restore_mask=mask,object_id=oid,report=str(path),assessment=mission_assessment if mission_assessment is not None else runtime.assessment(report),native=report.get('native',{}),status=report.get('status'),native_gate_no_lease=gate_proof,child_exit_code=child.returncode)
     with self.lock:r['unit_results'].append(result);self._audit(dict(event='unit_feedback',command_id=command,**result))
     if r.get('module')=='raid' and r.get('purpose')=='harass_economy' and report.get('request',{}).get('target_role')!='economy':raise ValueError('harass_target_role_changed')
     if combat and report.get('request',{}).get('target_contact_id')!=r.get('target_contact_id'):raise ValueError('target_contact_binding_mismatch')
     if child.returncode!=0 or result['assessment'].get('status')!=schema['success'] or nr.get('phase')!=3 or nr.get('restore_mask')!=mask or nr.get('active')!=0 or nr.get('error')!=0 or not nr.get('return_verified'):raise ValueError('primitive_not_verified')
    with self.lock:r.update(status='completed',completed=True,goal_observed=True,restoration_verified=True)
   except Exception as error:
    with self.lock:
     self._certify_queue_rejection(r,str(error));r.update(status='cancelled' if self.stopping.is_set() else ('unknown' if r.get('dispatch_attempted') and not r['unit_results'] else 'failed'),completed=False,reason_code=str(error),restoration_verified=(len(r['unit_results'])==1 and r['unit_results'][0].get('batch_restoration',{}).get('restoration_verified',False)) if r.get('kind')=='formation' else (len(r['unit_results'])==len(r['object_ids']) and all(x.get('control_release',{}).get('restoration_verified',False) for x in r['unit_results'])))
   finally:
    with self.lock:
     reports=r['unit_results'];issued=[x.get('native',{}).get('issued_frame',0) for x in reports if x.get('native',{}).get('issued_frame',0)];r['execution']=dict(formation_versions=r.get('formation_versions',{}),issued_frame=r.get('issued_frame') or (min(issued) if issued else 0),expires_frame=r.get('expires_frame',max(issued)+180 if issued else 0),command_source='game_thread_bridge',interference='none' if r.get('completed') else 'unknown',goal_observed=r.get('goal_observed',False),restoration_verified=r.get('restoration_verified',False));r['interference']=r['execution']['interference'];r['issued_frame']=r['execution']['issued_frame'];r['started']=r['issued_frame']>0
     if r['started']:r['no_dispatch_verified']=False
     self._audit(dict(event='task_feedback',receipt=r));self.active=None
     if r.get('restoration_verified') or r.get('scene_disposed_control_release_verified') is True or r.get('no_dispatch_verified') or not r.get('dispatch_attempted'):self.reserved_units.difference_update(r['object_ids'])
    self.pending.task_done()
 def _request_native_stop(self,path):
  try:
   report=json.loads(path.read_text(encoding='utf-8'));token=report['request']['token'];combat='target_contact_id' in report.get('request',{});runtime=backend
   formation='front_id' in report.get('request',{});prefix='RA3TacticalReusable_'
   if combat or formation:
    active=self.ledger.get(self.active,{})
    if Path(active.get('active_report','')).resolve()!=path.resolve():return
    directory=active.get('executor_directory','formation' if formation else 'combat-finite');schema,runtime=runtime_backend(directory);prefix=schema['mapping_prefix']
   k=backend.k;k.OpenFileMappingW.argtypes=[backend.w.DWORD,backend.w.BOOL,backend.w.LPCWSTR];k.OpenFileMappingW.restype=backend.w.HANDLE;k.MapViewOfFile.argtypes=[backend.w.HANDLE,backend.w.DWORD,backend.w.DWORD,backend.w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
   h=k.OpenFileMappingW(0xf001f,False,('Local\\'+prefix)+str(self.session['pid'])+'_'+str(token))
   if not h:return
   v=k.MapViewOfFile(h,0xf001f,0,0,c.sizeof(runtime.Tactical))
   if v:
    shared=runtime.Tactical.from_address(v)
    if shared.token==token and shared.pid==self.session['pid']:shared.stop_requested=1
    k.UnmapViewOfFile(v)
   k.CloseHandle(h)
  except (OSError,ValueError,KeyError):pass
 def request_mission_retreat(self,task_id,reason='replan'):
  """Idempotent host request. Keeps actor reservations until actual release.
  This writes only the reviewed channel flag; the game-thread state machine
  performs all SDK calls. A queued mission has no actor lease and can cancel.
  """
  with self.lock:
   try:canonical=str(uuid.UUID(str(task_id)))
   except ValueError:return dict(accepted=False,reason='task_id_invalid')
   found=[r for r in self.ledger.values() if str(uuid.UUID(str(r['task_id'])))==canonical]
   if len(found)!=1:return dict(accepted=False,reason='mission_not_found')
   r=found[0];directory=r.get('executor_directory');schema=trusted_executor(directory) if directory else {}
   if schema.get('mission_protocol')!='continuous_tactical_v1':return dict(accepted=False,reason='not_continuous_mission')
   if reason not in ['replan','deadline','host_stop','model_retreat','target_lost']:return dict(accepted=False,reason='retreat_reason_invalid')
   if r.get('retreat_request_sent'):return dict(accepted=True,already_requested=True)
   if r.get('status')=='queued' and not r.get('dispatch_attempted'):
    if not self._certify_queue_rejection(r,'retreat_before_dispatch'):return dict(accepted=False,reason='queue_ownership_unknown')
    r.update(status='cancelled',completed=False,reason_code='retreat_before_dispatch',retreat_request_sent=True);self.reserved_units.difference_update(r['object_ids']);return dict(accepted=True,no_dispatch=True)
   if r.get('status') in ['completed','failed','cancelled'] and r.get('restoration_verified'):return dict(accepted=True,already_terminal=True)
   if self.active!=r['command_id'] or not r.get('active_report'):return dict(accepted=False,reason='native_channel_not_ready')
   path=Path(r['active_report']);runtime_schema,runtime=runtime_backend(directory)
   try:
    report=json.loads(path.read_text(encoding='utf-8'));rq=report['request'];native=report.get('native',{})
    if report['session_id']!=self.session['session_id'] or native.get('session_id')!=self.session['session_id'] or native.get('command_id')!=rq['command_id'] or native.get('task_id')!=rq['task_id']:return dict(accepted=False,reason='native_report_not_ready')
    api=backend.k;api.OpenFileMappingW.argtypes=[backend.w.DWORD,backend.w.BOOL,backend.w.LPCWSTR];api.OpenFileMappingW.restype=backend.w.HANDLE;api.MapViewOfFile.argtypes=[backend.w.HANDLE,backend.w.DWORD,backend.w.DWORD,backend.w.DWORD,c.c_size_t];api.MapViewOfFile.restype=c.c_void_p;api.UnmapViewOfFile.argtypes=[c.c_void_p]
    h=api.OpenFileMappingW(0xf001f,False,'Local\\'+runtime_schema['mapping_prefix']+str(self.session['pid'])+'_'+str(rq['token']))
    if not h:return dict(accepted=False,reason='native_channel_not_ready')
    try:
     view=api.MapViewOfFile(h,0xf001f,0,0,c.sizeof(runtime.Tactical))
     if not view:return dict(accepted=False,reason='native_channel_not_ready')
     try:
      shared=runtime.Tactical.from_address(view)
      import struct
      ident=lambda field:str(uuid.UUID(bytes=struct.pack('<4I',*getattr(shared,field))))
      if shared.pid!=self.session['pid'] or shared.token!=rq['token'] or shared.seq!=rq['seq'] or ident('session')!=self.session['session_id'] or ident('commander')!=self.commander_id or ident('command')!=rq['command_id'] or ident('task')!=rq['task_id']:return dict(accepted=False,reason='native_channel_binding_mismatch')
      if shared.phase not in [1,5,6]:return dict(accepted=False,reason='native_not_active')
      shared.retreat_requested=1;r.update(retreat_request_sent=True,retreat_request_reason=reason);self._audit(dict(event='mission_retreat_requested',command_id=r['command_id'],reason=reason));return dict(accepted=True)
     finally:api.UnmapViewOfFile(view)
    finally:api.CloseHandle(h)
   except (OSError,ValueError,KeyError,AttributeError):return dict(accepted=False,reason='native_channel_not_ready')
 def status(self):
  with self.lock:return dict(state=self.state,session_id=getattr(self,'session',{}).get('session_id'),commander_id=self.commander_id,player_id=3,capabilities=self.capabilities,manifest=self.manifest(),active_command_id=self.active,ledger=json.loads(json.dumps(list(self.ledger.values()))))
 def stop(self):
  self.stopping.set()
  with self.lock:
   self.state='stopping'
   if self.active and self.ledger[self.active].get('active_report'):self._request_native_stop(Path(self.ledger[self.active]['active_report']))
   for receipt in self.ledger.values():
    if receipt['status']=='queued':
     if self._certify_queue_rejection(receipt,'stop_before_dispatch'):self.reserved_units.difference_update(receipt['object_ids'])
     receipt.update(status='cancelled',reason_code='stop_before_dispatch')
  if self.worker:self.worker.join(timeout=1)
  with self.lock:self.state='return_pending' if self.reserved_units or self.worker and self.worker.is_alive() else 'stopped';result=self.status();self._audit(dict(event='stop_requested',status=result));return result
