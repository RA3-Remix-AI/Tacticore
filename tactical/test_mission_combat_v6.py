"""Offline MCT6 raw evidence, independent of the game and endpoint."""
import copy,ctypes as c,hashlib,importlib.util,json,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from test_mission_combat_v4 import fixture as old_fixture
from test_mission_actor_admission import Memory as AdmissionMemory
import mission_actor_admission as admission
import mission_combat_v6_qualification as q
HERE=Path(__file__).resolve().parent;D=HERE/'mission-combat-v6'

def fixture():
 r=old_fixture();old=r['events'];ev=[]
 def block(stage,delta=0,revised=None,lease=None,omit=()):
  rows=[]
  for source in old:
   if source['mission_stage']!=stage or source['kind'] in omit:continue
   e=copy.deepcopy(source);e['frame']+=delta;e['tick']=e['frame']*60;e['stage_frame']+=delta
   if revised is not None:
    e['mission_stage']=revised
    if e['kind']==50:e['arg']=revised
   if lease is not None:e['lease_stage']=lease
   rows.append(e)
  return rows
 ev+=block(0)+block(1)+block(3,-38,omit=(42,))+block(5,-38)
 # The optional direct-AK preparation gate is published before leaving stage3.
 e=copy.deepcopy(next(x for x in old if x['kind']==42));e.update(frame=108,tick=6480,stage_frame=105);at=next(i for i,x in enumerate(ev) if x['mission_stage']==5);ev.insert(at,e)
 ev+=block(2,7)
 early=copy.deepcopy(ev[-1]);early.update(kind=3,frame=150,tick=9000,mission_stage=2);ev.append(early)
 ready=block(3,7,revised=11,lease=9,omit=(42,))
 for e in ready:
  if e['kind']==58:e['kind']=66
 ev+=ready
 orders=block(6,5,omit=(20,24,22));ev.append(orders.pop(0))
 e=copy.deepcopy(ev[-1]);e.update(kind=68,damage_before=100.,damage_after=20.,damage_reported=0.);ev.append(e);ev+=orders
 damage=next(x for x in old if x['kind']==20);commit=next(x for x in old if x['kind']==24);ammo=next(x for x in old if x['kind']==22);target=r['private_target'];body=int(target['body'],0) if isinstance(target['body'],str) else target['body'];actor=int(target['address'],0) if isinstance(target['address'],str) else target['address']
 for number,frame in enumerate([156,160,164,174]):
  sample=copy.deepcopy(damage);sample.update(kind=3,frame=frame,tick=frame*60);ev.append(sample)
  for original in [commit,damage]:
   e=copy.deepcopy(original);e.update(frame=frame,tick=frame*60,damage_before=100.-number*5,damage_after=95.-number*5,damage_reported=5.,health_pre_visible=1,health_post_identity=1,health_observed_frame=frame,health_body=body,health_actor=actor,health_post_id=target['object_id'],health_post_owner=target['owner'],health_post_template=target['template'],health_post_vtable=0xc37fe8);ev.append(e)
  e=copy.deepcopy(ammo);before=3-number if number<3 else 3;e.update(frame=frame+1,tick=(frame+1)*60,ammo_previous_frame=frame-1,ammo_previous_tick=(frame-1)*60,damage_before=float(before),damage_after=float(before-1),active_weapon_ammo=before-1);ev.append(e)
  if number==2:
   e=copy.deepcopy(ammo);e.update(kind=67,frame=170,tick=10200,ammo_previous_frame=169,ammo_previous_tick=10140,damage_before=0.,damage_after=3.,active_weapon_ammo=3);ev.append(e)
 ev+=block(7,25)+block(8,25)+block(9,25)+block(10,25)
 first=copy.deepcopy(ev[0]);first.update(kind=64);ev.insert(0,first)
 revision=0;stage_frame=0;seen=0
 for i,e in enumerate(ev):
  if e['kind']==50:revision+=1;stage_frame=e['frame']
  if e['kind'] in [64,3] and e['current_visible'] and (e['mission_stage']<=6 or e['mission_stage']==11):seen=e['frame']
  e.update(seq=i+1,stage_revision=revision,stage_frame=stage_frame,target_id=r['request']['target_object_id'],target_last_seen_frame=seen,memory_wait_started=0,remembered_target_xyz=[600.,0.,210.])
 r['events']=ev;r['native'].update(returned_frame=220,attack_issued_frame=154,engage_started=154,approach_started=112,retreat_started=176,stop_calls=6,private_stop_calls=6,total_private_stops=6,prepare_gate_frame=108,damage_count=4,damage_total=20.,shot_samples=4,rounds_consumed=4,reload_samples=1,last_ammo=2,weapon_binding_fail=0,engagement_initial_hp=100.,damage_goal=20.,engagement_goal_reached=1,lethal_source_hits=0)
 r['request']['mission'].update(engagement_policy='bounded_single_order_native_burst',damage_goal_fraction=.2,damage_goal_cap=150.)
 a=admission.actor_admission(AdmissionMemory(),0x2000);u=r['preflight']['selected']
 for record in [a,a['grounded_status']]:record.update(object_id=u['object_id'],address=u['address'],owner=r['preflight']['owner'],type_hash=u['type_hash'],frame=99,end_frame=99)
 a['state_snapshot'].update(update=u['ai_address'],update_backref=u['address'],sm_owner=u['address']);r['actor_admission']=a;r['actor_admission_helper_sha256']=hashlib.sha256((HERE/'mission_actor_admission.py').read_bytes()).hexdigest()
 r.update(json.loads((D/'revision.json').read_text()));return r

class Mission6Tests(unittest.TestCase):
 def test_full_synthetic_raw_burst_reload_retreat(self):
  a=q.qualify(fixture());self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks']);self.assertTrue(a['sustained_engagement_verified']);self.assertTrue(a['damage_goal_reached']);self.assertEqual(a['observed_reload_count'],1);self.assertEqual(a['observed_rounds_consumed'],4);self.assertEqual(len(a['qualified_hits']),4)
 def test_compiled_layout_and_all_new_ctypes_fields(self):
  s=importlib.util.spec_from_file_location('mct6_layout_test',D/'lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(event=c.sizeof(m.Event),tactical=c.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0));e=m.Event();e.requested[0]=float('nan');e.health_post_identity=1;record=m.event_record(e);json.dumps(record,allow_nan=False);self.assertIsNone(record['requested'][0]);self.assertEqual(record['health_post_identity'],1)
 def test_normal_reload_is_required_raw_chain_not_header_counter(self):
  for change in ['missing','partial_refill','wrong_asset','wrong_before','wrong_last']:
   r=fixture();e=next(x for x in r['events'] if x['kind']==67)
   if change=='missing':r['events'].remove(e)
   elif change=='partial_refill':e['damage_after']=2.
   elif change=='wrong_asset':e['active_weapon_asset']=0x41872ecc
   elif change=='wrong_before':e['damage_before']=1.
   else:r['native']['last_ammo']=0
   self.assertFalse(q.qualify(r)['checks']['same_entry_ammo'],change)
 def test_only_damage_goal_counter_does_not_establish_success(self):
  r=fixture();r['events']=[e for e in r['events'] if e['kind'] not in [20,24]];a=q.qualify(r);self.assertFalse(a['damage_goal_reached']);self.assertFalse(a['sustained_engagement_verified']);self.assertTrue(a['engagement_partial']);self.assertEqual(a['status'],'not_passed')
 def test_post_lethal_same_body_packet_is_accepted_without_hidden_refresh(self):
  r=fixture();rows=[e for e in r['events'] if e['kind'] in [20,24]]
  for e in rows[-2:]:e.update(damage_before=4.,damage_after=-1.)
  a=q.qualify(r);self.assertEqual(len(a['qualified_hits']),4);self.assertEqual(a['observed_lethal_hit_count'],1);self.assertEqual(a['qualified_hits'][-1]['effective_hp_loss'],4.)
 def test_lethal_body_reuse_missing_visibility_and_frame_change_fail(self):
  for field,value in [('health_post_identity',0),('health_pre_visible',0),('health_body',123),('health_observed_frame',999),('health_post_id',999),('health_post_owner',999),('health_post_template',999),('health_post_vtable',999)]:
   r=fixture();e=[x for x in r['events'] if x['kind']==20][-1];e[field]=value;self.assertFalse(q.qualify(r)['effect_verified'],field)
 def test_ammo_poll_must_contain_actual_damage_time(self):
  r=fixture();next(x for x in r['events'] if x['kind']==22)['ammo_previous_tick']+=180;self.assertFalse(q.qualify(r)['effect_verified'])
 def test_early_preparation_never_regresses_public_phase(self):
  r=fixture();stages=[]
  for i in range(1,len(r['events'])+1):
   x=dict(r,events=r['events'][:i]);v=q.progress(x,'task')
   if v:stages.append(v['stage'])
  order={'approach':0,'prepare':1,'engage':2,'retreat':3,'restored':4};self.assertEqual([order[x] for x in stages],sorted(order[x] for x in stages))
 def test_partial_exit_can_release_without_completing(self):
  r=fixture();r['native'].update(reason_code=5,engagement_goal_reached=0);r['events']=[e for e in r['events'] if not(e['kind'] in [20,24] and e['frame']>=160)];a=q.qualify(r);self.assertEqual(a['status'],'not_passed');self.assertTrue(a['restoration_verified']);self.assertTrue(a['engagement_partial'])
 def test_damage_cannot_precede_unique_attack_order(self):
  r=fixture();e=next(x for x in r['events'] if x['kind']==20);e['seq']=1;self.assertFalse(q.qualify(r)['effect_verified'])
 def test_no_old_scope_or_old_inc_mutation(self):
  m=json.loads((HERE/'mission-combat-v5/revision.json').read_text());self.assertEqual(hashlib.sha256((HERE/'mission-combat-v5/mission_tick.inc').read_bytes()).hexdigest(),m['native_includes_sha256']['mission_tick.inc']);code=(D/'lease.cpp').read_text();self.assertIn('word(p->unit+0x374)==p->update',code);self.assertNotIn('word(p->unit+0x378)',code);self.assertIn('version!=14',code);self.assertEqual(code.count('if(!tag&&actor_lease_active())'),5)
 def test_same_frame_two_hits_are_not_sustained(self):
  r=fixture();a=q.qualify(r);hits=copy.deepcopy(a['qualified_hits'])
  for h in hits:h['body_frame']=156
  orders=[e for e in r['events'] if e['kind'] in [34,12,13,35] and e['tag']==2];post=[e for e in r['events'] if e['kind']==30 and e['lease_stage']==7];p=q.engagement_policy(r,hits,orders,post,True)
  self.assertFalse(p['sustained_engagement_verified']);self.assertEqual(p['attributed_hit_span_frames'],0);self.assertEqual(p['engagement_frames'],22)
 def test_clamped_overkill_without_matching_packet_remains_unknown(self):
  r=fixture()
  for e in [x for x in r['events'] if x['kind'] in [20,24]][-2:]:e.update(damage_before=4.,damage_after=0.)
  a=q.qualify(r);self.assertFalse(a['effect_verified']);self.assertEqual(len(a['qualified_hits']),3)
 def test_policy_goal_uses_visible_entry_not_header_only(self):
  r=fixture();r['native'].update(damage_goal=5.,engagement_initial_hp=25.);self.assertFalse(q.qualify(r)['checks']['engagement_policy_raw'])
  r=fixture();next(x for x in r['events'] if x['kind']==68)['current_visible']=0;self.assertFalse(q.qualify(r)['checks']['engagement_policy_raw'])
 def test_reload_and_round_counts_cannot_be_forged(self):
  for key,value in [('reload_samples',7),('rounds_consumed',99),('weapon_binding_fail',1)]:
   r=fixture();r['native'][key]=value;self.assertFalse(q.qualify(r)['checks']['same_entry_ammo'],key)
 def test_deadline_and_inlease_override_are_still_independent(self):
  r=fixture();r['native']['mission_deadline_frame']+=1;self.assertFalse(q.qualify(r)['checks']['mission_deadline'])
  r=fixture();at=next(i for i,e in enumerate(r['events']) if e['mission_stage']==2 and e['kind']==3);e=copy.deepcopy(r['events'][at]);e.update(kind=10,tag=0);r['events'].insert(at,e)
  for i,e in enumerate(r['events']):e['seq']=i+1
  r['native']['native_move']=1;a=q.qualify(r);self.assertFalse(a['checks']['no_native_override']);self.assertTrue(a['checks']['native_counter_lease_scope'])
 def test_new_reader_exact_fourteen_pristine_entries_and_old_profile_rejected(self):
  import mission_v6_readonly_disposal as reader
  r=fixture();entries=reader.trusted_entries(r);self.assertEqual(len({x['address'] for x in entries}),14)
  source=Path('E:/RedRar3/Data/RA3_1.12.game');self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),q.EXE)
  for row in entries:self.assertEqual(reader.pe_bytes(source,row['address'],len(bytes.fromhex(row['expected']))).hex(),row['expected'])
  r['native_binary_sha256']=json.loads((HERE/'mission-combat-v5/revision.json').read_text())['native_binary_sha256']
  with self.assertRaises(ValueError):reader.profile(r)

if __name__=='__main__':unittest.main()
