"""Offline brief-raid evidence. Synthetic traces never grant field capabilities."""
import copy,ctypes as c,hashlib,importlib.util,json,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from test_mission_combat_v6 import fixture as old_fixture
from test_mission_actor_admission import Memory
import mission_actor_admission_v2 as admission
import mission_combat_v7_qualification as strict
import mission_combat_v7_runtime_qualification as runtime
P=Path(__file__).resolve().parent;D=P/'mission-combat-v7'
def fixture():
 r=old_fixture();old=r['events'];body=copy.deepcopy(next(e for e in old if e['kind']==20));commit=copy.deepcopy(next(e for e in old if e['kind']==24));ammo=copy.deepcopy(next(e for e in old if e['kind']==22));ev=[copy.deepcopy(e) for e in old if e['mission_stage']<6 or e['mission_stage']==11 or e['mission_stage']==6 and e['frame']<156]
 for index,frame in enumerate([156,160,164,174,178,182]):
  e=copy.deepcopy(body);e.update(kind=3,frame=frame,tick=frame*60);ev.append(e)
  for template in [commit,body]:
   e=copy.deepcopy(template);e.update(frame=frame,tick=frame*60,health_observed_frame=frame,damage_before=1000.-index*5,damage_after=995.-index*5);ev.append(e)
  before=3-index%3;e=copy.deepcopy(ammo);e.update(frame=frame+1,tick=(frame+1)*60,ammo_previous_frame=frame-1,ammo_previous_tick=(frame-1)*60,damage_before=float(before),damage_after=float(before-1),active_weapon_ammo=before-1);ev.append(e)
  if index==2:
   e=copy.deepcopy(ammo);e.update(kind=67,frame=170,tick=10200,ammo_previous_frame=169,ammo_previous_tick=10140,damage_before=0.,damage_after=3.,active_weapon_ammo=3);ev.append(e)
 for e in old:
  if e['mission_stage'] not in [7,8,9,10]:continue
  e=copy.deepcopy(e);e.update(frame=e['frame']+8,tick=(e['frame']+8)*60);ev.append(e)
 revision=0;stage_frame=0;seen=0
 for i,e in enumerate(ev):
  if e['kind']==50:revision+=1;stage_frame=e['frame']
  if e['kind'] in [64,3] and e['current_visible'] and (e['mission_stage']<=6 or e['mission_stage']==11):seen=e['frame']
  e.update(seq=i+1,stage_revision=revision,stage_frame=stage_frame,target_last_seen_frame=seen)
  if e['kind']==68:e.update(damage_before=1000.,damage_after=30.)
 r['events']=ev;r['native'].update(returned_frame=228,retreat_started=184,damage_count=6,damage_total=30.,shot_samples=6,rounds_consumed=6,last_ammo=0,engagement_initial_hp=1000.,damage_goal=30.,engage_limit=60)
 r['request']['mission'].update(engagement_policy='brief_raid_single_order_native_burst',damage_goal_cap=30.,engage_frames=60)
 a=admission.actor_admission(Memory(),0x2000);u=r['preflight']['selected']
 for record in [a,a['grounded_status']]:record.update(object_id=u['object_id'],address=u['address'],owner=r['preflight']['owner'],type_hash=u['type_hash'],frame=99,end_frame=99)
 a['state_snapshot'].update(update=u['ai_address'],update_backref=u['address'],sm_owner=u['address']);r['actor_admission']=a;r['actor_admission_helper_sha256']=strict.sha(P/'mission_actor_admission_v2.py')
 r.update(json.loads((D/'revision.json').read_text()));return r
def short_goal():
 r=fixture();r['events']=[e for e in r['events'] if e['kind'] not in [20,24,22,67] or e['kind'] in [20,24] and e['frame']==156 or e['kind']==22 and e['frame']==157]
 r['native'].update(damage_count=1,damage_total=5.,rounds_consumed=1,shot_samples=1,reload_samples=0,last_ammo=2,engagement_initial_hp=5.,damage_goal=1.,lethal_source_hits=1)
 for i,e in enumerate(r['events']):
  e['seq']=i+1
  if e['kind']==68:e.update(damage_before=5.,damage_after=1.)
  if e['kind'] in [20,24]:e.update(damage_before=5.,damage_after=0.)
 return r
def goal_and_safety():
 r=fixture();r['events']=[e for e in r['events'] if not(e['mission_stage']==6 and e['frame']>=178)]
 r['native'].update(damage_count=4,damage_total=20.,rounds_consumed=4,shot_samples=4,last_ammo=2,engagement_initial_hp=100.,damage_goal=20.,initial_hp=100.,reason_code=5)
 r['request']['mission']['retreat_hp_fraction']=.8
 for e in r['events']:
  if e['kind']==68:e.update(damage_before=100.,damage_after=20.)
  if e['kind'] in [20,24]:e['damage_before']-=900.;e['damage_after']-=900.
  if e['mission_stage']==6 and e['frame']==174:
   e.update(frame=182,tick=10920)
   if e['kind'] in [20,24]:e['health_observed_frame']=182
  if e['kind']==22 and e['frame']==175:e.update(frame=184,tick=11040,ammo_previous_frame=182,ammo_previous_tick=10920)
  if e['mission_stage'] in [7,8,9,10]:e.update(own_hp=80.,mission_reason=5)
 # Damage arrives after the 182 callback; the next callback observes own HP80,
 # takes the safety guard, and its pre-Stop own-weapon poll records that last shot.
 row=copy.deepcopy(next(e for e in r['events'] if e['kind']==3 and e['frame']==182));row.update(frame=184,tick=11040,own_hp=80.)
 at=next(i for i,e in enumerate(r['events']) if e['kind']==22 and e['frame']==184);r['events'].insert(at,row);seen=0
 for i,e in enumerate(r['events']):
  e['seq']=i+1
  if e['kind'] in [64,3] and e['current_visible'] and (e['mission_stage']<=6 or e['mission_stage']==11):seen=e['frame']
  e['target_last_seen_frame']=seen
 return r
class Mission7(unittest.TestCase):
 def test_goal_and_low_health_same_tick_preserves_safety_reason(self):
  r=goal_and_safety();a=runtime.qualify(r);self.assertTrue(a['runtime_goal_verified'],a['checks']);self.assertEqual(a['reason_code'],'low_hp');self.assertTrue(a['damage_goal_reached']);self.assertTrue(a['retreat_verified']);self.assertFalse(a['strict_burst_trace_verified'])
 def test_goal_counter_or_safety_reason_never_replaces_raw_goal(self):
  for change in ['flag','damage','health','reason']:
   r=goal_and_safety()
   if change=='flag':r['native']['engagement_goal_reached']=0
   if change=='damage':r['native']['damage_total']=15.
   if change=='health':next(e for e in r['events'] if e['kind']==50 and e['arg']==7)['own_hp']=95.
   if change=='reason':r['native']['reason_code']=10
   self.assertFalse(runtime.qualify(r)['runtime_goal_verified'],change)
 def test_true_subgoal_low_hp_exit_keeps_effect_and_release_but_fails(self):
  r=goal_and_safety();r['events']=[e for e in r['events'] if not(e['kind'] in [20,24] and e['frame']==182 or e['kind']==22 and e['frame']==184)]
  for i,e in enumerate(r['events']):e['seq']=i+1
  r['native'].update(damage_count=3,damage_total=15.,shot_samples=3,rounds_consumed=3,last_ammo=3,engagement_goal_reached=0)
  a=runtime.qualify(r);self.assertFalse(a['runtime_goal_verified']);self.assertTrue(a['effect_verified']);self.assertTrue(a['restoration_verified']);self.assertFalse(a['damage_goal_reached'])
 def test_goal_plus_same_tick_safety_does_not_complete_dead_actor(self):
  r=goal_and_safety();r['native'].update(phase=4,error=32,return_verified=0,returned_frame=0);self.assertFalse(runtime.qualify(r)['runtime_goal_verified'])
 def test_six_real_chains_reload_and_live_retreat_synthetic(self):
  a=strict.qualify(fixture());self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks']);self.assertEqual(a['source_damage_amount'],30);self.assertEqual(len(a['qualified_hits']),6);self.assertEqual(a['observed_rounds_consumed'],6);self.assertEqual(a['observed_reload_count'],1);self.assertTrue(a['long_retreat_verified'])
 def test_runtime_kill_does_not_claim_six_hit_source(self):
  r=short_goal();a=runtime.qualify(r);self.assertTrue(a['runtime_goal_verified'],a['checks']);self.assertFalse(a['strict_burst_trace_verified']);self.assertFalse(a['sustained_engagement_verified']);self.assertEqual(a['observed_lethal_hit_count'],1)
 def test_partial_timeout_releases_but_fails_goal(self):
  r=fixture();r['native'].update(reason_code=6,engagement_goal_reached=0);a=runtime.qualify(r);self.assertFalse(a['runtime_goal_verified']);self.assertTrue(a['restoration_verified'])
 def test_sixty_frame_limit_not_old_three_hundred(self):
  for value in [61,180,300]:
   r=fixture();r['request']['mission']['engage_frames']=value;r['native']['engage_limit']=value;self.assertFalse(runtime.qualify(r)['checks']['phase_limits'])
  r=fixture();next(e for e in r['events'] if e['kind']==30 and e['lease_stage']==7)['frame']=215;self.assertFalse(runtime.qualify(r)['checks']['normal_script_attack'])
 def test_no_v6_cap_or_profile_accepted(self):
  for key,value in [('damage_goal_cap',150.),('engagement_policy','bounded_single_order_native_burst')]:
   r=fixture();r['request']['mission'][key]=value;self.assertFalse(runtime.qualify(r)['checks']['engagement_policy_raw'])
 def test_header_damage_or_reload_never_replaces_raw(self):
  for kind in [20,24,22,67]:
   r=fixture();r['events'].remove(next(e for e in r['events'] if e['kind']==kind));self.assertFalse(runtime.qualify(r)['runtime_goal_verified'],kind)
 def test_inlease_override_retains_full_rejection(self):
  r=fixture();e=copy.deepcopy(next(e for e in r['events'] if e['mission_stage']==2 and e['kind']==3));e.update(kind=10,tag=0);at=next(i for i,x in enumerate(r['events']) if x['seq']==e['seq']);r['events'].insert(at,e)
  for i,e in enumerate(r['events']):e['seq']=i+1
  r['native']['native_move']=1;self.assertFalse(runtime.qualify(r)['checks']['no_native_override'])
 def test_no_return_and_death_never_complete(self):
  r=fixture();r['native'].update(return_verified=0,returned_frame=0,phase=4,error=32);a=runtime.qualify(r);self.assertFalse(a['runtime_goal_verified']);self.assertFalse(a['restoration_verified'])
 def test_initial_hidden_memory_not_refreshed_from_hidden_coordinates(self):
  r=fixture();e=next(x for x in r['events'] if x['mission_stage']==2 and x['kind']==3);e.update(current_visible=0,visible_target_xyz=[0.,0.,0.]);e['remembered_target_xyz']=[999.,0.,210.];self.assertFalse(runtime.qualify(r)['navigation_memory']['verified'])
 def test_body_identity_lethal_guards_unchanged(self):
  for k in ['health_post_identity','health_post_id','health_body','health_observed_frame']:
   r=short_goal();next(e for e in r['events'] if e['kind']==20)[k]=0;self.assertFalse(runtime.qualify(r)['runtime_goal_verified'],k)
 def test_layout_namespace_and_fourteen_pristine_exe_entries(self):
  s=importlib.util.spec_from_file_location('mct7_test_runtime',D/'lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(event=852,tactical=3490916,events=1124,unused1=0,unused2=0));self.assertEqual(c.sizeof(m.Event),852);self.assertEqual(c.sizeof(m.Tactical),3490916)
  import mission_v7_readonly_disposal as reader
  entries=reader.trusted_entries(fixture());self.assertEqual(len({e['address'] for e in entries}),14)
  for e in entries:self.assertEqual(reader.pe_bytes('E:/RedRar3/Data/RA3_1.12.game',e['address'],len(bytes.fromhex(e['expected']))).hex(),e['expected'])
  with self.assertRaises(ValueError):reader.profile(old_fixture())
 def test_static_protocol_scope_and_original_frozen(self):
  cpp=(D/'lease.cpp').read_text();self.assertIn('version!=15',cpp);self.assertIn('word(p->unit+0x374)==p->update',cpp);self.assertNotIn('unit+0x378',cpp);self.assertIn('id==10&&word(state)==0xc548c0',cpp);self.assertEqual(cpp.count('if(!tag&&actor_lease_active())'),5)
  rev=json.loads((P/'mission-combat-v6/revision.json').read_text())
  for key,name in [('native_binary_sha256','bin/TacticalMissionCombat6.dll'),('wrapper_sha256','lease.py'),('native_source_sha256','lease.cpp'),('native_shared_sha256','shared.h')]:self.assertEqual(strict.sha(P/'mission-combat-v6'/name),rev[key])
 def test_contract_fixed_profile_and_deadline(self):
  s=importlib.util.spec_from_file_location('mct7_contract_test',D/'mission_contract.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);r=fixture();pre=r['preflight'];pre['frame']=99
  a=m.validate_mission({'schema_version':1},pre,None);self.assertEqual(a['engage_frames'],60);self.assertEqual(a['damage_goal_cap'],30);self.assertEqual(a['retreat_hp_fraction'],.8)
  for change in [dict(engage_frames=180),dict(damage_goal_cap=150),dict(engage_frames=True),dict(expires_frame=4600),dict(retreat_hp_fraction=float('nan'))]:
   with self.assertRaises(ValueError):m.validate_mission(dict(schema_version=1,**change),pre,None)
 def test_no_source_reload_only_before_or_after_all_hits(self):
  r=fixture();a=strict.qualify(r);self.assertTrue(a['checks']['refill_between_source_hits'])
  rows=[e for e in r['events'] if e['kind']==67];rows[0]['seq']=1;self.assertFalse(strict.qualify(r)['checks']['refill_between_source_hits'])
 def test_real_old_ninety_damage_casualty_stays_failure(self):
  path=P.parent/'acceptance/runs/20261025-142348-commander/continuous-paid-v6-01-combat-v6.json';a=runtime.qualify(json.loads(path.read_text(encoding='utf-8-sig')));self.assertFalse(a['runtime_goal_verified']);self.assertEqual(a['status'],'not_passed')
if __name__=='__main__':unittest.main()
