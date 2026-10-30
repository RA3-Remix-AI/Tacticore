"""End an explicitly owned, stopped research game after retaining its final facts.

Only preserves a natural settlement already independently archived; no formal replay claim.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai')]
from observe_production import Memory,k
from read_match_state import snapshot
from read_script_flags import inspect_flags


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session',type=Path,required=True);p.add_argument('--transport',type=Path,required=True)
    p.add_argument('--fixed-driver',type=Path,help='Completed fixed regional research directory, without any model host')
    p.add_argument('--reason',required=True);a=p.parse_args()
    path=a.session.resolve();session=json.loads(path.read_text(encoding='utf-8-sig'));run=Path(session['run_directory']).resolve()
    if path.parent!=run or not run.is_relative_to(ROOT/'acceptance/runs') or (run/'fixture-ended.json').exists():
        raise ValueError('fresh_owned_research_fixture_required')
    finalpath=a.transport.resolve()/'final-state.json';final=json.loads(finalpath.read_text())
    status=None
    if a.fixed_driver:
        directory=a.fixed_driver.resolve();driver=json.loads((directory/'driver-preflight.json').read_text())
        driver_names={'fixed_far_then_near_native_region_trial':'region-driver.py',
            'fixed_far_then_near_native_area_defense_candidate_trial':'area-defense-driver.py',
            'fixed_far_then_near_native_area_hold_candidate_trial':'area-hold-driver.py',
            'fixed_near_hold_then_far_native_area_candidate_trial':'area-hold-near-driver.py',
            'fixed_hold_then_attack_native_area_candidate_trial':'area-hold-first-driver.py',
            'fixed_native_own_base_defense_then_public_attack_trial':'base-defense-driver.py',
            'fixed_original_native_group_roles_trial':'group-role-driver.py',
            'fixed_original_native_group_roles_attack_first_trial':'group-role-attack-first-driver.py'}
        driver_name=driver_names.get(driver.get('kind'))
        if (not directory.is_relative_to(ROOT/'reports') or a.transport.resolve()!=directory/'transport'
                or (run/'battle-host').exists() or driver_name is None
                or driver['session_id']!=session['session_id'] or driver['pid']!=session['pid']
                or driver['process_creation_filetime']!=session['process_creation_filetime']
                or driver['model_calls']!=0 or driver['unit_orders']!=0
                or hashlib.sha256((directory/driver_name).read_bytes()).hexdigest()!=driver['driver_sha256']):
            raise ValueError('completed_owned_fixed_region_driver_required')
    else:
        status=json.loads((run/'battle-host/host-status.json').read_text());release=json.loads((run/'battle-host/macro-release.json').read_text())
        if (status['state'] not in ('stopped','fault','result_candidate') or status['session_id']!=session['session_id'] or status['pid']!=session['pid']
                or release['native_release_verified'] is not True or release['final_state_sha256']!=hashlib.sha256(finalpath.read_bytes()).hexdigest()):
            raise ValueError('research_host_release_required')
    if (final['session_id']!=session['session_id'] or final['pid']!=session['pid']
            or final['process_creation_filetime']!=session['process_creation_filetime'] or final['unknown_command_ids']!=[]
            or final['cleanup_verified'] is not True):raise ValueError('research_host_release_required')
    if not a.fixed_driver:
        # The explicit new V5 route precedes any native observation below.
        # Existing older research grammars retain their original boundaries.
        sys.path.insert(0,str(ROOT/'integration'))
        from host_runtime.macro_catalog_release_route_v1 import requires_v5
        if requires_v5(run/'battle-host',release=release):
            from acceptance.end_released_macro_fixture import review_transport_release
            manifest_path=a.transport/'source'/next(row['copy'] for row in json.loads((a.transport/'preflight.json').read_text())['sources']
                if Path(row['path']).name=='build-manifest.json')
            review_transport_release(path,a.transport,json.loads(manifest_path.read_text()),final)
    k.OpenMutexW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenMutexW.restype=w.HANDLE
    lease=k.OpenMutexW(0x100000,False,'Local\\RA3MacroPolicyLease_'+str(session['pid']))
    if lease:
        k.CloseHandle(lease);raise ValueError('native_macro_lease_still_present')
    manifest=json.loads((a.transport/'source'/next(row['copy'] for row in json.loads((a.transport/'preflight.json').read_text())['sources']
        if Path(row['path']).name=='build-manifest.json')).read_text())
    memory=Memory(session['pid'],session)
    try:
        state=snapshot(memory.read)
        natural=False
        if not state['simulation_frame'] or any(row['defeat_frame'] or row['victory_frame'] for row in state['result_records']):
            archive=json.loads((run/'research-settlement.json').read_text(encoding='utf-8-sig'))
            if (archive['session_id']!=session['session_id'] or archive['pid']!=session['pid']
                    or archive['process_creation_filetime']!=session['process_creation_filetime']
                    or archive.get('natural_settlement_verified') is not True):
                raise ValueError('archive_natural_result_before_ending')
            for key in ('screenshot','replay'):
                artifact=(run/archive[key]).resolve()
                if artifact.parent!=run or hashlib.sha256(artifact.read_bytes()).hexdigest()!=archive[key+'_sha256']:
                    raise ValueError('natural_result_archive_changed')
            natural=True
        if status is not None and status['state']=='result_candidate' and not natural:
            raise ValueError('archive_natural_result_candidate_before_ending')
        flags=inspect_flags(memory.read,manifest['flags'])
        if any(row['present'] and row['value'] is not False for row in flags['flags']):raise ValueError('live_macro_flags_not_clear')
        (run/'post-model-research-native-state.json').write_text(json.dumps(dict(state=state,flags=flags),indent=2)+'\n')
    finally:memory.close()
    handle=k.OpenProcess(0x101001,False,session['pid'])
    if not handle:raise c.WinError(c.get_last_error())
    try:
        times=[w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle,*[c.byref(t) for t in times]):raise c.WinError(c.get_last_error())
        if times[0].dwLowDateTime|times[0].dwHighDateTime<<32!=session['process_creation_filetime']:
            raise ValueError('exact_owned_process_creation_required')
        image=c.create_unicode_buffer(32768);size=w.DWORD(len(image))
        if not k.QueryFullProcessImageNameW(handle,0,image,c.byref(size)):raise c.WinError(c.get_last_error())
        if Path(image.value).resolve()!=Path(session['game']).resolve():raise ValueError('exact_owned_process_image_required')
        proof=dict(pid=session['pid'],process_creation_filetime=session['process_creation_filetime'],reason=a.reason,
            natural_settlement=natural,formal_G7=False,replay_claimed=False,last_observed_frame=state['simulation_frame'],
            all_macro_flags_clear=True,native_macro_lease_absent=True)
        proof['fixed_research_without_model_host']=a.fixed_driver is not None
        with (run/'planned-fixture-end.json').open('x') as stream:json.dump(proof,stream,indent=2)
        k.TerminateProcess.argtypes=[w.HANDLE,w.UINT];k.TerminateProcess.restype=w.BOOL
        if not k.TerminateProcess(handle,0):raise c.WinError(c.get_last_error())
        k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
        if k.WaitForSingleObject(handle,5000)!=0:raise ValueError('owned_fixture_exit_not_observed')
        proof['exact_owned_process_handle_terminated']=True
        with (run/'fixture-ended.json').open('x') as stream:json.dump(proof,stream,indent=2)
        print(json.dumps(proof))
    finally:k.CloseHandle(handle)


if __name__=='__main__':main()
