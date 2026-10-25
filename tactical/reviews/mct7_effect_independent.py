"""Read-only second review of MCT7 raw events; never an SDK or capability grant.

This reconstructs order, packet/commit/ammunition, physical retreat and pool
return independently of the family7 qualifier. Only the previously audited
DamageInfo argument decoder and Stop raw-geometry helper are shared.
"""
import argparse,hashlib,json,math,sys
from pathlib import Path
P=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(P))
from combo_qualification import damage_packet,finite,close,AK,EXE,target_scope
from stop_sequence import settled_stop
import mission_actor_admission_v2 as admission
D=P/'mission-combat-v7'
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def number(x):return int(x,0) if isinstance(x,str) else x
def point(x):return isinstance(x,(list,tuple)) and len(x)==3 and all(finite(v) for v in x)
def xyz(e):return [e.get(k) for k in ['x','y','z']]
def xy(a,b):return math.hypot(a[0]-b[0],a[1]-b[1]) if point(a) and point(b) else float('inf')
def audit(r):
 n=r.get('native',{});pre=r.get('preflight',{});rq=r.get('request',{});ev=r.get('events',[]);mission=rq.get('mission',{});u=pre.get('selected',{});t=r.get('private_target',{});source=u.get('object_id');target=rq.get('target_object_id');thread=pre.get('window_thread');owner=number(pre.get('owner',0));checks={}
 rev=json.loads((D/'revision.json').read_text());files={'native_binary_sha256':D/'bin/TacticalMissionCombat7.dll','native_host_sha256':D/'bin/tactical_host.exe','wrapper_sha256':D/'lease.py','native_source_sha256':D/'lease.cpp','native_shared_sha256':D/'shared.h','mission_contract_sha256':D/'mission_contract.py','origin_resolution_helper_sha256':D/'origin_resolution.py','pre_dispatch_helper_sha256':P/'pre_dispatch_v7_contract.py'}
 checks['actual_c510_revision']=all(r.get(k)==rev[k]==digest(v) for k,v in files.items()) and r.get('native_binary_sha256')=='c5100e55662609dd5549289b3653500b420aa3d4bc4fda6c4d4d7f434842cadf' and r.get('native_includes_sha256')==rev['native_includes_sha256']=={'mission_tick.inc':digest(D/'mission_tick.inc')}
 checks['dependency_fingerprints']=r.get('qualification_dependencies_sha256')==rev['qualification_dependencies_sha256']=={name:digest(P/name) for name in rev['qualification_dependencies_sha256']}
 actor=r.get('actor_admission',{});checks['actual_admission']=r.get('actor_admission_helper_sha256')==digest(P/'mission_actor_admission_v2.py') and admission.verify_evidence(actor)['verified'] and all(actor.get(k)==u.get(k) for k in ['object_id','address','type_hash']) and actor.get('owner')==pre.get('owner') and type(actor.get('frame')) is int and 0<=n.get('issued_frame',0)-actor['frame']<=60
 checks['identity_binding']=r.get('executable_sha256')==EXE and r.get('session_id')==pre.get('session_id')==n.get('session_id') and pre.get('commander_id')==n.get('commander_id') and pre.get('player_id')==3 and all(n.get(k)==rq.get(k) for k in ['command_id','task_id','seq']) and type(rq.get('seq')) is int and rq['seq']>0 and u.get('type_hash')=='0x19ab11af' and t.get('object_id')==target and target_scope(r)
 checks['published_order_thread']=bool(ev) and n.get('callback_thread')==thread and all(e.get('seq')==i+1 and e.get('thread')==thread for i,e in enumerate(ev)) and all(b['frame']>=a['frame'] and 0<=((b['tick']-a['tick'])&0xffffffff)<0x80000000 for a,b in zip(ev,ev[1:]))
 checks['terminal_alive_normal']=r.get('status')=='finished' and r.get('host_exit')==0 and n.get('phase')==3 and n.get('error')==0 and n.get('restore_mask')==16383 and n.get('active')==n.get('overflow')==n.get('lifecycle_fail')==0
 orders=[e for e in ev if e.get('kind') in [34,12,13,35] and e.get('tag')==2];posts=[e for e in ev if e.get('kind')==30 and e.get('lease_stage')==7];start=orders[-1]['seq'] if len(orders)==4 else 0;end=posts[0]['seq'] if len(posts)==1 else len(ev)+1
 order_ok=len(orders)==4 and [e['kind'] for e in orders]==[34,12,13,35] and all(e.get('arg')==target and e.get('arg_source')==1 and e.get('arg_shots')==0x7fffffff and e.get('mission_stage')==6 and e.get('frame')==n.get('attack_issued_frame') and e.get('current_visible')==1 for e in orders)
 checks['unique_native_script_attack']=order_ok and n.get('attack_calls')==n.get('attack_facade_calls')==n.get('attack_private_calls')==1 and n.get('limit_after')==0x7fffffff
 checks['brief_profile_and_limit']=mission.get('engagement_policy')=='brief_raid_single_order_native_burst' and mission.get('damage_goal_cap')==30. and mission.get('damage_goal_fraction')==.2 and mission.get('engage_frames')==n.get('engage_limit')==60 and len(posts)==1 and 0<=posts[0]['frame']-n.get('attack_issued_frame',0)<=60
 ammo=[e for e in ev if e.get('kind') in [22,67] and e.get('mission_stage')==6 and start<e.get('seq',0)<end];previous=n.get('weapon_ammo');chain=type(previous) is int and 1<=previous<=3;rounds=refills=0
 for e in ammo:
  before,after=e.get('damage_before'),e.get('damage_after');ok=all(finite(v) and v==int(v) and 0<=v<=3 for v in [before,after]) and close(before,previous) and e.get('active_weapon_asset')==AK and e.get('active_weapon_entry')==n.get('weapon_entry') and e.get('active_weapon_ammo')==after and e.get('damage_source')==source and type(e.get('ammo_previous_frame')) is int and n.get('attack_issued_frame',0)<=e['ammo_previous_frame']<=e.get('frame',-1) and 0<=((e.get('tick',0)-e.get('ammo_previous_tick',0))&0xffffffff)<=400
  if e['kind']==22:
   ok=ok and finite(before) and finite(after) and before>after
   if finite(before) and finite(after):rounds+=max(0,int(before-after))
  else:ok=ok and before<after and after==3;refills+=1
  chain=chain and ok;previous=after
 chain=bool(chain and ammo and close(previous,n.get('last_ammo')) and n.get('shot_samples')==sum(e['kind']==22 for e in ammo) and n.get('rounds_consumed')==rounds and n.get('reload_samples')==refills and n.get('weapon_binding_fail')==0)
 hits=[]
 def health(e):return e.get('health_pre_visible')==e.get('health_post_identity')==1 and e.get('health_observed_frame')==e.get('frame') and e.get('health_actor')==number(t.get('address',0)) and e.get('health_body')==number(t.get('body',0)) and e.get('health_post_id')==target and e.get('health_post_owner')==t.get('owner') and e.get('health_post_template')==t.get('template') and e.get('health_post_vtable')==0xc37fe8
 for e in ev:
  if e.get('kind')!=20 or e.get('mission_stage')!=6 or not start<e.get('seq',0)<end or e.get('damage_source')!=source or e.get('target_id')!=target or not health(e) or not finite(e.get('damage_reported')) or e['damage_reported']<=0 or not close(e.get('damage_before',0)-e.get('damage_after',0),e['damage_reported']):continue
  packets=damage_packet(e,source,number(t.get('address',0)))
  commits=[x for x in ev if x.get('kind')==24 and x.get('mission_stage')==6 and start<x.get('seq',0)<e['seq'] and x.get('frame')==e.get('frame') and x.get('tick')==e.get('tick') and x.get('target_id')==target and x.get('damage_source')==source and health(x) and all(close(x.get(k),e.get(k)) for k in ['damage_before','damage_after','damage_reported'])]
  consumed=[a for a in ammo if a['kind']==22 and e['seq']<a['seq'] and a['ammo_previous_frame']<=e['frame']<=a['frame'] and 0<=((e['tick']-a['ammo_previous_tick'])&0xffffffff)<=((a['tick']-a['ammo_previous_tick'])&0xffffffff)]
  if order_ok and len(packets)==len(commits)==len(consumed)==1:hits.append(dict(seq=e['seq'],frame=e['frame'],commit_seq=commits[0]['seq'],ammo_seq=consumed[0]['seq'],amount=e['damage_reported'],hp_before=e['damage_before'],hp_after=e['damage_after'],packet=packets[0]))
 amount=sum(h['amount'] for h in hits);allhits=[e for e in ev if e.get('kind')==20 and e.get('damage_source')==source]
 checks['packet_commit_ammo_all_source_hits']=bool(hits) and len(hits)==len(allhits)==n.get('damage_count') and close(amount,n.get('damage_total')) and chain and len(hits)<=rounds
 binding=r.get('weapon_asset_binding',{});checks['immutable_ak_asset']=binding.get('session_id')==r.get('session_id') and binding.get('pid')==pre.get('pid') and binding.get('reported_entry')==hex(n.get('weapon_entry',0)) and binding.get('reported_template')==hex(n.get('weapon_template',0)) and binding.get('asset_type')=='0x94d4d96e' and binding.get('asset_id')=='0x447ea26e'
 checks['source_six_and_natural_refill']=len(hits)>=6 and rounds>=6 and refills>=1 and any(any(h['seq']<e['seq'] for h in hits) and any(h['seq']>e['seq'] for h in hits) for e in ammo if e['kind']==67) and max((h['frame'] for h in hits),default=0)-min((h['frame'] for h in hits),default=0)>=15
 entries=[e for e in ev if e.get('kind')==68];goal=None
 if len(entries)==1 and finite(entries[0].get('damage_before')) and entries[0]['damage_before']>0:goal=min(30.,entries[0]['damage_before']*.2)
 checks['actual_visible_entry_goal']=goal is not None and entries[0].get('current_visible')==1 and entries[0]['seq']<orders[0]['seq'] if orders else False
 checks['actual_visible_entry_goal']=bool(checks['actual_visible_entry_goal'] and close(entries[0].get('damage_after'),goal) and close(n.get('engagement_initial_hp'),entries[0]['damage_before']) and close(n.get('damage_goal'),goal) and n.get('engagement_goal_reached')==1 and (amount>=goal-.05 or any(h['hp_after']<=0 for h in hits)))
 held=[e for e in ev if e.get('kind')==14 and e.get('tag')==1 and e.get('arg')==0];handoff=[e for e in ev if e.get('kind')==14 and e.get('tag')==3 and e.get('arg')==1];returned=[e for e in ev if e.get('kind')==15 and e.get('tag')==3 and e.get('arg')==1];a=held[0]['seq'] if len(held)==1 else 0;b=handoff[0]['seq'] if len(handoff)==1 else 0
 exclusive=[e for e in ev if a<e.get('seq',0)<b];manager=number(pre.get('ai',0))+0x104
 adds=[e for e in ev if e.get('kind')==16 and e.get('tag')==3 and e.get('arg')==manager and e.get('caller')==0x83885b];removes=[e for e in ev if e.get('kind')==18 and e.get('tag')==1 and e.get('arg')==manager and e.get('caller')==0x838877]
 checks['single_lease_live_pool_return']=len(held)==len(handoff)==len(returned)==len(adds)==len(removes)==1 and a<removes[0]['seq']<b<adds[0]['seq']<returned[0]['seq'] and n.get('detach_calls')==n.get('return_calls')==n.get('return_verified')==1 and returned[0].get('frame')==n.get('returned_frame') and returned[0].get('team')==number(pre.get('default_team',0)) and all(e.get('owner')==owner and finite(e.get('own_hp')) and e['own_hp']>0 for e in returned)
 checks['no_inlease_override']=a>0 and b>a and not any(e.get('tag')==0 and e.get('kind') in [10,12,14,16,18,30,52,54] and a<e.get('seq',0)<returned[0]['seq'] for e in ev) if len(returned)==1 else False
 stops={}
 for stage,gate in [(0,37),(6,58),(4,43),(9,66),(7,59),(2,38)]:
  rows=[dict(e,kind=23 if e.get('kind')==33 else 24 if e.get('kind')==gate else e['kind']) for e in exclusive if e.get('lease_stage')==stage and e.get('kind') in [3,33,gate]];stops[str(stage)]=settled_stop(rows)['verified']
 checks['all_six_normal_stops_settled']=all(stops.values())
 origins=mission.get('retreat_point',{}).get('xyz');arrival=[e for e in ev if e.get('kind')==60];retreat=[e for e in ev if e.get('kind')==50 and e.get('arg')==7];last=[]
 if len(arrival)==1:
  seen=set()
  for e in reversed(ev):
   if e.get('kind')==3 and e.get('mission_stage')==8 and e.get('seq',0)<arrival[0]['seq'] and e.get('frame') not in seen:last.append(e);seen.add(e['frame'])
   if len(last)==3:break
  last.reverse()
 retreat_distance=xy(xyz(retreat[0]),xyz(arrival[0])) if len(retreat)==len(arrival)==1 else None
 checks['physical_long_home_return']=len(last)==3 and all(xy(xyz(e),origins)<=15 and abs(e['z']-origins[2])<=10 for e in last) and len({e['frame'] for e in last})==3 and retreat_distance is not None and retreat_distance>=120 and len(returned)==1 and arrival[0]['seq']<returned[0]['seq']
 result=all(v is True for v in checks.values());return dict(status='independent_effect_chain_verified_not_a_grant' if result else 'not_passed',checks=checks,source_damage_amount=amount,qualified_hits=hits,observed_rounds_consumed=rounds,observed_reload_count=refills,goal=goal,retreat_displacement=retreat_distance,stops=stops,arrival_frames=[e['frame'] for e in last],actual_attack_frame=n.get('attack_issued_frame'),actual_return_frame=n.get('returned_frame'),native_reason=n.get('reason_code'),normal_return_verified=checks['single_lease_live_pool_return'],scene_disposal_is_not_return=True,completion_claim=False,sdk_or_game_calls=0)
def audit_path(path):
 path=Path(path);raw=path.read_bytes();result=audit(json.loads(raw.decode('utf-8-sig')));result.update(source_report=str(path.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),reviewer_sha256=digest(__file__),shared_decoders={name:digest(P/name) for name in ['combo_qualification.py','stop_sequence.py']});return result
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('raw',type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();result=audit_path(args.raw)
 with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
 print(json.dumps({k:result[k] for k in ['status','source_damage_amount','observed_reload_count','actual_return_frame']}))
