"""Isolated bounded-trial software smoke. No Game attach or real provider."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'integration'))
from host_runtime.native6_runtime_contract import sha,verify_inventory

PROBE=r'''
import asyncio, importlib, json, os, pathlib, socket, sys
from unittest.mock import patch
original_connect=socket.socket.connect
def connect(self,address):
    # Windows asyncio creates its own loopback socketpair for wakeups.
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):return original_connect(self,address)
    raise AssertionError('offline_network_forbidden')
socket.socket.connect=connect
root=pathlib.Path(sys.executable).resolve().parent.parent
from host_runtime import native6_qualification as q
from host_runtime.contracts import ContractError
pin=os.environ.pop('TACTICORE_RUNTIME_MANIFEST_SHA256')
for supplied in (None,'0'*64):
    if supplied is not None:os.environ['TACTICORE_RUNTIME_MANIFEST_SHA256']=supplied
    try:q.current()
    except (ContractError,ValueError):pass
    else:raise AssertionError('untrusted_manifest_accepted')
os.environ['TACTICORE_RUNTIME_MANIFEST_SHA256']=pin
_,_,inventory,build,cap=q.current()
assert cap['formal_games']==0 and not cap['product_acceptance_verified']
trial=pathlib.Path(sys.argv[1])/'trial.json';q.create(trial)
session=dict(mod_sha256=q.PACKAGE_SHA,registry=str(root/'qualification/registry.json'),scenario=dict(
    commander_id=q.COMMANDER,map_id='TemplePrime',computer_player_index=3,opponent_player_index=4,participant_count=2,observer_player_index=2))
from host_runtime.macro_bundle import load_bundle
bundle,scope=load_bundle(trial,session)
assert type(scope) is q.Native6Scope and len(scope.available_actions)==14 and not scope.production_counts
from macro_host import native_transport_config
config=native_transport_config(scope,build)
assert config['protocol_version']==6 and config['heartbeat_loss_ms']==5000
assert pathlib.Path(config['client_path'])==root/'app/integration/host_runtime/native6_transport.py'
from host_runtime.native6_transport import native_module
builder,sdk=native_module();sdk.verify_layout(build)
# No valid Game fixture is supplied: these constructors must fail on authority
# before even a Known Folder lookup, Memory handle, mapping or Native helper.
path=pathlib.Path(sys.argv[1])/'session.json';path.write_text(json.dumps(session),encoding='utf-8')
os.environ.pop('TACTICORE_RUNTIME_MANIFEST_SHA256')
from host_runtime.native6_paths import Native6Paths
with patch.object(Native6Paths,'current',side_effect=AssertionError('paths_before_authority')):
    try:sdk.Probe(path,root/'native/strategic6',pathlib.Path(sys.argv[1])/'output')
    except ContractError:pass
    else:raise AssertionError('constructor_without_authority')
os.environ['TACTICORE_RUNTIME_MANIFEST_SHA256']=pin
from http_adapter import Profile,Endpoint,system_prompt
from macro_policy import public_descriptions
from tacticore_agent_runtime import PolicyRequest,RuntimeAdapterError,pydantic_backend
from tacticore_agent_runtime.factory import NetworkBackend
import httpx2
async def providers():
    total=0
    for provider in ('OpenAI','DeepSeek'):
        calls=[]
        value=dict(commander_id=q.COMMANDER,session_id='00000000-0000-4000-8000-000000000003',player_id=3,
            snapshot_id=2,game_time_seconds=126.,control_mode='macro_native',allowed_production_focus=['native_baseline'],
            allowed_macro_actions=list(scope.available_actions),macro_policy_catalog=public_descriptions(scope.available_actions,region_targets=scope.regional_action_regions.items()),
            native_delegation={'kind':'native_ai_details_v1'},macro_strategy={'fact_catalog':{'own.credits':3000,'capabilities.actions':list(scope.available_actions)}})
        selected=Profile(q.COMMANDER,'Offline Native6 trial','00000000-0000-4000-8000-000000000002',provider,
            'fixture-model',0,'',Endpoint.parse('https://fixture.invalid/v1'),'FAKE-LOCAL-TEST')
        async def handler(request):
            calls.append(request.content);assert len(request.content)<=16384
            body=json.loads(request.content);assert 'tools' not in body
            assert body['response_format']=={'type':'json_object'}
            assert body['max_completion_tokens' if provider=='OpenAI' else 'max_tokens']==1536
            if provider=='DeepSeek':assert body['thinking']=={'type':'disabled'}
            prompt=body['messages'][0]['content']
            assert prompt==system_prompt(selected,value)
            answer=json.loads(prompt.split('\nExample: ',1)[1].split('\nStyle: ',1)[0])
            return httpx2.Response(200,json={'id':'synthetic','object':'chat.completion','created':1,'model':'fixture',
                'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(answer)}}]})
        backend=NetworkBackend(selected,timeout=4,max_tokens=1536,max_input_bytes=16384,max_inflight=1,
            module=pydantic_backend,transport=httpx2.MockTransport(handler))
        value['synthetic_padding']='';value['synthetic_padding']='x'*(16379-backend.input_size(value))
        assert backend.input_size(value)==16379
        assert backend.input_size(json.loads(json.dumps(value,sort_keys=True)))==16379
        answer=await backend.run(PolicyRequest(value));assert answer['macro_actions']==[]
        assert len(calls)==1 and backend.metrics['attempts']==1
        value['synthetic_padding']+='xxxxxx'
        try:await backend.run(PolicyRequest(value))
        except RuntimeAdapterError as error:assert str(error)=='input_budget_exceeded'
        else:raise AssertionError('oversized_input_accepted')
        assert len(calls)==1;total+=1
    return total
count=asyncio.run(providers())
for module in tuple(sys.modules.values()):
    origin=getattr(module,'__file__',None)
    if origin and not str(origin).startswith('<'):assert pathlib.Path(origin).resolve().is_relative_to(root),origin
print(json.dumps(dict(qualification=True,scope_actions=14,host_config=True,constructor_denied_before_native_io=True,
    sdk_layout=True,imports_confined=True,mock_provider_requests=count,budget_limit=16384,capacity_order_invariant=True)))
'''


def probe(runtime,destination=None):
    runtime=Path(runtime).absolute()
    if destination is not None:
        import importlib.util
        spec=importlib.util.spec_from_file_location('native6_offline_relocation',Path(__file__).with_name('probe-native6-runtime.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        runtime=module.relocate(runtime,destination)
    pin=sha(runtime/'manifest.json');verify_inventory(runtime,expected=pin)
    with tempfile.TemporaryDirectory(prefix='native6-trial-software-') as folder:
        temporary=Path(folder)
        for name in ('host_runtime','build','pydantic_ai','macro_host'):
            (temporary/(name+'.py')).write_text("raise AssertionError('hostile_cwd_import')\n",encoding='utf-8')
        environment={name:os.environ[name] for name in ('SYSTEMROOT','WINDIR','PATH') if name in os.environ}
        environment.update(PYTHONHOME=str(temporary/'missing'),PYTHONPATH=folder,TACTICORE_RUNTIME_MANIFEST_SHA256=pin,
            TEMP=folder,TMP=folder,LOCALAPPDATA=str(temporary/'local'),APPDATA=str(temporary/'roaming'),USERPROFILE=folder,HOME=folder)
        result=subprocess.run([str(runtime/'python/python.exe'),'-I','-S','-B','-c',PROBE,folder],cwd=temporary,env=environment,
            capture_output=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise ValueError('native6_software_smoke_failed:'+result.stderr.decode('utf-8',errors='replace')[-2600:])
        report=json.loads(result.stdout)
    verify_inventory(runtime,expected=pin)
    return dict(kind='native6_field_trial_software_smoke',runtime=str(runtime),runtime_manifest_sha256=pin,**report,
        inventory_unchanged=True,game_access=False,real_model_requests=0,formal_games=0,product_acceptance_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--relocate',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=probe(args.runtime,args.relocate)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
