"""Private fixed-ten-intent native trial, without model/product capability.

Reuses the existing durable command/unknown/STOP/watchdog client methods. Its
constructor, profile validation, versioned attach and observation are explicit
new routes; old qualification and old source files remain unchanged.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from strategic_transport_profile_v1 import verify_build,source_paths,action_mask,sha,load,VERSION
from strategic_expansion_observation_v1 import ExpansionObserver

spec=importlib.util.spec_from_file_location('strategic_shared_flag_client',ROOT/'native-ai/macro-policy-runtime-v2/client.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
Shared=base.Shared;k=base.k


class StrategicProbe(base.MacroPolicyProbe):
    def __init__(self,session_path,owner,build,output):
        self.session_path=Path(session_path).resolve(strict=True);self.session_raw=self.session_path.read_bytes();self.session=load(self.session_path)
        self.owner=owner;self.build=Path(build).resolve(strict=True);self.output=Path(output).resolve()
        self.host=None;self.mapping=None;self.view=None;self.state=None;self.memory=None;self.log=None;self.journal=None
        self.heartbeat=None;self.stop_event=threading.Event();self.ledger={};self.pending=False;self.seq=0
        self.injected_host_loss=False;self.build_observer=None
        if self.output.exists() or not self.output.is_relative_to(ROOT/'reports'):
            raise ValueError('fresh_local_strategic_trial_required')
        self.manifest=verify_build(self.build)
        base.verify_session_package(self.session)
        if self.session['mod_sha256']!=self.manifest['package_sha256']:
            raise ValueError('strategic_exact_session_package')
        self.memory=base.Memory(self.session['pid'],self.session)
        try:
            times=[w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(self.memory.handle,*[c.byref(row) for row in times]):raise c.WinError(c.get_last_error())
            self.creation=times[0].dwLowDateTime|times[0].dwHighDateTime<<32
            if self.creation!=self.session['process_creation_filetime']:raise ValueError('strategic_process_incarnation')
            self.native=base.inspect_player(self.memory.read,owner)
            if self.native['player_index']!=3 or int(self.native['instance_id'],0)!=0x799613e0:
                raise ValueError('strategic_profile_owner')
            self.observer=ExpansionObserver(self.memory,owner,self.manifest['flags']);initial=self.observer.sample()
            flags=base.inspect_flags(self.memory.read,self.manifest['flags'])
            if any(row['present'] and row['value'] is not False for row in flags['flags']):raise ValueError('strategic_flags_not_quiescent')
            self.output.mkdir(parents=True);source=self.output/'source';source.mkdir();provenance=[]
            paths=source_paths()+[self.build/'profile.h',self.build/'build-manifest.json',self.session_path,
                Path(self.manifest['package_report']),Path(self.manifest['package_report']).parent/'compiled-strategic-audit.json']
            for i,path in enumerate(paths):
                target=source/(str(i)+'-'+path.name);shutil.copy2(path,target)
                provenance.append(dict(path=str(path.resolve()),copy=target.name,sha256=sha(target)))
            (self.output/'preflight.json').write_text(json.dumps(dict(
                kind='strategic_flag_trial_preflight_v1',session_sha256=hashlib.sha256(self.session_raw).hexdigest(),
                process_creation_filetime=self.creation,native=self.native,initial_flags=flags,
                initial_observation=initial,sources=provenance),indent=2)+'\n',encoding='utf8')
            self.journal=(self.output/'policy-probe.jsonl').open('x',encoding='utf8')
            self.attach()
        except BaseException:
            self.close();raise

    def attach(self):
        user=c.WinDLL('user32',use_last_error=True);callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];user.GetWindowThreadProcessId.restype=w.DWORD
        user.IsWindowVisible.argtypes=[w.HWND];user.GetWindow.argtypes=[w.HWND,w.UINT];user.GetWindow.restype=w.HWND
        user.EnumWindows.argtypes=[callback,w.LPARAM];windows=[]
        @callback
        def find(hwnd,unused):
            pid=w.DWORD();thread=user.GetWindowThreadProcessId(hwnd,c.byref(pid))
            if pid.value==self.session['pid'] and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd,4):windows.append(thread)
            return True
        user.EnumWindows(find,0)
        if len(set(windows))!=1:raise ValueError('strategic_unique_window_thread')
        k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE
        k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
        k.UnmapViewOfFile.argtypes=[c.c_void_p];k.GetTickCount.restype=w.DWORD
        self.mapping=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Shared),self.manifest['mapping_prefix']+str(self.session['pid']))
        if not self.mapping or c.get_last_error()==183:raise ValueError('strategic_runtime_epoch_already_exists')
        self.view=k.MapViewOfFile(self.mapping,0xf001f,0,0,c.sizeof(Shared))
        if not self.view:raise c.WinError(c.get_last_error())
        c.memset(self.view,0,c.sizeof(Shared));self.state=Shared.from_address(self.view);s=self.state
        s.magic=0x4d503032;s.version=VERSION;s.pid=self.session['pid'];s.thread=windows[0]
        s.start_low=self.creation&0xffffffff;s.start_high=self.creation>>32;s.owner=self.owner
        for field,key in [('ai','ai_player'),('personality','personality_wrapper'),('personality_id','instance_id'),('player_template','player_template')]:
            setattr(s,field,int(self.native[key],0))
        s.engine=self.memory.u32(0xcdd190);s.client_heartbeat=k.GetTickCount()
        def beat():
            while not self.stop_event.wait(.5):s.client_heartbeat=k.GetTickCount()
        self.heartbeat=threading.Thread(target=beat,daemon=True);self.heartbeat.start()
        self.event('attach_prepared',protocol_version=VERSION,capability_granted=False)
        self.log=(self.output/'host.log').open('x',encoding='utf8')
        self.host=subprocess.Popen([str(self.build/'macro_policy_host.exe'),str(s.pid)],stdout=self.log,stderr=self.log,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+5
        while s.phase==0 and time.monotonic()<deadline and self.host.poll() is None:time.sleep(.01)
        if s.phase!=1 or s.error or not s.self_hook_installed or not s.lease_held:
            raise ValueError('strategic_native_attach_unknown_or_rejected')
        self.event('attach_acknowledged',native=self.native_status())

    def apply(self,actions,duration_frames,command_id=None):
        import uuid
        mask=action_mask(actions,self.manifest)
        if type(duration_frames) is not int or not 1<=duration_frames<=1800:raise ValueError('strategic_duration_bounds')
        return self.command(1,mask,duration_frames,command_id or str(uuid.uuid4()))
