"""Strict local configuration DTO; WebView cannot choose files or secret refs."""
from .contracts import ContractError, canonical_json, identifier, integer, object_fields, sha256, text
from .profile_store import _endpoint

MAX_REQUEST_BYTES = 16384
OPERATIONS = frozenset({'connections.configuration', 'connections.configure', 'connections.recover', 'connections.cleanup_retired'})


def configure_args(value):
    value = object_fields(value, {'schema_version', 'connection_id', 'expected_config_fingerprint',
                                 'name', 'provider', 'endpoint', 'model', 'credential_operation'}, {'api_key'})
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ContractError('connection_config_schema_invalid')
    identifier(value['connection_id'])
    sha256(value['expected_config_fingerprint'])
    text(value['name'], 60)
    text(value['model'], 200, empty=True)
    if value['provider'] not in ('OpenAI', 'DeepSeek', '自定义'):
        raise ContractError('invalid_connection')
    _endpoint(value['endpoint'])
    operation = value['credential_operation']
    if operation not in ('keep', 'set', 'clear'):
        raise ContractError('connection_credential_operation_invalid')
    if operation == 'set':
        key = value.get('api_key')
        if type(key) is not str or not 1 <= len(key) <= 4096 or any(not 33 <= ord(c) <= 126 for c in key):
            raise ContractError('connection_credential_invalid')
    elif 'api_key' in value:
        raise ContractError('connection_credential_operation_invalid')
    if len(canonical_json(value).encode('utf8')) > MAX_REQUEST_BYTES:
        raise ContractError('request_too_large')
    return dict(value)
