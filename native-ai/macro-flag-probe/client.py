"""Bounded false/true/false native flag probe with explicit compiled modes.

Diagnostic mode uses an unreferenced name. Scout mode briefly enables exactly
the compiled native scouting state. Normal ScriptAction allocation and the
common-script helper run on the game UI thread; independent external tree
readback is mandatory after every transition. This does not grant a product API.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'production'))
sys.path.insert(0, str(ROOT/'native-ai'))
sys.path.insert(0, str(ROOT/'visibility'))
from observe_production import Memory, k
from session_package import verify_session_package
from read_selected_personality import inspect_player
from read_script_flags import inspect_flags
from macro_observation import MacroObserver

FLAG_NAME = '/TFMacroFlagABI_57e668b44d8943bdbc920dd436f046ef_P3'
SCOUT_FLAG = '/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_scout'
AIRFIELD_FLAG = '/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_build_airfield'
U, L = c.c_uint32, c.c_int32


class Shared(c.Structure):
    _fields_ = [(x, U) for x in 'magic version pid thread start_low start_high owner ai personality personality_id player_template engine'.split()] + [
        (x, L) for x in 'request ack phase active'.split()] + [(x, U) for x in
        'error attempted callback_thread start_tick start_frame last_frame before after cleanup_verified watchdog_requested'.split()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
        stream.flush()
        __import__('os').fsync(stream.fileno())


def prior_stop(memory, path, session, native, flag_name, creation):
    """Require a completed earlier round plus its still-live stopped native map."""
    report=json.loads(path.read_text(encoding='utf-8'))
    final=report.get('native_final',{})
    transitions=report.get('transitions',[])
    required=dict(phase=2,ack=3,error=0,active=0,cleanup_verified=1)
    if (report.get('pid')!=session['pid'] or report.get('session_id')!=session['session_id']
        or report.get('mode')!='scout_state' or report.get('flag_name')!=flag_name
        or report.get('complete') is not True or report.get('cleanup_verified') is not True
        or report.get('host_returncode')!=0 or any(final.get(key)!=value for key,value in required.items())
        or len(transitions)!=3 or transitions[-1].get('request')!=3 or transitions[-1].get('expected') is not False):
        raise ValueError('previous_native_stop_evidence_required')
    name=report.get('native_mapping_name','Local\\RA3MacroScoutState_'+str(session['pid']))
    if name!='Local\\RA3MacroScoutState_'+str(session['pid']):
        epoch=report.get('epoch')
        if type(epoch) is not int or not 1<=epoch<=999 or name!=f'Local\\RA3MacroScoutStateV{epoch}_'+str(session['pid']):
            raise ValueError('previous_native_mapping_name')
    k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE
    k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
    k.UnmapViewOfFile.argtypes=[c.c_void_p]
    mapping=k.OpenFileMappingW(4,False,name)
    if not mapping:raise ValueError('previous_native_stop_map_unavailable')
    view=None
    try:
        view=k.MapViewOfFile(mapping,4,0,0,c.sizeof(Shared))
        if not view:raise ValueError('previous_native_stop_map_read_unavailable')
        raw=c.string_at(view,c.sizeof(Shared));state=Shared.from_buffer_copy(raw)
        expected=dict(magic=0x4d464150,version=1,pid=session['pid'],start_low=creation&0xffffffff,start_high=creation>>32,
            owner=int(native['player'],0),ai=int(native['ai_player'],0),personality=int(native['personality_wrapper'],0),
            personality_id=int(native['instance_id'],0),player_template=int(native['player_template'],0),
            engine=memory.u32(0xcdd190),request=3,after=0,**required)
        if any(getattr(state,key)!=value for key,value in expected.items()) or c.string_at(view,len(raw))!=raw:
            raise ValueError('previous_native_stop_not_live_or_binding_changed')
        return dict(report=str(path.resolve()),report_sha256=sha(path),mapping_name=name,
            shared_sha256=hashlib.sha256(raw).hexdigest(),native_stop_live_verified=True,
            process_writes=0)
    finally:
        if view:k.UnmapViewOfFile(view)
        k.CloseHandle(mapping)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--owner', type=lambda x: int(x, 0), required=True)
    parser.add_argument('--probe-build', type=Path, required=True)
    parser.add_argument('--macro-package-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['diagnostic_abi', 'scout_state','build_airfield'], default='diagnostic_abi')
    parser.add_argument('--previous-stop-report',type=Path)
    parser.add_argument('--visibility-session',type=Path)
    parser.add_argument('--visibility-build-capability',type=Path)
    parser.add_argument('--visibility-safety',type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'reports'):
        raise ValueError('fresh_local_report_directory_required')
    session_raw = args.session.read_bytes(); session = json.loads(session_raw.decode('utf-8-sig'))
    package = verify_session_package(session)
    package_report = json.loads(args.macro_package_report.read_text(encoding='utf-8'))
    if package_report.get('variant')=='expanded_macro_policy_v1':
        raise ValueError('expanded_policy_requires_exclusive_persistent_transport')
    if (package_report.get('kind') != 'isolated_native_macro_probe' or package_report.get('compiled') is not True
        or package_report.get('big_sha256') != session.get('mod_sha256')
        or package_report.get('commander_id') != '57e668b4-4d89-43bd-bc92-0dd436f046ef'
        or package_report.get('player_slot') != 3):
        raise ValueError('macro_probe_package_binding')
    native_bin = args.probe_build.resolve()
    manifest_path = native_bin/'build-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('mode', 'diagnostic_abi') != args.mode:
        raise ValueError('probe_mode_mismatch')
    flag_name = AIRFIELD_FLAG if args.mode=='build_airfield' else SCOUT_FLAG if args.mode=='scout_state' else FLAG_NAME
    mapping_prefix = 'Local\\RA3MacroScoutState_' if args.mode=='scout_state' else 'Local\\RA3MacroFlagABI_'
    library = 'MacroScoutState.dll' if args.mode=='scout_state' else 'MacroFlagABI.dll'
    epoch=manifest.get('epoch')
    if epoch is not None:
        if args.mode=='diagnostic_abi' or type(epoch) is not int or not 1<=epoch<=999:
            raise ValueError('invalid_compiled_probe_epoch')
        mapping_prefix=f'Local\\RA3MacroScoutStateV{epoch}_'
        library=f'MacroScoutStateV{epoch}.dll'
        if args.mode=='build_airfield':
            mapping_prefix=f'Local\\RA3MacroAirfieldV{epoch}_';library=f'MacroAirfieldV{epoch}.dll'
    elif args.mode=='build_airfield':
        raise ValueError('airfield_requires_compiled_epoch')
    if set(manifest['artifacts']) != {'macro_flag_host.exe', library}:
        raise ValueError('probe_artifact_set_mismatch')
    for name, digest in manifest['artifacts'].items():
        if sha(native_bin/name) != digest:
            raise ValueError('probe_binary_hash_changed')
    for name, digest in manifest['sources'].items():
        if name not in {'shared.h', 'native.cpp', 'host.cpp', 'build.py'} or sha(HERE/name) != digest:
            raise ValueError('probe_source_changed_since_build')
    layout = dict(size=c.sizeof(Shared), request=Shared.request.offset, error=Shared.error.offset, after=Shared.after.offset)
    if manifest['layout'] != layout or json.loads(subprocess.check_output([str(native_bin/'macro_flag_host.exe'), '--layout'], text=True)) != layout:
        raise ValueError('shared_layout_mismatch')
    memory = Memory(session['pid'], session)
    host, state, mapping, view, log = None, None, None, None, None
    hold_seconds=180 if args.mode=='build_airfield' else 30 if args.mode=='scout_state' else 0
    report = dict(kind='native_script_flag_abi_diagnostic' if args.mode=='diagnostic_abi' else 'native_'+args.mode+'_gate_probe', field_macro_capability_granted=False,
        ai_consumption_verified=False, macro_effect_verified=False, unit_control=False,
        native_code_patches=0, session_id=session['session_id'], pid=session['pid'],
        flag_name=flag_name, mode=args.mode, output=str(output), transitions=[], complete=False,
        epoch=epoch,native_mapping_name=mapping_prefix+str(session['pid']),
        hold_seconds=hold_seconds)
    observations=[];observer=None;legal_reader=None;legal_proof=None
    try:
        times = [w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(memory.handle, *[c.byref(x) for x in times]):
            raise c.WinError(c.get_last_error())
        creation = times[0].dwLowDateTime | times[0].dwHighDateTime << 32
        if type(session.get('process_creation_filetime')) is not int or session['process_creation_filetime'] != creation:
            raise ValueError('exact_process_creation_required')
        native = inspect_player(memory.read, args.owner)
        if native['player_index'] != 3 or int(native['instance_id'], 0) != 0x799613e0:
            raise ValueError('exact_probe_personality_owner_required')
        if memory.u32(memory.u32(0xcd8ce4)+0x15c):
            raise ValueError('game_paused')
        before = inspect_flags(memory.read, [flag_name])
        previous=None
        if before['flags'][0]['present']:
            if args.mode!='scout_state' or epoch is None or not args.previous_stop_report or before['flags'][0]['value'] is not False:
                raise ValueError('existing_flag_requires_false_and_live_previous_stop')
            previous=prior_stop(memory,args.previous_stop_report,session,native,flag_name,creation)
            if previous['mapping_name']==report['native_mapping_name']:
                raise ValueError('new_round_requires_distinct_compiled_epoch')
        elif args.previous_stop_report:
            raise ValueError('previous_round_flag_missing')
        # The diagnostic name is deliberately not a gate in the compiled source.
        xml = args.macro_package_report.parent/'MacroProbe.xml'
        if sha(xml) != package_report['macro_xml_sha256']:
            raise ValueError('macro_source_changed')
        if args.mode=='diagnostic_abi' and flag_name in xml.read_text(encoding='utf-8'):
            raise ValueError('diagnostic_flag_must_have_no_ai_consumer')
        if args.mode!='diagnostic_abi' and (package_report['flags'].get('build_airfield' if args.mode=='build_airfield' else 'scout') != flag_name or flag_name not in xml.read_text(encoding='utf-8')):
            raise ValueError('exact_native_macro_gate_required')
        if args.mode!='diagnostic_abi':
            expected_feedback={phase:int(entry['hash'],0) for phase,entry in package_report['streams'][0].get('native_feedback',{}).items()}
            observer=MacroObserver(memory,args.owner,list(package_report['flags'].values()),expected_feedback,
                terrain_feedback=True,construction_feedback=args.mode=='build_airfield')
        visibility_args=[args.visibility_session,args.visibility_build_capability,args.visibility_safety]
        if any(visibility_args):
            if not all(visibility_args) or args.mode!='scout_state':
                raise ValueError('complete_visibility_evidence_requires_scout_probe')
            from capability import bind_session
            from projection import VisibilityProjection
            from collector import VisibilityCollector
            visible_session=json.loads(args.visibility_session.read_text(encoding='utf-8-sig'))
            if any(visible_session.get(key)!=session.get(key) for key in ['session_id','pid','process_creation_filetime','mod_sha256']):
                raise ValueError('visibility_macro_session_mismatch')
            legal_proof,safety=bind_session(memory,visible_session,3,args.visibility_build_capability,args.visibility_safety)
            legal_reader=VisibilityCollector(memory,visible_session,3,
                VisibilityProjection(session['session_id'],3,session['mod_sha256'],legal_proof,safety))
        output.mkdir(parents=True)
        source = output/'source'; source.mkdir()
        paths = [HERE/'shared.h', HERE/'native.cpp', HERE/'host.cpp', HERE/'build.py', Path(__file__),
            ROOT/'native-ai/read_script_flags.py', ROOT/'native-ai/test_script_flags.py',
            ROOT/'native-ai/stage_macro_probe.py', xml, args.macro_package_report, manifest_path, args.session]
        paths += [ROOT/'native-ai/macro_observation.py',ROOT/'native-ai/test_macro_observation.py',
            ROOT/'native-ai/read_selected_personality.py',ROOT/'production/observe_production.py',
            ROOT/'production/session_package.py',ROOT/'probe.py']
        paths += [ROOT/'visibility/native_read.py']
        if legal_reader is not None:
            save(output/'visibility-session-proof.json',legal_proof)
            paths += visibility_args+[ROOT/'visibility'/name for name in ['capability.py','collector.py','projection.py','audit_templates.py']]
        provenance = []
        for i, path in enumerate(paths):
            copy = source/(str(i)+'-'+path.name); shutil.copy2(path, copy)
            provenance.append(dict(path=str(path.resolve()), copy=copy.name, sha256=sha(copy)))
        save(output/'preflight.json', dict(session_sha256=hashlib.sha256(session_raw).hexdigest(),
            process_creation_filetime=creation, mod_sha256=sha(package), native=native,
            initial_flags=before, previous_stop=previous,sources=provenance, probe_artifacts=manifest['artifacts']))

        def observe(label):
            if observer is None:
                return
            try:
                value=dict(label=label,observation=observer.sample())
            except (ValueError,RuntimeError) as error:
                value=dict(label=label,read_error=str(error))
            if legal_reader is not None and 'observation' in value:
                try:
                    current_frame=memory.u32(memory.u32(0xcd8ce4)+0x50)
                    value['battlefield']=legal_reader.collect(current_frame/15)
                except (ValueError,RuntimeError) as error:
                    value['battlefield_read_error']=str(error)
            observations.append(value)
            with (output/'macro-observations.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(value,ensure_ascii=False)+'\n');stream.flush()
            return 'observation' in value and (legal_reader is None or 'battlefield' in value)

        if observer is not None and not observe('before_native_attach'):
            raise ValueError('native_macro_preflight_observation_unavailable')
        user = c.WinDLL('user32', use_last_error=True)
        user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        user.GetWindowThreadProcessId.restype = w.DWORD
        user.IsWindowVisible.argtypes = [w.HWND]
        user.IsWindowVisible.restype = w.BOOL
        user.GetWindow.argtypes = [w.HWND, w.UINT]
        user.GetWindow.restype = w.HWND
        user.EnumWindows.argtypes = [c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM), w.LPARAM]
        windows = []

        @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        def find_window(hwnd, unused):
            process_id = w.DWORD()
            thread = user.GetWindowThreadProcessId(hwnd, c.byref(process_id))
            if process_id.value == session['pid'] and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd, 4):
                windows.append((hwnd, thread))
            return True

        user.EnumWindows(find_window, 0)
        threads = {thread for _, thread in windows}
        if len(threads) != 1:
            raise ValueError('unique_game_window_thread_required')
        k.CreateFileMappingW.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR]
        k.CreateFileMappingW.restype = w.HANDLE
        k.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, c.c_size_t]
        k.MapViewOfFile.restype = c.c_void_p
        k.UnmapViewOfFile.argtypes = [c.c_void_p]
        mapping = k.CreateFileMappingW(w.HANDLE(-1), None, 4, 0, c.sizeof(Shared), mapping_prefix+str(session['pid']))
        if not mapping or c.get_last_error() == 183:
            raise ValueError('probe_already_used_in_process')
        view = k.MapViewOfFile(mapping, 0xf001f, 0, 0, c.sizeof(Shared))
        if not view:
            raise c.WinError(c.get_last_error())
        c.memset(view, 0, c.sizeof(Shared)); state = Shared.from_address(view)
        state.magic=0x4d464150; state.version=1; state.pid=session['pid']; state.thread=next(iter(threads))
        state.start_low=times[0].dwLowDateTime; state.start_high=times[0].dwHighDateTime; state.owner=args.owner
        for field, key in [('ai','ai_player'), ('personality','personality_wrapper'), ('personality_id','instance_id'), ('player_template','player_template')]:
            setattr(state, field, int(native[key], 0))
        state.engine=memory.u32(0xcdd190)
        state.request=1
        log=(output/'host.log').open('x', encoding='utf-8')
        save(output/'dispatch-pending.json', dict(request=1, cleanup_required=True, diagnostic_only=True))
        host=subprocess.Popen([str(native_bin/'macro_flag_host.exe'), str(session['pid'])], stdout=log, stderr=log)
        for request, expected in [(1, False), (2, True), (3, False)]:
            state.request=request
            deadline=time.monotonic()+5
            while state.ack != request and time.monotonic() < deadline:
                if host.poll() is not None or state.phase==4:
                    raise ValueError('native_probe_rejected_'+str(state.error))
                time.sleep(.01)
            if state.ack != request:
                raise ValueError('native_probe_outcome_unknown')
            sample=inspect_flags(memory.read, [flag_name])
            if not sample['flags'][0]['present'] or sample['flags'][0]['value'] is not expected:
                raise ValueError('independent_flag_readback_mismatch')
            row=dict(request=request, expected=expected, native_before=state.before, native_after=state.after,
                native_thread=state.callback_thread, expected_thread=state.thread,
                frame=state.last_frame, sample=sample)
            save(output/('transition-'+str(request)+'.json'), row)
            report['transitions'].append(row)
            observe('request_'+str(request)+'_readback')
            if request==2 and args.mode!='diagnostic_abi':
                # Let the original strategic/team managers evaluate several
                # natural updates. No actor is selected or commanded here.
                deadline=time.monotonic()+hold_seconds
                next_sample=0
                while time.monotonic()<deadline:
                    if host.poll() is not None or state.phase!=1 or state.ack!=2:
                        raise ValueError('scout_gate_lifecycle_changed')
                    if time.monotonic()>=next_sample:
                        observe('scout_gate_held')
                        next_sample=time.monotonic()+.5
                    time.sleep(.05)
                held=inspect_flags(memory.read,[flag_name])
                save(output/'gate-hold-end.json',held)
                if held['flags'][0]['value'] is not True:
                    raise ValueError('scout_gate_expired_during_hold')
            if request==3 and observer is not None:
                for i in range(4):
                    time.sleep(.5)
                    observe('after_native_clear_'+str(i))
        host.wait(timeout=5)
        if host.returncode or state.phase != 2 or state.ack != 3 or not state.cleanup_verified or state.active or state.error:
            raise ValueError('native_cleanup_unverified')
        if args.session.read_bytes() != session_raw or sha(package) != session['mod_sha256'] or inspect_player(memory.read,args.owner) != native:
            raise ValueError('binding_changed_during_probe')
        report.update(complete=True, diagnostic_abi_verified=args.mode=='diagnostic_abi', native_gate_readback_verified=True, cleanup_verified=True,
            game_thread_only=True, attempted=state.attempted, watchdog_requested=bool(state.watchdog_requested))
        samples=[v['observation'] for v in observations if 'observation' in v]
        report.update(native_macro_samples=len(samples),native_macro_read_errors=len(observations)-len(samples),
            native_state_score_positive_observed=any(s['state_scores'].get(flag_name,{}).get('score',0)>0 for s in samples),
            native_execution_active_observed=any(r['native_execution_active'] for s in samples for r in s['runtimes']))
        if legal_reader is not None:
            public=[v['battlefield'] for v in observations if 'battlefield' in v]
            report.update(legal_battlefield_samples=len(public),legal_battlefield_read_errors=sum('battlefield_read_error' in v for v in observations),
                currently_visible_contact_ids_observed=sorted({contact['contact_id'] for b in public for contact in b['contacts'] if contact['currently_visible']}),
                exclusively_attributed_to_macro_scout=False)
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        if state is not None and state.phase != 2:
            state.request=3
        if host:
            try:
                host.wait(timeout=55)
            except subprocess.TimeoutExpired:
                report['host_still_running']=True
            report['host_returncode']=host.poll()
        if state is not None:
            report['native_final']={name:int(getattr(state,name)) for name in ['phase','ack','error','active','attempted','cleanup_verified','watchdog_requested']}
        if output.exists():
            save(output/'report.json',report)
        if log and host and host.poll() is not None:
            log.close()
        if view:
            k.UnmapViewOfFile(view)
        if mapping:
            k.CloseHandle(mapping)
        memory.close()
    print(json.dumps(dict(output=str(output),complete=report['complete'],macro_effect_verified=False,capability_granted=False)))


if __name__ == '__main__':
    main()
