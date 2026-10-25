import unittest
from live_state import verify_scenario_map

class ScenarioMapIdentity(unittest.TestCase):
 def test_exact_native_map_components(self):
  verify_scenario_map(r'data\maps\official\map_mp_2_feasel6\map_mp_2_feasel6.map',{'map_id':'map_mp_2_feasel6'})
  verify_scenario_map(r'DATA\MAPS\OFFICIAL\MAP_MP_2_FEASEL6\MAP_MP_2_FEASEL6.MAP',{'map_id':'map_mp_2_feasel6'})
 def test_other_map_or_substring_rejected(self):
  for path in (r'data\map_mp_2_feasel6\other.map',r'data\other\map_mp_2_feasel6.map',r'data\map_mp_2_feasel6_extra\map_mp_2_feasel6_extra.map'):
   with self.subTest(path=path),self.assertRaises(ValueError):verify_scenario_map(path,{'map_id':'map_mp_2_feasel6'})
 def test_invalid_recorded_identity_rejected(self):
  with self.assertRaises(ValueError):verify_scenario_map('anything.map',{'map_id':r'data\anything'})
 def test_optional_for_existing_unrecorded_sessions(self):
  verify_scenario_map('anything.map',{})
