import unittest,importlib.util,sys,ctypes as c,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from test_reusable import AssessmentTests
spec=importlib.util.spec_from_file_location('stop_move',ROOT/'stop-move/lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class StopTests(unittest.TestCase):
 def good(self):
  r=AssessmentTests().good();r['native'].update(restore_mask=127,stop_calls=1,private_stop_calls=1,private_stop_frame=101,move_issued_frame=105,stable_samples=3,stop_gate_samples=3)
  for e in r['events']:e.update(path=0,sm_flags=0,source=1)
  r['events']=[x for x in r['events'] if x['kind'] not in [10,11]]
  for kind,tag,caller,frame in [(20,4,0,100),(21,4,0,100),(22,4,0x787791,101),(23,4,0x787791,101),(3,0,0,102),(3,0,0,103),(24,0,0,105),(10,2,0,105),(11,2,0,105)]:r['events'].append(dict(kind=kind,tag=tag,caller=caller,arg=1,frame=frame,thread=999,team=0x40000,owner=0x10000,path=0,sm_flags=0,source=1,x=0.,y=0.,z=210.))
  r['events'].sort(key=lambda x:x['frame'])
  for i,e in enumerate(r['events']):e['seq']=i+1
  # clean pre-move samples are not arrival samples
  return r
 def test_stop_move_primitive(self):self.assertEqual(m.assessment(self.good())['status'],'stop_move_and_return_primitive_verified')
 def test_layout(self):
  n=json.loads(subprocess.check_output([str(ROOT/'stop-move/bin/tactical_host.exe'),'--layout'],text=True));self.assertEqual(n['event'],c.sizeof(m.Event));self.assertEqual(n['tactical'],c.sizeof(m.Tactical));self.assertEqual(n['events'],m.Tactical.events.offset)
 def test_stop_return_is_not_execution(self):
  r=self.good();r['events']=[e for e in r['events'] if e['kind'] not in [22,23]];self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_stop_deferred_after_move(self):
  r=self.good();next(e for e in r['events'] if e['kind']==23)['frame']=106;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_path_uncleared(self):
  r=self.good();next(e for e in r['events'] if e['kind']==24)['path']=123;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_lock_still_active(self):
  r=self.good();next(e for e in r['events'] if e['kind']==24)['sm_flags']=1;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_unstable(self):
  r=self.good();r['native']['stable_samples']=0;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_unknown_private_caller(self):
  r=self.good();next(e for e in r['events'] if e['kind']==23)['caller']=0;self.assertEqual(m.assessment(r)['status'],'not_passed')
if __name__=='__main__':unittest.main()
