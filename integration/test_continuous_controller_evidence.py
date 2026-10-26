"""New synthetic envelopes test the parent reader boundary, not Native authority.

The physical/source qualifier is explicitly mocked here; its own adversarial and
actual typed-trace tests are independent. No recorded game report is rewritten.
"""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

import continuous_evidence as m
import test_formation16_terminal as frozen_entries


class ControllerReader(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.run=Path(self.tmp.name);self.path=self.run/'new-controller.json'
  self.real=m._qualifier('mission-formation-v14','controller_reader_typed_wire_only')
  verified=lambda *a,**k:dict(verified=True)
  self.q=SimpleNamespace(source_pins=lambda r:True,actor=lambda r,role:dict(object_id=[101,102][role]),controller=SimpleNamespace(L=self.real.controller.L,plain=self.real.controller.plain,ident=self.real.controller.ident,RS_KINDS=set(),reserve_record=lambda e:e,clock_audit=verified,cohort_audit=verified,borrow_audit=verified,parent_request_audit=verified),control_release=lambda r:dict(control_release_verified=True,restoration_verified=False,return_verified=True),qualify=lambda r:dict(effect_verified=False,restoration_verified=False,checks=dict(actual_effect=False)),progress=lambda r,task:dict(revision=r['events'][-1]['seq'],observed_frame=r['events'][-1]['frame'],mission_id=task))
  for name in ('input_audit','producer_arm_audit','producer_audit','ready_audit','stop_audit','origin_audit','precommit_audit','commit_audit','target_proof_audit','spawn_wait_audit'):setattr(self.q.controller,name,verified)
  self.addCleanup(patch.stopall);patch.object(m,'_qualifier',return_value=self.q).start();patch.object(m,'verify_formation_release',return_value=None).start()
  self.fixture()
 def fixture(self,version=14):
  family='mission-formation-v'+str(version);magic=m.CONTROLLER_FAMILIES[family][0]
  session=str(uuid.UUID(int=1));commander=str(uuid.UUID(int=2));parent=str(uuid.UUID(int=3));task=str(uuid.UUID(int=4));outer=str(uuid.UUID(int=5));lease=str(uuid.UUID(int=6));child=str(uuid.uuid5(uuid.UUID(parent),'formation'));child_task=str(uuid.uuid5(uuid.UUID(task),'formation'))
  body=self.real.controller.L.MissionCommitBody13()
  for key,value in dict(controller=outer,lease=lease,parent_command=parent,parent_task=task,command=child,task=child_task).items():getattr(body,key)[:]=struct.unpack('<4I',uuid.UUID(value).bytes)
  body.seq=7;body.front_id=101;body.support_id=102;body.reserve_start_frame=100;body.reserve_deadline_frame=550 if version>=16 else 400;body.hard_deadline_frame=4600
  prefix=bytes(body)[:252];digest=hashlib.sha256(prefix).digest();body.digest_sha256[:]=struct.unpack('<8I',digest)
  public=dict(formation_versions=[['formation_example',1]],target_contact_id='contact_example',expires_frame=4600)
  self.r=dict(session_id=session,package_sha256='mod',executable_sha256=m.EXPECTED,preflight=dict(pid=123,commander_id=commander,player_id=3,window_thread=8),request=dict(command_id=outer,task_id=lease,seq=9,token=10),native=dict(magic=magic,version=version,pid=123,thread=8,session_id=session,commander_id=commander,command_id=outer,task_id=lease,seq=9,token=10,issued_frame=100,mission_deadline_frame=4600,mission_commit=dict(generation=2,status=1,ack_frame=200,body=self.real.controller.plain(body)),controller=dict(lease_issued_frame=100,reserve_start_frame=100,reserve_deadline_frame=400,hard_deadline_frame=4600,mission_commit_frame=200,approach_frame=200),detach_calls=1,support=dict(detach_calls=1),phase=4,active=0),mission_request=dict(parent_command_id=parent,parent_task_id=task,child_command_id=child,child_task_id=child_task,seq=7,commit_body_hex=bytes(body).hex(),commit_prefix_hex=prefix.hex(),digest_sha256=digest.hex(),public_command=public,public_command_path=str(self.run/'original-public.json'),public_command_sha256='source'),events=[dict(kind=14,tag=1,role=0,seq=1,frame=100),dict(kind=14,tag=1,role=1,seq=2,frame=101),dict(kind=153,seq=3,frame=200)],status='finished',host_exit=0)
  self.entry=dict(executor_directory=family,module='combined_arms',command_id=parent,task_id=task,seq=7,object_ids=[101,102],formation_versions={'formation_example':1},target_contact_id='contact_example',dispatch_frame=190,expires_frame=4600,controller_id=outer,lease_id=lease)
  self.r['native']['controller']['reserve_deadline_frame']=body.reserve_deadline_frame
  self.host=SimpleNamespace(session=dict(run_directory=str(self.run),pid=123,mod_sha256='mod'),binding=SimpleNamespace(session_id=session,commander_id=commander,player_id=3))
  self.receipt=dict(active_report=str(self.path),object_ids=[101,102],started=True,issued_frame=200,execution=dict(issued_frame=200),status='failed')
  self.write()
 def write(self):self.path.write_text(json.dumps(self.r),encoding='utf-8')
 def test_both_families_keep_lease_older_than_actual_model_issue(self):
  for version in (13,14,15,16,17):
   self.fixture(version);out=m.bound_report(self.host,self.receipt,self.entry,terminal=True)
   self.assertEqual((out['lease_issued_frame'],out['model_issued_frame']),(100,200));self.assertTrue(out['model_started'])
 def test_receipt_cannot_use_outer_lease_issue_as_model_issue(self):
  self.receipt['execution']['issued_frame']=100
  with self.assertRaisesRegex(ValueError,'confused lease'):m.bound_report(self.host,self.receipt,self.entry)
 def scene_fixture(self):
  self.fixture(17);self.r['host_exit']=9;self.r['native']['error']=31;self.r['events'].append(dict(kind=4,seq=4,frame=0,native_error=31));self.write()
  path=self.run/'original-scene-sidecar.json';path.write_text('{"actual_reader_test_boundary":true}')
  proof=dict(sidecar_path=str(path),sidecar_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),control_release_verified=True,scene_disposed_control_release=True,actors=[dict(role=r,object_id=oid,released=True,returned=False,disposed=False) for r,oid in enumerate((101,102))])
  proof.update({k:False for k in ('restoration_verified','return_verified','physical_retreat_verified','completed','goal_observed','completion_claim')})
  self.receipt['unit_results']=[dict(report=str(self.path),object_ids=[101,102],scene_release=copy.deepcopy(proof))]
  self.q.control_release=lambda r:dict(control_release_verified=False)
  original=m._load
  reader=SimpleNamespace(verify_path=lambda *args:copy.deepcopy(proof))
  patch.object(m,'_load',side_effect=lambda path,name:reader if name=='continuous_exact_scene_release17' else original(path,name)).start()
  return proof
 def test17_scene_certificate_releases_exclusivity_without_rewriting_raw(self):
  self.scene_fixture();before=self.path.read_bytes();out=m.terminal_facts(self.host,self.receipt,self.entry)
  self.assertTrue(out['control_release']['control_release_verified']);self.assertFalse(out['control_release']['restoration_verified']);self.assertFalse(out['qualification']['effect_verified']);self.assertEqual(self.path.read_bytes(),before)
 def test17_scene_receipt_boolean_does_not_replace_reader(self):
  proof=self.scene_fixture();proof['control_release_verified']=False
  with self.assertRaisesRegex(ValueError,'closure unproven'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test17_scene_sidecar_must_bind_original_raw_digest(self):
  proof=self.scene_fixture();proof['source_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'closure unproven'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test17_scene_sidecar_bytes_must_match_receipt_digest(self):
  self.scene_fixture();self.receipt['unit_results'][0]['scene_release']['sidecar_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'digest changed'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test17_scene_false_physical_home_or_return_claim_rejected(self):
  proof=self.scene_fixture();proof['return_verified']=True
  with self.assertRaisesRegex(ValueError,'physical outcome'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test17_scene_completion_never_inherits_failed_qualification(self):
  self.scene_fixture();self.receipt['status']='completed'
  with self.assertRaisesRegex(ValueError,'not mission completion'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test17_scene_wrong_actor_or_foreign_sidecar_rejected(self):
  proof=self.scene_fixture();proof['actors'][0]['object_id']=999
  with self.assertRaisesRegex(ValueError,'actor release changed'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test_parent_uuid_hex_is_compared_without_rewriting_raw(self):
  self.entry['task_id']=uuid.UUID(self.entry['task_id']).hex;self.entry['command_id']=uuid.UUID(self.entry['command_id']).hex;before=self.path.read_bytes()
  self.assertTrue(m.bound_report(self.host,self.receipt,self.entry)['model_started']);self.assertEqual(before,self.path.read_bytes())
 def test_different_family_or_foreign_controller_rejected(self):
  self.entry['executor_directory']='mission-formation-v13'
  with self.assertRaisesRegex(ValueError,'namespace'):m.bound_report(self.host,self.receipt,self.entry)
  self.entry['executor_directory']='mission-formation-v14';self.entry['controller_id']=str(uuid.uuid4())
  with self.assertRaisesRegex(ValueError,'another controller'):m.bound_report(self.host,self.receipt,self.entry)
 def test_binary_body_and_digest_are_original_not_echo_boolean(self):
  self.r['mission_request']['commit_prefix_hex']='00'*252;self.write()
  with self.assertRaisesRegex(ValueError,'seal'):m.bound_report(self.host,self.receipt,self.entry)
 def test_source_verification_cannot_be_skipped(self):
  self.q.source_pins=lambda r:False
  with self.assertRaisesRegex(ValueError,'source bundle'):m.bound_report(self.host,self.receipt,self.entry)
 def test_actual_admission_and_borrow_still_required(self):
  self.q.controller.borrow_audit=lambda *a:dict(verified=False)
  with self.assertRaisesRegex(ValueError,'lease admission'):m.bound_report(self.host,self.receipt,self.entry)
 def test15_passive_wait_cannot_bypass_original_native_cohort_binding(self):
  self.fixture(15);self.q.controller.spawn_wait_audit=lambda *a:dict(verified=False)
  with self.assertRaisesRegex(ValueError,'lease admission'):m.bound_report(self.host,self.receipt,self.entry)
 def test_original_paid_receipts_origin_and_physical_ready_are_not_header_masks(self):
  for name in ('producer_audit','origin_audit','ready_audit','stop_audit'):
   original=getattr(self.q.controller,name);setattr(self.q.controller,name,lambda *a:dict(verified=False))
   with self.assertRaisesRegex(ValueError,'lease admission'):m.bound_report(self.host,self.receipt,self.entry)
   setattr(self.q.controller,name,original)
 def test_common153_cannot_replace_typed_commit_and_original_target_proof(self):
  self.q.controller.commit_audit=lambda *a:dict(verified=False)
  self.assertIsNone(m.bound_report(self.host,self.receipt,self.entry))
  with self.assertRaisesRegex(ValueError,'committed scope'):m.bound_report(self.host,self.receipt,self.entry,terminal=True)
 def test_deadline_cannot_be_extended_or_shortened(self):
  for expiry in (4599,4601):
   self.entry['expires_frame']=expiry
   with self.assertRaisesRegex(ValueError,'deadline'):m.bound_report(self.host,self.receipt,self.entry)
 def test16_existing_reserve450_does_not_renew_original_hard4500(self):
  self.fixture(16);self.r['native']['controller']['reserve_deadline_frame']=550;self.write()
  self.assertEqual(m.bound_report(self.host,self.receipt,self.entry)['lease_issued_frame'],100)
  self.entry['expires_frame']=4750
  with self.assertRaisesRegex(ValueError,'deadline'):m.bound_report(self.host,self.receipt,self.entry)
 def test_pending_never_manufactures_progress_or_acceptance(self):
  self.r['native']['mission_commit']['status']=0;self.r['events'].pop();self.receipt['started']=False;self.write()
  self.assertIsNone(m.bound_report(self.host,self.receipt,self.entry));self.assertIsNone(m.progress_evidence(self.host,self.receipt,self.entry,dict(revision=2,observed_frame=101)))
  self.receipt['started']=True
  with self.assertRaisesRegex(ValueError,'falsely started'):m.bound_report(self.host,self.receipt,self.entry)
 def test_missing_original153_is_not_terminal_acceptance(self):
  self.r['events'].pop();self.write()
  self.assertIsNone(m.bound_report(self.host,self.receipt,self.entry))
  with self.assertRaisesRegex(ValueError,'original153'):m.bound_report(self.host,self.receipt,self.entry,terminal=True)
 def test_failed_mission_does_not_relabel_stance_restore_as_true(self):
  out=m.terminal_facts(self.host,self.receipt,self.entry);self.assertFalse(out['qualification']['restoration_verified']);self.assertFalse(out['control_release']['restoration_verified'])
 def test_effectless_completed_receipt_rejected(self):
  self.receipt['status']='completed'
  with self.assertRaisesRegex(ValueError,'completion lacks'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test_progress_before153_rejected_and_canonical_parent_id_returned(self):
  with self.assertRaisesRegex(ValueError,'before original153'):m.progress_evidence(self.host,self.receipt,self.entry,dict(revision=2,observed_frame=101))
  self.entry['task_id']=uuid.UUID(self.entry['task_id']).hex;progress=dict(revision=3,observed_frame=200,mission_id=str(uuid.UUID(self.entry['task_id'])))
  self.assertIsNotNone(m.progress_evidence(self.host,self.receipt,self.entry,progress))
 def reject(self):
  n=self.r['native'];n['mission_commit'].update(status=2,reason=3);n['controller'].update(mission_commit_frame=0,approach_frame=0)
  for k in ('attack_calls','attack_facade_calls','attack_private_calls','toggle_calls','toggle_hook_calls','damage_count','commit_own_calls'):n[k]=0
  self.r['events'][-1]['kind']=154;self.receipt.update(started=False,issued_frame=0,execution=dict(issued_frame=0));self.write()
 def test_rejection_before153_is_not_exclusive_control_never_held(self):
  self.reject();out=m.pre_dispatch_facts(self.host,self.receipt,self.entry);p=out['proof']
  self.assertTrue(p['model_mission_never_started']);self.assertTrue(p['controller_lease_was_held']);self.assertFalse(p['exclusive_control_never_held']);self.assertEqual(p['model_combat_sdk_calls'],0);self.assertEqual(p['protocol'],'mf14_model_rejection_after_actual_reserve_v1');self.assertFalse(p['restoration_verified'])
 def test_rejected_model_with_combat_or_no_release_cannot_claim_no_dispatch(self):
  self.reject();self.r['native']['attack_calls']=1;self.write()
  with self.assertRaisesRegex(ValueError,'combat counters'):m.pre_dispatch_facts(self.host,self.receipt,self.entry)
  self.r['native']['attack_calls']=0;self.write();self.q.control_release=lambda r:dict(control_release_verified=False)
  with self.assertRaisesRegex(ValueError,'release unproven'):m.pre_dispatch_facts(self.host,self.receipt,self.entry)
 def test_unpublished_mission_none_stays_fail_closed(self):
  self.r['mission_request']=None;self.write()
  with self.assertRaisesRegex(ValueError,'publication missing'):m.pre_dispatch_facts(self.host,self.receipt,self.entry)
 def test_terminal_requires_actual_host_exit_and_finished(self):
  self.r['host_exit']=None;self.write()
  with self.assertRaisesRegex(ValueError,'terminal unproven'):m.terminal_facts(self.host,self.receipt,self.entry)
 def test_failed_exited_host_does_not_prevent_independently_verified_release(self):
  self.r['host_exit']=9;self.write();out=m.terminal_facts(self.host,self.receipt,self.entry)
  self.assertTrue(out['control_release']['control_release_verified']);self.assertFalse(out['qualification']['restoration_verified'])
  self.r['host_exit']=False;self.write()
  with self.assertRaisesRegex(ValueError,'terminal unproven'):m.terminal_facts(self.host,self.receipt,self.entry)


class Controller13Restoration(frozen_entries.Formation16Terminal):
 family='mission-formation-v13'
 hooks=17


class Controller14Restoration(frozen_entries.Formation16Terminal):
 family='mission-formation-v14'
 hooks=17


if __name__=='__main__':unittest.main()
