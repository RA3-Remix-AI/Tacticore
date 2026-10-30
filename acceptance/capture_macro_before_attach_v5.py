"""Capture only: passive process/DLL/flags/channel/semaphore evidence, no release.

Does not construct a transport, create/open a writable mapping, install/unhook,
wait/acquire/release a lease, load credentials or modify any prior receipt.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime,timedelta,timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility'),str(ROOT)]
from host_runtime.contracts import SessionBinding
from host_runtime.macro_native_presence import query_macro_objects

NATIVE_SHA='f0528ca468f5a24ca63b5b6d630d5e13a4ed68c5c04b6efe3d25d4310902062b'
DLL_SHA='aaca067e003a603c3df7f30615de3dda2f0b2ab6beb241b2905fa5a610610c62'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def reject(code):raise ValueError(code)


class CaptureFailure(ValueError):
    def __init__(self,code,telemetry):super().__init__(code);self.telemetry=telemetry


class MODULEENTRY32W(c.Structure):
    _fields_=[('dwSize',w.DWORD),('th32ModuleID',w.DWORD),('th32ProcessID',w.DWORD),('GlblcntUsage',w.DWORD),('ProccntUsage',w.DWORD),
        ('modBaseAddr',c.c_void_p),('modBaseSize',w.DWORD),('hModule',w.HMODULE),('szModule',w.WCHAR*256),('szExePath',w.WCHAR*260)]


class ModuleImageReader:
    """Same held process handle; reads confined to one OS-enumerated image."""
    def __init__(self,memory,kernel,base,size):
        self.memory=memory;self.kernel=kernel;self.base=base;self.size=size
        kernel.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
        kernel.ReadProcessMemory.restype=w.BOOL
    def read(self,address,size):
        if not self.base<=address<self.base+self.size or not 0<size<=0x2000 or address+size>self.base+self.size:
            reject('module_image_read_bounds')
        buffer=c.create_string_buffer(size);got=c.c_size_t()
        if not self.kernel.ReadProcessMemory(self.memory.handle,c.c_void_p(address),buffer,size,c.byref(got)) or got.value!=size:
            reject('module_image_read_unavailable_or_short')
        return buffer.raw


def read_stable(memory,address,size):
    result=memory.read(address,size)
    if memory.read(address,size)!=result:reject('module_image_bytes_changed')
    return result


def block(memory,address,size):
    return b''.join(read_stable(memory,address+offset,min(0x2000,size-offset)) for offset in range(0,size,0x2000))


def exported_names(memory,base,size):
    dos=read_stable(memory,base,64)
    if dos[:2]!=b'MZ':reject('module_dos_header_unverified')
    offset=struct.unpack_from('<I',dos,0x3c)[0]
    if not 64<=offset<=min(65536,size-264):reject('module_pe_header_bounds')
    header=read_stable(memory,base+offset,264)
    machine,magic=struct.unpack_from('<H',header,4)[0],struct.unpack_from('<H',header,24)[0]
    if header[:4]!=b'PE\0\0' or (machine,magic) not in ((0x14c,0x10b),(0x8664,0x20b)):
        reject('module_PE_machine_or_optional_magic_unverified')
    bits=32 if machine==0x14c else 64
    if bits==32 and base+size>0x100000000:reject('x86_module_address_overflow')
    metadata=dict(machine=hex(machine),optional_magic=hex(magic),image_bits=bits,reviewed_x86_hook_eligible=bits==32)
    if struct.unpack_from('<I',header,80)[0]!=size:reject('module_image_size_unverified')
    rva,length=struct.unpack_from('<II',header,120 if bits==32 else 136)
    if not rva and not length:return [],metadata
    if not 0<rva<=size-40 or not 40<=length<=size-rva:reject('module_export_directory_bounds')
    directory=read_stable(memory,base+rva,40);count=struct.unpack_from('<I',directory,24)[0];names=struct.unpack_from('<I',directory,32)[0]
    if not 0<=count<=65536 or count and not 0<names<=size-count*4:reject('module_export_name_table_bounds')
    pointers=struct.unpack('<'+'I'*count,block(memory,base+names,count*4)) if count else ()
    result=[]
    for pointer in pointers:
        if not 0<pointer<size:reject('module_export_name_pointer')
        raw=read_stable(memory,base+pointer,min(256,size-pointer))
        if b'\0' not in raw:reject('module_export_name_unterminated')
        result.append(raw.split(b'\0',1)[0].decode('ascii'))
    return result,metadata


def mapped_backing_path(memory,kernel,base):
    """OS-provided mapped image backing, never guessed from Toolhelp text."""
    kernel.K32GetMappedFileNameW.argtypes=[w.HANDLE,c.c_void_p,w.LPWSTR,w.DWORD]
    kernel.K32GetMappedFileNameW.restype=w.DWORD
    kernel.QueryDosDeviceW.argtypes=[w.LPCWSTR,w.LPWSTR,w.DWORD];kernel.QueryDosDeviceW.restype=w.DWORD
    kernel.GetLogicalDriveStringsW.argtypes=[w.DWORD,w.LPWSTR];kernel.GetLogicalDriveStringsW.restype=w.DWORD
    mapped=c.create_unicode_buffer(32768)
    length=kernel.K32GetMappedFileNameW(memory.handle,c.c_void_p(base),mapped,len(mapped))
    if not 0<length<len(mapped)-1:reject('mapped_backing_path_unavailable_or_truncated')
    native=mapped.value
    if not native.startswith('\\Device\\') or '\x00' in native:reject('mapped_backing_path_namespace_unverified')
    drives=c.create_unicode_buffer(4096);count=kernel.GetLogicalDriveStringsW(len(drives),drives)
    if not 0<count<len(drives):reject('logical_drive_mapping_unavailable')
    mappings=[]
    for drive in drives[:count].split('\x00'):
        if not drive:continue
        if len(drive)!=3 or drive[1:]!=':\\' or not drive[0].isalpha():reject('logical_drive_mapping_invalid')
        targets=c.create_unicode_buffer(32768);got=kernel.QueryDosDeviceW(drive[:2],targets,len(targets))
        if not 0<got<len(targets):reject('dos_device_mapping_unavailable')
        for target in targets[:got].split('\x00'):
            if target and native.casefold().startswith((target+'\\').casefold()):
                mappings.append((target,drive[:2]+native[len(target):]))
    if len(mappings)!=1:reject('mapped_backing_path_not_unique')
    device,path=mappings[0];backing=Path(path)
    if not backing.is_absolute() or not backing.is_file():reject('mapped_backing_file_unavailable')
    return dict(mapped_device_path=native,mapped_device_prefix=device,mapped_backing_path=str(backing.resolve()))


def unique_modules(rows):
    unique={};duplicates=[]
    for row in rows:
        prior=unique.get(row['base'])
        if prior is not None:
            if prior!=row:raise CaptureFailure('conflicting_module_duplicate',dict(module_base=row['base'],first=prior,second=row))
            duplicates.append(row)
        else:unique[row['base']]=row
    result=sorted(unique.values(),key=lambda row:int(row['base'],0))
    if not any(int(row['base'],0)==0x400000 for row in result):reject('main_module_identity_missing')
    return result,duplicates


def modules(memory,kernel):
    telemetry=dict(snapshot_flags=0x18,python_pointer_bits=c.sizeof(c.c_void_p)*8,wchar_bytes=c.sizeof(w.WCHAR),
        dword_bytes=c.sizeof(w.DWORD),module_entry_size=c.sizeof(MODULEENTRY32W))
    kernel.IsWow64Process2.argtypes=[w.HANDLE,c.POINTER(w.USHORT),c.POINTER(w.USHORT)];kernel.IsWow64Process2.restype=w.BOOL
    process,native=w.USHORT(),w.USHORT()
    success=kernel.IsWow64Process2(memory.handle,c.byref(process),c.byref(native))
    telemetry.update(process_machine=int(process.value),native_machine=int(native.value))
    if not success or process.value!=0x14c or native.value!=0x8664:
        telemetry.update(api='IsWow64Process2',win32_error=int(c.get_last_error()))
        raise CaptureFailure('exact_x86_on_amd64_identity_unverified',telemetry)
    kernel.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];kernel.CreateToolhelp32Snapshot.restype=w.HANDLE
    for name in ('Module32FirstW','Module32NextW'):
        function=getattr(kernel,name);function.argtypes=[w.HANDLE,c.POINTER(MODULEENTRY32W)];function.restype=w.BOOL
    handle=kernel.CreateToolhelp32Snapshot(0x18,memory.pid) # TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32
    if handle in (None,0,c.c_void_p(-1).value):
        telemetry.update(api='CreateToolhelp32Snapshot',win32_error=int(c.get_last_error()))
        raise CaptureFailure('module_snapshot_unavailable',telemetry)
    result=[]
    try:
        row=MODULEENTRY32W();row.dwSize=c.sizeof(row)
        telemetry['dwSize']=int(row.dwSize)
        present=kernel.Module32FirstW(handle,c.byref(row))
        if not present:
            telemetry.update(api='Module32FirstW',win32_error=int(c.get_last_error()))
            raise CaptureFailure('module_first_unavailable',telemetry)
        while present:
            base,size=int(row.modBaseAddr or 0),int(row.modBaseSize);path=Path(row.szExePath)
            telemetry.update(module_name=row.szModule,module_base=hex(base),module_size=size,toolhelp_path=row.szExePath,
                complete_rows=len(result),row_pid=int(row.th32ProcessID))
            checks=dict(pid=row.th32ProcessID==memory.pid,base=0x10000<=base<0x0000800000000000,
                size=0<size<=0x40000000,end=base+size<=0x0000800000000000,name=bool(row.szModule),
                path_untruncated=len(row.szExePath)<259,toolhelp_path_absolute=path.is_absolute())
            if not all(checks.values()):
                telemetry.update(checks=checks,api='Toolhelp_module_metadata',win32_error=int(c.get_last_error()))
                raise CaptureFailure('module_inventory_row_unverified',telemetry)
            try:
                mapped=mapped_backing_path(memory,kernel,base)
                exports,pe=exported_names(ModuleImageReader(memory,kernel,base,size),base,size)
                file_digest=sha(mapped['mapped_backing_path'])
            except BaseException as error:
                telemetry.update(api='module_mapped_file_or_PE_export_read',win32_error=int(c.get_last_error()),
                    underlying_error_type=type(error).__name__,failed_check=str(error) if isinstance(error,ValueError) else 'module_read_or_file_hash')
                raise CaptureFailure('module_image_or_exports_unverified',telemetry) from None
            result.append(dict(pid=memory.pid,base=hex(base),size=size,name=row.szModule,toolhelp_path=str(path),
                path=mapped['mapped_backing_path'],**mapped,file_sha256=file_digest,**pe,
                export_count=len(exports),control_exports=[name for name in exports if 'macropolicycontrol' in name.lower()]))
            if len(result)>1024:raise CaptureFailure('module_inventory_bound',telemetry)
            present=kernel.Module32NextW(handle,c.byref(row))
        terminal=int(c.get_last_error());telemetry['terminal_error']=terminal
        if terminal!=18:
            telemetry.update(api='Module32NextW',win32_error=terminal,complete_rows=len(result))
            raise CaptureFailure('module_enumeration_incomplete',telemetry) # ERROR_NO_MORE_FILES only
    finally:kernel.CloseHandle(handle)
    raw=result
    try:result,duplicates=unique_modules(raw)
    except CaptureFailure:raise
    except BaseException as error:
        telemetry.update(failed_check=str(error),api='module_identity_deduplication')
        raise CaptureFailure('module_inventory_identity',telemetry) from None
    telemetry.update(raw_rows=raw,raw_row_count=len(raw),exact_duplicate_rows=duplicates,exact_duplicate_count=len(duplicates),complete_rows=len(result))
    return result,telemetry


def process_identity(kernel,handle):
    kernel.GetProcessId.argtypes=[w.HANDLE];kernel.GetProcessId.restype=w.DWORD
    kernel.GetProcessTimes.argtypes=[w.HANDLE,*[c.POINTER(w.FILETIME)]*4];kernel.GetProcessTimes.restype=w.BOOL
    kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)];kernel.QueryFullProcessImageNameW.restype=w.BOOL
    times=[w.FILETIME() for _ in range(4)];path=c.create_unicode_buffer(32768);count=w.DWORD(len(path))
    if not kernel.GetProcessTimes(handle,*[c.byref(t) for t in times]) or not kernel.QueryFullProcessImageNameW(handle,0,path,c.byref(count)):
        reject('held_process_identity_unavailable')
    ticks=times[0].dwLowDateTime|times[0].dwHighDateTime<<32
    return dict(pid=int(kernel.GetProcessId(handle)),process_creation_filetime=int(ticks),image_path=str(Path(path.value).resolve()),image_sha256=sha(path.value))


def host_state(kernel,pid,start):
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,c.POINTER(w.DWORD)];kernel.GetExitCodeProcess.restype=w.BOOL
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        error=c.get_last_error()
        if error!=87:reject('original_host_process_state_unknown')
        return dict(pid=pid,original_incarnation_ended=True,open_error=error)
    try:
        times=[w.FILETIME() for _ in range(4)];exit_code=w.DWORD()
        if not kernel.GetProcessTimes(handle,*[c.byref(t) for t in times]) or not kernel.GetExitCodeProcess(handle,c.byref(exit_code)):
            reject('original_host_process_state_unknown')
        ticks=times[0].dwLowDateTime|times[0].dwHighDateTime<<32
        timestamp=datetime.fromtimestamp((ticks-116444736000000000)/10000000,timezone.utc).isoformat()
        ended=timestamp!=start or exit_code.value!=259
        if not ended:reject('original_host_still_alive')
        return dict(pid=pid,original_incarnation_ended=True,current_incarnation_filetime=ticks,current_incarnation_start=timestamp,exit_code=int(exit_code.value))
    finally:kernel.CloseHandle(handle)


def inputs(run,run_id):
    host=run/'battle-host';index=load(host/'sources.json');rows=index.get('sources')
    if index.get('kind')!='pre_execution_macro_host_sources' or type(rows) is not list or len(rows)<5:reject('frozen_source_index_unverified')
    copied={};evidence={str(host/'sources.json'):sha(host/'sources.json')}
    for row in rows:
        path=(host/'source'/row['copy']).resolve()
        if path.parent!=(host/'source').resolve() or sha(path)!=row['sha256'] or row['path'] in copied:reject('frozen_source_copy_unverified')
        copied[row['path']]=path;evidence[str(path)]=row['sha256']
    if [Path(r['path']).name for r in rows[:3]]!=['macro_host.py','session.json','macro-budget-bundle.json']:reject('frozen_source_order_unverified')
    session=load(copied[rows[1]['path']]);bundle=load(copied[rows[2]['path']]);binding=SessionBinding.from_dict(load(copied[rows[4]['path']]))
    status=load(host/'host-status.json');events=(host/'host-events.jsonl').read_bytes()
    for path in (host/'host-status.json',host/'host-events.jsonl'):evidence[str(path)]=sha(path)
    if (status.get('state')!='fault' or status.get('runtime_macro',{}).get('run_id')!=run_id
            or status['runtime_macro'].get('binding_hash')!=binding.binding_hash or status.get('session_id')!=binding.session_id
            or status.get('pid')!=binding.game_process_id or status.get('process_start')!=binding.game_process_start
            or session.get('pid')!=binding.game_process_id or session.get('session_id')!=binding.session_id
            or session.get('start_time')!=binding.game_process_start or session.get('mod_sha256')!=binding.mod_sha256):reject('frozen_run_binding_unverified')
    manifest_path=Path(bundle['build'])/'build-manifest.json';manifest=load(manifest_path)
    if (sha(manifest_path)!=bundle.get('pins',{}).get(str(manifest_path)) or manifest.get('protocol_version')!=2
            or manifest.get('epoch')!=4 or manifest.get('library')!='MacroPolicy2V4.dll' or manifest.get('mapping_prefix')!='Local\\RA3MacroPolicy2V4_'
            or manifest.get('package_sha256')!=binding.mod_sha256 or manifest.get('sources',{}).get('native.cpp')!=NATIVE_SHA
            or manifest.get('artifacts',{}).get(manifest['library'])!=DLL_SHA or len(manifest.get('flags',[]))!=20
            or len(set(manifest['flags']))!=20):reject('reviewed_protocol2_binary_pin_unverified')
    for relative,expected in [('native-ai/macro-policy-runtime-v2/native.cpp',NATIVE_SHA),('native-ai/read_script_flags.py',None),('native-ai/read_selected_personality.py',None)]:
        original=str((ROOT/relative).resolve());copy=copied.get(original)
        if copy is None or expected is not None and sha(copy)!=expected or sha(ROOT/relative)!=sha(copy):reject('reviewed_reader_source_unverified')
    for name,wanted in manifest['artifacts'].items():
        path=manifest_path.parent/name
        if sha(path)!=wanted:reject('reviewed_native_artifact_changed')
        evidence[str(path)]=wanted
    evidence[str(manifest_path)]=sha(manifest_path)
    return session,binding,status,manifest,manifest_path,evidence


def capture(run,run_id,output):
    if output.exists() or not output.is_relative_to(ROOT/'reports'):reject('fresh_local_capture_required')
    output.mkdir(parents=True);source=output/'source';source.mkdir()
    for path in (Path(__file__),ROOT/'integration/host_runtime/macro_native_presence.py'):
        shutil.copy2(path,source/path.name)
    result=dict(kind='macro_before_attach_passive_capture',schema_version=5,run_id=run_id,native_release_verified=False,
        native_writes=0,sdk_game_calls=0,lease_acquire_or_release_calls=0,credentials_accessed=False,model_calls=0,completed=False)
    memory=None;stage='frozen_inputs'
    try:
        session,binding,status,manifest,manifest_path,evidence=inputs(run,run_id)
        result.update(binding=binding.public(),host_pid=status['host_pid'],host_start_time=status['host_start_time'],
            expected_process_creation_filetime=session['process_creation_filetime'],native_manifest_sha256=sha(manifest_path),
            input_sha256=evidence,reviewed_native_source_sha256=NATIVE_SHA,reviewed_dll_sha256=DLL_SHA)
        stage='held_readonly_process'
        win=importlib.import_module('observe_production');memory=win.Memory(session['pid'],session);kernel=win.k
        identity=process_identity(kernel,memory.handle)
        if (identity['pid']!=binding.game_process_id or identity['process_creation_filetime']!=session['process_creation_filetime']
                or identity['image_sha256']!=binding.game_sha256 or Path(identity['image_path'])!=Path(session['game']).resolve()):reject('exact_process_identity_mismatch')
        result['identity_before']=identity
        result['host_state_before']=host_state(kernel,status['host_pid'],status['host_start_time'])
        stage='first_module_inventory';before,api=modules(memory,kernel);result['modules_before']=before;result['modules_before_api']=api
        stage='first_objects';first=query_macro_objects(session['pid'],manifest['mapping_prefix'],kernel=kernel);result['objects_before']=first
        stage='first_twenty_flags';reader=importlib.import_module('read_script_flags');flags_before=reader.inspect_flags(memory.read,manifest['flags']);result['flags_before']=flags_before
        stage='second_twenty_flags';flags_after=reader.inspect_flags(memory.read,manifest['flags']);result['flags_after']=flags_after
        stage='second_objects';second=query_macro_objects(session['pid'],manifest['mapping_prefix'],kernel=kernel);result['objects_after']=second
        stage='second_module_inventory';after,api=modules(memory,kernel);result['modules_after']=after;result['modules_after_api']=api
        stage='final_identity_and_source';result['identity_after']=process_identity(kernel,memory.handle)
        result['host_state_after']=host_state(kernel,status['host_pid'],status['host_start_time'])
        if result['identity_after']!=identity or before!=after or flags_before!=flags_after:reject('passive_capture_changed')
        main=[row for row in after if int(row['base'],0)==0x400000]
        if (len(main)!=1 or main[0]['image_bits']!=32 or main[0]['file_sha256']!=identity['image_sha256']
                or Path(main[0]['mapped_backing_path'])!=Path(identity['image_path'])):reject('main_module_held_identity_mismatch')
        for path,wanted in evidence.items():
            if sha(path)!=wanted:reject('capture_source_changed')
        control=[row for row in after if row['file_sha256']==DLL_SHA or row['reviewed_x86_hook_eligible']
            and (row['control_exports'] or 'macropolicy' in row['name'].lower())]
        result['control_modules']=control
        quiescent_flags=(type(flags_after.get('flags')) is list and len(flags_after['flags'])==20
            and [row.get('name') for row in flags_after['flags']]==manifest['flags']
            and all(row.get('present') is False or row.get('present') is True and row.get('value') is False for row in flags_after['flags']))
        result.update(completed=True,complete_module_double_enumeration=True,complete_x86_module_double_enumeration=True,
            module_machine_counts={str(bits):sum(row['image_bits']==bits for row in after) for bits in (32,64)},reviewed_macro_control_dll_absent=not control,
            reviewed_macro_hook_absent_via_pinned_module_invariant=not control and first['mapping_status']==second['mapping_status']=='absent',
            twenty_flags_quiescent=quiescent_flags,objects_quiescent=first['mapping_status']==second['mapping_status']=='absent'
                and first['semaphore_status'] in ('absent','free') and second['semaphore_status'] in ('absent','free'),
            hook_scope='reviewed_MacroPolicyControl_only_not_arbitrary_system_hooks')
    except BaseException as error:
        result.update(failure_stage=stage,error_type=type(error).__name__,reason_code=str(error) if isinstance(error,ValueError) and str(error).replace('_','').isalnum() else 'passive_capture_unverified')
        if isinstance(error,CaptureFailure):result['api_telemetry']=error.telemetry
        else:result['last_win32_error']=int(c.get_last_error())
    finally:
        if memory is not None:memory.close()
        (output/'capture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-directory',type=Path,required=True);p.add_argument('--run-id',required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=capture(args.run_directory.resolve(),args.run_id,args.output.resolve())
    print(json.dumps({key:result.get(key) for key in ('completed','failure_stage','reason_code','reviewed_macro_control_dll_absent','twenty_flags_quiescent','objects_quiescent','native_release_verified')}))


if __name__=='__main__':main()
