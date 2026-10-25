import copy,unittest
from natural_evidence import compatible_natural_calls
def fixture():return dict(pid=123,state=2,error=0,original_bytes_restored=True,active_detours=0,window_thread=99,callback_thread=99,events=[dict(thread=99,caller='0x4f49e7',raw_args_after_template=[0,0xcd7e84,0,0,0,0,0],matched_node='0x10000',return_value=7,node_cost=220)])
class EvidenceTests(unittest.TestCase):
 def test_observed_source_pairs(self):
  for caller in ['0x4f49e7','0x4f467a']:
   for flag in [0,0x200]:
    observation=fixture();observation['events'][0]['caller']=caller;observation['events'][0]['raw_args_after_template'][0]=flag;self.assertEqual(len(compatible_natural_calls(observation,123)),1)
 def reject(self,mutate):
  observation=fixture();mutate(observation);self.assertRaises(RuntimeError,compatible_natural_calls,observation,123)
 def test_unknown_flag(self):self.reject(lambda o:o['events'][0]['raw_args_after_template'].__setitem__(0,1))
 def test_unknown_caller(self):self.reject(lambda o:o['events'][0].__setitem__('caller','0x79078b'))
 def test_wrong_sentinel(self):self.reject(lambda o:o['events'][0]['raw_args_after_template'].__setitem__(1,0xcd7e88))
 def test_nonzero_tail(self):self.reject(lambda o:o['events'][0]['raw_args_after_template'].__setitem__(6,1))
 def test_wrong_thread(self):self.reject(lambda o:o['events'][0].__setitem__('thread',100))
 def test_missing_node(self):self.reject(lambda o:o['events'][0].__setitem__('matched_node','0x0'))
 def test_missing_queue_id(self):self.reject(lambda o:o['events'][0].__setitem__('return_value',0))
 def test_missing_cost(self):self.reject(lambda o:o['events'][0].__setitem__('node_cost',0))
 def test_active_detour_rejected(self):self.reject(lambda o:o.__setitem__('active_detours',1))
 def test_pid_mismatch(self):self.assertRaises(RuntimeError,compatible_natural_calls,fixture(),124)
if __name__=='__main__':unittest.main()
