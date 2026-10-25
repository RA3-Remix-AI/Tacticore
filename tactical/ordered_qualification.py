"""Independent qualification of bounded Conscript AK orders; never invokes game code.
The immutable diagnostic assessment is retained. This verifier joins a decoded
current Body-call DamageInfo packet, exact order, near-tick ammo observation,
normal Stop boundaries and native AI pool return. No single-shot claim.
"""
import hashlib,json,math,struct
from pathlib import Path
from stop_sequence import settled_stop
from restoration import single_control_release
EXE='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
DLL='9c898e61651698fd04412c914b6a4c577dea941a20c6af31a88b38b9457af142'
HOST='80a6fb060d508be9855148b1cf909ccdffb7acafe4d84b7c1885feb7624fbbd9'
AK=0x447ea26e
SAFETY_SHA='1d14e41e10224fb2a8215a2321a7fbbbeae8434b8c006a80fd314f4a11e7719e'
GROUND_TARGET_ROLES=['infantry','armor','structure','economy']

def target_scope(report):
 path=Path(__file__).resolve().parent.parent/'visibility/template-safety-2d7873e1.json';raw=path.read_bytes();rq=report.get('request',{});target=report.get('private_target',{})
 if hashlib.sha256(raw).hexdigest()!=SAFETY_SHA or rq.get('safety_sha256')!=SAFETY_SHA:return False
 catalog=json.loads(raw);entry=catalog['templates'].get(target.get('type_hash'),{})
 return entry.get('role') in GROUND_TARGET_ROLES and rq.get('target_role')==entry.get('role') and (entry['role']!='economy' or target.get('type_hash')=='0xc45aaeab')

def finite(v):return type(v) in [int,float] and math.isfinite(v)
def close(a,b):return finite(a) and finite(b) and abs(a-b)<.05
def damage_packet(event,source,target_address):
 """Bind actual 78e313 return+argument to a packet inside captured raw stack.
 Body ABI:78e311 calls vt+10 with DamageInfo*, return78e313. The
 DamageNugget caller is7ad79e. This is an argument-bound packet, not an
 arbitrary stack word matching a source ID.
 """
 words=event.get('stack_words',[])[:event.get('stack_word_count',0)];base=event.get('stack_words_address',0);packets=[]
 if event.get('caller')!=0x78e313 or not base or len(words)>128:return packets
 for i,value in enumerate(words[:-5]):
  if value!=0x78e313:continue
  pointer=words[i+1]
  if pointer<base or (pointer-base)%4:continue
  at=(pointer-base)//4
  if at+36>=len(words) or words[i+2]!=target_address or words[i+4]!=0x7ad79e or words[i+5]!=pointer:continue
  packet=words[at:at+37]
  if packet[0]!=0xbe9508 or packet[1]!=0xbe9318 or packet[2]!=source or packet[4]!=AK or packet[5]!=AK or packet[7]!=21:continue
  damage=struct.unpack('<f',struct.pack('<I',packet[36]))[0];requested=struct.unpack('<f',struct.pack('<I',packet[35]))[0]
  if not finite(damage) or damage<=0 or not finite(requested) or requested<=0 or not close(damage,event.get('damage_reported')):continue
  packets.append(dict(argument_address=hex(pointer),source_actor_id=packet[2],weapon_asset_id=hex(packet[4]),warhead_asset_id=hex(packet[5]),damage_type='GUN',damage_type_id=21,requested_damage=requested,actual_damage=damage,packet_word_offset=at,caller_return=hex(value)))
 return packets

def qualify(report,template_binding=None):
 n=report.get('native',{});pre=report.get('preflight',{});rq=report.get('request',{});events=report.get('events',[]);source=pre.get('selected',{}).get('object_id');target=rq.get('target_object_id');thread=pre.get('window_thread');issued=n.get('issued_frame',0);attack=n.get('attack_issued_frame',0);returned=n.get('returned_frame',0);owner=int(pre.get('owner','0'),0);checks={}
 checks['finished']=report.get('status')=='finished' and report.get('host_exit')==0
 checks['certified_executor']=report.get('executable_sha256')==EXE and report.get('native_binary_sha256')==DLL and report.get('native_host_sha256')==HOST
 checks['binding']=bool(source) and bool(target) and pre.get('player_id')==3 and n.get('session_id')==report.get('session_id')==pre.get('session_id') and n.get('commander_id')==pre.get('commander_id') and n.get('command_id')==rq.get('command_id') and n.get('task_id')==rq.get('task_id') and type(rq.get('seq')) is int and rq['seq']>0 and n.get('seq')==rq['seq']
 checks['actor_and_target_scope']=pre.get('selected',{}).get('type_hash')=='0x19ab11af' and target_scope(report) and report.get('private_target',{}).get('object_id')==target and report.get('private_target',{}).get('owner_player_id') not in [None,3]
 checks['thread_owner']=bool(events) and n.get('callback_thread')==thread and all(e.get('thread')==thread for e in events) and all(e.get('owner')==owner for e in events if issued<=e.get('frame',0)<=returned and e.get('kind')!=4)
 checks['published_order']=bool(events) and all(e.get('seq')==i+1 for i,e in enumerate(events))
 checks['monotonic_frame_tick']=bool(events) and all(type(e.get('frame')) is int and type(e.get('tick')) is int for e in events) and all(b['frame']>=a['frame'] and 0<=((b['tick']-a['tick'])&0xffffffff)<0x80000000 for a,b in zip(events,events[1:]))
 checks['critical_finite']=all(all(finite(e.get(k)) for k in ['x','y','z','damage_before','damage_after','damage_reported']) for e in events) and all(not any(k in ['x','y','z','damage_before','damage_after','damage_reported'] for k in e.get('invalid_float_fields',[])) for e in events)
 checks['frame_bound']=0<issued<=attack<=returned and returned-issued<=rq.get('lease_frames',0)+35
 checks['clean_hooks']=n.get('phase')==3 and n.get('error')==0 and n.get('restore_mask')==2047 and n.get('active')==0 and n.get('overflow')==0 and n.get('lifecycle_fail')==0
 checks['bounded_normal_burst']=n.get('attack_calls')==n.get('attack_facade_calls')==n.get('attack_private_calls')==1 and n.get('detach_calls')==n.get('return_calls')==1 and n.get('move_calls')==0 and n.get('limit_after')==0x7fffffff and n.get('stop_calls')==n.get('private_stop_calls')==2 and n.get('stop_failed')==0
 stops=[]
 for stage,kind in [(0,37),(2,38)]:
  translated=[dict(e,kind=23 if e.get('kind')==33 else 24 if e.get('kind')==kind else e.get('kind')) for e in events if e.get('lease_stage')==stage and e.get('kind') in [3,33,kind]];bound=settled_stop(translated);gates=[e for e in events if e.get('kind')==kind];stops.append(bound)
  checks['stop_'+str(stage)]=bound['verified'] and len(gates)==1 and gates[0].get('state_id')==16 and gates[0].get('holder')==0 and gates[0].get('requested')==[0.,0.,0.] and gates[0].get('effective')==[0.,0.,0.]
 orders=[e for e in events if e.get('kind') in [12,13,34,35] and e.get('tag')==2]
 checks['unique_script_order']=all(sum(e.get('kind')==kind and e.get('arg')==target and e.get('arg_source')==1 and e.get('arg_shots')==0x7fffffff and e.get('lease_stage')==1 and e.get('frame')==attack for e in orders)==1 for kind in [12,13,34,35]) and len(orders)==4
 pre_gates=[e for e in events if e.get('kind')==37];post_stops=[e for e in events if e.get('kind')==30 and e.get('lease_stage')==2];post_gates=[e for e in events if e.get('kind')==38];returns=[e for e in events if e.get('kind')==15 and e.get('tag')==3]
 ordered_boundary=len(pre_gates)==len(post_stops)==len(post_gates)==len(returns)==1 and len(orders)==4 and pre_gates[0]['seq']<orders[0]['seq']<orders[1]['seq']<orders[2]['seq']<orders[3]['seq']<post_stops[0]['seq']<post_gates[0]['seq']<returns[0]['seq'] and [e['kind'] for e in orders]==[34,12,13,35]
 checks['ordered_stop_attack_return_sequence']=ordered_boundary
 checks['no_lease_override']=not any(e.get('tag')==0 and e.get('kind') in [10,12,14,16,18,30] and issued<=e.get('frame',0)<returned for e in events)
 if not checks['critical_finite']:return dict(status='not_passed',checks=checks,new_order_fire_association_verified=False,qualified_hits=[],actor_roles=['infantry'],harass_economy_verified=False)
 qualified=[]
 for hit in events:
  if hit.get('kind')!=20 or hit.get('lease_stage')!=1 or hit.get('damage_source')!=source or hit.get('target_id')!=target or not attack<=hit.get('frame',0)<returned or not close(hit.get('damage_before',0)-hit.get('damage_after',0),hit.get('damage_reported')) or hit.get('damage_reported',0)<=0:continue
  packets=damage_packet(hit,source,report.get('private_target',{}).get('address'))
  commits=[e for e in events if ordered_boundary and e.get('kind')==24 and e.get('lease_stage')==1 and e.get('damage_source')==source and e.get('target_id')==target and e.get('frame')==hit['frame'] and e.get('tick')==hit.get('tick') and orders[-1]['seq']<e.get('seq',0)<hit['seq']<post_stops[0]['seq'] and close(e.get('damage_before'),hit['damage_before']) and close(e.get('damage_after'),hit['damage_after']) and close(e.get('damage_reported'),hit['damage_reported'])]
  ammo=[e for e in events if e.get('kind')==22 and e.get('lease_stage')==1 and e.get('damage_source')==source and e.get('target_id')==target and attack<=e.get('frame',0)<returned and abs(e.get('frame',-100)-hit['frame'])<=2 and abs(e.get('tick',0)-hit.get('tick',0))<=200 and finite(e.get('damage_before')) and finite(e.get('damage_after')) and e['damage_before']>e['damage_after']>=0]
  if len(packets)==len(commits)==len(ammo)==1:qualified.append(dict(body_event_seq=hit['seq'],commit_event_seq=commits[0]['seq'],ammo_event_seq=ammo[0]['seq'],body_frame=hit['frame'],ammo_frame=ammo[0]['frame'],damage=hit['damage_reported'],packet=packets[0]))
 source_hits=[e for e in events if e.get('kind')==20 and e.get('damage_source')==source and e.get('target_id')==target and issued<=e.get('frame',0)<returned]
 checks['direct_ak_source_damage']=bool(qualified) and len(qualified)==len(source_hits)==n.get('damage_count') and close(sum(x['damage'] for x in qualified),n.get('damage_total'))
 initial=n.get('weapon_ammo',0);last=n.get('last_ammo',-1)
 checks['same_entry_ammo']=n.get('weapon_entry',0)>0 and n.get('weapon_slot',0)>0 and type(initial) is int and 1<=initial<=3 and n.get('shot_samples')==len([e for e in events if e.get('kind')==22 and attack<=e.get('frame',0)<returned]) and 0<=last<initial and all(orders[-1]['seq']<e['seq']<post_stops[0]['seq'] and 0<=e['damage_after']<e['damage_before']<=3 for e in events if e.get('kind')==22 and e.get('lease_stage')==1) if ordered_boundary else False
 drops=[e for e in events if e.get('kind')==22 and e.get('lease_stage')==1]
 checks['same_entry_ammo']=checks['same_entry_ammo'] and bool(drops) and close(drops[0]['damage_before'],initial) and close(drops[-1]['damage_after'],last) and all(close(a['damage_after'],b['damage_before']) for a,b in zip(drops,drops[1:]))
 release=single_control_release(report,2047);checks['native_pool_return']=release['return_verified']
 binding=report.get('weapon_asset_binding') or template_binding;checks['observed_ak_template']=bool(binding) and binding.get('session_id')==report.get('session_id') and binding.get('pid')==pre.get('pid') and binding.get('reported_entry')==hex(n.get('weapon_entry',0)) and binding.get('reported_template')==hex(n.get('weapon_template',0)) and binding.get('asset_type')=='0x94d4d96e' and binding.get('asset_id')=='0x447ea26e' and binding.get('method')=='reported_template_plus4_to_schema_to_asset_header'
 ok=all(v is True for v in checks.values())
 return dict(status='bounded_ak_ordered_attack_verified' if ok else 'not_passed',checks=checks,new_order_fire_association_verified=ok,qualified_hits=qualified,stop_boundaries=stops,restoration=release,scope='conscript_ak_direct_ground_ordered_burst',actor_roles=['infantry'],harass_economy_verified=ok and rq.get('target_role')=='economy',single_shot_claim=False)


def qualify_path(path):
 path=Path(path).resolve();raw=path.read_bytes();report=json.loads(raw.decode('utf-8-sig'));sha=hashlib.sha256(raw).hexdigest();binding=report.get('weapon_asset_binding');sources=[]
 if not binding:
  matches=[]
  for candidate in path.parent.glob('*template.json'):
   try:
    data=candidate.read_bytes();value=json.loads(data.decode('utf-8-sig'))
    if value.get('report_sha256')==sha and Path(value.get('report','')).resolve()==path:matches.append((value,candidate,hashlib.sha256(data).hexdigest()))
   except (OSError,ValueError):continue
  if len(matches)==1:
   binding,candidate,digest=matches[0];sources.append(dict(path=str(candidate),sha256=digest,report_sha256=sha))
 result=qualify(report,binding);result.update(source_report=str(path),source_sha256=sha,supplemental_sources=sources,qualifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),sdk_source=dict(name='SovietAntiInfantryInfantryAK47',source_sha256='7a82e52aa6142f96271173195366227b21a552657bd683f7a33a22e770e1bad1',clip_size=3,damage_type='GUN',damage_delay_seconds=0.0,projectile_nugget=False))
 return result
