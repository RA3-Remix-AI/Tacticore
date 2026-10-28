"""Safety metadata remains current outside the immutable release."""
import json
from pathlib import Path
import tempfile
import unittest
from session_history import unknown_session

IDENT='7fe0470d-178d-45e0-b514-de66e11ef29e'
OTHER='11111111-1111-4111-8111-111111111111'


class SessionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.companion=self.root/'companion'
        (self.source/'production').mkdir(parents=True);self.companion.mkdir()
        self.history=self.source/'production/unknown_sessions.json';self.history.write_text(json.dumps({IDENT:{'reason':'unknown'}}))
        self.layout=self.companion/'companion-layout.json';self.layout.write_text(json.dumps(dict(schema_version=1,source_root=str(self.source))))
    def test_repo_and_companion_reject_same_known_unknown_session(self):
        self.assertTrue(unknown_session(IDENT,bridge_root=self.source))
        self.assertTrue(unknown_session(IDENT,bridge_root=self.companion))
        self.assertFalse(unknown_session(OTHER,bridge_root=self.companion))
    def test_updated_history_is_not_a_stale_packaged_copy(self):
        self.assertFalse(unknown_session(OTHER,bridge_root=self.companion))
        self.history.write_text(json.dumps({OTHER:{'reason':'new uncertainty'}}))
        self.assertTrue(unknown_session(OTHER,bridge_root=self.companion))
        self.assertFalse((self.companion/'production').exists())
    def test_missing_history_does_not_silently_allow_a_session(self):
        self.history.unlink()
        with self.assertRaisesRegex(RuntimeError,'session_history_unavailable'):unknown_session(OTHER,bridge_root=self.companion)
    def test_invalid_external_root_fails_closed(self):
        self.layout.write_text(json.dumps(dict(schema_version=1,source_root='relative')))
        with self.assertRaises(RuntimeError):unknown_session(OTHER,bridge_root=self.companion)
    def test_duplicate_or_malformed_history_fails_closed(self):
        for raw in ('[]','{"invalid":{}}',json.dumps({IDENT:{}})[:-1]+',"'+IDENT+'":{}}'):
            self.history.write_text(raw)
            with self.assertRaises(RuntimeError):unknown_session(OTHER,bridge_root=self.companion)


if __name__=='__main__':unittest.main()
