"""Client dispatch routing with fake child/reader; no game or kernel access."""
import types,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
import test_client as boundary
m=boundary.m

class FormationGateClientTests(unittest.TestCase):
 def executor(self):return m.TacticalExecutor('unused-session','unused-natural','57e668b4-4d89-43bd-bc92-0dd436f046ef')
 def test_both_new_directories_use_continuous_worker(self):
  e=self.executor();e._execute_formation_mission=MagicMock(return_value='mission')
  for directory in ['mission-formation-v2','mission-formation-v3']:
   self.assertEqual(e._execute_formation('cmd',dict(executor_directory=directory)),'mission')
  self.assertEqual(e._execute_formation_mission.call_count,2)
 def invoke(self,e,directory,report,collector):
  module=types.SimpleNamespace(collect=collector);spec=types.SimpleNamespace(loader=MagicMock())
  with patch.object(m,'trusted_executor',return_value={}),patch.object(m.importlib.util,'spec_from_file_location',return_value=spec) as load,patch.object(m.importlib.util,'module_from_spec',return_value=module):
   result=e._formation_native_gate(directory,report,Path('raw.json'))
  return result,load
 def test_zero_lease_uses_exact_reader_and_preserves_sidecar(self):
  for directory in ['mission-formation-v2','mission-formation-v3']:
   collector=MagicMock(return_value=dict(no_actor_lease_verified=True,evidence_path='raw.native-gate.json',native_host_launched=True,restoration_verified=False,return_verified=False,completion_claim=False));e=self.executor()
   result,load=self.invoke(e,directory,{'native':dict(phase=4,issued_frame=0)},collector)
   self.assertEqual(load.call_args.args[1].name,'mission_formation_v3_gate_no_lease.py');collector.assert_called_once_with(Path('raw.json'),e.session_path)
   self.assertTrue(result['native_host_launched']);self.assertFalse(result['completion_claim']);self.assertFalse(result['return_verified']);self.assertFalse(result['restoration_verified'])
 def test_borrowed_actor_or_success_or_old_scope_never_zero_lease(self):
  for directory,native in [('mission-formation-v3',dict(phase=4,issued_frame=100)),('mission-formation-v3',dict(phase=3,issued_frame=0)),('mission-formation',dict(phase=4,issued_frame=0))]:
   collector=MagicMock();result,load=self.invoke(self.executor(),directory,dict(native=native),collector);self.assertIsNone(result);collector.assert_not_called();load.assert_not_called()
 def test_reader_failure_never_certifies_release(self):
  result,_=self.invoke(self.executor(),'mission-formation-v3',dict(native=dict(phase=4,issued_frame=0)),MagicMock(side_effect=ValueError('binding')))
  self.assertFalse(result['no_dispatch_verified']);self.assertFalse(result['no_actor_lease_verified']);self.assertEqual(result['error_type'],'ValueError')
 def test_pre_native_v3_uses_exact_v3_helper(self):
  e=self.executor();e.session={};proof=dict(no_dispatch_verified=False);verify=MagicMock(return_value=proof);module=types.SimpleNamespace(verify_no_dispatch=verify);spec=types.SimpleNamespace(loader=MagicMock())
  with patch.object(m,'trusted_executor',return_value={}),patch.object(m.importlib.util,'spec_from_file_location',return_value=spec) as load,patch.object(m.importlib.util,'module_from_spec',return_value=module):
   self.assertFalse(e._record_pre_native_rejection(dict(object_ids=[1,2]),{},Path('raw.json'),64,'cmd','task',1,'mission-formation-v3'))
  self.assertEqual(load.call_args.args[1].name,'pre_dispatch_formation_v3_contract.py');self.assertEqual(verify.call_args.kwargs['directory'],'mission-formation-v3')

if __name__=='__main__':unittest.main()
