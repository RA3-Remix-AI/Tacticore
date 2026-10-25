"""Controller loss policy with actual MF10 Header; no process or game actions."""
import importlib.util
from pathlib import Path
import unittest
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mf10_host_loss_runtime',H/'lease.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class Host:
 def __init__(self,code):self.code=code
 def poll(self):return self.code
class Lifecycle(unittest.TestCase):
 def test_alive_host_does_not_fabricate_stop_or_progress(self):
  n=w.Header();n.phase=1;n.pulse_requested=101;n.pulse_acknowledged=101;before=bytes(n)
  w.require_live_host_or_terminal(Host(None),n);self.assertEqual(bytes(n),before)
 def test_any_exit_code_before_terminal_sets_stop_for_existing_drain(self):
  for phase in (0,1,2,5,7):
   for code in (0,9,-1):
    n=w.Header();n.phase=phase;n.issued_frame=100;n.pulse_requested=1001;n.pulse_acknowledged=1001
    with self.subTest(phase=phase,code=code),self.assertRaisesRegex(RuntimeError,'native_host_exited_before_terminal'):w.require_live_host_or_terminal(Host(code),n)
    self.assertEqual(n.stop_requested,1);self.assertEqual(n.phase,phase);self.assertEqual(n.issued_frame,100);self.assertEqual(n.pulse_acknowledged,1001)
 def test_real_terminal_exit_is_not_rewritten_as_live_loss(self):
  for phase in (3,4):
   n=w.Header();n.phase=phase;n.restore_mask=65535;before=bytes(n)
   w.require_live_host_or_terminal(Host(9),n);self.assertEqual(bytes(n),before)
 def test_final_reader_rejects_ack_change_during_entry_scan(self):
  # Existing real-bounds fake catches a pulse ack race; ack is not restoration.
  import test_bounded_readonly as fixture
  import tempfile,struct
  from unittest.mock import patch
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);m,b,p,l,h,r=fixture.Bounded().terminal_fixture(directory);changed=False
   def change(m,a,n):
    nonlocal changed
    if a==0x500000 and not changed:m.put(p+w.Header.pulse_acknowledged.offset,struct.pack('<I',123));changed=True
   m.change=change
   with patch.object(w,'HERE',directory),patch.object(w,'module',return_value=SimpleNamespace(module_base=lambda memory,path:b)):
    with self.assertRaisesRegex(ValueError,'readonly_header_changed_during_entries'):w.terminal_readonly(m,r)
if __name__=='__main__':unittest.main()
