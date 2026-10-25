"""Failure-path tests never start a native process or access a game."""
import copy,hashlib,json,subprocess,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import run_flak as task

class DispatchEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'bridge-probe/production';self.root.mkdir(parents=True)
  package=self.base/'Mods/TriadFront/TriadFront.big';package.parent.mkdir(parents=True);package.write_bytes(b'test-package')
  self.session=self.base/'session.json';self.snapshot=self.base/'snapshot.json';self.observation=self.base/'observer.json'
  self.session.write_text(json.dumps(dict(session_id='test',pid=123,mod_big=str(package),mod_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),run_directory=str(self.base))))
  self.snapshot.write_text(json.dumps(dict(pid=123,candidates=[dict(address='0x10000',type_hash='0x80d4ea1e',owner_index_candidate=3,owner_address='0x20000')])))
  self.observation.write_text(json.dumps(dict(pid=123,original_bytes_restored=True,active_detours=0,state=2,error=0,window_thread=99,callback_thread=99,events=[dict(thread=99,caller='0x4f49e7',raw_args_after_template=[0,0xcd7e84,0,0,0,0,0],matched_node='0x30000',return_value=1,node_cost=220)])))
  self.args=types.SimpleNamespace(session=self.session,snapshot=self.snapshot,natural_observation=self.observation,factory='0x10000')
 def tearDown(self):self.tmp.cleanup()
 def simulate(self,behavior):
  report=dict(status='preflight',active_enqueue_attempted=False,session_id='test',pid=123);saved=[]
  def persist():
   saved.append(copy.deepcopy(report));task.durable_write(self.base/'evidence.json',report)
  def native(*args,**kwargs):
   disk=json.loads((self.base/'evidence.json').read_text())
   self.assertEqual(disk['status'],'dispatch_pending');self.assertEqual(disk['active_enqueue_attempted'],'unknown')
   if isinstance(behavior,Exception):raise behavior
   return behavior
  memory=Mock(handle=1)
  with patch.object(task,'ROOT',self.root),patch.object(task,'Memory',return_value=memory),patch.object(task,'read_owner',return_value=dict(ai_player='0x40000',resource_available=True,display_sum=500)),patch.object(task,'read_factory',return_value=dict(interface='0x50000',production_interface_available=True,queue_candidate=dict(module='0x4ffdc',head='0x0',tail='0x0',nodes=[]))),patch.object(task.k,'GetProcessTimes',return_value=1),patch.object(task.subprocess,'run',side_effect=native):
   task.execute(self.args,report,persist)
  memory.close.assert_called_once();return report,saved
 def test_timeout_preserves_unknown_and_partial_output(self):
  report,saved=self.simulate(subprocess.TimeoutExpired('native',20,output=b'partial',stderr=b'error'))
  self.assertEqual(report['status'],'native_timeout');self.assertEqual(report['active_enqueue_attempted'],'unknown');self.assertEqual(report['native_stdout'],'partial');self.assertEqual(len(saved),1)
 def test_launch_failure_is_not_a_game_call(self):
  report,_=self.simulate(FileNotFoundError('missing native host'))
  self.assertEqual(report['status'],'native_launch_failed');self.assertFalse(report['active_enqueue_attempted'])
 def test_invalid_result_does_not_infer_success_from_exit_zero(self):
  report,_=self.simulate(subprocess.CompletedProcess('native',0,stdout='',stderr=''))
  self.assertEqual(report['status'],'native_result_unavailable');self.assertEqual(report['active_enqueue_attempted'],'unknown')
 def test_valid_result_retained_without_spend_inference(self):
  report,_=self.simulate(subprocess.CompletedProcess('native',0,stdout='{"state":2,"active_enqueue_attempted":true,"native_cost":220}',stderr=''))
  self.assertEqual(report['native_result']['native_cost'],220);self.assertTrue(report['active_enqueue_attempted']);self.assertNotIn('spend_verified',report)

if __name__=='__main__':unittest.main()
