"""MFM16 raw verifier, independent of Native execution and aggregate claims.

No process access, SDK, GUI, host launch or capability grant. Published native
events, actual surface samples, source packets and physical returns are joined
independently. A synthetic protocol replay is never a live source certificate.
"""
import hashlib,importlib.util,json,math,re,struct,sys,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
sys.path.insert(0,str(HERE))
from combo_qualification import damage_packet,EXE,AK,finite,close
from stop_sequence import settled_stop
import mission_actor_admission_v2 as admission
def own_module(name):
 spec=importlib.util.spec_from_file_location('mf16_qualifier_'+name,HERE/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
stance=own_module('stance_ownership')
controller=own_module('reserve_controller_audit')
actors=own_module('actor_binding')
ROLE_TYPES={0:0x19ab11af,1:0x2c358c61}
REASONS={0:'active',1:'source_damage',2:'fov_lost',3:'low_hp',4:'cancelled',5:'engage_limit',6:'retreat_failed',7:'prepare_failed',8:'approach_stalled'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def number(x):return int(x,0) if isinstance(x,str) else x
def point(p):return isinstance(p,(list,tuple)) and len(p)==3 and all(finite(v) for v in p)
def xyz(e):return [e.get(k) for k in ('x','y','z')]
def distance(a,b):return math.dist(a[:2],b[:2]) if point(a) and point(b) else math.inf
def same(a,b):return point(a) and point(b) and all(abs(x-y)<=.01 for x,y in zip(a,b))
def actor(report,role):return actors.actor(report,role)
def mission_fields(report):
 b=report.get('native',{}).get('mission_commit',{}).get('body',{});m=report.get('mission_request') or {}
 return dict(target_object_id=b.get('target_id'),front_id=b.get('front_id'),support_id=b.get('support_id'),target_contact_id=m.get('contact_id'),expires_frame=b.get('hard_deadline_frame'),button=m.get('button',{}),target_role=m.get('target_role'),safety_sha256=m.get('safety_sha256'))

def target_scope(report):
 from combo_qualification import SAFETY_SHA,GROUND_TARGET_ROLES
 path=HERE.parent.parent/'visibility/template-safety-2d7873e1.json';rq=mission_fields(report);target=report.get('private_target',{})
 if sha(path)!=SAFETY_SHA or rq.get('safety_sha256')!=SAFETY_SHA:return False
 entry=json.loads(path.read_bytes())['templates'].get(target.get('type_hash'),{})
 return entry.get('role') in GROUND_TARGET_ROLES and rq.get('target_role')==entry.get('role') and (entry['role']!='economy' or target.get('type_hash')=='0xc45aaeab')

def source_paths():
 return list(HERE.glob('*.cpp.inc'))+[HERE/'wait_anchor_replan.py',HERE/'retreat_departure.py',HERE/'pending_lineage.py',HERE/'stance_ownership.py',HERE/'actor_binding.py',HERE/'producer_binding.py',HERE/'reserve_controller_audit.py',HERE.parent/'running_birth_source_v1.py',HERE/'native_layout.py',HERE/'controller_contract.py',Path(__file__),HERE/'inert-layout.json',HERE.parent/'mobility_guard.py',HERE.parent/'mission_actor_admission_v2.py',HERE.parent/'mission_actor_admission.py',HERE.parent/'grounded_status_v2.py',HERE.parent/'grounded_status.py',HERE.parent/'ordered-combo/lease.py',HERE.parent/'ordered_qualification.py',HERE.parent/'combo_qualification.py',HERE.parent/'stop_sequence.py',HERE.parent/'readonly_disposal.py',HERE.parent/'recon/read_own_command_buttons.py',HERE.parent.parent/'visibility/capability.py',HERE.parent.parent/'visibility/collector.py',HERE.parent.parent/'visibility/projection.py',HERE.parent.parent/'visibility/native_read.py',HERE.parent.parent/'integration/own_candidates.py',HERE.parent.parent/'production/persistent/client.py',HERE.parent.parent/'production/persistent/shared.h',HERE.parent.parent/'production/persistent/executor.cpp',HERE.parent.parent/'production/persistent/bin-v2/ProductionPersistent.dll',HERE.parent.parent/'production/persistent/bin-v2/persistent_host.exe']
def source_pins(report):
 try:
  files={'native_binary_sha256':HERE/'bin/TacticalMissionFormation16.dll','native_host_sha256':HERE/'bin/tactical_host.exe','native_source_sha256':HERE/'lease.cpp','native_shared_sha256':HERE/'shared.h','wrapper_sha256':HERE/'lease.py'}
  supplements=report.get('supplemental_sources',{});includes=list(HERE.glob('*.cpp.inc'))
  revision=json.loads((HERE/'revision.json').read_text());compiled={k:sha(p) for k,p in files.items() if k!='wrapper_sha256'};compiled['native_includes_sha256']={p.name:sha(p) for p in includes}
  return bool(includes) and all(report.get(k)==sha(p) for k,p in files.items()) and report.get('native_revision_sha256')==sha(HERE/'revision.json') and all(report.get(k)==v and revision.get(k)==v for k,v in compiled.items()) and report.get('native_layout_sha256')==sha(HERE/'native_layout.py') and report.get('controller_contract_sha256')==sha(HERE/'controller_contract.py') and isinstance(supplements,dict) and supplements=={p.name:sha(p) for p in source_paths()}
 except (OSError,TypeError,ValueError):return False
def common_audit(report):
 n=report.get('native',{});pre=report.get('preflight',{});rq=report.get('request',{});ev=report.get('events',[]);checks={};front=actor(report,0);support=actor(report,1);body=n.get('mission_commit',{}).get('body',{});ctl=n.get('controller',{})
 checks['actual_protocol_namespace']=n.get('magic')==0x4d463136 and n.get('version')==16
 checks['compiled_source_revision']=source_pins(report) and report.get('executable_sha256')==EXE
 checks['identity_and_outer_lease']=pre.get('player_id')==3 and n.get('session_id')==pre.get('session_id')==report.get('session_id') and n.get('commander_id')==pre.get('commander_id') and all(n.get(k)==rq.get(k) for k in ('command_id','task_id','seq','token')) and type(rq.get('seq')) is int and rq['seq']>0 and type(rq.get('token')) is int and rq['token']>0 and report.get('controller_input')==n.get('controller_input')
 checks['actual_native_pointer_binding']=n.get('pid')==pre.get('pid') and n.get('thread')==pre.get('window_thread') and all(n.get(k)==number(pre.get(k,0)) for k in ('owner','ai','logic')) and n.get('unit')==number(front.get('address',0)) and n.get('update')==number(front.get('ai_address',0)) and n.get('type_hash')==ROLE_TYPES[0] and n.get('support',{}).get('thing')==number(support.get('address',0)) and n.get('support',{}).get('update')==number(support.get('ai_address',0)) and n.get('support',{}).get('hash')==ROLE_TYPES[1]
 checks['exact_actors']=front.get('type_hash')=='0x19ab11af' and support.get('type_hash')=='0x2c358c61' and front['object_id']!=support['object_id'] and body.get('front_id')==n.get('object_id')==front['object_id'] and body.get('support_id')==n.get('support',{}).get('id')==support['object_id']
 checks['published_monotonic_log']=bool(ev) and all(e.get('seq')==i+1 and type(e.get('frame')) is int and type(e.get('tick')) is int for i,e in enumerate(ev)) and all(b['frame']>=a['frame'] and 0<=((b['tick']-a['tick'])&0xffffffff)<0x80000000 for a,b in zip(ev,ev[1:]))
 checks['critical_finite']=bool(ev) and all(all(finite(e.get(k)) for k in ('x','y','z','own_hp','damage_before','damage_after','damage_reported')) for e in ev)
 checks['role_thread_and_owner']=n.get('callback_thread')==pre.get('window_thread') and all(e.get('thread')==pre.get('window_thread') and (e.get('kind')==4 or controller.prebind_actor_event(report,e) or e.get('role') in (0,1) and e.get('owner')==number(pre.get('owner',0)) and e.get('unit_id')==actor(report,e['role'])['object_id']) for e in ev)
 checks['fixed_navigation_limits']=n.get('memory_ttl_frames')==900 and n.get('approach_limit')==2100 and n.get('retreat_limit')==1800 and n.get('hold_timeout_frames')==60 and type(n.get('combat_frames')) is int and 30<=n['combat_frames']<=300 and n.get('route_count')==n.get('route_ready')==n.get('route_generation')==0
 start=ctl.get('reserve_start_frame',0);deadline=ctl.get('hard_deadline_frame',0)
 freeze=next((e['seq'] for e in ev if e.get('kind')==145),float('inf'))
 checks['original_deadline']=0<start==n.get('issued_frame') and deadline==start+4500==n.get('mission_deadline_frame') and all(e.get('mission_deadline_frame')==(0 if e.get('seq',0)<freeze else deadline) for e in ev if e.get('seq',0)>1)
 checks['explicit_ground_target']=bool(mission_fields(report).get('target_contact_id')) and body.get('target_id')==n.get('target_id')==report.get('private_target',{}).get('object_id') and report.get('private_target',{}).get('owner_player_id') not in (None,3) and target_scope(report)
 return dict(verified=all(v is True for v in checks.values()),checks=checks)
def surface_sample(crumb,report,event=None):
 """Recompute positive surface evidence from all actual crumb values, not160."""
 checks={}
 try:
  role=crumb.get('role');u=actor(report,role);words=crumb.get('status_words');pos=crumb.get('xyz')
  checks['typed_native_words']=role in (0,1) and isinstance(words,list) and len(words)==7 and all(type(x) is int and 0<=x<=0xffffffff for x in words)
  if not checks['typed_native_words']:return dict(verified=False,checks=checks)
  bit=lambda i:bool(words[i//32]&(1<<(i%32)))
  checks['actual_identity']=crumb.get('thing')==number(u.get('address',0)) and crumb.get('object_id')==u.get('object_id') and crumb.get('type_hash')==ROLE_TYPES[role] and crumb.get('owner')==number(report.get('preflight',{}).get('owner',0)) and crumb.get('update')==number(u.get('ai_address',0))
  checks['ground_cache_positive']=type(crumb.get('height_flags')) is int and crumb['height_flags']&4!=0 and finite(crumb.get('height')) and abs(crumb['height'])<=.5
  checks['air_dead_garrison_immobile_excluded']=not any(bit(i) for i in (0,7,8,51,61,161,207,211)) and crumb.get('holder')==0
  checks['actual_position_health']=point(pos) and finite(crumb.get('hp')) and crumb['hp']>0 and finite(crumb.get('path_distance')) and crumb['path_distance']>=0
  checks['typed_clock_index']=type(crumb.get('frame')) is int and crumb['frame']>0 and type(crumb.get('index')) is int and 0<=crumb['index']<128 and type(crumb.get('published_seq')) is int and crumb['published_seq']>0
  if event is not None:checks['source_event_echo']=event.get('kind')==80 and event.get('role')==role and event.get('unit_id')==crumb['object_id'] and event.get('arg')==crumb['index'] and event.get('frame')==crumb['frame'] and event.get('mission_stage')==crumb.get('mission_stage') and event.get('seq')==crumb['published_seq'] and same(xyz(event),pos) and close(event.get('own_hp'),crumb['hp'])
 except (KeyError,TypeError,ValueError):checks['well_formed']=False
 return dict(verified=all(v is True for v in checks.values()),checks=checks,ground160_required=False)
def breadcrumb_audit(report):
 ev=report.get('events',[]);rows=[e for e in ev if e.get('kind')==80];byrole={0:[],1:[]};checks=dict(actual_surface=bool(rows),immutable_unique_publication=bool(rows),header_matches_all_published=bool(rows));published={}
 for e in rows:
  c=e.get('breadcrumb',{});role=c.get('role');index=c.get('index');checks['actual_surface'] &= surface_sample(c,report,e)['verified']
  if role not in (0,1) or type(index) is not int:checks['immutable_unique_publication']=False;continue
  key=str(role)+':'+str(index);checks['immutable_unique_publication'] &= key not in published and index==len(byrole[role]) and (not byrole[role] or c['frame']>=byrole[role][-1]['frame']);published[key]=c;byrole[role].append(c)
 stored=report.get('native',{}).get('crumbs')
 checks['header_matches_all_published'] &= isinstance(stored,list) and len(stored)==2 and all(stored[role]==byrole[role] for role in (0,1))
 return dict(verified=all(v is True for v in checks.values()),checks=checks,published=published,roles=byrole,observed_count=len(rows))
def motion_distance(report,role,stage,until_seq):
 origins=[e for e in report.get('events',[]) if e.get('kind')==80 and e.get('role')==role and e.get('mission_stage')==stage and e.get('seq',0)<=until_seq]
 if not origins:return None
 first=origins[0];previous=first['breadcrumb']['xyz'];frame=first['frame'];total=0.
 for e in report['events']:
  if e.get('role')!=role or e.get('mission_stage')!=stage or not first['seq']<e.get('seq',0)<=until_seq or e.get('kind') not in (3,80) or e.get('frame',-1)<=frame:continue
  current=xyz(e)
  if not point(current):return None
  total+=distance(previous,current);previous=current;frame=e['frame']
 return total
def breadcrumb_motion_audit(report,crumbs):
 checks=dict(actual_eighty_unit_publications=True,actual_path_distance=True,phase_origins_zero=True);previous={};events=report.get('events',[])
 for e in events:
  if e.get('kind')!=80:continue
  c=e.get('breadcrumb',{});key=(c.get('role'),c.get('mission_stage'));p=previous.get(key)
  if key[0] not in (0,1) or key[1] not in (1,3):checks['actual_eighty_unit_publications']=False;continue
  if p:checks['actual_eighty_unit_publications'] &= distance(c.get('xyz'),p.get('xyz'))>=79.99
  else:checks['phase_origins_zero'] &= close(c.get('path_distance'),0.)
  travelled=motion_distance(report,key[0],key[1],e['seq']);checks['actual_path_distance'] &= finite(travelled) and finite(c.get('path_distance')) and abs(travelled-c['path_distance'])<=.5
  previous[key]=c
 return dict(verified=crumbs['verified'] and all(v is True for v in checks.values()),checks=checks)
def dispatch_diagnostic_audit(report):
 """Audit diagnostic input/counter conservation. No command obtains credit."""
 try:return _dispatch_diagnostic_audit(report)
 except (KeyError,TypeError,ValueError,IndexError,OverflowError):
  return dict(verified=False,observed=True,checks={'well_formed_diagnostic_raw':False},field_verified=False,move_authority_granted=False,completion_claim=False)

def _dispatch_diagnostic_audit(report):
 ev=report.get('events',[]);n=report.get('native',{});pre=report.get('preflight',{});rows=[e for e in ev if e.get('kind') in (124,125)];byseq={};paired=set();counters={0:0,1:0};records=[];checks=dict(typed_original_inputs=True,paired_dispatch_scope=True,every_foreign_increment_has_cause=True,all_before_records_closed=True,final_counters_conserved=True)
 for e in rows:
  raw=e.get('stack_words');typed=isinstance(raw,list) and 80<=len(raw)<=128 and all(type(x) is int and 0<=x<=0xffffffff for x in raw) and e.get('stack_word_count')==80
  checks['typed_original_inputs'] &= typed
  if not typed:continue
  w=raw[:80];role=e.get('role');u=actor(report,role) if role in (0,1) else {};cause=w[2];ref=w[3];before=w[10];after=w[11]
  bound=w[0]==0x44473131 and w[1]==(1 if e['kind']==124 else 2) and role in (0,1) and w[4]==role and w[2]==e.get('arg') and w[8]==e.get('caller') and w[9]==e.get('tag') and e.get('unit_id')==u.get('object_id') and e.get('owner')==number(pre.get('owner')) and e.get('thread')==pre.get('window_thread') and w[75]==number(u.get('ai_address'))+0x310 and w[76]<=w[77]<=e.get('frame',-1) and all(x in (0,1) for x in w[13:20]+w[21:24])
  if w[6]==number(u.get('address')):bound &= w[78]==u.get('object_id') and w[79]==number(pre.get('owner'))
  if w[22]:bound &= w[7]!=0
  checks['typed_original_inputs'] &= bound
  checks['every_foreign_increment_has_cause'] &= role in (0,1) and before==counters.get(role) and (after==before if cause==0 else cause in range(1,8) and after==before+1)
  if e['kind']==124:
   checks['paired_dispatch_scope'] &= cause==ref==0 and before==after and e['seq'] not in byseq and w[5]==number(u.get('ai_address'))+0x24 and w[6]==number(u.get('address'))
   byseq[e['seq']]=(e,w)
  else:
   if cause in (0,5):
    prior=byseq.get(ref);valid=prior is not None and ref not in paired and ref<e['seq']
    if prior:
     start,p=prior;valid &= p[4:10]==w[4:10] and start.get('frame')<=e.get('frame') and (w[12] in (1,2,4) if cause==0 else w[12]==3)
    checks['paired_dispatch_scope'] &= valid
    if valid:paired.add(ref)
   elif ref:checks['paired_dispatch_scope'] &= ref in byseq and ref<e['seq'] and byseq[ref][1][4]==role
  if role in (0,1):counters[role]=after
  records.append(dict(seq=e['seq'],kind=e['kind'],role=role,frame=e.get('frame'),cause_id=cause,linked_pre_seq=ref,counter_before=before,counter_after=after,decision_reason=w[12],actual_this=w[5],actual_thing=w[6],actual_command_pointer=w[7],actual_caller=w[8],actual_tag=w[9],command_readable=bool(w[22]),slot_readable=bool(w[23]),opcode_word=w[28] if w[22] else None,command_source_word=w[29] if w[22] else None,command_words=w[28:51],stored_words=w[51:75],ticket_flags=w[13:20],generation=w[20],role_leased=bool(w[21]),scalar_tls=w[24:28],move_authority_granted=False))
 checks['all_before_records_closed']=set(byseq)==paired
 for role in (0,1):
  header=n if role==0 else n.get('support',{});checks['final_counters_conserved'] &= type(header.get('native_move')) is int and header['native_move']==counters[role]
 return dict(verified=all(v is True for v in checks.values()),observed=bool(rows),checks=checks,records=records,foreign_increment_count=sum(r['counter_after']-r['counter_before'] for r in records),field_verified=False,move_authority_granted=False,completion_claim=False,semantics='raw_diagnostic_only_native_override_gates_unchanged')

def tls_alignment_audit(report):
 """Bind the scalar TLS repair to compiled sources; never an SDK/effect grant."""
 try:
  proof_path=HERE/'tls-alignment-proof.json';proof=json.loads(proof_path.read_text());revision=json.loads((HERE/'revision.json').read_text());regression=json.loads((HERE/'tls-alignment-regression.json').read_text());source=(HERE/'pending.cpp.inc').read_text();checks={}
  checks['sealed_actual_compiled_alignment_proof']=revision.get('tls_alignment_proof_sha256')==sha(proof_path) and proof.get('protocol')=='mfm10_actual_compiled_tls_scalar_alignment_v1' and proof.get('native_binary_sha256')==report.get('native_binary_sha256')==sha(HERE/'bin/TacticalMissionFormation16.dll')
  paths={'pending_source_sha256':HERE/'pending.cpp.inc','regression_source_sha256':HERE/'test_tls_alignment_native.cpp','regression_binary_sha256':HERE/'bin/test_tls_alignment_native.exe','regression_report_sha256':HERE/'tls-alignment-regression.json','disassembly_sha256':HERE/'tls-accessors-disassembly.txt'}
  checks['all_alignment_evidence_bound']=proof.get('source_file')=='pending.cpp.inc' and all(proof.get(k)==sha(p) for k,p in paths.items()) and isinstance(proof.get('checks'),dict) and bool(proof['checks']) and all(v is True for v in proof['checks'].values())
  checks['actual_misaligned_buffer_and_real_thread_test']=regression.get('protocol')=='actual_cpp_tls_scalar_alignment_regression_v1' and regression.get('passed') is True and type(regression.get('cases')) is int and regression['cases']>=15 and type(regression.get('buffer_address')) is int and regression['buffer_address']%16==regression.get('buffer_mod16')==8 and regression['buffer_address']%4==regression.get('buffer_mod4')==0 and regression.get('context_bytes')==16 and regression.get('actual_thread_isolation') is True and regression.get('begin_and_restore') is True and type(regression.get('main_tls_address')) is int and type(regression.get('worker_tls_address')) is int and regression['main_tls_address']>0 and regression['worker_tls_address']>0 and regression['main_tls_address']!=regression['worker_tls_address']
  names=('load_dispatch_words','store_dispatch_words','set_dispatch_words','clear_dispatch_words','load_move_context','set_move_context','clear_move_context','restore_move_context');functions=proof.get('functions',[])
  checks['all_actual_accessors_disassembled']=isinstance(functions,list) and len(functions)==8 and all(sum(name in f.get('symbol','') and isinstance(f.get('instructions'),list) and bool(f['instructions']) for f in functions)==1 for name in names)
  checks['true_tls_all_scalar_save_and_restore']=bool(re.search(r'static\s+__thread\s+volatile\s+uint32_t\s+move_context_words\s*\[4\]',source)) and not re.search(r'\bmove_context\s*=',source) and all(name in source for name in names) and 'restore_move_context(prior)' in source and 'clear_move_context();' in (HERE/'mission_state.cpp.inc').read_text()
  checks['software_only_no_capability']=proof.get('field_verified') is False and proof.get('sdk_calls')==0 and regression.get('game_access') is False and regression.get('sdk_calls')==0 and regression.get('capability_granted') is False
  return dict(verified=all(v is True for v in checks.values()),checks=checks,field_verified=False,semantics='compiled_tls_alignment_repair_only_never_effect_or_home_credit')
 except (OSError,KeyError,TypeError,ValueError,IndexError):return dict(verified=False,checks={'actual_sealed_alignment_evidence':False},field_verified=False)

def schedule_audit(report):
 """Sparse native scheduling captures do not stand in for any motion sample."""
 try:return _schedule_audit(report)
 except (KeyError,TypeError,ValueError,IndexError,OverflowError,struct.error):
  return dict(verified=False,observed=False,field_verified=False,checks={'well_formed_scheduler':False})

def _schedule_audit(report):
 ev=report.get('events',[]);n=report.get('native',{});rq=report.get('request',{});pre=report.get('preflight',{});rows=[e for e in ev if e.get('kind') in (121,122,123)];installs=[e for e in ev if e.get('kind')==0];checks=dict(actual_sparse_schedule=bool(rows) and len(installs)==1,typed_and_original_binding=True,first_capture=True,nonce_fresh_monotonic=True,actual_unique_advance=True,fallback_only_after_lost_pulse=True);parsed=[];prior=None;last_pulse=None
 word=lambda x:type(x) is int and 0<=x<=0xffffffff
 delta=lambda a,b:(a-b)&0xffffffff
 command=list(struct.unpack('<4I',uuid.UUID(rq['command_id']).bytes));task=list(struct.unpack('<4I',uuid.UUID(rq['task_id']).bytes))
 for e in rows:
  data=e.get('stack_words');typed=isinstance(data,list) and 24<=len(data)<=128 and all(word(x) for x in data) and e.get('stack_word_count')==24
  checks['typed_and_original_binding'] &= typed
  if not typed:continue
  w=data[:24];origin=e['kind']-120;bound=w[0]==0x53434839 and w[1]==origin==e.get('arg') and w[2]==rq.get('token') and w[3]==rq.get('seq') and w[4:8]==command and w[8:12]==task and w[14]==e.get('frame') and w[16]==e.get('thread')==pre.get('window_thread')==n.get('callback_thread') and w[17:19]==[20,100] and w[21]==(0 if e['seq']<next((x['seq'] for x in ev if x.get('kind')==145),float('inf')) else n.get('controller',{}).get('hard_deadline_frame')) and w[23]==1000 and w[22]<=20000
  checks['typed_and_original_binding'] &= bound
  if prior:
   checks['actual_unique_advance'] &= w[14]>prior[14] and w[20]>prior[20] and w[15]>=prior[14] and w[15]<w[14] and w[22]>=prior[22]
   if origin==prior[1]:checks['actual_unique_advance'] &= origin==2 and w[22]%64==0
  else:
   install=installs[0] if len(installs)==1 else None
   first=bool(install and install['seq']<e['seq'] and w[15]==0xffffffff and w[20]==1)
   if origin==1:first &= w[14]==install['frame'] and w[13]==w[19]==w[22]==0 and (w[12]==0 or delta(e['tick'],w[12])<=1000)
   else:first &= n.get('paused_samples',0)>0 and w[14]>=install['frame']
   starts=[x for x in ev if x.get('kind')==71]
   if starts:first &= all(e['seq']<x['seq'] for x in starts)
   checks['first_capture'] &= first
  if origin==2:
   checks['nonce_fresh_monotonic'] &= w[12]==w[13]!=0 and 0<=delta(e['tick'],w[12])<=1000 and delta(w[19],w[12])<=1000 and delta(e['tick'],w[19])<=1000 and w[22]>0
   if last_pulse:
    diff=delta(w[13],last_pulse[13]);checks['nonce_fresh_monotonic'] &= 0<diff<0x80000000 and w[22]>last_pulse[22] and diff>=20*(w[22]-last_pulse[22])
   last_pulse=w
  elif origin==3:
   checks['fallback_only_after_lost_pulse'] &= w[19]==0 or 100<delta(e['tick'],w[19])<0x80000000
  elif origin==1:checks['first_capture'] &= prior is None
  prior=w;parsed.append(dict(seq=e['seq'],frame=e['frame'],origin=origin,requested_nonce=w[12],acknowledged_nonce=w[13],actual_advance_count=w[20],accepted_pulse_count=w[22]))
 samples=[e for e in ev if e.get('kind')==3 and e.get('role') in (0,1)];keys=[(e['role'],e.get('frame')) for e in samples];checks['one_real_role_sample_per_logical_frame']=len(keys)==len(set(keys))
 request=n.get('pulse_requested');ack=n.get('pulse_acknowledged');checks['terminal_original_nonce_state']=word(request) and word(ack)
 if checks['terminal_original_nonce_state']:
  checks['terminal_original_nonce_state'] &= request==ack or request!=0 and (ack==0 or 0<delta(request,ack)<0x80000000)
  if last_pulse:checks['terminal_original_nonce_state'] &= ack!=0 and (ack==last_pulse[13] or 0<delta(ack,last_pulse[13])<0x80000000)
 checks['bounded_sparse_proof_count']=len(rows)<=2+2*len([r for r in parsed if r['origin']==3])+max([r['accepted_pulse_count'] for r in parsed]+[0])//64
 return dict(verified=all(v is True for v in checks.values()),observed=bool(rows),field_verified=False,checks=checks,captures=parsed,posted_pulse_observed=any(r['origin']==2 for r in parsed),fallback_observed=any(r['origin']==3 for r in parsed),paused_counter=n.get('paused_samples'),semantics='scheduling_only_never_stop_arrival_damage_or_sdk_credit')

def pending_lineage_audit(report):
 spec=importlib.util.spec_from_file_location('mfm14_pending_lineage_q',HERE/'pending_lineage.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.audit(report)

def normal_move_audit(report):
 ev=report.get('events',[]);moves=[e for e in ev if e.get('kind')==50 and e.get('tag')==6];groups=[];checks=dict(complete_normal_chain=bool(moves),actual_counts=True);lineage=pending_lineage_audit(report);accepted={x['facade_seq']:x for x in lineage.get('accepted',[]) if lineage['verified'] and x.get('verified') is True};byseq={e['seq']:e for e in ev}
 for e in moves:
  rows=[x for x in ev if x.get('role')==e.get('role') and x.get('tag')==6 and x.get('kind') in (50,10,11,51) and x.get('seq',0)>=e['seq']][:4]
  good=len(rows)==4 and [x['kind'] for x in rows]==[50,10,11,51] and all(x.get('arg')==1 and x.get('frame')==e.get('frame') and same(x.get('command_xyz'),e.get('command_xyz')) for x in rows) and rows[1].get('argument_path')==0 and finite(rows[1].get('argument_limit')) and rows[1]['argument_limit']>1e30
  last_seq=rows[-1]['seq'] if rows else e['seq']
  pending=accepted.get(e['seq'])
  if pending:
   own=[x for x in rows if x['kind'] in (50,51)][:2];private=byseq.get(pending['private_move_seq']);done=byseq.get(pending['private_done_seq'])
   good=len(own)==2 and [x['kind'] for x in own]==[50,51] and all(x.get('arg')==1 and x.get('frame')==e.get('frame') and same(x.get('command_xyz'),e.get('command_xyz')) for x in own) and private is not None and done is not None and own[-1]['seq']<private['seq']<done['seq'];last_seq=done['seq'] if done else e['seq']
  checks['complete_normal_chain'] &= good;groups.append(dict(role=e.get('role'),seq=e['seq'],last_seq=last_seq,frame=e.get('frame'),mission_stage=e.get('mission_stage'),goal=e.get('command_xyz'),verified=bool(good)))
 for role in (0,1):checks['actual_counts'] &= (report.get('native',{}) if role==0 else report.get('native',{}).get('support',{})).get('move_calls')==sum(g['role']==role for g in groups)
 return dict(verified=all(v is True for v in checks.values()),checks=checks,groups=groups)
def follow_audit(report,crumbs,moves):
 ev=report.get('events',[]);requests=[e for e in ev if e.get('kind')==81];results=[];last={};checks=dict(prior_actual_crumb=bool(requests),strict_reference_order=True,actual_leader_one_hundred_ahead=True,leader_clear_of_goal=True,normal_follow_input=True,three_distinct_arrival=True,stop_before_next=True)
 for i,e in enumerate(requests):
  c=e.get('breadcrumb',{});key=str(c.get('role'))+':'+str(c.get('index'));source=crumbs.get('published',{}).get(key);stage=e.get('mission_stage');leader=0 if stage==1 else 1 if stage==3 else None;follower=1-leader if leader is not None else None
  bound=source==c and source is not None and c.get('published_seq',e['seq'])<e['seq'] and c.get('frame',e['frame']+1)<=e['frame'] and c.get('mission_stage')==stage and e.get('role')==e.get('follower_role')==follower and e.get('leader_role')==c.get('role')==leader and e.get('follow_crumb_role')==leader and e.get('follow_crumb_index')==c.get('index')
  checks['prior_actual_crumb'] &= bound;previous=last.get(stage);index=c.get('index');ordered=type(index) is int and (previous is None or index>previous);checks['strict_reference_order'] &= ordered;last[stage]=index
  phase_crumbs=[x for x in crumbs.get('roles',{}).get(leader,[]) if x.get('mission_stage')==stage];first=bool(phase_crumbs) and c==phase_crumbs[0]
  travelled=motion_distance(report,leader,stage,e['seq']) if leader is not None else None;ahead=finite(travelled) and finite(c.get('path_distance')) and travelled-c['path_distance']>=(24.99 if first else 99.5);checks['actual_leader_one_hundred_ahead'] &= ahead
  poses=[x for x in ev if x.get('role')==leader and x.get('kind') in (3,80) and x.get('frame')==e['frame'] and x['seq']<e['seq']];clear=bool(poses) and distance(xyz(poses[-1]),c.get('xyz'))>=24.99;checks['leader_clear_of_goal'] &= clear
  following=[g for g in moves.get('groups',[]) if g['role']==follower and g['seq']>e['seq']];move=following[0] if following else None;input_ok=bool(move and move['verified'] and same(move['goal'],c.get('xyz')) and move['mission_stage']==stage);checks['normal_follow_input'] &= input_ok
  later=[x for x in requests[i+1:] if x.get('role')==follower];end=later[0]['seq'] if later else len(ev)+1
  gates=[x for x in ev if x.get('kind')==84 and x.get('role')==follower and e['seq']<x['seq']<end and x.get('breadcrumb')==c];stops=[x for x in ev if x.get('kind')==94 and x.get('role')==follower and e['seq']<x['seq']<end and x.get('breadcrumb')==c]
  arrival=False;stopped=False
  if len(gates)==len(stops)==1 and move:
   gate=gates[0];samples=[x for x in ev if x.get('kind')==3 and x.get('role')==follower and move['last_seq']<x.get('seq',0)<gate['seq']];samples=list({x['frame']:x for x in samples}.values())[-3:]
   arrival=len(samples)==3 and all(distance(xyz(x),c['xyz'])<=15 and abs(x['z']-c['xyz'][2])<=10 for x in samples) and samples[-1]['frame']==gate['frame'] and gate['seq']<stops[0]['seq'] and distance(xyz(gate),c['xyz'])<=15
   stopped=arrival and role_stop_gate(report,follower,stops[0]) and not any(x.get('kind')==50 and x.get('tag')==6 and x.get('role')==follower and move['last_seq']<x['seq']<stops[0]['seq'] for x in ev)
  checks['three_distinct_arrival'] &= arrival;checks['stop_before_next'] &= stopped;results.append(dict(request_seq=e['seq'],role=follower,source_role=leader,source_index=index,mission_stage=stage,phase_origin_exception=first,actual_leader_path=travelled,source_path_distance=c.get('path_distance'),arrival_verified=bool(arrival),stop_verified=bool(stopped),verified=bool(bound and ordered and ahead and clear and input_ok and arrival and stopped)))
 return dict(verified=crumbs['verified'] and moves['verified'] and all(v is True for v in checks.values()),checks=checks,stages=results,approach_follow_observed=any(r['mission_stage']==1 for r in results),retreat_follow_observed=any(r['mission_stage']==3 for r in results))
def last_position_samples(report,role,before,after=0,stage=None,motion=None):
 rows=[e for e in report.get('events',[]) if e.get('kind')==3 and e.get('role')==role and after<e.get('seq',0)<before and (stage is None or e.get('mission_stage')==stage) and (motion is None or e.get('motion_state')==motion)]
 return list({e['frame']:e for e in rows}.values())[-3:]
def conditional_audit(report,moves):
 """Unseen branches stay unseen; every observed branch must conserve raw state."""
 ev=report.get('events',[]);n=report.get('native',{});regroups=[e for e in ev if e.get('kind')==82];repairs=[e for e in ev if e.get('kind')==92];group_results=[];repair_results=[]
 for i,start in enumerate(regroups):
  role=start.get('leader_role');end=regroups[i+1]['seq'] if i+1<len(regroups) else len(ev)+1;gates=[e for e in ev if e.get('kind')==83 and e.get('role')==role and start['seq']<e['seq']<end];gate=gates[0] if gates else None;resumes=[e for e in ev if e.get('kind')==85 and e.get('role')==role and gate and gate['seq']<e['seq']<end];resume=resumes[0] if resumes else None
  pairs=[e for e in ev if e.get('kind')==3 and e.get('frame')==start.get('frame') and e.get('mission_stage')==start.get('mission_stage')];pose={e.get('role'):xyz(e) for e in pairs};actual_gap=distance(pose.get(0),pose.get(1));resume_pose={e.get('role'):xyz(e) for e in ev if resume and e.get('kind')==3 and e.get('frame')==resume['frame'] and e['seq']<resume['seq']};resume_gap=distance(resume_pose.get(0),resume_pose.get(1))
  good=role in (0,1) and start.get('role')==role and actual_gap>240 and gate is not None and role_stop_gate(report,role,gate) and gate['frame']-start['frame']<=60 and resume is not None and finite(resume_gap) and resume_gap<=200 and close(resume.get('actual_gap'),resume_gap) and resume['frame']-start['frame']<=300 and same(gate.get('leader_hold_xyz'),xyz(gate)) and any(g['role']==role and g.get('verified') is True and g['seq']>resume['seq'] and g['mission_stage']==resume.get('mission_stage') for g in moves['groups'])
  group_results.append(dict(start_seq=start['seq'],actual_gap=actual_gap if finite(actual_gap) else None,stop_gate_seq=gate['seq'] if gate else None,resume_seq=resume['seq'] if resume else None,verified=bool(good)))
 for i,start in enumerate(repairs):
  role=start.get('leader_role');end=repairs[i+1]['seq'] if i+1<len(repairs) else len(ev)+1;anchors=[e for e in ev if e.get('kind')==83 and e.get('role')==role and e['seq']<start['seq']];anchor=anchors[-1].get('leader_hold_xyz') if anchors else None;gates=[e for e in ev if e.get('kind')==93 and e.get('role')==role and start['seq']<e['seq']<end];gate=gates[0] if len(gates)==1 else None;groups=[g for g in moves['groups'] if g['role']==role and start['seq']<g['seq']<end];move=groups[0] if groups else None
  stops=[e for e in ev if e.get('kind')==33 and e.get('role')==role and move and move['last_seq']<e['seq'] and gate and e['seq']<gate['seq']];stop=stops[-1] if stops else None;samples=last_position_samples(report,role,stop['seq'] if stop else 0,move['last_seq'] if move else 0,motion=4)
  arrived=len(samples)==3 and point(anchor) and all(distance(xyz(e),anchor)<=15 and abs(e['z']-anchor[2])<=10 for e in samples)
  good=role in (0,1) and start.get('role')==role and point(anchor) and distance(xyz(start),anchor)>15 and same(start.get('leader_hold_xyz'),anchor) and move is not None and move['verified'] and same(move['goal'],anchor) and arrived and gate is not None and role_stop_gate(report,role,gate) and same(gate.get('leader_hold_xyz'),anchor) and distance(xyz(gate),anchor)<=15 and stop is not None and stop['frame']-start['frame']<=120 and gate['frame']-stop['frame']<=60
  repair_results.append(dict(start_seq=start['seq'],anchor=anchor,arrival_frames=[e['frame'] for e in samples],stop_gate_seq=gate['seq'] if gate else None,verified=bool(good)))
 checks=dict(regroup_bounded=len(regroups)<=24 and all(sum(e.get('mission_stage')==stage for e in regroups)<=12 for stage in (1,3)) and all(e.get('mission_stage') in (1,3) for e in regroups) and n.get('regroup_count')==len(regroups),all_regroups_raw=all(x['verified'] for x in group_results),repair_bounded=len(repairs)<=2 and n.get('hold_repair_count')==len(repairs),all_repairs_raw=all(x['verified'] for x in repair_results))
 return dict(verified=all(v is True for v in checks.values()),checks=checks,regroup=dict(observed=bool(regroups),field_verified=bool(regroups) and all(x['verified'] for x in group_results),events=group_results),hold_repair=dict(observed=bool(repairs),field_verified=bool(repairs) and all(x['verified'] for x in repair_results),events=repair_results))
def memory_audit(report,moves):
 ev=report.get('events',[]);target=mission_fields(report).get('target_object_id');current=None;seen=0;hidden=False;ever_hidden=False;reacquired=False;checks=dict(legal_visible_updates=True,hidden_point_frozen=True,normal_leader_navigation_bound=True,attack_live_only=True,loss_reacquisition_sequence=True)
 for e in ev:
  at=e.get('target_last_seen_frame',0);value=e.get('last_seen_target');frame=e.get('frame',0)
  if not at:continue
  if type(at) is not int or at>frame or not point(value):checks['legal_visible_updates']=False;continue
  if at!=seen:
   witness=[x for x in ev if x.get('seq',0)<=e['seq'] and x.get('frame')==at and x.get('target_visible')==1 and same(x.get('visible_target_xyz'),value)]
   checks['legal_visible_updates'] &= bool(witness) and at>=seen
   current=list(value);seen=at
  else:checks['hidden_point_frozen'] &= current is not None and same(value,current)
  if e.get('target_visible')!=1:checks['hidden_point_frozen'] &= e.get('visible_target_xyz')==[0.,0.,0.]
  if e.get('kind')==87:checks['loss_reacquisition_sequence'] &= not hidden and e.get('target_visible')==0;hidden=True;ever_hidden=True
  if e.get('kind')==88:checks['loss_reacquisition_sequence'] &= hidden and e.get('target_visible')==1 and at==frame;hidden=False;reacquired=True
  if e.get('kind') in (34,12,13,35,20,24,37,39,40,41,42,43,86) and e.get('mission_stage')==2:checks['attack_live_only'] &= e.get('target_visible')==1
 for g in moves.get('groups',[]):
  if g['mission_stage']==1 and g['role']==0:
   e=next(x for x in ev if x['seq']==g['seq']);markers=[x for x in ev if x.get('kind') in (81,85,92,95) and x.get('role')==0 and x['seq']<g['seq']];marker=markers[-1] if markers else {}
   if marker.get('kind')==85:checks['normal_leader_navigation_bound'] &= same(g['goal'],e.get('last_seen_target')) and type(e.get('target_last_seen_frame')) is int and 0<=e['frame']-e['target_last_seen_frame']<=900
   elif marker.get('kind')!=92:checks['normal_leader_navigation_bound']=False
 return dict(verified=seen>0 and all(v is True for v in checks.values()),checks=checks,hidden_navigation_observed=ever_hidden,reacquisition_observed=reacquired,memory_ttl_frames=900,unobserved_branch_status=None if ever_hidden and reacquired else 'unproven_not_field_certified')

def lease_audit(report):
 n=report.get('native',{});pre=report.get('preflight',{});ev=report.get('events',[]);roles=[];manager=number(pre.get('ai',0))+0x104;lineage=pending_lineage_audit(report);credited=set(lineage.get('accepted_private_sequences',[])) if lineage['verified'] else set()
 for role in (0,1):
  rows=[e for e in ev if e.get('role')==role];starts=[e for e in rows if e.get('kind')==1 and e.get('tag')==1];ends=[e for e in rows if e.get('kind')==5 and e.get('tag')==3];baselines=[e for e in rows if e.get('kind')==144];removes=[e for e in rows if e.get('kind')==18 and e.get('tag')==1 and e.get('arg')==manager and e.get('caller')==0x838877];counts=n if not role else n.get('support',{})
  bound=controller.borrow_boundary(report,role)['verified'] and len(starts)==len(ends)==len(baselines)==len(removes)==1 and baselines[0]['seq']<removes[0]['seq']<starts[0]['seq']<ends[0]['seq'] and baselines[0]['frame']==starts[0]['frame']==n['slots'][role]['borrow_frame'] and starts[0].get('team')==number(pre.get('script_team',0)) and ends[0].get('team')==number(pre.get('default_team',0))
  overrides=[e['seq'] for e in rows if bound and baselines[0]['seq']<e['seq']<ends[0]['seq'] and e.get('tag')==0 and e.get('kind') in (10,12,14,16,18,30,50) and not(e.get('kind')==10 and e['seq'] in credited)]
  zero=all(counts.get('native_'+key)==0 for key in ('move','attack','add','remove','stop'))
  roles.append(dict(role=role,verified=bool(bound and not overrides and zero),boundaries_verified=bool(bound),override_event_sequences=overrides,counters_zero=zero))
 return dict(verified=all(r['verified'] for r in roles),roles=roles)

def entry_audit(report):
 n=report.get('native',{});ev=report.get('events',[]);reserve=controller.audit(report);ctl=n.get('controller',{});checks=dict(original_paid_slots_and_origin350=reserve['verified']);details=[]
 for role in (0,1):
  slot=n['slots'][role];gates=[e for e in ev if e.get('kind')==58 and e.get('role')==role and e.get('mission_stage')==1 and e.get('frame',0)>=ctl.get('mission_commit_frame',0)];starts=[e for e in ev if e.get('kind')==76 and e.get('role')==role and e.get('frame')==ctl.get('mission_commit_frame')];safe=n.get('safe_support' if role else 'safe_front')
  good=len(starts)==len(gates)==1 and starts[0]['seq']<gates[0]['seq'] and same(safe,slot['anchor']) and same(xyz(starts[0]),slot['anchor']) and role_stop_gate(report,role,gates[0])
  details.append(dict(role=role,verified=bool(good),origin=safe,source_frame=slot['anchor_frame']))
 checks['actual_reserved_anchors_and_core_entry_stops']=all(x['verified'] for x in details) and 25<=distance(n.get('safe_front'),n.get('safe_support'))<=180
 return dict(verified=all(v is True for v in checks.values()),checks=checks,roles=details,origin_semantics='same_lease_actual_reserved_anchors_not_spawn_or_proposal')

def raw_pairs(report,stage=None):
 pairs=[];seen=set()
 for a,b in zip(report.get('events',[]),report.get('events',[])[1:]):
  key=(a.get('frame'),a.get('tick'),a.get('mission_stage'))
  if a.get('kind')==b.get('kind')==3 and a.get('role')==0 and b.get('role')==1 and all(a.get(k)==b.get(k) for k in ('frame','tick','mission_stage')) and key not in seen and (stage is None or key[2]==stage):pairs.append((a,b));seen.add(key)
 return pairs

def prepare_checks(report):
 n=report.get('native',{});ev=report.get('events',[]);rq=mission_fields(report);toggle=n.get('toggle_frame',0);button=rq.get('button',{});entry=int(button.get('toggle',{}).get('entry','0'),0);gates=[e for e in ev if e.get('kind')==42];before=[e for e in ev if e.get('kind')==37];after=[e for e in ev if e.get('kind')==43];calls=[e for e in ev if e.get('kind') in [40,41] and e.get('tag')==5];replay=[e for e in ev if e.get('kind')==33 and e.get('lease_stage')==3];checks={}
 checks['exact_toggle_button']=button.get('command_set_hash')=='0xb74cf71a' and button.get('toggle',{}).get('asset_id')=='0x5977a798' and button.get('toggle',{}).get('asset_type')=='0x7d464170' and entry==n.get('button') and int(button.get('toggle',{}).get('schema','0'),0)==n.get('button_schema')
 checks['initial_actual_weapon_capture']=len(before)==1 and n.get('initial_weapon_asset')==before[0].get('active_weapon_asset') in (0x447ea26e,0x41872ecc) and type(n.get('initial_weapon_entry')) is int and n['initial_weapon_entry']>0 and n['initial_weapon_entry']==before[0].get('active_weapon_entry')
 checks['prepare_stage_order']=len(gates)==len(before)==len(after)==1 and before[0]['seq']<gates[0]['seq']<after[0]['seq'] and n.get('prepare_gate_frame')==gates[0]['frame'] and gates[0].get('active_weapon_asset')==after[0].get('active_weapon_asset')==0x447ea26e
 if n.get('toggle_calls')==0:
  checks['optional_normal_toggle']=not calls and not replay and n.get('toggle_hook_calls')==0 and n.get('initial_weapon_asset') in [0x447ea26e,0x41872ecc]
  checks['prepare_idle_ak_raw']=checks['prepare_stage_order'] and gates[0].get('lease_stage')==0
 else:
  checks['optional_normal_toggle']=n.get('toggle_calls')==n.get('toggle_hook_calls')==1 and len(calls)==2 and [x['kind'] for x in calls]==[40,41] and calls[0]['arg']==entry and all(x.get('lease_stage')==3 and x['frame']==toggle for x in calls) and checks['prepare_stage_order'] and before[0]['seq']<calls[0]['seq']<calls[1]['seq']<gates[0]['seq'] and n.get('initial_weapon_asset') in [0x447ea26e,0x41872ecc]
  rows=[];seen=set()
  if len(gates)==1:
   for e in reversed(ev):
    if e.get('kind')==3 and e.get('lease_stage')==3 and e.get('seq',0)<gates[0]['seq'] and e.get('frame') not in seen:rows.append(e);seen.add(e['frame'])
    if len(rows)==3:break
  checks['prepare_idle_ak_raw']=len(rows)==3 and all(e['frame']>=toggle+15 and e.get('active_weapon_asset')==0x447ea26e and e.get('active_weapon_entry')==n.get('observed_weapon_entry') and stance.sample(e,hold=True) and not e.get('status84',0)&0x20080000 for e in rows) and n.get('ak_samples',0)>=3
 replay_before=[e for e in ev if e.get('kind')==32 and e.get('lease_stage')==3]
 checks['bounded_prepare_reconstituted_stops']=len(replay)==len(replay_before)==n.get('prepare_reconstituted_stops') and all(a.get('arg')==b.get('arg')==1 and a.get('caller')==b.get('caller')==0x787791 and a.get('tag')==b.get('tag')==0 and a.get('frame')==b.get('frame') and toggle+15<=b['frame']<=n.get('prepare_gate_frame',0) and a['seq']<b['seq'] and a.get('state_id')==96 and stance.sample(b,hold=True) and a.get('active_weapon_asset')==b.get('active_weapon_asset')==0x447ea26e for a,b in zip(replay_before,replay))
 all_stops=[e for e in ev if e.get('kind')==33 and report['native'].get('issued_frame',0)<=e.get('frame',0)<report['native'].get('returned_frame',0)]
 checks['no_unbound_private_stops']=len(all_stops)==3+len(replay) and all(e.get('lease_stage') in [0,4,2,3] and e.get('arg')==1 and e.get('caller')==0x787791 for e in all_stops) and n.get('total_private_stops',0)>=len(all_stops)
 return checks


def effect_audit(report):
 ev=report.get('events',[]);n=report.get('native',{});rq=mission_fields(report);front=actor(report,0).get('object_id');target=rq.get('target_object_id');attack=n.get('attack_issued_frame',0);retreat=n.get('retreat_started',0);orders=[e for e in ev if e.get('kind') in (34,12,13,35) and e.get('tag')==2];checks={};pairs=raw_pairs(report,2)
 checks['one_explicit_normal_script_attack']=len(orders)==4 and [e['kind'] for e in orders]==[34,12,13,35] and all(e.get('role')==0 and e.get('frame')==attack and e.get('arg')==target and e.get('arg_source')==1 and e.get('arg_shots')==0x7fffffff and e.get('target_visible')==1 and e.get('mission_stage')==2 and e.get('lease_stage')==1 for e in orders) and n.get('attack_calls')==n.get('attack_facade_calls')==n.get('attack_private_calls')==1
 body=[e for e in ev if e.get('kind')==20 and e.get('role')==0 and e.get('damage_source')==front and e.get('target_id')==target];drops=[e for e in ev if e.get('kind')==22 and e.get('role')==0 and e.get('lease_stage')==1];hits=[];used=set()
 for hit in body:
  if not checks['one_explicit_normal_script_attack'] or not orders[-1]['seq']<hit['seq'] or hit.get('target_visible')!=1 or hit.get('mission_stage')!=2 or hit.get('lease_stage')!=1 or not attack<=hit['frame']<retreat or not finite(hit.get('damage_reported')) or hit['damage_reported']<=0 or hit.get('damage_after',0)<=0 or not close(hit.get('damage_before',0)-hit.get('damage_after',0),hit['damage_reported']):continue
  packets=damage_packet(hit,front,number(report.get('private_target',{}).get('address',0)))
  commits=[e for e in ev if e.get('kind')==24 and e.get('caller')==0x7d2946 and e.get('role')==0 and e.get('target_visible')==1 and e.get('lease_stage')==1 and e.get('mission_stage')==2 and e.get('damage_source')==front and e.get('target_id')==target and e.get('frame')==hit['frame'] and e.get('tick')==hit.get('tick') and orders[-1]['seq']<e['seq']<hit['seq'] and all(close(e.get(k),hit.get(k)) for k in ('damage_before','damage_after','damage_reported'))]
  ammo=[e for e in drops if e['seq']>hit['seq'] and 0<=e['frame']-hit['frame']<=3 and 0<=((e.get('tick',0)-hit.get('tick',0))&0xffffffff)<=250 and e.get('active_weapon_asset')==AK and e.get('active_weapon_entry')==n.get('weapon_entry') and e.get('damage_source')==front and e.get('target_id')==target and close(e.get('damage_before',0)-e.get('damage_after',0),1)]
  gates=[e for e in ev if e.get('kind')==86 and e.get('role')==1 and e['seq']<hit['seq']];hold=xyz(gates[-1]) if gates else None
  near=[p for p in pairs if abs(p[0]['frame']-hit['frame'])<=3 and p[0]['seq']>orders[-1]['seq'] and p[0].get('target_visible')==1 and stance.sample(p[1],hold=True) and 25<=distance(xyz(p[0]),xyz(p[1]))<=350 and distance(xyz(p[1]),hold)<=15]
  if len(packets)==len(commits)==len(ammo)==1 and near and ammo[0]['seq'] not in used:
   used.add(ammo[0]['seq']);hits.append(dict(body_event_seq=hit['seq'],commit_event_seq=commits[0]['seq'],ammo_event_seq=ammo[0]['seq'],body_frame=hit['frame'],paired_support_frame=near[0][0]['frame'],damage=hit['damage_reported'],packet=packets[0]))
 checks['same_order_packet_commit_ammo_and_support']=bool(hits) and len(hits)==len(body)==n.get('damage_count') and close(sum(h['damage'] for h in hits),n.get('damage_total')) and n.get('commit_own_calls')==len(hits)
 initial=n.get('weapon_ammo');last=n.get('last_ammo');checks['actual_same_entry_ammo_chain']=type(initial) is int and 1<=initial<=3 and type(last) is int and 0<=last<initial and len(drops)==n.get('shot_samples')==len(hits) and bool(drops) and close(drops[0].get('damage_before'),initial) and close(drops[-1].get('damage_after'),last) and all(close(a.get('damage_after'),b.get('damage_before')) for a,b in zip(drops,drops[1:])) and all(e.get('active_weapon_entry')==n.get('weapon_entry') and e.get('active_weapon_asset')==AK and 0<=e.get('damage_after',-1)<e.get('damage_before',0)<=3 and orders and orders[-1]['seq']<e['seq'] and attack<=e['frame']<=retreat for e in drops)
 binding=report.get('weapon_asset_binding',{});checks['actual_immutable_ak_asset']=binding.get('session_id')==report.get('session_id') and binding.get('pid')==report.get('preflight',{}).get('pid') and binding.get('reported_entry')==hex(n.get('weapon_entry',0)) and binding.get('reported_template')==hex(n.get('weapon_template',0)) and binding.get('asset_type')=='0x94d4d96e' and binding.get('asset_id')=='0x447ea26e' and binding.get('method')=='reported_template_plus4_to_schema_to_asset_header'
 front_report=dict(report,events=[e for e in ev if e.get('role')==0]);preparation=prepare_checks(front_report);preparation.pop('no_unbound_private_stops',None);gates=[e for e in ev if e.get('kind') in (37,43) and e.get('role')==0];checks['normal_prepare_and_two_clean_stops']=bool(gates) and all(v is True for v in preparation.values()) and all(role_stop_gate(report,0,g) for g in gates)
 dual=[e for e in ev if e.get('kind')==86];checks['dual_stop_before_attack']=len(dual)==2 and {e.get('role') for e in dual}=={0,1} and len({(e['frame'],e['tick']) for e in dual})==1 and all(role_stop_gate(report,e['role'],e) and e.get('target_visible')==1 and orders and e['seq']<orders[0]['seq'] for e in dual)
 checks['no_support_attack']=not any(e.get('role')==1 and e.get('kind') in (12,13,34,35) and e.get('mission_stage') in (1,2,3,4) for e in ev)
 return dict(verified=all(v is True for v in checks.values()),checks=checks,qualified_hits=hits,source_damage_amount=sum(h['damage'] for h in hits),prepare_checks=preparation,lethal_verified=False,scope='nonlethal Conscript direct AK with Flak actual positional support; no Flak ground-fire claim')

def weapon_metadata_audit(report):
 """Actual own-live authorization and immutable AK schema reads, never stale entry RPM."""
 try:
  n=report['native'];b=report['weapon_asset_binding'];a=b['current_own_actor'];raw=b['raw_before'];after=b['raw_after'];expected=[n['unit'],n['object_id'],n['owner'],n['weapon_entry'],n['weapon_template'],n['weapon_slot']]
  checks={}
  checks['original_native_binding']=b['session_id']==report['session_id'] and b['pid']==report['preflight']['pid'] and b['reported_entry']==hex(n['weapon_entry']) and b['reported_template']==hex(n['weapon_template']) and b['native_binding_before']==b['native_binding_after']==expected and all(type(x) is int and x>0 for x in expected)
  checks['actual_owned_actor_authorized']=a['object_id']==n['object_id'] and number(a['address'])==n['unit'] and number(a['type_hash'])==0x19ab11af and number(a['owner_address'])==n['owner'] and controller.word(b['own_hp_bits']) and finite(controller.f32(b['own_hp_bits'])) and controller.f32(b['own_hp_bits'])>0
  checks['actual_readonly_double_asset_words']=isinstance(raw,list) and len(raw)==5 and raw==after and all(type(x) is int and 0<=x<=0xffffffff for x in raw) and raw[0]==0xc37534 and raw[1]>0 and raw[2]>0 and raw[3:]==[0x94d4d96e,0x447ea26e] and number(b['template_schema'])==raw[1] and number(b['asset_header'])==raw[2] and b['asset_type']=='0x94d4d96e' and b['asset_id']=='0x447ea26e' and b['entry_memory_read'] is False and b['mutations'] is False and b['method']=='reported_template_plus4_to_schema_to_asset_header'
  checks['true_observation_clock']=all(type(b[k]) is int for k in ('observed_frame_start','observed_frame','own_frame_start','own_frame_end')) and n['attack_issued_frame']<=b['observed_frame_start']<=b['own_frame_start']==b['own_frame_end']<=b['observed_frame']<=b['observed_frame_start']+4
  return dict(verified=all(v is True for v in checks.values()),checks=checks,scope='actual_immutable_weapon_metadata_only_no_effect_or_entry_liveness_credit')
 except (KeyError,TypeError,ValueError,IndexError,OverflowError,struct.error):return dict(verified=False,checks={'actual_asset_read_evidence':False})

def retreat_audit(report,moves,follow):
 ev=report.get('events',[]);n=report.get('native',{});begins=[e for e in ev if e.get('kind')==89];checks=dict(two_role_retreat_boundary=len(begins)==2 and {e.get('role') for e in begins}=={0,1} and len({(e['frame'],e['tick']) for e in begins})==1 and all(e.get('mission_stage')==3 and e.get('leader_role')==1 and e.get('follower_role')==0 and e.get('frame')==n.get('retreat_started') for e in begins));details=[]
 for role in (0,1):
  origin=n.get('safe_support' if role else 'safe_front');gates=[e for e in ev if e.get('kind')==91 and e.get('role')==role];gate=gates[0] if len(gates)==1 else None;samples=last_position_samples(report,role,gate['seq'] if gate else 0,stage=3);final=[e for e in ev if e.get('kind')==66 and e.get('role')==role];start=next((e for e in begins if e.get('role')==role),None)
  good=bool(gate and len(samples)==3 and samples[-1]['frame']==gate['frame'] and all(distance(xyz(e),origin)<=15 and abs(e['z']-origin[2])<=10 for e in samples) and distance(xyz(gate),origin)<=15 and len(final)==1 and gate['seq']<final[0]['seq'] and role_stop_gate(report,role,final[0]) and distance(xyz(final[0]),origin)<=15 and abs(final[0]['z']-origin[2])<=10)
  displacement=distance(xyz(start),xyz(gate)) if start and gate else None;details.append(dict(role=role,verified=good,home_arrival_frames=[e['frame'] for e in samples],retreat_displacement=displacement if finite(displacement) else None))
 last=[e for e in ev if e.get('kind')==95];leaderhome=[e for e in ev if e.get('kind')==91 and e.get('role')==1];leaderstops=[e for e in ev if e.get('kind')==83 and e.get('role')==1 and e.get('mission_stage')==3];frontstops=[e for e in ev if e.get('kind')==94 and e.get('role')==0 and e.get('mission_stage')==3]
 checks['last_front_move_after_leader_home_and_follow_stop']=len(last)==1 and last[0].get('role')==0 and bool(leaderhome) and bool(leaderstops) and bool(frontstops) and leaderhome[-1]['seq']<leaderstops[-1]['seq']<last[0]['seq'] and frontstops[-1]['seq']<last[0]['seq'] and role_stop_gate(report,1,leaderstops[-1]) and any(g['role']==0 and g['seq']>last[0]['seq'] and same(g['goal'],n.get('safe_front')) for g in moves['groups'])
 checks['both_actual_home_three_frames_and_final_stops']=all(x['verified'] for x in details) and n.get('home_arrivals')==[3,3] and n.get('front_retreat_arrivals')==n.get('support_retreat_arrivals')==3
 checks['retreat_within_fixed_limit']=n.get('retreat_started',0)<n.get('returned_frame',0)<=n.get('mission_deadline_frame',0) and n.get('returned_frame',0)-n.get('retreat_started',0)<=1800
 checks['actual_retreat_follow']=follow['retreat_follow_observed'] and all(x['verified'] for x in follow['stages'] if x['mission_stage']==3)
 return dict(verified=all(v is True for v in checks.values()),checks=checks,roles=details,long_retreat_verified=all(finite(x['retreat_displacement']) and x['retreat_displacement']>=120 for x in details))
def role_stop_gate(report,role,gate):
 events=[e for e in report.get('events',[]) if e.get('role')==role and e.get('seq',0)<gate.get('seq',0)];stops=[e for e in events if e.get('kind')==33 and e.get('tag')==4 and e.get('arg')==1 and e.get('caller')==0x787791]
 if not stops:return False
 stop=stops[-1];samples=[e for e in events if e.get('kind')==3 and e['seq']>stop['seq']];last=list({e['frame']:e for e in samples}.values())[-3:];chain=[e for e in events if e.get('kind') in (30,32,33,31) and e.get('tag')==4 and e.get('frame')==stop['frame']]
 return stance.sample(gate,hold=True) and [e['kind'] for e in chain]==[30,32,33,31] and all(e.get('arg')==1 for e in chain) and settled_stop([dict(stop,kind=23)]+samples+[dict(gate,kind=24)])['verified'] and len(last)==3 and all(stance.sample(e,hold=True) for e in last)
def terminal_entries_verified(entries):
 try:
  block=(HERE/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0];expected={int(a,0):s.replace('\\x','') for a,s in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',block)}
  return len(expected)==len(entries)==len({number(e['address']) for e in entries})==17 and all(e.get('expected')==e.get('actual')==expected.get(number(e['address'])) and e.get('restored') is True for e in entries)
 except (OSError,ValueError,TypeError,KeyError,IndexError):return False
def terminal_readonly_audit(report):
 n=report.get('native',{});pre=report.get('preflight',{});rq=report.get('request',{});t=report.get('terminal_readonly',{})
 expected=dict(pid=pre.get('pid'),session_id=report.get('session_id'),commander_id=pre.get('commander_id'),command_id=rq.get('command_id'),task_id=rq.get('task_id'),seq=rq.get('seq'),token=rq.get('token'),owner=pre.get('owner'),logic=pre.get('logic'),native_binary_sha256=report.get('native_binary_sha256'))
 try:layout=json.loads((HERE/'inert-layout.json').read_text())
 except (OSError,ValueError):return False
 return all(v is not None and t.get(k)==v and type(t.get(k)) is type(v) for k,v in expected.items()) and t.get('layout')==layout and layout.get('dll_sha256')==report.get('native_binary_sha256') and t.get('mutations') is False and t.get('binding_verified') is True and t.get('timer')==t.get('active')==0 and t.get('phase')==n.get('phase') and t.get('error')==n.get('error') and t.get('front_return_verified')==n.get('return_verified') and t.get('support_return_verified')==n.get('support',{}).get('returned') and t.get('restore_mask')==131071 and terminal_entries_verified(t.get('entries',[])) and terminal_header_audit(report,t)

def terminal_header_audit(report,t):
 """Decode both original31148B headers; no confidence from a binding boolean."""
 try:
  a=bytes.fromhex(t['header_before_hex']);b=bytes.fromhex(t['header_after_hex'])
  if len(a)!=31148 or a!=b:return False
  h=controller.plain(controller.L.Header.from_buffer_copy(a));n=report['native']
  if (h['magic'],h['version'])!=(0x4d463136,16) or h['phase'] not in (3,4):return False
  fixed=('magic','version','pid','thread','owner','ai','logic','start_low','start_high','session','commander','command','task','token','seq','phase','error','active','restore_mask','return_verified','overflow','controller_input','controller','slots','mission_commit','stances')
  return all(h[k]==n[k] for k in fixed) and h['active']==h['overflow']==0 and h['restore_mask']==131071 and h['support']['returned']==n['support']['returned'] and h['controller']['held_mask']==h['controller']['channel_claimed']==0
 except (KeyError,TypeError,ValueError,IndexError,OverflowError):return False

def disposal_binding_verified(disposition,report,role):
 """Only independent complete, same-frame live lists can prove dead lease release."""
 try:
  d=disposition;pre=report['preflight'];rq=report['request'];oid=actor(report,role)['object_id'];expected=dict(pid=pre['pid'],session_id=report['session_id'],commander_id=pre['commander_id'],command_id=rq['command_id'],task_id=rq['task_id'],seq=rq['seq'],token=rq['token'],owner=pre['owner'],logic=pre['logic'],native_binary_sha256=report['native_binary_sha256'])
  if role not in (0,1) or not all(d.get(k)==v and type(d.get(k)) is type(v) for k,v in expected.items()) or d.get('role')!=role or d.get('object_id')!=oid or d.get('source_session_id')!=report['session_id'] or d.get('mutations') is not False:return False
  canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  if d.get('source_request_sha256')!=canonical(rq) or d.get('source_preflight_sha256')!=canonical(pre):return False
  states=[d.get('terminal_before',{}),d.get('terminal_after',{})]
  if not all(terminal_readonly_audit(dict(report,terminal_readonly=t)) and t.get('phase')==4 and t.get('error')==report['native'].get('error') for t in states):return False
  if not states[0].get('shared_pointer') or states[0].get('shared_pointer')!=states[1].get('shared_pointer') or not states[0].get('module_base') or states[0].get('module_base')!=states[1].get('module_base'):return False
  scans=d.get('scans',[])
  if len(scans)!=2:return False
  for s in scans:
   ids=s.get('ids');count=s.get('count')
   if s.get('logic')!=pre['logic'] or s.get('complete') is not True or type(s.get('frame')) is not int or type(s.get('end_frame')) is not int or s['frame']!=s['end_frame'] or s['frame']<report['native'].get('issued_frame',0) or not isinstance(ids,list) or type(count) is not int or not 1<=count<=20000 or len(ids)!=count or len(set(ids))!=count or any(type(i) is not int or i<=0 for i in ids) or oid in ids:return False
  return scans[0]['frame']<scans[1]['frame']
 except (KeyError,ValueError,TypeError,OSError):return False
def control_release(report):
 """Independent normal return or proven disposal; scene disposal remains unknown."""
 n=report.get('native',{});ev=report.get('events',[]);pre=report.get('preflight',{});manager=number(pre.get('ai',0))+0x104;roles=[]
 for role,data in [(0,n),(1,n.get('support',{}))]:
  rows=[e for e in ev if e.get('role')==role];returned=[e for e in rows if e.get('kind')==5 and e.get('tag')==3];transfers=[e for e in rows if e.get('kind')==15 and e.get('tag')==3 and e.get('arg')==1];adds=[e for e in rows if e.get('kind')==16 and e.get('tag')==3 and e.get('arg')==manager and e.get('caller')==0x83885b];gates=[e for e in rows if e.get('kind') in (66,67,68)];forced=any(e.get('kind')==69 for e in rows)
  good=False
  if len(returned)==len(transfers)==len(adds)==1 and gates:
   before=[g for g in gates if g['seq']<min(transfers[0]['seq'],adds[0]['seq'])];gate=before[-1] if before else None
   good=bool(gate and role_stop_gate(report,role,gate) and not forced and data.get('detach_calls')==data.get('return_calls')==data.get('return_verified',data.get('returned'))==1 and transfers[0]['seq']<returned[0]['seq'] and adds[0]['seq']<returned[0]['seq'] and returned[0].get('team')==number(pre.get('default_team',0)) and finite(returned[0].get('own_hp')) and returned[0]['own_hp']>0)
  never=data.get('detach_calls')==0 and not any(e.get('kind')==14 and e.get('tag')==1 for e in rows)
  disposed=disposal_binding_verified(report.get('disposal_readonly',{}).get(str(role),{}),report,role)
  view=actor(report,role) if not never else {}
  roles.append(dict(role=role,object_id=view.get('object_id',n.get('slots',[{},{}])[role].get('id',0)),returned=good,disposed=disposed,never_held=never,released=bool(good or disposed or never)))
 inert=n.get('controller',{}).get('held_mask')==n.get('controller',{}).get('channel_claimed')==0 and n.get('phase') in (3,4) and n.get('restore_mask')==131071 and n.get('active')==n.get('overflow')==0 and terminal_readonly_audit(report);ok=source_pins(report) and inert and all(x['released'] for x in roles)
 stance_restores={x['role']:x.get('original_stance_restored',False) for x in stance.audit(report).get('roles',[])}
 restored=bool(ok and all(x['never_held'] or stance_restores.get(x['role'],False) for x in roles))
 return dict(restoration_verified=restored,stance_restoration_verified=restored,control_release_verified=bool(ok),return_verified=bool(ok and all(x['returned'] for x in roles)),disposed_verified=bool(ok and any(x['disposed'] for x in roles)),actors=roles,semantics='independent_native_pool_return_or_readonly_disposal' if ok else 'unknown',completion_claim=False)
def progress(report,mission_id):
 n=report.get('native',{});ev=report.get('events',[])
 if n.get('mission_commit',{}).get('status')!=1 or not n.get('controller',{}).get('mission_commit_frame') or not n.get('issued_frame') or not ev:return None
 last=ev[-1];roles={};remaining=None
 for e in ev:
  if e.get('role') in (0,1) and finite(e.get('own_hp')):roles[e['role']]=max(0,e['own_hp'])
  if e.get('role')==0 and e.get('target_visible')==1 and point(e.get('visible_target_xyz')):remaining=distance(xyz(e),e['visible_target_xyz'])
 restored={e.get('role') for e in ev if e.get('kind')==5 and e.get('tag')==3}=={0,1};stage=last.get('mission_stage');phase='restored' if restored else 'prepare' if stage==2 and last.get('lease_stage')!=1 else {0:'approach',1:'approach',2:'engage',3:'retreat',4:'retreat',5:'retreat'}.get(stage,'retreat')
 return dict(mission_id=mission_id,stage=phase,revision=last['seq'],observed_frame=last['frame'],deadline_frame=last['mission_deadline_frame'],approach_distance=remaining,own_hp=min(roles.values()) if roles else None,damage=sum(e['damage_reported'] for e in ev if e.get('kind')==20 and e.get('role')==0 and finite(e.get('damage_reported')) and e['damage_reported']>0),reason=REASONS.get(last.get('mission_reason'),'initial_binding'))
def qualify(report):
 try:return _qualify(report)
 except (KeyError,ValueError,TypeError,IndexError,OverflowError,OSError,struct.error):
  release=dict(control_release_verified=False,restoration_verified=False,return_verified=False,completion_claim=False)
  try:release=control_release(report)
  except (KeyError,ValueError,TypeError,IndexError,OverflowError,OSError,struct.error):pass
  return dict(status='not_passed',checks={'well_formed_raw_evidence':False},effect_verified=False,source_damage_amount=0.,approach_verified=False,long_approach_verified=False,retreat_verified=False,long_retreat_verified=False,restoration_verified=release['restoration_verified'],restoration=release,control_release_verified=release['control_release_verified'],combined_arms_verified=False,qualified_hits=[],paired_stages=[],mission_protocol='continuous_tactical_v1',qualification_revision='mfm14_actual_breadcrumbs_v1')

def wait_anchor_audit(report):
 spec=importlib.util.spec_from_file_location('mfm14_wait_anchor_replan_q',HERE/'wait_anchor_replan.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.audit(report)

def retreat_departure_audit(report):
 spec=importlib.util.spec_from_file_location('mfm14_retreat_departure_q',HERE/'retreat_departure.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.audit(report)

def _qualify(report):
 common=common_audit(report);crumbs=breadcrumb_audit(report);release=control_release(report);motion=breadcrumb_motion_audit(report,crumbs);moves=normal_move_audit(report);follow=follow_audit(report,crumbs,moves);conditional=conditional_audit(report,moves);memory=memory_audit(report,moves);lease=lease_audit(report);entry=entry_audit(report);effect=effect_audit(report);retreat=retreat_audit(report,moves,follow);checks=dict(common['checks']);replans=wait_anchor_audit(report);n=report.get('native',{});ev=report.get('events',[]);rq=mission_fields(report)
 reserve=controller.audit(report);checks['original_paid_controller_and_write_once_commit']=reserve['verified']
 checks['explicit_actual_wait_anchor_replans']=replans['verified']
 departure=retreat_departure_audit(report);checks['explicit_actual_retreat_departure']=departure['verified'] and departure['success_verified']
 lineage=pending_lineage_audit(report);checks['explicit_actual_pending_lineage']=lineage['verified']
 schedule=schedule_audit(report);checks['original_thread_bounded_scheduler']=schedule['verified']
 alignment=tls_alignment_audit(report);checks['compiled_tls_scalar_alignment']=alignment['verified']
 asset=weapon_metadata_audit(report);checks['actual_owned_raw_weapon_asset_capture']=asset['verified']
 stances=stance.audit(report);checks['normal_stance_ownership_and_restore']=stances['verified']
 diagnostics=dispatch_diagnostic_audit(report);checks['raw_dispatch_diagnostic_counter_links']=diagnostics['verified']
 checks.update(actual_breadcrumb_publications=crumbs['verified'],actual_positive_path_motion=motion['verified'],normal_move_chains=moves['verified'],every_follow_actual_arrival_and_stop=follow['verified'],conditional_branches_if_observed=conditional['verified'],legal_frozen_memory_and_current_fire=memory['verified'],lease_scoped_no_native_override=lease['verified'],fresh_admission_actual_origins=entry['verified'],actual_nonlethal_packet_commit_ammo_support=effect['verified'],both_physical_retreat_origins=retreat['verified'])
 checks['finished_host_and_native']=report.get('status')=='finished' and report.get('host_exit')==0 and report.get('native_launch_intent_persisted') is True and n.get('phase')==3 and n.get('error')==n.get('lifecycle_fail')==n.get('owner_fail')==n.get('overflow')==n.get('active')==0 and n.get('restore_mask')==131071 and n.get('mission_stage')==4
 issued=n.get('issued_frame',0);attack=n.get('attack_issued_frame',0);returned=n.get('returned_frame',0);starts=[e for e in ev if e.get('kind')==76 and e.get('role')==0 and e.get('frame')==n.get('controller',{}).get('mission_commit_frame')];ends=[e for e in ev if e.get('kind')==64 and e.get('role')==0];initial=starts[0] if len(starts)==1 else None;end=ends[0] if len(ends)==1 else None
 endpoint_pairs=[p for p in raw_pairs(report) if end and p[0]['frame']==end['frame'] and p[0]['seq']<end['seq']];endpoint_geometry=bool(end and end.get('target_visible')==1 and distance(xyz(end),end.get('visible_target_xyz'))<=150 and endpoint_pairs and 25<=distance(xyz(endpoint_pairs[-1][0]),xyz(endpoint_pairs[-1][1]))<=200)
 approach=bool(initial and end and initial['seq']<end['seq'] and end['frame']-issued<=2100 and endpoint_geometry and follow['approach_follow_observed'] and all(r['verified'] for r in follow['stages'] if r['mission_stage']==1))
 long_approach=bool(approach and initial.get('target_visible')==1 and distance(xyz(initial),initial.get('visible_target_xyz'))>=300 and distance(xyz(initial),xyz(end))>=120)
 checks['actual_long_approach']=long_approach;checks['actual_long_retreat']=retreat['long_retreat_verified']
 checks['frozen_phase_deadlines']=0<issued<attack<n.get('retreat_started',0)<returned<=rq.get('expires_frame',0) and 300<=n.get('lease_frames',0)<=4500 and returned-issued<=n.get('lease_frames',0) and 0<attack-n.get('combat_started',attack)<=n.get('combat_frames',0)
 checks['effect_precedes_source_damage_retreat']=bool(effect['qualified_hits']) and n.get('retreat_reason')==1 and n.get('retreat_started',0)>=max(h['body_frame'] for h in effect['qualified_hits'])
 checkpoints=[e for e in ev if e.get('kind')==90];paired=[]
 for gate in (e for e in ev if e.get('kind')==84):
  rows=[e for e in checkpoints if e.get('frame')==gate['frame'] and e.get('tick')==gate['tick'] and e.get('mission_stage')==gate.get('mission_stage') and e.get('breadcrumb')==gate.get('breadcrumb') and e['seq']>gate['seq']];by={e.get('role'):e for e in rows};good=len(rows)==2 and set(by)=={0,1} and all(close(e.get('actual_gap'),distance(xyz(by[0]),xyz(by[1]))) for e in rows) and distance(xyz(by[gate['role']]),gate.get('breadcrumb',{}).get('xyz'))<=15
  paired.append(dict(frame=gate['frame'],mission_stage=gate.get('mission_stage'),follower_role=gate['role'],verified=bool(good)))
 checks['actual_paired_follow_checkpoints']=bool(paired) and len(checkpoints)==2*len(paired) and all(x['verified'] for x in paired)
 checks['bounded_actual_commands']=0<n.get('leader_move_count',999)<=32 and n.get('leader_move_count')==sum(e.get('kind') in (85,92) for e in ev) and n.get('follow_move_count',999)==sum(e.get('kind')==81 for e in ev)<=128 and n.get('leader_move_count')+n.get('follow_move_count')+len([e for e in ev if e.get('kind')==95])+2==len(moves['groups']) and n.get('approach_completed')==sum(e.get('kind')==84 and e.get('mission_stage')==1 for e in ev) and n.get('retreat_completed')==sum(e.get('kind')==84 and e.get('mission_stage')==3 for e in ev)
 checks['two_live_pool_returns_and_actual_pristine_terminal']=release['return_verified'] and not release['disposed_verified']
 complete=all(v is True for v in checks.values())
 return dict(status='formation_mission_effect_retreat_verified' if complete else 'not_passed',checks=checks,effect_verified=effect['verified'],source_damage_amount=effect['source_damage_amount'],new_order_fire_association_verified=effect['verified'],approach_verified=approach,long_approach_verified=long_approach,retreat_verified=retreat['verified'],long_retreat_verified=retreat['long_retreat_verified'],restoration_verified=release['restoration_verified'],combined_arms_verified=complete,qualified_hits=effect['qualified_hits'],paired_stages=paired,reserve_controller=reserve,weapon_metadata=asset,breadcrumb_audit=crumbs,motion_audit=motion,follow_audit=follow,conditional_branches=conditional,wait_anchor_replans=replans,retreat_departure=departure,pending_lineage=lineage,schedule_audit=schedule,tls_alignment_audit=alignment,dispatch_diagnostics=diagnostics,stance_ownership=stances,memory_checks=memory,lease_audit=lease,entry_audit=entry,effect_audit=effect,retreat_audit=retreat,restoration=release,lethal_verified=False,role_scope='Conscript nonlethal direct AK; Flak actual breadcrumb following and idle support, no Flak ground-fire claim',mission_protocol='continuous_tactical_v1',qualification_revision='mfm14_actual_breadcrumbs_v1')
def qualify_path(path):
 path=Path(path);raw=path.read_bytes();result=qualify(json.loads(raw.decode('utf-8-sig')));result.update(source_report=str(path.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),qualifier_sha256=sha(__file__),supplemental_sources=[dict(path=str(p),sha256=sha(p)) for p in source_paths() if p.exists()]);return result
