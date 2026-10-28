"""Paired real-provider style study on one frozen lawful observation.

Explicit shadow research: no live game reads, executor, native call or dispatch.
Uses the normal protected loader only at actual provider startup. Never exports
the protected Profile, connection library, credentials or exception text.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration'),str(ROOT/'strategy')]
from host_runtime.application import apply_commander_draft,create_applied_backend
from host_runtime.desktop_registry import load_registration
from http_adapter import load_profile
from engine import Binding,Snapshot,validate_policy,ContractError

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def frozen_case(run,original_profile=None,variant_name='scouting'):
    status=load(run/'battle-host/host-status.json')
    if status['state'] not in ('stopped','result_candidate','completed') or load(run/'battle-host/macro-release.json').get('native_release_verified') is not True:
        raise ValueError('stop_live_host_before_shadow_study')
    events=[json.loads(l) for l in (run/'battle-host/host-events.jsonl').read_text().splitlines()]
    first=next(r for r in events if r['kind']=='model_macro_request_context')
    context=first['context']
    encoded=json.dumps(context,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if hashlib.sha256(encoded).hexdigest()!=first['context_sha256']:raise ValueError('frozen_public_context_changed')
    snapshot=next(json.loads(l) for l in (run/'battle-host/macro-snapshots.jsonl').read_text().splitlines()
        if json.loads(l)['snapshot_id']==context['snapshot_id'])
    observed=Snapshot.from_dict(snapshot)
    if list(observed.macro_control or ())!=context['allowed_macro_actions'] or context.get('control_mode')!='macro_native':
        raise ValueError('frozen_macro_observation_binding')
    profile=load(run/'battle-host/profile.json')
    if original_profile is not None:
        original_profile=Path(original_profile).resolve(strict=True)
        if (not original_profile.is_relative_to(ROOT/'reports')
                and not original_profile.is_relative_to(ROOT/'acceptance/runs')):
            raise ValueError('local_public_profile_snapshot_required')
        original=load(original_profile)
        if (profile['revision']<=original['revision'] or original['profile_id']!=profile['profile_id']
                or original['connection_id']!=profile['connection_id']
                or profile['draft']['custom_traits']==original['draft']['custom_traits']
                or profile['effective']['effective_hash']!=status['profile_application']['effective_hash']
                or re.fullmatch(r'[a-z][a-z0-9_]{0,31}',variant_name) is None or variant_name=='original'):
            raise ValueError('captured_style_pair_required')
        return context,observed,dict(original=original['draft'],**{variant_name:profile['draft']})
    if profile['revision']!=8 or '把侦察和情报更新作为开局' not in profile['custom_traits']:
        raise ValueError('captured_scout_style_required')
    original=load(run/'style-original-profile.json')
    if original['revision']!=7 or original['profile_id']!=profile['profile_id'] or original['connection_id']!=profile['connection_id']:
        raise ValueError('captured_original_style_required')
    return context,observed,dict(original=original['draft'],scouting=profile['draft'])

async def compare(a):
    run=a.source_run.resolve();out=a.output.resolve()
    if (not run.is_relative_to(ROOT/'acceptance/runs') or out.exists() or not out.is_relative_to(ROOT/'reports')
            or not 1<=a.pairs<=3):raise ValueError('fresh_bounded_shadow_study_required')
    context,observed,drafts=frozen_case(run,a.original_profile,a.variant_name)
    out.mkdir();source=out/'source';source.mkdir();pins=[]
    paths=[Path(__file__),ROOT/'strategy/http_adapter.py',ROOT/'strategy/engine.py',ROOT/'strategy/model_backend.py',
        ROOT/'integration/host_runtime/application.py',ROOT/'integration/host_runtime/profiles.py',
        *sorted((ROOT/'agent_runtime/src/tacticore_agent_runtime').glob('*.py'))]
    for i,p in enumerate(paths):
        target=source/(str(i)+'-'+p.name);shutil.copy2(p,target);pins.append(dict(path=str(p),copy=target.name,sha256=sha(target)))
    (out/'public-context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (out/'public-drafts.json').write_text(json.dumps(drafts,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    manifest=dict(kind='paired_frozen_observation_macro_style_study',source_run=str(run),sources=pins,
        context_sha256=sha(out/'public-context.json'),drafts_sha256=sha(out/'public-drafts.json'),pairs=a.pairs,
        actual_provider_calls_requested=2*a.pairs,native_dispatches=0,live_game_access=False,game_process_writes=0,
        same_observation_for_all_styles=True,styles=list(drafts),
        model_nondeterminism_controlled=False,formal_goal_complete=False)
    (out/'preflight.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Actual provider startup only. Keep the protected object in memory; never
    # inspect, serialize, print or copy its credential/endpoint fields.
    registration=load_registration(Path(os.environ['LOCALAPPDATA'])/'Tacticore')
    protected=load_profile(Path(registration['library_path']),context['commander_id'])
    outcomes=[];calls=0
    with (out/'provider-events.jsonl').open('x',encoding='utf8') as stream:
        def event(style,pair):
            def emit(kind,payload):
                stream.write(json.dumps(dict(kind=kind,style=style,pair=pair+1,**payload),ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
            return emit
        for pair in range(a.pairs):
            for style in drafts:
                application=apply_commander_draft(protected,drafts[style]);backend=create_applied_backend(application,
                    event_sink=event(style,pair),backend='pydantic',timeout=28,max_tokens=1536,max_input_bytes=16384,max_inflight=1)
                request=copy.deepcopy(context);wire_bytes=backend.input_size(request)
                result=dict(pair=pair+1,style=style,effective_hash=application.effective.effective_hash,
                    traits_sha256=hashlib.sha256(application.effective.traits.encode()).hexdigest(),wire_bytes=wire_bytes,
                    same_context_sha256=manifest['context_sha256'],native_dispatches=0)
                try:
                    if wire_bytes>16384:raise ValueError('shadow_wire_budget_exceeded')
                    calls+=1;answer=await backend(request);public=backend.observation()
                    receipt=public.get('transport_receipt') or {}
                    genuine=all(receipt.get(k)==v for k,v in dict(real_network_verified=True,injected_transport=False,
                        expected_origin=True,https=True,loopback=False,http_status=200,response_complete=True).items())
                    binding=Binding(context['session_id'],3,context['commander_id'],drafts[style]['name'],drafts[style]['connection_id'])
                    plan=validate_policy(answer,observed,observed,binding,30)
                    result.update(valid_policy=True,real_network_verified=genuine,macro_actions=list(plan.macro_actions),
                        macro_production=plan.macro_production.public() if plan.macro_production else None,
                        stance=plan.stance,objective_region=plan.objective_region,
                        economy_policy=plan.economy_policy,tech_policy=plan.tech_policy,transport_receipt=receipt)
                except ContractError as error:
                    code=str(error);result.update(valid_policy=False,reason_code=code if re.fullmatch(r'[a-z][a-z0-9_]{0,79}',code) else 'shadow_policy_rejected')
                except Exception:
                    result.update(valid_policy=False,reason_code='shadow_call_or_input_failed')
                outcomes.append(result)
                with (out/'outcomes.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
    result=dict(**manifest,provider_calls_attempted=calls,outcomes=outcomes,
        decision_difference_pairs=sum(a.get('macro_actions')!=b.get('macro_actions') or a.get('macro_production')!=b.get('macro_production')
            for a,b in zip(outcomes[::2],outcomes[1::2]) if a.get('valid_policy') and b.get('valid_policy')),
        causal_style_effect_verified=False,live_behavior_difference_verified=False,win_rate_effect_verified=False)
    (out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    return dict(output=str(out),provider_calls_attempted=calls,valid_policies=sum(r.get('valid_policy',False) for r in outcomes),
        native_dispatches=0,live_game_access=False,decision_difference_pairs=result['decision_difference_pairs'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--pairs',type=int,default=3)
    p.add_argument('--original-profile',type=Path,help='Original public ProfileStore snapshot; variant is the captured run profile')
    p.add_argument('--variant-name',default='scouting');a=p.parse_args()
    try:print(json.dumps(asyncio.run(compare(a))))
    except Exception:print(json.dumps(dict(state='failed',reason_code='shadow_study_not_completed',native_dispatches=0)));raise SystemExit(1)

if __name__=='__main__':main()
