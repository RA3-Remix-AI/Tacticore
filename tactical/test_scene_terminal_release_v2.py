"""Synthetic MF5 ended-scene certificate; never collected from a game."""
import copy,hashlib,importlib.util,json,unittest
from pathlib import Path
import test_scene_terminal_release as old
import scene_terminal_release_v2 as reader
P=Path(__file__).resolve().parent

def fixture():
 r,e=old.fixture('mission-formation-v4');p=reader.PROFILES['mission-formation-v5']
 r.update(native_binary_sha256=p['binary'],native_host_sha256=p['host'],native_source_sha256=p['cpp'],native_shared_sha256=p['shared'])
 r['native'].update(returned_frame=0,return_calls=0,return_verified=0)
 r['native']['support'].update(return_calls=0,returned=0)
 e.update(protocol=reader.PROTOCOL,directory='mission-formation-v5',native_binary_sha256=p['binary'],reader_sha256=reader.sha(reader.__file__))
 for sample in e['snapshots']:
  for name in ('native_before','native_after'):
   sample[name].update(magic=p['magic'],version=5,returned_frame=0,return_calls=0,return_verified=0)
   sample[name]['support'].update(return_calls=0,returned=0)
 e['source_sha256']=hashlib.sha256(json.dumps(r).encode()).hexdigest()
 return r,e

class SceneV2(unittest.TestCase):
 def test_actual_frozen_five_profile_and_synthetic_closed_scene_only_release(self):
  r,e=fixture();result=reader.verify(e,r,e['source_sha256'])
  self.assertTrue(result['scene_disposed_control_release'],result)
  for key in ('return_verified','restoration_verified','physical_retreat_verified','completed','goal_observed','completion_claim'):self.assertIs(result[key],False)
  self.assertEqual(len(reader.expected_entries(r)),13)

 def test_both_actor_and_closed_scene_identity_are_still_required(self):
  for change in ('support','live','timer','wrong_binary','claimed_return'):
   r,e=fixture()
   if change=='support':
    for sample in e['snapshots']:
     sample['native_before']['support']['id']+=1;sample['native_after']['support']['id']+=1
   elif change=='live':
    for sample in e['snapshots']:
     sample['scene_before']['frame']=100;sample['scene_after']['frame']=100
   elif change=='timer':e['snapshots'][0]['timer']=1
   elif change=='wrong_binary':r['native_binary_sha256']='0'*64
   else:e['return_verified']=True
   self.assertFalse(reader.verify(e,r,e['source_sha256'])['scene_disposed_control_release'],change)

 def test_common_and_support_offsets_match_actual_five_ctypes(self):
  spec=importlib.util.spec_from_file_location('scene_v2_actual_five',P/'mission-formation-v5/native_layout.py');layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
  for name,offset in reader.COMMON.items():self.assertEqual(getattr(layout.Tactical,name).offset,offset,name)
  self.assertEqual(layout.Tactical.support.offset,484);self.assertEqual(layout.Tactical.events.offset,27900)
  self.assertEqual(reader.PROFILES['mission-formation-v5']['header'],27900)

if __name__=='__main__':unittest.main()
