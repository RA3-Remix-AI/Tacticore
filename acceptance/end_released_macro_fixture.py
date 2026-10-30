"""End one explicitly bound research game only after current independent release.

This is a non-natural research ending, never a formal match result. It neither
claims nor releases a semaphore and never sends game commands or unit orders.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'native-ai'),str(ROOT/'production')]
from observe_production import Memory
from read_script_flags import inspect_flags

REQUIRED=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0)

def review_transport_release(session_path,transport,manifest,final):
    """Choose a source-bound release grammar before opening an end handle."""
    sys.path.insert(0,str(ROOT/'integration'))
    from host_runtime.macro_release_review_v4 import publication_v4_was_selected,v4_release_trial
    host=Path(session_path).resolve().parent/'battle-host'
    proof_path=host/'macro-release.json'
    proof=json.loads(proof_path.read_text(encoding='utf-8-sig')) if proof_path.exists() else {}
    if type(proof) is not dict:raise ValueError('release_proof_invalid')
    from host_runtime.macro_catalog_release_route_v1 import requires_v5,reviewed_v5_trial
    if requires_v5(host,release=proof):
        return reviewed_v5_trial(transport,output=host,release=proof,expected=manifest)
    extensions=('native_release_contract','publication_v4_contract_sha256','publication_v4_release_review_sha256')
    if publication_v4_was_selected(host) or any(key in proof for key in extensions):
        return v4_release_trial(transport,contract_path=host/'publication-v4-contract.json',expected=manifest)
    from host_runtime.macro_expansion_scope import v2_trial
    return v2_trial(transport,fault=final.get('intentional_external_host_loss') is True,expected=manifest)


def safe_release(session,manifest,final,state,flags,current_count,maximum_count):
    try:
        expected=manifest['flags'];created=state['start_low']|(state['start_high']<<32)
        return (manifest['protocol_version']==2 and len(expected)==20 and len(set(expected))==20
            and final['session_id']==session['session_id'] and final['pid']==session['pid']
            and final['process_creation_filetime']==session['process_creation_filetime']
            and final['mod_sha256']==session['mod_sha256']==manifest['package_sha256']
            and type(final['host_returncode']) is int
            and (final['host_returncode']==0 and final.get('intentional_external_host_loss',False) is False
                or final['host_returncode']!=0 and final.get('intentional_external_host_loss') is True
                and type(state.get('watchdog_reason')) is int and state['watchdog_reason']==1
                and final['native'].get('watchdog_reason')==1)
            and final['cleanup_verified'] is True and final['unknown_command_ids']==[]
            and state['magic']==0x4d503032 and state['version']==2 and state['pid']==session['pid']
            and created==session['process_creation_filetime'] and state['request']==state['ack']
            and all(type(state.get(k)) is int and state[k]==v and type(final['native'].get(k)) is int and final['native'][k]==v for k,v in REQUIRED.items())
            and len(flags['flags'])==20 and {r['name'] for r in flags['flags']}==set(expected)
            and all(type(r['present']) is bool and (not r['present'] or r['value'] is False) for r in flags['flags'])
            and type(current_count) is int and type(maximum_count) is int and current_count==maximum_count==1)
    except (KeyError,TypeError,ValueError):return False

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','transport','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_local_end_evidence_required')
    session=json.loads(args.session.read_text(encoding='utf-8-sig'))
    manifest=json.loads((args.build/'build-manifest.json').read_text(encoding='utf8'))
    final_path=args.transport/'final-state.json';final=json.loads(final_path.read_text(encoding='utf8'))
    # A fault helper exit is expected only for the independently validated
    # host-loss scene. It cannot excuse an arbitrary crashed or unknown run.
    review_transport_release(args.session,args.transport,manifest,final)
    spec=importlib.util.spec_from_file_location('released_macro_fixture_v2',ROOT/'native-ai/macro-policy-runtime-v2/client.py')
    runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
    kernel=c.WinDLL('kernel32',use_last_error=True);ntdll=c.WinDLL('ntdll',use_last_error=True)
    kernel.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];kernel.OpenFileMappingW.restype=w.HANDLE
    kernel.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];kernel.MapViewOfFile.restype=c.c_void_p
    kernel.UnmapViewOfFile.argtypes=[c.c_void_p];kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.OpenSemaphoreW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];kernel.OpenSemaphoreW.restype=w.HANDLE
    ntdll.NtQuerySemaphore.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)];ntdll.NtQuerySemaphore.restype=c.c_long
    class SemaphoreInfo(c.Structure):_fields_=[('current',c.c_long),('maximum',c.c_long)]
    mapping=kernel.OpenFileMappingW(4,False,manifest['mapping_prefix']+str(session['pid']))
    if not mapping:raise ValueError('retained_release_mapping_unavailable')
    view=kernel.MapViewOfFile(mapping,4,0,0,c.sizeof(runtime.Shared))
    if not view:kernel.CloseHandle(mapping);raise ValueError('retained_release_mapping_unavailable')
    sem=kernel.OpenSemaphoreW(1,False,'Local\\RA3MacroPolicyLease_'+str(session['pid']))
    memory=None
    try:
        if not sem:raise ValueError('actual_policy_semaphore_query_unavailable')
        info=SemaphoreInfo();returned=w.ULONG()
        status=ntdll.NtQuerySemaphore(sem,0,c.byref(info),c.sizeof(info),c.byref(returned))
        if status!=0 or returned.value!=c.sizeof(info):raise ValueError('actual_policy_semaphore_query_unknown')
        memory=Memory(session['pid'],session)
        first=runtime.Shared.from_buffer_copy(c.string_at(view,c.sizeof(runtime.Shared)))
        flags=inspect_flags(memory.read,manifest['flags'])
        current=runtime.Shared.from_buffer_copy(c.string_at(view,c.sizeof(runtime.Shared)))
        state={name:int(getattr(current,name)) for name,_ in runtime.Shared._fields_}
        if any(getattr(first,key)!=getattr(current,key) for key in REQUIRED):raise ValueError('release_state_changed')
        if not safe_release(session,manifest,final,state,flags,info.current,info.maximum):raise ValueError('current_independent_release_not_verified')
    finally:
        if memory:memory.close()
        if sem:kernel.CloseHandle(sem)
        kernel.UnmapViewOfFile(view);kernel.CloseHandle(mapping)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.GetProcessTimes.argtypes=[w.HANDLE]+[c.POINTER(w.FILETIME)]*4
    kernel.TerminateProcess.argtypes=[w.HANDLE,w.UINT];kernel.TerminateProcess.restype=w.BOOL
    kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
    handle=kernel.OpenProcess(0x101001,False,session['pid'])
    if not handle:raise ValueError('exact_research_process_handle_unavailable')
    record=dict(kind='exact_released_macro_research_fixture_end',session_id=session['session_id'],pid=session['pid'],
        process_creation_filetime=session['process_creation_filetime'],natural_settlement=False,formal_candidate_match=False,
        current_native=state,independent_flags=flags,semaphore_query=dict(api='NtQuerySemaphore',current=info.current,maximum=info.maximum,acquired=False),
        final_state_sha256=hashlib.sha256(final_path.read_bytes()).hexdigest(),ended=False,
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    try:
        times=[w.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*[c.byref(t) for t in times]):raise ValueError('exact_creation_read_failed')
        if times[0].dwLowDateTime|(times[0].dwHighDateTime<<32)!=session['process_creation_filetime']:raise ValueError('exact_creation_changed')
        out.mkdir();path=out/'record.json';path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        if not kernel.TerminateProcess(handle,0):raise ValueError('owned_research_process_end_failed')
        if kernel.WaitForSingleObject(handle,5000)!=0:raise ValueError('owned_research_process_end_unconfirmed')
        record['ended']=True;path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    finally:kernel.CloseHandle(handle)
    print(json.dumps(dict(output=str(out),pid=session['pid'],ended=True,natural_settlement=False)))

if __name__=='__main__':main()
