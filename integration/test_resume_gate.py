import unittest
from run_when_live import ready

class ResumeGate(unittest.TestCase):
 def test_paused_or_same_frame_does_not_start_child(self):
  self.assertFalse(ready(100,101,3));self.assertFalse(ready(100,100,0));self.assertFalse(ready(0,100,0))
 def test_resumed_simulation_must_advance(self):self.assertTrue(ready(100,101,0))
 def test_rollback_is_a_lifecycle_error(self):
  with self.assertRaises(ValueError):ready(100,1,0)
