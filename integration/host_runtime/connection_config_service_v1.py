"""Trusted-path local connection editor, independent of the active bridge.

Every edit rotates the physical connection UUID. The encrypted key is ready at
that new UUID before one atomic library replacement, so an interrupted edit
cannot pair a new endpoint with the old endpoint's key. No game/model access.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import uuid

from .connection_config_credentials_v1 import WindowsConnectionCredentialsV1
from .connection_config_atomic_v1 import exclusive_bytes
from .connection_config_schema_v1 import MAX_REQUEST_BYTES, OPERATIONS, configure_args
from .contracts import ContractError, canonical_json, identifier, object_fields
from .profile_store import _decode


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_bytes(path, raw):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + str(uuid.uuid4()) + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class ConnectionConfigServiceV1:
    """Paths/store/stop guard are native-owned constructor arguments only.

    Fusion MUST use admission_barrier for run.check and run.start as well as
    configure. This serializes native bridge writers and checks the durable
    fingerprint after crashes. It is not a game or preference lease.
    """
    def __init__(self, profile_store, *, stopped_guard, registration_path=None, credentials=None):
        if not callable(stopped_guard):
            raise ContractError('connection_config_guard_required')
        self.store = profile_store
        self.library = Path(profile_store.library_path).resolve()
        self.state = Path(profile_store.state_dir).resolve()
        self.registration = Path(registration_path).resolve() if registration_path is not None else None
        self.stopped_guard = stopped_guard
        self.credentials = credentials if credentials is not None else WindowsConnectionCredentialsV1()
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.state / 'connection-config-v1.sqlite3'), timeout=10,
                                   check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA journal_mode=WAL')
        self._db.execute('PRAGMA synchronous=FULL')
        self._db.executescript('''
          CREATE TABLE IF NOT EXISTS connection_config_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), library_sha256 TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS connection_config_receipts (request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, receipt_json TEXT NOT NULL);
        ''')
        _, _, initial = self.store._library()
        self._db.execute('INSERT OR IGNORE INTO connection_config_meta VALUES (1,?)', (initial,))
        try:
            self._receipt_key = self._load_receipt_key()
        except BaseException:
            self._db.close()
            raise

    def close(self):
        self._db.close()

    def _load_receipt_key(self):
        path = self.state / 'connection-receipts-v1.dpapi'
        if not path.exists():
            encrypted = self.credentials.protect(secrets.token_hex(32))
            try:
                exclusive_bytes(path, encrypted)
            except FileExistsError:
                pass
        try:
            key = self.credentials.unprotect(path.read_bytes())
            if type(key) is not str or len(key) != 64:
                raise ValueError()
            return bytes.fromhex(key)
        except Exception:
            raise ContractError('connection_config_unavailable') from None

    def _library(self):
        # Existing schema validation is reused; no credential loader is used.
        _, _, observed = self.store._library()
        raw = self.library.read_bytes()
        if digest(raw) != observed:
            raise ContractError('connection_config_changed')
        return _decode(raw), observed

    def _registration(self, expected):
        if self.registration is None:
            return None, None
        raw = self.registration.read_bytes()
        value = object_fields(_decode(raw), {'schema_version', 'registration_id', 'library_path', 'library_sha256'})
        identifier(value['registration_id'])
        if (type(value['schema_version']) is not int or value['schema_version'] != 1
                or Path(value['library_path']).resolve() != self.library or value['library_sha256'] != expected):
            raise ContractError('connection_config_registration_changed')
        return value, digest(raw)

    def _coherent(self):
        if self._pending():
            raise ContractError('connection_config_recovery_required')
        document, current = self._library()
        known = self._db.execute('SELECT library_sha256 FROM connection_config_meta WHERE singleton=1').fetchone()[0]
        if current != known:
            raise ContractError('connection_config_recovery_required')
        self._registration(current)
        return document, current

    @contextmanager
    def _transaction(self, coherent=True):
        with self._lock:
            self._db.execute('BEGIN IMMEDIATE')
            try:
                if coherent:
                    self._coherent()
                yield
                self._db.execute('COMMIT')
            except BaseException:
                self._db.execute('ROLLBACK')
                raise

    @contextmanager
    def admission_barrier(self):
        """Native fusion wraps full run.check/run.start with this same barrier."""
        with self._transaction():
            yield

    def _intent_path(self, request_id):
        identifier(request_id)
        directory = self.state / 'connection-config-intents-v1'
        directory.mkdir(exist_ok=True)
        return directory / (request_id + '.json')

    def _write_intent(self, intent):
        raw = canonical_json(intent).encode('utf8')
        value = dict(body=intent, seal=hmac.new(self._receipt_key, raw, hashlib.sha256).hexdigest())
        atomic_bytes(self._intent_path(intent['request_id']), (canonical_json(value) + '\n').encode('utf8'))

    def _intents(self):
        directory = self.state / 'connection-config-intents-v1'
        result = []
        for path in sorted(directory.glob('*.json')):
            try:
                raw = path.read_bytes()
                if len(raw) > 1024 * 1024:
                    raise ValueError()
                value = object_fields(_decode(raw), {'body', 'seal'})
                body = value['body']
                identifier(body['request_id'])
                expected = hmac.new(self._receipt_key, canonical_json(body).encode('utf8'), hashlib.sha256).hexdigest()
                if (path.name != body['request_id'] + '.json' or type(value['seal']) is not str
                        or not hmac.compare_digest(value['seal'], expected)
                        or body['phase'] not in ('prepared', 'completed', 'cancelled')):
                    raise ValueError()
                result.append(body)
            except Exception:
                raise ContractError('connection_config_recovery_required') from None
        return result

    def _pending(self):
        return [row for row in self._intents() if row['phase'] == 'prepared']

    def _draft_plan(self, old_id, new_id, new_hash):
        result = []
        for row in self.store._db.execute('SELECT * FROM style_drafts').fetchall():
            draft = _decode(row['draft_json'].encode('utf8'))
            if draft['connection_id'] != old_id:
                continue
            if type(row['revision']) is not int or row['revision'] >= 2 ** 53 - 1:
                raise ContractError('connection_config_profile_revision_invalid')
            draft.update(connection_id=new_id, revision=row['revision'] + 1)
            after = dict(profile_id=row['profile_id'], revision=draft['revision'], draft_json=canonical_json(draft), library_hash=new_hash)
            result.append(dict(before=dict(row), after=after))
        return result

    def _apply_draft_plan(self, intent, *, apply):
        plan = intent['drafts']
        ids = {entry['before']['profile_id'] for entry in plan}
        for row in self.store._db.execute('SELECT * FROM style_drafts').fetchall():
            draft = _decode(row['draft_json'].encode('utf8'))
            if draft['connection_id'] == intent['old_connection_id'] and row['profile_id'] not in ids:
                raise ContractError('connection_config_style_changed')
        for entry in plan:
            row = self.store._db.execute('SELECT * FROM style_drafts WHERE profile_id=?', (entry['before']['profile_id'],)).fetchone()
            current = dict(row) if row is not None else None
            if current not in (entry['before'], entry['after']):
                raise ContractError('connection_config_style_changed')
            if apply and current == entry['before']:
                after = entry['after']
                self.store._db.execute('UPDATE style_drafts SET revision=?,draft_json=?,library_hash=? WHERE profile_id=?',
                                      (after['revision'], after['draft_json'], after['library_hash'], after['profile_id']))

    @staticmethod
    def _public(row, credential_present):
        return dict(id=row['id'], name=row['name'], provider=row['provider'], endpoint=row['base_url'],
                    model=row['default_model'], remember_key=row['remember_key'],
                    credential_configured=credential_present, credential_check='stored_not_read' if credential_present else 'not_stored')

    def configuration(self, args):
        object_fields(args, set())
        with self._transaction(coherent=False):
            pending = self._pending()
            if pending:
                return dict(schema_version=1, ready=False, connections=[], config_fingerprint=None,
                            recovery=[dict(configuration_request_id=row['request_id'],
                                           expected_config_fingerprint=row['after_sha256']) for row in pending],
                            retired_credentials=[], remote_connection_tested=False, host_recheck_required=True)
            document, current = self._coherent()
            retired = [dict(configuration_request_id=row['request_id'], expected_config_fingerprint=current)
                       for row in self._intents() if row['phase'] == 'completed'
                       and (self.library.parent / 'secrets' / (row['old_connection_id'] + '.dpapi')).is_file()
                       and not any(c['id'] == row['old_connection_id'] for c in document['connections'])]
            return dict(schema_version=1, ready=True, recovery=[], retired_credentials=retired, config_fingerprint=current,
                        connections=[self._public(row, row['remember_key'] and
                            (self.library.parent / 'secrets' / (row['id'] + '.dpapi')).is_file()) for row in document['connections']],
                        remote_connection_tested=False, host_recheck_required=True)

    def _stopped(self):
        if self.stopped_guard() is not True:
            raise ContractError('connection_config_run_unreleased')

    def configure(self, args, request_id):
        identifier(request_id)
        args = configure_args(args)
        fingerprint = hmac.new(self._receipt_key, canonical_json(args).encode('utf8'), hashlib.sha256).hexdigest()
        with self.admission_barrier():
            previous = self._db.execute('SELECT * FROM connection_config_receipts WHERE request_id=?', (request_id,)).fetchone()
            if previous is not None:
                if previous['fingerprint'] != fingerprint:
                    raise ContractError('request_id_conflict')
                receipt = json.loads(previous['receipt_json'])
                if digest(self.library.read_bytes()) != receipt['config_fingerprint']:
                    raise ContractError('connection_config_changed')
                return receipt
            self._stopped()
            document, before = self._coherent()
            if args['expected_config_fingerprint'] != before:
                raise ContractError('connection_config_changed')
            originals = [row for row in document['connections'] if row['id'] == args['connection_id']]
            if len(originals) != 1:
                raise ContractError('connection_config_connection_missing')
            original = originals[0]
            registry, registry_hash = self._registration(before)
            secret_root = self.library.parent / 'secrets'
            secret_root.mkdir(exist_ok=True)
            old_secret = secret_root / (original['id'] + '.dpapi')
            encrypted = None
            operation = args['credential_operation']
            if operation == 'set':
                encrypted = self.credentials.protect(args['api_key'])
                if self.credentials.unprotect(encrypted) != args['api_key']:
                    raise ContractError('connection_credential_unavailable')
            elif operation == 'keep' and original['remember_key']:
                if (args['endpoint'], args['provider']) != (original['base_url'], original['provider']):
                    raise ContractError('connection_credential_reentry_required')
                encrypted = old_secret.read_bytes()
            if encrypted is not None and not 1 <= len(encrypted) <= 65536:
                raise ContractError('connection_credential_unavailable')
            new_id = str(uuid.uuid4())
            replacement = dict(id=new_id, name=args['name'], provider=args['provider'], base_url=args['endpoint'],
                               default_model=args['model'], remember_key=encrypted is not None)
            updated = deepcopy(document)
            updated['connections'] = [replacement if row['id'] == original['id'] else row for row in updated['connections']]
            for row in updated['commanders']:
                if row['connection_id'] == original['id']:
                    row['connection_id'] = new_id
            raw = (canonical_json(updated) + '\n').encode('utf8')
            after = digest(raw)
            new_secret = secret_root / (new_id + '.dpapi')
            # New credential is unreferenced until the atomic library commit.
            if encrypted is not None:
                with new_secret.open('xb') as stream:
                    stream.write(encrypted)
                    stream.flush()
                    os.fsync(stream.fileno())
            receipt = dict(schema_version=1, saved=True, previous_connection_id=original['id'], connection_id=new_id,
                           config_fingerprint=after, profile_recheck_required=True, runtime_reload_required=True,
                           remote_connection_tested=False, credential_configured=encrypted is not None,
                           credential_operation_completed=True, retired_credential_cleanup_pending=old_secret.is_file())
            new_registry = deepcopy(registry)
            if new_registry is not None:
                new_registry.update(library_sha256=after, registration_id=str(uuid.uuid4()))
            intent = dict(request_id=request_id, phase='prepared', fingerprint=fingerprint, before_sha256=before,
                          after_sha256=after, old_connection_id=original['id'], new_connection_id=new_id,
                          encrypted_sha256=digest(encrypted) if encrypted is not None else None,
                          old_registration_sha256=registry_hash, new_registration=new_registry,
                          drafts=self._draft_plan(original['id'], new_id, after), receipt=receipt)
            self._write_intent(intent)
            try:
                self._stopped()
                if digest(self.library.read_bytes()) != before or (self.registration is not None and digest(self.registration.read_bytes()) != registry_hash):
                    raise ContractError('connection_config_changed')
            except BaseException:
                intent['phase'] = 'cancelled'
                self._write_intent(intent)
                new_secret.unlink(missing_ok=True)
                raise
            # A crash after the file replacement and before SQLite commit leaves
            # meta != library. All later admissions reject until explicit repair.
            with self.store._transaction():
                self._apply_draft_plan(intent, apply=False)
                atomic_bytes(self.library, raw)
                if new_registry is not None:
                    atomic_bytes(self.registration, (canonical_json(new_registry) + '\n').encode('utf8'))
                self._apply_draft_plan(intent, apply=True)
                self._db.execute('UPDATE connection_config_meta SET library_sha256=? WHERE singleton=1', (after,))
                self._db.execute('INSERT INTO connection_config_receipts VALUES (?,?,?)', (request_id, fingerprint, canonical_json(receipt)))
        # Only after both SQLite transactions committed may the intent close.
        intent['phase'] = 'completed'
        self._write_intent(intent)
        return receipt

    def recover(self, args):
        args = object_fields(args, {'configuration_request_id', 'expected_config_fingerprint'})
        identifier(args['configuration_request_id'])
        with self._transaction(coherent=False):
            self._stopped()
            rows = [row for row in self._intents() if row['request_id'] == args['configuration_request_id']]
            if len(rows) != 1 or rows[0]['after_sha256'] != args['expected_config_fingerprint']:
                raise ContractError('connection_config_recovery_required')
            intent = rows[0]
            if intent['phase'] != 'prepared':
                self._coherent()
                return dict(schema_version=1, recovered=True, saved=intent['phase'] == 'completed', host_recheck_required=True)
            _, current = self._library()
            known = self._db.execute('SELECT library_sha256 FROM connection_config_meta WHERE singleton=1').fetchone()[0]
            if known not in (intent['before_sha256'], intent['after_sha256']):
                raise ContractError('connection_config_recovery_required')
            if current == intent['before_sha256']:
                self._registration(current)
                with self.store._transaction():
                    self._apply_draft_plan(intent, apply=False)
                    if any(dict(self.store._db.execute('SELECT * FROM style_drafts WHERE profile_id=?',
                            (entry['before']['profile_id'],)).fetchone()) != entry['before'] for entry in intent['drafts']):
                        raise ContractError('connection_config_style_changed')
                intent['phase'] = 'cancelled'
                (self.library.parent / 'secrets' / (intent['new_connection_id'] + '.dpapi')).unlink(missing_ok=True)
                saved = False
            elif current == intent['after_sha256']:
                encrypted = intent['encrypted_sha256']
                secret = self.library.parent / 'secrets' / (intent['new_connection_id'] + '.dpapi')
                if encrypted is not None and (not secret.is_file() or digest(secret.read_bytes()) != encrypted):
                    raise ContractError('connection_config_recovery_required')
                if self.registration is not None:
                    registry_raw = (canonical_json(intent['new_registration']) + '\n').encode('utf8')
                    observed = digest(self.registration.read_bytes())
                    if observed not in (intent['old_registration_sha256'], digest(registry_raw)):
                        raise ContractError('connection_config_registration_changed')
                self._stopped()
                with self.store._transaction():
                    self._apply_draft_plan(intent, apply=False)
                    if self.registration is not None:
                        atomic_bytes(self.registration, registry_raw)
                    self._apply_draft_plan(intent, apply=True)
                    self._db.execute('UPDATE connection_config_meta SET library_sha256=? WHERE singleton=1', (current,))
                    self._db.execute('INSERT OR REPLACE INTO connection_config_receipts VALUES (?,?,?)',
                                     (intent['request_id'], intent['fingerprint'], canonical_json(intent['receipt'])))
                intent['phase'] = 'completed'
                saved = True
            else:
                raise ContractError('connection_config_recovery_required')
        self._write_intent(intent)
        return dict(schema_version=1, recovered=True, saved=saved, host_recheck_required=True)

    def cleanup_retired(self, args):
        args = object_fields(args, {'configuration_request_id', 'expected_config_fingerprint'})
        identifier(args['configuration_request_id'])
        with self.admission_barrier():
            self._stopped()
            rows = [row for row in self._intents() if row['request_id'] == args['configuration_request_id'] and row['phase'] == 'completed']
            document, current = self._coherent()
            if len(rows) != 1 or current != args['expected_config_fingerprint']:
                raise ContractError('connection_config_changed')
            old = rows[0]['old_connection_id']
            if any(row['id'] == old for row in document['connections']):
                raise ContractError('connection_config_recovery_required')
            (self.library.parent / 'secrets' / (old + '.dpapi')).unlink(missing_ok=True)
            return dict(schema_version=1, retired_credential_removed=True, config_fingerprint=current)

    def dispatch(self, operation, args, request_id):
        if operation not in OPERATIONS:
            raise ContractError('operation_unsupported')
        if operation == 'connections.configuration':
            return self.configuration(args)
        if operation == 'connections.recover':
            return self.recover(args)
        if operation == 'connections.cleanup_retired':
            return self.cleanup_retired(args)
        return self.configure(args, request_id)

    def handle(self, request):
        request_id = None
        try:
            value = object_fields(request, {'schema_version', 'request_id', 'operation', 'args'})
            request_id = identifier(value['request_id'])
            if len(canonical_json(value).encode('utf8')) > MAX_REQUEST_BYTES:
                raise ContractError('request_too_large')
            if type(value['schema_version']) is not int or value['schema_version'] != 1:
                raise ContractError('connection_config_schema_invalid')
            result = self.dispatch(value['operation'], value['args'], request_id)
            from .bridge_service import _result_safe
            _result_safe(result)
            if len(canonical_json(result).encode('utf8')) > MAX_REQUEST_BYTES:
                raise ContractError('connection_config_response_too_large')
            return dict(schema_version=1, request_id=request_id, ok=True, result=result)
        except ContractError as error:
            allowed = {'connection_config_schema_invalid', 'connection_config_changed', 'connection_config_recovery_required',
                       'connection_config_run_unreleased', 'connection_config_connection_missing', 'connection_config_registration_changed',
                       'connection_credential_unavailable', 'connection_credential_invalid', 'connection_credential_operation_invalid',
                       'connection_credential_reentry_required',
                       'request_id_conflict', 'operation_unsupported', 'unexpected_fields', 'invalid_uuid', 'invalid_sha256',
                       'invalid_connection_endpoint', 'invalid_connection', 'invalid_text', 'request_too_large'}
            return dict(schema_version=1, request_id=request_id, ok=False,
                        error=dict(code=error.code if error.code in allowed else 'connection_config_unavailable'))
        except Exception:
            return dict(schema_version=1, request_id=request_id, ok=False, error=dict(code='connection_config_unavailable'))
