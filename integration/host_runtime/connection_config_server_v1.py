"""Separate bounded configuration pipe; it cannot dispatch game/model actions.

Only the native launcher supplies paths and the packaged commander identity.
Its separate channel permits recovery when the normal library digest changed.
"""
import argparse
from pathlib import Path
import sys
from .bridge_service import decode_request
from .connection_config_bootstrap_v1 import initialize_connection_library_v1
from .connection_config_rpc_v1 import ConnectionAwareBridgeV1
from .connection_config_schema_v1 import MAX_REQUEST_BYTES, OPERATIONS
from .contracts import ContractError, canonical_json, identifier, object_fields
from .profile_store import ProfileStore


class NativeConfigurationServerV1:
    def __init__(self, library, state_dir, registration, commander_id, *, backend_factory=None):
        identifier(commander_id)
        self.library, self.state, self.registration = (Path(p).resolve() for p in (library, state_dir, registration))
        self.commander = commander_id
        self.store = self.backend = self.bridge = None
        self.backend_factory = backend_factory

    def close(self):
        if self.bridge is not None:
            self.bridge.close()
        if self.backend is not None:
            self.backend.close()
        if self.store is not None:
            self.store.close()

    def _load(self):
        if self.bridge is None:
            if not self.library.is_file() or not self.registration.is_file():
                raise ContractError('connection_setup_required')
            self.store = ProfileStore(self.library, self.state)
            if self.backend_factory is None:
                from .desktop_backend import DesktopBackend
                self.backend = DesktopBackend(self.store)
            else:
                self.backend = self.backend_factory(self.store)
            self.bridge = ConnectionAwareBridgeV1(self.store, self.backend, registration_path=self.registration)

    def handle(self, request):
        request_id = None
        try:
            value = object_fields(request, {'schema_version', 'request_id', 'operation', 'args'})
            request_id = identifier(value['request_id'])
            if type(value['schema_version']) is not int or value['schema_version'] != 1:
                raise ContractError('connection_config_schema_invalid')
            if len(canonical_json(value).encode('utf8')) > MAX_REQUEST_BYTES:
                raise ContractError('request_too_large')
            operation = value['operation']
            if operation == 'connections.bootstrap':
                object_fields(value['args'], set())
                # Do not initialize over any existing launch ledger. Existing
                # registered users query/recover their source instead.
                if not self.library.exists() and any((self.state / name).exists() for name in
                        ('host-runtime.sqlite3', 'desktop-launch-index.sqlite3')):
                    raise ContractError('connection_setup_existing_source')
                result = initialize_connection_library_v1(self.library, self.registration, self.state,
                                                           commander_id=self.commander)
                return dict(schema_version=1, request_id=request_id, ok=True, result=result)
            if type(operation) is not str or operation not in OPERATIONS:
                raise ContractError('operation_unsupported')
            self._load()
            return self.bridge.handle(value)
        except ContractError as error:
            allowed = {'connection_setup_required', 'connection_setup_existing_source', 'connection_setup_conflict',
                       'operation_unsupported', 'unexpected_fields', 'invalid_uuid', 'request_too_large', 'connection_config_schema_invalid'}
            return dict(schema_version=1, request_id=request_id, ok=False,
                        error=dict(code=error.code if error.code in allowed else 'connection_config_unavailable'))
        except Exception:
            return dict(schema_version=1, request_id=request_id, ok=False, error=dict(code='connection_config_unavailable'))


def serve(service, source, target):
    while True:
        raw = source.readline(MAX_REQUEST_BYTES + 1)
        if not raw:
            return
        try:
            if len(raw) > MAX_REQUEST_BYTES:
                while raw and not raw.endswith(b'\n'):
                    raw = source.readline(MAX_REQUEST_BYTES + 1)
                raise ContractError('request_too_large')
            response = service.handle(decode_request(raw))
        except ContractError:
            response = dict(schema_version=1, request_id=None, ok=False, error=dict(code='request_invalid'))
        encoded = (canonical_json(response) + '\n').encode('utf8')
        if len(encoded) > MAX_REQUEST_BYTES:
            encoded = (canonical_json(dict(schema_version=1, request_id=response.get('request_id'), ok=False,
                       error=dict(code='connection_config_response_too_large'))) + '\n').encode('utf8')
        target.write(encoded)
        target.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('library', 'state-dir', 'registration'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--commander-id', required=True)
    args = parser.parse_args(argv)
    server = NativeConfigurationServerV1(args.library, args.state_dir, args.registration, args.commander_id)
    try:
        serve(server, sys.stdin.buffer, sys.stdout.buffer)
    finally:
        server.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
