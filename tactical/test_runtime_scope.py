import unittest,importlib.util,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import evidence,restoration
class RuntimeScopeTests(unittest.TestCase):
 def test_unknown_directory_closed(self):
  with self.assertRaises(ValueError):evidence.executor_schema('../combat-commit')
 def test_diagnostic_not_grantable(self):
  for directory in ['combat-commit','combat-traced','combat-stack','formation-stop']:
   with self.assertRaises(ValueError):evidence.executor_schema(directory)
 def test_stop2_exact_runtime(self):
  s=evidence.executor_schema('formation-stop-v2');self.assertEqual((s['dll'],s['mapping_prefix'],s['restore_mask']),('TacticalFormationStop2.dll','RA3TacticalFormationStop2_',127))
 def test_failed_goal_restored_separately(self):
  r=json.loads((ROOT/'../acceptance/runs/20261024-234355-commander/formation-stop01.json').read_text(encoding='utf-8'));self.assertEqual(r['assessment']['status'],'not_passed');self.assertTrue(restoration.formation_restoration(r,127)['restoration_verified']);self.assertFalse(restoration.formation_restoration(r,31)['restoration_verified'])
 def test_unknown_mask_closed(self):
  r=json.loads((ROOT/'../acceptance/runs/20261024-234355-commander/formation-stop01.json').read_text(encoding='utf-8'));self.assertFalse(restoration.formation_restoration(r,255)['restoration_verified'])
 def test_failed_calibration_cannot_grant(self):
  r=json.loads((ROOT/'../acceptance/runs/20261024-234355-commander/formation-stop01.json').read_text(encoding='utf-8'))
  with self.assertRaises(ValueError):evidence.verify_purpose('combined_arms','coordinate_force',ROOT/'../acceptance/runs/20261024-234355-commander/formation-stop01.json',{'mod_sha256':r['package_sha256'],'session_id':r['session_id']},r['preflight']['commander_id'])
if __name__=='__main__':unittest.main()
