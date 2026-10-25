"""Synthetic full-target path protocol. Not live capability evidence."""
import copy,ctypes as c,importlib.util,json,subprocess,unittest
from pathlib import Path
from test_mission_combat import fixture as v1_fixture
import mission_combat_v2_qualification as q
HERE=Path(__file__).resolve().parent;D=HERE/'mission-combat-v2'
def fixture():
 r=v1_fixture();events=[]
 for e in r['events']:
  if e['mission_stage']==2 and (e['kind']==57 or e['kind'] in [54,52,53,55] and e['move_index']==2):continue
  if e['mission_stage']==2:
   e['move_index']=1;e['command_xyz']=[600.,0.,210.]
  elif e['move_index']>=2:e['move_index']-=1
  events.append(e)
  if e['kind']==3 and e['mission_stage']==2 and e['frame']==122:events.append(dict(e,kind=61,arg=1))
 for i,e in enumerate(events):e['seq']=i+1
 r['events']=events;r['native'].update(move_calls=3,normal_move_facade_calls=3,normal_move_private_calls=3,approach_move_calls=1,retreat_move_calls=2,checkpoint_count=2,checkpoints=[[0.,0.,210.],[250.,0.,210.]])
 r.update(json.loads((D/'revision.json').read_text()));return r
class MissionCombat2Tests(unittest.TestCase):
 def test_real_compiled_layout(self):
  s=importlib.util.spec_from_file_location('mct2_layout',D/'lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(event=c.sizeof(m.Event),tactical=c.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0));self.assertEqual(len(m.Tactical().checkpoint),32)
 def test_full_target_synthetic_protocol(self):
  result=q.qualify(fixture());self.assertEqual(result['status'],'continuous_ak_combat_mission_verified',result['checks']);self.assertTrue(result['long_approach_verified'])
 def test_linear_midpoint_cannot_claim_full_target_path(self):
  r=fixture();next(e for e in r['events'] if e['kind']==54 and e['mission_stage']==2)['command_xyz']=[250.,0.,210.];self.assertFalse(q.qualify(r)['checks']['full_visible_target_path_requests'])
 def test_checkpoint_needs_actual_position_event(self):
  r=fixture();r['native']['checkpoints'][1][0]=270.;self.assertFalse(q.qualify(r)['checks']['actual_own_checkpoints'])
 def test_checkpoint_count_cannot_replace_event(self):
  r=fixture();r['events']=[e for e in r['events'] if e['kind']!=61];self.assertFalse(q.qualify(r)['checks']['actual_own_checkpoints'])
 def test_final_three_samples_are_frozen_goal_not_near_checkpoint(self):
  r=fixture();rows=[e for e in r['events'] if e['kind']==3 and e['mission_stage']==8 and e['move_index']==3]
  for e,x in zip(rows,[16.1285,12.7953,6.1287]):e['x']=x
  r['native']['retreat_arrival_samples']=3;self.assertFalse(q.qualify(r)['retreat_verified'])
 def test_v1_source_never_grants_v2(self):
  result=q.qualify(v1_fixture());self.assertEqual(result['status'],'not_passed');self.assertFalse(result['checks']['certified_revision'])
 def test_native_no_linear_endpoint_or_short_approach_timeout(self):
  source=(D/'mission_tick.inc').read_text();self.assertIn('memcpy(p->waypoint,destination,12)',source);self.assertNotIn('d>250?250/d',source);part=source.split('if(p->mission_stage==2){',1)[1].split('if(p->mission_stage==3)',1)[0];self.assertNotIn('move_started>=450',part);self.assertIn('event(61,p->checkpoint_count-1)',part);self.assertNotIn('move_started>=450',source)
if __name__=='__main__':unittest.main()
