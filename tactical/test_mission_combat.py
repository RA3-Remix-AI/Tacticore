"""Offline synthetic protocol fixtures. Reuses a real packet, never field evidence."""
import copy,ctypes as c,hashlib,importlib.util,json,math,subprocess,unittest
from pathlib import Path
import mission_combat_qualification as q
HERE=Path(__file__).resolve().parent;D=HERE/'mission-combat'
def runtime():
 sp=importlib.util.spec_from_file_location('test_mission_backend',D/'lease.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def fixture():
 r=json.loads((HERE/'../acceptance/runs/20261025-030636-commander/combo-economy01.json').read_text(encoding='utf-8'));base=copy.deepcopy(r['events'][0]);damage=copy.deepcopy(next(x for x in r['events'] if x['kind']==20));commit=copy.deepcopy(next(x for x in r['events'] if x['kind']==24));ammo=copy.deepcopy(next(x for x in r['events'] if x['kind']==22));ev=[];pos=[0.,0.,210.];goal=[0.,0.,210.];stage=revision=stageframe=mi=0
 n=r['native'];n.update(issued_frame=100,returned_frame=195,attack_issued_frame=149,mission_deadline_frame=4599,approach_limit=2100,engage_limit=300,retreat_limit=1800,approach_started=105,engage_started=149,retreat_started=151,reason_code=1,mission_stage=10,move_calls=4,normal_move_facade_calls=4,normal_move_private_calls=4,approach_move_calls=2,retreat_move_calls=2,stop_calls=5,private_stop_calls=5,total_private_stops=5,restore_mask=16383,retreat_goal=[0.,0.,210.],retreat_arrival_samples=3,weapon_ammo=3,last_ammo=2,damage_count=1,damage_total=5.,commit_own_calls=1,shot_samples=1,toggle_calls=0,toggle_hook_calls=0,prepare_reconstituted_stops=0,initial_weapon_asset=q.AK,prepare_gate_frame=146,native_attack=1)
 r['preflight']['frame']=99;r['preflight']['selected']['xyz']=[0.,0.,210.];r['request'].update(target=[600.,0.,210.],mission_protocol='continuous_tactical_v1',expires_frame=4599,mission=dict(schema_version=1,expires_frame=4599,approach_frames=2100,engage_frames=300,retreat_frames=1800,retreat_point=dict(xyz=[0.,0.,210.],observed_frame=99,source='own_actor_history',anchor_object_id=r['preflight']['selected']['object_id'])));r['weapon_asset_binding'].update(reported_entry=hex(n['weapon_entry']),reported_template=hex(n['weapon_template']))
 def add(kind,frame,lease=0,tag=0,arg=0,template=None,**kw):
  e=copy.deepcopy(template or base);e.update(kind=kind,frame=frame,tick=frame*60,lease_stage=lease,tag=tag,arg=arg,mission_stage=stage,stage_revision=revision,stage_frame=stageframe,mission_reason=1 if stage>=7 else 0,move_index=mi,x=pos[0],y=pos[1],z=pos[2],command_xyz=list(goal),argument_path=0,argument_limit=3.402823466e38,current_visible=1,visible_target_xyz=[600.,0.,210.],own_hp=100.,source=1,state_id=16,sm_flags=0,path=0,holder=0,requested=[0.,0.,0.],effective=[0.,0.,0.],active_weapon_asset=q.AK,active_weapon_entry=n['weapon_entry'],active_weapon_ammo=3,status84=0);e.update(kw);ev.append(e);return e
 def change(value,frame,lease=0):
  nonlocal stage,revision,stageframe
  stage=value;revision+=1;stageframe=frame;add(50,frame,lease,arg=value)
 def stop(lease,frame,gate):
  for k in [30,32,33,31,36]:add(k,frame,lease,4,1,caller=0x787791 if k in [32,33] else 0)
  for f in [frame+1,frame+2,frame+3]:add(3,f,lease)
  add(gate,frame+3,lease)
 def move(frame,destination):
  nonlocal mi,goal
  mi+=1;goal=list(destination)
  for k in [54,52,53,55]:add(k,frame,5 if stage==2 else 8,6,1)
 def arrive(frames,positions):
  nonlocal pos
  for f,x in zip(frames,positions):pos=[float(x),0.,210.];add(3,f,5 if stage==2 else 8)
  add(57,frames[-1],5 if stage==2 else 8)
 manager=int(r['preflight']['ai'],0)+0x104
 add(14,100,tag=1,arg=0);add(18,100,tag=1,arg=manager,caller=0x838877);add(19,100,tag=1,arg=manager);add(15,100,tag=1,arg=0);add(1,100,tag=1)
 change(1,100);stop(0,100,37);change(2,105)
 move(106,[250.,0.,210.]);arrive([120,121,122],[240,245,250]);move(124,[500.,0.,210.]);pos=[500.,0.,210.];add(3,142,5);change(3,143);stop(6,143,58);add(42,146,6);change(5,146);stop(4,146,43);change(6,149,1)
 for k in [34,12,13,35]:add(k,149,1,2,r['request']['target_object_id'],arg_shots=0x7fffffff,arg_source=1)
 add(24,150,1,template=commit);add(20,150,1,template=damage);add(22,151,1,template=ammo);change(7,151);stop(7,151,59);change(8,154,8)
 move(155,[250.,0.,210.]);arrive([170,171,172],[260,255,250]);move(174,[0.,0.,210.]);arrive([190,191,192],[10,5,0]);add(60,192,8);change(9,192);stop(2,192,38)
 add(14,195,tag=3,arg=1);add(16,195,tag=3,arg=manager,caller=0x83885b);add(17,195,tag=3,arg=manager);add(15,195,tag=3,arg=1);add(5,195,tag=3);change(10,195);add(12,220,tag=0);add(4,225)
 for i,e in enumerate(ev):e['seq']=i+1
 r['events']=ev;r.update(json.loads((D/'revision.json').read_text()));r['status']='finished';r['host_exit']=0;r['native_launch_intent_persisted']=True
 return r
class MissionCombatTests(unittest.TestCase):
 def test_layout_and_real_ctypes_arrays(self):
  m=runtime();layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(event=c.sizeof(m.Event),tactical=c.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0));e=m.Event();e.requested[0]=float('nan');value=m.event_record(e);json.dumps(value,allow_nan=False);self.assertIsNone(value['requested'][0])
 def test_full_synthetic_protocol(self):
  a=q.qualify(fixture());self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks']);self.assertTrue(a['long_approach_verified']);self.assertTrue(a['long_retreat_verified'])
 def test_no_damage_never_completes(self):
  r=fixture();r['events']=[e for e in r['events'] if e['kind'] not in [20,24,22]];self.assertEqual(q.qualify(r)['status'],'not_passed')
 def test_source_packet_not_other_actor(self):
  r=fixture();next(e for e in r['events'] if e['kind']==20)['stack_words'][34]=999;self.assertFalse(q.qualify(r)['effect_verified'])
 def test_not_returned_is_not_released(self):
  r=fixture();r['native']['return_verified']=0;self.assertFalse(q.control_release(r)['restoration_verified'])
 def test_retreat_scalar_does_not_replace_geometry(self):
  r=fixture()
  for e in r['events']:
   if e.get('mission_stage')==8:e['x']=400
  self.assertFalse(q.qualify(r)['retreat_verified'])
 def test_repeated_same_frame_does_not_arrive(self):
  r=fixture()
  for e in r['events']:
   if e.get('kind')==3 and e.get('mission_stage')==8 and e['move_index']==4:e.update(frame=192,tick=192*60)
  self.assertFalse(q.qualify(r)['retreat_verified'])
 def test_late_ammo_does_not_qualify_effect(self):
  r=fixture();next(e for e in r['events'] if e['kind']==22)['frame']+=10;self.assertFalse(q.qualify(r)['effect_verified'])
 def test_fov_confirmation_required(self):
  r=fixture();next(e for e in r['events'] if e['kind']==50 and e['arg']==3)['current_visible']=0;self.assertFalse(q.qualify(r)['approach_verified'])
 def test_progress_is_stable_at_published_event_revision(self):
  r=fixture();a=q.progress(r,'task');r['native'].update(own_hp=1,damage_total=100,stage_revision=999,approach_distance=0);self.assertEqual(a,q.progress(r,'task'));self.assertEqual(a['revision'],r['events'][-1]['seq'])
 def test_queued_has_no_progress(self):
  r=fixture();r['native']['issued_frame']=0;self.assertIsNone(q.progress(r,'task'))
 def test_deadline_not_extended_by_receipt(self):
  r=fixture();r['native']['mission_deadline_frame']+=1;self.assertFalse(q.qualify(r)['checks']['mission_deadline'])
 def test_native_override_before_handoff_rejected_post_allowed(self):
  r=fixture();self.assertTrue(q.qualify(r)['checks']['no_native_override']);r['events'][-2]['seq']=20;self.assertFalse(q.qualify(r)['checks']['no_native_override'])
if __name__=='__main__':unittest.main()
