import unittest,importlib.util,sys,json,ctypes as c,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from test_formation_stop import FormationStopTests
from stop_sequence import settled_stop
s=importlib.util.spec_from_file_location('formation_stop2',ROOT/'formation-stop-v2/lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Stop2Tests(unittest.TestCase):
 def good(self):
  r=FormationStopTests().good()
  for u in r['units']:
   e=dict(next(e for e in r['events'] if e['kind']==3 and e['stage']==0 and e['unit_id']==u['id']));e.update(frame=104,tick=1040);r['events'].append(e)
  r['events'].sort(key=lambda e:(e['frame'],-2 if e['kind']==3 and e['stage']==0 else -1 if e['kind']==24 else 0))
  for i,e in enumerate(r['events']):e['seq']=i+1
  return r
 def test_new_good(self):self.assertEqual(m.assessment(self.good())['status'],'two_role_staged_advance_primitive_verified')
 def test_duplicate_goal_frame_rejected(self):
  r=self.good()
  for e in r['events']:
   if e['kind']==3 and e['stage']==2:e.update(frame=112,tick=1120)
  self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_forged_counter_cannot_hide_moving_support(self):
  r=self.good();next(e for e in r['events'] if e['kind']==3 and e['stage']==0 and e['frame']==102 and e['unit_id']==101)['x']+=2
  self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_reverse_frame_rejected(self):
  r=self.good();[e.update(frame=111,tick=1110) for e in r['events'] if e['kind']==3 and e['stage']==2 and e['frame']==116];self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_real_single_stop_stable(self):
  r=json.loads((ROOT/'../acceptance/runs/20261024-234355-commander/stop-move01.json').read_text(encoding='utf-8'));self.assertTrue(settled_stop(r['events'])['verified'])
 def test_real_batch_stable(self):
  r=json.loads((ROOT/'../acceptance/runs/20261024-234355-commander/formation-stop01.json').read_text(encoding='utf-8'))
  for u in r['units']:self.assertTrue(settled_stop(r['events'],u['id'])['verified'])
 def test_layout(self):
  n=json.loads(subprocess.check_output([str(ROOT/'formation-stop-v2/bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual((n['event'],n['tactical'],n['events']),(c.sizeof(m.Event),c.sizeof(m.Tactical),m.Tactical.events.offset))
if __name__=='__main__':unittest.main()
