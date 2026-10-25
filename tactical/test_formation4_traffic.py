"""Planner to provenance integration on synthetic grounded source files."""
import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from test_mission_actor_admission import Memory
P=Path(__file__).resolve().parent;D=P/'mission-formation-v4'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
traffic=load('traffic_policy_test',D/'traffic_occupancy_v2.py')
planner=load('traffic_planner_test',D/'role_route_planner_traffic_v2.py')
validator=load('traffic_provenance_test',D/'route_provenance_traffic_v2.py')

class TrafficPlanning(unittest.TestCase):
 def census(self):
  m=Memory();m.xyz=[100.,0.,210.]
  row=dict(object_id=77,address='0x2000',type_hash='0x19ab11af',xyz=m.xyz,ai_address='0x6000')
  return traffic.classify_owned(m,[row],'0x3000',0x1000)
 def history(self,folder):
  for i,x in enumerate([100.,200.,300.]):
   m=Memory();m.xyz=[x,0.,210.];g=traffic.admission.g.grounded_status(m,0x2000)
   row=dict(object_id=77,type_hash='0x19ab11af',xyz=g['xyz'],hp=100.,grounded_verified=True,grounded_status=g)
   record=dict(session_id='s',pid=1,player_id=3,logic_frame_candidate=100,method='same_frame_owned_position_with_verified_native_surface',ground_reader_sha256=hashlib.sha256((P/'grounded_status_v2.py').read_bytes()).hexdigest(),source_collector_sha256=hashlib.sha256((P.parent/'integration/ground_history.py').read_bytes()).hexdigest(),mutations=False,walkable_route_verified=False,own_objects=[row])
   (Path(folder)/f'{i}.json').write_text(json.dumps(record),encoding='utf-8')
 def plan(self,folder,rows):
  return planner.plan_from_history(folder,dict(frame=120,owner='0x3000'),dict(session_id='s',pid=1),dict(object_id=1,xyz=[0.,0.,210.]),dict(object_id=2,xyz=[-60.,0.,210.]),[500.,0.,210.],rows)
 def test_real_frame_survives_planner_to_independent_source_validator(self):
  with tempfile.TemporaryDirectory() as folder:
   self.history(folder);plan=self.plan(folder,[])
   sources=validator.source_records(plan['route'],dict(session_id='s',pid=1),120,'0x3000')
   self.assertEqual(len(sources),len(plan['route']));self.assertTrue(all(n['observed_frame']==100 for n in plan['route']))
   self.assertFalse(plan['walkable_route_verified'])
   plan['route'][0].pop('observed_frame')
   with self.assertRaises(ValueError):validator.source_records(plan['route'],dict(session_id='s',pid=1),120,'0x3000')
 def test_verified_mobile_traffic_does_not_disconnect_but_unknown_stays_hard(self):
  census=self.census();self.assertTrue(traffic.verify_census(census,'0x3000'))
  with tempfile.TemporaryDirectory() as folder:
   self.history(folder);plan=self.plan(folder,census['owned_positions'])
   self.assertTrue(validator.occupancy(plan['route'],census['owned_positions'],{1,2},'0x3000')['verified'])
   row=copy.deepcopy(census['owned_positions'][0]);row['traffic_class']='hard_or_unknown'
   with self.assertRaises(ValueError):self.plan(folder,[row])
   with self.assertRaises(ValueError):validator.occupancy(plan['route'],[row],{1,2},'0x3000')
 def test_mobile_label_ground_and_owner_tamper_cannot_remove_obstacle(self):
  for mutate in ('evidence','position','owner','state','frame','reader','duplicate'):
   c=self.census();r=c['owned_positions'][0]
   if mutate=='evidence':r['traffic_admission']['admission_verified']=False
   elif mutate=='position':r['xyz']=[101.,0.,210.]
   elif mutate=='owner':c['owner']='0x4000'
   elif mutate=='state':r['traffic_admission']['state_snapshot']['state_id']=54
   elif mutate=='frame':c.update(frame_start=110,frame_end=110)
   elif mutate=='reader':c['reader_sha256']='0'*64
   else:c['owned_positions'].append(copy.deepcopy(r))
   self.assertFalse(traffic.verify_census(c,'0x3000'),mutate)
 def test_locked_or_garrison_state_remains_hard(self):
  for state in (54,77):
   m=Memory();m.state_id=state
   c=traffic.classify_owned(m,[dict(object_id=77,address='0x2000',type_hash='0x19ab11af',xyz=m.xyz,ai_address='0x6000')],'0x3000',0x1000)
   self.assertTrue(traffic.verify_census(c,'0x3000'));self.assertEqual(c['owned_positions'][0]['traffic_class'],'hard_or_unknown')
 def test_soft_traffic_never_changes_leased_role_geometry(self):
  self.assertFalse(planner.route_geometry([0.,0.,210.],[-60.,0.,210.],[dict(xyz=[-100.,0.,210.]),dict(xyz=[-200.,0.,210.])]))
  self.assertFalse(planner.route_geometry([0.,0.,210.],[-60.,0.,210.],[dict(xyz=[180.,0.,210.]),dict(xyz=[300.,0.,210.])]))

if __name__=='__main__':unittest.main()
