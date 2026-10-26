"""Static targets isolate the attack chain from pursuit of a moving contact."""
import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('static_targets17',HERE/'paid_pair_controller_v17.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class StaticTargets(unittest.TestCase):
 def setUp(self):self.safety={'templates':{'b':{'role':'structure','template':'SovietBarracks'},'0xc45aaeab':{'role':'economy','template':'SovietRefinery'},'i':{'role':'infantry','template':'SovietAntiVehicleInfantry'},'d':{'role':'structure','template':'SovietBaseDefenseAntiInfantry'}}}
 def t(self,i,kind,x,hp=1500):return dict(object_id=i,type_hash=kind,xyz=[x,0,210],hp=hp)
 def choose(self,rows):return m.select_target(rows,self.safety,[[0,0,210]])
 def test_moving_infantry_cannot_supplant_a_static_target(self):self.assertEqual(self.choose({'i':self.t(1,'i',600,120),'b':self.t(2,'b',1500)})[2],'b')
 def test_a_closer_barracks_precedes_a_deep_refinery(self):self.assertEqual(self.choose({'b':self.t(1,'b',1500),'r':self.t(2,'0xc45aaeab',1900,2400)})[2],'b')
 def test_defence_or_low_health_or_outside_range_is_not_a_target(self):
  for kind,x,hp in [('d',600,1500),('b',1000,599),('b',2001,1500),('b',449,1500),('i',600,120)]:
   with self.subTest(kind=kind,x=x,hp=hp):self.assertIsNone(self.choose({'x':self.t(1,kind,x,hp)}))
 def test_only_current_projection_can_supply_a_target(self):self.assertIsNone(self.choose({}))
if __name__=='__main__':unittest.main()
