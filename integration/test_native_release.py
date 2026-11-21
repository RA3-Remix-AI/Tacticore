"""STOP and return: the short proof check, Host finish and desktop release read.

Artificial proofs and the real durable journal; no Game or native call.
"""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from host_runtime import native_lifecycle as lifecycle, native_release as release, native_runtime_contract
from host_runtime.contracts import ContractError, SessionBinding
from host_runtime.journal import CommandJournal
import test_native_journal as journal_fixture

SESSION = str(uuid.uuid4())
TICKS = 134376028671883531


def proof():
    """An independent-release proof as written by client.Probe.independent_release."""
    binding = dict(
        journal_fixture.binding(),
        pid=4321,
        start_low=TICKS & 0xFFFFFFFF,
        start_high=TICKS >> 32,
        session=list(uuid.UUID(SESSION).bytes),
    )
    sample = dict(
        source="bound_native_enemy_selector_v2",
        manual=0,
        isolated=0,
        enumeration_lock=0,
        enemy_mask=(1 << 0) | (1 << 7),
        alive_mask=(1 << 0) | (1 << 3) | (1 << 7),
        priority=[1 if player in (0, 7) else 0 for player in range(16)],
    )
    native = dict(
        magic=0x53434737,
        version=7,
        size=4736,
        binding=binding,
        phase=2,
        error=0,
        cleanup_verified=1,
        lease_held=0,
        hook_held=0,
        applied_mask=0,
        flag_deadline=0,
        journal_records=0,
        gates=[dict(phase=4), dict(phase=0)],
        focus=dict(phase=4),
    )
    return dict(
        native_release_verified=True, host_process_ended=True, host_returncode=0, native=native, enemy_focus=sample
    )


class Restored(unittest.TestCase):
    def check(self, value):
        return release.restored(value, pid=4321, ticks=TICKS, session_id=SESSION)

    def test_original_settings_back_on_the_actual_state(self):
        self.assertTrue(self.check(proof()))

    def test_each_field_that_matters_is_checked(self):
        mutations = (
            lambda p: p.update(native_release_verified=False),
            lambda p: p.update(host_returncode=1),
            lambda p: p.update(host_process_ended=False),
            lambda p: p["native"]["binding"].update(pid=1),
            lambda p: p["native"]["binding"].update(start_low=1),
            lambda p: p["native"].update(phase=1),
            lambda p: p["native"].update(lease_held=1),
            lambda p: p["native"].update(hook_held=1),
            lambda p: p["native"].update(applied_mask=4),
            lambda p: p["native"].update(cleanup_verified=0),
            lambda p: p["native"]["gates"][0].update(phase=1),
            lambda p: p["native"]["focus"].update(phase=1),
            lambda p: p["enemy_focus"].update(manual=1),
            lambda p: p["enemy_focus"]["priority"].__setitem__(7, 10),
            lambda p: p["native"].update(size=4672),
            lambda p: p.pop("enemy_focus"),
        )
        for index, mutate in enumerate(mutations):
            value = copy.deepcopy(proof())
            mutate(value)
            with self.subTest(index=index):
                self.assertFalse(self.check(value))

    def test_final_state_binds_proof_and_journal_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            value = proof()
            raw = json.dumps(value).encode()
            (folder / "independent-release.json").write_bytes(raw)
            (folder / "native-journal.bin").write_bytes(b"")
            binding = SimpleNamespace(session_id=SESSION, game_process_id=4321)
            final = dict(
                native_release_contract=release.KIND,
                cleanup_verified=True,
                session_id=SESSION,
                pid=4321,
                independent_release_sha256=hashlib.sha256(raw).hexdigest(),
                native_journal_sha256=hashlib.sha256(b"").hexdigest(),
            )
            session = dict(process_creation_filetime=TICKS)
            path = folder / "independent-release.json"
            self.assertTrue(release.verified_final(final, path, session, binding))
            self.assertFalse(
                release.verified_final(dict(final, independent_release_sha256="0" * 64), path, session, binding)
            )
            (folder / "native-journal.bin").write_bytes(b"x")
            self.assertFalse(release.verified_final(final, path, session, binding))

    def test_unowned_terminal_focus_must_agree_with_the_durable_journal(self):
        value = proof()
        value["enemy_focus"].update(alive_mask=1 << 3, own_player_id=3, automatic_scheme=2)
        value["native"]["focus"] = dict(
            phase=0, baseline_captured=0, call_reservations=0, selector=0, deadline_frame=0, deadline_ms=0
        )
        self.assertTrue(self.check(value))
        journal_binding = value["native"]["binding"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "independent-release.json"
            session = dict(process_creation_filetime=TICKS)
            binding = SimpleNamespace(session_id=SESSION, game_process_id=4321)
            final = dict(native_release_contract=release.KIND, cleanup_verified=True, session_id=SESSION, pid=4321)
            with patch.object(journal_fixture, "binding", return_value=journal_binding):
                unexpected_focus = journal_fixture.record(1, 10, 4)
            for raw, count, expected in ((b"", 0, True), (unexpected_focus, 1, False)):
                with self.subTest(expected=expected):
                    value["native"]["journal_records"] = count
                    evidence = json.dumps(value).encode()
                    path.write_bytes(evidence)
                    path.with_name("native-journal.bin").write_bytes(raw)
                    final.update(
                        independent_release_sha256=hashlib.sha256(evidence).hexdigest(),
                        native_journal_sha256=hashlib.sha256(raw).hexdigest(),
                    )
                    self.assertEqual(release.verified_final(final, path, session, binding), expected)


class HostFinish(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.journal = CommandJournal(self.folder / "ledger.sqlite3")
        self.addCleanup(self.journal.close)
        self.binding = SessionBinding(
            1, SESSION, 3, str(uuid.uuid4()), 4321, "2026-11-20T00:00:00+00:00", str(uuid.uuid4()), "c" * 64, "a" * 64
        )
        self.run = str(uuid.uuid4())
        self.journal.register_run(self.run, self.binding.public())
        self.report = self.folder / "report"
        self.report.mkdir()
        (self.report / "final-state.json").write_text(json.dumps(dict(independent_release_sha256="e" * 64)))
        self.stopped = []
        controller = SimpleNamespace(stop=lambda: self.stopped.append(True))
        self.host = SimpleNamespace(
            journal=self.journal,
            run_id=self.run,
            binding=self.binding,
            output=self.folder,
            host_pid=77,
            host_start_time="start",
            host_start="start",
            transport=SimpleNamespace(),
            controller=controller,
            session=dict(session_id=SESSION, process_creation_filetime=TICKS),
            strategy_runtime=None,
            latest=None,
        )
        patch.object(lifecycle, "report_directory", return_value=self.report).start()
        self.addCleanup(patch.stopall)
        patch.object(native_runtime_contract, "plain_local", lambda value, existing=True: Path(value)).start()

    def finish(self, verified):
        with patch.object(release, "verified_final", return_value=verified):
            lifecycle.finish(self.host)

    def uncertain_delivery(self):
        self.journal.reserve_command(self.run, "delivery", "macro_policy", dict(actions=["budgetarmy"]))
        self.journal.mark_dispatching(self.run, "delivery")
        self.journal.record_outcome(self.run, "delivery", "uncertain", dict(reason_code="unknown"))

    def test_verified_return_releases_the_stop_and_settles_earlier_unknown_delivery(self):
        self.uncertain_delivery()
        self.finish(True)
        stop = self.journal.get_command(self.run, "macro-stop")
        self.assertEqual(stop["status"], "released")
        self.assertTrue(self.stopped)
        status = dict(native_release_verified=True)
        backend = SimpleNamespace(journal=self.journal)
        row = dict(run_id=self.run, output_path=str(self.folder))
        self.assertEqual(lifecycle.unresolved_ownership(backend, row, status), [])
        receipt = dict(host_pid=77, host_start_time="start")
        self.assertTrue(lifecycle.verified_return(backend, row, self.binding, receipt))
        self.assertFalse(lifecycle.verified_return(backend, row, self.binding, dict(receipt, host_pid=78)))
        self.assertEqual(len(lifecycle.unresolved_ownership(backend, row, dict(native_release_verified=False))), 1)

    def test_unverified_return_stays_uncertain_and_never_claims_release(self):
        with self.assertRaisesRegex(ContractError, "macro_stop_unverified"):
            self.finish(False)
        self.assertEqual(self.journal.get_command(self.run, "macro-stop")["status"], "uncertain")
        backend = SimpleNamespace(journal=self.journal)
        row = dict(run_id=self.run, output_path=str(self.folder))
        receipt = dict(host_pid=77, host_start_time="start")
        self.assertFalse(lifecycle.verified_return(backend, row, self.binding, receipt))

    def test_a_second_stop_is_never_claimed(self):
        self.finish(True)
        with self.assertRaisesRegex(ContractError, "already_claimed"):
            self.finish(True)


class ArchivedHistory(unittest.TestCase):
    def test_desktop_reports_archived_launches_as_finished_history(self):
        from host_runtime.desktop_backend import DesktopBackend

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            backend = DesktopBackend(SimpleNamespace(state_dir=state))
            try:
                binding = SessionBinding(
                    1,
                    SESSION,
                    3,
                    str(uuid.uuid4()),
                    4321,
                    "2026-11-20T00:00:00+00:00",
                    str(uuid.uuid4()),
                    "c" * 64,
                    "a" * 64,
                )
                backend._db.execute(
                    "INSERT INTO launches (run_id,request_id,fingerprint,session_path,output_path,"
                    "binding_json,channel_hash) VALUES (?,?,?,?,?,?,?)",
                    (
                        "old-run",
                        "r",
                        "f",
                        str(state / "missing.json"),
                        str(state / "missing"),
                        json.dumps(binding.public()),
                        "h",
                    ),
                )
                row = backend._db.execute("SELECT * FROM launches WHERE run_id='old-run'").fetchone()
                (state / "history-archive.json").write_text(json.dumps(dict(archived_through_rowid=1)))
                status = backend._status(row)
                self.assertTrue(status["history_archived"])
                self.assertEqual(status["state"], "stopped")
                (state / "history-archive.json").write_text(json.dumps(dict(archived_through_rowid=0)))
                self.assertNotIn("history_archived", backend._status(row))
            finally:
                backend.close()


if __name__ == "__main__":
    unittest.main()
