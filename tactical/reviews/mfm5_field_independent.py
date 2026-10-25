"""Independent MF5 field audit. Pure files only; no capability or game calls.

Uses the previously audited DamageInfo decoder and Stop geometry helper, but
rebuilds breadcrumb, reference, damage/support, retreat and release evidence
without delegating the result to the runtime qualifier.
"""
import argparse,hashlib,importlib.util,json,math,re,sys
from pathlib import Path
T=Path(__file__).resolve().parents[1];B=T/'mission-formation-v5';sys.path.insert(0,str(T))
from combo_qualification import damage_packet,AK
from stop_sequence import settled_stop

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def num(v):return int(v,0) if isinstance(v,str) else v
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def point(v):return isinstance(v,list) and len(v)==3 and all(finite(x) for x in v)
def xyz(e):return [e.get(k) for k in ('x','y','z')]
def dist(a,b):return math.dist(a[:2],b[:2]) if point(a) and point(b) else math.inf
def same(a,b):return point(a) and point(b) and all(abs(x-y)<=.01 for x,y in zip(a,b))
def distinct(rows):return list({e['frame']:e for e in rows}.values())
def stop3(ev,role,gate):
 rows=[e for e in ev if e.get('role')==role and e['seq']<gate['seq']];stops=[e for e in rows if e.get('kind')==33 and e.get('tag')==4 and e.get('arg')==1 and e.get('caller')==0x787791]
 if not stops:return False
 s=stops[-1];samples=[e for e in rows if e.get('kind')==3 and s['seq']<e['seq']];last=distinct(samples)[-3:];chain=[e for e in rows if e.get('kind') in (30,32,33,31) and e.get('tag')==4 and e['frame']==s['frame']]
 return [e['kind'] for e in chain]==[30,32,33,31] and all(e.get('arg')==1 for e in chain) and len(last)==3 and all(e.get('state_id')==16 and e.get('source')==1 and e.get('path')==e.get('holder')==0 and not e.get('sm_flags',65535)&65535 for e in last) and settled_stop([dict(s,kind=23)]+samples+[dict(gate,kind=24)])['verified']
def actual_path(ev,role,stage,until):
 origin=next((e for e in ev if e.get('kind')==80 and e['role']==role and e.get('mission_stage')==stage),None)
 if not origin:return None
 previous=origin['breadcrumb']['xyz'];frame=origin['frame'];total=0.
 for e in ev:
  if origin['seq']<e['seq']<=until and e['role']==role and e.get('mission_stage')==stage and e['kind'] in (3,80) and e['frame']>frame:
   total+=dist(previous,xyz(e));previous=xyz(e);frame=e['frame']
 return total

def review(report):
 r=report;n=r.get('native',{});pre=r.get('preflight',{});rq=r.get('request',{});ev=r.get('events',[]);checks={};actors=[pre.get('selected',{}),pre.get('support',{})];types=[0x19ab11af,0x2c358c61];source=actors[0].get('object_id');target=rq.get('target_object_id')
 rev=json.loads((B/'revision.json').read_text());files={'native_binary_sha256':B/'bin/TacticalMissionFormation5.dll','native_host_sha256':B/'bin/tactical_host.exe','native_source_sha256':B/'lease.cpp','native_shared_sha256':B/'shared.h'}
 checks['compiled_native_source_joint_pin']=all(rev.get(k)==r.get(k)==sha(p) for k,p in files.items()) and r.get('native_includes_sha256')==rev.get('native_includes_sha256')=={p.name:sha(p) for p in B.glob('*.cpp.inc')} and r.get('native_revision_sha256')==sha(B/'revision.json')
 checks['frozen_q_and_wrapper']=r.get('wrapper_sha256')==sha(B/'lease.py') and sha(B/'formation_mission_qualification.py')=='125010f807677b8d2081dd35133ae7d87b666ccddc8d3d61c89f50ae5b7074c6'
 checks['native_and_child_clean_terminal']=r.get('status')=='finished' and r.get('host_exit')==0 and n.get('phase')==3 and n.get('error')==n.get('active')==n.get('overflow')==0 and n.get('restore_mask')==8191
 checks['published_clock_identity']=bool(ev) and all(e.get('seq')==i+1 and e.get('thread')==pre.get('window_thread') and (e.get('kind')==4 or e.get('role') in (0,1) and e.get('owner')==num(pre.get('owner')) and e.get('unit_id')==actors[e['role']].get('object_id')) for i,e in enumerate(ev)) and all(b['frame']>=a['frame'] and 0<=((b['tick']-a['tick'])&0xffffffff)<0x80000000 for a,b in zip(ev,ev[1:]))
 published={};byrole=[[],[]];surface=[]
 for e in ev:
  if e.get('kind')!=80:continue
  c=e['breadcrumb'];role=c.get('role');words=c.get('status_words');valid=role in (0,1) and isinstance(words,list) and len(words)==7 and all(type(w) is int and 0<=w<=0xffffffff for w in words)
  if valid:
   u=actors[role];valid=all(not(words[i//32]&(1<<(i%32))) for i in (0,7,8,51,61,161,207,211)) and c.get('holder')==0 and type(c.get('height_flags')) is int and c['height_flags']&4 and finite(c.get('height')) and abs(c['height'])<=.5 and finite(c.get('hp')) and c['hp']>0 and point(c.get('xyz')) and c.get('thing')==num(u.get('address')) and c.get('update')==num(u.get('ai_address')) and c.get('object_id')==u.get('object_id') and c.get('type_hash')==types[role] and c.get('owner')==num(pre.get('owner')) and c.get('index')==len(byrole[role]) and c.get('published_seq')==e['seq'] and c.get('frame')==e['frame'] and c.get('mission_stage')==e.get('mission_stage') and e.get('arg')==c.get('index') and same(c.get('xyz'),xyz(e))
  surface.append(bool(valid))
  if role in (0,1):published[(role,c['index'])]=c;byrole[role].append(c)
 checks['actual_ground_publications_and_immutable_header']=bool(surface) and all(surface) and n.get('crumbs')==byrole
 move_groups=[]
 for e in ev:
  if e.get('kind')!=50 or e.get('tag')!=6:continue
  rows=[x for x in ev if x['seq']>=e['seq'] and x['role']==e['role'] and x.get('tag')==6 and x['kind'] in (50,10,11,51)][:4]
  good=[x['kind'] for x in rows]==[50,10,11,51] and all(x.get('arg')==1 and x['frame']==e['frame'] and same(x.get('command_xyz'),e.get('command_xyz')) for x in rows) and rows[1].get('argument_path')==0 and rows[1].get('argument_limit',0)>1e30
  move_groups.append(dict(seq=e['seq'],end=rows[-1]['seq'],role=e['role'],stage=e['mission_stage'],goal=e.get('command_xyz'),verified=good))
 checks['every_move_normal_source1']=bool(move_groups) and all(g['verified'] for g in move_groups)
 refs=[];last={};paired=[]
 for e in ev:
  if e.get('kind')!=81:continue
  c=e['breadcrumb'];stage=e['mission_stage'];leader=0 if stage==1 else 1 if stage==3 else None;role=e['role'];pub=published.get((c.get('role'),c.get('index')));phase=[x for x in byrole[c['role']] if x.get('mission_stage')==stage];first=bool(phase) and phase[0]==c;travel=actual_path(ev,leader,stage,e['seq']) if leader is not None else None;leader_rows=[x for x in ev if x['role']==leader and x['kind']==3 and x['frame']==e['frame'] and x['seq']<e['seq']];clear=dist(xyz(leader_rows[-1]),c['xyz']) if leader_rows else None
  next_seq=next((x['seq'] for x in ev if x['seq']>e['seq'] and x['kind']==81 and x['role']==role),len(ev)+1);moves=[g for g in move_groups if g['seq']>e['seq'] and g['role']==role];m=moves[0] if moves else None;gates=[x for x in ev if x['kind']==84 and x['role']==role and e['seq']<x['seq']<next_seq and x.get('breadcrumb')==c];stops=[x for x in ev if x['kind']==94 and x['role']==role and e['seq']<x['seq']<next_seq and x.get('breadcrumb')==c];gate=gates[0] if len(gates)==1 else None;samples=distinct([x for x in ev if gate and m and x['kind']==3 and x['role']==role and m['end']<x['seq']<gate['seq']])[-3:]
  good=pub==c and c['published_seq']<e['seq'] and c['mission_stage']==stage and leader==c['role'] and role==1-leader and e.get('follow_crumb_role')==leader and e.get('follow_crumb_index')==c['index'] and c['index']>last.get(stage,-1) and finite(travel) and travel-c['path_distance']>=(24.99 if first else 99.5) and finite(clear) and clear>=24.99 and m is not None and m['verified'] and same(m['goal'],c['xyz']) and len(samples)==3 and all(dist(xyz(x),c['xyz'])<=15 and abs(x['z']-c['xyz'][2])<=10 for x in samples) and gate['frame']==samples[-1]['frame'] and len(stops)==1 and gate['seq']<stops[0]['seq'] and stop3(ev,role,stops[0])
  last[stage]=c['index'];refs.append(dict(seq=e['seq'],stage=stage,role=role,source_index=c['index'],phase_origin=first,actual_leader_path=travel,leader_source_clear=clear,arrival_frames=[x['frame'] for x in samples],verified=bool(good)))
  rows=[x for x in ev if gate and x['kind']==90 and x['frame']==gate['frame'] and x['tick']==gate['tick'] and x['seq']>gate['seq'] and x.get('breadcrumb')==c];paired.append(len(rows)==2 and {x['role'] for x in rows}=={0,1})
 checks['every_prior_reference_arrival_and_stop']=bool(refs) and all(x['verified'] for x in refs) and {x['stage'] for x in refs}=={1,3};checks['actual_two_role_follow_checkpoints']=bool(paired) and all(paired)
 orders=[e for e in ev if e['kind'] in (34,12,13,35) and e.get('tag')==2];checks['one_explicit_source1_ak_attack']=[e['kind'] for e in orders]==[34,12,13,35] and all(e['role']==0 and e.get('arg_source')==1 and e.get('arg_shots')==0x7fffffff and e.get('arg')==target and e.get('target_visible')==1 and e.get('lease_stage')==1 for e in orders)
 hits=[]
 for e in ev:
  if e['kind']!=20 or e['role']!=0:continue
  packets=damage_packet(e,source,num(r.get('private_target',{}).get('address')));commits=[x for x in ev if x['kind']==24 and x['role']==0 and x.get('caller')==0x7d2946 and x['frame']==e['frame'] and x['tick']==e['tick'] and x['seq']<e['seq'] and all(x.get(k)==e.get(k) for k in ('damage_before','damage_after','damage_reported','damage_source','target_id'))];ammo=[x for x in ev if x['kind']==22 and x['role']==0 and x['seq']>e['seq'] and 0<=x['frame']-e['frame']<=3 and x.get('active_weapon_asset')==AK and x.get('active_weapon_entry')==n.get('weapon_entry') and x.get('damage_before',0)-x.get('damage_after',0)==1];hold=[x for x in ev if x['kind']==86 and x['role']==1 and x['seq']<e['seq']];support=[x for x in ev if x['kind']==3 and x['role']==1 and abs(x['frame']-e['frame'])<=3 and hold and dist(xyz(x),xyz(hold[-1]))<=15 and x.get('state_id')==16 and x.get('source')==1 and x.get('path')==x.get('holder')==0]
  good=checks['one_explicit_source1_ak_attack'] and len(packets)==len(commits)==len(ammo)==1 and bool(support) and orders[-1]['seq']<commits[0]['seq']<e['seq'] and e.get('target_visible')==commits[0].get('target_visible')==1 and e.get('damage_source')==source and e.get('target_id')==target and 0<e.get('damage_after',0)<e.get('damage_before',0) and abs(e['damage_before']-e['damage_after']-e['damage_reported'])<.05
  hits.append(dict(body_seq=e['seq'],commit_seq=commits[0]['seq'] if commits else None,ammo_seq=ammo[0]['seq'] if ammo else None,damage=e.get('damage_reported'),packet=packets[0] if packets else None,verified=bool(good)))
 checks['real_nonlethal_source_damage_and_support']=bool(hits) and all(x['verified'] for x in hits)
 homes=[];boundaries=[];overrides=[]
 for role in (0,1):
  begin=[e for e in ev if e['kind']==89 and e['role']==role];home=[e for e in ev if e['kind']==91 and e['role']==role];final=[e for e in ev if e['kind']==66 and e['role']==role];returns=[e for e in ev if e['kind']==5 and e['role']==role and e.get('tag')==3];baseline=[e for e in ev if e['kind']==71 and e['role']==role];origin=n.get('safe_support' if role else 'safe_front');samples=distinct([e for e in ev if len(home)==1 and e['kind']==3 and e['role']==role and e.get('mission_stage')==3 and e['seq']<home[0]['seq']])[-3:]
  good=len(begin)==len(home)==len(final)==len(returns)==len(baseline)==1 and same(origin,xyz(baseline[0])) and len(samples)==3 and all(dist(xyz(e),origin)<=15 and abs(e['z']-origin[2])<=10 for e in samples) and samples[-1]['frame']==home[0]['frame'] and dist(xyz(begin[0]),xyz(home[0]))>=120 and home[0]['seq']<final[0]['seq']<returns[0]['seq'] and stop3(ev,role,final[0]) and dist(xyz(final[0]),origin)<=15 and returns[0].get('team')==num(pre.get('default_team')) and returns[0].get('own_hp',0)>0
  transfer=[e for e in ev if e['kind']==15 and e['role']==role and e.get('tag')==3 and e.get('arg')==1];add=[e for e in ev if e['kind']==16 and e['role']==role and e.get('tag')==3 and e.get('arg')==num(pre.get('ai'))+0x104 and e.get('caller')==0x83885b];good=good and len(transfer)==len(add)==1 and final[0]['seq']<min(transfer[0]['seq'],add[0]['seq'])<returns[0]['seq'];homes.append(dict(role=role,verified=bool(good),arrival_frames=[e['frame'] for e in samples]))
  if baseline and returns:overrides.extend(e['seq'] for e in ev if e['role']==role and baseline[0]['seq']<e['seq']<returns[0]['seq'] and e.get('tag')==0 and e['kind'] in (10,12,14,16,18,30,50))
 checks['both_actual_long_retreat_and_live_pool_returns']=all(x['verified'] for x in homes);checks['no_in_lease_foreign_command']=not overrides
 starts=[e for e in ev if e['kind']==71 and e['role']==0];end=[e for e in ev if e['kind']==64 and e['role']==0];checks['actual_long_approach']=len(starts)==len(end)==1 and starts[0].get('target_visible')==1 and dist(xyz(starts[0]),starts[0].get('visible_target_xyz'))>=300 and dist(xyz(starts[0]),xyz(end[0]))>=120
 terminal=r.get('terminal_readonly',{});code=(B/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0];expected={int(a,0):s.replace('\\x','') for a,s in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',code)};entries=terminal.get('entries',[]);layout=json.loads((B/'inert-layout.json').read_text());identity=dict(pid=pre.get('pid'),session_id=r.get('session_id'),commander_id=pre.get('commander_id'),command_id=rq.get('command_id'),task_id=rq.get('task_id'),seq=rq.get('seq'),token=rq.get('token'),owner=pre.get('owner'),logic=pre.get('logic'))
 checks['actual_bound_timer_and_thirteen_pristine_bytes']=bool(len(expected)==len(entries)==len({num(e['address']) for e in entries})==13 and all(e.get('expected')==e.get('actual')==expected.get(num(e['address'])) and e.get('restored') is True for e in entries) and all(terminal.get(k)==v for k,v in identity.items()) and terminal.get('binding_verified') is True and terminal.get('mutations') is False and terminal.get('timer')==terminal.get('active')==0 and terminal.get('phase')==3 and terminal.get('error')==0 and terminal.get('restore_mask')==8191 and terminal.get('front_return_verified')==terminal.get('support_return_verified')==1 and terminal.get('layout')==layout and terminal.get('native_binary_sha256')==sha(files['native_binary_sha256']))
 return dict(status='independent_mfm5_field_chain_verified' if all(v is True for v in checks.values()) else 'not_passed',checks=checks,follow_references=refs,qualified_damage=hits,source_damage_amount=sum(x['damage'] for x in hits if x['verified']),home_audits=homes,override_event_sequences=overrides,conditional_observations={str(k):sum(e['kind']==k for e in ev) for k in (82,87,88,92)},lethal_verified=False,economic_suppression_verified=False,sdk_calls=0,gui_calls=0)

def review_path(path):
 path=Path(path).resolve();raw=path.read_bytes();r=json.loads(raw.decode('utf-8-sig'));a=review(r);a.update(source_report=str(path),source_sha256=hashlib.sha256(raw).hexdigest(),reviewer_sha256=sha(__file__));return a
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('report',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args();a=review_path(args.report);out=args.output or args.report.with_suffix('.independent-review.json')
 if out.exists():raise SystemExit('Review file already exists; preserve evidence')
 out.write_text(json.dumps(a,indent=2,allow_nan=False));print(json.dumps(dict(status=a['status'],checks=a['checks'],output=str(out))))
