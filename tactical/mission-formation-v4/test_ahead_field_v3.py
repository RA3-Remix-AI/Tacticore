"""Field selection uses actual current target direction, never a paid-ID override."""
import importlib.util,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('ahead_selector_test',H/'field_plan_ahead_v3.py');field=importlib.util.module_from_spec(s);s.loader.exec_module(field)
def actor(i,x,y=0):return dict(object_id=i,xyz=[float(x),float(y),210.])
class Ahead(unittest.TestCase):
 def test_paid_actor_behind_cannot_win(self):
  behind=(actor(1,0),actor(2,50));ahead=(actor(3,50),actor(4,0));self.assertEqual(field.ahead_pairs([behind,ahead],[500,0,210],1,2),[ahead])
 def test_direction_recomputed_for_each_current_target(self):
  east=(actor(1,50),actor(2,0));west=(actor(3,0),actor(4,50));self.assertEqual(field.ahead_pairs([east,west],[500,0,210]),[east]);self.assertEqual(field.ahead_pairs([east,west],[-500,0,210]),[west])
 def test_preference_only_orders_legal_ahead_then_distance(self):
  far=(actor(1,50),actor(2,0));near=(actor(3,100),actor(4,0));self.assertEqual(field.ahead_pairs([far,near],[500,0,210]),[near,far]);self.assertEqual(field.ahead_pairs([near,far],[500,0,210],1,2),[far,near])
 def test_exact_sideways_boundary_allowed_but_negative_rejected(self):
  side=(actor(1,0),actor(2,0,50));bad=(actor(3,-.1),actor(4,0));self.assertEqual(field.ahead_pairs([side,bad],[500,0,210]),[side])
if __name__=='__main__':unittest.main()
