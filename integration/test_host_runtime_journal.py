"""Real SQLite crash-boundary and concurrency checks; no game/model access."""
import concurrent.futures
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from host_runtime.journal import CommandJournal, IdentityConflict, JournalError, RequestConflict, TransitionError


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "journal.sqlite"
        self.journal = CommandJournal(self.path)
        self.binding = {"session_id": "session-a", "player_id": 3, "host_identity": {"pid": 100, "start_time": "one"}}
        self.journal.register_run("run-a", self.binding)

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def reserve(self, request="request-a"):
        return self.journal.reserve_command("run-a", request, "mission.start", {"actor_id": 4, "lease_id": "lease-a"})

    def test_duplicate_request_cannot_claim_a_second_dispatch(self):
        first = self.reserve()
        again = self.reserve()
        self.assertTrue(first["created"])
        self.assertFalse(again["created"])
        self.assertEqual(first["command_id"], again["command_id"])
        self.journal.mark_dispatching("run-a", "request-a")
        with self.assertRaises(TransitionError):
            self.journal.mark_dispatching("run-a", "request-a")

    def test_recent_projection_updates_after_first_page_and_reports_truncation(self):
        self.journal.register_run('other-run', self.binding)
        for index in range(35):
            self.journal.append_event('run-a', 'observation', {'index': index})
            self.journal.append_event('other-run', 'other', {'index': index})
        page = self.journal.latest_events('run-a', limit=3)
        self.assertEqual([32,33,34], [event['payload']['index'] for event in page['events']])
        self.assertEqual(36, page['total_count'])  # Includes the durable run_registered event.
        self.assertTrue(page['truncated'])
        self.assertEqual(page['events'][0]['seq'], page['first_seq'])
        self.assertEqual(page['events'][-1]['seq'], page['last_seq'])
        self.journal.append_event('run-a', 'observation', {'index': 35})
        self.assertEqual([33,34,35], [event['payload']['index'] for event in self.journal.latest_events('run-a', limit=3)['events']])
        with self.assertRaises(JournalError):
            self.journal.latest_events('run-a', limit=True)

    def test_request_content_and_run_binding_are_immutable(self):
        self.reserve()
        with self.assertRaises(RequestConflict):
            self.journal.reserve_command("run-a", "request-a", "mission.stop", {"actor_id": 4})
        self.journal.register_run("run-a", dict(reversed(list(self.binding.items()))))
        with self.assertRaises(IdentityConflict):
            self.journal.register_run("run-a", {**self.binding, "player_id": 4})

    def test_crash_after_intent_is_uncertain_after_reopen(self):
        self.reserve()
        self.journal.mark_dispatching("run-a", "request-a")
        self.journal.close()
        self.journal = CommandJournal(self.path)
        recovered = self.journal.reconcile_interrupted("run-a")
        self.assertEqual([r["status"] for r in recovered], ["uncertain"])
        self.assertEqual(self.reserve()["status"], "uncertain")
        with self.assertRaises(TransitionError):
            self.journal.mark_dispatching("run-a", "request-a")
        with self.assertRaises(TransitionError):
            self.journal.record_outcome("run-a", "request-a", "completed", {"ok": True})
        row = self.journal.resolve_uncertain("run-a", "request-a", "released", {"control_released": True, "effect_verified": False}, evidence_id="evidence-1")
        self.assertEqual(row["status"], "released")
        self.assertFalse(row["receipt"]["effect_verified"])

    def test_accepted_crash_preserves_prior_receipt(self):
        self.reserve()
        self.journal.mark_dispatching("run-a", "request-a")
        self.journal.record_outcome("run-a", "request-a", "accepted", {"native_seq": 7})
        result = self.journal.reconcile_interrupted("run-a")[0]
        self.assertEqual(result["receipt"]["previous_receipt"], {"native_seq": 7})
        self.assertEqual(self.journal.reconcile_interrupted("run-a"), [])

    def test_terminal_result_is_idempotent_but_cannot_be_rewritten(self):
        self.reserve()
        self.journal.mark_dispatching("run-a", "request-a")
        receipt = {"reason_code": "target_lost"}
        self.journal.record_outcome("run-a", "request-a", "failed", receipt)
        before = len(self.journal.events("run-a"))
        self.journal.record_outcome("run-a", "request-a", "failed", receipt)
        self.assertEqual(len(self.journal.events("run-a")), before)
        with self.assertRaises(TransitionError):
            self.journal.record_outcome("run-a", "request-a", "completed", {"ok": True})
        self.assertEqual(self.journal.unresolved("run-a"), [])

    def test_two_connections_race_for_one_request_and_one_dispatch(self):
        other = CommandJournal(self.path)
        try:
            def claim(journal):
                row = journal.reserve_command("run-a", "race", "production.start", {"unit": "conscript"})
                try:
                    journal.mark_dispatching("run-a", "race")
                    return row["command_id"], True
                except TransitionError:
                    return row["command_id"], False
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(claim, journal) for journal in (self.journal, other)]
                result = [future.result() for future in futures]
            self.assertEqual(len({row[0] for row in result}), 1)
            self.assertEqual(sum(row[1] for row in result), 1)
        finally:
            other.close()

    def test_event_cannot_attach_a_command_from_another_run(self):
        row = self.reserve()
        self.journal.register_run("run-b", {**self.binding, "session_id": "session-b"})
        with self.assertRaises(IdentityConflict):
            self.journal.append_event("run-b", "effect", {}, command_id=row["command_id"])
        event = self.journal.append_event("run-a", "effect", {"effect_verified": False}, command_id=row["command_id"], game_frame=7, monotonic_ns=9)
        self.assertEqual(self.journal.events("run-a", after=event["seq"]), [])

    def test_named_credentials_and_invalid_numbers_never_reach_disk(self):
        for payload in ({"connection": {"apiKey": "never-store-this"}}, {"profile": {"key": "never-store-this"}}, {"connection": {"api_token": "never-store-this"}}, {"hp": float("nan")}, {"x": "x" * 70000}):
            with self.assertRaises(JournalError):
                self.journal.append_event("run-a", "invalid", payload)
        self.assertNotIn("never-store-this", json.dumps(self.journal.events("run-a")))
        with self.assertRaises(JournalError):
            self.journal.append_event("run-a", "invalid", {}, game_frame=True)

    def test_intent_and_event_transaction_roll_back_together(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER fail_intent BEFORE INSERT ON events WHEN NEW.event_type='command_reserved' BEGIN SELECT RAISE(ABORT,'injected'); END")
            db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.reserve()
        self.assertEqual(self.journal.unresolved("run-a"), [])
        self.assertEqual([e["event_type"] for e in self.journal.events("run-a")], ["run_registered"])

    def test_abrupt_process_exit_leaves_durable_intent_without_redispatch(self):
        program = """import os,sys
from host_runtime.journal import CommandJournal
j=CommandJournal(sys.argv[1])
j.reserve_command('run-a','abrupt','mission.start',{'actor_id':9})
j.mark_dispatching('run-a','abrupt')
os._exit(17)
"""
        result = subprocess.run([sys.executable, "-c", program, str(self.path)], cwd=Path(__file__).resolve().parent, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 17, result.stderr.decode(errors="replace"))
        self.assertEqual(self.journal.get_command("run-a", "abrupt")["status"], "dispatching")
        recovered = self.journal.reconcile_interrupted("run-a")
        self.assertEqual(recovered[0]["status"], "uncertain")
        with self.assertRaises(TransitionError):
            self.journal.mark_dispatching("run-a", "abrupt")


if __name__ == "__main__":
    unittest.main()
