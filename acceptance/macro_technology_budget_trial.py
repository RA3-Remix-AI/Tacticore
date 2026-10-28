"""Bounded native technology-budget study in an owned research fixture.

Fixed research policy, zero provider calls; not model technology attribution.
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
sys.path[:0]=[str(ROOT),str(ROOT/'production'),str(ROOT/'native-ai'),str(ROOT/'visibility')]
from observe_production import Memory
from read_match_state import snapshot
from read_selected_personality import inspect_player


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('session','build','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--wait-seconds',type=int,default=0)
    a=p.parse_args();out=a.output.resolve();raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'))
    if not 0<=a.wait_seconds<=180:raise ValueError('bounded_technology_wait_required')
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_technology_budget_trial_required')
    run=Path(session['run_directory']).resolve();prior_responses=None
    if not run.is_relative_to(ROOT/'acceptance/runs') or a.session.resolve().parent!=run:
        raise ValueError('owned_research_fixture_required')
    if (run/'battle-host').exists():
        status=json.loads((run/'battle-host/host-status.json').read_text())
        release=json.loads((run/'battle-host/macro-release.json').read_text())
        if (status['state']!='stopped' or release.get('native_release_verified') is not True
                or status['session_id']!=session['session_id']):raise ValueError('known_model_host_release_required')
        prior_responses=status['profile_consumption']['responses_returned']
    elif session.get('phase')!='macro_native_interface_probe':raise ValueError('explicit_research_fixture_required')
    out.mkdir(parents=True);shutil.copy2(__file__,out/'technology-driver.py')
    pre=dict(kind='fixed_native_technology_budget_trial',session_id=session['session_id'],pid=session['pid'],
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),policy=['budgettech'],
        model_calls=0,whole_session_model_calls_before_trial=prior_responses,
        desired_native_account_shares=dict(investment=.15,special_operations=0,production=.25,defense=.1,technology=.4,slush_fund=.1),
        payment_verified=False,technology_upgrade_verified=False,product_capability_granted=False,formal_goal_complete=False)
    (out/'driver-preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
    memory=Memory(session['pid'],session);transport=None
    try:
        until=time.monotonic()+a.wait_seconds
        while True:
            if a.session.read_bytes()!=raw:raise ValueError('technology_budget_session_changed')
            try:state=snapshot(memory.read)
            except (ValueError,RuntimeError):state=None
            if state and state['simulation_frame']>=1800 and not state['pause_flag_candidate']:
                if any(r['defeat_frame'] or r['victory_frame'] for r in state['result_records']):
                    raise ValueError('live_nonterminal_research_match_required')
                break
            if time.monotonic()>=until:raise ValueError('live_nonterminal_research_match_required')
            time.sleep(.25)
        owners=[int(r['player'],0) for r in state['victory_conditions']['participants'] if r['player_index']==3]
        if len(owners)!=1 or int(inspect_player(memory.read,owners[0])['instance_id'],0)!=0x799613e0:
            raise ValueError('unique_bound_macro_ai_required')
        spec=importlib.util.spec_from_file_location('fixed_technology_native_transport',ROOT/'native-ai/macro-policy-runtime/client.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        transport=module.MacroPolicyProbe(a.session,owners[0],a.build,out/'transport')
        transport.event('fixed_technology_budget_policy',model_calls=0,prior_model_host_stopped=prior_responses is not None)
        transport.observe('before_technology_budget');transport.apply(['budgettech'],900)
        until=time.monotonic()+35
        while time.monotonic()<until:
            if a.session.read_bytes()!=raw:raise ValueError('technology_budget_session_changed')
            transport.observe('technology_budget_held');time.sleep(.25)
        transport.apply([],1)
        until=time.monotonic()+5
        while time.monotonic()<until:
            transport.observe('after_technology_budget_release');time.sleep(.25)
    finally:
        if transport:transport.close()
        memory.close()
    print(json.dumps(dict(output=str(out),model_calls=0,payment_verified=False,
        technology_upgrade_verified=False,product_capability_granted=False)))


if __name__=='__main__':main()
