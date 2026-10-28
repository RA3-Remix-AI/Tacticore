"""Read-only RPC smoke test of an isolated companion, without game/model IO."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import subprocess, sys, tempfile, uuid

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'integration'))
from host_runtime.desktop_registry import load_registration


def probe(release):
    release=Path(release).resolve(strict=True); runtime=release/'runtime'
    manifest=json.loads((runtime/'manifest.json').read_text(encoding='utf-8'))
    registration=load_registration(Path(os.environ['LOCALAPPDATA'])/'Tacticore')
    request=dict(schema_version=1,request_id=str(uuid.uuid4()),operation='profiles.list',args={})
    with tempfile.TemporaryDirectory(prefix='tacticore-clean-launch-') as temp:
        trap=Path(temp)/'host_runtime'; trap.mkdir()
        (trap/'__init__.py').write_text("raise RuntimeError('untrusted cwd imported')\n",encoding='utf-8')
        environment=dict(os.environ,PYTHONPATH=temp,PYTHONHOME=str(Path(temp)/'missing-python'))
        child=subprocess.run([str(runtime/'python/python.exe'),'-I','-S','-B','-m','host_runtime.bridge_service','--library',registration['library_path'],'--state-dir',str(Path(temp)/'state')],cwd=temp,env=environment,input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        response=json.loads(child.stdout)
        if child.returncode!=0 or response.get('request_id')!=request['request_id'] or response.get('ok') is not True:
            raise ValueError('companion_rpc_failed')
        profiles=response['result']['profiles']
    observed={p.relative_to(runtime).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.rglob('*') if p.is_file() and p.name!='manifest.json'}
    if observed!=manifest['files']:raise ValueError('runtime_inventory_changed_after_import')
    return dict(schema_version=1,kind='clean_path_companion_rpc_smoke',manifest_sha256=hashlib.sha256((runtime/'manifest.json').read_bytes()).hexdigest(),outside_repository_cwd=True,hostile_pythonhome_ignored=True,hostile_pythonpath_and_cwd_ignored=True,rpc_profiles_list_verified=True,profile_count=len(profiles),inventory_unchanged_after_import=True,credential_material_copied=False,game_access=False,model_requests=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--release',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('output_must_be_new')
    result=probe(args.release)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
