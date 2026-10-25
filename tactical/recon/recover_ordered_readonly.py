"""Read actual ordered-attack mapping and timer; never changes native state."""
import argparse,ctypes as c,hashlib,importlib.util,json,struct,uuid
from ctypes import wintypes as w
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('ordered_recovery_backend',HERE.parent/'ordered-attack/lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
def clean(v):
 if isinstance(v,c.Array):return [clean(x) for x in v]
 if isinstance(v,c.Structure):return {k:clean(getattr(v,k)) for k,_ in v._fields_}
 return v
def main():
 p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=json.loads(a.report.read_text(encoding='utf-8-sig'));session=json.loads(a.session.read_text(encoding='utf-8-sig'));token=source['request']['token'];k=b.k
 k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p]
 h=k.OpenFileMappingW(4,False,'Local\\RA3TacticalOrderedAttack_'+str(session['pid'])+'_'+str(token))
 if not h:raise c.WinError(c.get_last_error())
 view=k.MapViewOfFile(h,4,0,0,c.sizeof(b.Tactical))
 if not view:raise c.WinError(c.get_last_error())
 try:
  raw=c.string_at(view,c.sizeof(b.Tactical));s=b.Tactical.from_buffer_copy(raw)
  if s.pid!=session['pid'] or s.token!=token:raise ValueError('mapping_identity_mismatch')
  data={key:clean(getattr(s,key)) for key,_ in s._fields_ if key!='events'};data['events']=[clean(s.events[i]) for i in range(min(max(s.count,0),4096))]
  data['session_id']=str(uuid.UUID(bytes=struct.pack('<4I',*s.session)));data['command_id']=str(uuid.UUID(bytes=struct.pack('<4I',*s.command)));data['task_id']=str(uuid.UUID(bytes=struct.pack('<4I',*s.task)))
  m=b.Memory(session['pid'],session)
  try:
   ps=c.WinDLL('psapi',use_last_error=True);modules=(c.c_void_p*1024)();needed=w.DWORD();ps.EnumProcessModulesEx.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),w.DWORD];ps.GetModuleFileNameExW.argtypes=[w.HANDLE,c.c_void_p,w.LPWSTR,w.DWORD]
   if not ps.EnumProcessModulesEx(m.handle,modules,c.sizeof(modules),c.byref(needed),3):raise c.WinError(c.get_last_error())
   loaded=[]
   for module in modules[:needed.value//c.sizeof(c.c_void_p)]:
    path=c.create_unicode_buffer(1024);ps.GetModuleFileNameExW(m.handle,module,path,1024)
    if path.value.lower().endswith('tacticalorderedattack.dll'):loaded.append((module,path.value))
   if len(loaded)!=1:raise ValueError('ordered_module_not_unique')
   base,path=loaded[0];timer=m.u32(base+0x13278);native_shared=m.u32(base+0x13288)
   data.update(native_dll_base=hex(base),native_dll_path=path,native_dll_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),timer_rva='0x13278',timer=timer,native_shared_pointer=hex(native_shared),native_shared_phase=m.u32(native_shared+b.Tactical.phase.offset),native_shared_token=m.u32(native_shared+b.Tactical.token.offset))
  finally:m.close()
  out=dict(kind='actual_mapping_and_timer_readonly_recovery',mutations=False,source_report=str(a.report.resolve()),mapping_sha256=hashlib.sha256(raw).hexdigest(),native=data)
  a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(report=str(a.output),phase=s.phase,error=s.error,mask=s.restore_mask,active=s.active,timer=timer,detach=s.detach_calls,attack=s.attack_calls,stops=s.stop_calls,returned=s.return_calls)))
 finally:k.UnmapViewOfFile(view);k.CloseHandle(h)
if __name__=='__main__':main()
