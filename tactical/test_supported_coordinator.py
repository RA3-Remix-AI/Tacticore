"""The final selector and native child must share the same plan/proof and actors."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'acceptance/calibration/field_coordinate_margin12_supported.py'
spec=importlib.util.spec_from_file_location('supported_coordinator_tests',path)
coordinator=importlib.util.module_from_spec(spec);spec.loader.exec_module(coordinator)

class Coordinator(unittest.TestCase):
 def test_exact_new_plan_proof_and_current_actors_reach_frozen_wrapper(self):
  selection=dict(front_id=17,support_id=23,contact_id='current-visible',expires_frame=2000)
  args=coordinator.child_arguments(Path('session'),Path('natural'),Path('raw'),selection,
   Path('supported-plan'),Path('supported-proof'),'command','task',11)
  self.assertEqual(Path(args[1]),ROOT/'tactical/mission-formation-v12/lease.py')
  for key,value in [('--front-id','17'),('--support-id','23'),('--contact-id','current-visible'),
   ('--mission-file','supported-plan'),('--proof-file','supported-proof')]:
   self.assertEqual(args[args.index(key)+1],value)
 def test_final_readiness_runs_supported_selector_and_never_dispatches_without_execute(self):
  with tempfile.TemporaryDirectory() as temp:
   output=Path(temp)/'output.json';captured=[]
   def run(args,**kwargs):
    captured.append(args)
    self.assertEqual(Path(args[1]),path.with_name('field_plan_margin12_supported.py'))
    plan=Path(args[args.index('--output')+1])
    plan.with_name(plan.stem+'-selection.json').write_text('{}')
    return type('Result',(),dict(returncode=0,stdout='',stderr=''))()
   argv=['coordinator','--session','session','--natural','natural','--output',str(output)]
   with patch.object(sys,'argv',argv),patch.object(coordinator.subprocess,'run',side_effect=run),patch.object(coordinator.subprocess,'Popen') as spawn:
    coordinator.main();spawn.assert_not_called()
   self.assertEqual(len(captured),1)

if __name__=='__main__':unittest.main()
