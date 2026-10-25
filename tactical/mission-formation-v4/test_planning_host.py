"""Controller-only tests: no game process, hooks, UI or SDK calls."""
import ctypes as c,hashlib,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
w=load('mfm4_wrapper_test',HERE/'lease.py');host=load('mfm4_host_test',HERE/'planning_host.py');coverage=load('mfm4_coverage_test',HERE/'coverage.py')
class Handshake(unittest.TestCase):
 def shared(self):
  s=w.Tactical();s.phase=1;s.mission_stage=9;s.planning_ready=1;return s
 def test_compiled_and_python_abi(self):
  actual=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
  self.assertEqual(actual,dict(event=c.sizeof(w.Event),tactical=c.sizeof(w.Tactical),events=w.Tactical.events.offset,unused1=0,unused2=0))
 def test_atomic_publication_order_and_frozen_input(self):
  s=self.shared();observed=[];route=[dict(xyz=[100.,0.,210.]),dict(xyz=[200.,0.,210.])]
  host.publish_route(s,route,[0.,0.,210.],[-60.,0.,210.],dict(xyz=[300.,0.,210.],observed_frame=101),lambda:observed.append((s.route_generation,s.route_ready,s.route_count,list(s.route[1]))))
  self.assertEqual([x[:3] for x in observed],[(1,0,2),(2,0,2)]);self.assertEqual((s.route_generation,s.route_ready),(2,1));self.assertEqual(list(s.route[1]),route[1]['xyz'])
  with self.assertRaisesRegex(ValueError,'already_closed'):host.publish_route(s,route,[0.,0.,210.],[-60.,0.,210.],dict(xyz=[300.,0.,210.],observed_frame=101),lambda:None)
 def test_no_publish_before_native_ready_or_after_cleanup(self):
  for field,value in [('planning_ready',0),('mission_stage',8),('phase',7),('route_generation',1),('route_ready',1)]:
   s=self.shared();setattr(s,field,value)
   with self.assertRaises(ValueError):host.publish_route(s,[dict(xyz=[100,0,210]),dict(xyz=[200,0,210])],[0,0,210],[-60,0,210],dict(xyz=[300,0,210],observed_frame=10),lambda:None)
   self.assertEqual(s.route_count,0)
 def test_invalid_route_count_never_publishes(self):
  s=self.shared()
  with self.assertRaisesRegex(ValueError,'count'):host.publish_route(s,[dict(xyz=[100,0,210])],[0,0,210],[-60,0,210],{},lambda:None)
  self.assertEqual(s.route_ready,0)
 def test_native_handshake_software_fault_branches(self):
  result=json.loads(subprocess.check_output([str(HERE/'bin/test_planning_native.exe')],text=True));self.assertTrue(result['passed']);self.assertFalse(result['game_access']);self.assertEqual(result['native_handshake_cases'],27)
  self.assertIn((HERE/'planning.cpp.inc').read_text(),(HERE/'mission_state.cpp.inc').read_text())
 def test_selectors_cannot_compute_pre_stop_route(self):
  text=(HERE/'field_plan.py').read_text();self.assertNotIn('plan_from_history(',text);self.assertIn('covered_goal(',text);self.assertIn('preferred-front-id',text);self.assertNotIn('wrapper-filename',(HERE/'field_coordinate.py').read_text())
 def test_coverage_requires_positive_owned_source_without_route(self):
  session=dict(session_id='session',pid=1)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'point.json';p.write_text(json.dumps(dict(session_id='session',pid=1,player_id=3,logic_frame_candidate=10,own_objects=[dict(object_id=7,xyz=[100,0,210])])),encoding='utf-8')
   with patch.object(coverage.roles,'positive_ground',return_value=False):self.assertIsNone(coverage.covered_goal(folder,session,11,'0x123',[100,0,210],1e20))
   with patch.object(coverage.roles,'positive_ground',return_value=True),patch.object(coverage.proof,'source_records',return_value=[]) as prove:
    result=coverage.covered_goal(folder,session,11,'0x123',[100,0,210],1e20);self.assertFalse(result['route_planning_performed']);prove.assert_called_once()
   with patch.object(coverage.roles,'positive_ground',return_value=True),patch.object(coverage.proof,'source_records',side_effect=ValueError('wrong_source')):self.assertIsNone(coverage.covered_goal(folder,session,11,'0x123',[100,0,210],1e20))
 def test_no_route_can_be_sent_at_native_launch(self):
  text=(HERE/'lease.py').read_text();self.assertIn('s.route_count=0',text);self.assertNotIn('points=route_points(',text);self.assertIn('if shared.planning_ready:',text)
if __name__=='__main__':unittest.main()
