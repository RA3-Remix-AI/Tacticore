"""Memory navigation protocol only. Synthetic evidence is never field evidence."""
import copy,ctypes as c,importlib.util,json,subprocess,unittest
from pathlib import Path
import mission_combat_v5_qualification as q
HERE=Path(__file__).resolve().parent;D=HERE/'mission-combat-v5'

def fixture():
 def e(seq,frame,kind=3,visible=0,seen=100,point=None,stage=2):
  point=point or [600.,0.,210.]
  return dict(seq=seq,frame=frame,kind=kind,mission_stage=stage,target_id=77,current_visible=visible,target_last_seen_frame=seen,remembered_target_xyz=point,visible_target_xyz=point if visible else [0.,0.,0.],command_xyz=point,x=100.,y=0.,z=210.,memory_wait_started=0)
 return dict(request=dict(target_object_id=77),events=[e(1,100,64,1,100,stage=0),e(2,110,3,0),e(3,111,54,0),e(4,400,3,0),e(5,500,3,1,500),e(6,500,50,1,500,stage=3),e(7,505,3,1,505,stage=6),e(8,505,34,1,505,stage=6)])

class MemoryMissionTests(unittest.TestCase):
 def test_full_synthetic_protocol_still_requires_and_accepts_effect_retreat(self):
  from test_mission_combat_v4 import fixture as previous
  r=previous();r.update(json.loads((D/'revision.json').read_text()));events=r['events'];first=copy.deepcopy(events[0]);first.update(kind=64,mission_stage=0);rows=[first]
  for e in events:
   if e.get('kind')==50 and e.get('arg')==3:
    sample=copy.deepcopy(e);sample.update(kind=3,mission_stage=2);rows.append(sample)
   rows.append(e)
  seen=0
  for i,e in enumerate(rows):
   if e['kind'] in [64,3] and e.get('current_visible') and e.get('mission_stage')<=6:seen=e['frame']
   e.update(seq=i+1,target_id=r['request']['target_object_id'],target_last_seen_frame=seen,memory_wait_started=0,remembered_target_xyz=[600.,0.,210.])
  r['events']=rows;a=q.qualify(r);self.assertEqual(a['status'],'continuous_ak_combat_mission_verified',a['checks']);self.assertFalse(a['navigation_memory']['hidden_navigation_observed']);self.assertFalse(a['economic_disruption_verified'])
 def test_visible_memory_hidden_move_reacquisition(self):
  r=fixture();r['events'][5]['arg']=3;a=q.memory_checks(r);self.assertTrue(a['verified'],a);self.assertTrue(a['hidden_navigation_observed']);self.assertTrue(a['reacquisition_observed'])
 def test_hidden_coordinates_cannot_be_refreshed(self):
  for field,value in [('remembered_target_xyz',[601.,0.,210.]),('target_last_seen_frame',110),('visible_target_xyz',[600.,0.,210.]),('target_id',78)]:
   r=fixture();r['events'][1][field]=value;self.assertFalse(q.memory_checks(r)['verified'],field)
 def test_move_cannot_extend_ttl_or_use_other_point(self):
  for field,value in [('frame',1001),('command_xyz',[601.,0.,210.])]:
   r=fixture();r['events'][2][field]=value;self.assertFalse(q.memory_checks(r)['checks']['memory_move_bound'],field)
 def test_attack_and_prepare_require_current_view(self):
  r=fixture();r['events'][-1]['current_visible']=0;r['events'][-1]['visible_target_xyz']=[0.,0.,0.];self.assertFalse(q.memory_checks(r)['checks']['memory_attack_currently_visible'])
  r=fixture();r['events'][5].update(arg=3,current_visible=0,visible_target_xyz=[0.,0.,0.]);self.assertFalse(q.memory_checks(r)['checks']['memory_attack_currently_visible'])
 def test_memo_update_needs_actual_visible_publication(self):
  r=fixture();r['events'][3].update(target_last_seen_frame=400,current_visible=1,kind=54,visible_target_xyz=[600.,0.,210.]);self.assertFalse(q.memory_checks(r)['verified'])
 def test_memory_expiry_and_reacquisition_wait_have_real_clock(self):
  r=fixture();r['events']=r['events'][:2];e=copy.deepcopy(r['events'][-1]);e.update(seq=3,kind=65,arg=1,frame=1001);r['events'].append(e);self.assertTrue(q.memory_checks(r)['checks']['memory_wait_bounded']);e['frame']=1000;self.assertFalse(q.memory_checks(r)['checks']['memory_wait_bounded'])
  e.update(arg=2,frame=200,memory_wait_started=155,x=500.);self.assertTrue(q.memory_checks(r)['checks']['memory_wait_bounded']);e['frame']=199;self.assertFalse(q.memory_checks(r)['checks']['memory_wait_bounded'])
 def test_false_memory_never_means_effect_or_task_success(self):
  r=fixture();r['native']={};r['preflight']={};a=q.qualify(r);self.assertFalse(a['effect_verified']);self.assertFalse(a['retreat_verified']);self.assertEqual(a['status'],'not_passed')
 def test_compiled_layout_agrees_with_true_ctypes_arrays(self):
  sp=importlib.util.spec_from_file_location('mct5_layout',D/'lease.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(layout,dict(event=c.sizeof(m.Event),tactical=c.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0))
  event=m.Event();event.remembered_target_xyz[:]=[1.,2.,3.];self.assertEqual(m.event_record(event)['remembered_target_xyz'],[1.,2.,3.])
 def test_memory_wait_cannot_extend_absolute_approach_deadline(self):
  code=(D/'mission_tick.inc').read_text().split('if(p->mission_stage==2){',1)[1].split('if(p->mission_stage==3)',1)[0];self.assertLess(code.index('now-p->approach_started>=p->approach_limit'),code.index('remaining<=125'))
 def test_hidden_visibility_check_does_not_read_xy_hp_early(self):
  source=(D/'lease.cpp').read_text().split('static bool visible_target(){',1)[1].split('static void __attribute__',1)[0]
  self.assertLess(source.index('for(uint32_t i=0;i<num;i++)'),source.index('read(t+0x38'))
  self.assertLess(source.index('if(!total)return false;'),source.index('read(t+0x38'))
  self.assertLess(source.index('read(t+0x38'),source.index('float hp=0'))
 def test_no_core_offset_or_old_namespace_changed(self):
  source=(D/'lease.cpp').read_text();self.assertIn('word(p->unit+0x374)==p->update',source);self.assertNotIn('word(p->unit+0x378)',source);self.assertEqual(source.count('if(!tag&&actor_lease_active())'),5);self.assertIn('version!=13',source);self.assertIn('WM_APP+0x381',(D/'shared.h').read_text())

if __name__=='__main__':unittest.main()
