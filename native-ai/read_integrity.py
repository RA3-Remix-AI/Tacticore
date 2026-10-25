"""Read-only process token integrity and foreground attribution, never input."""
import ctypes as c,json,sys
from ctypes import wintypes as w
k=c.WinDLL('kernel32',use_last_error=True);a=c.WinDLL('advapi32',use_last_error=True);u=c.WinDLL('user32',use_last_error=True)
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
a.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)]
a.GetTokenInformation.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)]
a.GetSidSubAuthorityCount.argtypes=[c.c_void_p];a.GetSidSubAuthorityCount.restype=c.POINTER(c.c_ubyte)
a.GetSidSubAuthority.argtypes=[c.c_void_p,w.DWORD];a.GetSidSubAuthority.restype=c.POINTER(w.DWORD)
k.CloseHandle.argtypes=[w.HANDLE]
def one(pid):
 h=k.OpenProcess(0x1000,False,pid);t=w.HANDLE();r={'pid':pid}
 try:
  if not h or not a.OpenProcessToken(h,8,c.byref(t)):raise c.WinError(c.get_last_error())
  n=w.DWORD();a.GetTokenInformation(t,25,None,0,c.byref(n));b=c.create_string_buffer(n.value)
  if not a.GetTokenInformation(t,25,b,n,c.byref(n)):raise c.WinError(c.get_last_error())
  sid=c.cast(b,c.POINTER(c.c_void_p))[0];count=a.GetSidSubAuthorityCount(sid)[0];level=a.GetSidSubAuthority(sid,count-1)[0]
  ui=w.DWORD();size=w.DWORD();a.GetTokenInformation(t,26,c.byref(ui),4,c.byref(size))
  r.update(integrity_rid=level,integrity={0x1000:'low',0x2000:'medium',0x2100:'medium_plus',0x3000:'high',0x4000:'system'}.get(level,'other'),ui_access=ui.value)
 except Exception as e:r['error']=str(e)
 finally:
  if t:k.CloseHandle(t)
  if h:k.CloseHandle(h)
 return r
u.GetForegroundWindow.restype=w.HWND;fg=u.GetForegroundWindow();pid=w.DWORD();u.GetWindowThreadProcessId(fg,c.byref(pid))
print(json.dumps({'foreground_window':fg,'foreground_pid':pid.value,'processes':[one(int(p)) for p in sys.argv[1:]],'mutations':False},indent=2))
