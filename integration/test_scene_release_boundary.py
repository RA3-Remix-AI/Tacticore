"""Scene certificate consumption; reader and raw binding are fake boundaries."""
import copy,hashlib,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import tactical_bridge as bridge

class SceneReleaseBoundary(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.run=Path(self.tmp.name)
  self.raw=self.run/'task.json';self.raw.write_text('{}');self.sidecar=self.run/'scene.json';self.sidecar.write_text('{}')
  digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  self.proof=dict(sidecar_path=str(self.sidecar),sidecar_sha256=digest(self.sidecar))
  self.verified=dict(self.proof,source_sha256=digest(self.raw),scene_disposed_control_release=True,semantics='scene_disposed_exclusive_control_released',restoration_verified=False,return_verified=False,physical_retreat_verified=False,completed=False,goal_observed=False,completion_claim=False)
  self.bound=dict(path=self.raw,sha256=digest(self.raw))
  self.entry=dict(mission_protocol='continuous_tactical_v1',executor_directory='mission-combat-v7',object_ids=[1],formation_versions={'f':1},expires_frame=4599)
  self.receipt=dict(status='failed',completed=False,goal_observed=False,restoration_verified=False,object_ids=[1],scene_disposed_control_release_verified=True,unit_results=[dict(scene_release=self.proof)],execution=dict(formation_versions={'f':1},issued_frame=100,expires_frame=4599,command_source='game_thread_bridge',interference='unknown',goal_observed=False,restoration_verified=False))
  self.b=bridge.TacticalBridge.__new__(bridge.TacticalBridge);self.b.host=types.SimpleNamespace(session=dict(run_directory=str(self.run)))
 def check(self):
  def load(path,name):
   if Path(path).name=='evidence.py':return types.SimpleNamespace(executor_schema=lambda directory:{})
   return types.SimpleNamespace(verify_path=lambda *args:self.verified)
  with patch.object(bridge,'bound_report',return_value=self.bound),patch.object(bridge,'module',side_effect=load):
   return self.b.verify_scene_release(self.receipt,self.entry)
 def test_valid_scene_release_retains_every_failure_fact(self):
  r=self.check();self.assertTrue(r['scene_disposed_control_release'])
  self.assertFalse(r['return_verified']);self.assertFalse(self.receipt['restoration_verified']);self.assertFalse(self.receipt['goal_observed'])
 def test_return_success_restoration_and_foreign_scope_never_accepted(self):
  original=copy.deepcopy(self.receipt)
  for key,value in [('status','completed'),('completed',True),('goal_observed',True),('restoration_verified',True),('object_ids',[2]),('scene_disposed_control_release_verified',False)]:
   self.receipt=copy.deepcopy(original);self.receipt[key]=value
   with self.assertRaises(ValueError):self.check()
  self.receipt=original;self.entry['executor_directory']='mission-combat-v6'
  with self.assertRaises(ValueError):self.check()
 def test_actual_reverification_and_sidecar_digest_are_mandatory(self):
  original=copy.deepcopy(self.verified)
  for key,value in [('scene_disposed_control_release',False),('source_sha256','bad'),('sidecar_sha256','bad'),('return_verified',True),('restoration_verified',True),('physical_retreat_verified',True),('completion_claim',True)]:
   self.verified=copy.deepcopy(original);self.verified[key]=value
   with self.assertRaises(ValueError):self.check()
  self.verified=original;self.sidecar.write_text('{"changed":true}')
  with self.assertRaises(ValueError):self.check()
 def test_scene_flag_cannot_exist_without_actual_sidecar(self):
  self.receipt['unit_results']=[]
  with self.assertRaises(ValueError):self.check()

if __name__=='__main__':unittest.main()
