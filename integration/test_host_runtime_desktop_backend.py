"""Offline launch-boundary checks. Fake admission cannot reach a native spawner."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from host_runtime.bridge_service import BridgeService
from host_runtime.contracts import ContractError, SessionBinding, content_hash
from host_runtime.desktop_backend import Admission, DesktopBackend, NativeChecks, NativeHostSpawner, SessionRegistration, READINESS_MS
from host_runtime.profile_store import ProfileStore
from test_host_runtime_profile_store import PROFILE, library

SESSION = "7233de3c-d636-471d-9fd1-33af63bdc566"
START = "2026-10-26T11:00:00+08:00"
HOST_START = "2026-10-26T04:00:00+00:00"


class Checks:
    test_only = True
    def __init__(self):
        self.calls = 0; self.changed = False; self.failure = None

    def inspect(self, registration, profile_id, state_dir):
        return dict(id=SESSION, map="Test", player_name=profile_id, faction="unknown")

    def check(self, registration, profile, host_id, state_dir, library_path, limits):
        self.calls += 1
        if self.failure:raise ContractError(self.failure)
        session = json.loads(registration.session_path.read_text())
        binding = SessionBinding(1, session["session_id"], 3, PROFILE, session["pid"], session["start_time"], host_id, "a" * 64, "b" * 64)
        fingerprint = content_hash(dict(binding=binding.public(), effective=profile["effective"]["effective_hash"],
                                        changed=self.changed, library_hash=profile["library_hash"]))
        return Admission(binding, fingerprint, self.inspect(registration, PROFILE, state_dir),
                         dict(supported_units=["conscript"], supported_foci=["infantry"], tactics_supported=False), True)


class Spawner:
    test_only = True
    def __init__(self):
        self.commands = []; self.failure = False; self.alive = True
    def spawn(self, command, log_path, admission):
        self.commands.append(command)
        if self.failure:raise OSError("PRIVATE")
        return types.SimpleNamespace(pid=220, poll=lambda: None if self.alive else 0)
    def identity(self, pid):
        return HOST_START if self.alive and pid == 220 else None


class DesktopBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.lib = self.root / "library.v2.json"; self.lib.write_text(json.dumps(library()), encoding="utf-8")
        self.run = self.root / "acceptance" / "new-run"; self.run.mkdir(parents=True)
        self.session = self.run / "session.json"
        self.session.write_text(json.dumps(dict(session_id=SESSION, pid=101, start_time=START,
            run_directory=str(self.run), scenario=dict(commander_id=PROFILE, computer_player_index=3))))
        self.report = self.run / "report.json"; self.report.write_text("{}")
        self.persistent = self.run / "persistent-status.json"; self.persistent.write_text("{}")
        self.store = ProfileStore(self.lib, self.root / "state")
        self.checks = Checks(); self.spawner = Spawner(); self.now = 100_000
        self.backend = self.new_backend()
        self.backend.register_session(self.session, self.report, self.persistent)
        self.profile = self.store.get_profile(PROFILE)["profile"]

    def new_backend(self, **changes):
        return DesktopBackend(self.store, checks=changes.get("checks", self.checks), spawner=changes.get("spawner", self.spawner),
                              now_ms=lambda: self.now, registration_root=self.root / "acceptance", caller_alive=lambda: True)

    def tearDown(self):
        self.backend.close(); self.store.close(); self.temp.cleanup()

    def assertCode(self, code, call):
        with self.assertRaises(ContractError) as caught:call()
        self.assertEqual(code, caught.exception.code)

    def ready(self):
        return self.backend.run_check(self.profile, {}, str(uuid.uuid4()))

    def start_args(self, ready):
        return dict(profile_id=PROFILE, profile_revision=self.profile["revision"], session_id=SESSION, ready_token=ready["ready_token"])

    def start(self):
        ready = self.ready(); request_id = str(uuid.uuid4()); args = self.start_args(ready)
        return self.backend.run_start(self.profile, args, request_id), request_id, args

    def status_file(self, result, **changes):
        row = self.backend._launch(result["run_id"])
        binding = SessionBinding.from_dict(json.loads(row["binding_json"]))
        output = self.run / "battle-host"; output.mkdir(exist_ok=True)
        status = dict(session_id=SESSION, pid=101, process_start=START, host_pid=220, host_start_time=HOST_START,
            state="running", runtime_production=dict(run_id=result["run_id"], binding_hash=binding.binding_hash),
            profile_application=dict(state="host_profile_applied", profile_id=PROFILE, profile_revision=self.profile["revision"],
                                     effective_hash=self.profile["effective"]["effective_hash"]),
            profile_consumption=dict(profile_id=PROFILE, profile_revision=self.profile["revision"], effective_hash=self.profile["effective"]["effective_hash"],
                                     calls_started=0, responses_returned=0, model_response_received=False), jobs=[], metrics={})
        status.update(changes)
        (output / "host-status.json").write_text(json.dumps(status))

    def test_registration_is_persistent_hashed_and_never_latest_directory_guess(self):
        self.assertEqual(SESSION, self.backend.session_inspect({}, str(uuid.uuid4()))["session"]["id"])
        self.backend.close(); self.backend = self.new_backend()
        self.assertTrue(self.ready()["ready"])
        self.report.write_text('{"changed":true}')
        result = self.ready()
        self.assertFalse(result["ready"]); self.assertEqual("session_unavailable", result["reason_code"])
        (self.store.state_dir / "session-registration.json").unlink()
        self.assertIsNone(self.backend.session_inspect({}, str(uuid.uuid4()))["session"])
        outside = self.root / "outside.json"; outside.write_text("{}")
        self.assertCode("session_unavailable", lambda: self.backend.register_session(self.session, outside, self.persistent))

    def test_check_ttl_profile_binding_and_second_live_admission(self):
        ready = self.ready(); self.assertTrue(ready["ready"])
        self.assertEqual(self.now + READINESS_MS, ready["expires_at"])
        self.checks.changed = True
        self.assertCode("session_changed", lambda: self.backend.run_start(self.profile, self.start_args(ready), str(uuid.uuid4())))
        self.assertEqual(0, len(self.spawner.commands)); self.checks.changed = False
        ready = self.ready(); self.now += READINESS_MS
        self.assertCode("readiness_expired", lambda: self.backend.run_start(self.profile, self.start_args(ready), str(uuid.uuid4())))
        self.assertEqual(0, len(self.spawner.commands))

    def test_default_backend_missing_registration_refuses_without_game_or_secret_access(self):
        self.backend.close()
        (self.store.state_dir / "session-registration.json").unlink()
        self.backend = DesktopBackend(self.store)
        with patch("host_runtime.desktop_backend._module", side_effect=AssertionError("must not touch Win32/model/credentials")):
            self.assertIsNone(self.backend.session_inspect({}, str(uuid.uuid4()))["session"])
            ready = self.ready()
            self.assertFalse(ready["ready"])
            self.assertEqual("session_unavailable", ready["reason_code"])
        self.assertFalse(self.backend.ledger_path.read_bytes().find(b"PRIVATE") >= 0)

    def test_failed_live_or_credential_admission_never_issues_token(self):
        for reason in ("session_mismatch", "capability_unavailable", "credentials_unavailable", "run_already_active"):
            self.checks.failure = reason
            result = self.ready()
            self.assertFalse(result["ready"])
            self.assertIsNone(result["ready_token"])
            self.assertEqual(reason, result["reason_code"])
        self.assertEqual(0, len(self.spawner.commands))

    def test_model_or_revision_change_invalidates_existing_ready_token(self):
        ready = self.ready(); args = self.start_args(ready)
        draft = dict(self.profile["draft"], model="changed-model")
        self.profile = self.store.save_profile(str(uuid.uuid4()), draft, 1)["profile"]
        args["profile_revision"] = 2
        self.assertCode("session_changed", lambda: self.backend.run_start(self.profile, args, str(uuid.uuid4())))
        self.assertEqual(0, len(self.spawner.commands))

    def test_dispatch_gate_rechecks_ttl_revision_and_native_parent_after_slow_admission(self):
        for mutation, code in [("timeout", "readiness_expired"), ("revision", "effective_profile_changed"), ("parent", "adapter_unavailable")]:
            with self.subTest(mutation=mutation):
                ready = self.ready(); args = self.start_args(ready)
                original_check = self.checks.check
                def delayed(*values):
                    admission = original_check(*values)
                    if mutation == "timeout":self.now += READINESS_MS
                    elif mutation == "revision":self.store.save_profile(str(uuid.uuid4()), self.profile["draft"], self.profile["revision"])
                    else:self.backend.caller_alive = lambda: False
                    return admission
                with patch.object(self.checks, "check", delayed):
                    self.assertCode(code, lambda: self.backend.run_start(self.profile, args, str(uuid.uuid4())))
                self.profile = self.store.get_profile(PROFILE)["profile"]
                self.backend.caller_alive = lambda: True
        self.assertEqual(0, len(self.spawner.commands))

    def test_unparameterized_native_scope_rejects_other_player_before_win32(self):
        value = json.loads(self.session.read_text()); value["scenario"]["computer_player_index"] = 5
        self.session.write_text(json.dumps(value))
        registration = SessionRegistration.trusted(self.session, self.report, self.persistent, root=self.root / "acceptance")
        with patch("host_runtime.desktop_backend._module", side_effect=AssertionError("scope rejection must precede native access")):
            self.assertCode("legacy_executor_player_unsupported", lambda: NativeChecks().inspect(registration, PROFILE, self.store.state_dir))

    def test_start_run_id_equals_request_and_one_launch_survives_lost_response_reopen(self):
        result, request_id, args = self.start()
        self.assertEqual(request_id, result["run_id"]); self.assertEqual("starting", result["state"])
        self.assertEqual(1, len(self.spawner.commands)); command = self.spawner.commands[0]
        self.assertIn("--runtime-ledger", command)
        self.assertEqual(command[command.index("--control-mode")+1],"macro_native")
        self.assertEqual(request_id, command[command.index("--runtime-run-id") + 1])
        self.assertNotIn("--tactical-evidence", command)
        self.assertNotIn("PRIVATE", json.dumps(command))
        self.backend.close(); self.backend = self.new_backend()
        self.assertEqual(request_id, self.backend.run_status(dict(run_id=request_id), str(uuid.uuid4()))["run_id"])
        self.assertEqual("starting", self.backend.run_start(self.profile, args, request_id)["state"])
        self.assertEqual(1, len(self.spawner.commands))
        self.assertCode("request_id_conflict", lambda: self.backend.run_start(self.profile, {**args, "ready_token": "different"}, request_id))
        self.assertFalse(self.ready()["ready"])

    def test_unknown_spawn_never_retries_even_after_restart(self):
        self.spawner.failure = True; ready = self.ready(); args = self.start_args(ready); request_id = str(uuid.uuid4())
        self.assertCode("run_state_conflict", lambda: self.backend.run_start(self.profile, args, request_id))
        self.assertEqual("uncertain", self.backend.journal.get_command(request_id, request_id)["status"])
        self.backend.close(); self.backend = self.new_backend(); self.spawner.failure = False
        self.assertEqual("uncertain", self.backend.run_start(self.profile, args, request_id)["state"])
        self.assertFalse(self.backend._cancel_reserved_launch(self.backend._launch(request_id),'test_cancel'))
        self.assertEqual(1, len(self.spawner.commands))

    def test_failure_before_dispatch_is_cancelled_and_never_resumed(self):
        ready = self.ready(); args = self.start_args(ready); request_id = str(uuid.uuid4())
        with patch("host_runtime.desktop_backend._atomic", side_effect=OSError("disk failure")):
            result=self.backend.run_start(self.profile,args,request_id)
        self.assertEqual('stopped',result['state']);self.assertTrue(result['no_native_execution_started'])
        self.assertEqual("cancelled", self.backend.journal.get_command(request_id, request_id)["status"])
        self.assertEqual("stopped", self.backend.run_start(self.profile, args, request_id)["state"])
        self.assertFalse(self.ready()["ready"])
        self.assertEqual(0, len(self.spawner.commands))

    def test_orphaned_reserved_launch_can_be_cancelled_but_dispatching_cannot(self):
        ready=self.ready();args=self.start_args(ready);request_id=str(uuid.uuid4())
        with patch.object(self.backend,'_cancel_reserved_launch',return_value=False), \
                patch('host_runtime.desktop_backend._atomic',side_effect=OSError('disk failure')):
            self.assertCode('run_state_conflict',lambda:self.backend.run_start(self.profile,args,request_id))
        result=self.backend.run_stop(dict(run_id=request_id,session_id=args['session_id']),str(uuid.uuid4()))
        self.assertTrue(result['no_native_execution_started']);self.assertEqual(0,len(self.spawner.commands))

    def test_expiry_after_reservation_records_known_no_delivery_with_reason(self):
        ready=self.ready();args=self.start_args(ready);request_id=str(uuid.uuid4())
        with patch.object(self.backend,'_predispatch',side_effect=[None,ContractError('readiness_expired')]):
            result=self.backend.run_start(self.profile,args,request_id)
        self.assertEqual(result['state'],'stopped');self.assertTrue(result['no_native_execution_started'])
        command=self.backend.journal.get_command(request_id,request_id)
        self.assertEqual(command['receipt']['preparation_reason_code'],'readiness_expired')
        self.assertEqual(0,len(self.spawner.commands));self.assertEqual([],self.backend.journal.unresolved(request_id))

    def test_two_backend_process_indexes_cannot_launch_same_session_twice(self):
        ready = self.ready(); args = self.start_args(ready); other = self.new_backend()
        def start(backend):
            try:return backend.run_start(self.profile, args, str(uuid.uuid4()))["state"]
            except ContractError as error:return error.code
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(start, [self.backend, other]))
            self.assertEqual(1, len(self.spawner.commands))
            self.assertEqual(1, outcomes.count("starting"))
        finally:other.close()

    def test_test_admission_cannot_use_default_real_spawner(self):
        self.backend.close(); self.backend = self.new_backend(spawner=NativeHostSpawner())
        ready = self.ready(); args = self.start_args(ready); request_id = str(uuid.uuid4())
        self.assertCode("run_state_conflict", lambda: self.backend.run_start(self.profile, args, request_id))
        self.assertEqual("uncertain", self.backend.journal.get_command(request_id, request_id)["status"])

    def test_status_only_accepts_same_runtime_host_process_identity_and_actual_receipts(self):
        result, request_id, _ = self.start(); self.status_file(result)
        status = self.backend.run_status(dict(run_id=request_id), str(uuid.uuid4()))
        self.assertEqual("running", status["state"])
        self.assertEqual("host_profile_applied", status["profile_application"]["state"])
        self.assertFalse(status["profile_consumption"]["model_response_received"])
        self.status_file(result, host_start_time="2000-01-01T00:00:00+00:00")
        self.assertNotEqual("running", self.backend.run_status(dict(run_id=request_id), str(uuid.uuid4()))["state"])
        self.status_file(result); self.spawner.alive = False
        self.assertEqual("uncertain", self.backend.run_status(dict(run_id=request_id), str(uuid.uuid4()))["state"])
        self.status_file(result, state="stopped")
        self.assertEqual("stopped", self.backend.run_status(dict(run_id=request_id), str(uuid.uuid4()))["state"])
        self.assertEqual("completed", self.backend.journal.get_command(request_id, request_id)["status"])
        self.assertEqual("stopped", self.backend.run_status(dict(run_id=request_id), str(uuid.uuid4()))["state"])

    def test_old_profile_consumption_receipt_cannot_be_projected_to_new_run(self):
        result, run_id, _ = self.start()
        stale = dict(profile_id=PROFILE, profile_revision=0, effective_hash="0" * 64,
                     state="host_profile_applied", calls_started=1, responses_returned=1, model_response_received=True)
        self.status_file(result, profile_application=stale, profile_consumption=stale)
        status = self.backend.run_status(dict(run_id=run_id), str(uuid.uuid4()))
        self.assertEqual("fault", status["state"])
        self.assertEqual("effective_profile_changed", status["reason_code"])
        self.assertNotIn("profile_application", status)
        self.assertNotIn("profile_consumption", status)

    def test_ended_host_needs_journal_native_release_not_status_boolean(self):
        result,run_id,_ = self.start();self.spawner.alive=False
        self.status_file(result,state='stopped',native_release_verified=True)
        status=self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))
        self.assertFalse(status['native_release_verified'])
        request=str(uuid.uuid4())
        self.backend.journal.reserve_command(run_id,request,'stop',dict(scope='production'))
        self.backend.journal.mark_dispatching(run_id,request)
        self.backend.journal.record_outcome(run_id,request,'released',dict(reason_code='native_receipt_verified',facts=dict(
            source='native_persistent_production',production_release_verified=True,native_phase=2,native_error=0,restore_mask=31,active_callbacks=0)))
        self.assertTrue(self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))['native_release_verified'])

    def test_independent_unattached_review_is_bound_to_the_exact_host(self):
        result,run_id,_ = self.start();self.spawner.alive=False;self.status_file(result,state='fault')
        self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))
        row=self.backend._launch(run_id);binding=SessionBinding.from_dict(json.loads(row['binding_json']))
        request=str(uuid.uuid4());self.backend.journal.reserve_command(run_id,request,'review_host_release',dict(binding_hash=binding.binding_hash))
        self.backend.journal.mark_dispatching(run_id,request)
        self.backend.journal.record_outcome(run_id,request,'released',dict(
            reason_code='unattached_host_native_entries_independently_verified',native_release_verified=True,
            binding_hash=binding.binding_hash,host_pid=220,host_start_time='wrong-host',review_sha256='a'*64))
        self.assertFalse(self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))['native_release_verified'])

    def test_stop_is_bound_request_only_and_diagnostics_contains_no_paths(self):
        result, run_id, _ = self.start(); self.status_file(result)
        self.assertCode("session_mismatch", lambda: self.backend.run_stop(dict(run_id=run_id, session_id=str(uuid.uuid4())), str(uuid.uuid4())))
        request_id = str(uuid.uuid4()); args = dict(run_id=run_id, session_id=SESSION)
        self.backend.run_stop(args, request_id); self.backend.run_stop(args, request_id)
        stop = json.loads((self.run / "battle-host" / "stop.json").read_text())
        self.assertEqual(dict(session_id=SESSION), stop)
        self.assertFalse(self.backend.journal.get_command(run_id, request_id)["receipt"]["native_release_verified"])
        diagnostics = self.backend.diagnostics_export(dict(run_id=run_id), str(uuid.uuid4()))
        self.assertNotIn(str(self.root), json.dumps(diagnostics))
        self.assertNotIn("ready_token", json.dumps(diagnostics))

    def test_bridge_exact_shapes_and_no_claimed_model_on_check_start(self):
        service = BridgeService(self.store, self.backend)
        def rpc(operation, args=None, request_id=None):
            return service.handle(dict(schema_version=1, request_id=request_id or str(uuid.uuid4()), operation=operation, args=args or {}))
        inspected = rpc("session.inspect"); self.assertTrue(inspected["ok"])
        ready = rpc("run.check", dict(profile_id=PROFILE, profile_revision=1))["result"]
        run_id = str(uuid.uuid4()); launched = rpc("run.start", self.start_args(ready), run_id)
        self.assertTrue(launched["ok"]); self.assertEqual(run_id, launched["result"]["run_id"])
        self.assertNotIn("profile_application", launched["result"])
        self.assertTrue(rpc("diagnostics.export", dict(run_id=run_id))["ok"])


if __name__ == "__main__":unittest.main()
