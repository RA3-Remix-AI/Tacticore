"""Exercise the staged interpreter and real local RPCs without game/model IO."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

from release_preflight import read_json, verify_inventory


# Executed only by the isolated companion interpreter. Import origins and
# children must stay in the companion even under hostile environment/cwd.
IMPORT_PROBE = '''
import importlib, json, pathlib, socket, sys
def denied(*args, **kwargs):
    raise RuntimeError('offline_probe_network_forbidden')
socket.socket.connect = denied
socket.create_connection = denied
root = pathlib.Path(sys.executable).resolve().parent.parent
for name in ('host_runtime.bridge_service', 'host_runtime.desktop_backend',
             'host_runtime.connection_config_server_v1', 'host_runtime.control_only_server_v1',
             'tacticore_agent_runtime.factory', 'pydantic_ai.models.openai',
             'pydantic_ai.providers.openai', 'openai', 'httpx2', 'pydantic'):
    importlib.import_module(name)
from tacticore_agent_runtime.factory import check_backend_available
check_backend_available('pydantic')
for module in tuple(sys.modules.values()):
    file = getattr(module, '__file__', None)
    if file and not str(file).startswith('<') and not pathlib.Path(file).resolve().is_relative_to(root):
        raise RuntimeError('offline_probe_import_outside_companion')
print(json.dumps(dict(imports_confined=True, pydantic_backend_available=True)))
'''


def probe(runtime):
    runtime = Path(runtime).absolute()
    before = verify_inventory(runtime)
    stage_kind = read_json(runtime / 'release-stage.json').get('kind')
    if stage_kind not in ('locked_python_stage', 'portable_native6_offline_candidate', 'portable_native6_field_trial_candidate'):
        raise ValueError('offline_companion_stage_required')
    with tempfile.TemporaryDirectory(prefix='tacticore-python-stage-') as temporary:
        temporary = Path(temporary)
        for name in ('host_runtime', 'pydantic_ai', 'openai'):
            trap = temporary / name
            trap.mkdir()
            (trap / '__init__.py').write_text("raise RuntimeError('untrusted_import')\n", encoding='utf-8')
        environment = {name: os.environ[name] for name in ('SYSTEMROOT', 'WINDIR', 'PATH') if name in os.environ}
        environment.update(PYTHONPATH=str(temporary), PYTHONHOME=str(temporary / 'no-python'),
                           PYDANTIC_AI_NO_BANNER='1', LOCALAPPDATA=str(temporary / 'local-app-data'),
                           APPDATA=str(temporary / 'roaming'), USERPROFILE=str(temporary), HOME=str(temporary),
                           TEMP=str(temporary), TMP=str(temporary))
        common = dict(cwd=temporary, env=environment, text=True, encoding='utf-8', capture_output=True,
                      timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        python = str(runtime / 'python/python.exe')
        imported = subprocess.run([python, '-I', '-S', '-B', '-c', IMPORT_PROBE], **common)
        if imported.returncode or json.loads(imported.stdout) != dict(imports_confined=True, pydantic_backend_available=True):
            raise ValueError('python_stage_import_probe_failed')
        home = temporary / 'local-app-data/Tacticore'
        state = home / 'desktop-runtime'
        library = home / 'library.json'
        registration = home / 'desktop-runtime-config.json'
        commander = str(uuid.uuid4())

        def call(module, arguments, operations):
            requests = [dict(schema_version=1, request_id=str(uuid.uuid4()), operation=op, args={}) for op in operations]
            child = subprocess.run([python, '-I', '-S', '-B', '-m', module, *arguments],
                                   input=''.join(json.dumps(row) + '\n' for row in requests), **common)
            if child.returncode:
                raise ValueError('python_stage_rpc_process_failed')
            replies = [json.loads(row) for row in child.stdout.splitlines()]
            if len(replies) != len(requests) or any(reply.get('request_id') != request['request_id'] or reply.get('ok') is not True
                    for reply, request in zip(replies, requests)):
                raise ValueError('python_stage_rpc_response_failed')
            return replies

        configuration = ['--library', str(library), '--state-dir', str(state), '--registration', str(registration), '--commander-id', commander]
        call('host_runtime.connection_config_server_v1', configuration, ['connections.bootstrap', 'connections.configuration'])
        profiles = call('host_runtime.bridge_service', ['--library', str(library), '--state-dir', str(state)], ['profiles.list'])
        if len(profiles[0]['result']['profiles']) != 1:
            raise ValueError('python_stage_bootstrap_profile_missing')
        # A separate process reopens the same generated state: no user profile
        # or credentials are read and the first-use state must persist.
        call('host_runtime.connection_config_server_v1', configuration, ['connections.configuration'])
    after = verify_inventory(runtime, before['manifest_sha256'])
    if before != after:
        raise ValueError('python_stage_inventory_changed_after_probe')
    return dict(schema_version=1, kind='locked_python_stage_smoke', companion_stage=stage_kind, **after,
                isolated_imports=True, hostile_cwd_and_python_environment_ignored=True,
                user_provider_environment_not_inherited=True,
                pydantic_backend_imported=True, first_use_rpc=True, profile_query_rpc=True, reopen_rpc=True,
                inventory_unchanged=True, game_access=False, model_requests=0, user_credentials_read=False,
                game_qualified=False, public_release_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.runtime)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))
