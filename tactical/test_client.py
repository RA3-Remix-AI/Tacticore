import importlib.util,unittest,uuid
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('tactical_client',Path(__file__).parent/'client.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Memory:
 def u32(self,a):
  for base,oid in [(0x10000,1),(0x20000,2),(0x30000,3)]:
   if a in {base,base+0xdc,base+0x418,base+0x84}:return {base:0xc4db60,base+0xdc:oid,base+0x418:0x2000,base+0x84:0}[a]
  return 0 if a==0x115c else 1000
 def close(self):pass
class ModelBoundary(unittest.TestCase):
 def executor(self):
  e=m.TacticalExecutor('unused','unused','57e668b4-4d89-43bd-bc92-0dd436f046ef');e.state='running';e._binding=lambda:None;e.session={'session_id':'65bb88da-f5dc-48be-a3c1-5b6ee83cb017'};e.logic=0x1000;e.owner=0x2000;e.native_personality='p';e.formations={'f':dict(version=1,object_ids=[1,2],role='mixed')};e.regions={'region':dict(xyz=[80.,0.,210.],observed_frame=1000)};e.contacts={'contact_c':dict(contact_id='contact_c',currently_visible=True,relation='enemy',region_id='region',role='infantry')};e.visibility_proof_path='proof';e.capabilities={'attack':('main_attack',),'raid':('harass_economy',),'combined_arms':('coordinate_force',)}
  return e
 def task(self):return dict(task_id=uuid.uuid4().hex,command_id=str(uuid.uuid4()),seq=1,module='attack',purpose='main_attack',target_region='region',target_contact_id='contact_c',formation_ids=['f'],formation_versions={'f':1},required_roles=['infantry'],force_fraction=.5,expires_frame=1600)
 def preflight(self):return dict(owner='0x2000',personality='p',units=[dict(address='0x10000',object_id=1,eligible=True,type_hash='0x19ab11af',xyz=[0.,0.,210.]),dict(address='0x20000',object_id=2,eligible=True,type_hash='0x2c358c61',xyz=[-40.,0.,210.])])
 def call(self,e,t):
  with patch.object(m.backend,'readiness',return_value=(self.preflight(),None,None,None,None,None,Memory())):return e.submit(t)
 def test_empty_single_actor_role_rejected(self):
  e=self.executor();t=self.task();t['required_roles']=[];self.assertEqual(self.call(e,t)['reason_code'],'single_actor_role_required')
 def test_ambiguous_single_actor_role_rejected(self):
  e=self.executor();t=self.task();t['required_roles']=['infantry','anti_air'];self.assertEqual(self.call(e,t)['reason_code'],'single_actor_role_required')
 def test_air_contact_cannot_pick_conscript(self):
  e=self.executor();e.contacts['contact_c']['role']='air';self.assertEqual(self.call(e,self.task())['reason_code'],'air_target_requires_anti_air')
 def test_flak_required_never_picks_nearer_conscript(self):
  e=self.executor();t=self.task();t['required_roles']=['anti_air'];chosen=[]
  def queue(**kwargs):
   chosen.append(kwargs['object_id']);value=dict(command_id=kwargs['command_id'],task_id=kwargs['task_id'],status='queued',accepted=True,started=False,completed=False,object_ids=[kwargs['object_id']]);e.ledger[kwargs['command_id']]=value;return dict(value)
  e.submit_attack_probe=queue;r=self.call(e,t);self.assertEqual(chosen,[2]);self.assertEqual(r['actual_roles'],['anti_air'])
 def test_fresh_private_contact_selects_actor_without_region_centroid_bias(self):
  e=self.executor();t=self.task();e.formations['f']['object_ids'].append(3);e.private_visible_positions={'contact_c':dict(xyz=[500.,0.,210.],observed_frame=1000)};pre=self.preflight();pre['units'].append(dict(address='0x30000',object_id=3,eligible=True,type_hash='0x19ab11af',xyz=[490.,0.,210.]));chosen=[]
  def queue(**kwargs):
   chosen.append(kwargs['object_id']);value=dict(command_id=kwargs['command_id'],task_id=kwargs['task_id'],status='queued',accepted=True,started=False,completed=False,object_ids=[kwargs['object_id']]);e.ledger[kwargs['command_id']]=value;return dict(value)
  e.submit_attack_probe=queue
  with patch.object(m.backend,'readiness',return_value=(pre,None,None,None,None,None,Memory())):r=e.submit(t)
  self.assertEqual(chosen,[3]);self.assertEqual(r['selection_basis'],'fresh_private_visible_contact');self.assertNotIn('selection_point',r)
 def test_no_evidence_never_calls_backend(self):
  e=self.executor();e.capabilities={}
  with patch.object(m.backend,'readiness',side_effect=AssertionError('must not read/dispatch')):self.assertEqual(e.submit(self.task())['reason_code'],'tactical_capability_not_verified')
 def test_version_change_rejects_before_dispatch(self):
  e=self.executor();t=self.task();t['formation_versions']={'f':2};self.assertEqual(self.call(e,t)['reason_code'],'formation_version_changed')
 def test_expired_rejects_before_dispatch(self):
  e=self.executor();t=self.task();t['expires_frame']=900;self.assertEqual(self.call(e,t)['reason_code'],'task_expiry_bounds')
 def test_stale_region_rejects(self):
  e=self.executor();e.regions['region']['observed_frame']=800;self.assertEqual(self.call(e,self.task())['reason_code'],'target_region_not_current_known')
 def test_nonvisible_target_rejects(self):
  e=self.executor();e.contacts={};self.assertEqual(self.call(e,self.task())['reason_code'],'current_visible_target_required')
 def test_harass_requires_economy_target(self):
  e=self.executor();t=self.task();t.update(module='raid',purpose='harass_economy');self.assertEqual(self.call(e,t)['reason_code'],'current_visible_target_required')
 def test_inflight_formation_rejects(self):
  e=self.executor();e.reserved_units={1};self.assertEqual(self.call(e,self.task())['reason_code'],'formation_overlap_or_inflight')
 def test_opaque_address_not_an_acceptable_target(self):
  e=self.executor();t=self.task();t['target_contact_id']='0x123400';self.assertEqual(self.call(e,t)['reason_code'],'current_visible_target_required')
 def test_accepted_keeps_original_hex_task_and_is_not_started(self):
  e=self.executor();t=self.task()
  def queue(**kwargs):
   value=dict(command_id=kwargs['command_id'],task_id=kwargs['task_id'],status='queued',accepted=True,started=False,completed=False,object_ids=[kwargs['object_id']]);e.ledger[kwargs['command_id']]=value;return dict(value)
  e.submit_attack_probe=queue;result=self.call(e,t);self.assertEqual(result['task_id'],t['task_id']);self.assertFalse(result['started']);self.assertFalse(result['completed']);self.assertEqual(result['expires_frame'],1600)
 def test_contract_point_six_is_allocated_with_explicit_cap(self):
  e=self.executor();t=self.task();t['force_fraction']=.6
  def queue(**kwargs):
   value=dict(command_id=kwargs['command_id'],task_id=kwargs['task_id'],status='queued',accepted=True,started=False,completed=False,object_ids=[kwargs['object_id']]);e.ledger[kwargs['command_id']]=value;return dict(value)
  e.submit_attack_probe=queue;r=self.call(e,t);self.assertTrue(r['accepted']);self.assertEqual(r['requested_force_fraction'],.6);self.assertEqual(r['allocation_cap_fraction'],.5);self.assertEqual(r['allocated_force_fraction'],.5)
 def test_point_zero_one_too_small_never_dispatches(self):
  e=self.executor();t=self.task();t['force_fraction']=.01;self.assertEqual(self.call(e,t)['reason_code'],'force_budget_too_small')
 def test_garrison_is_excluded_from_force_budget(self):
  e=self.executor();t=self.task();original=Memory.u32
  with patch.object(Memory,'u32',lambda self,a:0x20000000 if a==0x10084 else original(self,a)):
   self.assertEqual(self.call(e,t)['reason_code'],'force_budget_too_small')
if __name__=='__main__':unittest.main()
