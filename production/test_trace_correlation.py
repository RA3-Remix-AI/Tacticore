import copy,struct,unittest
from assess_trace import assess

def bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]
def fixture():
 base=dict(record='event',node=0x10000,queue_id=1,thread=99,owner=0x20000,factory=0x30000,template_hash=0x2c358c61,cost=220,resource=0x40000,context_valid=1,object=0x50000,object_id=7,object_owner=0x20000,object_hash=0x2c358c61)
 def e(seq,kind,frame,**values):return dict(base,seq=seq,kind=kind,frame=frame,**values)
 records=[e(0,2,1,caller=0x7baaff,paid_before=0,paid_after=100),e(1,3,1,caller=0x70f578,requested=100,actual=100,cash_before_raw=500,cash_after_raw=400),e(2,2,2,caller=0x7baaff,paid_before=100,paid_after=220),e(3,3,2,caller=0x70f578,requested=120,actual=120,cash_before_raw=400,cash_after_raw=280),e(4,4,2,caller=0x7baffe,paid_before=220,returned=0x50000),e(5,5,2,caller=0x7bb7b6,paid_before=220),e(6,7,10,object_hp_bits=bits(100),object_x_bits=bits(20),object_y_bits=bits(0),object_z_bits=bits(0),factory_x_bits=bits(0),factory_y_bits=bits(0),factory_z_bits=bits(0))]
 report=dict(status='trace_finished',native_exit_code=0,session_unchanged_after=True,session_id='test',pid=123,mod_sha256='hash',installed=dict(callback_thread=99),preflight=dict(player=dict(address='0x20000',resource='0x40000'),factory=dict(address='0x30000')),stopped=dict(state=2,restore_mask=31,error=0,active_detours=0,dropped=0,emitted_events=7,total_events=7),enqueue_result=dict(session_id='test',pid=123,mod_sha256='hash',session_unchanged_after=True,native_result=dict(state=2,error=0,active_enqueue_attempted=True,queue_preserved=True,initial_paid=0,queue_id=1,node='0x10000',native_cost=220)))
 return report,records

class CorrelationTests(unittest.TestCase):
 def test_complete_chain_only_proves_primitive(self):
  report,records=fixture();result=assess(report,records);self.assertTrue(result['production_primitive_verified']);self.assertFalse(result['runtime_direction_switch_verified']);self.assertEqual(result['attributed_debits'],220)
 def test_net_cash_drop_does_not_replace_resource_call(self):
  report,records=fixture();records=[r for r in records if r['kind']!=3];self.assertFalse(assess(report,records)['production_primitive_verified'])
 def test_scan_discovery_does_not_replace_factory_creation(self):
  report,records=fixture();records=[r for r in records if r['kind']!=4];self.assertFalse(assess(report,records)['checks']['native_factory_creation'])
 def test_other_payment_caller_is_not_attributed(self):
  report,records=fixture();records[1]['caller']=0x84ca1a;self.assertFalse(assess(report,records)['checks']['cost_fully_attributed'])
 def test_previous_payment_not_observed_is_incomplete(self):
  report,records=fixture();records[0]['paid_before']=1;self.assertFalse(assess(report,records)['checks']['node_paid_accumulator'])
 def test_other_object_id_rejects_live_unit(self):
  report,records=fixture();records[-1]['object_id']=8;self.assertFalse(assess(report,records)['checks']['created_object_remains_live'])
 def test_other_thread_breaks_identity_chain(self):
  report,records=fixture();records[3]['thread']=100;self.assertFalse(assess(report,records)['checks']['identity_chain'])
 def test_dropped_events_prevent_pass(self):
  report,records=fixture();report['stopped']['dropped']=1;self.assertFalse(assess(report,records)['production_primitive_verified'])
 def test_unknown_enqueue_never_passes(self):
  report,records=fixture();report.pop('enqueue_result');self.assertFalse(assess(report,records)['production_primitive_verified'])
 def test_natural_chain_can_never_be_bridge_success(self):
  report,records=fixture();report.pop('enqueue_result');result=assess(report,records,dict(node=0x10000,queue_id=1,native_cost=220));self.assertTrue(result['natural_chain_verified']);self.assertFalse(result['production_primitive_verified']);self.assertFalse(result['checks']['bridge_enqueue'])

if __name__=='__main__':unittest.main()
