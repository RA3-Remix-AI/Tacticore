"""Cancel a provably unclaimed host launch through the normal journal API.

Never reconciles dispatching/unknown delivery, writes game memory or starts a
host. Original launch and cancellation records remain in the durable journal.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'production'),str(ROOT/'native-ai')]
from host_runtime.desktop_registry import load_registration
from host_runtime.desktop_session_registry import load_root
from host_runtime.profile_store import ProfileStore
from host_runtime.desktop_backend import DesktopBackend
from observe_production import Memory,k
from read_script_flags import inspect_flags
from read_match_state import snapshot

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-id',required=True)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    uuid.UUID(a.run_id);out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_unsent_review_required')
    home=Path(os.environ['LOCALAPPDATA'])/'Tacticore';state=home/'desktop-runtime';registration=load_registration(home)
    store=ProfileStore(Path(registration['library_path']),state)
    backend=DesktopBackend(store,registration_root=Path(load_root(state)['session_root']))
    try:
        row=backend._launch(a.run_id);commands=backend.journal.commands_for_run(a.run_id)
        if len(commands)!=1 or commands[0]['operation']!='host_start' or commands[0]['status']!='reserved':
            raise ValueError('only_unclaimed_reserved_host_start_can_be_cancelled')
        session=json.loads(Path(row['session_path']).read_text(encoding='utf-8-sig'));run=Path(session['run_directory'])
        if not run.resolve().is_relative_to(ROOT/'acceptance/runs') or Path(row['output_path'])!=run/'battle-host':
            raise ValueError('owned_macro_session_required')
        if (run/'battle-host').exists() or (state/'runs'/a.run_id/'host.log').exists():
            raise ValueError('host_execution_artifacts_present')
        manifest=json.loads((a.build/'build-manifest.json').read_text())
        if manifest['package_sha256']!=session['mod_sha256']:raise ValueError('unsent_package_mismatch')
        k.OpenMutexW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenMutexW.restype=w.HANDLE
        lease=k.OpenMutexW(0x100000,False,'Local\\RA3MacroPolicyLease_'+str(session['pid']))
        if lease:k.CloseHandle(lease);raise ValueError('macro_lease_present')
        memory=Memory(session['pid'],session)
        try:
            flags=inspect_flags(memory.read,manifest['flags']);native=snapshot(memory.read)
            if len(flags['flags'])!=13 or any(r['present'] and r['value'] is not False for r in flags['flags']):
                raise ValueError('macro_flags_not_clear')
        finally:memory.close()
        out.mkdir();shutil.copy2(__file__,out/'reviewer.py')
        shutil.copy2(ROOT/'integration/host_runtime/desktop_backend.py',out/'desktop_backend.py')
        proof=dict(kind='unclaimed_macro_host_launch_cancellation',run_id=a.run_id,session_id=session['session_id'],
            pid=session['pid'],process_creation_filetime=session['process_creation_filetime'],
            before_status=commands[0]['status'],native_macro_lease_absent=True,independent_flags=flags,native_state=native,
            sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()},
            model_calls=0,native_calls=0,process_writes=0,native_host_started=False,formal_goal_complete=False)
        result=backend.run_stop(dict(run_id=a.run_id,session_id=session['session_id']),str(uuid.uuid4()))
        command=backend.journal.get_command(a.run_id,row['request_id'])
        if command['status']!='cancelled' or result.get('no_native_execution_started') is not True:
            raise ValueError('unclaimed_cancellation_not_confirmed')
        proof.update(after_status=command['status'],receipt=command['receipt'],public_status=result,
            unresolved=backend.journal.unresolved(a.run_id))
        (out/'review.json').write_text(json.dumps(proof,indent=2)+'\n')
        print(json.dumps(dict(run_id=a.run_id,before='reserved',after=command['status'],no_native_execution_started=True)))
    finally:backend.close();store.close()

if __name__=='__main__':main()
