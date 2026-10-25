import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('formation_backend',Path(__file__).parent/'formation/lease.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class FormationTests(unittest.TestCase):
 def good(self):
  units=[dict(id=100,hash=0x19ab11af,initial=[0.,0.,210.],goal=[80.,0.,210.],hold=[0.,0.,210.],move_calls=1,detach_calls=1,return_calls=1,returned=1),dict(id=101,hash=0x2c358c61,initial=[-40.,0.,210.],goal=[20.,0.,210.],hold=[-40.,0.,210.],move_calls=2,detach_calls=1,return_calls=1,returned=1)]
  ev=[]
  def row(unit,kind,tag,frame,stage=1,arg=0,caller=0,x=0.):return dict(unit_id=unit,kind=kind,tag=tag,frame=frame,tick=frame*10,stage=stage,arg=arg,caller=caller,thread=999,owner=0x10000,x=x,y=0.,z=210.)
  for oid in [100,101]:ev.append(row(oid,18,1,100,arg=0x20104,caller=0x838877))
  for oid,frame in [(101,100),(100,100),(101,110)]:ev.extend([row(oid,10,2,frame),row(oid,11,2,frame)])
  for frame in [102,104,106]:ev.extend([row(100,3,0,frame,x=80.),row(101,3,0,frame,x=-40.)])
  for frame in [112,114,116]:ev.extend([row(100,3,0,frame,stage=2,x=80.),row(101,3,0,frame,stage=2,x=20.)])
  for oid in [100,101]:ev.append(row(oid,16,3,116,stage=3,arg=0x20104,caller=0x83885b))
  n=dict(commander_id='commander',seq=1,phase=3,error=0,restore_mask=31,active=0,stage=3,goal_samples=3,issued_frame=100,front_arrival_frame=110,support_issued_frame=110,returned_frame=116,callback_thread=999,session_id='s',command_id='c',task_id='t',overflow=0)
  return dict(native=n,units=units,events=ev,session_id='s',preflight=dict(commander_id='commander',window_thread=999,owner='0x10000',ai='0x20000',session_id='s'),request=dict(front_goal=[80.,0.,210.],support_goal=[20.,0.,210.],seq=1,command_id='c',task_id='t',lease_frames=180,min_spacing=40,max_spacing=100))
 def test_staged_pair_is_separate_capability(self):
  a=m.assessment(self.good());self.assertEqual(a['status'],'two_role_staged_advance_primitive_verified');self.assertFalse(a['combined_arms_verified'])
 def test_same_role_rejected(self):
  r=self.good();r['units'][1]['hash']=0x19ab11af;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_premature_support_release_rejected(self):
  r=self.good();r['native']['support_issued_frame']=105;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_same_point_without_spacing_rejected(self):
  r=self.good()
  for e in r['events']:
   if e['unit_id']==101 and e['stage']==2:e['x']=80.
  self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_different_frames_not_combined(self):
  r=self.good()
  for e in r['events']:
   if e['unit_id']==101 and e['kind']==3:e['frame']+=1
  self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_excessive_commands_rejected(self):
  r=self.good();r['units'][1]['move_calls']=50;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_unknown_return_rejected(self):
  r=self.good();r['units'][1]['returned']=0;self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_stage_two_before_order_is_not_geometry_evidence(self):
  r=self.good()
  for e in r['events']:
   if e['kind']==3 and e['stage']==2:e['frame']=90;e['tick']=900
  self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_one_sided_stage_cannot_pair(self):
  r=self.good()
  for e in r['events']:
   if e['kind']==3 and e['stage']==2 and e['unit_id']==101:e['stage']=1
  self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_scalar_front_arrival_without_trajectory_fails(self):
  r=self.good()
  for e in r['events']:
   if e['kind']==3 and e['stage']==1 and e['unit_id']==100:e['x']=0.
  self.assertEqual(m.assessment(r)['status'],'not_passed')
 def test_goal_not_matching_request_fails(self):
  r=self.good();r['request']['front_goal']=[999.,0.,210.];self.assertEqual(m.assessment(r)['status'],'not_passed')
if __name__=='__main__':unittest.main()
