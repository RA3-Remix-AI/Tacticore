"""One explicit registered-provider call on one archived public macro context.

No game access, executor, model retry, or raw response export. Run only by the
operator with --real-model; imports and --help never load protected profiles.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'strategy'),str(ROOT/'agent_runtime/src')]
from host_runtime.application import apply_commander_draft,create_applied_backend,safe_backend_diagnostics
from host_runtime.desktop_registry import load_registration
from host_runtime.profile_store import ProfileStore
from http_adapter import load_profile
from macro_strategy import DECLARATION_FIELDS


def archived_context(path: Path, sequence: int) -> tuple[dict,str]:
    matches=[]
    with path.open('rb') as stream:
        while True:
            line=stream.readline(131073)
            if not line: break
            if len(line)>131072: raise ValueError('archive_line_bounds')
            row=json.loads(line)
            if row.get('kind')=='model_macro_request_context' and row.get('sequence')==sequence:
                context=row.get('context')
                if type(context) is not dict or context.get('control_mode')!='macro_native':
                    raise ValueError('archive_context_invalid')
                raw=json.dumps(context,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')
                digest=hashlib.sha256(raw).hexdigest()
                if len(raw)!=row.get('context_bytes') or digest!=row.get('context_sha256'):
                    raise ValueError('archive_context_hash_mismatch')
                matches.append((context,digest))
    if len(matches)!=1: raise ValueError('archive_sequence_not_unique')
    return matches[0]


def response_shape(value) -> dict:
    strategy=value.get('macro_strategy') if type(value) is dict else None
    return {'json_object':type(value) is dict,'macro_strategy_object':type(strategy) is dict,
        'macro_strategy_fields_match':type(strategy) is dict and set(strategy)==set(DECLARATION_FIELDS),
        'macro_actions_list':type(value) is dict and type(value.get('macro_actions')) is list}


async def probe(args):
    if not args.real_model: raise ValueError('explicit_real_model_required')
    if args.output.exists(): raise ValueError('probe_output_must_be_new')
    context,digest=archived_context(args.events,args.sequence)
    # Follow the same explicit registration/ProfileStore/load_profile path as
    # normal desktop startup. Never read or export the library's raw content.
    home=Path(os.environ['LOCALAPPDATA'])/'Tacticore'
    registration=load_registration(home)
    library=Path(registration['library_path'])
    store=ProfileStore(library,home/'desktop-runtime')
    try: record=store.get_profile(context['commander_id'])['profile']
    finally: store.close()
    base=load_profile(library,context['commander_id'])
    applied=apply_commander_draft(base,record['draft'])
    archived=json.loads(args.events.with_name('profile.json').read_text(encoding='utf8'))
    if (applied.effective.effective_hash!=record['effective']['effective_hash']
        or applied.effective.effective_hash!=archived['effective']['effective_hash']):
        raise ValueError('effective_profile_changed')
    backend=create_applied_backend(applied,backend='pydantic',timeout=28,max_tokens=1536,
        max_input_bytes=16384,max_inflight=1,http_retries=0)
    report={'schema_version':1,'kind':'archived_macro_backend_diagnostic',
        'sequence':args.sequence,'context_sha256':digest,'effective_hash':applied.effective.effective_hash,
        'game_access':False,'executor_created':False,'native_commands':0,'calls_invoked':0,
        'raw_request_persisted':False,'raw_response_persisted':False,'credentials_persisted':False,
        'response_returned':False,'response_shape':None,'real_network_response_verified':False}
    started=time.monotonic()
    try:
        report['input_estimate_bytes']=backend.input_size(context)
        report['calls_invoked']=1
        result=await backend(context)
        report['response_returned']=True
        report['response_shape']=response_shape(result)
        report['real_network_response_verified']=backend.observation().get('real_network_verified') is True
    except Exception:
        # No str(exception), provider text, arbitrary type names, or payload.
        report['failed']=True
    report['backend_diagnostics']=safe_backend_diagnostics(backend)
    receipt=getattr(backend,'last_transport_receipt',None)
    report['complete_200_receipt']=type(receipt) is dict and receipt.get('http_status')==200 and receipt.get('response_complete') is True
    report['elapsed_seconds']=round(time.monotonic()-started,3)
    with args.output.open('x',encoding='utf8') as stream:
        json.dump(report,stream,ensure_ascii=False,allow_nan=False,indent=2);stream.write('\n')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events',type=Path,required=True)
    parser.add_argument('--sequence',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--real-model',action='store_true')
    args=parser.parse_args(argv)
    try:
        report=asyncio.run(probe(args))
        print(json.dumps(report,ensure_ascii=True))
        return 0 if report['response_returned'] else 2
    except Exception:
        print(json.dumps({'probe_started':False,'error_code':'probe_setup_failed'}))
        return 2


if __name__=='__main__': raise SystemExit(main())
