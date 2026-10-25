"""Final diagnostic CLI boundaries; no automatic capability or game calls."""
import subprocess,sys,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
class FinalDiagnosticCLI(unittest.TestCase):
 def test_missing_actor_binding_rejected_before_game_read(self):
  result=subprocess.run([sys.executable,str(H/'lease.py'),'--execute'],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,2)
  self.assertIn('--front-id',result.stderr)
  self.assertNotIn('FileNotFoundError',result.stderr)
 def test_help_and_joint_diagnostic_unlock(self):
  result=subprocess.run([sys.executable,str(H/'lease.py'),'--help'],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0)
  self.assertNotIn('mfm11_candidate_not_joint_diag_verified',(H/'lease.py').read_text())
if __name__=='__main__':unittest.main()
