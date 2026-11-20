"""Desktop status writing for the macro host."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest


class MacroStatusWriteTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows file-sharing regression')
    def test_ui_reader_temporarily_holding_status_does_not_fault_writer(self):
        import ctypes
        from ctypes import wintypes
        from host_runtime.desktop_backend import _atomic
        win=ctypes.WinDLL('kernel32',use_last_error=True)
        win.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,
                                 wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        win.CreateFileW.restype=wintypes.HANDLE;win.CloseHandle.argtypes=[wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'host-status.json';_atomic(path,dict(sequence=1))
            handle=win.CreateFileW(str(path),0x80000000,1,None,3,0,None)
            self.assertNotIn(handle,(None,ctypes.c_void_p(-1).value))
            def release():time.sleep(.08);win.CloseHandle(handle)
            worker=threading.Thread(target=release);worker.start()
            try:_atomic(path,dict(sequence=2))
            finally:worker.join()
            self.assertEqual(json.loads(path.read_text()),dict(sequence=2))
            self.assertEqual(list(Path(temp).glob('*.tmp')),[])


if __name__=='__main__':unittest.main()
