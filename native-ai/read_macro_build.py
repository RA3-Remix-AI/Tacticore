"""Bounded read-only native macro builder study; never attaches an actuator."""
import argparse
import ctypes as c
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'native-ai'),str(ROOT/'production'),str(ROOT/'visibility')]
from observe_production import Memory,k,w
from session_package import verify_session_package
from macro_build_observation import NativeBuildObserver

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session',type=Path,required=True);p.add_argument('--owner',type=lambda x:int(x,0),required=True)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=20);p.add_argument('--interval',type=float,default=.25);a=p.parse_args()
    if not 1<=a.seconds<=180 or not .1<=a.interval<=2:raise ValueError('bounded_native_macro_builder_observation')
    out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_local_builder_observation_required')
    raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));verify_session_package(session)
    manifest=json.loads((a.build/'build-manifest.json').read_text(encoding='utf-8'))
    if manifest['package_sha256']!=session['mod_sha256']:raise ValueError('builder_package_mismatch')
    memory=Memory(session['pid'],session)
    try:
        times=[w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(memory.handle,*[c.byref(x) for x in times]):raise RuntimeError('builder_identity_unavailable')
        if times[0].dwLowDateTime|times[0].dwHighDateTime<<32!=session['process_creation_filetime']:raise ValueError('builder_creation_mismatch')
        observer=NativeBuildObserver(memory,a.owner,manifest['flags'])
        out.mkdir(parents=True);source=out/'source';source.mkdir();pins=[]
        for i,path in enumerate([Path(__file__),ROOT/'native-ai/macro_build_observation.py',ROOT/'native-ai/macro_observation.py',
                ROOT/'native-ai/read_selected_personality.py',ROOT/'production/observe_production.py',ROOT/'production/session_package.py',
                ROOT/'probe.py',a.session,a.build/'build-manifest.json']):
            target=source/(str(i)+'-'+path.name);shutil.copy2(path,target)
            pins.append(dict(path=str(path.resolve()),copy=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        (out/'preflight.json').write_text(json.dumps(dict(session_id=session['session_id'],pid=session['pid'],sources=pins),indent=2),encoding='utf-8')
        started=time.monotonic();samples=errors=0
        with (out/'native-builder-observations.jsonl').open('x',encoding='utf-8') as stream:
            while time.monotonic()-started<a.seconds:
                if a.session.read_bytes()!=raw:raise ValueError('builder_session_changed')
                try:value=observer.sample();samples+=1
                except (ValueError,RuntimeError) as error:value={'read_error':str(error)};errors+=1
                stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();time.sleep(a.interval)
        report=dict(session_id=session['session_id'],samples=samples,read_errors=errors,mutations=False,native_calls=0,
            product_capability_granted=False,construction_or_production_effect_verified=False)
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(dict(output=str(out),**report)))
    finally:memory.close()
