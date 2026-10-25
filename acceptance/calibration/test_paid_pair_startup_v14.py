"""Actual five-entry rules across partial producer installation; no game."""
import importlib.util,struct,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('paid_pair_startup_v14',HERE/'paid_pair_controller_v14.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Startup(unittest.TestCase):
 def setUp(self):
  self.binding=m.load('original_binding_for_startup_test',m.NATIVE/'producer_binding.py');self.rows=self.binding.entries();self.base=0x10000000;self.size=0x10000
 def installed(self,index):
  row=self.rows[index];address=int(row['address'],0);target=self.base+0x1000+index*0x100
  return b'\xe9'+struct.pack('<i',target-address-5)+bytes.fromhex(row['expected'])[5:]
 def test_actual_patch_preserves_tail_and_reaches_the_loaded_image(self):
  for index,row in enumerate(self.rows):self.assertEqual(m.patch_state(self.installed(index),bytes.fromhex(row['expected']),int(row['address'],0),self.base,self.size),'installed')
 def test_original_bytes_are_pending_and_not_ready(self):
  row=self.rows[0];raw=bytes.fromhex(row['expected']);self.assertEqual(m.patch_state(raw,raw,int(row['address'],0),self.base,self.size),'original')
 def test_unknown_tail_or_foreign_jump_never_gets_a_grace_period(self):
  row=self.rows[0];expected=bytes.fromhex(row['expected']);raw=self.installed(0)
  for candidate in (raw[:-1]+bytes([raw[-1]^1]),b'\xe9'+struct.pack('<i',123-int(row['address'],0)-5)+expected[5:]):
   with self.assertRaises(ValueError):m.patch_state(candidate,expected,int(row['address'],0),self.base,self.size)
 def run_barrier(self,states,*,timeout=.12):
  calls={'entries':0,'time':0.0};rows=self.rows
  def read(address,length):
   if address==self.base:return b'MZ'
   if address==self.base+0x80:return b'PE\0\0'
   if address==self.base+0x80+24:return b'\x0b\x01'
   i=next(i for i,r in enumerate(rows) if int(r['address'],0)==address);step=min(calls['entries']//5,len(states)-1);state=states[step][i];calls['entries']+=1
   return bytes.fromhex(rows[i]['expected']) if state=='original' else self.installed(i) if state=='installed' else b'\xcc'*length
  memory=types.SimpleNamespace(read=read,u32=lambda address:0x80 if address==self.base+0x3c else self.size)
  helper=types.SimpleNamespace(module_base=lambda *a:self.base)
  producer=types.SimpleNamespace(shared=types.SimpleNamespace(phase=1,error=0,stop_requested=0))
  def sleep(seconds):calls['time']+=seconds
  def load(name,path):return self.binding if Path(path).name=='producer_binding.py' else helper
  with tempfile.TemporaryDirectory() as folder,patch.object(m,'load',side_effect=load),patch.object(self.binding,'module',return_value=helper):
   output=Path(folder)/'observations.json'
   try:result=m.wait_producer_installed(memory,producer,output,timeout=timeout,clock=lambda:calls['time'],sleep=sleep);error=None
   except ValueError as failure:result=None;error=failure
   import json
   diagnostic=json.loads(output.read_text());return result,error,diagnostic,calls
 def test_phase_one_with_partial_hooks_waits_until_two_complete_actual_reads(self):
  result,error,diagnostic,calls=self.run_barrier([['original']*5,['installed']*2+['original']*3,['installed']*5,['installed']*5])
  self.assertIsNone(error);self.assertTrue(result['ready']);self.assertEqual(len(diagnostic['samples']),4);self.assertEqual(len(result['original_loaded_entries']['entries']),5);self.assertEqual(calls['entries'],25)
 def test_unknown_entry_stops_on_first_observation_and_preserves_raw(self):
  result,error,diagnostic,calls=self.run_barrier([['installed']*4+['unknown']])
  self.assertIsNone(result);self.assertIn('unknown_entry',str(error));self.assertEqual(len(diagnostic['samples']),1);self.assertFalse(diagnostic['ready']);self.assertTrue(diagnostic['samples'][0]['entries'][-1]['actual'].startswith('cccc'))
 def test_incomplete_installation_times_out_without_an_arm_or_order(self):
  result,error,diagnostic,calls=self.run_barrier([['installed']*4+['original']])
  self.assertIsNone(result);self.assertIn('timeout',str(error));self.assertFalse(diagnostic['ready']);self.assertGreaterEqual(calls['time'],.12);self.assertLess(calls['time'],.15)
if __name__=='__main__':unittest.main()
