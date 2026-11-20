"""The installed runtime: one manifest hash, the build it pins, the session descriptor.

A synthetic runtime directory only; no Game, compiler or native call.
"""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from host_runtime import native_runtime as runtime, native_runtime_contract as contract
from host_runtime.contracts import ContractError


def local(value, *, existing=True):
    return Path(value)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Runtime(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.addCleanup(patch.stopall)
        for module in (runtime, contract):
            patch.object(module, "plain_local", local).start()
        for name, raw in {
            "python/python.exe": b"python",
            "app/integration/host_runtime/bridge_service.py": b"#",
            "app/integration/host_runtime/native_runtime.py": b"#",
            "qualification/registry.json": b"{}",
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        build = self.root / contract.BUILD_DIR
        build.mkdir(parents=True)
        for name in contract.ARTIFACTS:
            (build / name).write_bytes(name.encode())
        self.seal(field=True)
        patch.object(runtime, "runtime_root", side_effect=lambda: self.root).start()
        patch.object(runtime, "trusted_pin", side_effect=lambda: sha(self.root / "manifest.json")).start()

    def seal(self, *, field):
        build = self.root / contract.BUILD_DIR
        files = {
            p.relative_to(self.root).as_posix(): sha(p)
            for p in sorted(self.root.rglob("*"))
            if p.is_file() and p.name not in ("manifest.json", "build-manifest.json", "profile.h")
        }
        pins = contract.locked_inputs(dict(files=files))
        provenance = {"native.cpp": "b" * 64}
        (build / "profile.h").write_text(contract.profile(pins, provenance, field_candidate=field), encoding="ascii")
        manifest = dict(
            schema_version=1,
            kind=contract.FIELD_KIND if field else contract.KIND,
            protocol_version=contract.PROTOCOL,
            compile_only=not field,
            admission_ready=field,
            product_capability_granted=False,
            formal_games=0,
            game_sha256=contract.GAME_SHA,
            package_sha256=contract.PACKAGE_SHA,
            actions=list(contract.ACTIONS),
            flags=list(contract.FLAGS),
            input_pins=pins,
            build_source_pins=provenance,
            source_closure_sha256=contract.closure(pins, provenance, field_candidate=field),
            artifacts={name: sha(build / name) for name in contract.ARTIFACTS},
            layout={},
        )
        (build / "build-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        files = {
            p.relative_to(self.root).as_posix(): sha(p)
            for p in sorted(self.root.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        }
        value = dict(schema_version=1, python="python/python.exe", working_directory="app/integration", files=files)
        (self.root / "manifest.json").write_text(json.dumps(value), encoding="utf-8")

    def test_whole_runtime_is_verified_against_the_one_manifest_hash(self):
        root, pin, inventory, build = runtime.current()
        self.assertEqual(root, self.root)
        self.assertEqual(build["protocol_version"], 7)
        self.assertIn("app/integration/host_runtime/native_runtime.py", inventory["files"])

    def test_any_changed_extra_or_missing_file_fails_closed(self):
        changes = (
            lambda: (self.root / "app/integration/host_runtime/native_runtime.py").write_bytes(b"changed"),
            lambda: (self.root / "app/extra.py").write_bytes(b"extra"),
            lambda: (self.root / "python/python.exe").unlink(),
            lambda: (self.root / contract.BUILD_DIR / contract.ARTIFACTS[0]).write_bytes(b"other dll"),
        )
        for change in changes:
            with self.subTest(change=change):
                pin = sha(self.root / "manifest.json")
                change()
                with self.assertRaisesRegex(ContractError, "native_runtime_not_verified"):
                    runtime.verify_runtime(self.root, pin)
                self.setUp()

    def test_a_non_attachable_build_is_refused(self):
        self.seal(field=False)
        with self.assertRaisesRegex(ContractError, "native_runtime_not_verified"):
            runtime.current()

    def test_source_edits_need_no_hand_pins_only_a_new_seal(self):
        (self.root / "app/integration/host_runtime/native_runtime.py").write_bytes(b"# edited")
        self.seal(field=True)
        self.assertEqual(runtime.current()[0], self.root)

    def test_descriptor_points_at_this_runtime_only(self):
        path = self.root / "descriptor.json"
        runtime.create(path)
        descriptor, scope = runtime.load(path)
        self.assertEqual(scope.runtime_root, self.root)
        self.assertEqual(descriptor["build"], str(self.root / "native/strategic7"))
        with self.assertRaises(FileExistsError):
            runtime.create(path)
        for change in (
            dict(schema_version=15),
            dict(kind="native7_manifest_bound_trial"),
            dict(runtime_manifest_sha256="0" * 64),
            dict(runtime_root=str(self.root / "other")),
        ):
            value = dict(json.loads(path.read_text()), **change)
            path.write_text(json.dumps(value))
            with self.subTest(change=change), self.assertRaisesRegex(ContractError, "native_runtime_not_verified"):
                runtime.load(path)

    def test_attach_rechecks_the_pinned_build_cheaply(self):
        manifest = runtime.admitted_build(self.root / contract.BUILD_DIR)
        self.assertTrue(manifest["admission_ready"])
        (self.root / contract.BUILD_DIR / contract.ARTIFACTS[1]).write_bytes(b"other helper")
        with self.assertRaisesRegex(ContractError, "native_runtime_not_verified"):
            runtime.admitted_build(self.root / contract.BUILD_DIR)
        with self.assertRaisesRegex(ContractError, "native_runtime_not_verified"):
            runtime.admitted_build(self.root / "native/strategic6")


if __name__ == "__main__":
    unittest.main()
