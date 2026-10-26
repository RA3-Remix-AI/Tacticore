"""Current-FOV target ranking for the fragile calibration pair; no game calls."""
import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('paid_pair_targets16',HERE/'paid_pair_controller_v16.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Targets(unittest.TestCase):
 def setUp(self):self.safety={'templates':{'inf':{'role':'infantry','template':'SovietAntiInfantryInfantry'},'barracks':{'role':'structure','template':'SovietBarracks'},'0xc45aaeab':{'role':'economy','template':'SovietRefinery'},'tank':{'role':'armor','template':'SovietAntiVehicleVehicleTech1'},'scout':{'role':'infantry','template':'SovietScoutInfantry'}}}
 def target(self,oid,kind,x,hp=100):return dict(object_id=oid,type_hash=kind,xyz=[x,0,210],hp=hp)
 def choose(self,rows):return m.select_target(rows,self.safety,[[0,0,210]])
 def test_near_barracks_is_preferred_to_deep_refinery(self):
  selected=self.choose({'b':self.target(1,'barracks',1500),'r':self.target(2,'0xc45aaeab',1900,2400)})
  self.assertEqual(selected[2],'b')
 def test_a_local_ground_skirmish_precedes_a_long_base_march(self):
  selected=self.choose({'i':self.target(1,'inf',650),'b':self.target(2,'barracks',1600)})
  self.assertEqual(selected[2],'i')
 def test_observed_nearby_armour_changes_the_rank_without_becoming_a_target(self):
  selected=self.choose({'i':self.target(1,'inf',600),'t':self.target(2,'tank',650),'b':self.target(3,'barracks',-900)})
  self.assertEqual(selected[2],'b')
 def test_short_or_deep_or_low_health_or_unsupported_contacts_are_not_candidates(self):
  for kind,x,hp in [('inf',449,100),('barracks',2001,100),('inf',600,59),('tank',600,100),('scout',600,100),('unknown',600,100)]:
   with self.subTest(kind=kind,x=x,hp=hp):self.assertIsNone(self.choose({'x':self.target(1,kind,x,hp)}))
 def test_an_empty_current_view_does_not_supply_a_remembered_target(self):self.assertIsNone(self.choose({}))
if __name__=='__main__':unittest.main()
