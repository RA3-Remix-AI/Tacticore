"""Read-sharing handles keep the admitted product candidate immutable."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import hashlib

class ProductSourceLocksV5:
    def __init__(self,pins):
        self.handles=[];self.kernel=c.WinDLL('kernel32',use_last_error=True);k=self.kernel
        k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE];k.CreateFileW.restype=w.HANDLE
        k.CloseHandle.argtypes=[w.HANDLE]
        try:
            for path,expected in pins.items():
                path=Path(path).resolve(strict=True)
                handle=k.CreateFileW(str(path),0x80000000,1,None,3,0x80,None)
                if handle in (None,c.c_void_p(-1).value):raise c.WinError(c.get_last_error())
                self.handles.append(handle)
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
                if digest.hexdigest()!=expected:raise ValueError('unified_locked_source_changed')
        except BaseException:self.close();raise
    def close(self):
        for handle in self.handles:self.kernel.CloseHandle(handle)
        self.handles=[]
