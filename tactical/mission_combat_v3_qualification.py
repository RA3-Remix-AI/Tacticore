"""Independent raw combat-mission verification. No SDK, UI, mapping or network."""
import hashlib,json,math
from pathlib import Path
from combo_qualification import damage_packet,target_scope,finite,close,EXE,AK
from stop_sequence import settled_stop
HERE=Path(__file__).resolve().parent
DIRECTORY=HERE/'mission-combat-v3'
REASONS={0:'active',1:'source_damage',2:'fov_lost',3:'approach_stalled',4:'approach_limit',5:'low_hp',6:'engage_limit',7:'retreat_failed',8:'deadline',9:'cancelled',10:'native_override',11:'prepare_failed',12:'heartbeat_lost',13:'target_invalid',14:'initial_binding'}
STAGES={0:'armed',1:'approach',2:'approach',3:'prepare',4:'prepare',5:'prepare',6:'engage',7:'retreat',8:'retreat',9:'retreat',10:'restored'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def point(value):return isinstance(value,(list,tuple)) and len(value)==3 and all(finite(v) for v in value)
def xyz(event):return [event.get('x'),event.get('y'),event.get('z')]
def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def revision_checks(report):
 files={'native_binary_sha256':DIRECTORY/'bin/TacticalMissionCombat3.dll','native_host_sha256':DIRECTORY/'bin/tactical_host.exe','wrapper_sha256':DIRECTORY/'lease.py','native_source_sha256':DIRECTORY/'lease.cpp','native_shared_sha256':DIRECTORY/'shared.h'}
 try:
  freeze=json.loads((DIRECTORY/'revision.json').read_text())
  return all(report.get(key)==freeze[key]==sha(path) for key,path in files.items()) and report.get('native_includes_sha256')==freeze['native_includes_sha256']=={'mission_tick.inc':sha(DIRECTORY/'mission_tick.inc')} and report.get('mission_contract_sha256')==freeze['mission_contract_sha256']==sha(DIRECTORY/'mission_contract.py') and report.get('pre_dispatch_helper_sha256')==freeze['pre_dispatch_helper_sha256']==sha(HERE/'pre_dispatch_v3_contract.py') and report.get('origin_resolution_helper_sha256')==freeze['origin_resolution_helper_sha256']==sha(DIRECTORY/'origin_resolution.py')
 except (OSError,ValueError,KeyError):return False
def control_release(report):
 n=report.get('native',{});rq=report.get('request',{});pre=report.get('preflight',{});events=report.get('events',[]);thread=pre.get('window_thread');owner=int(pre.get('owner','0'),0);manager=int(pre.get('ai','0'),0)+0x104
 bound=n.get('session_id')==report.get('session_id')==pre.get('session_id') and n.get('commander_id')==pre.get('commander_id') and all(n.get(k)==rq.get(k) for k in ['command_id','task_id','seq']) and type(rq.get('seq')) is int and rq['seq']>0 and n.get('callback_thread')==thread
 clean=n.get('phase')==3 and n.get('error')==0 and n.get('restore_mask')==16383 and n.get('active')==0 and n.get('overflow')==0
 held=[e for e in events if e.get('kind')==14 and e.get('tag')==1 and e.get('arg')==0];returned=[e for e in events if e.get('kind')==15 and e.get('tag')==3 and e.get('arg')==1]
 remove=[e for e in events if e.get('kind')==18 and e.get('tag')==1 and e.get('arg')==manager and e.get('caller')==0x838877];add=[e for e in events if e.get('kind')==16 and e.get('tag')==3 and e.get('arg')==manager and e.get('caller')==0x83885b]
 normal=n.get('detach_calls')==n.get('return_calls')==n.get('return_verified')==1 and len(held)==len(returned)==len(remove)==len(add)==1 and held[0]['seq']<remove[0]['seq']<add[0]['seq']<returned[0]['seq'] and returned[0]['frame']==n.get('returned_frame') and all(e.get('thread')==thread and e.get('owner')==owner for e in held+returned+remove+add)
 ok=bool(bound and clean and normal)
 return dict(restoration_verified=ok,control_release_verified=ok,return_verified=ok,disposed_verified=False,semantics='native_pool_return' if ok else 'unknown',completion_claim=False)
def last_samples(events,before,stage,count=3,move_index=None):
 rows=[];seen=set()
 for e in reversed(events):
  if e.get('seq',0)>=before or e.get('kind')!=3 or e.get('mission_stage')!=stage or move_index is not None and e.get('move_index')!=move_index:continue
  if e.get('frame') in seen:continue
  seen.add(e['frame']);rows.append(e)
  if len(rows)==count:break
 return list(reversed(rows))
def qualify(report):
 n=report.get('native',{});rq=report.get('request',{});pre=report.get('preflight',{});ev=report.get('events',[]);mission=rq.get('mission',{});source=pre.get('selected',{}).get('object_id');target=rq.get('target_object_id');issued=n.get('issued_frame',0);returned=n.get('returned_frame',0);attack=n.get('attack_issued_frame',0);thread=pre.get('window_thread');owner=int(pre.get('owner','0'),0);checks={};release=control_release(report)
 checks['certified_revision']=report.get('executable_sha256')==EXE and revision_checks(report)
 checks['launch_intent']=report.get('native_launch_intent_persisted') is True
 checks['finished']=report.get('status')=='finished' and report.get('host_exit')==0 and n.get('phase')==3 and n.get('error')==0
 checks['binding']=bool(source) and bool(target) and n.get('session_id')==report.get('session_id')==pre.get('session_id') and n.get('commander_id')==pre.get('commander_id') and pre.get('player_id')==3 and all(n.get(k)==rq.get(k) for k in ['command_id','task_id','seq']) and type(rq.get('seq')) is int and rq['seq']>0
 checks['actor_target_scope']=pre.get('selected',{}).get('type_hash')=='0x19ab11af' and target_scope(report) and report.get('private_target',{}).get('object_id')==target and report.get('private_target',{}).get('owner_player_id') not in [None,3]
 checks['ordered_log']=bool(ev) and all(e.get('seq')==i+1 for i,e in enumerate(ev)) and all(type(e.get('frame')) is int and type(e.get('tick')) is int for e in ev) and all(b['frame']>=a['frame'] and 0<=((b['tick']-a['tick'])&0xffffffff)<0x80000000 for a,b in zip(ev,ev[1:]))
 checks['thread_owner']=bool(ev) and n.get('callback_thread')==thread and all(e.get('thread')==thread for e in ev) and all(e.get('owner')==owner for e in ev if issued<=e.get('frame',0)<=returned and e.get('kind')!=4)
 checks['critical_finite']=all(all(finite(e.get(k)) for k in ['x','y','z','own_hp','damage_before','damage_after','damage_reported']) for e in ev)
 checks['clean_restore']=n.get('restore_mask')==16383 and n.get('active')==0 and n.get('overflow')==0 and n.get('lifecycle_fail')==0 and n.get('stop_failed')==0
 deadline=mission.get('expires_frame',0)
 checks['mission_deadline']=rq.get('mission_protocol')=='continuous_tactical_v1' and type(deadline) is int and deadline==rq.get('expires_frame')==n.get('mission_deadline_frame') and 0<issued<returned<=deadline and 300<=deadline-pre.get('frame',0)<=4500
 resolution=report.get('origin_resolution',{});retreat_point=mission.get('retreat_point',{})
 if mission.get('origin_policy')=='implicit_actor_origin':
  checks['resolved_actual_implicit_origin']=resolution.get('method')=='last_pre_native_launch_own_actor_position' and resolution.get('object_id')==source and resolution.get('address')==pre.get('selected',{}).get('address') and resolution.get('owner')==pre.get('owner') and resolution.get('type_hash')=='0x19ab11af' and resolution.get('update')==pre.get('selected',{}).get('ai_address') and resolution.get('mutations') is False and type(resolution.get('frame_start')) is int and resolution['frame_start']<=resolution.get('frame_end',-1)<=resolution['frame_start']+1 and resolution.get('observed_frame')==resolution.get('frame_end')==retreat_point.get('observed_frame') and resolution['observed_frame']<=issued<=resolution['observed_frame']+60 and point(resolution.get('xyz')) and point(retreat_point.get('xyz')) and math.dist(resolution['xyz'],retreat_point['xyz'])<=.01 and resolution.get('status84',0x20080000)&0x20080000==0 and finite(resolution.get('hp')) and resolution['hp']>0
 else:checks['resolved_actual_implicit_origin']=mission.get('origin_policy')=='explicit_fixed_point' and not resolution
 checks['phase_limits']=all(type(mission.get(k)) is int and low<=mission[k]<=high and mission[k]==n.get(native) for k,native,low,high in [('approach_frames','approach_limit',30,2100),('engage_frames','engage_limit',30,300),('retreat_frames','retreat_limit',60,1800)])
 changes=[e for e in ev if e.get('kind')==50];stage_ids=[e.get('arg') for e in changes]
 checks['stage_sequence']=stage_ids in [[1,2,3,4,5,6,7,8,9,10],[1,2,3,5,6,7,8,9,10]] and all(e.get('mission_stage')==e.get('arg') and e.get('stage_revision')==i+1 and e.get('stage_frame')==e.get('frame') for i,e in enumerate(changes)) and n.get('mission_stage')==10
 checks['success_reason']=n.get('reason_code')==1
 for stage,gate in [(0,37),(6,58),(4,43),(7,59),(2,38)]:
  rows=[dict(e,kind=23 if e.get('kind')==33 else 24 if e.get('kind')==gate else e.get('kind')) for e in ev if e.get('lease_stage')==stage and e.get('kind') in [3,33,gate]]
  gates=[e for e in ev if e.get('kind')==gate]
  checks['stop_'+str(stage)]=settled_stop(rows)['verified'] and len(gates)==1 and gates[0].get('state_id')==16 and gates[0].get('holder')==gates[0].get('path')==0
 ownstops=[e for e in ev if e.get('kind')==33 and e.get('lease_stage') in [0,6,4,7,2] and issued<=e.get('frame',0)<returned]
 replay=[e for e in ev if e.get('kind')==33 and e.get('lease_stage')==3 and issued<=e.get('frame',0)<returned]
 checks['normal_stop_counts']=n.get('stop_calls')==n.get('private_stop_calls')==len(ownstops)==5 and n.get('total_private_stops',0)>=len(ownstops)+len(replay) and all(e.get('arg')==1 and e.get('caller')==0x787791 for e in ownstops+replay)
 button=rq.get('button',{});calls=[e for e in ev if e.get('kind') in [40,41] and e.get('tag')==5];gates=[e for e in ev if e.get('kind')==42];toggle=n.get('toggle_frame',0)
 checks['button_identity']=button.get('command_set_hash')=='0xb74cf71a' and button.get('toggle',{}).get('asset_id')=='0x5977a798' and button.get('toggle',{}).get('asset_type')=='0x7d464170' and int(button.get('toggle',{}).get('entry','0'),0)==n.get('button') and int(button.get('toggle',{}).get('schema','0'),0)==n.get('button_schema')
 if n.get('toggle_calls')==0:
  checks['optional_prepare']=not calls and not replay and n.get('toggle_hook_calls')==0 and len(gates)==1 and gates[0].get('mission_stage')==3 and gates[0].get('active_weapon_asset')==AK
 else:
  rows=last_samples(ev,gates[0]['seq'],4) if len(gates)==1 else []
  checks['optional_prepare']=n.get('toggle_calls')==n.get('toggle_hook_calls')==1 and len(calls)==2 and [e.get('kind') for e in calls]==[40,41] and calls[0].get('arg')==n.get('button') and all(e.get('mission_stage')==4 and e.get('frame')==toggle for e in calls) and len(gates)==1 and calls[-1]['seq']<gates[0]['seq'] and len(rows)==3 and all(e['frame']>=toggle+15 and e.get('active_weapon_asset')==AK and e.get('state_id')==16 and e.get('path')==e.get('holder')==0 and not e.get('sm_flags',0xffff)&0xffff and e.get('source')==1 for e in rows) and all(e.get('mission_stage')==4 and toggle+15<=e['frame']<=n.get('prepare_gate_frame',0) and e.get('tag')==0 for e in replay)
 normal_moves=[e for e in ev if e.get('kind') in [54,52,53,55]];moves=[]
 for i in range(0,len(normal_moves),4):
  group=normal_moves[i:i+4]
  if len(group)!=4:continue
  good=[e.get('kind') for e in group]==[54,52,53,55] and len({e.get('move_index') for e in group})==1 and len({e.get('mission_stage') for e in group})==1 and all(e.get('tag')==6 and e.get('arg')==1 and point(e.get('command_xyz')) for e in group) and all(math.dist(group[0]['command_xyz'],e['command_xyz'])<=.01 for e in group) and group[1].get('argument_path')==0 and finite(group[1].get('argument_limit')) and group[1]['argument_limit']>1e30
  moves.append(dict(valid=good,index=group[0].get('move_index'),stage=group[0].get('mission_stage'),frame=group[0].get('frame'),seq=group[0]['seq'],goal=group[0].get('command_xyz')))
 checks['normal_move_chains']=len(normal_moves)==4*len(moves) and all(x['valid'] for x in moves) and n.get('move_calls')==n.get('normal_move_facade_calls')==n.get('normal_move_private_calls')==len(moves) and len({m['index'] for m in moves})==len(moves) and all(m['stage'] in [2,8] for m in moves) and len([m for m in moves if m['stage']==2])==n.get('approach_move_calls')<=12 and 1<=len([m for m in moves if m['stage']==8])==n.get('retreat_move_calls')<=3
 # Each completed waypoint is verified from three actual positions, never its counter.
 arrivals=[e for e in ev if e.get('kind')==57];arrival_ok=True
 for end in arrivals:
  matching=[m for m in moves if m['index']==end.get('move_index') and m['stage']==end.get('mission_stage') and m['seq']<end['seq']]
  rows=last_samples(ev,end['seq'],end.get('mission_stage'),move_index=end.get('move_index'))
  arrival_ok &= len(matching)==1 and len(rows)==3 and all(point(xyz(e)) and distance(xyz(e),matching[0]['goal'])<=15.01 and e['seq']>matching[0]['seq'] for e in rows)
 checks['waypoint_arrival_raw']=arrival_ok
 approach_gates=[e for e in changes if e.get('arg')==3]
 approach_starts=[e for e in changes if e.get('arg')==2]
 initial=xyz(approach_starts[0]) if len(approach_starts)==1 else None;initial_target=approach_starts[0].get('visible_target_xyz') if len(approach_starts)==1 else None;approach_verified=False
 approach_orders=[e for e in ev if e.get('kind')==54 and e.get('mission_stage')==2]
 checks['full_visible_target_path_requests']=bool(approach_orders) and all(e.get('current_visible')==1 and point(e.get('visible_target_xyz')) and point(e.get('command_xyz')) and math.dist(e['visible_target_xyz'],e['command_xyz'])<=.05 for e in approach_orders)
 checkpoints=n.get('checkpoints',[]);samples=[e for e in ev if e.get('kind')==61]
 checks['actual_own_checkpoints']=isinstance(checkpoints,list) and 1<=len(checkpoints)<=32 and n.get('checkpoint_count')==len(checkpoints) and all(point(x) for x in checkpoints) and len(samples)==len(checkpoints)-1 and all(e.get('arg')==i and e.get('mission_stage')==2 and math.dist(xyz(e),checkpoints[i])<=.05 and distance(checkpoints[i-1],checkpoints[i])>=119.95 for i,e in enumerate(samples,1))
 checks['approach_live_start']=len(approach_starts)==1 and approach_starts[0].get('current_visible')==1 and approach_starts[0]['frame']==n.get('approach_started') and pre.get('frame',0)<=issued<=pre.get('frame',0)+60
 if len(approach_gates)==1 and point(initial) and point(initial_target):
  g=approach_gates[0];approach_verified=g.get('current_visible')==1 and point(g.get('visible_target_xyz')) and distance(xyz(g),g['visible_target_xyz'])<=125.01 and (distance(initial,initial_target)<=125.01 or distance(initial,xyz(g))>=40) and g['frame']-n.get('approach_started',0)<=n.get('approach_limit',0)+2
 checks['approach_effect']=approach_verified
 long_approach_verified=bool(approach_verified and point(initial) and point(initial_target) and distance(initial,initial_target)>=300 and distance(initial,xyz(approach_gates[0]))>=120)
 retreat=rq.get('mission',{}).get('retreat_point',{});goals=retreat.get('xyz');retreat_gates=[e for e in ev if e.get('kind')==60];retreat_verified=False
 if len(retreat_gates)==1 and point(goals) and point(n.get('retreat_goal')):
  gate=retreat_gates[0];rows=last_samples(ev,gate['seq'],8,move_index=gate.get('move_index'));retreat_start=[e for e in changes if e.get('arg')==7]
  retreat_verified=math.dist(goals,n['retreat_goal'])<=.01 and len(rows)==3 and all(distance(xyz(e),goals)<=15.01 and abs(e['z']-goals[2])<=10 for e in rows) and len(retreat_start)==1 and distance(xyz(retreat_start[0]),xyz(gate))>=40 and n.get('retreat_started')==retreat_start[0]['frame'] and gate['frame']-n['retreat_started']<=n.get('retreat_limit',0)+1 and gate['frame']<returned
 retreat_moves=[m for m in moves if m['stage']==8];fallbacks=[e for e in ev if e.get('kind')==62];resumes=[e for e in ev if e.get('kind')==63]
 route_ok=bool(retreat_moves) and point(goals) and math.dist(retreat_moves[0]['goal'],goals)<=.05
 if not fallbacks and not resumes:
  route_ok=route_ok and len(retreat_moves)==1 and n.get('retreat_replans')==0
 elif len(fallbacks)==len(resumes)==1 and len(retreat_moves)==3:
  f,z=fallbacks[0],resumes[0];index=f.get('arg');cp=n.get('checkpoints',[]);valid=type(index) is int and 0<=index<len(cp)
  if valid:
   position=xyz(f);home=distance(position,goals);eligible=[(distance(position,c),i) for i,c in enumerate(cp) if distance(position,c)>=80 and 15<distance(c,goals)<=home-80];nearest=min(eligible)[1] if eligible else None
   samples=[e for e in ev if e.get('kind')==3 and e.get('mission_stage')==8 and e.get('move_index')==retreat_moves[0]['index'] and retreat_moves[0]['seq']<e['seq']<f['seq']]
   begins=[e for e in ev if e.get('kind')==54 and e.get('move_index')==retreat_moves[0]['index']];evidence=([begins[0]] if len(begins)==1 else [])+samples
   reference=xyz(evidence[0]) if evidence else None;last_motion=evidence[0]['frame'] if evidence else f['frame']
   for row in evidence[1:]:
    if distance(xyz(row),reference)>=9.99:reference=xyz(row);last_motion=row['frame']
   no_motion=bool(evidence) and f['frame']-last_motion>=250 and distance(xyz(f),reference)<10.01 and all(b['frame']-a['frame']<=3 for a,b in zip(evidence,evidence[1:]))
   movement=distance(xyz(z),position);gain=home-distance(xyz(z),goals);arrival_rows=last_samples(ev,z['seq'],8,move_index=retreat_moves[1]['index'])
   resume_valid=z.get('arg')==1 and (movement>=119.95 or gain>=79.95) or z.get('arg')==2 and len(arrival_rows)==3 and all(distance(xyz(e),cp[index])<=15.01 for e in arrival_rows)
   route_ok=route_ok and n.get('retreat_replans')==2 and n.get('retreat_mode')==0 and n.get('fallback_checkpoint_index')==index==nearest and f.get('state_id')==16 and f.get('path')==0 and no_motion and resume_valid and math.dist(retreat_moves[1]['goal'],cp[index])<=.05 and math.dist(retreat_moves[2]['goal'],goals)<=.05 and retreat_moves[0]['seq']<f['seq']<retreat_moves[1]['seq']<z['seq']<retreat_moves[2]['seq']
  else:route_ok=False
 else:route_ok=False
 checks['bounded_direct_goal_fallback_policy']=bool(route_ok)
 checks['retreat_effect']=retreat_verified
 long_retreat_verified=bool(retreat_verified and distance(xyz(retreat_start[0]),xyz(retreat_gates[0]))>=120)
 orders=[e for e in ev if e.get('kind') in [34,12,13,35] and e.get('tag')==2];post=[e for e in ev if e.get('kind')==30 and e.get('lease_stage')==7]
 order_ok=len(orders)==4 and [e.get('kind') for e in orders]==[34,12,13,35] and all(e.get('arg')==target and e.get('arg_source')==1 and e.get('arg_shots')==0x7fffffff and e.get('mission_stage')==6 and e.get('frame')==attack for e in orders) and len(post)==1 and orders[-1]['seq']<post[0]['seq'] and n.get('attack_calls')==n.get('attack_facade_calls')==n.get('attack_private_calls')==1 and n.get('limit_after')==0x7fffffff
 checks['normal_script_attack']=order_ok and 0<attack<returned and n.get('engage_started')==attack and post[0]['frame']-attack<=n.get('engage_limit',0)+2
 boundaries=[]
 for kind in [37,58,42,43,59,60,38]:boundaries.append([e for e in ev if e.get('kind')==kind])
 checks['stop_prepare_attack_retreat_order']=all(len(x)==1 for x in boundaries) and order_ok and boundaries[0][0]['seq']<boundaries[1][0]['seq']<boundaries[2][0]['seq']<boundaries[3][0]['seq']<orders[0]['seq']<orders[-1]['seq']<post[0]['seq']<boundaries[4][0]['seq']<boundaries[5][0]['seq']<boundaries[6][0]['seq']
 all_private=[e for e in ev if e.get('kind') in [32,33] and issued<=e.get('frame',0)<returned]
 checks['private_stop_pairs']=len(all_private)==2*(5+len(replay)) and all(a.get('kind')==32 and b.get('kind')==33 and a.get('frame')==b.get('frame') and a.get('arg')==b.get('arg')==1 and a.get('caller')==b.get('caller')==0x787791 and a.get('lease_stage')==b.get('lease_stage') and (a.get('lease_stage')!=3 or a.get('mission_stage')==b.get('mission_stage')==4 and a.get('state_id')==96 and b.get('state_id')==16 and a.get('active_weapon_asset')==b.get('active_weapon_asset')==AK) for a,b in zip(all_private[::2],all_private[1::2]))
 hits=[]
 for e in ev:
  if e.get('kind')!=20 or e.get('mission_stage')!=6 or e.get('damage_source')!=source or e.get('target_id')!=target or not finite(e.get('damage_reported')) or e['damage_reported']<=0 or not close(e.get('damage_before',0)-e.get('damage_after',0),e['damage_reported']):continue
  packets=damage_packet(e,source,report.get('private_target',{}).get('address'));commits=[x for x in ev if x.get('kind')==24 and x.get('mission_stage')==6 and x.get('damage_source')==source and x.get('target_id')==target and x.get('frame')==e.get('frame') and x.get('tick')==e.get('tick') and order_ok and orders[-1]['seq']<x['seq']<e['seq']<post[0]['seq'] and all(close(x.get(k),e.get(k)) for k in ['damage_before','damage_after','damage_reported'])];ammo=[x for x in ev if x.get('kind')==22 and x.get('mission_stage')==6 and x.get('damage_source')==source and abs(x.get('frame',-100)-e['frame'])<=2 and abs(x.get('tick',0)-e.get('tick',0))<=200 and x.get('active_weapon_asset')==AK and x.get('active_weapon_entry')==n.get('weapon_entry') and x.get('damage_before',0)>x.get('damage_after',0)>=0]
  if len(packets)==len(commits)==len(ammo)==1:hits.append(dict(body_event_seq=e['seq'],commit_event_seq=commits[0]['seq'],ammo_event_seq=ammo[0]['seq'],body_frame=e['frame'],damage=e['damage_reported'],packet=packets[0]))
 source_hits=[e for e in ev if e.get('kind')==20 and e.get('damage_source')==source];checks['direct_source_effect']=bool(hits) and len(hits)==len(source_hits)==n.get('damage_count') and close(sum(h['damage'] for h in hits),n.get('damage_total'))
 drops=[e for e in ev if e.get('kind')==22 and e.get('mission_stage')==6];initial_ammo=n.get('weapon_ammo',0);last=n.get('last_ammo',-1)
 checks['same_entry_ammo']=type(initial_ammo) is int and 1<=initial_ammo<=3 and bool(drops) and n.get('shot_samples')==len(drops) and close(drops[0].get('damage_before'),initial_ammo) and close(drops[-1].get('damage_after'),last) and all(close(a.get('damage_after'),b.get('damage_before')) for a,b in zip(drops,drops[1:])) and 0<=last<initial_ammo and all(order_ok and orders[-1]['seq']<e['seq']<post[0]['seq'] for e in drops)
 binding=report.get('weapon_asset_binding',{});checks['immutable_ak_asset']=binding.get('session_id')==report.get('session_id') and binding.get('pid')==pre.get('pid') and binding.get('reported_entry')==hex(n.get('weapon_entry',0)) and binding.get('reported_template')==hex(n.get('weapon_template',0)) and binding.get('asset_type')=='0x94d4d96e' and binding.get('asset_id')=='0x447ea26e'
 handoff=[e['seq'] for e in ev if e.get('kind')==14 and e.get('tag')==3 and e.get('arg')==1];end_seq=handoff[0] if len(handoff)==1 else 0
 checks['no_native_override']=bool(end_seq) and not any(e.get('tag')==0 and e.get('kind') in [10,12,14,16,18,30,52,54] and issued<=e.get('frame',0) and e['seq']<end_seq for e in ev)
 checks['native_pool_return']=release['return_verified']
 effect=checks['direct_source_effect'] and checks['same_entry_ammo'] and checks['immutable_ak_asset'] and checks['normal_script_attack'];ok=all(v is True for v in checks.values())
 return dict(status='continuous_ak_combat_mission_verified' if ok else 'not_passed',checks=checks,effect_verified=bool(effect),approach_verified=bool(approach_verified),long_approach_verified=long_approach_verified,long_retreat_verified=long_retreat_verified,retreat_verified=bool(retreat_verified),restoration_verified=release['restoration_verified'],new_order_fire_association_verified=bool(effect),source_damage_amount=sum(h['damage'] for h in hits),qualified_hits=hits,harass_economy_verified=bool(ok and rq.get('target_role')=='economy'),actor_roles=['infantry'],fallback_branch_observed=bool(fallbacks),fallback_replan_sequence_verified=bool(route_ok and fallbacks),fallback_field_effect_verified=bool(ok and fallbacks),restoration=release,reason_code=REASONS.get(n.get('reason_code'),'unknown'),mission_protocol='continuous_tactical_v1')
def qualify_path(path):
 path=Path(path).resolve();raw=path.read_bytes();result=qualify(json.loads(raw.decode('utf-8-sig')));sources=[dict(path=str(DIRECTORY/name),sha256=sha(DIRECTORY/name),purpose='immutable_mission_source') for name in ['mission_tick.inc','mission_contract.py','origin_resolution.py']]+[dict(path=str(HERE/'pre_dispatch_v3_contract.py'),sha256=sha(HERE/'pre_dispatch_v3_contract.py'),purpose='pre_native_launch_boundary')];result.update(source_report=str(path),source_sha256=hashlib.sha256(raw).hexdigest(),qualifier_sha256=sha(__file__),supplemental_sources=sources,sdk_source=dict(name='SovietAntiInfantryInfantryAK47',source_sha256='7a82e52aa6142f96271173195366227b21a552657bd683f7a33a22e770e1bad1',clip_size=3,damage_type='GUN',damage_delay_seconds=0.0,projectile_nugget=False));return result
def progress(report,mission_id):
 n=report.get('native',{});events=report.get('events',[])
 if not n.get('issued_frame') or not events or events[-1].get('mission_stage') not in range(1,11):return None
 last=events[-1];visible=[e for e in events if e.get('current_visible')==1 and point(e.get('visible_target_xyz')) and point(xyz(e))];latest=visible[-1] if visible else None
 return dict(mission_id=mission_id,stage=STAGES.get(last.get('mission_stage'),'armed'),revision=last['seq'],observed_frame=last['frame'],deadline_frame=report.get('request',{}).get('mission',{}).get('expires_frame',0),approach_distance=distance(xyz(latest),latest['visible_target_xyz']) if latest else None,own_hp=last.get('own_hp') if finite(last.get('own_hp')) else None,damage=sum(e['damage_reported'] for e in events if e.get('kind')==20 and e.get('mission_stage')==6 and finite(e.get('damage_reported'))),reason=REASONS.get(last.get('mission_reason'),'unknown'))
