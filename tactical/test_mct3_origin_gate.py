"""Read-only resolution and zero-lease-gate proofs, no SDK/GUI calls."""
import copy,importlib.util,json,struct,unittest
from pathlib import Path
import mission_v3_gate_no_lease as gate
HERE=Path(__file__).resolve().parent;D=HERE/'mission-combat-v3'
def load(name):
 s=importlib.util.spec_from_file_location('test_mct3_'+name,D/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class OriginGateTests(unittest.TestCase):
 def pre(self):return dict(frame=100,owner='0x2000',logic='0x3000',selected=dict(address='0x1000',object_id=7,type_hash='0x19ab11af',ai_address='0x4000',xyz=[0.,0.,210.]))
 def memory(self,changed=False):
  words={0xcd8ce4:0x3000,0x3000+0x50:101,0x3000+0x15c:0,0x1000:0xc4db60,0x1000+0xdc:7,0x1000+0x418:0x2000,0x2000+0x20:3,0x1000+4:0x5000,0x5000+8:0x19ab11af,0x1000+0x374:0x4000,0x4000+8:0x1000,0x1000+0x84:0x20000000 if changed else 0,0x1000+0x33c:0x6000}
  class Memory:
   def u32(self,a):return words[a]
   def f32(self,a):return 100.
   def read(self,a,n):return struct.pack('<fff',20.,30.,210.)
  return Memory()
 def test_implicit_contract_re_resolves_current_actor_not_stale_queue_position(self):
  m=load('mission_contract');value=dict(schema_version=1,origin_policy='implicit_actor_origin',retreat_point=dict(xyz=[999.,999.,210.],observed_frame=1,source='own_actor_history',anchor_object_id=7));r=m.validate_mission(value,self.pre(),None,4600);self.assertEqual(r['origin_policy'],'implicit_actor_origin');self.assertEqual(r['retreat_point']['xyz'],[0.,0.,210.]);self.assertEqual(value['retreat_point']['xyz'],[999.,999.,210.])
 def test_explicit_fixed_point_not_silently_refreshed(self):
  m=load('mission_contract')
  with self.assertRaises(ValueError):m.validate_mission(dict(schema_version=1,retreat_point=dict(xyz=[999.,999.,210.],observed_frame=100,source='own_actor_history',anchor_object_id=7)),self.pre(),None,4600)
 def test_final_same_actor_sample_reports_actual_frame_and_mobility(self):
  r=load('origin_resolution').resolve(self.memory(),self.pre());self.assertEqual(r['xyz'],[20.,30.,210.]);self.assertEqual(r['frame_start'],101);self.assertEqual(r['frame_end'],101);self.assertFalse(r['mutations'])
 def test_final_sample_rejects_garrison(self):
  with self.assertRaises(ValueError):load('origin_resolution').resolve(self.memory(True),self.pre())
 def fixture(self):
  p=HERE/'../acceptance/runs/20261025-105617-commander/main-mct3-01.json';r=json.loads(p.read_text(encoding='utf-8'));pre=r['preflight'];rq=r['request'];state=dict(binding_verified=True,timer=0,active=0,phase=4,error=r['native']['error'],restore_mask=16383,counters={k:0 for k in gate.COUNTERS},pid=pre['pid'],session_id=r['session_id'],command_id=rq['command_id'],task_id=rq['task_id'],seq=rq['seq'],token=rq['token'],commander_id=pre['commander_id'],object_id=pre['selected']['object_id'],unit=pre['selected']['address'],owner=pre['owner'],ai=pre['ai'],logic=pre['logic'],thread=pre['window_thread'],callback_thread=pre['window_thread'],entries=[dict(x,actual=x['expected']) for x in gate.d.trusted_entries(r)]);e=dict(protocol=gate.PROTOCOL,source_sha256='source',session_id=r['session_id'],pid=pre['pid'],command_id=rq['command_id'],task_id=rq['task_id'],seq=rq['seq'],token=rq['token'],native_host_exit=r.get('host_exit'),snapshots=[copy.deepcopy(state),copy.deepcopy(state)],completed=False,return_verified=False,restoration_verified=False);return r,e
 def test_actual_native_gate_shape_is_never_a_pre_native_or_return_claim(self):
  r,e=self.fixture();a=gate.verify(e,r,'source');self.assertTrue(a['no_actor_lease_verified'],a);self.assertTrue(a['native_host_launched']);self.assertFalse(a['return_verified']);self.assertFalse(a['restoration_verified'])
 def test_any_actor_command_or_timer_or_wrong_task_rejects_proof(self):
  for key,value in [('timer',1),('task_id','foreign'),('object_id',999)]:
   r,e=self.fixture();e['snapshots'][1][key]=value;self.assertFalse(gate.verify(e,r,'source')['no_actor_lease_verified'])
  r,e=self.fixture();e['snapshots'][1]['counters']['detach_calls']=1;self.assertFalse(gate.verify(e,r,'source')['no_actor_lease_verified'])
 def test_mask_without_fourteen_actual_original_entries_rejected(self):
  r,e=self.fixture();e['snapshots'][1]['entries']=e['snapshots'][1]['entries'][:13];self.assertFalse(gate.verify(e,r,'source')['no_actor_lease_verified'])
if __name__=='__main__':unittest.main()
