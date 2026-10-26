"""Pure controller boundaries and actual compiled-layout decoding; no game SDK."""
import ctypes as c,hashlib,importlib.util,json,struct,subprocess,tempfile,unittest,uuid,types
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf16_wrapper_tests',HERE/'lease_v2.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def config():
 controller=str(uuid.uuid4());return dict(schema_version=1,controller_id=controller,lease_id=str(uuid.uuid4()),formation_uuid=m.contract.formation_ids(controller)[0],formation_version=1,seq=1,startup_deadline_frame=900,startup_wall_ms=60000,slots=[dict(role=i,command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=i+1,unit=unit,cost=cost,factory=0x20000,factory_id=765,iface=0x30000) for i,(unit,cost) in enumerate((('conscript',85),('flak',220)))])
class Contract(unittest.TestCase):
 def test_binary_commit_seal_covers_actual_prefix_and_detects_changes(self):
  body=m.layout_module.MissionCommitBody13();body.target_id=123;body.visible_target[:]=[1.25,2.5,210]
  seal=m.contract.seal_body(body);self.assertTrue(m.contract.verify_body(body));self.assertEqual(seal['digest_sha256'],hashlib.sha256(bytes(body)[:252]).hexdigest());body.target_id=124;self.assertFalse(m.contract.verify_body(body))
 def test_two_real_role_specs_and_original_startup_bound(self):
  x=config();self.assertEqual([s['unit_hash'] for s in m.contract.validate_controller(x,100)['slots']],[0x19ab11af,0x2c358c61])
  for mutate in (lambda v:v['slots'][0].update(cost=86),lambda v:v['slots'][1].update(role=0),lambda v:v.update(startup_deadline_frame=1001),lambda v:v.update(startup_wall_ms=60001),lambda v:v['slots'][1].update(command_id=v['slots'][0]['command_id'])):
   x=config();mutate(x)
   with self.assertRaises(ValueError):m.contract.validate_controller(x,100)
 def test_candidate_cannot_even_select_game_or_open_process(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(m,'EXECUTE_ENABLED',False),patch.object(m,'module',side_effect=AssertionError('No game selection')):
   runtime=m.ControllerRuntime('unused',config(),Path(folder)/'out.json','unused')
   with self.assertRaisesRegex(ValueError,'candidate_locked'):runtime.arm()
 def test_actual_cpp_controller_layout_matches_all_eighteen_fields(self):
  actual=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--controller-layout'],text=True))
  self.assertEqual(actual,m.layout_module.controller_layout());self.assertEqual(c.sizeof(m.Header),31148)
 def test_actual_cpp_record_is_decoded_without_writing_or_filling_future_actors(self):
  raw=(HERE/'controller-pair-ready.bin').read_bytes();shared=m.Tactical.from_buffer_copy(raw);before=bytes(shared);report={};m.capture(report,shared)
  self.assertEqual(bytes(shared),before);self.assertEqual(report['native']['count'],len(report['events']));self.assertEqual(report['native']['controller_input']['schema'],1);self.assertNotIn('preflight',report)
 def test_actual_slot_lookup_ignores_unrelated_preflight_selected(self):
  shared=m.Tactical.from_buffer_copy((HERE/'controller-pair-ready.bin').read_bytes());report={};m.capture(report,shared);report['preflight']={'selected':{'object_id':999999}}
  actors=m.module('mf16_actual_actor_test',HERE/'actor_binding.py');self.assertEqual(actors.actor(report,0)['object_id'],report['native']['slots'][0]['id']);report['native']['slots'][1]['admission_last']['frame']=0
  with self.assertRaisesRegex(ValueError,'not_admitted'):actors.actor(report,1)
 def test_published_prefix_regression_is_not_hidden(self):
  shared=m.Tactical();report={'events':[{'seq':1}]}
  with self.assertRaisesRegex(ValueError,'regressed'):m.capture(report,shared)
 def test_dead_host_cannot_keep_a_fresh_native_heartbeat(self):
  runtime=m.ControllerRuntime('unused',config(),'unused','unused');runtime.shared=m.Tactical();runtime.shared.phase=1;runtime.host=types.SimpleNamespace(poll=lambda:9)
  runtime._heartbeat();self.assertEqual(runtime.shared.stop_requested,1);self.assertEqual(runtime.shared.heartbeat_tick,0)
 def test_changed_binding_stops_heartbeat_without_sdk(self):
  runtime=m.ControllerRuntime('unused',config(),'unused','unused');runtime.shared=m.Tactical();runtime.shared.phase=1;runtime.host=types.SimpleNamespace(poll=lambda:None);runtime.backend=types.SimpleNamespace(k=types.SimpleNamespace(GetTickCount=lambda:55));runtime.session_path=types.SimpleNamespace(read_bytes=lambda:b'changed');runtime.session_raw=b'original'
  runtime._heartbeat();self.assertEqual(runtime.shared.stop_requested,1);self.assertEqual(runtime.shared.heartbeat_tick,55)
 def test_live_controller_mapping_cannot_be_closed(self):
  runtime=m.ControllerRuntime('unused',config(),'unused','unused');runtime.host=types.SimpleNamespace(poll=lambda:None)
  with self.assertRaisesRegex(ValueError,'live_controller_cannot_unmap'):runtime.close()
 def test_no_launch_certificate_only_after_no_intent_and_no_mapping(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder);session=path/'session.json';session.write_text(json.dumps(dict(session_id=str(uuid.uuid4()),pid=1234,run_directory=str(path),scenario={'commander_id':str(uuid.uuid4())})))
   runtime=m.ControllerRuntime(session,config(),path/'out.json','unused');proof=runtime.verified_no_launch();self.assertTrue(proof['never_attached']);self.assertEqual(proof['sdk_calls'],0)
   runtime.intent=True
   with self.assertRaisesRegex(ValueError,'not_proven'):runtime.verified_no_launch()
 def test_no_launch_refuses_open_mapping_or_any_published_event(self):
  runtime=m.ControllerRuntime('unused',config(),'unused','unused');runtime.view=42
  with self.assertRaisesRegex(ValueError,'not_proven'):runtime.verified_no_launch()
  runtime.view=None;runtime.report={'events':[{'seq':1}]}
  with self.assertRaisesRegex(ValueError,'not_proven'):runtime.verified_no_launch()
 def test_loaded_producer_table_comes_from_actual_source(self):
  reader=m.module('mf16_producer_binding_test',HERE/'producer_binding.py');entries=reader.entries();self.assertEqual(len(entries),5);self.assertEqual(entries[0]['address'],'0x7ba770');self.assertTrue(all(len(bytes.fromhex(e['expected']))==e['length'] for e in entries))
if __name__=='__main__':unittest.main()
