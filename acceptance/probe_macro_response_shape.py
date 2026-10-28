"""One real-provider shadow probe on a stopped frozen public request; no game."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'integration'),str(ROOT/'strategy')]
from host_runtime.application import apply_commander_draft,create_applied_backend
from host_runtime.desktop_registry import load_registration
from http_adapter import load_profile
from engine import Binding,Snapshot,validate_policy,ContractError
from macro_policy import ACTIONS


def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


async def probe(run,out):
    run=run.resolve();out=out.resolve();host=run/'battle-host'
    if not run.is_relative_to(ROOT/'acceptance/runs') or not out.is_relative_to(ROOT/'reports') or out.exists():
        raise ValueError('fresh_explicit_shadow_probe_required')
    if load(host/'host-status.json')['state'] not in ('stopped','result_candidate') or load(host/'macro-release.json')['native_release_verified'] is not True:
        raise ValueError('stop_and_release_before_shadow_probe')
    rows=[json.loads(x) for x in (host/'host-events.jsonl').read_text(encoding='utf8').splitlines()]
    request=next(r for r in rows if r['kind']=='model_macro_request_context');context=request['context']
    if hashlib.sha256(json.dumps(context,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()!=request['context_sha256']:
        raise ValueError('frozen_context_changed')
    snapshot=next(json.loads(x) for x in (host/'macro-snapshots.jsonl').read_text(encoding='utf8').splitlines() if json.loads(x)['snapshot_id']==context['snapshot_id'])
    observed=Snapshot.from_dict(snapshot);profile=load(host/'profile.json');out.mkdir()
    def emit(kind,payload):
        with (out/'provider-events.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(kind=kind,**payload),ensure_ascii=False)+'\n')
    # Normal protected startup only; never log/inspect the protected object.
    registration=load_registration(Path(os.environ['LOCALAPPDATA'])/'Tacticore')
    protected=load_profile(Path(registration['library_path']),context['commander_id'])
    application=apply_commander_draft(protected,profile['draft'])
    backend=create_applied_backend(application,event_sink=emit,backend='pydantic',timeout=28,max_tokens=1536,max_input_bytes=16384,max_inflight=1)
    answer=await backend(context)
    actions=answer.get('macro_actions');shape=dict(macro_actions_type=type(actions).__name__,
        macro_actions_present='macro_actions' in answer,macro_actions_count=len(actions) if isinstance(actions,(list,dict,str)) else None,
        known_action_items=[x for x in actions if isinstance(x,str) and x in ACTIONS] if isinstance(actions,(list,dict)) else [],
        item_types=[type(x).__name__ for x in actions] if isinstance(actions,list) else [],
        unknown_string_item_hashes=[hashlib.sha256(x.encode()).hexdigest() for x in actions if isinstance(x,str) and x not in ACTIONS] if isinstance(actions,list) else [])
    binding=Binding(context['session_id'],context['player_id'],context['commander_id'],profile['draft']['name'],profile['draft']['connection_id'])
    try:
        plan=validate_policy(answer,observed,observed,binding,30);valid=True;reason='valid_policy'
    except ContractError as e:valid=False;reason=str(e)
    value=dict(kind='single_frozen_public_macro_response_shape_probe',source_run=str(run),snapshot_id=context['snapshot_id'],
        context_sha256=request['context_sha256'],http_adapter_sha256=sha(ROOT/'strategy/http_adapter.py'),
        wire_estimate=backend.input_size(context),provider_calls=1,live_game_access=False,native_dispatches=0,
        shape=shape,valid_policy=valid,reason_code=reason,transport_receipt=backend.observation().get('transport_receipt'),
        formal_goal_complete=False)
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print(json.dumps(value))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();asyncio.run(probe(a.source_run,a.output))
