"""Synthetic direct-home protocol. All fixtures are software tests only."""
import ctypes as c,importlib.util,json,subprocess,unittest
from pathlib import Path
from test_mission_combat_v2 import fixture as v2_fixture
import mission_combat_v3_qualification as q
HERE=Path(__file__).resolve().parent;D=HERE/'mission-combat-v3'
def fixture():
 r=v2_fixture();events=[]
 for e in r['events']:
  if e['mission_stage']==8:
   if e['kind']==57 or e['kind'] in [54,52,53,55] and e['move_index']==3:continue
   e['move_index']=2;e['command_xyz']=[0.,0.,210.]
  elif e['move_index']>=3:e['move_index']-=1
  events.append(e)
 for i,e in enumerate(events):e['seq']=i+1
 r['request']['mission']['origin_policy']='explicit_fixed_point'
 r['events']=events;r['native'].update(move_calls=2,normal_move_facade_calls=2,normal_move_private_calls=2,retreat_move_calls=1,retreat_replans=0,retreat_mode=0,fallback_checkpoint_index=0);r.update(json.loads((D/'revision.json').read_text()));return r
def fallback_fixture():
 r=fixture();prefix=[e for e in r['events'] if e['mission_stage']<8 or e['mission_stage']==8 and (e['kind']==50 or e['kind'] in [54,52,53,55])];template=next(e for e in r['events'] if e['kind']==3 and e['mission_stage']==8);extra=[]
 def add(kind,frame,x,index=2,arg=0,goal=None,tag=0):
  e=dict(template,kind=kind,frame=frame,tick=frame*60,x=float(x),y=0.,z=210.,arg=arg,move_index=index,tag=tag,command_xyz=goal or [0.,0.,210.]);extra.append(e)
 for f in range(156,406):add(3,f,500)
 add(62,405,500,arg=1)
 for k in [54,52,53,55]:add(k,405,500,index=3,arg=1,goal=[250.,0.,210.],tag=6)
 for f in range(406,418):add(3,f,500-(f-405)*10,index=3,goal=[250.,0.,210.])
 add(63,417,380,index=3,arg=1,goal=[250.,0.,210.])
 for k in [54,52,53,55]:add(k,417,380,index=4,arg=1,tag=6)
 for f,x in [(430,10),(431,5),(432,0)]:add(3,f,x,index=4)
 add(60,432,0,index=4)
 tail=[]
 for e in r['events']:
  if e['mission_stage']<9:continue
  e=dict(e,frame=e['frame']+240,tick=(e['frame']+240)*60,stage_frame=e['stage_frame']+240,move_index=4,x=0.,y=0.,z=210.);tail.append(e)
 r['events']=prefix+extra+tail
 for i,e in enumerate(r['events']):e['seq']=i+1
 r['native'].update(move_calls=4,normal_move_facade_calls=4,normal_move_private_calls=4,retreat_move_calls=3,retreat_replans=2,retreat_mode=0,fallback_checkpoint_index=1,returned_frame=435);return r
class MissionCombat3Tests(unittest.TestCase):
 def test_compiled_abi(self):
  sp=importlib.util.spec_from_file_location('mct3_layout',D/'lease.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(event=c.sizeof(m.Event),tactical=c.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0))
 def test_direct_goal_has_no_false_need_for_waypoint57(self):
  r=fixture();self.assertFalse(any(e['kind']==57 for e in r['events']));a=q.qualify(r);self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks']);self.assertFalse(a['fallback_branch_observed']);self.assertFalse(a['fallback_field_effect_verified'])
 def test_no_final_actual_arrival_stays_failed(self):
  r=fixture()
  for e in r['events']:
   if e['kind']==3 and e['mission_stage']==8 and e['frame']>=190:e['x']=22.
  self.assertFalse(q.qualify(r)['retreat_verified'])
 def test_v2_intermediate_policy_cannot_claim_direct_goal(self):
  r=v2_fixture();r.update(json.loads((D/'revision.json').read_text()));r['native'].update(retreat_replans=0,retreat_mode=0);self.assertFalse(q.qualify(r)['checks']['bounded_direct_goal_fallback_policy'])
 def test_fallback_counter_without_published_replan_rejected(self):
  r=fixture();r['native']['retreat_replans']=2;self.assertFalse(q.qualify(r)['checks']['bounded_direct_goal_fallback_policy'])
 def test_software_bounded_fallback_sequence(self):
  r=fallback_fixture();a=q.qualify(r);self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks']);self.assertTrue(a['fallback_branch_observed'])
 def test_no_motion_window_not_scalar_counter(self):
  r=fallback_fixture();next(e for e in r['events'] if e['kind']==3 and e['frame']==350)['x']=700.;self.assertFalse(q.qualify(r)['checks']['bounded_direct_goal_fallback_policy'])
 def test_resume_needs_actual_motion_or_verified_checkpoint(self):
  r=fallback_fixture();next(e for e in r['events'] if e['kind']==63)['x']=490.;self.assertFalse(q.qualify(r)['checks']['bounded_direct_goal_fallback_policy'])
 def test_fallback_cannot_pick_arbitrary_position(self):
  r=fallback_fixture();next(e for e in r['events'] if e['kind']==62)['arg']=99;self.assertFalse(q.qualify(r)['checks']['bounded_direct_goal_fallback_policy'])
 def test_native_route_has_two_replans_and_three_commands_bound(self):
  s=(D/'mission_tick.inc').read_text();self.assertIn('p->retreat_replans>=2||p->retreat_move_calls>=3',s);self.assertIn('p->retreat_mode==0&&p->retreat_replans==0',s);self.assertIn('waypoint_to(p->retreat_goal,true)',s);self.assertNotIn('waypoint_to(goal,true)',s)
if __name__=='__main__':unittest.main()
