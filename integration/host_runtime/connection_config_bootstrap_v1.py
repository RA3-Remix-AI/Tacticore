"""Native-owned first-use paths only. No WebView path or credential inputs."""
import hashlib
import json
import os
from pathlib import Path
import uuid
from .contracts import ContractError, canonical_json, identifier
from .profile_store import _decode, ProfileStore
from .connection_config_atomic_v1 import exclusive_bytes


def create_once(path, raw):
    exclusive_bytes(path, raw)


def initialize_connection_library_v1(library_path, registration_path, state_dir, *, commander_id):
    """Caller supplies packaged commander identity and trusted native paths.

    Does not adopt/overwrite an unrelated existing library. A public bootstrap
    marker lets an interrupted first use complete exactly the same template.
    """
    identifier(commander_id)
    library_path, registration_path, state_dir = (Path(p).resolve() for p in (library_path, registration_path, state_dir))
    library_path.parent.mkdir(parents=True, exist_ok=True)
    registration_path.parent.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    marker = state_dir / 'connection-first-use-v1.json'
    if marker.exists():
        intent = _decode(marker.read_bytes())
        if (intent.get('kind') != 'native_connection_first_use_v1' or intent.get('commander_id') != commander_id
                or intent.get('library_path') != str(library_path) or intent.get('registration_path') != str(registration_path)):
            raise ContractError('connection_setup_conflict')
    else:
        if library_path.exists() or registration_path.exists():
            raise ContractError('connection_setup_existing_source')
        connection = str(uuid.uuid4())
        document = dict(schema_version=2, connections=[dict(id=connection, name='默认连接', provider='OpenAI',
            base_url='https://api.openai.com/v1', remember_key=False, default_model='')],
            commanders=[dict(id=commander_id, name='原生 AI 指挥官', connection_id=connection,
                             model='', personality=2, traits='')])
        raw = (canonical_json(document) + '\n').encode('utf8')
        registration = dict(schema_version=1, registration_id=str(uuid.uuid4()), library_path=str(library_path),
                            library_sha256=hashlib.sha256(raw).hexdigest())
        intent = dict(kind='native_connection_first_use_v1', commander_id=commander_id,
                      library_path=str(library_path), registration_path=str(registration_path),
                      document=document, registration=registration)
        create_once(marker, (canonical_json(intent) + '\n').encode('utf8'))
    raw = (canonical_json(intent['document']) + '\n').encode('utf8')
    registered = (canonical_json(intent['registration']) + '\n').encode('utf8')
    for path, expected in ((library_path, raw), (registration_path, registered)):
        if path.exists():
            if path.read_bytes() != expected:
                raise ContractError('connection_setup_conflict')
        else:
            create_once(path, expected)
    store = ProfileStore(library_path, state_dir)
    try:
        profiles = store.list_profiles()['profiles']
        connections = store.list_connections()['connections']
        if len(profiles) != 1 or profiles[0]['profile_id'] != commander_id or len(connections) != 1:
            raise ContractError('connection_setup_conflict')
    finally:
        store.close()
    return dict(schema_version=1, initialized=True, profile_id=commander_id, connection_id=connections[0]['id'],
                config_fingerprint=hashlib.sha256(raw).hexdigest(), credentials_created=False,
                remote_connection_tested=False, host_started=False)
