"""Pure serial handover and paid-order boundaries, no process or SDK access."""
import copy,importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('paid',Path(__file__).with_name('continuous_paid_driver.py'));d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
class Handover(unittest.TestCase):
 def fixture(self):
  session=dict(pid=1,session_id='session',scenario=dict(commander_id='commander'));identity=dict(pid=1,session_id='session',commander_id='commander');status=dict(native_phase=2,native_error=0,restore_mask=31,active_callbacks=0)
  entries=[dict(address=hex(a),expected=b,actual=b) for a,b in d.ENTRIES.items()];return status,identity,session,entries
 def test_exact_stopped_and_five_bytes_required(self):self.assertTrue(d.restored(*self.fixture()))
 def test_phase_callbacks_identity_and_bytes_tamper_refuse(self):
  for key,value in [('native_phase',1),('native_error',1),('restore_mask',15),('active_callbacks',1)]:
   args=self.fixture();args[0][key]=value;self.assertFalse(d.restored(*args))
  args=self.fixture();args[1]['session_id']='old';self.assertFalse(d.restored(*args))
  args=self.fixture();args[3][0]['actual']='90';self.assertFalse(d.restored(*args))
  args=self.fixture();args[3].pop();self.assertFalse(d.restored(*args))
  args=self.fixture();args[3][:]=[args[3][0]]*5;self.assertFalse(d.restored(*args))
 def paid(self):
  command=dict(command_id='cmd',task_id='task',seq=1,unit='flak');receipt=dict(command,completed=True,paid_verified=True,created=True,completion_observed=True,queue_preserved=True,object_id=7,live_samples=1,payment_error=0)
  return [dict(command=command,receipt=dict(accepted=True))],dict(ledger=[receipt])
 def test_actual_payment_birth_and_live_chain(self):self.assertTrue(d.paid_orders_verified(*self.paid()))
 def test_ack_payment_only_or_wrong_order_cannot_release_for_tactical(self):
  for key,value in [('command_id','wrong'),('task_id','wrong'),('seq',2),('paid_verified',False),('created',False),('live_samples',0),('payment_error',1),('completed',False),('queue_preserved',False)]:
   commands,status=self.paid();status['ledger'][0][key]=value;self.assertFalse(d.paid_orders_verified(commands,status),key)
if __name__=='__main__':unittest.main()
