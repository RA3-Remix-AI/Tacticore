import copy,unittest
from run_flak import validate_append_queue

def factory(count):
 nodes=[dict(address=hex(0x20000+i*0x100),kind_raw=1,template_hash='0x2c358c61',production_id_raw=i+1,native_cost_plus_30=220,paid_accumulator_plus_68=0) for i in range(count)]
 return dict(interface='0x10024',production_interface_available=True,queue_candidate=dict(module='0x10000',head=nodes[0]['address'] if nodes else '0x0',tail=nodes[-1]['address'] if nodes else '0x0',nodes=nodes))

class AppendTests(unittest.TestCase):
 def test_default_zero_rejects_existing_queue(self):self.assertRaisesRegex(RuntimeError,'queue-limit',validate_append_queue,factory(1),0)
 def test_two_existing_orders_are_allowed_only_explicitly(self):self.assertEqual(len(validate_append_queue(factory(2),2)),2)
 def test_three_existing_orders_rejected(self):self.assertRaisesRegex(RuntimeError,'queue-limit',validate_append_queue,factory(3),2)
 def test_duplicate_production_id_rejected(self):
  f=factory(2);f['queue_candidate']['nodes'][1]['production_id_raw']=1;self.assertRaisesRegex(RuntimeError,'identity',validate_append_queue,f,2)
 def test_unknown_template_rejected(self):
  f=factory(1);f['queue_candidate']['nodes'][0]['template_hash']='0xdeadbeef';self.assertRaisesRegex(RuntimeError,'template',validate_append_queue,f,1)
 def test_paid_above_cost_rejected(self):
  f=factory(1);f['queue_candidate']['nodes'][0]['paid_accumulator_plus_68']=221;self.assertRaisesRegex(RuntimeError,'payment',validate_append_queue,f,1)
 def test_wrong_module_rejected(self):
  f=factory(0);f['queue_candidate']['module']='0x30000';self.assertRaisesRegex(RuntimeError,'module',validate_append_queue,f,0)

if __name__=='__main__':unittest.main()
