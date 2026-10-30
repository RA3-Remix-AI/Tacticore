"""Bind the existing Native5 helper to its OS incarnation before model use.

This records identities only. It never starts, signals or changes a helper,
opens a game mapping, or claims that an ended process returned ownership.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path


KIND = 'native5_helper_identity_v1'


def process_identity(pid,*,require_image=True):
    """A held query/synchronize handle; access failures remain unknown."""
    if type(pid) is not int or not 0<pid<=0xffffffff:raise ValueError('native5_process_identity_required')
    k=c.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
    k.GetProcessId.argtypes=[w.HANDLE];k.GetProcessId.restype=w.DWORD
    k.GetProcessTimes.argtypes=[w.HANDLE,*[c.POINTER(w.FILETIME)]*4];k.GetProcessTimes.restype=w.BOOL
    k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
    k.QueryFullProcessImageNameW.restype=w.BOOL
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
    k.CloseHandle.argtypes=[w.HANDLE]
    handle=k.OpenProcess(0x100000|0x1000,False,pid)
    if not handle:raise c.WinError(c.get_last_error())
    try:
        times=[w.FILETIME() for _ in range(4)]
        path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if (k.GetProcessId(handle)!=pid or not k.GetProcessTimes(handle,*[c.byref(v) for v in times])):
            raise c.WinError(c.get_last_error())
        has_image=bool(k.QueryFullProcessImageNameW(handle,0,path,c.byref(size)))
        if require_image and not has_image:raise c.WinError(c.get_last_error())
        result=k.WaitForSingleObject(handle,0)
        if result not in (0,258):raise c.WinError(c.get_last_error())
        return dict(pid=pid,process_creation_filetime=times[0].dwLowDateTime|(times[0].dwHighDateTime<<32),
                    image=str(Path(path.value).resolve()) if has_image else None,alive=result==258)
    finally:k.CloseHandle(handle)


def record_helper_identity(probe):
    """Called inside the admitted constructor, after actual attach succeeds."""
    helper=process_identity(probe.host.pid);parent=process_identity(os.getpid())
    image=probe.build/'manager_host.exe'
    if (not helper['alive'] or not parent['alive'] or Path(helper['image'])!=image.resolve()
            or probe.host.poll() is not None):
        raise ValueError('native5_helper_incarnation_not_live')
    value=dict(kind=KIND,session_id=probe.session['session_id'],
        game_pid=probe.session['pid'],game_creation_filetime=probe.session['process_creation_filetime'],
        native_binding=probe.status()['binding'],helper=helper,parent=parent,
        helper_image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        build_manifest_sha256=hashlib.sha256((probe.build/'build-manifest.json').read_bytes()).hexdigest(),
        capture_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        native_commands_allowed=False)
    target=probe.output/'helper-identity.json'
    with target.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return value


def ended_incarnation(expected):
    """Prove the recorded incarnation ended, without inventing an exit code."""
    if (not isinstance(expected,dict) or type(expected.get('pid')) is not int or not 0<expected['pid']<=0xffffffff
            or type(expected.get('process_creation_filetime')) is not int or expected['process_creation_filetime']<=0):
        raise ValueError('native5_exact_incarnation_required')
    try:current=process_identity(expected['pid'],require_image=False)
    except OSError as error:
        # ERROR_INVALID_PARAMETER for a positive PID means no such process.
        # Access denied and every other failure must remain unknown.
        if getattr(error,'winerror',None)!=87:raise
        return dict(ended=True,reason='pid_absent',exit_code=None)
    if current['process_creation_filetime']!=expected['process_creation_filetime']:
        return dict(ended=True,reason='different_incarnation',exit_code=None,current=current)
    return dict(ended=not current['alive'],reason='same_incarnation_ended' if not current['alive'] else 'still_alive',
                exit_code=None,current=current)
