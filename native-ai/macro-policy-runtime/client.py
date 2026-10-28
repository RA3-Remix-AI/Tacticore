"""Private field-qualification transport for fixed native AI policy gates.

No product grant, model integration, arbitrary script API or unit command exists
here. Native acknowledgement and independently observed behavior stay distinct.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from observe_production import Memory,k
from session_package import verify_session_package
from read_selected_personality import inspect_player
from read_script_flags import inspect_flags
from macro_observation import MacroObserver

U,L=c.c_uint32,c.c_int32
class Shared(c.Structure):
    _fields_=[(name,U) for name in 'magic version pid thread start_low start_high owner ai personality personality_id player_template engine'.split()]+[
        (name,L) for name in 'request ack phase active'.split()]+[(name,U) for name in
        'error attempted callback_thread start_frame last_frame applied_mask deadline_frame cleanup_verified watchdog_reason self_hook_installed client_heartbeat kind mask duration_frames emergency_stop lease_held'.split()]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def wait_native_idle(state,timeout=.5):
    """Wait only before preparing a command, never retry an issued request."""
    deadline=time.monotonic()+timeout
    while True:
        if state.phase!=1 or state.error or state.request!=state.ack:raise ValueError('macro_native_not_ready')
        if not state.active:return
        if time.monotonic()>=deadline:raise ValueError('macro_native_not_ready')
        time.sleep(.005)


def action_mask(actions,manifest):
    if not isinstance(actions,list) or len(actions)>13 or any(type(action) is not str for action in actions) or len(set(actions))!=len(actions):raise ValueError('macro_actions_bounds_or_duplicate')
    by_action={r['action']:manifest['flags'].index(r['flag']) for r in manifest['consumers']}
    if any(type(action) is not str or action not in by_action for action in actions):raise ValueError('unsupported_macro_action')
    mask=sum(1<<by_action[action] for action in actions)
    if any(value and value&(value-1) for value in [mask&group for group in manifest['exclusive_masks']]):
        raise ValueError('conflicting_macro_policy_actions')
    return mask


class MacroPolicyProbe:
    def __init__(self,session_path,owner,build,output,*,build_feedback=False):
        self.session_path=session_path;self.session_raw=session_path.read_bytes();self.session=load(session_path)
        self.owner=owner;self.build=build.resolve();self.output=output.resolve();self.host=None;self.mapping=None;self.view=None
        self.state=None;self.memory=None;self.log=None;self.journal=None;self.heartbeat=None;self.stop_event=threading.Event();self.ledger={}
        self.manifest=load(self.build/'build-manifest.json');self.pending=False;self.seq=0;self.injected_host_loss=False
        self.build_observer=None
        if self.output.exists() or not self.output.is_relative_to(ROOT/'reports'):raise ValueError('fresh_local_macro_probe_output_required')
        manifest=self.manifest
        if manifest.get('kind')!='native_macro_policy_transport_candidate' or manifest.get('capability_granted') is not False:
            raise ValueError('field_candidate_only')
        verify_session_package(self.session)
        if self.session['mod_sha256']!=manifest['package_sha256']:raise ValueError('macro_transport_package_mismatch')
        report_path=Path(manifest['package_report'])
        if sha(report_path)!=manifest['package_report_sha256']:raise ValueError('macro_transport_package_report_changed')
        package_report=load(report_path)
        if package_report.get('variant')!='expanded_macro_policy_v1' or package_report.get('big_sha256')!=manifest['package_sha256']:
            raise ValueError('macro_transport_wrong_policy_package')
        if set(manifest['artifacts'])!={manifest['library'],'macro_policy_host.exe'}:raise ValueError('macro_transport_artifact_set')
        for name,digest in manifest['artifacts'].items():
            if sha(self.build/name)!=digest:raise ValueError('macro_transport_binary_changed')
        for name,digest in manifest['sources'].items():
            if name not in {'shared.h','native.cpp','host.cpp','build.py'} or sha(HERE/name)!=digest:raise ValueError('macro_transport_source_changed')
        if sha(self.build/'profile.h')!=manifest['profile_header_sha256']:raise ValueError('macro_transport_profile_changed')
        layout=dict(size=c.sizeof(Shared),request=Shared.request.offset,error=Shared.error.offset,mask=Shared.mask.offset,heartbeat=Shared.client_heartbeat.offset)
        if layout!=manifest['layout']:raise ValueError('macro_transport_layout')
        self.memory=Memory(self.session['pid'],self.session)
        try:
            times=[w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(self.memory.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())
            self.creation=times[0].dwLowDateTime|times[0].dwHighDateTime<<32
            if self.creation!=self.session.get('process_creation_filetime'):raise ValueError('macro_transport_exact_creation_required')
            self.native=inspect_player(self.memory.read,owner)
            if self.native['player_index']!=3 or int(self.native['instance_id'],0)!=0x799613e0:raise ValueError('macro_transport_profile_owner')
            self.observer=MacroObserver(self.memory,owner,manifest['flags'],terrain_feedback=True,construction_feedback=True)
            initial=self.observer.sample()
            if build_feedback:
                from macro_build_observation import NativeBuildObserver
                self.build_observer=NativeBuildObserver(self.memory,owner,manifest['flags'])
                self.build_observer.sample()
            flags=inspect_flags(self.memory.read,manifest['flags'])
            if any(row['present'] and row['value'] is not False for row in flags['flags']):raise ValueError('macro_flags_not_quiescent')
            self.output.mkdir(parents=True);source=self.output/'source';source.mkdir()
            paths=[HERE/name for name in ['shared.h','native.cpp','host.cpp','build.py','client.py']]+[
                self.build/'profile.h',self.build/'build-manifest.json',report_path,session_path,
                ROOT/'native-ai/macro_observation.py',ROOT/'native-ai/macro_build_observation.py',ROOT/'native-ai/read_script_flags.py',ROOT/'visibility/native_read.py',
                ROOT/'production/observe_production.py',ROOT/'production/session_package.py',ROOT/'native-ai/read_selected_personality.py',ROOT/'probe.py']
            provenance=[]
            for i,path in enumerate(paths):
                target=source/(str(i)+'-'+path.name);shutil.copy2(path,target);provenance.append(dict(path=str(path.resolve()),copy=target.name,sha256=sha(target)))
            with (self.output/'preflight.json').open('x',encoding='utf-8') as f:
                json.dump(dict(session_sha256=hashlib.sha256(self.session_raw).hexdigest(),process_creation_filetime=self.creation,
                    native=self.native,initial_flags=flags,initial_observation=initial,sources=provenance),f,ensure_ascii=False,indent=2)
            self.journal=(self.output/'policy-probe.jsonl').open('x',encoding='utf-8')
            self.attach()
        except BaseException:
            self.close();raise

    def event(self,kind,**fields):
        if self.journal:
            self.journal.write(json.dumps(dict(kind=kind,session_id=self.session['session_id'],pid=self.session['pid'],
                monotonic_ns=time.monotonic_ns(),**fields),ensure_ascii=False,allow_nan=False)+'\n')
            self.journal.flush();os.fsync(self.journal.fileno())

    def attach(self):
        user=c.WinDLL('user32',use_last_error=True)
        callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];user.GetWindowThreadProcessId.restype=w.DWORD
        user.IsWindowVisible.argtypes=[w.HWND];user.GetWindow.argtypes=[w.HWND,w.UINT];user.GetWindow.restype=w.HWND
        user.EnumWindows.argtypes=[callback,w.LPARAM];windows=[]
        @callback
        def find(hwnd,unused):
            pid=w.DWORD();thread=user.GetWindowThreadProcessId(hwnd,c.byref(pid))
            if pid.value==self.session['pid'] and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd,4):windows.append(thread)
            return True
        user.EnumWindows(find,0)
        if len(set(windows))!=1:raise ValueError('macro_unique_window_thread_required')
        k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE
        k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
        k.UnmapViewOfFile.argtypes=[c.c_void_p];k.GetTickCount.restype=w.DWORD
        self.mapping=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Shared),self.manifest['mapping_prefix']+str(self.session['pid']))
        if not self.mapping or c.get_last_error()==183:raise ValueError('macro_runtime_epoch_already_exists')
        self.view=k.MapViewOfFile(self.mapping,0xf001f,0,0,c.sizeof(Shared))
        if not self.view:raise c.WinError(c.get_last_error())
        c.memset(self.view,0,c.sizeof(Shared));self.state=Shared.from_address(self.view);s=self.state
        s.magic=0x4d504f4c;s.version=1;s.pid=self.session['pid'];s.thread=windows[0];s.start_low=self.creation&0xffffffff;s.start_high=self.creation>>32;s.owner=self.owner
        for field,key in [('ai','ai_player'),('personality','personality_wrapper'),('personality_id','instance_id'),('player_template','player_template')]:setattr(s,field,int(self.native[key],0))
        s.engine=self.memory.u32(0xcdd190);s.client_heartbeat=k.GetTickCount()
        def beat():
            while not self.stop_event.wait(.5):s.client_heartbeat=k.GetTickCount()
        self.heartbeat=threading.Thread(target=beat,daemon=True);self.heartbeat.start()
        self.event('attach_prepared',mapping_name=self.manifest['mapping_prefix']+str(s.pid),capability_granted=False)
        self.log=(self.output/'host.log').open('x',encoding='utf-8')
        self.host=subprocess.Popen([str(self.build/'macro_policy_host.exe'),str(s.pid)],stdout=self.log,stderr=self.log)
        deadline=time.monotonic()+5
        while s.phase==0 and time.monotonic()<deadline and self.host.poll() is None:time.sleep(.01)
        if s.phase!=1 or s.error or not s.self_hook_installed or not s.lease_held:raise ValueError('macro_native_attach_unknown_or_rejected')
        self.event('attach_acknowledged',native=self.native_status())

    def native_status(self):return {name:int(getattr(self.state,name)) for name,_ in Shared._fields_}

    def apply(self,actions,duration_frames,command_id=None):
        mask=action_mask(actions,self.manifest)
        if type(duration_frames) is not int or not 1<=duration_frames<=4500:raise ValueError('macro_duration_bounds')
        return self.command(1,mask,duration_frames,command_id or str(uuid.uuid4()))

    def command(self,kind,mask,duration,command_id):
        if str(uuid.UUID(command_id))!=command_id:raise ValueError('macro_command_id_required')
        fingerprint=(kind,mask,duration)
        if command_id in self.ledger:
            previous=self.ledger[command_id]
            if previous['fingerprint']!=fingerprint:raise ValueError('macro_command_id_conflict')
            if previous['status']=='unknown':raise ValueError('macro_previous_command_unknown')
            return previous['receipt']
        if self.pending:raise ValueError('macro_outstanding_command_unknown')
        if self.session_path.read_bytes()!=self.session_raw or inspect_player(self.memory.read,self.owner)!=self.native:
            raise ValueError('macro_session_identity_changed')
        s=self.state
        wait_native_idle(s)
        self.seq+=1;self.pending=True
        self.ledger[command_id]=dict(fingerprint=fingerprint,status='unknown')
        self.event('command_prepared',command_id=command_id,seq=self.seq,kind_code=kind,mask=mask,duration_frames=duration)
        s.kind=kind;s.mask=mask;s.duration_frames=duration;s.request=self.seq
        deadline=time.monotonic()+5
        while s.ack!=self.seq and time.monotonic()<deadline:
            if s.phase==4 or self.host.poll() is not None:break
            time.sleep(.01)
        if s.ack!=self.seq or s.error:
            self.event('command_unknown',command_id=command_id,seq=self.seq,native=self.native_status())
            raise ValueError('macro_native_command_unknown')
        flags=inspect_flags(self.memory.read,self.manifest['flags'])
        expected=mask if kind==1 else 0
        for index,row in enumerate(flags['flags']):
            wanted=bool(expected&(1<<index))
            if (wanted and (not row['present'] or row['value'] is not True)) or (not wanted and row['present'] and row['value'] is not False):
                self.event('independent_readback_unknown',command_id=command_id,seq=self.seq)
                raise ValueError('macro_flag_readback_unknown')
        receipt=dict(command_id=command_id,seq=self.seq,native_gate_acknowledged=True,independent_flags=flags,
            native=self.native_status(),effect_verified=False,capability_granted=False)
        self.ledger[command_id].update(status='acknowledged',receipt=receipt);self.pending=False
        self.event('command_acknowledged',**receipt);return receipt

    def observe(self,label):
        try:value=dict(label=label,observation=self.observer.sample())
        except (ValueError,RuntimeError) as error:value=dict(label=label,read_error=str(error))
        self.event('macro_observation',**value)
        if self.build_observer is not None:
            try:build=dict(label=label,observation=self.build_observer.sample())
            except (ValueError,RuntimeError) as error:build=dict(label=label,read_error=str(error))
            self.event('native_builder_observation',**build)
            if 'observation' in build:value['build_observation']=build['observation']
        return value

    def host_loss_probe(self):
        """Deliberate local helper fault; game's own hook must clear policy gates."""
        self.apply(['budgetarmy'],450)
        for _ in range(4):self.observe('before_external_host_loss');time.sleep(.5)
        self.event('fault_injection_external_host_loss',host_pid=self.host.pid,
            process_handle_owned=True,native=self.native_status())
        self.injected_host_loss=True;self.stop_event.set();self.heartbeat.join(timeout=2)
        # Popen retains the exact process handle; no PID lookup or game process
        # termination occurs. This is exposed only by the explicit field CLI.
        self.host.terminate();self.host.wait(timeout=5)
        deadline=time.monotonic()+10
        while self.state.phase not in (2,4) and time.monotonic()<deadline:
            self.observe('external_host_lost_waiting_for_native_watchdog');time.sleep(.5)
        self.observe('after_external_host_loss')
        native=self.native_status();flags=inspect_flags(self.memory.read,self.manifest['flags'])
        if (any(native[key]!=value for key,value in dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0,watchdog_reason=1).items())
            or any(row['present'] and row['value'] is not False for row in flags['flags'])):
            raise ValueError('native_host_loss_cleanup_unverified')
        self.event('native_host_loss_cleanup_verified',native=native,independent_flags=flags,
            host_returncode=self.host.poll(),normal_host_exit=False)

    def expiry_probe(self):
        receipt=self.apply(['budgetarmy'],60);deadline_frame=receipt['native']['deadline_frame']
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:self.observe('waiting_for_native_policy_expiry');time.sleep(.5)
        native=self.native_status();flags=inspect_flags(self.memory.read,self.manifest['flags'])
        if (native['last_frame']<deadline_frame or any(native[key]!=value for key,value in dict(phase=1,error=0,active=0,applied_mask=0,deadline_frame=0,cleanup_verified=1,self_hook_installed=1,lease_held=1).items())
            or any(row['present'] and row['value'] is not False for row in flags['flags'])):
            raise ValueError('native_policy_expiry_unverified')
        self.event('native_policy_expiry_verified',expected_deadline_frame=deadline_frame,native=native,independent_flags=flags)

    def close(self):
        if self.state is not None and self.host is not None:
            if self.state.phase==1 and not self.pending:
                try:self.command(2,0,0,str(uuid.uuid4()))
                except (ValueError,RuntimeError):self.state.emergency_stop=1
            elif self.state.phase not in (2,4):self.state.emergency_stop=1
        self.stop_event.set()
        if self.heartbeat:self.heartbeat.join(timeout=2)
        if self.host:
            try:self.host.wait(timeout=8)
            except subprocess.TimeoutExpired:pass
        if self.state is not None:self.event('transport_closed',native=self.native_status(),host_returncode=self.host.poll() if self.host else None)
        if self.state is not None and self.journal:
            native=self.native_status();flags=None;flag_error=None
            try:flags=inspect_flags(self.memory.read,self.manifest['flags'])
            except (ValueError,RuntimeError) as error:flag_error=str(error)
            verified=(all(native[key]==value for key,value in dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0).items())
                and self.host is not None and (self.host.poll()==0 or self.injected_host_loss and self.host.poll() is not None) and flags is not None
                and all(not row['present'] or row['value'] is False for row in flags['flags']))
            with (self.output/'final-state.json').open('x',encoding='utf-8') as f:
                json.dump(dict(session_id=self.session['session_id'],pid=self.session['pid'],process_creation_filetime=self.creation,
                    mod_sha256=self.session['mod_sha256'],native=native,independent_flags=flags,flag_read_error=flag_error,
                    host_returncode=self.host.poll() if self.host else None,cleanup_verified=verified,
                    unknown_command_ids=[key for key,row in self.ledger.items() if row['status']=='unknown'],
                    intentional_external_host_loss=self.injected_host_loss,
                    capability_granted=False,formal_goal_complete=False),f,ensure_ascii=False,indent=2)
        if self.journal:self.journal.close();self.journal=None
        if self.log and self.host and self.host.poll() is not None:self.log.close()
        if self.view:k.UnmapViewOfFile(self.view);self.view=None;self.state=None
        if self.mapping:k.CloseHandle(self.mapping);self.mapping=None
        if self.memory:self.memory.close();self.memory=None


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True)
    p.add_argument('--owner',type=lambda x:int(x,0),required=True);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--scout-rounds',type=int,default=0)
    p.add_argument('--actions',nargs='+');p.add_argument('--hold-seconds',type=int,default=20)
    p.add_argument('--duration-frames',type=int,default=450)
    p.add_argument('--host-loss-probe',action='store_true')
    p.add_argument('--expiry-probe',action='store_true')
    p.add_argument('--build-feedback',action='store_true',help='Read native builder/job records; no additional execution authority')
    args=p.parse_args()
    if not 0<=args.scout_rounds<=3:raise ValueError('bounded_macro_field_rounds')
    if args.actions and (args.scout_rounds or not 1<=args.hold_seconds<=180):raise ValueError('one_bounded_field_scenario_required')
    if args.host_loss_probe and (args.actions or args.scout_rounds):raise ValueError('one_host_loss_field_scenario_required')
    if args.expiry_probe and (args.host_loss_probe or args.actions or args.scout_rounds):raise ValueError('one_expiry_field_scenario_required')
    executor=MacroPolicyProbe(args.session,args.owner,args.build,args.output,build_feedback=args.build_feedback)
    try:
        executor.observe('attached')
        if args.host_loss_probe:executor.host_loss_probe()
        if args.expiry_probe:executor.expiry_probe()
        if args.actions:
            executor.apply(args.actions,args.duration_frames)
            deadline=time.monotonic()+args.hold_seconds
            while time.monotonic()<deadline:
                executor.observe('fixed_macro_actions_held');time.sleep(.5)
            executor.apply([],1);executor.observe('fixed_macro_actions_released')
            time.sleep(2);executor.observe('after_native_policy_reassessment')
        for round_index in range(args.scout_rounds):
            executor.apply(['scout'],450)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                executor.observe('scout_round_'+str(round_index));time.sleep(.5)
            executor.apply([],1);executor.observe('released_round_'+str(round_index))
            time.sleep(2)
    finally:executor.close()
    print(json.dumps(dict(output=str(args.output.resolve()),field_candidate=True,capability_granted=False)))


if __name__=='__main__':main()
