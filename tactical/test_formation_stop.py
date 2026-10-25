import unittest,importlib.util,sys,ctypes as c,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from test_formation import FormationTests
spec=importlib.util.spec_from_file_location('formation_stop_backend',ROOT/'formation-stop/lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FormationStopTests(unittest.TestCase):
 def good(self):
  r=FormationTests().good();r['native']['restore_mask']=127
  # Remove the old support Move(self); only one advance per role remains.
  r['events']=[e for e in r['events'] if not(e['unit_id']==101 and e['kind'] in [10,11] and e['frame']==100)]
  for e in r['events']:
   if e['unit_id']==100 and e['kind'] in [10,11]:e['frame']=104;e['tick']=1040
   if e['kind']==3 and e['stage']==1:e['frame']+=3;e['tick']=e['frame']*10
  for i,u in enumerate(r['units']):
   u.update(move_calls=1,stop_calls=1,private_stop_calls=1,stable_samples=3,gate_samples=3,native_stop=0)
   x=u['hold'][0]
   for kind,tag,caller,frame in [(20,4,0,100),(21,4,0,100),(22,4,0x787791,100),(23,4,0x787791,100),(3,0,0,101),(3,0,0,102),(24,0,0,104)]:r['events'].append(dict(unit_id=u['id'],kind=kind,tag=tag,caller=caller,arg=1,frame=frame,tick=frame*10,stage=0,thread=999,owner=0x10000,x=x,y=0.,z=210.,path=0,sm_flags=0,source=1))
  r['events'].sort(key=lambda x:(x['frame'],-1 if x['kind']==24 else 0))
  for i,e in enumerate(r['events']):e.update(seq=i+1,path=e.get('path',0),sm_flags=e.get('sm_flags',0),source=e.get('source',1))
  return r
 def test_two_stops_two_moves(self):self.assertEqual(m.assessment(self.good())['status'],'two_role_staged_advance_primitive_verified')
 def test_layout(self):
  n=json.loads(subprocess.check_output([str(ROOT/'formation-stop/bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual((n['event'],n['tactical'],n['events']),(c.sizeof(m.Event),c.sizeof(m.Tactical),m.Tactical.events.offset))
 def test_old_support_self_move(self):
  r=self.good();r['units'][1]['move_calls']=2;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_missing_one_private_stop(self):
  r=self.good();r['events']=[e for e in r['events'] if not(e['kind']==23 and e['unit_id']==101)];self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_hold_capture_differs(self):
  r=self.good();next(e for e in r['events'] if e['kind']==24 and e['unit_id']==101)['x']+=20;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_active_lock_rejected(self):
  r=self.good();next(e for e in r['events'] if e['kind']==24)['sm_flags']=1;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_uncleared_path_rejected(self):
  r=self.good();next(e for e in r['events'] if e['kind']==24)['path']=123;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_stop_after_move_rejected(self):
  r=self.good();next(e for e in r['events'] if e['kind']==23)['frame']=106;self.assertEqual(m.assessment(r)['status'],'not_passed')
if __name__=='__main__':unittest.main()

