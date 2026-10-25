"""Fresh-view ranking improves admission margin without granting any safety."""
import unittest
import test_client as boundary

class OriginSelection(unittest.TestCase):
 def setUp(self):
  self.executor=boundary.m.TacticalExecutor('unused','unused','57e668b4-4d89-43bd-bc92-0dd436f046ef')
  self.executor.contacts={'enemy':dict(currently_visible=True)}
  self.executor.private_visible_positions={'enemy':dict(xyz=[0,0,0],observed_frame=100)}

 def rank(self,units,distance):return self.executor._origin_selection_priority(units,distance,100)

 def test_clearance_margin_beats_closer_but_borderline_actor(self):
  borderline=dict(xyz=[360,0,0]);rear=dict(xyz=[500,0,0])
  self.assertLess(self.rank((rear,),800),self.rank((borderline,),660))

 def test_both_roles_are_checked_and_safe_actors_keep_target_priority(self):
  front=dict(xyz=[600,0,0]);support=dict(xyz=[360,0,0])
  self.assertGreater(self.rank((front,support),400),self.rank((front,dict(xyz=[500,0,0])),500))
  self.assertLess(self.rank((dict(xyz=[500,0,0]),),300),self.rank((dict(xyz=[900,0,0]),),800))

 def test_hidden_stale_and_unbound_positions_do_not_change_ranking(self):
  self.executor.contacts['enemy']['currently_visible']=False
  self.executor.contacts['stale']=dict(currently_visible=True)
  self.executor.private_visible_positions.update(stale=dict(xyz=[0,0,0],observed_frame=84),unbound=dict(xyz=[0,0,0],observed_frame=100))
  self.assertEqual(self.rank((dict(xyz=[1,0,0]),),123),(0,0,1,123))

 def test_current_idle_state_is_preferred_after_both_origins_have_margin(self):
  idle=dict(xyz=[700,0,0],actor_admission=dict(state_snapshot=dict(state_id=16,path='0x0')))
  moving=dict(xyz=[500,0,0],actor_admission=dict(state_snapshot=dict(state_id=1,path='0x1234')))
  self.assertLess(self.rank((idle,),700),self.rank((moving,),500))
