from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from host_runtime import connection_config_bootstrap_v1 as bootstrap
from host_runtime.contracts import ContractError
from host_runtime.profile_store import ProfileStore
from host_runtime.connection_config_service_v1 import ConnectionConfigServiceV1

COMMANDER = '11111111-1111-4111-8111-111111111111'


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='connection-first-use-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = (self.root / 'library.v2.json', self.root / 'desktop-runtime-config.json', self.root / 'desktop-runtime')

    def initialize(self):
        return bootstrap.initialize_connection_library_v1(*self.args, commander_id=COMMANDER)

    def test_new_user_template_is_configurable_without_key_or_model_call(self):
        receipt = self.initialize()
        self.assertTrue(receipt['initialized'])
        self.assertFalse(receipt['host_started'])
        self.assertFalse(receipt['credentials_created'])
        store = ProfileStore(self.args[0], self.args[2])
        self.addCleanup(store.close)
        service = ConnectionConfigServiceV1(store, stopped_guard=lambda: True, registration_path=self.args[1])
        self.addCleanup(service.close)
        value = service.configuration({})
        self.assertTrue(value['ready'])
        self.assertFalse(value['connections'][0]['credential_configured'])
        self.assertEqual(self.initialize(), receipt)

    def test_interrupted_registration_initialization_completes_exact_public_template(self):
        real = bootstrap.create_once
        def create(path, raw):
            if Path(path) == self.args[1]:
                raise OSError('test only')
            return real(path, raw)
        with patch.object(bootstrap, 'create_once', side_effect=create):
            with self.assertRaises(OSError):
                self.initialize()
        raw = self.args[0].read_bytes()
        self.assertTrue(self.initialize()['initialized'])
        self.assertEqual(self.args[0].read_bytes(), raw)

    def test_unrelated_existing_source_and_changed_template_are_never_overwritten(self):
        self.args[0].write_text('do not overwrite')
        with self.assertRaises(ContractError):
            self.initialize()
        self.assertEqual(self.args[0].read_text(), 'do not overwrite')
