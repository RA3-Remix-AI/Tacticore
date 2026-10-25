"""Complete synthetic protocol replay; source hashes are real, never a field grant."""
import copy,hashlib,json,re,unittest,importlib.util,struct,uuid
from pathlib import Path
from test_common_qualification import q,fixture
from test_effect_qualification import effect_fixture
from test_mission_actor_admission import Memory

def full_fixture():
 r=effect_fixture();r['events']=[];n=r['native'];rq=r['request'];pre=r['preflight'];rq.update(command_id='00000000-0000-0000-0000-000000000001',task_id='00000000-0000-0000-0000-000000000002');n.update(command_id=rq['command_id'],task_id=rq['task_id'],pulse_requested=14390,pulse_acknowledged=14390,paused_samples=0);pre.update(default_team='0x7000',script_team='0x7100',logic='0x9000');rq.update(token=10,lease_frames=4500,target_contact_id='synthetic_current_contact',target_role='structure',safety_sha256='1d14e41e10224fb2a8215a2321a7fbbbeae8434b8c006a80fd314f4a11e7719e');r['private_target'].update(type_hash='0x92f9ad85',owner_player_id=4,object_id=77,owner=0x3500) # Use an actual audited structure below.
 catalog=json.loads((q.HERE.parent.parent/'visibility/template-safety-2d7873e1.json').read_text());kind=next(k for k,v in catalog['templates'].items() if v.get('role')=='structure');r['private_target']['type_hash']=kind
 n.update(pid=12,thread=9,owner=0x3000,ai=0x8000,logic=0x9000,unit=0x2000,update=0x4000,type_hash=q.ROLE_TYPES[0],token=10,callback_thread=9,target_id=77,phase=3,error=0,active=0,overflow=0,lifecycle_fail=0,owner_fail=0,restore_mask=65535,issued_frame=110,returned_frame=240,attack_issued_frame=183,retreat_started=189,combat_started=170,mission_stage=4,retreat_reason=1,detach_calls=1,return_calls=1,return_verified=1,move_calls=3,native_move=0,native_attack=0,native_add=0,native_remove=0,native_stop=0,regroup_count=0,hold_repair_count=0,leader_move_count=2,follow_move_count=2,approach_completed=1,retreat_completed=1,home_arrivals=[3,3],front_retreat_arrivals=3,support_retreat_arrivals=3,safe_front=[140.,0.,210.],safe_support=[0.,0.,210.],lease_frames=4500,prepare_gate_frame=177,crumbs=[[],[]])
 n['support'].update(thing=0x5000,update=0x6000,hash=q.ROLE_TYPES[1],detach_calls=1,return_calls=1,returned=1,move_calls=2,native_move=0,native_attack=0,native_add=0,native_remove=0,native_stop=0)
 r.update(status='finished',host_exit=0,native_launch_intent_persisted=True,executable_sha256=q.EXE)
 origins=[n['safe_front'],n['safe_support']];positions=copy.deepcopy(origins);stage=0;lease=0;seen=110;target=[480.,0.,210.];leader=0;followref=None
 def add(kind,role,frame,**v):
  pos=positions[role];e=dict(seq=len(r['events'])+1,kind=kind,role=role,unit_id=42+role,frame=frame,tick=frame*60,thread=9,owner=0x3000,team=0x7100,source=1,x=pos[0],y=pos[1],z=pos[2],own_hp=100.,tag=0,arg=0,caller=0,state_id=16,sm_flags=0,path=0,holder=0,lease_stage=lease,mission_stage=stage,mission_deadline_frame=4600,target_visible=1,target_last_seen_frame=seen,last_seen_target=list(target),visible_target_xyz=list(target),active_weapon_entry=0x123 if role==0 else 0,active_weapon_asset=q.AK if role==0 else 0,active_weapon_ammo=3,damage_source=42,target_id=77,damage_before=0.,damage_after=0.,damage_reported=0.,leader_role=leader,follower_role=1-leader,actual_gap=q.distance(*positions),breadcrumb=copy.deepcopy(followref) if followref else {})
  e.update(v);r['events'].append(e);return e
 def scheduler_capture(origin,frame,previous,advances):
  nonce=frame*60-10 if origin==2 else 0;words=[0x53434839,origin,rq['token'],rq['seq']]+list(struct.unpack('<4I',uuid.UUID(rq['command_id']).bytes))+list(struct.unpack('<4I',uuid.UUID(rq['task_id']).bytes))+[nonce,nonce,frame,previous,9,100,350,frame*60 if origin==2 else 0,advances,4600,1 if origin==2 else 0,1000];add(120+origin,0,frame,arg=origin,stack_count=0,stack_word_count=24,stack_words=words+[0]*104)
 def pair(frame):
  for role in (0,1):add(3,role,frame)
 def stop(role,frame):
  for kind in (30,32,33,31):add(kind,role,frame,tag=4,arg=1,caller=0x787791)
 def clean(roles,frames):
  for frame in frames:
   if frame==111:scheduler_capture(2,111,110,2)
   for role in roles:add(3,role,frame)
 def move(role,frame,goal):
  for kind in (50,10,11,51):add(kind,role,frame,tag=6,arg=1,command_xyz=list(goal),argument_path=0,argument_limit=3.4028234663852886e38)
 def crumb(role,frame,path):
  index=len(n['crumbs'][role]);e=add(80,role,frame,arg=index);u=q.actor(r,role);c=dict(index=index,role=role,frame=frame,published_seq=e['seq'],thing=int(u['address'],0),object_id=u['object_id'],type_hash=q.ROLE_TYPES[role],owner=0x3000,update=int(u['ai_address'],0),holder=0,status_words=[0]*7,height_flags=4,height=0.,hp=100.,xyz=list(positions[role]),path_distance=path,mission_stage=stage,surface_verified=1);e['breadcrumb']=copy.deepcopy(c);n['crumbs'][role].append(copy.deepcopy(c));return c
 def follow(role,frame,c):
  nonlocal followref
  followref=copy.deepcopy(c);add(81,role,frame,follow_crumb_role=c['role'],follow_crumb_index=c['index'],follow_active=1);move(role,frame,c['xyz'])
 def arrival(role,frames,c):
  nonlocal followref
  positions[role]=list(c['xyz'])
  for f in frames:pair(f)
  add(84,role,frames[-1],follow_crumb_role=c['role'],follow_crumb_index=c['index'],follow_active=1)
  for other in (0,1):add(90,other,frames[-1])
  stop(role,frames[-1]);clean([role],[frames[-1]+2,frames[-1]+4,frames[-1]+6]);add(94,role,frames[-1]+6)
 # Captured admission records use the real pure record verifier and source fingerprints.
 records=[]
 for role in (0,1):
  record=q.admission.actor_admission(Memory(),0x2000);u=q.actor(r,role);ground=record['grounded_status'];record.update(object_id=u['object_id'],address=u['address'],type_hash=u['type_hash']);ground.update(object_id=u['object_id'],address=u['address'],type_hash=u['type_hash'],xyz=list(origins[role]),template='SovietAntiVehicleInfantry' if role else 'SovietAntiInfantryInfantry');record['state_snapshot'].update(update=u['ai_address'],update_backref=u['address'],sm_owner=u['address']);records.append(record)
 r['private_target']['observed_frame']=100;r['initial_admission']=dict(frame=100,validated_frame=100,mutations=False,front=records[0],support=records[1],target=copy.deepcopy(r['private_target']));rq['safe_origin']=dict(origin_method='current_verified_owned_movable_positions',viewer_player_id=3,front_id=42,support_id=43,currently_visible_enemy_threats_within350=[],observed_frame=100)
 add(0,0,110);scheduler_capture(1,110,0xffffffff,1)
 for role in (0,1):add(71,role,110)
 for role in (0,1):
  add(18,role,110,tag=1,arg=0x8104,caller=0x838877);add(1,role,110,tag=1)
 stage=1;lease=5
 for role in (0,1):stop(role,110)
 clean([0,1],[111,113,115])
 for role in (0,1):add(58,role,115)
 c0=crumb(0,115,0.);crumb(1,115,0.);add(85,0,115);move(0,115,target)
 positions[0]=[180.,0.,210.];pair(130);positions[0]=[220.,0.,210.];pair(140);crumb(0,140,80.)
 positions[0]=[260.,0.,210.];pair(150);follow(1,150,c0);arrival(1,[151,153,155],c0)
 positions[0]=[340.,0.,210.];pair(170);crumb(0,170,200.)
 stage=2;lease=0
 for role in (0,1):add(64,role,170);stop(role,170)
 clean([0,1],[173,175,177])
 for role in (0,1):add(86,role,177)
 add(37,0,177);add(42,0,177);lease=4;stop(0,177);clean([0],[179,181,183]);add(43,0,183);lease=1
 for kind in (34,12,13,35):add(kind,0,183,tag=2,arg=77,arg_source=1,arg_shots=0x7fffffff)
 add(24,0,187,caller=0x7d2946,damage_before=100.,damage_after=95.,damage_reported=5.)
 template=next(e for e in effect_fixture()['events'] if e['kind']==20);fields={k:copy.deepcopy(template[k]) for k in ('stack_words','stack_word_count','stack_words_address')};add(20,0,187,caller=0x78e313,damage_before=100.,damage_after=95.,damage_reported=5.,**fields)
 pair(188);add(22,0,188,damage_before=3.,damage_after=2.)
 stage=3;lease=5;leader=1
 for role in (0,1):stop(role,189);add(89,role,189,arg=1)
 clean([0,1],[191,193,195])
 for role in (0,1):add(58,role,195)
 crumb(0,195,0.);cs=crumb(1,195,0.);add(98,1,195,breadcrumb=copy.deepcopy(cs),argument_path=195,argument_limit=200.,follow_active=0,motion_state=1);add(85,1,195);move(1,195,origins[1])
 positions[1]=[110.,0.,210.];pair(200);add(99,1,200,arg=1,breadcrumb=copy.deepcopy(cs),argument_path=195,argument_limit=200.,follow_active=0,motion_state=1);follow(0,200,cs)
 positions[1]=[0.,0.,210.]
 for f in (210,212,214):pair(f)
 crumb(1,214,140.);add(91,1,214);stop(1,214);clean([1],[216,218,220]);add(83,1,220,leader_hold_xyz=origins[1])
 # Merge by real logical time below; every role's arrival and Stop remains distinct.
 arrival(0,[215,216,218],cs);add(95,0,225);move(0,225,origins[0]);positions[0]=list(origins[0])
 for f in (227,229,231):pair(f)
 add(91,0,231);stage=4;lease=2
 for role in (0,1):stop(role,231)
 clean([0,1],[234,236,238])
 for role in (0,1):add(66,role,238)
 for role in (0,1):add(15,role,240,tag=3,arg=1);add(16,role,240,tag=3,arg=0x8104,caller=0x83885b);add(5,role,240,tag=3,team=0x7000)
 # This fixture authors independent role timelines, then serializes their actual frame order.
 seen=set();r['events']=[e for e in r['events'] if e['kind']!=3 or not ((e['role'],e['frame']) in seen or seen.add((e['role'],e['frame'])))];old_events=list(r['events']);r['events'].sort(key=lambda e:(e['frame'],e['seq']));seqmap={e['seq']:i+1 for i,e in enumerate(r['events'])}
 for e in r['events']:
  e['seq']=seqmap[e['seq']]
  if e.get('breadcrumb',{}).get('published_seq'):e['breadcrumb']['published_seq']=seqmap[e['breadcrumb']['published_seq']]
 for role in (0,1):
  for c in n['crumbs'][role]:c['published_seq']=seqmap[c['published_seq']]
 # Source provenance is actual on-disk Native build metadata; it is never mocked True.
 paths={'native_binary_sha256':q.HERE/'bin/TacticalMissionFormation10.dll','native_host_sha256':q.HERE/'bin/tactical_host.exe','native_source_sha256':q.HERE/'lease.cpp','native_shared_sha256':q.HERE/'shared.h','wrapper_sha256':q.HERE/'lease.py','native_layout_sha256':q.HERE/'native_layout.py','mission_contract_sha256':q.HERE/'mission_contract.py','native_revision_sha256':q.HERE/'revision.json'}
 for key,path in paths.items():r[key]=q.sha(path)
 r['native_includes_sha256']={p.name:q.sha(p) for p in q.HERE.glob('*.cpp.inc')};r['supplemental_sources']={p.name:q.sha(p) for p in q.source_paths()}
 layout=json.loads((q.HERE/'inert-layout.json').read_text());block=(q.HERE/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0];entries=[dict(address=a,expected=s.replace('\\x',''),actual=s.replace('\\x',''),restored=True) for a,s in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',block)]
 r['terminal_readonly']=dict(pid=pre['pid'],session_id=r['session_id'],commander_id=pre['commander_id'],command_id=rq['command_id'],task_id=rq['task_id'],seq=rq['seq'],token=rq['token'],owner=pre['owner'],logic=pre['logic'],native_binary_sha256=r['native_binary_sha256'],layout=layout,mutations=False,binding_verified=True,timer=0,active=0,phase=3,error=0,restore_mask=65535,front_return_verified=1,support_return_verified=1,entries=entries)
 return r

class CompleteSyntheticProtocol(unittest.TestCase):
 def test_full_protocol_no_mock_source_pins(self):
  if not(q.HERE/'revision.json').exists():self.skipTest('Native build revision not frozen yet')
  r=full_fixture();a=q.qualify(r);self.assertTrue(q.source_pins(r));self.assertEqual(a['status'],'formation_mission_effect_retreat_verified',a);self.assertFalse(a['lethal_verified'])
 def test_real_wrapper_and_q_exact_source_set_and_revision(self):
  r=full_fixture();spec=importlib.util.spec_from_file_location('mf5_complete_wrapper',q.HERE/'lease.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
  self.assertEqual(w.supplemental(),{p.name:q.sha(p) for p in q.source_paths()});self.assertTrue(w.frozen_sources_match(r));self.assertTrue(q.source_pins(r))
  for key in ('native_binary_sha256','native_shared_sha256','native_source_sha256','native_revision_sha256','wrapper_sha256'):
   changed=copy.deepcopy(r);changed[key]='0'*64;self.assertFalse(q.source_pins(changed),key)
  r['native_includes_sha256']['breadcrumb.cpp.inc']='0'*64;self.assertFalse(q.source_pins(r))
 def test_same_frame_in_lease_override_rejected_but_pre_post_allowed(self):
  r=full_fixture();first=next(e for e in r['events'] if e['kind']==1);extra=copy.deepcopy(first);extra.update(kind=10,tag=0);r['events'].insert(r['events'].index(first)+1,extra)
  for i,e in enumerate(r['events']):e['seq']=i+1
  self.assertFalse(q.lease_audit(r)['verified']);self.assertNotEqual(q.qualify(r)['status'],'formation_mission_effect_retreat_verified')
  r=full_fixture();extra=copy.deepcopy(r['events'][0]);extra.update(kind=10,tag=0,seq=0);r['events'].insert(0,extra);extra=copy.deepcopy(r['events'][-1]);extra.update(kind=10,tag=0,seq=len(r['events'])+1);r['events'].append(extra)
  self.assertTrue(q.lease_audit(r)['verified']) # Boundary audit is exact-seq, independent of common publication audit.
 def test_original_clock_token_identity_and_actual_return_cannot_change(self):
  for key,value in [('token',11),('pid',99),('update',0x1234),('mission_deadline_frame',4601),('callback_thread',10),('return_verified',0),('restore_mask',31)]:
   r=full_fixture();r['native'][key]=value;self.assertNotEqual(q.qualify(r)['status'],'formation_mission_effect_retreat_verified',key)
 def test_home_counter_cannot_replace_distinct_physical_arrivals(self):
  for mode in ('duplicate','out_of_range','wrong_origin','forced'):
   r=full_fixture()
   if mode=='duplicate':
    for e in r['events']:
     if e['kind']==3 and e['role']==0 and e['frame'] in (227,229,231):e['frame']=231
   if mode=='out_of_range':
    for e in r['events']:
     if e['kind']==3 and e['role']==1 and e['frame'] in (210,212,214):e['x']=30.
   if mode=='wrong_origin':r['native']['safe_front']=[1000.,0.,210.]
   if mode=='forced':next(e for e in r['events'] if e['kind']==66)['kind']=69
   self.assertNotEqual(q.qualify(r)['status'],'formation_mission_effect_retreat_verified',mode)
 def test_every_required_raw_check_is_a_real_completion_gate(self):
  if not(q.HERE/'revision.json').exists():self.skipTest('Native build revision not frozen yet')
  r=full_fixture()
  for kind in (20,24,22,81,84,94,91,95,66,5):
   damaged=copy.deepcopy(r);damaged['events']=[e for e in damaged['events'] if e['kind']!=kind];self.assertNotEqual(q.qualify(damaged)['status'],'formation_mission_effect_retreat_verified',kind)
if __name__=='__main__':unittest.main()
