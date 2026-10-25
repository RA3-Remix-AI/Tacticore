"""New controller/mission identities stay distinct; no old raw translation."""
import copy
import importlib.util
from pathlib import Path
import sys
import struct
import unittest
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('mf13_qualification_under_test',HERE/'formation_mission_qualification.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

class NewQualification(unittest.TestCase):
 def test_empty_report_fails_closed(self):
  out=q.qualify({});self.assertEqual(out['status'],'not_passed');self.assertFalse(out['effect_verified']);self.assertFalse(out['combined_arms_verified'])
 def test_source_unknown_fails_closed(self):self.assertFalse(q.source_pins({}))
 def test_outer_envelope_cannot_supply_target(self):
  r=dict(request=dict(target_object_id=99,front_id=4,support_id=5,expires_frame=9999),native={})
  fields=q.mission_fields(r);self.assertIsNone(fields['target_object_id']);self.assertIsNone(fields['expires_frame'])
 def test_model_body_fields_do_not_replace_outer_envelope(self):
  r=dict(request=dict(command_id='outer',task_id='lease'),native=dict(mission_commit=dict(body=dict(target_id=201,front_id=100,support_id=101,hard_deadline_frame=4505))),mission_request=dict(contact_id='contact'))
  saved=copy.deepcopy(r);fields=q.mission_fields(r)
  self.assertEqual(fields['target_object_id'],201);self.assertEqual(fields['target_contact_id'],'contact');self.assertEqual(r,saved)
 def test_actor_view_never_uses_future_preflight_selected(self):
  with self.assertRaises((KeyError,ValueError)):q.actor(dict(preflight=dict(selected=dict(object_id=100))),0)
 def test_actor_view_rejects_header_not_admitted(self):
  r=dict(native=dict(slots=[dict(admission_last=dict(frame=0)),{}]))
  with self.assertRaises(ValueError):q.actor(r,0)
 def test_source_paths_only_new_q_and_new_contract(self):
  paths=q.source_paths();self.assertIn(HERE/'reserve_controller_audit.py',paths);self.assertIn(HERE/'controller_contract.py',paths)
  self.assertNotIn(HERE/'mission_contract.py',paths);self.assertNotIn(HERE/'stance_admission.py',paths)
 def test_actual_old12_report_never_requalified_as13(self):
  self.assertEqual(q.qualify(dict(native=dict(magic=0x4d463132,version=12)))['status'],'not_passed')
 def test_import_has_no_executor_authority(self):
  for name in ('OpenProcess','WriteProcessMemory','execute','attach','start_host'):self.assertFalse(hasattr(q,name))
 def test_untasked_pool_is_not_model_approach_progress(self):
  r=dict(native=dict(issued_frame=10,mission_commit=dict(status=0),controller=dict(mission_commit_frame=0)),events=[dict(seq=1)])
  self.assertIsNone(q.progress(r,'parent-task'))
 def test_never_borrowed_roles_need_no_future_actor_descriptor(self):
  n=dict(detach_calls=0,support=dict(detach_calls=0),slots=[dict(id=0),dict(id=0)],controller=dict(held_mask=0,channel_claimed=0))
  out=q.control_release(dict(native=n,events=[]))
  self.assertFalse(out['control_release_verified']);self.assertTrue(all(x['never_held'] for x in out['actors']))
 def test_still_claimed_controller_cannot_release_from_role_booleans(self):
  n=dict(detach_calls=0,support=dict(detach_calls=0),slots=[dict(id=0),dict(id=0)],controller=dict(held_mask=0,channel_claimed=1),phase=3,restore_mask=131071,active=0,overflow=0)
  self.assertFalse(q.control_release(dict(native=n,events=[]))['control_release_verified'])
 def terminal_fixture(self):
  h=q.controller.L.Header.from_buffer_copy((HERE/'controller-commit-accepted.bin').read_bytes()[:31148]);h.phase=3;h.active=h.overflow=0;h.restore_mask=131071;h.controller.held_mask=h.controller.channel_claimed=0
  n=q.controller.plain(h);return dict(native=n),dict(header_before_hex=bytes(h).hex(),header_after_hex=bytes(h).hex())
 def test_original_double_terminal_header_decode(self):
  r,t=self.terminal_fixture();self.assertTrue(q.terminal_header_audit(r,t))
 def test_mutated_terminal_header_not_binding_boolean(self):
  r,t=self.terminal_fixture();r['native']['token']+=1;t['binding_verified']=True
  self.assertFalse(q.terminal_header_audit(r,t))
 def test_one_terminal_header_not_two(self):
  r,t=self.terminal_fixture();t.pop('header_after_hex');self.assertFalse(q.terminal_header_audit(r,t))
 def test_old28132_header_not_new_controller_terminal(self):
  r,t=self.terminal_fixture();t['header_before_hex']=t['header_after_hex']=t['header_before_hex'][:28132*2]
  self.assertFalse(q.terminal_header_audit(r,t))
 def test_initial_weapon_zero_is_not_filled_from_button_or_target(self):
  r=dict(native=dict(initial_weapon_asset=0,initial_weapon_entry=0),events=[dict(kind=37,active_weapon_asset=q.AK,active_weapon_entry=0x1234)])
  self.assertFalse(q.prepare_checks(r)['initial_actual_weapon_capture'])

class PoolScheduler(unittest.TestCase):
 def fixture(self):
  rq=dict(command_id=str(uuid.UUID(int=1)),task_id=str(uuid.UUID(int=2)),token=5,seq=9)
  def e(kind,seq,frame,tick,previous,advances,count,deadline):
   origin=kind-120;w=[0x53434839,origin,5,9,*struct.unpack('<4I',uuid.UUID(int=1).bytes),*struct.unpack('<4I',uuid.UUID(int=2).bytes),0 if kind==121 else tick,0 if kind==121 else tick,frame,previous,7,20,100,0 if kind==121 else tick,advances,deadline,count,1000]
   return dict(kind=kind,seq=seq,frame=frame,tick=tick,thread=7,arg=origin,stack_words=w+[0]*104,stack_word_count=24)
  es=[dict(kind=0,seq=1,frame=10,tick=1000),e(121,2,10,1000,0xffffffff,1,0,0),e(122,3,11,1020,10,2,1,0),dict(kind=145,seq=4,frame=12,tick=1040),e(122,5,80,2300,79,71,64,4512)]
  return dict(request=rq,preflight=dict(window_thread=7),native=dict(callback_thread=7,controller=dict(reserve_start_frame=12,hard_deadline_frame=4512),pulse_requested=2300,pulse_acknowledged=2300),events=es)
 def test_pool20_and_once_clock_freeze(self):
  out=q.schedule_audit(self.fixture());self.assertTrue(out['verified'],out['checks'])
 def test_old100ms_period_not_new_pool_source(self):
  r=self.fixture();r['events'][1]['stack_words'][17]=100
  self.assertFalse(q.schedule_audit(r)['verified'])
 def test_postfreeze_capture_cannot_keep_unbound_deadline(self):
  r=self.fixture();r['events'][-1]['stack_words'][21]=0
  self.assertFalse(q.schedule_audit(r)['checks']['typed_and_original_binding'])
 def test_no_ack_as_sample_credit(self):
  r=self.fixture();r['events'][-1]['stack_words'][14]=11;r['events'][-1]['frame']=11
  self.assertFalse(q.schedule_audit(r)['checks']['actual_unique_advance'])
 def test_postcount20001_not_approved_transport(self):
  r=self.fixture();r['events'][-1]['stack_words'][22]=20001
  self.assertFalse(q.schedule_audit(r)['checks']['typed_and_original_binding'])
 def test_initial_weapon_requires_original37_entry_and_asset(self):
  r=dict(native=dict(initial_weapon_asset=q.AK,initial_weapon_entry=0x1234),events=[dict(kind=37,active_weapon_asset=q.AK,active_weapon_entry=0x1234)])
  self.assertTrue(q.prepare_checks(r)['initial_actual_weapon_capture']);r['events'][0]['active_weapon_entry']+=4
  self.assertFalse(q.prepare_checks(r)['initial_actual_weapon_capture'])

if __name__=='__main__':unittest.main()
