"""Durable command intents and audit events, never a game-command dispatcher.

Domain contracts validate identities and native evidence before calling this
module. A database transaction cannot make an external game action exactly-once:
persist intent, claim dispatch once, and reconcile uncertain delivery separately.
JSON exports are projections of this ledger, not competing sources of truth.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import uuid
from collections.abc import Mapping


class JournalError(ValueError):
    pass


class IdentityConflict(JournalError):
    pass


class RequestConflict(JournalError):
    pass


class TransitionError(JournalError):
    pass


_SECRET_KEYS = {
    "key", "apikey", "apitoken", "authorization", "password", "secret",
    "clientsecret", "secretkey", "token", "accesstoken", "refreshtoken",
    "privatekey", "credentialvalue", "credentials", "connectionstring",
}
_TRANSITIONS = {
    "reserved": {"rejected", "cancelled"},
    "dispatching": {"accepted", "started", "completed", "released", "rejected", "failed", "uncertain"},
    "accepted": {"started", "completed", "released", "failed", "uncertain", "cancelled"},
    "started": {"completed", "released", "failed", "uncertain"},
    "completed": {"released"},
    "released": set(), "rejected": set(), "failed": set(), "cancelled": set(),
    "uncertain": set(),
}
_UNRESOLVED = ("reserved", "dispatching", "accepted", "started", "uncertain")


def _identifier(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ord(c) < 32 for c in value):
        raise JournalError("invalid_" + label)
    return value


def _json(value):
    """Bound diagnostic size and reject named credentials before persistence."""
    count = 0

    def visit(item, depth=0):
        nonlocal count
        count += 1
        if count > 4096 or depth > 12:
            raise JournalError("payload_too_complex")
        if isinstance(item, Mapping):
            if len(item) > 128:
                raise JournalError("payload_too_complex")
            result = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    raise JournalError("invalid_payload_key")
                normalized = "".join(c.lower() for c in key if c.isalnum())
                if normalized in _SECRET_KEYS:
                    raise JournalError("credential_field_forbidden")
                result[key] = visit(child, depth + 1)
            return result
        if isinstance(item, (list, tuple)):
            if len(item) > 256:
                raise JournalError("payload_too_complex")
            return [visit(child, depth + 1) for child in item]
        if item is None or type(item) in (str, int, float, bool):
            return item
        raise JournalError("invalid_payload_value")

    try:
        text = json.dumps(visit(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        if isinstance(error, JournalError):
            raise
        raise JournalError("invalid_payload") from None
    if len(text.encode("utf-8")) > 65536:
        raise JournalError("payload_too_large")
    return text


def _object(value):
    if not isinstance(value, Mapping):
        raise JournalError("payload_must_be_object")
    return _json(value)


def _utc():
    return datetime.now(timezone.utc).isoformat()


class CommandJournal:
    def __init__(self, path: str | Path):
        self._lock = threading.RLock()
        self._closed = False
        self._db = sqlite3.connect(str(path), timeout=5, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        try:
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise JournalError("unsupported_journal_version")
            with self._transaction():
                self._db.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, binding TEXT NOT NULL, created_at TEXT NOT NULL)")
                self._db.execute("""CREATE TABLE IF NOT EXISTS commands (
                    command_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
                    request_id TEXT NOT NULL, operation TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    payload TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(run_id, request_id))""")
                self._db.execute("""CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(run_id), event_type TEXT NOT NULL,
                    command_id TEXT REFERENCES commands(command_id), payload TEXT NOT NULL,
                    game_frame INTEGER, monotonic_ns INTEGER, created_at TEXT NOT NULL)""")
                self._db.execute("CREATE INDEX IF NOT EXISTS events_by_run ON events(run_id, seq)")
                self._db.execute("""CREATE TABLE IF NOT EXISTS native_sequences (
                    command_id TEXT PRIMARY KEY REFERENCES commands(command_id),
                    run_id TEXT NOT NULL REFERENCES runs(run_id), channel_hash TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK(sequence BETWEEN 1 AND 4294967295),
                    UNIQUE(channel_hash, sequence))""")
                self._db.execute("PRAGMA user_version=1")
        except BaseException:
            self._db.close()
            self._closed = True
            raise

    @contextmanager
    def _transaction(self):
        with self._lock:
            if self._closed:
                raise JournalError("journal_closed")
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def _run(self, run_id):
        _identifier(run_id, "run_id")
        row = self._db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise JournalError("unknown_run")
        return row

    def _command(self, run_id, request_id):
        self._run(run_id)
        _identifier(request_id, "request_id")
        row = self._db.execute("SELECT * FROM commands WHERE run_id=? AND request_id=?", (run_id, request_id)).fetchone()
        if row is None:
            raise JournalError("unknown_command")
        return row

    @staticmethod
    def _public(row):
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        result["receipt"] = json.loads(result["receipt"]) if result["receipt"] is not None else None
        return result

    def _event(self, run_id, kind, payload, command_id=None, game_frame=None, monotonic_ns=None):
        self._db.execute(
            "INSERT INTO events(run_id,event_type,command_id,payload,game_frame,monotonic_ns,created_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, kind, command_id, payload, game_frame, monotonic_ns, _utc()),
        )
        return self._db.execute("SELECT last_insert_rowid()").fetchone()[0]

    def register_run(self, run_id: str, binding: Mapping) -> None:
        _identifier(run_id, "run_id")
        if not binding:
            raise JournalError("empty_binding")
        encoded = _object(binding)
        with self._transaction():
            prior = self._db.execute("SELECT binding FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if prior:
                if prior[0] != encoded:
                    raise IdentityConflict("immutable_run_binding_changed")
                return
            self._db.execute("INSERT INTO runs VALUES (?,?,?)", (run_id, encoded, _utc()))
            self._event(run_id, "run_registered", encoded)

    def reserve_command(self, run_id, request_id, operation, payload: Mapping) -> dict:
        _identifier(request_id, "request_id")
        _identifier(operation, "operation")
        encoded = _object(payload)
        fingerprint = hashlib.sha256(_json({"operation": operation, "payload": json.loads(encoded)}).encode("utf-8")).hexdigest()
        with self._transaction():
            self._run(run_id)
            prior = self._db.execute("SELECT * FROM commands WHERE run_id=? AND request_id=?", (run_id, request_id)).fetchone()
            if prior:
                if prior["fingerprint"] != fingerprint:
                    raise RequestConflict("request_id_content_conflict")
                return {**self._public(prior), "created": False}
            ident, now = str(uuid.uuid4()), _utc()
            self._db.execute("INSERT INTO commands VALUES (?,?,?,?,?,?,?,?,?,?)", (ident, run_id, request_id, operation, fingerprint, encoded, "reserved", None, now, now))
            self._event(run_id, "command_reserved", _json({"request_id": request_id, "operation": operation, "fingerprint": fingerprint}), ident)
            return {**self._public(self._command(run_id, request_id)), "created": True}

    def mark_dispatching(self, run_id, request_id) -> dict:
        """Claim once BEFORE the external call; re-claiming always fails."""
        with self._transaction():
            row = self._command(run_id, request_id)
            if row["status"] != "reserved":
                raise TransitionError("command_already_claimed_or_terminal")
            self._db.execute("UPDATE commands SET status='dispatching',updated_at=? WHERE command_id=?", (_utc(), row["command_id"]))
            self._event(run_id, "dispatch_intent_committed", "{}", row["command_id"])
            return self._public(self._command(run_id, request_id))

    def reserve_native_sequence(self, run_id, command_id, observed_last_seq) -> int:
        """Atomically assign one persistent-production sequence per command.

        The native high-water mark is supplied only by the trusted adapter's
        current admission read. The durable channel excludes host ID so a new
        host/run cannot reset numbering for the same game/player/commander.
        """
        _identifier(command_id, "command_id")
        if type(observed_last_seq) is not int or not 0 <= observed_last_seq <= 0xffffffff:
            raise JournalError("invalid_native_sequence")
        with self._transaction():
            run = self._run(run_id)
            command = self._db.execute("SELECT * FROM commands WHERE command_id=? AND run_id=?",
                                       (command_id, run_id)).fetchone()
            if command is None:
                raise IdentityConflict("native_sequence_command_run_mismatch")
            binding = json.loads(run['binding'])
            fields = ('session_id', 'player_id', 'commander_id', 'game_process_id',
                      'game_process_start', 'game_sha256', 'mod_sha256')
            if any(field not in binding for field in fields):
                raise JournalError("native_sequence_binding_incomplete")
            channel = hashlib.sha256(_json({field: binding[field] for field in fields}).encode('utf-8')).hexdigest()
            prior = self._db.execute("SELECT sequence,channel_hash FROM native_sequences WHERE command_id=?",
                                     (command_id,)).fetchone()
            if prior:
                if prior['channel_hash'] != channel:
                    raise IdentityConflict("native_sequence_channel_changed")
                return prior['sequence']
            if command['status'] not in ('reserved', 'dispatching'):
                raise TransitionError("native_sequence_requires_unsent_or_dispatching_command")
            high = self._db.execute("SELECT COALESCE(MAX(sequence),0) FROM native_sequences WHERE channel_hash=?",
                                    (channel,)).fetchone()[0]
            sequence = max(high, observed_last_seq) + 1
            if sequence > 0xffffffff:
                raise JournalError("native_sequence_exhausted")
            self._db.execute("INSERT INTO native_sequences VALUES (?,?,?,?)", (command_id, run_id, channel, sequence))
            self._event(run_id, 'native_sequence_reserved', _json({'sequence': sequence, 'channel_hash': channel}), command_id)
            return sequence

    def native_sequence_high_water(self, binding: Mapping) -> int:
        """Read the durable game/player/commander counter across host epochs."""
        fields=('session_id','player_id','commander_id','game_process_id',
                'game_process_start','game_sha256','mod_sha256')
        if not isinstance(binding,Mapping) or any(k not in binding for k in fields):
            raise JournalError('native_sequence_binding_incomplete')
        channel=hashlib.sha256(_json({k:binding[k] for k in fields}).encode('utf-8')).hexdigest()
        with self._transaction():
            return self._db.execute('SELECT COALESCE(MAX(sequence),0) FROM native_sequences WHERE channel_hash=?',(channel,)).fetchone()[0]

    def get_native_sequence(self, run_id, command_id) -> int:
        """Read an existing allocation; observing a receipt never allocates one."""
        _identifier(command_id, 'command_id')
        with self._transaction():
            self._run(run_id)
            row = self._db.execute('SELECT sequence FROM native_sequences WHERE run_id=? AND command_id=?',
                                   (run_id, command_id)).fetchone()
            if row is None:
                raise JournalError('native_sequence_not_allocated')
            return row['sequence']

    def _outcome(self, row, status, receipt, evidence_id=None):
        self._db.execute("UPDATE commands SET status=?,receipt=?,updated_at=? WHERE command_id=?", (status, receipt, _utc(), row["command_id"]))
        payload = {"status": status, "receipt": json.loads(receipt)}
        if evidence_id is not None:
            payload["evidence_id"] = evidence_id
        self._event(row["run_id"], "command_outcome", _json(payload), row["command_id"])
        return self._public(self._command(row["run_id"], row["request_id"]))

    def record_outcome(self, run_id, request_id, status, receipt: Mapping) -> dict:
        encoded = _object(receipt)
        with self._transaction():
            row = self._command(run_id, request_id)
            if status == row["status"] and row["receipt"] == encoded:
                return self._public(row)
            if status not in _TRANSITIONS.get(row["status"], set()):
                raise TransitionError("invalid_command_transition")
            return self._outcome(row, status, encoded)

    def resolve_uncertain(self, run_id, request_id, status, receipt: Mapping, *, evidence_id: str) -> dict:
        """Persist an adapter's reconciliation, not validate evidence or retry.

        The caller must independently verify the evidence against the run binding.
        Merely supplying an evidence ID never grants native execution authority.
        """
        _identifier(evidence_id, "evidence_id")
        encoded = _object(receipt)
        if status not in {"accepted", "started", "completed", "released", "rejected", "failed", "cancelled"}:
            raise TransitionError("invalid_reconciliation_status")
        with self._transaction():
            row = self._command(run_id, request_id)
            if row["status"] != "uncertain":
                raise TransitionError("command_not_uncertain")
            return self._outcome(row, status, encoded, evidence_id)

    def reconcile_interrupted(self, run_id) -> list[dict]:
        """Call only AFTER the owner host is confirmed dead; never dispatch.

        Accepted/started receipts survive inside the recovery event. No caller may
        use recovery as proof that the game did, or did not, execute a command.
        """
        with self._transaction():
            self._run(run_id)
            rows = self._db.execute("SELECT * FROM commands WHERE run_id=? AND status IN ('dispatching','accepted','started') ORDER BY rowid", (run_id,)).fetchall()
            result = []
            for row in rows:
                recovery = _json({"reason_code": "owner_interrupted", "previous_status": row["status"], "previous_receipt": json.loads(row["receipt"]) if row["receipt"] else None})
                result.append(self._outcome(row, "uncertain", recovery))
            return result

    def append_event(self, run_id, event_type, payload: Mapping, *, command_id=None, game_frame=None, monotonic_ns=None) -> dict:
        _identifier(event_type, "event_type")
        encoded = _object(payload)
        for value in (game_frame, monotonic_ns):
            if value is not None and (type(value) is not int or value < 0 or value > 2**63 - 1):
                raise JournalError("invalid_event_clock")
        with self._transaction():
            self._run(run_id)
            if command_id is not None:
                _identifier(command_id, "command_id")
                if not self._db.execute("SELECT 1 FROM commands WHERE command_id=? AND run_id=?", (command_id, run_id)).fetchone():
                    raise IdentityConflict("event_command_run_mismatch")
            seq = self._event(run_id, event_type, encoded, command_id, game_frame, monotonic_ns)
            return self._read_event(self._db.execute("SELECT * FROM events WHERE seq=?", (seq,)).fetchone())

    @staticmethod
    def _read_event(row):
        return {**dict(row), "payload": json.loads(row["payload"])}

    def get_command(self, run_id, request_id) -> dict:
        with self._transaction():
            return self._public(self._command(run_id, request_id))

    def get_command_by_id(self, run_id, command_id) -> dict:
        _identifier(command_id,'command_id')
        with self._transaction():
            self._run(run_id)
            row=self._db.execute('SELECT * FROM commands WHERE run_id=? AND command_id=?',(run_id,command_id)).fetchone()
            if row is None:raise IdentityConflict('command_id_run_mismatch')
            return self._public(row)

    def commands_for_run(self, run_id, *, operation=None) -> list[dict]:
        if operation is not None:_identifier(operation,'operation')
        with self._transaction():
            self._run(run_id)
            rows=self._db.execute('SELECT * FROM commands WHERE run_id=? ORDER BY rowid',(run_id,)).fetchall()
            return [self._public(row) for row in rows if operation is None or row['operation']==operation]

    def _completed_reserves_still_held(self, run_id):
        """Ready completes Reserve, not control ownership. Only release closes it.

        This durable projection is no physical proof: the trusted adapter checks
        the actual native release before the outcome is written to the journal.
        """
        records = [(row, json.loads(row['payload'])) for row in self._db.execute(
            "SELECT * FROM commands WHERE run_id=? AND (operation='reserve' OR status='released') ORDER BY rowid", (run_id,))]
        def key(payload):
            return payload.get('lease_id'), payload.get('task_id'), payload.get('generation')
        released = {key(payload) for row, payload in records if row['status'] == 'released'
                    and row['operation'] in ('reserve', 'commit', 'return', 'stop', 'query_status', 'reconcile_release','reconcile_return_home')}
        return [row for row, payload in records if row['operation'] == 'reserve' and row['status'] == 'completed'
                and isinstance(payload.get('lease_id'), str) and key(payload) not in released]

    def unresolved(self, run_id) -> list[dict]:
        with self._transaction():
            self._run(run_id)
            return [self._public(row) for row in self._unresolved_commands(run_id)]

    def _unresolved_commands(self, run_id):
        """A verified new release closes ownership, never rewrites old failure.

        Only the trusted adapter may publish the release outcome. Its receipt
        must name the exact prior unknown command and the same task/lease and
        generation. The original uncertain receipt and audit events survive.
        """
        releases = list(self._db.execute("SELECT * FROM commands WHERE run_id=? AND operation IN ('reconcile_release','reconcile_return_home') AND status='released'",(run_id,)))
        by_id={row['command_id']:row for row in self._db.execute('SELECT * FROM commands WHERE run_id=?',(run_id,))}
        recovered = {}
        for release in releases:
            payload=json.loads(release['payload']);receipt=json.loads(release['receipt'] or '{}')
            facts=receipt.get('facts',{})
            prior=payload.get('recovery_of_command_id')
            if (isinstance(prior,str) and facts.get('recovery_of_command_id')==prior
                    and facts.get('command_id')==release['command_id']
                    and facts.get('control_released') is True and facts.get('stance_restored') is True
                    and facts.get('held') is False and facts.get('mission_effect_verified') is False
                    and (release['operation']!='reconcile_return_home' or facts.get('physical_home')is True)):
                # A failed first-home command may itself need one new release.
                # Resolve its control ancestry only; keep every old outcome.
                chain=[];cursor=prior
                while isinstance(cursor,str) and cursor not in chain and cursor in by_id:
                    old=by_id[cursor];old_payload=json.loads(old['payload'])
                    if (old['status']!='uncertain' or old['operation']not in ('reserve','commit','return','stop','reconcile_return_home')
                            or not all(old_payload.get(k)==payload.get(k) and payload.get(k)is not None for k in ('task_id','lease_id','generation'))):break
                    chain.append(cursor)
                    if old['operation']!='reconcile_return_home':
                        recovered.update({item:payload for item in chain});break
                    cursor=old_payload.get('recovery_of_command_id')
        marks=','.join('?' for _ in _UNRESOLVED)
        rows=list(self._db.execute(f'SELECT * FROM commands WHERE run_id=? AND status IN ({marks}) ORDER BY rowid',(run_id,*_UNRESOLVED)))
        # A failed successor attach is not a tactical lease. Only a separately
        # verified closed, never-borrowed channel may close that ownership
        # projection; the original uncertain command/receipt stays unchanged.
        attach_reviews={}
        run_binding=json.loads(self._run(run_id)['binding'])
        binding_hash=hashlib.sha256(_json(run_binding).encode('utf-8')).hexdigest()
        for review in self._db.execute("SELECT * FROM commands WHERE run_id=? AND operation='review_runtime_channel_release' AND status='released'",(run_id,)):
            payload=json.loads(review['payload']);receipt=json.loads(review['receipt']or'{}')
            prior=payload.get('recovery_of_command_id');old=by_id.get(prior)
            digest=receipt.get('review_sha256')
            if (old is not None and old['operation']=='runtime_channel_attach' and old['status']=='uncertain'
                    and receipt.get('reason_code')=='runtime_attach_no_control_independently_closed'
                    and receipt.get('source')=='independent_runtime_epoch_release_review'
                    and receipt.get('reviewed_command_id')==prior
                    and payload.get('binding_hash')==receipt.get('binding_hash')==binding_hash
                    and receipt.get('native_release_verified')is True and receipt.get('channel_closed')is True
                    and receipt.get('no_control_acquired')is True and receipt.get('mission_effect_granted')is False
                    and isinstance(digest,str)and len(digest)==64 and all(x in '0123456789abcdef'for x in digest)):
                attach_reviews[prior]=review['command_id']
        def closed(row):
            if row['command_id']in attach_reviews:return True
            payload=json.loads(row['payload']);release=recovered.get(row['command_id'])
            return (row['status']=='uncertain' and row['operation'] in ('reserve','commit','return','stop','reconcile_return_home')
                and release is not None and all(payload.get(k)==release.get(k) and payload.get(k) is not None
                    for k in ('task_id','lease_id','generation')))
        return [row for row in rows if not closed(row)]+self._completed_reserves_still_held(run_id)

    def unresolved_for_session(self, binding: Mapping, *, exclude_run_id=None) -> list[dict]:
        """Find unresolved ownership in earlier runs of the same game channel.

        A new host UUID/run ID is not permission to forget uncertain work. The
        caller must reconcile it against native state before starting another run.
        """
        fields = ('session_id', 'player_id', 'commander_id', 'game_process_id',
                  'game_process_start', 'game_sha256', 'mod_sha256')
        if not isinstance(binding, Mapping) or any(field not in binding for field in fields):
            raise JournalError('session_recovery_binding_incomplete')
        if exclude_run_id is not None:
            _identifier(exclude_run_id, 'run_id')
        with self._transaction():
            matching = []
            for run in self._db.execute('SELECT run_id,binding FROM runs'):
                if run['run_id'] == exclude_run_id:
                    continue
                prior = json.loads(run['binding'])
                if prior.get('session_id') != binding['session_id'] or prior.get('player_id') != binding['player_id']:
                    continue
                if any(field not in prior for field in fields):
                    raise JournalError('prior_session_binding_incomplete')
                if all(prior[field] == binding[field] for field in fields):
                    matching.append(run['run_id'])
            result = []
            for run_id in matching:
                result.extend(self._public(row) for row in self._unresolved_commands(run_id))
            return result

    def events(self, run_id, after=0, *, limit=1000) -> list[dict]:
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 10000:
            raise JournalError("invalid_event_page")
        with self._transaction():
            self._run(run_id)
            return [self._read_event(row) for row in self._db.execute("SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?", (run_id, after, limit))]

    def latest_events(self, run_id, *, limit=30) -> dict:
        """A single consistent recent-page projection, including its truncation."""
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise JournalError("invalid_event_page")
        with self._transaction():
            self._run(run_id)
            total = self._db.execute("SELECT COUNT(*) FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
            records = list(self._db.execute("SELECT * FROM events WHERE run_id=? ORDER BY seq DESC LIMIT ?", (run_id, limit)))
            events = [self._read_event(row) for row in reversed(records)]
            return dict(events=events, total_count=total, first_seq=events[0]['seq'] if events else None,
                        last_seq=events[-1]['seq'] if events else None, truncated=total > len(events))

    def close(self):
        with self._lock:
            if not self._closed:
                self._db.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
