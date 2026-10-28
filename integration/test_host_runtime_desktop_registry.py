import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from host_runtime.contracts import ContractError
from host_runtime.desktop_registry import CONFIG_NAME, load_registration, register_library
from test_host_runtime_profile_store import library


class DesktopRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "protected-library.json"
        self.library.write_text(json.dumps(library(), ensure_ascii=False), encoding="utf-8")
        self.home = self.root / "home"

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_reference_is_idempotent_and_never_copies_credentials(self):
        before = self.library.read_bytes()
        with patch("ctypes.WinDLL", side_effect=AssertionError("No DPAPI access")):
            first = register_library(self.library, self.home)
            second = register_library(self.library, self.home)
        self.assertEqual(first, second)
        self.assertFalse(first["credential_material_copied"])
        self.assertEqual(before, self.library.read_bytes())
        self.assertEqual(load_registration(self.home)["library_path"], str(self.library.resolve()))
        self.assertEqual([p.name for p in self.home.iterdir()], [CONFIG_NAME])

    def test_registered_source_change_is_rejected_without_silent_migration(self):
        register_library(self.library, self.home)
        self.library.write_text(json.dumps({**library(), "unexpected": True}), encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            load_registration(self.home)
        self.assertEqual(caught.exception.code, "registered_library_changed")

    def test_different_source_does_not_replace_existing_registration(self):
        register_library(self.library, self.home)
        other = self.root / "another-library.json"
        other.write_bytes(self.library.read_bytes())
        with self.assertRaises(ContractError) as caught:
            register_library(other, self.home)
        self.assertEqual(caught.exception.code, "runtime_registration_conflict")

    def test_duplicate_unknown_and_relative_configuration_are_rejected(self):
        register_library(self.library, self.home)
        record = load_registration(self.home)
        for raw in [json.dumps({**record, "unknown": 1}), json.dumps({**record, "library_path": "relative.json"}), '{"schema_version":1,"schema_version":1}']:
            (self.home / CONFIG_NAME).write_text(raw, encoding="utf-8")
            with self.assertRaises(ContractError):
                load_registration(self.home)


if __name__ == "__main__":
    unittest.main()
