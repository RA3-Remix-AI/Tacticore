"""Read-only protected library plus authoritative SQLite style-draft revisions.

Listing never imports the credential loader or opens DPAPI files. Library
identity/connection records stay owned by library.v2.json; only style drafts and
their save receipts are owned by this database.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import ipaddress
import json
from pathlib import Path
import sqlite3
import threading
from urllib.parse import urlsplit

from .contracts import ContractError, canonical_json, content_hash, identifier, integer, object_fields, text
from .profiles import DOCTRINES, normalize_profile

MAX_LIBRARY_BYTES = 1024 * 1024


def _decode(raw: bytes):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ContractError("duplicate_library_key")
            value[key] = item
        return value
    def constant(_):
        raise ContractError("invalid_library_number")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
    except ContractError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError("invalid_library_json") from None


def _endpoint(value):
    text(value, 2048)
    try:
        if any(c.isspace() for c in value):
            raise ValueError()
        u = urlsplit(value)
        host = u.hostname
        loopback = host == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(host).is_loopback
        except (ValueError, TypeError):
            pass
        if (not host or u.username or u.password or u.query or u.fragment
                or not (u.scheme == "https" or u.scheme == "http" and loopback)
                or u.path.lower().endswith("/chat/completions") or not 1 <= (u.port or 443) <= 65535):
            raise ValueError()
    except ValueError:
        raise ContractError("invalid_connection_endpoint") from None


class ProfileStore:
    def __init__(self, library_path: Path, state_dir: Path):
        self.library_path = Path(library_path).resolve()
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = self.state_dir / "profile-drafts.sqlite3"
        if self.database_path == self.library_path:
            raise ContractError("profile_store_path_conflict")
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.database_path), timeout=10, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS style_drafts (
              profile_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
              draft_json TEXT NOT NULL, library_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS style_save_receipts (
              request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
              receipt_json TEXT NOT NULL);
        """)

    @contextmanager
    def _transaction(self):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def close(self):
        with self._lock:
            self._db.close()

    def _library(self):
        try:
            with self.library_path.open("rb") as stream:
                raw = stream.read(MAX_LIBRARY_BYTES + 1)
        except OSError:
            raise ContractError("profile_library_unavailable") from None
        if len(raw) > MAX_LIBRARY_BYTES:
            raise ContractError("profile_library_too_large")
        value = object_fields(_decode(raw), {"schema_version", "connections", "commanders"})
        if type(value["schema_version"]) is not int or value["schema_version"] != 2:
            raise ContractError("unsupported_library_schema")
        connections = {}; commanders = {}
        for field in ("connections", "commanders"):
            if not isinstance(value[field], list) or not 1 <= len(value[field]) <= 100:
                raise ContractError("invalid_library_count")
        for item in value["connections"]:
            row = object_fields(item, {"id", "name", "provider", "base_url", "remember_key", "default_model"})
            ident = identifier(row["id"])
            if ident in connections:
                raise ContractError("duplicate_connection_id")
            text(row["name"], 60); text(row["default_model"], 200, empty=True); _endpoint(row["base_url"])
            if row["provider"] not in ("OpenAI", "DeepSeek", "自定义") or type(row["remember_key"]) is not bool:
                raise ContractError("invalid_connection")
            connections[ident] = row
        for item in value["commanders"]:
            row = object_fields(item, {"id", "name", "connection_id", "model", "personality", "traits"})
            ident = identifier(row["id"]); connection = identifier(row["connection_id"])
            if ident in commanders:
                raise ContractError("duplicate_commander_id")
            if connection not in connections:
                raise ContractError("commander_connection_missing")
            text(row["name"], 40); text(row["model"], 200, empty=True); text(row["traits"], 4000, empty=True)
            integer(row["personality"], 0, 2, "invalid_personality")
            commanders[ident] = row
        return commanders, connections, hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _base_draft(commander):
        return dict(schema_version=1, profile_id=commander["id"], name=commander["name"], revision=1,
                    connection_id=commander["connection_id"], model=commander["model"],
                    doctrine=next(d for d, p in DOCTRINES.items() if p == commander["personality"]),
                    custom_traits=commander["traits"])

    def _record(self, profile_id, commanders, connections, library_hash, row=None):
        if profile_id not in commanders:
            raise ContractError("profile_not_found")
        commander = commanders[profile_id]
        draft = json.loads(row["draft_json"]) if row is not None else self._base_draft(commander)
        effective = None; reason = "ok"
        try:
            if draft["connection_id"] != commander["connection_id"] or draft["name"] != commander["name"]:
                raise ContractError("protected_profile_changed")
            resolved = dict(draft)
            resolved["model"] = (draft["model"].strip() or commander["model"].strip()
                                  or connections[commander["connection_id"]]["default_model"].strip())
            if not resolved["model"]:
                raise ContractError("model_not_resolved")
            effective = normalize_profile(resolved).public()
        except ContractError as error:
            reason = error.code
        return dict(profile_id=profile_id, name=commander["name"], revision=draft["revision"],
                    connection_id=commander["connection_id"], model=effective["model"] if effective else "",
                    personality=effective["personality"] if effective else commander["personality"],
                    doctrine=draft["doctrine"], preferences=effective["preferences"] if effective else draft.get("preferences"),
                    custom_traits=draft["custom_traits"], draft=draft, effective=effective,
                    validation=dict(ok=effective is not None, reason_code=reason),
                    state="saved" if row is not None else "library", host_applied=False,
                    library_hash=library_hash, library_changed=bool(row is not None and row["library_hash"] != library_hash))

    def list_profiles(self) -> dict:
        commanders, connections, library_hash = self._library()
        with self._lock:
            saved = {row["profile_id"]: row for row in self._db.execute("SELECT * FROM style_drafts")}
        return {"profiles": [self._record(ident, commanders, connections, library_hash, saved.get(ident)) for ident in commanders]}

    def list_connections(self) -> dict:
        _, connections, _ = self._library()
        return {"connections": [dict(id=row["id"], name=row["name"], provider=row["provider"],
            endpoint=row["base_url"], model=row["default_model"], credential_configured=None,
            credential_check="not_checked", remember_key=row["remember_key"])
            for row in connections.values()]}

    def get_profile(self, profile_id: str) -> dict:
        identifier(profile_id)
        commanders, connections, library_hash = self._library()
        with self._lock:
            row = self._db.execute("SELECT * FROM style_drafts WHERE profile_id=?", (profile_id,)).fetchone()
        return {"profile": self._record(profile_id, commanders, connections, library_hash, row)}

    def save_profile(self, request_id: str, draft: dict, expected_revision: int) -> dict:
        identifier(request_id); integer(expected_revision, 1, 2**53 - 2, "invalid_profile_revision")
        if not isinstance(draft, dict):
            raise ContractError("invalid_commander_draft")
        # Strict validation runs before any client payload is persisted, including
        # refusal of keys/endpoints/credentials smuggled into a draft.
        profile_id = identifier(draft.get("profile_id"))
        if type(draft.get("revision")) is not int or draft["revision"] != expected_revision:
            raise ContractError("profile_revision_mismatch")
        commanders, connections, library_hash = self._library()
        if profile_id not in commanders:
            raise ContractError("profile_not_found")
        commander = commanders[profile_id]
        if draft.get("connection_id") != commander["connection_id"]:
            raise ContractError("profile_connection_mismatch")
        if draft.get("name") != commander["name"]:
            raise ContractError("profile_name_mismatch")
        resolved = dict(draft)
        if not isinstance(resolved.get("model"), str):
            raise ContractError("invalid_model")
        resolved["model"] = (resolved["model"].strip() or commander["model"].strip()
                              or connections[commander["connection_id"]]["default_model"].strip())
        if not resolved["model"]:
            raise ContractError("model_not_resolved")
        normalize_profile(resolved)
        fingerprint = content_hash(dict(draft=draft, expected_revision=expected_revision))
        with self._transaction():
            old = self._db.execute("SELECT * FROM style_save_receipts WHERE request_id=?", (request_id,)).fetchone()
            if old is not None:
                if old["fingerprint"] != fingerprint:
                    raise ContractError("request_id_conflict")
                return json.loads(old["receipt_json"])
            row = self._db.execute("SELECT * FROM style_drafts WHERE profile_id=?", (profile_id,)).fetchone()
            current_revision = row["revision"] if row is not None else 1
            if current_revision != expected_revision:
                raise ContractError("profile_revision_conflict")
            updated = dict(draft, revision=expected_revision + 1)
            encoded = canonical_json(updated)
            self._db.execute("INSERT INTO style_drafts(profile_id,revision,draft_json,library_hash) VALUES (?,?,?,?) "
                "ON CONFLICT(profile_id) DO UPDATE SET revision=excluded.revision,draft_json=excluded.draft_json,library_hash=excluded.library_hash",
                (profile_id, expected_revision + 1, encoded, library_hash))
            row = dict(draft_json=encoded, library_hash=library_hash)
            result = dict(profile=self._record(profile_id, commanders, connections, library_hash, row), state="saved", host_applied=False)
            self._db.execute("INSERT INTO style_save_receipts VALUES (?,?,?)", (request_id, fingerprint, canonical_json(result)))
            return result
