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

NATIVE_LAUNCH_INTENT=False;REPORT_OWNED=False;CLI_ARGS=None



def pre_dispatch_helper():

 import importlib.util

 sp=importlib.util.spec_from_file_location('mission_combat_pre_dispatch_contract',HERE.parent/'pre_dispatch_v5_contract.py');mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod);return mod



U=c.c_uint32;L=c.c_int32

class Event(c.Structure):

 _fields_=[(x,U) for x in 'seq kind tag frame tick thread caller team owner source arg'.split()]+[(x,c.c_float) for x in 'x y z'.split()]+[(x,U) for x in ['target_id','damage_source']]+[(x,c.c_float) for x in ['damage_before','damage_after','damage_reported']]+[(x,U) for x in 'lease_stage sm sm_flags state state_id path holder arg_shots arg_source'.split()]+[('requested',c.c_float*3),('effective',c.c_float*3)]+[('stack_count',U),('stack',U*12),('stack_word_count',U),('stack_words_address',U),('stack_words',U*128)]+[(x,U) for x in 'active_weapon_entry active_weapon_asset active_weapon_ammo status84 mission_stage stage_revision stage_frame move_index'.split()]+[('command_xyz',c.c_float*3)]+[(x,c.c_float) for x in 'waypoint_distance own_hp'.split()]+[('argument_path',U),('current_visible',U),('mission_reason',U),('argument_limit',c.c_float),('visible_target_xyz',c.c_float*3)]+[(x,U) for x in 'target_last_seen_frame memory_wait_started'.split()]+[('remembered_target_xyz',c.c_float*3)]

HEADER='magic version pid thread owner ai personality personality_id player_template start_low start_high'.split()

TAIL='unit object_id type_hash update logic original_team script_team default_team lease_frames post_frames target_unit target_id target_hash target_owner target_template target_observed_frame attack_calls damage_count weapon_entry weapon_template weapon_slot weapon_ammo last_ammo last_limit limit_before limit_after shot_samples damage_hook_calls visible_damage_calls'.split()

RESULT='error restore_mask callback_thread issued_frame returned_frame move_calls detach_calls return_calls arrival_samples native_move native_attack native_add native_remove owner_fail lifecycle_fail paused_samples overflow return_verified return_pending'.split()

class Tactical(c.Structure):

 _fields_=[(x,U) for x in HEADER]+[('session',U*4),('commander',U*4),('command',U*4),('task',U*4),('token',U),('seq',U)]+[(x,U) for x in TAIL]+[(x,U) for x in ['commit_hook_calls','commit_visible_calls','commit_own_calls']]+[('damage_total',c.c_float)]+[('target',c.c_float*3)]+[(x,L) for x in 'phase stop_requested active count'.split()]+[(x,U) for x in RESULT]+[(x,U) for x in 'stop_calls private_stop_calls private_stop_frame attack_facade_calls attack_private_calls attack_issued_frame stable_samples stop_gate_samples last_sample_frame lease_stage stop_failed stop_issue_frame post_actor_disposed post_scene_changed'.split()]+[('stopped_xyz',c.c_float*3)]+[(x,U) for x in 'button button_schema command_set initial_weapon_asset initial_weapon_entry toggle_calls toggle_hook_calls toggle_frame ak_samples last_ak_frame prepare_reconstituted_stops observed_weapon_asset observed_weapon_entry observed_ammo total_private_stops prepare_gate_frame'.split()]+[(x,U) for x in 'mission_deadline_frame mission_stage stage_revision stage_frame reason_code approach_limit engage_limit retreat_limit approach_started engage_started retreat_started retreat_observed_frame retreat_source retreat_anchor retreat_anchor_id retreat_anchor_hash normal_move_facade_calls normal_move_private_calls move_index move_started move_last_progress_frame arrival_last_frame waypoint_samples retreat_arrival_samples approach_move_calls retreat_move_calls checkpoint_count retreat_index heartbeat_tick retreat_requested current_visible retreat_last_frame retreat_replans retreat_mode fallback_checkpoint_index target_last_seen_frame memory_wait_started'.split()]+[('retreat_goal',c.c_float*3),('waypoint',c.c_float*3),('checkpoint',(c.c_float*3)*32),('move_progress_xyz',c.c_float*3),('retreat_attempt_xyz',c.c_float*3)]+[(x,c.c_float) for x in 'retreat_attempt_home_distance move_best_distance approach_distance own_hp initial_hp retreat_hp_fraction'.split()]+[('events',Event*4096)]

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



def diagnostic_assessment(report):

 events=report.get('events',[]);n=report.get('native',{});pre=report['preflight'];req=report['request'];issued=n.get('issued_frame',0);returned=n.get('returned_frame',0);owner=int(pre['owner'],0);manager=int(pre['ai'],0)+0x104;thread=pre['window_thread'];source=pre['selected']['object_id'];target=req['target_object_id']

 if any(any(field in ['x','y','z','damage_before','damage_after','damage_reported'] for field in e.get('invalid_float_fields',[])) for e in events):return dict(status='not_passed',checks={'critical_native_float_finite':False},new_order_fire_association_verified=False,raid_verified=False,attack_verified=False,combined_arms_verified=False)

 shots=[e for e in events if e['kind']==22 and e['target_id']==target and e['damage_source']==source and e['thread']==thread and issued<=e['frame']<=returned and e['damage_before']>e['damage_after']]

 hits=[e for e in events if e['kind']==20 and e['target_id']==target and e['damage_source']==source and e['thread']==thread and issued<=e['frame']<=returned and e['damage_before']>e['damage_after'] and e['damage_reported']>0 and abs(e['damage_before']-e['damage_after']-e['damage_reported'])<.05 and any(s['frame']<e['frame'] or s['frame']==e['frame'] and s.get('seq',0)<e.get('seq',0) for s in shots)]

 checks=dict(stopped=n.get('phase')==3,no_error=n.get('error')==0,restore=n.get('restore_mask')==2047,no_active=n.get('active')==0,one_detach=n.get('detach_calls')==1,one_attack=n.get('attack_calls')==1,native_script_burst_limit=n.get('limit_after')==0x7fffffff,ammo_activity_observed=bool(shots) and n.get('shot_samples')==len(shots),no_move=n.get('move_calls')==0,one_return=n.get('return_calls')==1,returned=bool(n.get('return_verified')),owner=bool(events) and all(e['owner']==owner for e in events if issued<=e['frame']<=returned and e['kind']!=4),thread=n.get('callback_thread')==thread and all(e['thread']==thread for e in events),attack_trace=sum(e['kind']==12 and e['tag']==2 and e['arg']==target for e in events)==1 and sum(e['kind']==13 and e['tag']==2 and e['arg']==target for e in events)==1,remove=any(e['kind']==18 and e['tag']==1 and e['arg']==manager and e['caller']==0x838877 for e in events),add=any(e['kind']==16 and e['tag']==3 and e['arg']==manager and e['caller']==0x83885b for e in events),causal_damage=bool(hits) and n.get('damage_count')==len(hits) and abs(sum(e['damage_reported'] for e in hits)-n.get('damage_total',0))<.05,frame_window=issued>0 and 0<=returned-issued<=req['lease_frames']+35,session=report['session_id']==pre['session_id']==n.get('session_id'),command=req['command_id']==n.get('command_id') and req['task_id']==n.get('task_id') and bool(pre.get('commander_id')) and pre.get('commander_id')==n.get('commander_id') and type(req.get('seq')) is int and req['seq']>0 and req['seq']==n.get('seq'),no_lifecycle=n.get('lifecycle_fail')==0,no_overflow=n.get('overflow')==0,no_override=not any(e['tag']==0 and e['kind'] in [10,12,14,16,18] and issued<=e['frame']<returned for e in events))

 sys.path.insert(0,str(HERE.parent));from stop_sequence import settled_stop

 for stage,gate_kind in [(0,37),(2,38)]:

  translated=[dict(e,kind=23 if e['kind']==33 else 24 if e['kind']==gate_kind else e['kind']) for e in events if e.get('lease_stage')==stage and e['kind'] in [3,33,gate_kind]]

  checks['normal_stop_'+str(stage)+'_stable_raw']=settled_stop(translated)['verified']

 checks['normal_script_attack_chain']=n.get('attack_facade_calls')==n.get('attack_private_calls')==1 and sum(e['kind']==34 and e['arg']==target and e.get('arg_shots')==0x7fffffff and e.get('arg_source')==1 for e in events)==1 and sum(e['kind']==12 and e['arg']==target and e.get('arg_shots')==0x7fffffff and e.get('arg_source')==1 for e in events)==1

 checks['two_normal_stops']=n.get('stop_calls')==n.get('private_stop_calls')==2 and n.get('stop_failed')==0

 checks['diagnostic_only_no_capability']=False

 return dict(status='attack_damage_and_return_primitive_verified' if all(checks.values()) else 'not_passed',checks=checks,causal_damage=sum(e['damage_reported'] for e in hits),target_object_id=target,source_object_id=source,new_order_fire_association_verified=False,raid_verified=False,attack_verified=False,combined_arms_verified=False,note='Explicit attack and source-attributed damage primitive only. Purpose-level capability requires host review; no combined arms claim.')





def assessment(report):

 sys.path.insert(0,str(HERE.parent));from mission_combat_v5_qualification import qualify

 return qualify(report)



def capture_weapon_binding(report,memory):

 n=report.get('native',{});template=n.get('weapon_template',0);entry=n.get('weapon_entry',0)

 if not template or not entry:return

 old=report.get('weapon_asset_binding')

 if old:

  if old['reported_entry']!=hex(entry) or old['reported_template']!=hex(template):report['weapon_binding_changed']=True

  return

 if memory.u32(template)!=0xc37534:raise ValueError('weapon_template_vtable_unverified')

 schema=memory.u32(template+4);header=memory.u32(schema);typeid=memory.u32(header);asset=memory.u32(header+4)

 if not schema or not header or memory.u32(template+4)!=schema or memory.u32(schema)!=header:raise ValueError('weapon_binding_changed_during_read')

 report['weapon_asset_binding']=dict(session_id=report['session_id'],pid=report['preflight']['pid'],reported_entry=hex(entry),reported_template=hex(template),template_schema=hex(schema),asset_header=hex(header),asset_type=hex(typeid),asset_id=hex(asset),method='reported_template_plus4_to_schema_to_asset_header',observed_frame=n.get('attack_issued_frame',0),mutations=False)



def event_record(event):

 record={};invalid=[]

 def plain(value,path):

  if isinstance(value,c.Array):return [plain(x,path+'['+str(i)+']') for i,x in enumerate(value)]

  if isinstance(value,float) and not math.isfinite(value):invalid.append(path);return None

  return value

 for name,_ in Event._fields_:record[name]=plain(getattr(event,name),name)

 if invalid:record['invalid_float_fields']=invalid

 return record



def capture_shared(report,shared):

 # Copy first, then decode published event records. A final terminal read is mandatory.

 snapshot=Tactical.from_buffer_copy(c.string_at(c.addressof(shared),c.sizeof(Tactical)))

 report['events']=[]

 for index in range(max(0,min(snapshot.count,4096))):

  event=snapshot.events[index]

  if event.seq!=index+1:break

  report['events'].append(event_record(event))

 shared=snapshot

 report['native']={x:getattr(shared,x) for x in RESULT+['phase','active','count','attack_calls','damage_count','target_id','damage_total','weapon_entry','weapon_template','weapon_slot','weapon_ammo','last_ammo','last_limit','limit_before','limit_after','shot_samples','damage_hook_calls','visible_damage_calls','commit_hook_calls','commit_visible_calls','commit_own_calls']+['stop_calls', 'private_stop_calls', 'private_stop_frame', 'attack_facade_calls', 'attack_private_calls', 'attack_issued_frame', 'stable_samples', 'stop_gate_samples', 'last_sample_frame', 'lease_stage', 'stop_failed','stop_issue_frame','post_actor_disposed','post_scene_changed']};report['native'].update({x:getattr(shared,x) for x in 'button button_schema command_set initial_weapon_asset initial_weapon_entry toggle_calls toggle_hook_calls toggle_frame ak_samples last_ak_frame prepare_reconstituted_stops observed_weapon_asset observed_weapon_entry observed_ammo total_private_stops prepare_gate_frame'.split()});report['native'].update({x:getattr(shared,x) for x in 'mission_deadline_frame mission_stage stage_revision stage_frame reason_code approach_limit engage_limit retreat_limit approach_started engage_started retreat_started retreat_observed_frame retreat_source retreat_anchor retreat_anchor_id retreat_anchor_hash normal_move_facade_calls normal_move_private_calls move_index move_started move_last_progress_frame arrival_last_frame waypoint_samples retreat_arrival_samples approach_move_calls retreat_move_calls checkpoint_count retreat_index heartbeat_tick retreat_requested current_visible retreat_last_frame retreat_replans retreat_mode fallback_checkpoint_index target_last_seen_frame memory_wait_started retreat_attempt_home_distance move_best_distance approach_distance own_hp initial_hp retreat_hp_fraction'.split()});report['native']['retreat_goal']=list(shared.retreat_goal);report['native']['waypoint']=list(shared.waypoint);report['native']['checkpoints']=[list(x) for x in shared.checkpoint[:min(shared.checkpoint_count,32)]];report['native']['target']=list(shared.target);report['native'].update(session_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.session))),commander_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.commander))),command_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.command))),task_id=str(uuid.UUID(bytes=struct.pack('<4I',*shared.task))),seq=shared.seq);report['status']='finished' if shared.phase in [3,4] else 'running'

 return snapshot.phase in [3,4]



def main():

 global NATIVE_LAUNCH_INTENT,REPORT_OWNED,CLI_ARGS

 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--object-id',type=int);ap.add_argument('--execute',action='store_true');ap.add_argument('--readiness',action='store_true');ap.add_argument('--natural',type=Path);ap.add_argument('--dx',type=float,default=80);ap.add_argument('--dy',type=float,default=0);ap.add_argument('--lease-frames',type=int,default=4500);ap.add_argument('--post-frames',type=int,default=90)

 ap.add_argument('--mission-file',type=Path);ap.add_argument('--expires-frame',type=int);ap.add_argument('--proof-file',type=Path);ap.add_argument('--contact-id');ap.add_argument('--output',type=Path);ap.add_argument('--target-x',type=float);ap.add_argument('--target-y',type=float);ap.add_argument('--command-id',default=None);ap.add_argument('--task-id',default=None);ap.add_argument('--seq',type=int,required=False);args=ap.parse_args();CLI_ARGS=args

 if args.execute and args.output and args.output.exists():raise ValueError('existing_report_requires_recovery')

 pre,session,raw,package,registry_path,registry_digest,memory=readiness(args.session,args.object_id)

 if not args.execute:

  durable(HERE/'readiness.json',pre);print(json.dumps(pre,ensure_ascii=False));memory.close();return

 if not pre['selected']:raise ValueError('no_eligible_unit')

 if (args.target_x is None)!=(args.target_y is None):raise ValueError('both_target_coordinates_required')

 if args.target_x is not None:args.dx=args.target_x-pre['selected']['xyz'][0];args.dy=args.target_y-pre['selected']['xyz'][1]

 if not args.natural:raise ValueError('natural_thread_evidence_required')

 if not args.proof_file or not args.contact_id:raise ValueError('verified_visibility_proof_and_contact_required')

 sys.path.insert(0,str(BRIDGE/'visibility'))

 from projection import VisibilityProjection

 from collector import VisibilityCollector

 proof_raw=args.proof_file.read_bytes();proof=json.loads(proof_raw.decode('utf-8-sig'));safety_path=BRIDGE/'visibility/template-safety-2d7873e1.json';safety_raw=safety_path.read_bytes();safety=json.loads(safety_raw.decode('utf-8-sig'));projection=VisibilityProjection(session['session_id'],3,session['mod_sha256'],proof,safety)

 if not projection.verified():raise ValueError('visibility_capability_unverified')

 collector=VisibilityCollector(memory,session,3,projection);collector.collect(pre['frame']/15)

 contact=collector.private_targets.get(args.contact_id)

 if not contact:raise ValueError('contact_not_currently_visible')

 contact=dict(contact,template=memory.u32(contact['address']+4));args.dx=40.;args.dy=0.

 if args.mission_file is None:raise ValueError('trusted_mission_file_required')

 mission_raw=args.mission_file.read_bytes();mission=json.loads(mission_raw.decode('utf-8-sig'))

 sp_contract=__import__('importlib.util',fromlist=['util']);cs=sp_contract.spec_from_file_location('mission_combat_trusted_input',HERE/'mission_contract.py');cm=sp_contract.module_from_spec(cs);cs.loader.exec_module(cm);validate_mission=cm.validate_mission

 mission=validate_mission(mission,pre,memory,args.expires_frame)

 args.lease_frames=mission['expires_frame']-pre['frame']

 

 sys.path.insert(0,str(HERE.parent));from mobility_guard import mobility_status

 if not mobility_status(memory,int(pre['selected']['address'],0))['independently_movable']:raise ValueError('actor_garrisoned_or_immobile')

 import importlib.util

 sp=importlib.util.spec_from_file_location('combo_button_resolver',HERE.parent/'recon/read_own_command_buttons.py');resolver=importlib.util.module_from_spec(sp);sp.loader.exec_module(resolver);button_info=resolver.inspect(memory,int(pre['selected']['address'],0))

 obs=json.loads(args.natural.read_text(encoding='utf-8-sig'));compatible_natural_calls(obs,session['pid'])

 if obs['window_thread']!=pre['window_thread']:raise ValueError('natural_thread_mismatch')

 if not all(math.isfinite(x) for x in [args.dx,args.dy]) or not 20<=math.hypot(args.dx,args.dy)<=120 or not 300<=args.lease_frames<=4500 or not 30<=args.post_frames<=180:raise ValueError('lease_bounds')

 layout=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))

 if layout!={'event':c.sizeof(Event),'tactical':c.sizeof(Tactical),'events':Tactical.events.offset,'unused1':0,'unused2':0}:raise ValueError('layout_mismatch')

 command_id=str(uuid.UUID(args.command_id)) if args.command_id else str(uuid.uuid4());task_id=str(uuid.UUID(args.task_id)) if args.task_id else str(uuid.uuid4());token=int.from_bytes(os.urandom(4),'little') or 1;seq=args.seq if args.seq is not None else int(time.monotonic()*1000)&0xffffffff

 run=Path(session['run_directory']);target=args.output or run/('tactical-ordered-attack-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(token)+'.json');report=dict(session_id=session['session_id'],executable_sha256=EXPECTED,package_sha256=session['mod_sha256'],native_binary_sha256=hashlib.sha256((HERE/'bin'/'TacticalMissionCombat5.dll').read_bytes()).hexdigest(),native_host_sha256=hashlib.sha256((HERE/'bin/tactical_host.exe').read_bytes()).hexdigest(),wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_source_sha256=hashlib.sha256((HERE/'lease.cpp').read_bytes()).hexdigest(),native_shared_sha256=hashlib.sha256((HERE/'shared.h').read_bytes()).hexdigest(),native_includes_sha256={'mission_tick.inc':hashlib.sha256((HERE/'mission_tick.inc').read_bytes()).hexdigest()},mission_contract_sha256=hashlib.sha256((HERE/'mission_contract.py').read_bytes()).hexdigest(),origin_resolution_helper_sha256=hashlib.sha256((HERE/'origin_resolution.py').read_bytes()).hexdigest(),pre_dispatch_helper_sha256=hashlib.sha256((HERE.parent/'pre_dispatch_v5_contract.py').read_bytes()).hexdigest(),native_launch_intent_persisted=False,preflight=pre,status='preflight',events=[],native={},request=dict(command_id=command_id,task_id=task_id,seq=seq,token=token,dx=args.dx,dy=args.dy,lease_frames=args.lease_frames,post_frames=args.post_frames,target=[pre['selected']['xyz'][0]+args.dx,pre['selected']['xyz'][1]+args.dy,pre['selected']['xyz'][2]],arrival_radius=15,target_contact_id=args.contact_id,mission=mission,mission_protocol='continuous_tactical_v1',expires_frame=mission['expires_frame'],mission_source_sha256=hashlib.sha256(mission_raw).hexdigest(),target_role=safety['templates'][contact['type_hash']]['role'],target_object_id=contact['object_id'],visibility_proof_sha256=hashlib.sha256(proof_raw).hexdigest(),safety_sha256=hashlib.sha256(safety_raw).hexdigest()))

 

 report['request']['button']=button_info

 if target.exists():raise ValueError('existing_report_requires_recovery')

 durable(target,report);REPORT_OWNED=True;handle=None;view=None;host=None;shared=None;last=0

 try:

  k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]

  handle=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Tactical),'Local\\RA3TacticalMissionCombat5_'+str(session['pid'])+'_'+str(token))

  if not handle or c.get_last_error()==183:raise ValueError('tactical_lease_already_used_in_process')

  view=k.MapViewOfFile(handle,0xf001f,0,0,c.sizeof(Tactical))

  if not view:raise c.WinError(c.get_last_error())

  c.memset(view,0,c.sizeof(Tactical));shared=Tactical.from_address(view);s=shared;s.magic=0x4d435435;s.version=13;s.command[:]=words(command_id);s.task[:]=words(task_id);s.token=token;s.seq=seq;s.pid=session['pid'];s.thread=pre['window_thread'];s.owner=int(pre['owner'],0);s.ai=int(pre['ai'],0);s.personality=int(pre['personality'],0);s.personality_id=int(pre['personality_id'],0);s.player_template=int(pre['player_template'],0);s.logic=int(pre['logic'],0);s.script_team=int(pre['script_team'],0);s.default_team=int(pre['default_team'],0);s.unit=int(pre['selected']['address'],0);s.update=int(pre['selected']['ai_address'],0);s.object_id=pre['selected']['object_id'];s.type_hash=int(pre['selected']['type_hash'],0);s.button=int(button_info['toggle']['entry'],0);s.button_schema=int(button_info['toggle']['schema'],0);s.command_set=int(button_info['command_set_hash'],0);s.lease_frames=args.lease_frames;s.post_frames=args.post_frames;s.session[:]=words(session['session_id']);s.commander[:]=words(pre['commander_id']);s.target[:]=contact['xyz'];s.target_unit=contact['address'];s.target_id=contact['object_id'];s.target_hash=int(contact['type_hash'],0);s.target_owner=contact['owner'];s.target_template=contact['template'];contact['body']=memory.u32(contact['address']+0x33c);contact['body_vtable']=memory.u32(contact['body']);contact['body_damage_entry']=memory.u32(contact['body_vtable']+0x10);s.target_observed_frame=contact['observed_frame'];report['request']['target']=list(s.target);report['private_target']=dict(contact)

  s.mission_deadline_frame=mission['expires_frame'];s.retreat_goal[:]=mission['retreat_point']['xyz'];s.retreat_observed_frame=mission['retreat_point']['observed_frame'];s.retreat_source=1 if mission['retreat_point']['source']=='own_home_base' else 2;s.retreat_anchor=mission.get('anchor_address',0);s.retreat_anchor_id=mission['retreat_point'].get('anchor_object_id',0);s.retreat_anchor_hash=mission.get('anchor_hash',0);s.approach_limit=mission['approach_frames'];s.engage_limit=mission['engage_frames'];s.retreat_limit=mission['retreat_frames'];s.retreat_hp_fraction=mission['retreat_hp_fraction'];s.heartbeat_tick=k.GetTickCount()

  times=[w.FILETIME() for _ in range(4)]

  if not k.GetProcessTimes(memory.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())

  s.start_low=times[0].dwLowDateTime;s.start_high=times[0].dwHighDateTime

  if args.session.read_bytes()!=raw or hashlib.sha256(package.read_bytes()).hexdigest()!=session['mod_sha256'] or hashlib.sha256(registry_path.read_bytes()).hexdigest()!=registry_digest:raise ValueError('binding_changed_before_dispatch')

  if mission.get('origin_policy')=='implicit_actor_origin':
   rs=sp_contract.spec_from_file_location('mct3_final_owned_origin',HERE/'origin_resolution.py');rm=sp_contract.module_from_spec(rs);rs.loader.exec_module(rm);resolution=rm.resolve(memory,pre)
   mission['retreat_point']=dict(xyz=resolution['xyz'],observed_frame=resolution['observed_frame'],source='own_actor_history',anchor_object_id=pre['selected']['object_id']);s.retreat_goal[:]=resolution['xyz'];s.retreat_observed_frame=resolution['observed_frame'];report['origin_resolution']=resolution;report['request']['mission']=mission
  report['status']='dispatch_pending';durable(target,report)

  with target.with_suffix('.host.log').open('w',encoding='utf-8') as log:

   NATIVE_LAUNCH_INTENT=True;report['native_launch_intent_persisted']=True;durable(target,report)

   host=subprocess.Popen([str(HERE/'bin/tactical_host.exe'),str(session['pid']),str(token)],stdout=log,stderr=log);deadline=time.monotonic()+650

   while time.monotonic()<deadline:

    shared.heartbeat_tick=k.GetTickCount()

    if args.session.read_bytes()!=raw or hashlib.sha256(registry_path.read_bytes()).hexdigest()!=registry_digest or args.proof_file.read_bytes()!=proof_raw or safety_path.read_bytes()!=safety_raw or args.mission_file.read_bytes()!=mission_raw:shared.stop_requested=1

    capture_shared(report,shared);capture_weapon_binding(report,memory);durable(target,report)

    if host.poll() is not None:break

    time.sleep(.1)

   if host.poll() is None:shared.stop_requested=1;report['status']='unknown_pending_native_return'

   capture_shared(report,shared);capture_weapon_binding(report,memory)

   if host.poll() is None:report['status']='unknown_pending_native_return'

   report['host_exit']=host.poll();report['assessment']=assessment(report);durable(target,report);print(json.dumps(dict(report=str(target),assessment=report['assessment'],native=report['native']),ensure_ascii=False))

 except BaseException as error:

  if shared is not None:

   shared.stop_requested=1;deadline=time.monotonic()+10

   while True:

    terminal=capture_shared(report,shared)

    if terminal or not host or time.monotonic()>=deadline:break

    time.sleep(.1)

  report.update(status='dispatch_failed_native_terminal' if shared is not None and shared.phase in [3,4] else 'unknown_pending_native_return' if host else 'no_dispatch_rejected',error=str(error),host_exit=host.poll() if host else None)

  durable(target,report);raise

 finally:

  memory.close()

  if view:k.UnmapViewOfFile(view)

  if handle:k.CloseHandle(handle)

def entrypoint():

 try:main()

 except BaseException as error:

  if not NATIVE_LAUNCH_INTENT and CLI_ARGS is not None and CLI_ARGS.execute:

   try:pre_dispatch_helper().rejection(CLI_ARGS,HERE,error,owned=REPORT_OWNED)

   except Exception:raise error

   raise SystemExit(64)

  raise

if __name__=='__main__':entrypoint()

