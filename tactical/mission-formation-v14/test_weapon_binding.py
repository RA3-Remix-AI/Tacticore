"""Own live authorization and immutable asset reads; never read stale entry memory."""
import importlib.util,struct,types,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf14_weapon_wrapper_test',HERE/'lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class WeaponBinding(unittest.TestCase):
 def fixture(self,*,present=True,asset=0x447ea26e,hp=100.):
  r=m.ControllerRuntime('unused',{},'unused','unused');n=dict(unit=0x55000,object_id=803,owner=0x66000,weapon_entry=0x22000,weapon_template=0x33000,weapon_slot=0x44000,attack_issued_frame=90)
  r.report=dict(native=n,session_id='current-session',preflight=dict(pid=100,logic=hex(0x10000)));r.shared=types.SimpleNamespace(**n);self.reads=[];frames=iter([100,101])
  values={0x55000+0x33c:0x77000,0x77004:struct.unpack('<I',struct.pack('<f',hp))[0],0x33000:0xc37534,0x33004:0x88000,0x88000:0x99000,0x99000:0x94d4d96e,0x99004:asset}
  def read(address):
   self.reads.append(address)
   if address==0x10050:return next(frames)
   if 0x22000<=address<0x22100:raise AssertionError('Weapon entry memory must not be dereferenced')
   return values[address]
  r.memory=types.SimpleNamespace(u32=read)
  actor=dict(object_id=803,address='0x55000',type_hash='0x19ab11af',owner_address='0x66000')
  r.backend=types.SimpleNamespace(load_catalog=lambda:{},own_candidates=lambda *a:dict(frame_start=100,frame_end=100,candidates=[actor] if present else []))
  return r
 def test_asset_double_read_uses_actual_clock_and_preserves_raw(self):
  r=self.fixture();r._capture_weapon_binding();binding=r.report['weapon_asset_binding']
  self.assertEqual(binding['observed_frame'],101);self.assertNotEqual(binding['observed_frame'],90);self.assertEqual(binding['raw_before'],binding['raw_after']);self.assertEqual(binding['asset_id'],'0x447ea26e');self.assertFalse(binding['entry_memory_read']);self.assertEqual(binding['own_frame_start'],100)
 def test_absent_owned_actor_cannot_authorize_any_asset_dereference(self):
  r=self.fixture(present=False);r._capture_weapon_binding();self.assertNotIn('weapon_asset_binding',r.report);self.assertEqual(self.reads,[0x10050])
 def test_dead_owned_record_cannot_authorize_asset_reads(self):
  r=self.fixture(hp=0);r._capture_weapon_binding();self.assertNotIn(0x33000,self.reads);self.assertNotIn('weapon_asset_binding',r.report)
 def test_wrong_immutable_asset_is_not_relabelled_as_ak(self):
  r=self.fixture(asset=0x41872ecc)
  with self.assertRaisesRegex(ValueError,'asset_unstable'):r._capture_weapon_binding()
  self.assertNotIn('weapon_asset_binding',r.report)
 def test_a_published_binding_cannot_be_replaced_by_a_different_entry(self):
  r=self.fixture();r._capture_weapon_binding();r.report['native']['weapon_entry']+=4
  with self.assertRaisesRegex(ValueError,'binding_changed'):r._capture_weapon_binding()
if __name__=='__main__':unittest.main()
