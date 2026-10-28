"""Current Host/desktop paths cannot resurrect historical unit control.

All game/provider edges are replaced explicitly. These checks grant no new
native strategy, construction, scouting or force-deployment capability.
"""
import asyncio
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import uuid

from battle_host import Host, parser
from host_runtime.contracts import ContractError
from host_runtime.desktop_backend import DesktopBackend, NativeChecks
from host_runtime.macro_control import CONTROL_MODE, UNIT_CONTROL_EVIDENCE


class MacroControlBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="tacticore-macro-control-")
        self.root = Path(self.tmp.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.commander = str(uuid.uuid4())

    def tearDown(self):
        self.tmp.cleanup()

    def construct(self):
        session = self.root / "session.json"
        session.write_text(json.dumps(dict(session_id=str(uuid.uuid4()),
                                         run_directory=str(self.root))), encoding="utf-8")
        args = parser().parse_args(["--session", str(session), "--commander", self.commander])
        profile = SimpleNamespace(commander_name="Macro test", connection_id=str(uuid.uuid4()))
        with patch("battle_host.load_profile", return_value=profile), \
             patch("battle_host.LiveBattleState", return_value=SimpleNamespace(owner=None)), \
             patch("battle_host.create_backend", return_value=SimpleNamespace(metrics={})), \
             patch("battle_host.own_process_identity", return_value=(1, "2026-10-27T00:00:00+00:00")), \
             patch("host_runtime.model_tasks.ModelRuntimeTasks", side_effect=AssertionError("micro scheduler created")):
            return Host(args)

    def test_actual_host_constructs_without_micro_scheduler_or_native_edge(self):
        host = self.construct()
        self.assertEqual(host.control_mode, CONTROL_MODE)
        for name in ("runtime_model_tasks", "runtime_tactical", "tactical", "reserve_controller"):
            self.assertIsNone(getattr(host, name))
        self.assertIn("original native AI", host.engine.provenance_description)
        # Publish through the actual Host status path, rather than checking a
        # policy string that a real Host might never consume.
        host.session.update(pid=1, start_time="test", mod_sha256="b"*64, registry_revision="test")
        host.publish()
        status = json.loads((host.output / "host-status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["execution"]["control_mode"], CONTROL_MODE)
        self.assertEqual(status["execution"]["unit_operation_policy"], "native_ai")
        self.assertNotIn("runtime_model_tasks", status)

    def test_old_evidence_is_rejected_before_session_profile_or_game_access(self):
        for field in UNIT_CONTROL_EVIDENCE:
            with self.subTest(field=field), patch("battle_host.load_profile") as profile:
                args = SimpleNamespace(session=MagicMock())
                setattr(args, field, self.root / "historical-proof.json")
                with self.assertRaisesRegex(ContractError, "macro_mode_rejects_unit_control_evidence"):
                    Host(args)
                args.session.read_text.assert_not_called()
                profile.assert_not_called()

    def test_real_macro_host_unit_entrypoints_refuse_but_empty_cleanup_is_allowed(self):
        host = self.construct()
        calls = [lambda: host.attach_runtime_actor("paid"),
                 lambda: host.reserve_runtime_task("task", "paid"),
                 lambda: host.commit_runtime_task("task", target_point_id="point"),
                 lambda: host.renew_runtime_tactical(), lambda: host.suspend_runtime_tactical(),
                 lambda: host.resume_runtime_tactical("paid")]
        with patch("host_runtime.host_tactical.from_host") as attach:
            for call in calls:
                with self.assertRaisesRegex(ContractError, "unit_control_disabled_in_macro_mode"):
                    call()
            attach.assert_not_called()
        asyncio.run(host.stop_runtime_tactical())
        self.assertIsNone(host.runtime_tactical)

    def test_desktop_readiness_refuses_old_evidence_before_live_observation(self):
        checks = NativeChecks.__new__(NativeChecks)
        with patch.object(NativeChecks, "_observe") as observe:
            with self.assertRaisesRegex(ContractError, "macro_mode_rejects_unit_control_evidence"):
                checks.check(SimpleNamespace(runtime_report=self.root / "old.json"), {}, None, None, None, None)
            observe.assert_not_called()

    def test_desktop_launch_rechecks_boundary_before_any_durable_dispatch(self):
        backend = DesktopBackend.__new__(DesktopBackend)
        backend.journal = MagicMock()
        with self.assertRaisesRegex(ContractError, "macro_mode_rejects_unit_control_evidence"):
            backend._dispatch_launch(None, None, None, None, None,
                                     SimpleNamespace(runtime_recovery_report="old"), None)
        self.assertEqual(backend.journal.mock_calls, [])

    def test_cli_has_no_legacy_mode_override(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser().parse_args(["--session", "unused", "--commander", self.commander,
                                 "--control-mode", "legacy_unit_control"])


if __name__ == "__main__":
    unittest.main()
