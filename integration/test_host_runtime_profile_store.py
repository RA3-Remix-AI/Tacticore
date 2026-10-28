"""Real SQLite CAS and read-only library projection, without secret loading."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from host_runtime.contracts import ContractError
from host_runtime.profile_store import ProfileStore

PROFILE = "c37de935-529b-4129-85f2-7596ccdc6a12"
CONNECTION = "f76d0537-8b7b-4540-b5ed-c1558b2b7e32"


def library():
    return dict(schema_version=2, connections=[dict(id=CONNECTION, name="Local", provider="自定义",
        base_url="http://127.0.0.1:8080/v1", remember_key=True, default_model="model-default")],
        commanders=[dict(id=PROFILE, name="铁锤", connection_id=CONNECTION, model="", personality=0, traits="先侦察。")])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "library.v2.json"
        self.document = library()
        self.write()
        self.original = self.library.read_bytes()
        self.store = ProfileStore(self.library, self.root / "state")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def write(self):
        self.library.write_text(json.dumps(self.document, ensure_ascii=False), encoding="utf-8")

    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as error:
            call()
        self.assertEqual(code, error.exception.code)

    def draft(self):
        return self.store.get_profile(PROFILE)["profile"]["draft"]

    def test_listing_reads_only_library_and_never_claims_credential_validity(self):
        original_open = Path.open
        paths = []
        def guarded_open(path, *args, **kwargs):
            paths.append(path.resolve())
            self.assertEqual(path.resolve(), self.library.resolve())
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", guarded_open):
            connections = self.store.list_connections()["connections"]
            profiles = self.store.list_profiles()["profiles"]
        self.assertGreater(len(paths), 0)
        self.assertIsNone(connections[0]["credential_configured"])
        self.assertEqual("not_checked", connections[0]["credential_check"])
        self.assertTrue(connections[0]["remember_key"])
        self.assertEqual("model-default", profiles[0]["effective"]["model"])
        self.assertFalse(profiles[0]["host_applied"])
        self.assertEqual(self.original, self.library.read_bytes())

    def test_revision_cas_request_idempotency_persists_across_reopen(self):
        draft = self.draft(); draft["custom_traits"] = "回撤后重整。"
        request = str(uuid.uuid4())
        receipt = self.store.save_profile(request, draft, 1)
        self.assertEqual(2, receipt["profile"]["revision"])
        self.assertEqual("saved", receipt["state"])
        self.assertFalse(receipt["host_applied"])
        self.assertEqual(receipt, self.store.save_profile(request, draft, 1))
        self.assertCode("request_id_conflict", lambda: self.store.save_profile(request, {**draft, "custom_traits": "变化"}, 1))
        self.assertCode("profile_revision_conflict", lambda: self.store.save_profile(str(uuid.uuid4()), draft, 1))
        self.store.close()
        self.store = ProfileStore(self.library, self.root / "state")
        self.assertEqual(receipt, self.store.save_profile(request, draft, 1))
        self.assertEqual(receipt["profile"], self.store.get_profile(PROFILE)["profile"])
        self.assertEqual(self.original, self.library.read_bytes())

    def test_two_connections_cannot_win_same_revision(self):
        other = ProfileStore(self.library, self.root / "state")
        draft = self.draft()
        def save(store):
            try:
                return store.save_profile(str(uuid.uuid4()), draft, 1)["state"]
            except ContractError as error:
                return error.code
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(save, [self.store, other]))
            self.assertCountEqual(["saved", "profile_revision_conflict"], outcomes)
        finally:
            other.close()

    def test_effective_model_resolution_rehashes_and_invalidates_library_binding(self):
        saved = self.store.save_profile(str(uuid.uuid4()), self.draft(), 1)["profile"]
        self.document["connections"][0]["default_model"] = "replacement-model"
        self.write()
        current = self.store.get_profile(PROFILE)["profile"]
        self.assertTrue(current["library_changed"])
        self.assertEqual("replacement-model", current["model"])
        self.assertNotEqual(saved["effective"]["effective_hash"], current["effective"]["effective_hash"])
        self.document["commanders"][0]["model"] = "commander-default"
        self.write()
        self.assertEqual("commander-default", self.store.get_profile(PROFILE)["profile"]["model"])

    def test_unresolved_model_and_trait_overflow_are_explicit(self):
        self.document["connections"][0]["default_model"] = ""
        self.write()
        current = self.store.get_profile(PROFILE)["profile"]
        self.assertEqual(dict(ok=False, reason_code="model_not_resolved"), current["validation"])
        self.assertCode("model_not_resolved", lambda: self.store.save_profile(str(uuid.uuid4()), self.draft(), 1))
        self.document["connections"][0]["default_model"] = "model-default"
        self.write()
        self.assertCode("traits_budget_exceeded", lambda: self.store.save_profile(str(uuid.uuid4()), {**self.draft(), "custom_traits": "中" * 400}, 1))
        self.assertEqual(1, self.store.get_profile(PROFILE)["profile"]["revision"])

    def test_protected_connection_name_secret_and_library_schema_rejected(self):
        draft = self.draft()
        for mutation, code in [({"connection_id": str(uuid.uuid4())}, "profile_connection_mismatch"),
                               ({"name": "伪装"}, "profile_name_mismatch"), ({"api_key": "PRIVATE"}, "unexpected_fields")]:
            self.assertCode(code, lambda: self.store.save_profile(str(uuid.uuid4()), {**draft, **mutation}, 1))
        self.document["connections"][0]["base_url"] = "https://x.invalid/v1?api_key=PRIVATE"
        self.write()
        self.assertCode("invalid_connection_endpoint", self.store.list_connections)
        self.library.write_text('{"schema_version":2,"schema_version":2}', encoding="utf-8")
        self.assertCode("duplicate_library_key", self.store.list_profiles)


if __name__ == "__main__":
    unittest.main()
