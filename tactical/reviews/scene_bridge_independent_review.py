"""Actual Root bridge + actual scene reader coupling; synthetic sidecars only.

Run from integration cwd. No collect(), process open, native launch, SDK, GUI,
model or endpoint is called. Source fixtures seed only saved immutable RO facts.
"""
import copy,hashlib,importlib.util,json,subprocess,sys,tempfile,types,unittest,uuid
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent.parent;B=P.parent
sys.path.insert(0,str(B/'integration'));sys.path.insert(0,str(P))
import tactical_bridge as bridge
import scene_terminal_release as reader
from test_scene_terminal_release import fixture as scene_fixture
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
class ActualSceneCoupling(unittest.TestCase):
 def build(self,family='mission-combat-v7'):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.run=Path(temp.name)/'run';self.run.mkdir();self.family=family
  self.raw,self.side=scene_fixture(family);pre=self.raw['preflight'];n=self.raw['native'];rq=self.raw['request'];schema=bridge.module(P/'evidence.py','scene_coupling_schema').executor_schema(family)
  parent_command,parent_task=str(uuid.uuid4()),str(uuid.uuid4());objects=[pre['selected']['object_id']]+([pre['support']['object_id']] if family=='mission-formation-v4' else []);suffix='formation' if len(objects)==2 else str(objects[0]);child_command=str(uuid.uuid5(uuid.UUID(parent_command),suffix));child_task=str(uuid.uuid5(uuid.UUID(parent_task),suffix))
  for x in [rq,n]:x.update(command_id=child_command,task_id=child_task)
  for sample in self.side['snapshots']:
   for key in ['native_before','native_after']:sample[key].update(command=child_command,task=child_task)
  folder=P/family
  for key,file in [('native_binary_sha256',folder/'bin'/schema['dll']),('native_host_sha256',folder/'bin/tactical_host.exe'),('wrapper_sha256',folder/schema.get('wrapper_filename','lease.py')),('native_source_sha256',folder/'lease.cpp'),('native_shared_sha256',folder/'shared.h')]:self.raw[key]=digest(file)
  self.entry=dict(mission_protocol='continuous_tactical_v1',executor_directory=family,module='combined_arms' if len(objects)==2 else 'attack',purpose='coordinate_force' if len(objects)==2 else 'main_attack',object_ids=objects,command_id=parent_command,task_id=parent_task,formation_versions={'force':1},dispatch_frame=pre['frame'],expires_frame=n['mission_deadline_frame'],target_contact_id=rq['target_contact_id'])
  self.host=types.SimpleNamespace(session=dict(run_directory=str(self.run),pid=pre['pid'],mod_sha256=self.raw['package_sha256']),binding=types.SimpleNamespace(session_id=self.raw['session_id'],commander_id=pre['commander_id'],player_id=3))
  self.b=bridge.TacticalBridge.__new__(bridge.TacticalBridge);self.b.host=self.host;self.rawpath=self.run/'raw.json';self.sidepath=self.run/'sidecar.json'
  self.receipt=dict(status='failed',completed=False,goal_observed=False,restoration_verified=False,started=True,object_ids=objects,scene_disposed_control_release_verified=True,unit_results=[dict(report=str(self.rawpath),scene_release={})],execution=dict(formation_versions={'force':1},issued_frame=n['issued_frame'],expires_frame=self.entry['expires_frame'],command_source='game_thread_bridge',interference='unknown',goal_observed=False,restoration_verified=False));self.write()
 def write(self):
  self.rawpath.write_text(json.dumps(self.raw),encoding='utf-8');self.side['source_sha256']=digest(self.rawpath);self.sidepath.write_text(json.dumps(self.side),encoding='utf-8');self.receipt['unit_results'][0]['scene_release']=dict(sidecar_path=str(self.sidepath),sidecar_sha256=digest(self.sidepath))
 def check(self):return self.b.verify_scene_release(self.receipt,self.entry)
 def test_actual_bound_report_and_actual_reader_both_profiles(self):
  for family in reader.PROFILES:
   self.build(family);result=self.check();self.assertTrue(result['scene_disposed_control_release']);self.assertEqual(result['source_sha256'],digest(self.rawpath));self.assertEqual(result['sidecar_sha256'],digest(self.sidepath))
   for k in ['return_verified','restoration_verified','physical_retreat_verified','completed','goal_observed','completion_claim']:self.assertIs(result[k],False)
 def test_actual_clock_guard_rejects_before_source_reader(self):
  self.build();self.entry['dispatch_frame']=self.raw['native']['issued_frame']+1
  with self.assertRaisesRegex(ValueError,'issue clock'):self.check()
 def test_actual_token_guard_rejects_even_with_correct_sidecar_digest(self):
  self.build()
  for s in self.side['snapshots']:
   s['native_before']['token']+=1;s['native_after']['token']+=1
  self.write()
  with self.assertRaisesRegex(ValueError,'actual proof'):self.check()
 def test_actual_foreign_session_and_child_uuid_rejected(self):
  for section,key,value in [('preflight','pid',1),('preflight','commander_id',str(uuid.uuid4())),('request','command_id',str(uuid.uuid4())),('native','task_id',str(uuid.uuid4()))]:
   self.build();self.raw[section][key]=value;self.write()
   with self.assertRaises(ValueError):self.check()
 def test_actual_path_guards_and_mutated_sidecar_rejected(self):
  self.build();outside=self.run.parent/'outside.json';outside.write_text(self.sidepath.read_text());self.receipt['unit_results'][0]['scene_release'].update(sidecar_path=str(outside),sidecar_sha256=digest(outside))
  with self.assertRaisesRegex(ValueError,'outside match|changed'):self.check()
  self.build();self.sidepath.write_text('{}')
  with self.assertRaisesRegex(ValueError,'outside match|changed'):self.check()
  self.build();outside_raw=self.run.parent/'outside-raw.json';outside_raw.write_text(self.rawpath.read_text());self.receipt['unit_results'][0]['report']=str(outside_raw)
  with self.assertRaisesRegex(ValueError,'outside current match'):self.check()
 def test_actual_receipt_or_sidecar_cannot_claim_return_or_success(self):
  for key in ['completed','goal_observed','restoration_verified']:
   self.build();self.receipt[key]=True
   with self.assertRaises(ValueError):self.check()
  for key in ['return_verified','completed','goal_observed']:
   self.build();self.side[key]=True;self.write()
   with self.assertRaises(ValueError):self.check()
 def test_version_and_live_pause_do_not_release(self):
  self.build();self.receipt['execution']['formation_versions']={'force':2}
  with self.assertRaisesRegex(ValueError,'execution binding'):self.check()
  self.build()
  for sample in self.side['snapshots']:
   for world in [sample['scene_before'],sample['scene_after']]:world.update(frame=200,mode=2,paused_raw=3)
  self.write()
  with self.assertRaisesRegex(ValueError,'actual proof'):self.check()
 def test_fresh_integration_import_profiles_and_client_guard_without_commands(self):
  with patch.object(subprocess,'Popen',side_effect=AssertionError('No process may launch')) as launch:
   actual=bridge.module(P/'client.py','scene_review_actual_tactical_client');instance=actual.TacticalExecutor.__new__(actual.TacticalExecutor)
   for family,other in [('mission-combat-v7','mission-combat-v6'),('mission-formation-v4','mission-formation-v3')]:
    schema,backend=actual.runtime_backend(family);self.assertEqual(schema['restore_mask'],reader.PROFILES[family]['mask']);self.assertEqual(backend.Tactical.events.offset,reader.PROFILES[family]['header']);self.assertIsNone(instance._scene_release(other,{'native':dict(phase=4,error=31,issued_frame=1)},'unused'));self.assertIsNone(instance._scene_release(family,{'native':dict(phase=3,error=0,issued_frame=1)},'unused'))
   loaded=bridge.module(P/'scene_terminal_release.py','scene_review_fresh_reader');self.assertEqual(Path(loaded.__file__).resolve(),(P/'scene_terminal_release.py').resolve());self.assertEqual(set(loaded.PROFILES),{'mission-combat-v7','mission-formation-v4'});self.assertEqual(launch.call_count,0)
if __name__=='__main__':unittest.main()
