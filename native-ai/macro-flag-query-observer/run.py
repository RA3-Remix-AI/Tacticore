"""Bind and record one passive native AI flag-query observation, <=30s."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'production'));sys.path.insert(0,str(ROOT/'native-ai'))
from observe_production import Memory,k
from session_package import verify_session_package
from read_selected_personality import inspect_player
from read_script_flags import inspect_flags
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def save(path,data):
    with path.open('x',encoding='utf-8') as stream:stream.write(json.dumps(data,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--owner',type=lambda x:int(x,0),required=True)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=20);args=parser.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports') or not 1<=args.seconds<=30:raise ValueError('fresh_bounded_report_required')
    raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));package=verify_session_package(session)
    manifest_path=args.build/'build-manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for row in manifest['sources']:
        if sha(Path(row['path']))!=row['sha256']:raise ValueError('observer_source_changed')
    if type(manifest.get('epoch')) is not int or not 1<=manifest['epoch']<=999:raise ValueError('observer_epoch_required')
    if set(manifest['artifacts'])!={'MacroFlagQueryV'+str(manifest['epoch'])+'.dll','observe_flag_query.exe'}:raise ValueError('observer_artifact_set')
    for name,digest in manifest['artifacts'].items():
        if sha(args.build/name)!=digest:raise ValueError('observer_binary_changed')
    memory=Memory(session['pid'],session)
    try:
        times=[w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(memory.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())
        creation=times[0].dwLowDateTime|times[0].dwHighDateTime<<32
        if creation!=session.get('process_creation_filetime'):raise ValueError('exact_process_creation_mismatch')
        native=inspect_player(memory.read,args.owner)
        if native['player_index']!=3 or int(native['instance_id'],0)!=0x799613e0:raise ValueError('exact_probe_personality_required')
        package_report=json.loads(Path(session['macro_package_report']).read_text(encoding='utf-8'))
        if package_report['big_sha256']!=sha(package):raise ValueError('package_report_mismatch')
        names=list(package_report['flags'].values());flags=inspect_flags(memory.read,names)
        if any(row['value'] is True for row in flags['flags']):raise ValueError('passive_baseline_requires_all_macro_flags_off')
        before=memory.read(0x889bf0,17)
        if before.hex()!='8bc18b40048b5008518bcc52e80f2dc4ff':raise ValueError('query_signature_mismatch')
        out.mkdir(parents=True)
        shutil.copy2(HERE/'run.py',out/'run.py');shutil.copy2(args.build/'observer.cpp',out/'observer.cpp');shutil.copy2(manifest_path,out/'build-manifest.json')
        save(out/'preflight.json',dict(session_sha256=hashlib.sha256(raw).hexdigest(),creation_filetime=creation,native=native,
            mod_sha256=sha(package),flags=flags,query_bytes=before.hex(),runner_sha256=sha(HERE/'run.py')))
        with (out/'native.json').open('x',encoding='utf-8') as stream, (out/'stderr.log').open('x',encoding='utf-8') as error:
            result=subprocess.run([str((args.build/'observe_flag_query.exe').resolve()),str(session['pid']),str(args.seconds)],stdout=stream,stderr=error,timeout=50)
        data=json.loads((out/'native.json').read_text(encoding='utf-8'))
        after=memory.read(0x889bf0,17)
        stable=args.session.read_bytes()==raw and sha(package)==session['mod_sha256'] and inspect_player(memory.read,args.owner)==native
        queried={name:sum(e['name']==name for e in data['events']) for name in names}
        results={name:{str(value):sum(e['name']==name and e['result_bits']==bits for e in data['events'])
            for value,bits in [(0,0),(1,0x3f800000)]} for name in names}
        report=dict(returncode=result.returncode,identity_stable=stable,independent_query_bytes_restored=after==before,
            flags_after=inspect_flags(memory.read,names),sampled_query_counts=queried,
            all_query_results_zero=all(e['result_bits']==0 for e in data['events']),
            ai_player=native['ai_player'],observed_arg1_values=sorted({e['arg1'] for e in data['events']}),
            query_result_counts=results,all_matching_queries_bound_to_ai=all(int(e['arg1'],0)==int(native['ai_player'],0) for e in data['events']),
            native_restore_verified=data.get('independent_restore_verified'),setters_called=0,
            macro_effect_verified=False,capability_granted=False,
            passive_query_observed=bool(queried) and all(queried.values()),
            complete=result.returncode==0 and stable and after==before and data.get('phase')==2)
        save(out/'report.json',report)
        print(json.dumps(dict(output=str(out),**report)))
        if not report['complete']:raise ValueError('passive_observer_cleanup_or_binding_unverified')
    finally:memory.close()


if __name__=='__main__':main()
