"""Unfinished formation candidate must not enter the trusted runtime or dispatch."""
import subprocess
import sys
import unittest
from pathlib import Path
import evidence

class FormationCandidate(unittest.TestCase):
 def test_candidate_is_not_a_registered_executor(self):
  with self.assertRaisesRegex(ValueError,'executor_not_in_trusted_scope_table'):
   evidence.executor_schema('mission-formation-v7')

 def test_candidate_cli_stops_before_parsing_or_accessing_a_game(self):
  path=Path(__file__).parent/'mission-formation-v7/lease.py'
  result=subprocess.run([sys.executable,str(path),'--execute'],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('formation7_candidate_disabled_pending_qualification_bundle',result.stderr)
