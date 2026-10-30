"""Keep current source bytes immutable while a bounded field child owns Native.

Read-sharing Win32 handles deny edits/deletes during the trial. No game writes
are performed here; source locks are released only after confirmed return or
when the child demonstrably never attempted native attachment.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'native-ai')]
from strategic_transport_profile_v1 import verify_build,load,sha


class SourceLocks:
    def __init__(self,paths):
        self.kernel=c.WinDLL('kernel32',use_last_error=True);self.handles=[]
        self.kernel.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
        self.kernel.CreateFileW.restype=w.HANDLE;self.kernel.CloseHandle.argtypes=[w.HANDLE]
        try:
            for path in paths:
                handle=self.kernel.CreateFileW(str(Path(path).resolve()),0x80000000,1,None,3,0x80,None)
                if handle in (None,c.c_void_p(-1).value):raise c.WinError(c.get_last_error())
                self.handles.append(handle)
        except BaseException:self.close();raise

    def close(self):
        for handle in self.handles:self.kernel.CloseHandle(handle)
        self.handles=[]


def record_owner(session,state,pins,**extra):
    path=ROOT/'acceptance/strategic-active-owner.json'
    value=dict(schema_version=1,owner_thread='01a1856c-3b1e-7413-a45c-f2aa2db875c9',state=state,
        updated_at_utc=datetime.now(timezone.utc).isoformat(),formal_games_passed=0,formal_games_required=3,
        game_pid=session['pid'],session_id=session['session_id'],frozen_sources=pins,**extra)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temp.replace(path)


def released(output):
    try:
        final=load(output/'final-state.json');review=load(output/'independent-release.json')
        return (final['cleanup_verified'] is True
            and review['native_release_verified'] is True
            and review['native']==final['native'] and review['semaphore_current']==review['semaphore_maximum']==1
            and final['native']['phase']==2 and final['native']['lease_held']==0 and final['native']['self_hook_installed']==0)
    except (OSError,ValueError,KeyError,TypeError):return False


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','output','runner'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();session=load(args.session);manifest=load(args.build/'build-manifest.json')
    output=args.output.resolve();runner=args.runner.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports') or not runner.is_relative_to(ROOT/'acceptance'):
        raise ValueError('fresh_owned_guarded_trial_required')
    pins=dict(manifest['sources']);pins[str(runner)]=sha(runner);pins[str(Path(__file__).resolve())]=sha(__file__)
    locks=SourceLocks(pins)
    unlocked=False;child=None
    try:
        if any(sha(path)!=expected for path,expected in pins.items()):raise ValueError('source_changed_before_guard')
        verify_build(args.build)
        record_owner(session,'field_running',pins,trial_output=str(output))
        child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(runner),'--session',str(args.session.resolve()),
            '--build',str(args.build.resolve()),'--output',str(output)],cwd=ROOT)
        result=child.wait()
        prepared=False
        journal=output/'policy-probe.jsonl'
        if journal.exists():
            prepared=any(json.loads(line).get('kind')=='attach_prepared' for line in journal.read_text(encoding='utf8').splitlines())
        while prepared and not released(output):
            record_owner(session,'field_cleanup_pending',pins,trial_output=str(output),child_returncode=result)
            print(json.dumps(dict(phase='waiting_for_independent_return',source_locks_retained=True)),flush=True)
            time.sleep(10)
        record_owner(session,'implementing',{},last_trial=str(output),last_trial_returncode=result,
                     last_native_release_verified=released(output),game_still_open=True)
        locks.close();unlocked=True
        print(json.dumps(dict(phase='guard_released',child_returncode=result,source_hashes_stable=all(sha(path)==expected for path,expected in pins.items()))),flush=True)
        return result
    finally:
        if not unlocked:
            if child is not None:
                while child.poll() is None:time.sleep(.5)
                journal=output/'policy-probe.jsonl'
                prepared=journal.exists() and any(json.loads(line).get('kind')=='attach_prepared'
                    for line in journal.read_text(encoding='utf8').splitlines())
                while prepared and not released(output):
                    record_owner(session,'field_cleanup_pending',pins,trial_output=str(output))
                    time.sleep(5)
            locks.close()


if __name__=='__main__':raise SystemExit(main())
