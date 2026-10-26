"""A closed scene may release ownership, never substitute for a physical return."""
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf17_scene_wrapper_test',HERE/'lease.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SceneWrapper(unittest.TestCase):
 def runtime(self, path, phase, error, exit_code=9):
  runtime=m.ControllerRuntime('unused',{},path,'unused')
  runtime.report={'native':{'phase':phase,'error':error}}
  runtime.host=types.SimpleNamespace(poll=lambda:exit_code)
  runtime.poll=Mock()
  return runtime
 def test_only_terminal_scene_error_can_request_scene_disposal_proof(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'raw.json';path.write_bytes(b'original evidence')
   q=types.SimpleNamespace(source_pins=lambda r:True,control_release=lambda r:{'control_release_verified':False})
   collect=Mock(return_value={'control_release_verified':True,'scene_disposed_control_release':True,'restoration_verified':False,'return_verified':False,'physical_retreat_verified':False,'goal_observed':False,'completed':False})
   with patch.object(m,'qualifier',return_value=q),patch.object(m,'module',return_value=types.SimpleNamespace(collect=collect)):
    result=self.runtime(path,4,31).verified_release()
   collect.assert_called_once();self.assertFalse(result['physical_retreat_verified']);self.assertFalse(result['goal_observed']);self.assertEqual(path.read_bytes(),b'original evidence')
 def test_death_cleanup_live_host_or_other_phase_cannot_become_scene_release(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'raw.json';path.write_bytes(b'original evidence')
   q=types.SimpleNamespace(source_pins=lambda r:True,control_release=lambda r:{'control_release_verified':False})
   with patch.object(m,'qualifier',return_value=q),patch.object(m,'module',side_effect=AssertionError('No scene reader')):
    for phase,error,code in ((4,52,9),(3,31,0),(4,31,None)):
     self.assertFalse(self.runtime(path,phase,error,code).verified_release()['control_release_verified'])

if __name__=='__main__':unittest.main()
