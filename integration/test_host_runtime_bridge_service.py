"""Protocol checks exercise actual stdin loop, strict refusal and output bounds."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

from host_runtime.bridge_service import BridgeService, MAX_LINE_BYTES, decode_request, serve
from host_runtime.contracts import ContractError, canonical_json
from host_runtime.profile_store import ProfileStore
from test_host_runtime_profile_store import library, PROFILE


def request(operation, args=None, **changes):
    value = dict(schema_version=1, request_id=str(uuid.uuid4()), operation=operation, args=args or {})
    value.update(changes)
    return value


class Backend:
    def __init__(self):
        self.calls = []

    def run_check(self, profile, args, request_id):
        self.calls.append((profile, args, request_id))
        return dict(state="checked", session_id=PROFILE, ready_token="host-issued-token")

    def run_start(self, profile, args, request_id):
        self.calls.append((profile, args, request_id))
        return dict(state="starting", run_id=PROFILE)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "library.v2.json"
        self.library.write_text(json.dumps(library(), ensure_ascii=False), encoding="utf-8")
        self.store = ProfileStore(self.library, self.root / "state")
        self.service = BridgeService(self.store)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_native_list_save_envelope_and_no_implied_host_apply(self):
        call = request("profiles.list")
        result = self.service.handle(call)
        self.assertEqual(call["request_id"], result["request_id"])
        self.assertTrue(result["ok"])
        draft = result["result"]["profiles"][0]["draft"]
        saved = self.service.handle(request("profiles.save", dict(draft=draft, expected_revision=1)))
        self.assertTrue(saved["ok"])
        self.assertEqual("saved", saved["result"]["state"])
        self.assertFalse(saved["result"]["host_applied"])
        self.assertTrue(self.service.handle(request("connections.list"))["ok"])

    def test_default_backend_never_generates_success(self):
        args = {"session.inspect": {}, "run.check": dict(profile_id=PROFILE, profile_revision=1),
            "run.start": dict(profile_id=PROFILE, profile_revision=1, session_id=PROFILE, ready_token="x"),
            "run.status": dict(run_id=PROFILE), "run.stop": dict(run_id=PROFILE, session_id=PROFILE),
            "diagnostics.export": dict(run_id=PROFILE)}
        for operation, value in args.items():
            response = self.service.handle(request(operation, value))
            self.assertEqual(dict(code="adapter_unavailable"), response["error"])

    def test_backend_receives_current_revision_model_hash_and_ids_only(self):
        backend = Backend(); service = BridgeService(self.store, backend)
        check = request("run.check", dict(profile_id=PROFILE, profile_revision=1))
        result = service.handle(check)
        self.assertTrue(result["ok"])
        self.assertEqual("model-default", backend.calls[0][0]["effective"]["model"])
        start = request("run.start", dict(profile_id=PROFILE, profile_revision=1, session_id=PROFILE,
            ready_token=result["result"]["ready_token"], effective_hash=backend.calls[0][0]["effective"]["effective_hash"]))
        self.assertTrue(service.handle(start)["ok"])
        self.assertEqual(2, len(backend.calls))
        bad = request("run.check", dict(profile_id=PROFILE, profile_revision=1, effective_hash="0" * 64))
        self.assertEqual("effective_profile_changed", service.handle(bad)["error"]["code"])
        self.assertEqual(2, len(backend.calls))

    def test_unknown_fields_paths_processes_and_invalid_identity_refused(self):
        for call in [request("run.status", dict(run_id=PROFILE, path="C:/private")),
                     request("run.check", dict(profile_id=PROFILE, profile_revision=True)),
                     request("profiles.list", dict(command="powershell")), request("shell.run"),
                     request("profiles.get", dict(profile_id="demo")), request("profiles.list", schema_version=True)]:
            self.assertFalse(self.service.handle(call)["ok"])
        self.assertIsNone(self.service.handle(request("profiles.list", request_id="invalid"))["request_id"])

    def test_backend_sensitive_or_malformed_output_never_escapes(self):
        class Unsafe:
            def session_inspect(self, *_):
                return {"nested": {"api_key": "PRIVATE"}}
        class Malformed:
            def session_inspect(self, *_):
                raise ContractError("PRIVATE\nsecret")
        class Crash:
            def session_inspect(self, *_):
                raise RuntimeError("PRIVATE")
        for backend, code in [(Unsafe(), "backend_response_sensitive"), (Malformed(), "backend_error_invalid"), (Crash(), "bridge_operation_failed")]:
            result = BridgeService(self.store, backend).handle(request("session.inspect"))
            self.assertEqual(code, result["error"]["code"])
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_strict_decoder_and_oversize_drain_preserves_next_request(self):
        for raw, code in [(b'{"x":1,"x":2}', "duplicate_request_key"), (b'{"n":NaN}', "invalid_request_number"),
                          (b'\xff', "invalid_request_json")]:
            with self.assertRaises(ContractError) as caught:
                decode_request(raw)
            self.assertEqual(code, caught.exception.code)
        valid = request("connections.list")
        source = io.BytesIO(b"a" * (MAX_LINE_BYTES * 2) + b"\n" + canonical_json(valid).encode() + b"\n")
        target = io.BytesIO(); serve(self.service, source, target)
        results = [json.loads(line) for line in target.getvalue().splitlines()]
        self.assertEqual("request_too_large", results[0]["error"]["code"])
        self.assertEqual(valid["request_id"], results[1]["request_id"])
        self.assertTrue(results[1]["ok"])

    def test_actual_module_process_stays_alive_and_prints_only_json_lines(self):
        calls = [request("profiles.list"), request("connections.list"), request("run.status", dict(run_id=PROFILE)),
                 request("session.inspect")]
        proc = subprocess.run([sys.executable, "-m", "host_runtime.bridge_service", "--library", str(self.library),
            "--state-dir", str(self.root / "subprocess-state")], input="".join(canonical_json(v) + "\n" for v in calls).encode(),
            capture_output=True, cwd=Path(__file__).parent, timeout=15)
        self.assertEqual(0, proc.returncode, proc.stderr.decode())
        self.assertEqual(b"", proc.stderr)
        results = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(4, len(results))
        self.assertEqual([v["request_id"] for v in calls], [v["request_id"] for v in results])
        self.assertEqual("run_not_found", results[2]["error"]["code"])
        self.assertEqual(dict(session=None, reason_code="session_unavailable"), results[3]["result"])


if __name__ == "__main__":
    unittest.main()
