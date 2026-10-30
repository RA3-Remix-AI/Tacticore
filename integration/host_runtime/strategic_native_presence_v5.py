"""Read-only macro channel/semaphore checks. Never wait, create or acquire."""
import ctypes as c
from ctypes import wintypes as w
import re

from .contracts import ContractError


class SemaphoreBasicInformation(c.Structure):
    _fields_=[('CurrentCount',w.LONG),('MaximumCount',w.LONG)]


def query_macro_objects(pid,mapping_prefix,*,kernel=None,ntdll=None,last_error=None):
    if (type(pid) is not int or not 0<pid<=0xffffffff or type(mapping_prefix) is not str
            or mapping_prefix!='Local\\RA3StrategicCommanderV5_'):
        raise ContractError('session_not_ready')
    kernel=kernel or c.WinDLL('kernel32',use_last_error=True);ntdll=ntdll or c.WinDLL('ntdll')
    last_error=last_error or c.get_last_error
    kernel.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];kernel.OpenFileMappingW.restype=w.HANDLE
    kernel.OpenSemaphoreW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];kernel.OpenSemaphoreW.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    ntdll.NtQuerySemaphore.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)];ntdll.NtQuerySemaphore.restype=w.LONG
    result=dict(source='win32_read_only_macro_channel_and_semaphore_v1',mapping_name=mapping_prefix+str(pid),
        semaphore_name='Local\\RA3MacroPolicyLease_'+str(pid),mapping_status='unknown',semaphore_status='unknown',
        semaphore_current_count=None,semaphore_maximum_count=None,native_writes=0,acquire_or_wait_calls=0)
    mapping=kernel.OpenFileMappingW(4,False,result['mapping_name'])
    if mapping:
        result['mapping_status']='present';kernel.CloseHandle(mapping)
    else:
        error=int(last_error());result['mapping_open_error']=error
        if error==2:result['mapping_status']='absent'
    semaphore=kernel.OpenSemaphoreW(1,False,result['semaphore_name']) # SEMAPHORE_QUERY_STATE
    if not semaphore:
        error=int(last_error());result['semaphore_open_error']=error
        if error==2:result['semaphore_status']='absent'
        return result
    try:
        states=[]
        for _ in range(2):
            info=SemaphoreBasicInformation();returned=w.ULONG()
            status=int(ntdll.NtQuerySemaphore(semaphore,0,c.byref(info),c.sizeof(info),c.byref(returned)))
            if status!=0 or returned.value!=c.sizeof(info):return result
            states.append((int(info.CurrentCount),int(info.MaximumCount)))
        result['semaphore_double_read']=states
        if states[0]!=states[1] or states[0][1]!=1 or states[0][0] not in (0,1):return result
        result.update(semaphore_current_count=states[0][0],semaphore_maximum_count=states[0][1],
            semaphore_status='free' if states[0][0]==1 else 'held')
        return result
    finally:kernel.CloseHandle(semaphore)


def require_unused_macro_process(pid,manifest,*,probe=query_macro_objects):
    result=probe(pid,manifest.get('mapping_prefix'))
    if result['mapping_status']=='present':raise ContractError('macro_runtime_same_epoch_reattach_unsupported')
    if result['mapping_status']!='absent' or result['semaphore_status']=='unknown':raise ContractError('session_not_ready')
    if result['semaphore_status']=='held':raise ContractError('run_already_active')
    if result['semaphore_status'] not in ('absent','free'):raise ContractError('session_not_ready')
    return result
