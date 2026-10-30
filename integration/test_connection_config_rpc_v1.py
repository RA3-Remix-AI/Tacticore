import json
from pathlib import Path
import unittest
import uuid
import test_host_runtime_desktop_backend as fixtures
from host_runtime.connection_config_rpc_v1 import ConnectionAwareBridgeV1, NativeStoppedRunsV1
from host_runtime.connection_config_service_v1 import digest


class ConfiguredBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DesktopBackendTests()
        self.fixture.setUp()
        f = self.fixture
        self.registration = f.root / 'desktop-runtime-config.json'
        self.registration.write_text(json.dumps(dict(schema_version=1, registration_id=str(uuid.uuid4()),
            library_path=str(f.lib), library_sha256=digest(f.lib.read_bytes()))))
        self.bridge = ConnectionAwareBridgeV1(f.store, f.backend, registration_path=self.registration)

    def tearDown(self):
        self.bridge.close()
        self.fixture.tearDown()

    def call(self, operation, args):
        return self.bridge.handle(dict(schema_version=1, request_id=str(uuid.uuid4()), operation=operation, args=args))

    def test_actual_backend_guard_allows_no_run_and_refuses_an_unreleased_launch(self):
        f = self.fixture
        guard = NativeStoppedRunsV1(f.backend)
        self.assertTrue(guard())
        ready = f.ready()
        args = dict(session_id=ready['session_id'], ready_token=ready['ready_token'])
        f.backend.run_start(f.profile, args, str(uuid.uuid4()))
        self.assertEqual(len(f.spawner.commands), 1)  # Fake spawner only.
        self.assertFalse(guard())
        current = self.call('connections.configuration', {})['result']
        row = current['connections'][0]
        args = dict(schema_version=1, connection_id=row['id'], expected_config_fingerprint=current['config_fingerprint'],
            name=row['name'], provider=row['provider'], endpoint=row['endpoint'], model=row['model'], credential_operation='keep')
        failed = self.call('connections.configure', args)
        self.assertFalse(failed['ok'])
        self.assertEqual(failed['error']['code'], 'connection_config_run_unreleased')

    def test_configuration_save_invalidates_existing_check_and_uses_actual_service_entry(self):
        f = self.fixture
        self.assertTrue(f.ready()['ready'])
        self.assertGreater(f.backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0], 0)
        current = self.call('connections.configuration', {})['result']
        row = current['connections'][0]
        args = dict(schema_version=1, connection_id=row['id'], expected_config_fingerprint=current['config_fingerprint'],
            name=row['name'], provider=row['provider'], endpoint=row['endpoint'], model='new-offline-model', credential_operation='clear')
        saved = self.call('connections.configure', args)
        self.assertTrue(saved['ok'], saved)
        self.assertEqual(f.backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0], 0)
        self.assertEqual(f.spawner.commands, [])

    def test_corrupt_configuration_blocks_start_but_does_not_disable_status_or_stop_routes(self):
        f = self.fixture
        f.lib.write_bytes(f.lib.read_bytes() + b' ')
        failed = self.call('run.check', dict(profile_id=fixtures.PROFILE, profile_revision=f.profile['revision']))
        self.assertFalse(failed['ok'])
        self.assertEqual(failed['error']['code'], 'connection_config_recovery_required')
        resumed = self.call('run.resume', {})
        self.assertTrue(resumed['ok'], resumed)
        self.assertTrue(resumed['result']['observation_only'])
        self.assertEqual(f.spawner.commands, [])

    def test_existing_bad_receipt_key_does_not_disable_existing_run_observation(self):
        f = self.fixture
        self.bridge.close()
        path = f.store.state_dir / 'connection-receipts-v1.dpapi'
        path.write_bytes(b'old incomplete ciphertext')
        self.bridge = ConnectionAwareBridgeV1(f.store, f.backend, registration_path=self.registration)
        self.assertIsNone(self.bridge.configuration)
        self.assertTrue(self.call('run.resume', {})['ok'])
        failed = self.call('run.check', dict(profile_id=fixtures.PROFILE, profile_revision=f.profile['revision']))
        self.assertEqual(failed['error']['code'], 'connection_config_recovery_required')
        self.assertEqual(path.read_bytes(), b'old incomplete ciphertext')
