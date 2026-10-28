"""Fixed, bounded original-AI scouting plus lawful player-perspective feedback.

Research only. No provider, per-unit order, custom target pointer or product grant.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration'),str(ROOT/'strategy'),str(ROOT/'production'),str(ROOT/'native-ai')]
from observe_production import Memory
from read_match_state import snapshot
from host_runtime.macro_live import MacroSampler

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','desktop-session','bundle','build','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--wait-seconds',type=int,default=180);a=p.parse_args()
    out=a.output.resolve();raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'))
    if not 1<=a.wait_seconds<=300 or out.exists() or not out.is_relative_to(ROOT/'reports'):
        raise ValueError('fresh_bounded_scout_research_required')
    run=Path(session['run_directory']).resolve()
    if (not run.is_relative_to(ROOT/'acceptance/runs') or a.session.resolve().parent!=run
            or session.get('phase')!='macro_native_interface_probe' or (run/'battle-host').exists()):
        raise ValueError('untouched_owned_research_match_required')
    out.mkdir();shutil.copy2(__file__,out/'scout-driver.py')
    proof=dict(kind='fixed_native_scout_legal_feedback_trial',session_id=session['session_id'],pid=session['pid'],
        process_creation_filetime=session['process_creation_filetime'],driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        model_calls=0,unit_orders=0,policy=['scout'],target_policy='original_native_scout_target_selection',
        arbitrary_region_selected=False,product_capability_granted=False,formal_goal_complete=False)
    (out/'driver-preflight.json').write_text(json.dumps(proof,indent=2)+'\n')
    memory=Memory(session['pid'],session);sampler=None;transport=None
    try:
        end=time.monotonic()+a.wait_seconds
        while True:
            if a.session.read_bytes()!=raw:raise ValueError('scout_research_session_changed')
            try:state=snapshot(memory.read)
            except (ValueError,RuntimeError):state=None
            if state and state['simulation_frame']>=150 and not state['pause_flag_candidate']:
                if any(r['defeat_frame'] or r['victory_frame'] for r in state['result_records']):raise ValueError('live_scout_match_required')
                break
            if time.monotonic()>=end:raise ValueError('scout_wait_deadline_before_attach')
            time.sleep(.25)
        sampler=MacroSampler(a.desktop_session,a.bundle);first=sampler.collect()
        if sampler.session['session_id']!=session['session_id']:raise ValueError('scout_visibility_session_mismatch')
        with (out/'visibility-binding.json').open('x') as f:json.dump(sampler.footprint(),f,indent=2)
        spec=importlib.util.spec_from_file_location('scout_research_transport',ROOT/'native-ai/macro-policy-runtime/client.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        transport=module.MacroPolicyProbe(a.session,sampler.owner,a.build,out/'transport')
        samples=0;errors=0
        with (out/'lawful-snapshots.jsonl').open('x',encoding='utf8') as stream:
            def lawful(label):
                nonlocal samples,errors
                try:
                    value=sampler.collect();samples+=1
                    stream.write(json.dumps(dict(label=label,snapshot=value),ensure_ascii=False,allow_nan=False)+'\n')
                except (ValueError,RuntimeError) as error:
                    # Contract errors have fixed local codes; never provider text.
                    errors+=1;stream.write(json.dumps(dict(label=label,read_error=str(error)))+'\n')
                stream.flush()
            lawful('before_scout');transport.observe('before_scout');transport.apply(['scout'],1350)
            end=time.monotonic()+70
            while time.monotonic()<end:
                if a.session.read_bytes()!=raw:raise ValueError('scout_research_session_changed')
                transport.observe('scout_held');lawful('scout_held');time.sleep(.5)
            transport.apply([],1);end=time.monotonic()+10
            while time.monotonic()<end:
                transport.observe('scout_released');lawful('scout_released');time.sleep(.5)
        (out/'driver-result.json').write_text(json.dumps(dict(**proof,lawful_samples=samples,lawful_read_errors=errors,
            legal_information_exclusively_attributed_to_scout=False),indent=2)+'\n')
    finally:
        if transport:transport.close()
        if sampler:sampler.close()
        memory.close()
    print(json.dumps(dict(output=str(out),model_calls=0,product_capability_granted=False)))

if __name__=='__main__':main()
