"""Actual service entry, temporary libraries and fake-only Windows DPAPI keys."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from host_runtime.connection_config_service_v1 import ConnectionConfigServiceV1, digest
from host_runtime.connection_config_credentials_v1 import WindowsConnectionCredentialsV1
from host_runtime.contracts import ContractError
from host_runtime.profile_store import ProfileStore
from test_host_runtime_profile_store import PROFILE, library

FAKE_KEY = 'FAKE-ONLY-CONNECTION-CONFIG-SECRET-12345'


class ConnectionConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='connection-config-v1-')
        self.root = Path(self.temp.name)
        self.lib = self.root / 'library.v2.json'
        self.lib.write_text(json.dumps(library()), encoding='utf8')
        self.store = ProfileStore(self.lib, self.root / 'state')
        self.registration = self.root / 'desktop-runtime-config.json'
        self.registration.write_text(json.dumps(dict(schema_version=1, registration_id=str(uuid.uuid4()),
            library_path=str(self.lib), library_sha256=digest(self.lib.read_bytes()))))
        self.allowed = True
        self.service = ConnectionConfigServiceV1(self.store, stopped_guard=lambda: self.allowed,
                                                  registration_path=self.registration)

    def tearDown(self):
        self.service.close()
        self.store.close()
        self.temp.cleanup()

    def invoke(self, operation, args, request_id=None):
        return self.service.handle(dict(schema_version=1, request_id=request_id or str(uuid.uuid4()), operation=operation, args=args))

    def args(self, **changes):
        state = self.invoke('connections.configuration', {})['result']
        row = state['connections'][0]
        value = dict(schema_version=1, connection_id=row['id'], expected_config_fingerprint=state['config_fingerprint'],
                     name='Local test connection', provider='自定义', endpoint='http://127.0.0.1:9999/v1',
                     model='offline-model', credential_operation='set', api_key=FAKE_KEY)
        value.update(changes)
        return value

    def test_normal_service_save_real_dpapi_and_existing_model_loader_compatibility(self):
        args = self.args()
        saved = self.invoke('connections.configure', args)
        self.assertTrue(saved['ok'], saved)
        receipt = saved['result']
        self.assertNotEqual(receipt['connection_id'], args['connection_id'])
        state = self.invoke('connections.configuration', {})['result']
        self.assertEqual(state['config_fingerprint'], receipt['config_fingerprint'])
        self.assertTrue(state['connections'][0]['credential_configured'])
        doc = json.loads(self.lib.read_text())
        self.assertEqual(doc['commanders'][0]['connection_id'], receipt['connection_id'])
        cipher = self.lib.parent / 'secrets' / (receipt['connection_id'] + '.dpapi')
        self.assertNotIn(FAKE_KEY.encode(), cipher.read_bytes())
        self.assertEqual(WindowsConnectionCredentialsV1().unprotect(cipher.read_bytes()), FAKE_KEY)
        import sys
        strategy = str(Path(__file__).resolve().parents[1] / 'strategy')
        if strategy not in sys.path:
            sys.path.insert(0, strategy)
        from http_adapter import load_profile
        loaded = load_profile(self.lib, PROFILE)
        self.assertEqual(loaded.key, FAKE_KEY)
        self.assertEqual(loaded.model, 'offline-model')
        self.assertFalse(receipt['remote_connection_tested'])

    def test_status_error_receipt_library_and_sqlite_never_contain_plaintext_key(self):
        result = self.invoke('connections.configure', self.args())
        status = self.invoke('connections.configuration', {})
        for value in (result, status):
            text = json.dumps(value)
            self.assertNotIn(FAKE_KEY, text)
            self.assertNotIn(str(self.root), text)
            self.assertNotIn('api_key', text)
        self.assertNotIn(FAKE_KEY.encode(), self.lib.read_bytes())
        for path in self.store.state_dir.glob('*.sqlite3*'):
            self.assertNotIn(FAKE_KEY.encode(), path.read_bytes())

    def test_repeated_identical_request_is_one_write_and_different_secret_conflicts(self):
        args, request = self.args(), str(uuid.uuid4())
        first = self.invoke('connections.configure', args, request)
        before = self.lib.read_bytes()
        self.assertEqual(self.invoke('connections.configure', args, request), first)
        self.assertEqual(before, self.lib.read_bytes())
        changed = dict(args, api_key='FAKE-OTHER-KEY')
        response = self.invoke('connections.configure', changed, request)
        self.assertFalse(response['ok'])
        self.assertEqual(response['error']['code'], 'request_id_conflict')
        self.assertNotIn(changed['api_key'], json.dumps(response))

    def test_stale_configuration_fingerprint_cannot_replace_new_settings(self):
        old = self.args()
        self.assertTrue(self.invoke('connections.configure', old)['ok'])
        before = self.lib.read_bytes()
        failed = self.invoke('connections.configure', old)
        self.assertEqual(failed['error']['code'], 'connection_config_changed')
        self.assertEqual(before, self.lib.read_bytes())

    def test_unreleased_run_rejects_before_change(self):
        args = self.args()
        self.allowed = False
        before = self.lib.read_bytes()
        response = self.invoke('connections.configure', args)
        self.assertEqual(response['error']['code'], 'connection_config_run_unreleased')
        self.assertEqual(before, self.lib.read_bytes())

    def test_second_stopped_gate_and_source_cas_are_not_skipped_after_slow_preparation(self):
        args = self.args()
        checks = iter((True, False))
        self.service.stopped_guard = lambda: next(checks)
        before = self.lib.read_bytes()
        response = self.invoke('connections.configure', args)
        self.assertEqual(response['error']['code'], 'connection_config_run_unreleased')
        self.assertEqual(before, self.lib.read_bytes())

    def test_webview_paths_secret_refs_unknown_fields_and_wrong_types_reject(self):
        for changes in [dict(path='C:/secret'), dict(library_path='C:/secret'), dict(credential_reference='env:SECRET'),
                        dict(api_key_path='C:/secret'), dict(schema_version=True), dict(credential_operation='read'),
                        dict(connection_id='../secret'), dict(remember_key=True)]:
            args = self.args(**changes)
            before = self.lib.read_bytes()
            result = self.invoke('connections.configure', args)
            self.assertFalse(result['ok'], changes)
            self.assertEqual(before, self.lib.read_bytes())
            self.assertNotIn('C:/secret', json.dumps(result))

    def test_endpoint_rejects_userinfo_query_fragment_nonlocal_http_and_completion_suffix(self):
        for endpoint in ('https://user:password@example.com/v1', 'https://example.com/v1?api_key=secret',
                         'https://example.com/v1#secret', 'http://example.com/v1', 'https://example.com/v1/chat/completions'):
            result = self.invoke('connections.configure', self.args(endpoint=endpoint))
            self.assertFalse(result['ok'])
            self.assertNotIn(endpoint, json.dumps(result))

    def test_keep_and_clear_are_explicit_and_never_return_a_key(self):
        first = self.invoke('connections.configure', self.args())['result']
        kept = self.args(credential_operation='keep')
        kept.pop('api_key')
        request = str(uuid.uuid4())
        result = self.invoke('connections.configure', kept, request)
        self.assertTrue(result['ok'], result)
        self.assertTrue((self.lib.parent / 'secrets' / (first['connection_id'] + '.dpapi')).exists())
        cleanup = self.invoke('connections.cleanup_retired', dict(configuration_request_id=request,
            expected_config_fingerprint=result['result']['config_fingerprint']))
        self.assertTrue(cleanup['ok'], cleanup)
        self.assertFalse((self.lib.parent / 'secrets' / (first['connection_id'] + '.dpapi')).exists())
        clear = self.args(credential_operation='clear')
        clear.pop('api_key')
        result = self.invoke('connections.configure', clear)
        self.assertTrue(result['ok'], result)
        self.assertFalse(self.invoke('connections.configuration', {})['result']['connections'][0]['credential_configured'])
        self.assertFalse(json.loads(self.lib.read_text())['connections'][0]['remember_key'])

    def test_existing_saved_key_cannot_be_reused_for_a_new_endpoint_without_reentry(self):
        self.assertTrue(self.invoke('connections.configure', self.args())['ok'])
        args = self.args(credential_operation='keep', endpoint='https://new.example.test/v1')
        args.pop('api_key')
        before = self.lib.read_bytes()
        result = self.invoke('connections.configure', args)
        self.assertEqual(result['error']['code'], 'connection_credential_reentry_required')
        self.assertEqual(before, self.lib.read_bytes())

    def test_saved_style_is_retained_with_new_revision_and_connection_binding(self):
        profile = self.store.get_profile(PROFILE)['profile']
        draft = deepcopy(profile['draft'])
        draft['custom_traits'] = '持久化本机测试风格'
        self.store.save_profile(str(uuid.uuid4()), draft, profile['revision'])
        before = self.store.get_profile(PROFILE)['profile']
        result = self.invoke('connections.configure', self.args())['result']
        after = self.store.get_profile(PROFILE)['profile']
        self.assertEqual(after['revision'], before['revision'] + 1)
        self.assertEqual(after['custom_traits'], before['custom_traits'])
        self.assertEqual(after['connection_id'], result['connection_id'])
        self.assertTrue(after['validation']['ok'])

    def test_external_library_or_registration_change_permanently_blocks_admission_barrier(self):
        args = self.args()
        self.lib.write_bytes(self.lib.read_bytes() + b' ')
        result = self.invoke('connections.configure', args)
        self.assertEqual(result['error']['code'], 'connection_config_recovery_required')
        with self.assertRaises(ContractError):
            with self.service.admission_barrier():
                self.fail('must not reach launch')

    def test_interrupted_registration_commit_is_not_a_success_or_a_launchable_configuration(self):
        args = self.args()
        from host_runtime import connection_config_service_v1 as module
        real = module.atomic_bytes
        def write(path, raw):
            if Path(path) == self.registration:
                raise OSError('PRIVATE ' + FAKE_KEY)
            return real(path, raw)
        with patch.object(module, 'atomic_bytes', side_effect=write):
            result = self.invoke('connections.configure', args)
        self.assertFalse(result['ok'])
        self.assertNotIn(FAKE_KEY, json.dumps(result))
        pending = self.invoke('connections.configuration', {})['result']
        self.assertFalse(pending['ready'])
        self.assertEqual(pending['connections'], [])
        with self.assertRaises(ContractError):
            with self.service.admission_barrier():
                self.fail('must not reach model/host')
        recovery = self.invoke('connections.recover', pending['recovery'][0])
        self.assertTrue(recovery['ok'], recovery)
        self.assertTrue(recovery['result']['saved'])
        self.assertTrue(self.invoke('connections.configuration', {})['result']['ready'])
        with self.service.admission_barrier():
            pass

    def test_crash_after_library_before_draft_migration_can_restore_style_without_loss(self):
        profile = self.store.get_profile(PROFILE)['profile']
        draft = dict(profile['draft'], custom_traits='原有风格不丢失')
        self.store.save_profile(str(uuid.uuid4()), draft, profile['revision'])
        before = self.store.get_profile(PROFILE)['profile']
        args = self.args()
        with patch.object(self.service, '_apply_draft_plan', side_effect=lambda intent, apply: (
                (_ for _ in ()).throw(OSError('PRIVATE')) if apply else None)):
            response = self.invoke('connections.configure', args)
        self.assertFalse(response['ok'])
        pending = self.invoke('connections.configuration', {})['result']
        self.assertFalse(pending['ready'])
        result = self.invoke('connections.recover', pending['recovery'][0])
        self.assertTrue(result['ok'], result)
        after = self.store.get_profile(PROFILE)['profile']
        self.assertEqual(after['custom_traits'], before['custom_traits'])
        self.assertEqual(after['revision'], before['revision'] + 1)
        self.assertTrue(after['validation']['ok'])

    def test_crash_before_library_commit_cancels_the_prepared_edit_without_new_credentials(self):
        args = self.args()
        before = self.lib.read_bytes()
        from host_runtime import connection_config_service_v1 as module
        real = module.atomic_bytes
        def write(path, raw):
            if Path(path) == self.lib:
                raise OSError('PRIVATE')
            return real(path, raw)
        with patch.object(module, 'atomic_bytes', side_effect=write):
            self.assertFalse(self.invoke('connections.configure', args)['ok'])
        self.assertEqual(self.lib.read_bytes(), before)
        pending = self.invoke('connections.configuration', {})['result']['recovery'][0]
        result = self.invoke('connections.recover', pending)
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['result']['saved'])
        self.assertEqual(self.lib.read_bytes(), before)
        self.assertTrue(self.invoke('connections.configuration', {})['result']['ready'])

    def test_recovery_rejects_changed_style_or_missing_new_cipher_and_never_accepts_webview_paths(self):
        args = self.args()
        from host_runtime import connection_config_service_v1 as module
        real = module.atomic_bytes
        def write(path, raw):
            if Path(path) == self.registration:
                raise OSError('PRIVATE')
            return real(path, raw)
        with patch.object(module, 'atomic_bytes', side_effect=write):
            self.assertFalse(self.invoke('connections.configure', args)['ok'])
        pending = self.invoke('connections.configuration', {})['result']['recovery'][0]
        intent = self.service._pending()[0]
        cipher = self.lib.parent / 'secrets' / (intent['new_connection_id'] + '.dpapi')
        old = cipher.read_bytes()
        cipher.write_bytes(old + b'changed')
        self.assertFalse(self.invoke('connections.recover', pending)['ok'])
        cipher.write_bytes(old)
        self.assertFalse(self.invoke('connections.recover', dict(pending, path='C:/secret'))['ok'])
        self.assertTrue(self.invoke('connections.recover', pending)['ok'])

    def test_rpc_size_limit_and_malformed_secret_do_not_reach_a_write(self):
        for key in ('', 'spaces are invalid', 'line\nsecret', 'a' * 4097):
            self.assertFalse(self.invoke('connections.configure', self.args(api_key=key))['ok'])
        value = dict(schema_version=1, request_id=str(uuid.uuid4()), operation='connections.configure', args=self.args())
        value['args']['name'] = 'x' * 17000
        self.assertEqual(self.service.handle(value)['error']['code'], 'request_too_large')

    def test_credential_backend_exception_is_not_echoed(self):
        args = self.args()
        with patch.object(self.service.credentials, 'protect', side_effect=RuntimeError(FAKE_KEY)):
            result = self.invoke('connections.configure', args)
        self.assertEqual(result['error']['code'], 'connection_config_unavailable')
        self.assertNotIn(FAKE_KEY, json.dumps(result))
