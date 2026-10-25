"""Planning errors retain exact private local inputs before cleanup. No game access."""
import copy,importlib.util,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('trace_host_fault_test',H/'planning_host_trace_v4.py');host=importlib.util.module_from_spec(s);s.loader.exec_module(host)
class GraphFailure(ValueError):
 def __init__(self):super().__init__('no_role_safe_bounded_actual_own_route');self.diagnostics=dict(expanded_states=321,ground_nodes=44)
class Persistence(unittest.TestCase):
 def run_failure(self,error):
  durable=[];shared=types.SimpleNamespace(phase=1,mission_stage=9,planning_ready=1,route_ready=0,planning_ready_frame=100,planning_ready_tick=1000)
  pre=dict(logic='0x1000',frame=100,owner='0x9000',commander_id='c')
  actors=[dict(object_id=i+1,address=hex(i+1),type_hash='0x1',xyz=[i*50.,0.,210.],hp=100) for i in (0,1)]
  records=[dict(frame=100,grounded_status=dict(xyz=a['xyz'],hp=100)) for a in actors]
  owned=[dict(a) for a in actors];census=dict(frame_start=100,frame_end=100,owned_positions=owned)
  def plan(*args,**kwargs):
   self.assertEqual(len(durable),1);self.assertEqual(durable[0]['planning_inputs']['initial_occupancy'],census);raise error
  planner=types.SimpleNamespace(plan_from_history=plan,LAST_DIAGNOSTICS=dict(fallback=True))
  traffic=types.SimpleNamespace(classify_owned=lambda *args:census)
  def module(name,path):return planner if 'role_route' in path.name else traffic if path.name=='traffic_occupancy_v2.py' else types.SimpleNamespace()
  w=types.SimpleNamespace(module=module,b=types.SimpleNamespace(own_candidates=lambda *args:dict(candidates=owned),load_catalog=lambda:{},durable=lambda path,r:durable.append(copy.deepcopy(r)),k=types.SimpleNamespace(GetTickCount=lambda:1200)))
  memory=types.SimpleNamespace(u32=lambda address:100)
  report=dict(events=[dict(kind=72,role=i,frame=100,seq=i+1) for i in (0,1)],request=dict(command_id='cmd',task_id='task',seq=7,token=8,expires_frame=4500))
  target=dict(object_id=77,xyz=[500.,0.,210.],observed_frame=100)
  with patch.object(host,'stopped_records',return_value=(records,100)),patch.object(host,'refresh_guard',return_value=target),patch.object(host,'publish_route') as publish:
   with self.assertRaises(type(error)):
    host.make_and_publish(w,memory,dict(session_id='session',pid=1),pre,report,shared,None,*actors,'contact',{},H,Path('not-written.json'))
   publish.assert_not_called()
  self.assertEqual(len(durable),2);inputs=durable[0]['planning_inputs'];self.assertEqual(inputs['stopped_admission'],records);self.assertEqual(inputs['front'],actors[0]);self.assertEqual(inputs['source_frame_cutoff'],100);self.assertEqual(inputs['current_visible_target'],target);self.assertEqual(inputs['source_budget']['mission_deadline_frame'],4500);self.assertEqual(shared.route_ready,0);return durable[-1]
 def test_exact_graph_diagnostics_and_inputs_survive_error(self):
  r=self.run_failure(GraphFailure());self.assertEqual(r['planning_diagnostics'],dict(expanded_states=321,ground_nodes=44));self.assertEqual(r['planning_search_error'],'no_role_safe_bounded_actual_own_route')
 def test_unexpected_search_exception_keeps_inputs_and_fallback_diagnostics(self):
  r=self.run_failure(RuntimeError('disk_read'));self.assertEqual(r['planning_diagnostics'],dict(fallback=True));self.assertEqual(r['planning_search_error'],'disk_read')
if __name__=='__main__':unittest.main()
