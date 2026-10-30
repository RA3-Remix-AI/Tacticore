from io import BytesIO
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from host_runtime.connection_config_server_v1 import NativeConfigurationServerV1, serve


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='connection-server-v1-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        def backend(store):
            db = sqlite3.connect(':memory:')
            db.execute('CREATE TABLE readiness (id TEXT)')
            return SimpleNamespace(_db=db, run_resume=lambda *_: dict(run=None, observation_only=True, other_unreleased_runs=0), close=db.close)
        self.server = NativeConfigurationServerV1(root / 'library.json', root / 'state', root / 'registration.json',
            '11111111-1111-4111-8111-111111111111', backend_factory=backend)
        self.addCleanup(self.server.close)

    def call(self, operation, args):
        return self.server.handle(dict(schema_version=1, request_id=str(uuid.uuid4()), operation=operation, args=args))

    def test_first_use_bootstrap_then_configuration_via_actual_server_entry(self):
        self.assertEqual(self.call('connections.configuration', {})['error']['code'], 'connection_setup_required')
        self.assertTrue(self.call('connections.bootstrap', {})['ok'])
        result = self.call('connections.configuration', {})
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['result']['ready'])

    def test_configuration_channel_rejects_all_host_and_model_operations(self):
        for operation in ('run.start', 'run.stop', 'run.check', 'model.call', 'profiles.save'):
            self.assertEqual(self.call(operation, {})['error']['code'], 'operation_unsupported')
        self.assertIsNone(self.server.backend)

    def test_bounded_pipe_rejects_duplicate_keys_and_oversize_without_echoing_input(self):
        source = BytesIO(b'{"api_key":"FAKE-SECRET","api_key":"OTHER"}\n' + b'x' * 17000 + b'\n')
        target = BytesIO()
        serve(self.server, source, target)
        replies = target.getvalue().decode()
        self.assertNotIn('FAKE-SECRET', replies)
        self.assertNotIn('OTHER', replies)
        self.assertEqual(len(replies.splitlines()), 2)
        self.assertTrue(all(json.loads(row)['ok'] is False for row in replies.splitlines()))

    def test_actual_configuration_module_pipe_initializes_and_saves_without_host_or_model(self):
        self.server.close()
        # Replace the setUp object's cleanup with a harmless closed server.
        self.server.bridge = self.server.backend = self.server.store = None
        process = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', '-m', 'host_runtime.connection_config_server_v1',
            '--library', str(self.server.library), '--state-dir', str(self.server.state), '--registration', str(self.server.registration),
            '--commander-id', self.server.commander], cwd=Path(__file__).resolve().parent,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        def call(operation, args):
            value = dict(schema_version=1, request_id=str(uuid.uuid4()), operation=operation, args=args)
            process.stdin.write((json.dumps(value) + '\n').encode())
            process.stdin.flush()
            result = json.loads(process.stdout.readline())
            self.assertEqual(result['request_id'], value['request_id'])
            return result
        self.assertTrue(call('connections.bootstrap', {})['ok'])
        configuration = call('connections.configuration', {})['result']
        row = configuration['connections'][0]
        result = call('connections.configure', dict(schema_version=1, connection_id=row['id'],
            expected_config_fingerprint=configuration['config_fingerprint'], name='Local test', provider='自定义',
            endpoint='http://127.0.0.1:9999/v1', model='offline-only', credential_operation='set', api_key='FAKE-PIPE-KEY'))
        self.assertTrue(result['ok'], result)
        self.assertNotIn('FAKE-PIPE-KEY', json.dumps(result))
        self.assertEqual(call('run.start', {})['error']['code'], 'operation_unsupported')
        process.stdin.close()
        self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(process.stdout.read(), b'')
        self.assertNotIn(b'FAKE-PIPE-KEY', process.stderr.read())
        process.stdout.close()
        process.stderr.close()
        db = sqlite3.connect(self.server.state / 'desktop-launch-index.sqlite3')
        try:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM launches').fetchone()[0], 0)
        finally:
            db.close()
