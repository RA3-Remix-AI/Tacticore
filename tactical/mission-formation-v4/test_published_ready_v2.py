"""Exact header-before-capture race regression. Never accesses a game."""
import copy,hashlib,importlib.util,json,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mf4_ready_v2',H/'lease_ready_v2.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class Ready(unittest.TestCase):
 def fixture(self):
  return dict(native=dict(phase=1,mission_stage=9,planning_ready=1,planning_ready_frame=100),events=[dict(kind=72,role=i,frame=100,planning_ready_frame=100,planning_ready=1,mission_stage=9,seq=20+i) for i in (0,1)])
 def test_complete_same_capture_is_ready(self):self.assertTrue(w.captured_planning_ready(self.fixture()))
 def test_live_header_flag_cannot_replace_missing_published_prefix(self):
  # The old case read shared.ready=1 after a snapshot with no72 events.
  for events in ([],[self.fixture()['events'][0]],[self.fixture()['events'][1]]):
   r=self.fixture();r['events']=events;self.assertFalse(w.captured_planning_ready(r))
 def test_new_events_do_not_upgrade_an_old_native_snapshot(self):
  for key,value in [('phase',5),('mission_stage',8),('planning_ready',0),('planning_ready_frame',99)]:
   r=self.fixture();r['native'][key]=value;self.assertFalse(w.captured_planning_ready(r))
 def test_wrong_role_old_frame_or_unpublished_sequence_waits(self):
  for key,value in [('role',0),('frame',99),('planning_ready_frame',99),('seq',0)]:
   r=self.fixture();r['events'][1][key]=value;self.assertFalse(w.captured_planning_ready(r))
 def test_exact_failed_case_replayed_until_ready_prefix_arrives(self):
  p=H.parent.parent/'acceptance/runs/20261025-154511-commander/coord-mf4-02.json';r=json.loads(p.read_text(encoding='utf-8'));e=[x for x in r['events'] if x['kind']==72]
  report=dict(native=dict(phase=1,mission_stage=9,planning_ready=1,planning_ready_frame=e[0]['frame']),events=[])
  self.assertFalse(w.captured_planning_ready(report));report['events']=e[:1];self.assertFalse(w.captured_planning_ready(report));report['events']=e;self.assertTrue(w.captured_planning_ready(report))
 def test_original_source_and_native_preserved(self):
  expected={'lease.py':'39b18c8d6cafead36276ab72a49f09a149f13bc319bb8cd3fd8872b8e41bcb6f','formation_mission_qualification.py':'3d487ae9e3ec5b727ae9d50f814dbd05d5cf528e6c4ec73ca2a47260d9b042b3','bin/TacticalMissionFormation4.dll':'1421d30446aa27712654b269edea52fcbe4abf5913e027bd1b45ffd230d948a4'}
  for p,sha in expected.items():self.assertEqual(hashlib.sha256((H/p).read_bytes()).hexdigest(),sha)
  text=(H/'lease_ready_v2.py').read_text();self.assertIn('if captured_planning_ready(report):',text);self.assertNotIn('if shared.planning_ready:',text)
if __name__=='__main__':unittest.main()
