"""Private manager-only protocol 4. No model or product grant.

The schema has no building/unit/queue/position fields. Each process permits
one attach. Unknown apply is never retried. STOP requests native restoration;
only fresh independent baseline/lease reads permit a cleanup claim.
"""
import ctypes as c
from ctypes import wintypes as w
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai'),str(Path(__file__).parent)]
from observe_production import Memory
from read_selected_personality import inspect_player
from read_script_flags import inspect_flags
from build import verify,sha

u32=c.c_uint32
class Binding(c.Structure):
    _fields_=[(name,u32) for name in ('pid','thread','start_low','start_high','owner','ai','personality','personality_data','player_template','game','engine')]+[(name,c.c_ubyte*n) for name,n in [('session',16),('lease',16),('package',32),('sources',32)]]+[('deployment',c.c_wchar*520)]
class GateStatus(c.Structure):
    _fields_=[('phase',u32),('baseline_captured',u32),('baseline',u32*3),('observed',u32*3),('frame',u32),('deadline_frame',u32),('ms',c.c_uint64),('deadline_ms',c.c_uint64)]+[(name,u32) for name in ('attempted','requested_enabled','operation_enabled','already_satisfied')]
class Shared(c.Structure):
    _fields_=[('magic',u32),('version',u32),('size',u32),('binding',Binding)]+[(name,u32) for name in ('request','ack','phase','active','error','heartbeat','kind','gate','frames','wall_ms','result','stop','lease_held','hook_held','last_frame','cleanup_verified','journal_records')]+[('gates',GateStatus*2)]
class Audit(c.Structure):
    _fields_=[('request_id',c.c_uint64)]+[(name,u32) for name in ('gate','phase','trigger','frame','deadline_frame')]+[('ms',c.c_uint64),('deadline_ms',c.c_uint64),('baseline',c.c_ubyte*3),('observed',c.c_ubyte*3),('api_attempts',u32),('read_only_reconciliation',c.c_bool),('first_reconcile_frame',u32),('first_reconcile_ms',c.c_uint64),('first_reconcile_values',c.c_ubyte*3)]+[(name,c.c_bool) for name in ('requested_enabled','operation_enabled','state_already_satisfied','baseline_captured')]
class JournalRecord(c.Structure):
    _fields_=[(name,u32) for name in ('magic','version','sequence','size')]+[('binding',Binding),('audit',Audit),('end',u32)]

def verify_layout(manifest):
    actual=dict(size=c.sizeof(Shared),binding=Shared.binding.offset,request=Shared.request.offset,error=Shared.error.offset,gates=Shared.gates.offset,gate_size=c.sizeof(GateStatus),audit_size=c.sizeof(Audit),journal_size=c.sizeof(JournalRecord),journal_audit=JournalRecord.audit.offset,journal_end=JournalRecord.end.offset)
    if manifest['layout']!=actual:raise ValueError('manager_compiled_wire_layout_mismatch')
    return actual

def read_journal(path,expected_binding):
    raw=Path(path).read_bytes();size=c.sizeof(JournalRecord)
    if not raw or len(raw)%size or len(raw)//size>4096:raise ValueError('manager_native_journal_truncated_or_unbounded')
    rows=[]
    for index in range(len(raw)//size):
        record=JournalRecord.from_buffer_copy(raw[index*size:(index+1)*size])
        if record.magic!=0x534d4734 or record.version!=4 or record.sequence!=index+1 or record.size!=size or record.end!=0x454e4434 or bytes(record.binding)!=expected_binding:raise ValueError('manager_native_journal_identity_or_sequence')
        rows.append(projection(record.audit))
    return rows

def projection(value):
    if isinstance(value,c.Array):return [projection(v) for v in value]
    if isinstance(value,c.Structure):return {name:projection(getattr(value,name)) for name,_ in value._fields_}
    return value

def policy_modules(memory):
    psapi=c.WinDLL('psapi',use_last_error=True)
    psapi.EnumProcessModulesEx.argtypes=[w.HANDLE,c.POINTER(w.HMODULE),w.DWORD,c.POINTER(w.DWORD),w.DWORD]
    psapi.GetModuleFileNameExW.argtypes=[w.HANDLE,w.HMODULE,w.LPWSTR,w.DWORD]
    modules=(w.HMODULE*1024)();needed=w.DWORD()
    if not psapi.EnumProcessModulesEx(memory.handle,modules,c.sizeof(modules),c.byref(needed),3) or needed.value>c.sizeof(modules):raise ValueError('complete_module_inventory_required')
    found=[]
    for module in modules[:needed.value//c.sizeof(w.HMODULE)]:
        path=c.create_unicode_buffer(32768)
        if not psapi.GetModuleFileNameExW(memory.handle,module,path,len(path)):raise ValueError('module_path_unknown')
        if re.search(r'(?:MacroPolicy|StrategicPolicy|StrategicManager)',Path(path.value).name,re.I):found.append(path.value)
    return found

class Probe:
    def __init__(self,session,build,output):
        self.mapping=None;self.view=None;self.state=None;self.host=None;self.memory=None;self.seq=0;self.unknown=False;self.log=None
        self.stopped=threading.Event();self.heartbeat=None
        self.session_path=Path(session).resolve();self.session_raw=self.session_path.read_bytes();self.session=json.loads(self.session_raw)
        self.build=Path(build).resolve();self.manifest=verify(self.build);verify_layout(self.manifest);self.output=Path(output).resolve()
        if self.output.exists() or not self.output.is_relative_to(ROOT/'reports'):raise ValueError('fresh_owned_manager_report_required')
        self.output.mkdir();self.log=(self.output/'commands.jsonl').open('x',encoding='utf8')
        self.kernel=c.WinDLL('kernel32',use_last_error=True);k=self.kernel
        k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE
        k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
        k.UnmapViewOfFile.argtypes=[c.c_void_p];k.CloseHandle.argtypes=[w.HANDLE];k.GetTickCount.restype=w.DWORD
        k.GetProcessTimes.argtypes=[w.HANDLE,*[c.POINTER(w.FILETIME)]*4]
        try:
            self.memory=Memory(self.session['pid'],self.session)
            if policy_modules(self.memory):raise ValueError('previous_native_epoch_no_same_pid_reattach')
            if self.session['mod_sha256']!=self.manifest['package_sha256'] or sha(self.session['mod_big'])!=self.manifest['package_sha256']:raise ValueError('actual_deployment_required')
            people=[];manager=self.memory.u32(0xcdd1a0)
            for i in range(20):
                player=self.memory.u32(manager+0x48+4*i)
                if player and self.memory.u32(player+0x20)==3:people.append(player)
            if len(people)!=1:raise ValueError('unique_own_player_required')
            self.owner=people[0];native=inspect_player(self.memory.read,self.owner)
            if int(native['instance_id'],0)!=0x799613e0:raise ValueError('unique_macro_personality_required')
            flags=inspect_flags(self.memory.read,self.manifest['flags'])
            if any(row['present'] and row['value'] is not False for row in flags['flags']):raise ValueError('unowned_flag_intents_present')
            user=c.WinDLL('user32',use_last_error=True);callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM);threads=[]
            user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];user.GetWindowThreadProcessId.restype=w.DWORD
            user.IsWindowVisible.argtypes=[w.HWND];user.GetWindow.argtypes=[w.HWND,w.UINT];user.GetWindow.restype=w.HWND
            user.EnumWindows.argtypes=[callback,w.LPARAM]
            @callback
            def window(hwnd,unused):
                pid=w.DWORD();thread=user.GetWindowThreadProcessId(hwnd,c.byref(pid))
                if pid.value==self.session['pid'] and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd,4):threads.append(thread)
                return True
            user.EnumWindows(window,0)
            if len(threads)!=1:raise ValueError('unique_game_window_required')
            self.mapping=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Shared),'Local\\RA3StrategicManagerV4_'+str(self.session['pid']))
            if not self.mapping or c.get_last_error()==183:raise ValueError('manager_epoch_already_exists_no_reattach')
            self.view=k.MapViewOfFile(self.mapping,0xf001f,0,0,c.sizeof(Shared))
            if not self.view:raise c.WinError(c.get_last_error())
            c.memset(self.view,0,c.sizeof(Shared));self.state=Shared.from_address(self.view);s=self.state;b=s.binding
            s.magic=0x534d4734;s.version=4;s.size=c.sizeof(Shared);b.pid=self.session['pid'];b.thread=threads[0]
            created=[w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(self.memory.handle,*[c.byref(t) for t in created]):raise c.WinError(c.get_last_error())
            ticks=created[0].dwLowDateTime|created[0].dwHighDateTime<<32
            if ticks!=self.session['process_creation_filetime']:raise ValueError('exact_process_incarnation_required')
            b.start_low=ticks&0xffffffff;b.start_high=ticks>>32;b.owner=self.owner
            for field,key in [('ai','ai_player'),('personality','personality_wrapper'),('player_template','player_template')]:setattr(b,field,int(native[key],0))
            b.personality_data=self.memory.u32(b.personality);b.game=self.memory.u32(0xcd8ce4);b.engine=self.memory.u32(0xcdd190)
            for field,raw in [('session',uuid.UUID(self.session['session_id']).bytes),('lease',uuid.uuid4().bytes),('package',bytes.fromhex(self.manifest['package_sha256'])),('sources',bytes.fromhex(self.manifest['source_closure_sha256']))]:getattr(b,field)[:]=raw
            b.deployment=str(Path(self.session['mod_big']).resolve());s.heartbeat=k.GetTickCount()
            self.binding=bytes(b)
            def beat():
                while not self.stopped.wait(.5):s.heartbeat=k.GetTickCount()
            self.heartbeat=threading.Thread(target=beat,daemon=True);self.heartbeat.start()
            self.event('attach_prepared',native=self.status(),manifest_sha256=sha(self.build/'build-manifest.json'))
            self.host_log=(self.output/'host.log').open('x',encoding='utf8')
            self.host=subprocess.Popen([str(self.build/'manager_host.exe'),str(b.pid)],stdout=self.host_log,stderr=self.host_log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline=time.monotonic()+8
            while s.phase==0 and self.host.poll() is None and time.monotonic()<deadline:time.sleep(.02)
            if s.phase!=1 or s.error or not s.lease_held or not s.hook_held:
                self.event('attach_not_acknowledged',host_returncode=self.host.poll(),native=self.status())
                raise ValueError('manager_native_attach_not_verified')
            self.event('attach_acknowledged',native=self.status())
        except BaseException:
            self.close();raise

    def event(self,kind,**value):
        self.log.write(json.dumps(dict(kind=kind,session_id=self.session['session_id'],pid=self.session['pid'],monotonic_ns=time.monotonic_ns(),**value),ensure_ascii=False)+'\n');self.log.flush();os.fsync(self.log.fileno())
    def status(self):return projection(Shared.from_buffer_copy(c.string_at(self.view,c.sizeof(Shared))))
    def command(self,operation,gate,frames=60,wall_ms=10000):
        kinds={'pause':1,'enable':2,'release':3,'reconcile':4}
        if operation not in kinds or type(gate) is not int or gate not in (0,1) or type(frames) is not int or not 1<=frames<=1800 or type(wall_ms) is not int or not 1<=wall_ms<=120000:raise ValueError('manager_high_level_request_invalid')
        if self.unknown:raise ValueError('unknown_never_retry')
        verify(self.build)
        if self.session_path.read_bytes()!=self.session_raw or bytes(self.state.binding)!=self.binding:raise ValueError('manager_bound_inputs_changed')
        s=self.state
        # A callback may be sampling the same transport. Wait for a quiescent
        # read BEFORE preparing/publishing anything; this is not a retry.
        ready_by=time.monotonic()+2
        while s.phase==1 and s.active and time.monotonic()<ready_by:time.sleep(.005)
        if s.phase!=1 or s.active or s.request!=s.ack:raise ValueError('manager_not_ready')
        self.seq+=1;self.event('command_prepared',seq=self.seq,operation=operation,gate=gate,frames=frames,wall_ms=wall_ms)
        s.kind=kinds[operation];s.gate=gate;s.frames=frames;s.wall_ms=wall_ms;s.request=self.seq
        deadline=time.monotonic()+3
        while s.ack<self.seq and s.phase==1 and time.monotonic()<deadline:time.sleep(.01)
        status=self.status();unknown=s.ack!=self.seq or s.result in (4,5) or s.phase==5
        self.unknown=unknown;self.event('command_unknown' if unknown else 'command_receipt',seq=self.seq,native=status)
        if unknown:raise ValueError('manager_delivery_or_result_unknown')
        return status
    def close(self):
        if self.state is not None and self.host is not None:
            if self.state.phase==0 and self.host.poll() in (2,3,4,5,6,7,8):
                status=self.status();modules=policy_modules(self.memory)
                k=self.kernel;k.OpenSemaphoreW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenSemaphoreW.restype=w.HANDLE
                c.set_last_error(0);sem=k.OpenSemaphoreW(1,False,'Local\\RA3MacroPolicyLease_'+str(self.session['pid']));last_error=c.get_last_error()
                if sem:k.CloseHandle(sem)
                if not modules and not sem and last_error==2 and all(status[key]==0 for key in ('request','ack','active','lease_held','hook_held','journal_records')):
                    value=dict(native_attached=False,native_calls=0,native=status,policy_modules=modules,semaphore_absent=True,host_returncode=self.host.poll(),formal_games=0)
                    (self.output/'independent-no-attachment.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
                    self.event('unused_admission_independently_verified',host_returncode=self.host.poll())
                    self.host_log.close();self.host=None
        if self.state is not None and self.host is not None:
            self.state.stop=1;deadline=time.monotonic()+8
            while self.state.phase not in (2,4) and time.monotonic()<deadline:time.sleep(.05)
            self.event('stop_observed',native=self.status(),unknown_apply=self.unknown)
            # Keep mapping and heartbeat alive on unresolved restoration.
            if self.state.phase not in (2,4):raise ValueError('manager_cleanup_unresolved_lease_retained')
            if self.state.phase==2:
                review=self.independent_release()
                if self.state.journal_records:
                    journal=ROOT/'reports/strategic-manager-native-journal'/(uuid.UUID(self.session['session_id']).hex+'.bin')
                    rows=read_journal(journal,self.binding)
                    if len(rows)!=self.state.journal_records:raise ValueError('manager_native_durable_journal_count_mismatch')
                    (self.output/'native-manager-audits.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8')
                    review['native_durable_journal_verified']=True;review['native_durable_journal_records']=len(rows)
                else:review['native_durable_journal_verified']=False;review['native_durable_journal_records']=0
                (self.output/'independent-release.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf8')
            self.host.wait(timeout=5);self.host_log.close()
        self.stopped.set()
        if self.heartbeat:self.heartbeat.join(timeout=2)
        if self.memory:self.memory.close();self.memory=None
        self.state=None
        if self.view:self.kernel.UnmapViewOfFile(self.view);self.view=None
        if self.mapping:self.kernel.CloseHandle(self.mapping);self.mapping=None
        if self.log:self.log.close();self.log=None
    def independent_release(self):
        k=self.kernel;nt=c.WinDLL('ntdll');k.OpenSemaphoreW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenSemaphoreW.restype=w.HANDLE
        nt.NtQuerySemaphore.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)];nt.NtQuerySemaphore.restype=c.c_long
        class Info(c.Structure):_fields_=[('current',c.c_long),('maximum',c.c_long)]
        status=self.status();b=status['binding'];components=[]
        with_memory=Memory(self.session['pid'],self.session)
        try:
            if (b['pid']!=self.session['pid'] or b['start_low']|(b['start_high']<<32)!=self.session['process_creation_filetime'] or bytes(self.state.binding)!=self.binding or status['phase']!=2 or status['active'] or status['lease_held'] or status['hook_held'] or not status['cleanup_verified']):raise ValueError('manager_release_shared_not_verified')
            for index,(offset,vt,own,enabled) in enumerate(((0x458,0xc5f8f8,0x14,0x1c),(0x4d4,0xc5f484,8,0x10),(0x564,0xc5f440,8,0x10))):
                gate=status['gates'][int(index>0)];at=b['ai']+offset;value=with_memory.read(at+enabled,1)[0]
                if with_memory.u32(at)!=vt or with_memory.u32(at+own)!=b['owner'] or value>1:raise ValueError('manager_component_identity_not_verified')
                if gate['baseline_captured'] and (gate['phase']!=4 or value!=gate['baseline'][index]):raise ValueError('manager_actual_baseline_not_restored')
                components.append(dict(index=index,address=hex(at),enabled=value,owned=bool(gate['baseline_captured'])))
            flags=inspect_flags(with_memory.read,self.manifest['flags'])
            if any(r['present'] and r['value'] is not False for r in flags['flags']):raise ValueError('manager_unexpected_flag_intent')
        finally:with_memory.close()
        semaphore=k.OpenSemaphoreW(1,False,'Local\\RA3MacroPolicyLease_'+str(b['pid']));info=Info();size=w.ULONG()
        try:
            if not semaphore or nt.NtQuerySemaphore(semaphore,0,c.byref(info),c.sizeof(info),c.byref(size)) or info.current!=info.maximum or info.current!=1:raise ValueError('manager_actual_common_lease_not_returned')
        finally:
            if semaphore:k.CloseHandle(semaphore)
        return dict(native_release_verified=True,native=status,components=components,flags=flags,semaphore_current=info.current,semaphore_maximum=info.maximum,unknown_apply_preserved=self.unknown,strategic_effect_verified=False,formal_games=0,product_capability_granted=False)
