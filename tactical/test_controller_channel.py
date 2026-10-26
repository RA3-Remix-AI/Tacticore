"""Exclusive paid-controller channel fences the legacy free-unit worker."""
import unittest,uuid
import client

def uid():return str(uuid.uuid4())
class Channel(unittest.TestCase):
 def setUp(self):
  self.e=client.TacticalExecutor('unused','unused',uid());self.e.state='running';self.e.session={'session_id':uid()};self.e._binding=lambda:None;self.controller=uid()
 def test_claim_is_idempotent_only_for_same_controller(self):
  self.assertTrue(self.e.claim_controller_channel(self.controller));self.assertTrue(self.e.claim_controller_channel(self.controller));self.assertFalse(self.e.claim_controller_channel(uid()))
 def test_existing_free_work_or_reservation_prevents_claim(self):
  self.e.pending.put({});self.assertFalse(self.e.claim_controller_channel(self.controller));self.e.pending.get()
  self.e.reserved_units.add(123);self.assertFalse(self.e.claim_controller_channel(self.controller))
 def test_only_bound_independent_release_opens_the_channel(self):
  self.e.claim_controller_channel(self.controller)
  for who,verified in ((uid(),True),(self.controller,False)):
   with self.assertRaises(ValueError):self.e.release_controller_channel(who,independently_verified=verified)
  self.assertEqual(self.e.external_controller_channel,self.controller)
  self.e.release_controller_channel(self.controller,independently_verified=True);self.assertIsNone(self.e.external_controller_channel)
 def task(self):return dict(task_id=uid(),command_id=uid(),seq=1,module='combined_arms',purpose='coordinate_force')
 def test_paid_capability_cannot_spawn_the_free_unit_backend(self):
  for directory in ('mission-formation-v13','mission-formation-v14','mission-formation-v15','mission-formation-v16','mission-formation-v17','mission-formation-v18'):
   self.e.capabilities={'combined_arms':['coordinate_force']};self.e.capability_grants={('combined_arms','coordinate_force'):{'executor_directory':directory}}
   result=self.e.submit(self.task());self.assertFalse(result['accepted']);self.assertEqual(result['reason_code'],'prebound_paid_pair_requires_existing_controller');self.assertTrue(self.e.pending.empty())
 def test_occupied_channel_rejects_tasks_and_cannot_report_stopped(self):
  self.e.capabilities={'combined_arms':['coordinate_force']};self.e.claim_controller_channel(self.controller)
  result=self.e.submit(self.task());self.assertEqual(result['reason_code'],'native_channel_owned_by_controller');self.assertTrue(self.e.pending.empty())
  self.assertEqual(self.e.stop()['state'],'return_pending')
  self.e.release_controller_channel(self.controller,independently_verified=True);self.assertEqual(self.e.stop()['state'],'stopped')
if __name__=='__main__':unittest.main()
