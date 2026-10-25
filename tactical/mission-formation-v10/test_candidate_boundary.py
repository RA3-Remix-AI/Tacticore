"""Final CLI parse boundaries remain inert; execute requires the live contract."""
import subprocess,sys,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
class FinalCLI(unittest.TestCase):
 def test_missing_actor_binding_rejected_by_parser_before_game_read(self):
  result=subprocess.run([sys.executable,str(H/'lease.py'),'--execute'],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,2)
  self.assertIn('--front-id',result.stderr)
  self.assertNotIn('FileNotFoundError',result.stderr)
 def test_help_is_usable_and_temporary_guard_removed_after_joint_static_checks(self):
  result=subprocess.run([sys.executable,str(H/'lease.py'),'--help'],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0)
  self.assertNotIn('mfm10_candidate_not_joint_verified',(H/'lease.py').read_text())
if __name__=='__main__':unittest.main()
