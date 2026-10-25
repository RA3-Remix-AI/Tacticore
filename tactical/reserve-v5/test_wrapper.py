"""Process/ABI/admission boundaries, not a simulated claim of field holding."""
import ctypes,importlib.util,json,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('rsv5_wrapper_test',HERE/'lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Memory:
 def __init__(self):
  self.words={0x10000+0x380:0x20000,0x20000:0xc37f90,0x20004:0x30000,0x20008:0x10000,0x20038:0,0x30008:0x40000,0x40000:0x50000,0x50004:4,0x50008:0x60000,0xc37f98:0x71d3f0};self.rows=[1,0,0,0,2,0,3,0]
 def u32(self,address):return self.words[address]
 def read(self,address,length):
  if address==0x71d3f0:return bytes.fromhex('b84c7ec000c3')[:length]
  if address==0x60000:return struct.pack('<8I',*self.rows)[:length]
  raise ValueError('Unmapped')

class WrapperBoundaries(unittest.TestCase):
 def test_current_definition_list_and_module_owner_are_read_not_assumed(self):
  memory=Memory();r=m.preflight.stance_snapshot(memory,0x10000);self.assertEqual([d['enum'] for d in r['definitions']],[1,0,2,3])
  for address,value in ((0x20008,0x10004),(0x20038,2),(0x50004,5)):
   bad=Memory();bad.words[address]=value
   with self.assertRaises(ValueError):m.preflight.stance_snapshot(bad,0x10000)
  memory=Memory();memory.rows[4]=1
  with self.assertRaises(ValueError):m.preflight.stance_snapshot(memory,0x10000)

 def test_candidate_execute_refuses_before_game_selection_or_any_process(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(m,'EXECUTE_ENABLED',False),patch.object(m.preflight,'current_selection',side_effect=AssertionError('No game access')),patch.object(m.subprocess,'Popen',side_effect=AssertionError('No launch')):
   with self.assertRaisesRegex(ValueError,'candidate_locked'):
    m.main(['--session','unused','--commander','57e668b4-4d89-43bd-bc92-0dd436f046ef','--birth-report','unused','--output',str(Path(folder)/'result.json'),'--execute'])

 def test_source_poll_never_runs_another_host_or_repeats_abi_execution(self):
  with patch.object(m.subprocess,'Popen',side_effect=AssertionError('No process')):
   self.assertFalse(m.unchanged_sources({}))

 def test_actual_cpp_abi_matches_exact_python_layout(self):
  host=HERE/'bin/tactical_host.exe'
  if not host.exists():self.skipTest('Actual native host not built')
  actual=json.loads(subprocess.check_output([str(host),'--layout'],text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
  self.assertEqual(actual,m.layout_module.layout())

 def test_actual_software_fixture_decodes_without_claiming_a_game(self):
  path=HERE/'native-positive.bin'
  if not path.exists():self.skipTest('Actual native software fixture not built')
  shared=m.Probe.from_buffer_copy(path.read_bytes());r={};m.capture(r,shared)
  self.assertEqual(r['native']['count'],len(r['events']));self.assertGreater(len(r['events']),90)
  self.assertEqual(r['events'][0]['sample']['id'],shared.object_id)
  self.assertIsInstance(r['events'][0]['sample']['status_words'],list)

if __name__=='__main__':unittest.main()
