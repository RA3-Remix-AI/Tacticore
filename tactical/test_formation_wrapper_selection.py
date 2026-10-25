"""Trusted alternate Python wrapper routing, with no game/kernel operations."""
import json,tempfile,types,unittest,uuid
from pathlib import Path
from unittest.mock import MagicMock,patch
import test_client as boundary
m=boundary.m

class AlternateWrapperTests(unittest.TestCase):
 def test_runtime_uses_registry_wrapper_and_legacy_defaults(self):
  for schema,name in [({},'lease.py'),({'wrapper_filename':'lease_admission_v2.py'},'lease_admission_v2.py')]:
   module=types.SimpleNamespace();spec=types.SimpleNamespace(loader=MagicMock())
   with patch.object(m,'trusted_executor',return_value=schema),patch.object(m.importlib.util,'spec_from_file_location',return_value=spec) as loader,patch.object(m.importlib.util,'module_from_spec',return_value=module):self.assertIs(m.runtime_backend('mission-formation-v3')[1],module)
   self.assertEqual(loader.call_args.args[1].name,name)
 def test_filename_escape_never_imported(self):
  for value in ['../lease.py','C:/foreign.py','nested/name.py','.py',None]:
   with patch.object(m,'trusted_executor',return_value={'wrapper_filename':value}),patch.object(m.importlib.util,'spec_from_file_location') as loader,self.assertRaises(ValueError):m.runtime_backend('mission-formation-v3')
   loader.assert_not_called()
 def test_new_qualifier_selected_explicitly(self):
  spec=types.SimpleNamespace(loader=MagicMock());module=types.SimpleNamespace()
  with patch.object(m.importlib.util,'spec_from_file_location',return_value=spec) as loader,patch.object(m.importlib.util,'module_from_spec',return_value=module):m.formation_qualifier('mission-formation-v3',dict(qualifier_filename='formation_mission_qualification_v2.py'))
  self.assertEqual(loader.call_args.args[1].name,'formation_mission_qualification_v2.py')
 def test_pre_dispatch_and_gate_reader_use_trusted_names(self):
  e=boundary.ModelBoundary().executor();schema=dict(pre_dispatch_helper='pre_dispatch_formation_v3_admission_v2_contract.py',gate_reader='mission_formation_v3_admission_v2_gate_no_lease.py');module=types.SimpleNamespace(verify_no_dispatch=MagicMock(return_value=dict(no_dispatch_verified=False)),collect=MagicMock(return_value=dict(no_actor_lease_verified=True)));spec=types.SimpleNamespace(loader=MagicMock())
  with patch.object(m,'trusted_executor',return_value=schema),patch.object(m.importlib.util,'spec_from_file_location',return_value=spec) as loader,patch.object(m.importlib.util,'module_from_spec',return_value=module):
   self.assertFalse(e._record_pre_native_rejection(dict(object_ids=[1,2]),{},Path('raw'),64,'cmd','task',1,'mission-formation-v3'));self.assertEqual(loader.call_args.args[1].name,schema['pre_dispatch_helper'])
   proof=e._formation_native_gate('mission-formation-v3',dict(native=dict(phase=4,issued_frame=0)),Path('raw'));self.assertTrue(proof['no_actor_lease_verified']);self.assertEqual(loader.call_args.args[1].name,schema['gate_reader'])
 def test_real_mission_worker_runs_new_script_and_new_authority(self):
  e=boundary.ModelBoundary().executor();e.session['pid']=1234;e.native_seq=0;e._validate_task_dispatch=MagicMock();e._record_pre_native_rejection=MagicMock(return_value=False);e._binding=MagicMock();e._audit=MagicMock();schema=dict(wrapper_filename='lease_admission_v2.py',qualifier_filename='formation_mission_qualification_v2.py',restore_mask=8191,success='formation_mission_effect_retreat_verified');runtime=types.SimpleNamespace(progress=MagicMock(side_effect=AssertionError('old wrapper progress must not be authority')));qm=types.SimpleNamespace(progress=MagicMock(return_value=None),qualify=MagicMock(return_value={'status':schema['success']}),control_release=MagicMock(return_value=dict(restoration_verified=True)));command=str(uuid.uuid4());task=str(uuid.uuid4());r=dict(executor_directory='mission-formation-v3',task_id=task,object_ids=[1,2],mission_input={},target_contact_id='contact',visibility_proof_path='unused',expires_frame=4500,unit_results=[],issued_frame=0)
  with tempfile.TemporaryDirectory() as folder:
   e.run=Path(folder)
   def child(args,**kwargs):
    self.assertEqual(Path(args[1]).name,'lease_admission_v2.py');value=lambda flag:args[args.index(flag)+1];rq=dict(command_id=value('--command-id'),task_id=value('--task-id'),seq=int(value('--seq')),front_id=1,support_id=2,target_contact_id='contact');n=dict(rq,commander_id=e.commander_id,session_id=e.session['session_id'],issued_frame=10,support={'id':2},phase=3,restore_mask=8191,active=0);report=dict(session_id=e.session['session_id'],preflight=dict(pid=1234,commander_id=e.commander_id,selected={'object_id':1},support={'object_id':2}),request=rq,native=n);Path(value('--output')).write_text(json.dumps(report),encoding='utf-8');return types.SimpleNamespace(poll=lambda:0,returncode=0)
   with patch.object(m,'runtime_backend',return_value=(schema,runtime)),patch.object(m,'formation_qualifier',return_value=qm),patch.object(m.subprocess,'Popen',side_effect=child):e._execute_formation_mission(command,r)
   self.assertTrue(r['completed']);self.assertTrue(r['restoration_verified']);qm.qualify.assert_called_once();qm.control_release.assert_called_once();runtime.progress.assert_not_called()

if __name__=='__main__':unittest.main()
