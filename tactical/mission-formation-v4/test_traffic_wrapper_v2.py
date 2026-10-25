"""Traffic alternate regression suite. Pure files/ctypes only; no SDK calls."""
import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
H=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=load('traffic_planning_base',H/'test_planning_qualification.py')
ready=load('traffic_ready_base',H/'test_published_ready_v2.py')
q=load('traffic_qualification_candidate',H/'formation_mission_qualification_traffic_v2.py')
w=load('traffic_wrapper_candidate',H/'lease_traffic_v2.py')
base.q=q;ready.w=w

class Planning(base.PlanningQualificationTests):
 def test_actual_source_nodes_and_persisted_plan_are_independently_rechecked(self):
  fixture=load('traffic_actual_source_fixture',H.parent/'mission-formation-v3/test_admission_wrapper_v4.py');r=fixture.fixture();route=r['request']['route'];pre=r['preflight'];frame=r['last_admission']['frame']
  plan=dict(schema_version=1,session_id=r['session_id'],pid=pre['pid'],player_id=3,front_id=r['request']['front_id'],support_id=r['request']['support_id'],route=route,source='positive_ground_own_positions_role_aware',walkable_route_verified=False)
  origin=dict(origin_method='current_verified_owned_movable_positions',viewer_player_id=3,front_id=r['request']['front_id'],support_id=r['request']['support_id'],observed_frame=pre['frame'],front_initial=pre['selected']['xyz'],support_initial=pre['support']['xyz'],currently_visible_enemy_threats_within350=[]);r['request']['safe_origin']=origin
  provenance=q.load_local('traffic_real_source_validation','route_provenance_traffic_v2.py');traffic=q.load_local('traffic_census_validation','traffic_occupancy_v2.py')
  rows=[dict(object_id=x['object_id'],address=x['address'],type_hash=x['type_hash'],xyz=x['xyz'],traffic_class='hard_or_unknown') for x in [pre['selected'],pre['support']]]
  census=dict(protocol='verified_mobile_foot_traffic_v2',owner=pre['owner'],frame_start=frame,frame_end=frame,sample_started_frame=frame,sample_finished_frame=frame,owned_positions=rows,reader_sha256=hashlib.sha256((H/'traffic_occupancy_v2.py').read_bytes()).hexdigest(),mutations=False,walkable_route_verified=False)
  sources=provenance.source_records(route,dict(session_id=r['session_id'],pid=pre['pid']),frame,pre['owner'])
  result=provenance.occupancy(route,rows,{r['request']['front_id'],r['request']['support_id']},pre['owner'])
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'planned.json';path.write_text(json.dumps(plan),encoding='utf-8')
   r['planning_commit']=dict(source_plan=plan,source_plan_path=str(path),source_plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_validation=sources,submitted_frame=frame,planner_sha256=hashlib.sha256((H/'role_route_planner_traffic_v2.py').read_bytes()).hexdigest(),origin_safety=origin,target=r['private_target'],occupancy=census,initial_occupancy=copy.deepcopy(census),occupancy_result=result)
   self.assertTrue(q.planned_source_audit(r))
   for mode in ['wrongsha','occupied','fake_mobile','stale_mobile','duplicate','reader','summary','initial','slow_scan','late_submit','threat']:
    bad=copy.deepcopy(r);occ=bad['planning_commit']['occupancy']
    if mode=='wrongsha':bad['planning_commit']['source_validation'][0]['sha256']='0'*64
    elif mode in ['occupied','fake_mobile','stale_mobile']:
     row=dict(object_id=999999,address='0x9999',type_hash='0x19ab11af',xyz=route[0]['xyz'],traffic_class='hard_or_unknown')
     if mode!='occupied':row.update(traffic_class='verified_mobile_foot',traffic_admission={})
     occ['owned_positions'].append(row)
    elif mode=='duplicate':occ['owned_positions'].append(copy.deepcopy(rows[0]))
    elif mode=='reader':occ['reader_sha256']='0'*64
    elif mode=='summary':bad['planning_commit']['occupancy_result']['hard_occupants']+=1
    elif mode=='initial':bad['planning_commit']['initial_occupancy']['owner']='0x123'
    elif mode=='slow_scan':occ['sample_started_frame']=frame-5
    elif mode=='late_submit':bad['planning_commit']['submitted_frame']=frame+5
    else:bad['planning_commit']['origin_safety']['currently_visible_enemy_threats_within350']=[123]
    self.assertFalse(q.planned_source_audit(bad),mode)

class Ready(ready.Ready):pass

class Bindings(unittest.TestCase):
 def test_all_alternate_paths_are_pinned_without_mutating_predecessors(self):
  expected={'lease_ready_v2.py':'39445f66dbeb666563bc67496577218cda5086e17d9f55b46409f45c71cf9784','formation_mission_qualification_ready_v2.py':'b7303f4c73229b5a1bb8335e02403d9bad142b811455a3af01e9c5cb4f517e59','role_route_planner.py':'897fea98260b4a81122da9da03e120584dc427c35cf99a9f5504b3015cbad9bf','bin/TacticalMissionFormation4.dll':'1421d30446aa27712654b269edea52fcbe4abf5913e027bd1b45ffd230d948a4'}
  for p,s in expected.items():self.assertEqual(hashlib.sha256((H/p).read_bytes()).hexdigest(),s)
  sources=w.supplemental()
  for p in ['planning_host_traffic_v2.py','role_route_planner_traffic_v2.py','route_provenance_traffic_v2.py','traffic_occupancy_v2.py','formation_mission_qualification_traffic_v2.py']:self.assertEqual(sources[p],hashlib.sha256((H/p).read_bytes()).hexdigest())
 def test_snapshot_ready_race_guard_preserved(self):
  self.assertIn('if captured_planning_ready(report):',(H/'lease_traffic_v2.py').read_text())
  self.assertNotIn('if shared.planning_ready:',(H/'lease_traffic_v2.py').read_text())

if __name__=='__main__':unittest.main()
