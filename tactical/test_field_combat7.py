"""Do not import or execute the sole-runner selector; verify exact isolated clone."""
import ast,hashlib,unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'mission-formation-v3'
class Field7(unittest.TestCase):
 def test_exact_backend_admission_disposal_only_clone(self):
  old=(P/'field_combat_v6.py').read_text(encoding='utf-8');actual=(P/'field_combat_v7.py').read_text(encoding='utf-8')
  expected=old.replace('mission-combat-v6','mission-combat-v7').replace('from mission_actor_admission import','from mission_actor_admission_v2 import').replace('immediate_v6_disposal','immediate_v7_disposal').replace('mission_v6_readonly_disposal.py','mission_v7_readonly_disposal.py')
  self.assertEqual(actual,expected);ast.parse(actual);self.assertIn("choices=['mission-combat-v7'],default='mission-combat-v7'",actual);self.assertNotIn('mission_v6_readonly_disposal',actual);self.assertNotIn('mission-combat-v6',actual)
if __name__=='__main__':unittest.main()
