"""Bounded same-frame retry and physical published completion evidence."""
import copy,importlib.util,json,time,types,unittest
from pathlib import Path
from unittest.mock import patch
H=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
host=load('retry_stopped_host_test',H/'planning_host_trace_v4.py')
q=load('retry_completion_q_test',H/'formation_mission_qualification_trace_v4.py')
class Samples(unittest.TestCase):
 def setup(self,frames):
  rows=[]
  for i,frame in enumerate(frames):
   role=i%2;rows.append(dict(frame=frame,valid=True,grounded_status=dict(object_id=role+1,owner='0x9',type_hash='0x1',hp=100,xyz=[role*50.,0.,210.]),state_snapshot=dict(state_id=16,command_source=1,path='0x0')))
  self.rows=iter(rows);self.calls=0
  def actor(memory,address):self.calls+=1;return next(self.rows)
  a=types.SimpleNamespace(actor_admission=actor,verify_evidence=lambda r:dict(verified=r['valid']))
  self.w=types.SimpleNamespace(module=lambda *args:a,b=types.SimpleNamespace(k=types.SimpleNamespace(GetTickCount=lambda:1000)))
  self.memory=types.SimpleNamespace(u32=lambda address:100)
  self.pre=dict(owner='0x9',logic='0x1')
  self.actors=[dict(object_id=i+1,type_hash='0x1',address=hex(i+1)) for i in (0,1)]
  self.shared=types.SimpleNamespace(planning_front=[0.,0.,210.],planning_support=[50.,0.,210.],planning_ready_tick=0)
  self.audit=[]
 def run_sample(self,deadline=None):return host.stopped_records(self.w,self.memory,self.pre,*self.actors,self.shared,deadline or time.monotonic()+2,self.audit,'final')
 def test_clock_skew_only_is_resampled_then_complete_records_match(self):
  self.setup([99,100,100,100]);rows,frame=self.run_sample();self.assertEqual(frame,100);self.assertEqual(self.calls,4);self.assertEqual([x['result'] for x in self.audit],['clock_skew_retry','same_frame']);self.assertTrue(all(r['frame']==100 for r in rows))
 def test_maximum_three_attempts_no_unbounded_poll(self):
  self.setup([99,100]*3)
  with self.assertRaisesRegex(ValueError,'planning_actor_pair_not_same_frame'):self.run_sample()
  self.assertEqual(self.calls,6)
 def test_identity_hp_stop_state_path_and_pose_never_retry(self):
  for mode in ['hp','id','owner','state','source','path','pose','invalid']:
   self.setup([100,100]);rows=list(self.rows);r=rows[0]
   if mode=='hp':r['grounded_status']['hp']=49
   elif mode=='id':r['grounded_status']['object_id']=88
   elif mode=='owner':r['grounded_status']['owner']='0x88'
   elif mode=='state':r['state_snapshot']['state_id']=10
   elif mode=='source':r['state_snapshot']['command_source']=0
   elif mode=='path':r['state_snapshot']['path']='0x12'
   elif mode=='pose':r['grounded_status']['xyz'][0]=1.01
   else:r['valid']=False
   self.rows=iter(rows)
   with self.assertRaisesRegex(ValueError,'planning_actor_not_same_stopped_lease'):self.run_sample()
   self.assertEqual(self.calls,1,mode)
 def test_old_two_second_deadline_and_six_second_ready_are_not_reset(self):
  self.setup([100,100])
  with self.assertRaisesRegex(ValueError,'planning_budget_exceeded'):self.run_sample(time.monotonic()-1)
  self.assertEqual(self.calls,0)
  self.setup([100,100]);self.w.b.k.GetTickCount=lambda:6000
  with self.assertRaisesRegex(ValueError,'planning_budget_exceeded'):self.run_sample()
  self.assertEqual(self.calls,0)
 def test_deadline_expires_during_valid_sample(self):
  self.setup([100,100])
  with patch.object(host.time,'monotonic',side_effect=[0,2]):
   with self.assertRaisesRegex(ValueError,'planning_budget_exceeded'):self.run_sample(1)
  self.assertEqual(self.calls,2)

class Completion(unittest.TestCase):
 def fixture(self):
  p=H.parent.parent/'acceptance/runs/20261025-170331-commander/continuous-paid-mf4-traffic01-formation.json';return json.loads(p.read_text(encoding='utf-8'))
 def audit(self,r):return q.stage_audit(r['events'],[n['xyz'] for n in r['request']['route']],r['native']['safe_front'],r['native']['safe_support'],1)[3]
 def test_actual_third_frame_double_completion_records_geometry(self):
  r=self.fixture();a=self.audit(r);self.assertTrue(a['verified'],a);self.assertEqual(a['paired_arrival_run'],3)
 def test_duplicate_kind3_completion_same_frame_never_makes_three(self):
  r=self.fixture();r['events']=[e for e in r['events'] if not(e.get('mission_stage')==1 and e.get('route_index')==3 and e.get('nav_step')==2 and e['frame']==2192)]
  pair=[copy.deepcopy(e) for e in r['events'] if e.get('kind')==60 and e.get('mission_stage')==1 and e.get('route_index')==3]
  for e in pair:e['kind']=3
  r['events']+=pair;self.assertFalse(self.audit(r)['verified'])
 def test_one_role_mismatch_tick_wrong_geometry_rejected(self):
  for mode in ['one_role','tick','geometry']:
   r=self.fixture();e=next(e for e in r['events'] if e.get('kind')==60 and e.get('mission_stage')==1 and e.get('route_index')==3 and e.get('role')==1)
   if mode=='one_role':r['events'].remove(e)
   elif mode=='tick':e['tick']+=1
   else:e['x']+=100
   self.assertFalse(self.audit(r)['verified'],mode)
if __name__=='__main__':unittest.main()
