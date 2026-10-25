"""Real Windows delete-sharing regression. No game process or SDK is used."""
import ctypes as c,importlib.util,json,os,tempfile,threading,time,types,unittest,uuid
from ctypes import wintypes as w
from pathlib import Path
from unittest.mock import patch,Mock
import run_flak
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('io_test_production_client',ROOT/'persistent/client.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)

@unittest.skipUnless(os.name=='nt','Windows file-share semantics required')
class WindowsDurableTests(unittest.TestCase):
 def hold_reader(self,path):
  api=c.WinDLL('kernel32',use_last_error=True);api.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE];api.CreateFileW.restype=w.HANDLE;api.CloseHandle.argtypes=[w.HANDLE];api.CloseHandle.restype=w.BOOL
  # READ/WRITE sharing allows readers and writers, deliberately not DELETE.
  handle=api.CreateFileW(str(path),0x80000000,3,None,3,0x80,None)
  if handle==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
  return api,handle
 def test_real_reader_release_allows_atomic_replace_within_watchdog_budget(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'status.json';run_flak.durable_write(path,dict(version=1,complete=True));api,handle=self.hold_reader(path);denied=threading.Event();errors=[];original=Path.replace;count=[]
   def replace(source,target):
    count.append(1)
    try:return original(source,target)
    except PermissionError:denied.set();raise
   def writer():
    try:run_flak.durable_write(path,dict(version=2,complete=True))
    except Exception as error:errors.append(error)
   start=time.monotonic()
   try:
    with patch.object(Path,'replace',replace):
     worker=threading.Thread(target=writer);worker.start();self.assertTrue(denied.wait(1));self.assertEqual(json.loads(path.read_text())['version'],1);time.sleep(.06);api.CloseHandle(handle);handle=None;worker.join(2)
    self.assertFalse(worker.is_alive());self.assertFalse(errors);self.assertGreater(len(count),1);self.assertEqual(json.loads(path.read_text()),dict(version=2,complete=True));self.assertLess(time.monotonic()-start,3)
   finally:
    if handle:api.CloseHandle(handle)
 def test_permanent_lock_preserves_old_complete_report_and_propagates_failure(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'status.json';run_flak.durable_write(path,dict(version=1));api,handle=self.hold_reader(path);start=time.monotonic()
   try:
    with self.assertRaises(PermissionError):run_flak.durable_write(path,dict(version=2))
    self.assertEqual(json.loads(path.read_text()),dict(version=1));pending=list(Path(folder).glob('status.json.tmp-*'));self.assertEqual(len(pending),1);self.assertEqual(json.loads(pending[0].read_text()),dict(version=2));self.assertLess(time.monotonic()-start,3)
   finally:api.CloseHandle(handle)
 def test_bad_payload_does_not_damage_old_report(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'status.json';run_flak.durable_write(path,dict(version=1))
   with self.assertRaises(TypeError):run_flak.durable_write(path,dict(bad=object()))
   self.assertEqual(json.loads(path.read_text()),dict(version=1))

class HeartbeatClassificationTests(unittest.TestCase):
 def executor(self):
  e=client.ProductionExecutor('unused','unused','0x10000',str(uuid.uuid4()),'unused');e.shared=types.SimpleNamespace(heartbeat=0,stop_requested=0);e._record=Mock();return e
 def test_persistent_status_io_failure_is_not_reported_as_binding_change(self):
  e=self.executor();e._verify_binding=Mock();e._status_unlocked=Mock(side_effect=PermissionError('locked status'));e.stopping.wait=Mock(return_value=False);e._heartbeat();self.assertEqual(e.shared.stop_requested,1);self.assertTrue(e.stopping.is_set());self.assertEqual(e._record.call_args.args[0]['reason'],'status_persistence_failed')
 def test_real_binding_failure_retains_binding_classification(self):
  e=self.executor();e._verify_binding=Mock(side_effect=RuntimeError('binding changed'));e._status_unlocked=Mock();e.stopping.wait=Mock(return_value=False);e._heartbeat();e._status_unlocked.assert_not_called();self.assertEqual(e._record.call_args.args[0]['reason'],'binding_or_lifecycle_changed')
 def test_unpersisted_dispatch_intent_cannot_publish_request(self):
  e=client.ProductionExecutor('unused','unused','0x10000',str(uuid.uuid4()),'unused');e.shared=client.Persistent();e.shared.phase=1;e.memory=Mock();e.memory.u32.side_effect=lambda address:100 if address==0x100050 else 0x100000 if address==0xcd8ce4 else 1 if address==0x100dc else 0;e._verify_binding=lambda:None;e.candidate={};e.owner=0x20000;e.session=dict(session_id=str(uuid.uuid4()));e._record=Mock(side_effect=PermissionError('journal unavailable'));command=dict(session_id=e.session['session_id'],player_id=3,commander_id=e.commander_id,command_id=str(uuid.uuid4()),task_id=uuid.uuid4().hex,seq=1,unit='conscript',budget=85,reserve=500,expires_frame=200)
  with patch.object(client,'read_factory',return_value=dict(production_interface_available=True,interface='0x30000')):
   with self.assertRaises(PermissionError):e.submit(command)
  self.assertEqual(e.shared.request_state,0);self.assertEqual(e.shared.request.seq,0)
if __name__=='__main__':unittest.main()
