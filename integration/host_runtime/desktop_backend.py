"""Trusted desktop HostBackend: read-only live admission and durable launch claims.

Paths and dependency injection belong to the native bootstrap, never RPC args.
The default checks perform real Win32/registry/package/evidence verification.
Tests may replace checks and the spawner together; test admission cannot reach
the default spawner. A launch receipt never claims model/game completion.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import importlib
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path, PureWindowsPath
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
from typing import Mapping
import uuid

from .application import apply_commander_draft
from .contracts import ContractError, SessionBinding, canonical_json, content_hash, identifier, sha256
from .evidence_adapter import build_catalog
from .journal import CommandJournal, JournalError, RequestConflict, TransitionError
from .limits import ExecutionLimits
from .diagnostics import create_export, project_fields, project_tasks, project_plan, recent_events
from .application import load_commander_draft
from .profiles import normalize_profile
from .desktop_session_registry import load_root
from .python_runtime import interpreter, script_command
from .macro_control import require_macro_evidence, CONTROL_MODE

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "integration"
# Leave time for the visible UI and a second complete live admission. The
# actual dispatch still rechecks expiry, session, profile and caller identity.
READINESS_MS = 90_000


def _module(name, directory=INTEGRATION):
    for path in (directory, ROOT / "strategy", ROOT / "production", ROOT / "native-ai"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    module = importlib.import_module(name)
    if Path(module.__file__).resolve() != directory / (name + ".py"):
        raise ContractError("session_unavailable")
    return module


def _object(path, maximum=65536):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    def constant(_):raise ValueError()
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:raise ValueError()
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):raise ValueError()
    return value, hashlib.sha256(raw).hexdigest()


def _atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + str(uuid.uuid4()) + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(canonical_json(value)); stream.flush(); os.fsync(stream.fileno())
        for attempt in range(25):
            try:temporary.replace(path);break
            except PermissionError:
                if attempt==24:raise
                time.sleep(.02)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class SessionRegistration:
    session_path: Path
    production_report: Path | None
    persistent_status: Path | None
    runtime_report: Path | None = None
    runtime_sha256: str | None = None
    runtime_recovery_report: Path | None = None
    runtime_recovery_sha256: str | None = None
    macro_bundle: Path | None = None

    @classmethod
    def trusted(cls, session_path, production_report=None, persistent_status=None, *, root=None, runtime_report=None, runtime_sha256=None,
                runtime_recovery_report=None,runtime_recovery_sha256=None,macro_bundle=None):
        allowed = Path(root or ROOT / "acceptance/runs").resolve()
        if macro_bundle is not None:
            if any(value is not None for value in (production_report,persistent_status,runtime_report,runtime_sha256,runtime_recovery_report,runtime_recovery_sha256)):
                raise ContractError('macro_registration_mixed_evidence')
            session=Path(session_path).resolve(strict=True);bundle=Path(macro_bundle).resolve(strict=True)
            if any(not path.is_file() or not path.is_relative_to(allowed) for path in (session,bundle)):
                raise ContractError('session_unavailable')
            record,_=_object(session)
            if Path(record.get('run_directory','')).resolve()!=session.parent:raise ContractError('session_unavailable')
            from .macro_bundle import load_bundle
            load_bundle(bundle,record)
            return cls(session,None,None,macro_bundle=bundle)
        paths = [Path(p).resolve(strict=True) for p in (session_path, production_report, persistent_status)]
        if any(not p.is_file() or not p.is_relative_to(allowed) for p in paths):
            raise ContractError("session_unavailable")
        session, _ = _object(paths[0])
        if Path(session.get("run_directory", "")).resolve() != paths[0].parent:
            raise ContractError("session_unavailable")
        if (runtime_report is None) != (runtime_sha256 is None):
            raise ContractError("runtime_evidence_pin_required")
        if (runtime_recovery_report is None)!=(runtime_recovery_sha256 is None):
            raise ContractError('first_home_evidence_pin_required')
        if runtime_recovery_report is not None and runtime_report is None:
            raise ContractError('first_home_requires_baseline_scope')
        runtime=recovery=None
        if runtime_report is not None:
            runtime = Path(runtime_report).resolve(strict=True)
            sha256(runtime_sha256)
            if not runtime.is_file() or not runtime.is_relative_to(allowed):
                raise ContractError("runtime_evidence_registration_required")
            if hashlib.sha256(runtime.read_bytes()).hexdigest() != runtime_sha256:
                raise ContractError("runtime_evidence_pin_mismatch")
        if runtime_recovery_report is not None:
            recovery=Path(runtime_recovery_report).resolve(strict=True);sha256(runtime_recovery_sha256)
            if not recovery.is_file()or not recovery.is_relative_to(allowed):
                raise ContractError('first_home_evidence_registration_required')
            if hashlib.sha256(recovery.read_bytes()).hexdigest()!=runtime_recovery_sha256:
                raise ContractError('first_home_evidence_pin_mismatch')
        return cls(*paths,runtime,runtime_sha256,recovery,runtime_recovery_sha256)

    def evidence_paths(self):
        if self.macro_bundle is not None:return dict(session_file=self.session_path,macro_bundle=self.macro_bundle)
        paths = dict(session_file=self.session_path, production_report=self.production_report,
                     persistent_status=self.persistent_status)
        if self.runtime_report is not None:paths["runtime_report"] = self.runtime_report
        if self.runtime_recovery_report is not None:paths['runtime_recovery_report']=self.runtime_recovery_report
        return paths


@dataclass(frozen=True)
class Admission:
    binding: SessionBinding
    admission_hash: str
    session: Mapping
    capabilities: Mapping
    test_only: bool = False


class NativeChecks:
    """Only read game memory; all local observation outputs use the new state dir."""
    test_only = False

    def __init__(self, *, acceptance_root=None):
        self.acceptance_root = acceptance_root

    def _observe(self, registration, profile_id, state_dir):
        if getattr(registration,'macro_bundle',None) is not None:
            from .macro_desktop import observe
            return observe(registration,profile_id,state_dir)
        session, digest = _object(registration.session_path)
        identifier(session.get("session_id")); identifier(profile_id)
        scenario = session.get("scenario", {})
        opponent = scenario.get("opponent_player_index")
        if scenario.get("computer_player_index") != 3:
            raise ContractError("legacy_executor_player_unsupported")
        if (scenario.get("commander_id") != profile_id or scenario.get("computer_player_index") != 3
            or scenario.get("participant_count") != 2 or type(opponent) is not int or not 0 <= opponent <= 15 or opponent == 3):
            raise ContractError("session_mismatch")
        state = _module("live_state").LiveBattleState(registration.session_path, profile_id, 3,
                 output=Path(state_dir) / "admission" / session["session_id"], foci=("native_baseline", "infantry"))
        snapshot = state.collect()
        if state.owner is None or not state.native or not state.participant_identity:
            raise ContractError("session_not_ready")
        if any(row.get("victory_frame") or row.get("defeat_frame") or row.get("quit_frame")
               for row in state.native.get("result_records", [])):
            raise ContractError("session_not_ready")
        own, _ = _object(state.output / "own-state.json", 1024 * 1024)
        factories = [row for row in own.get("factories", []) if row.get("template") == "SovietBarracks"
                     and row.get("production_interface_available") is True and row.get("hp", 0) > 0]
        # This collector verifies process start, executable, current native AI,
        # registry UUID, scenario map and participants using fresh memory reads.
        footprint = dict(session_digest=digest, registry_sha256=hashlib.sha256(state.registry_raw).hexdigest(),
                         owner=state.owner, ai=state.ai, logic=state.logic, map=state.map,
                         participants=state.participant_identity,
                         producer_identity=[dict(address=row["address"], template=row["template"]) for row in factories])
        summary = dict(id=session["session_id"], map=PureWindowsPath(state.map).stem,
                       player_name=profile_id, faction="Soviet" if factories else "unknown")
        return session, snapshot, footprint, summary

    def inspect(self, registration, profile_id, state_dir):
        session, _, _, summary = self._observe(registration, profile_id, state_dir)
        return summary

    def check(self, registration, profile, host_id, state_dir, library_path, limits):
        require_macro_evidence(registration)
        if getattr(registration,'macro_bundle',None) is not None:
            from .macro_desktop import check
            return check(self,registration,profile,host_id,state_dir,library_path,limits)
        session, snapshot, footprint, summary = self._observe(registration, profile["profile_id"], state_dir)
        if snapshot.get("paused") is not False:
            raise ContractError("session_not_ready")
        if not footprint["producer_identity"]:
            raise ContractError("session_not_ready")
        binding = SessionBinding(1, session["session_id"], 3, profile["profile_id"], session["pid"],
                   session["start_time"], host_id, hashlib.sha256(Path(session["game"]).read_bytes()).hexdigest(), session["mod_sha256"])
        try:
            evidence = build_catalog(binding, session, production_report=registration.production_report,
                                     persistent_status=registration.persistent_status, acceptance_root=self.acceptance_root,
                                     runtime_report=registration.runtime_report, runtime_sha256=registration.runtime_sha256,
                                     runtime_recovery_report=registration.runtime_recovery_report,runtime_recovery_sha256=registration.runtime_recovery_sha256)
            grant = evidence.catalog.require("production.infantry", binding)
        except Exception:
            raise ContractError("capability_unavailable") from None
        constraint = grant.public()["execution_constraints"]
        if (evidence.test_only or constraint.get("runtime_family") != "production_persistent_v2"
            or constraint.get("execution_ready") is not True or constraint.get("executor_directory") != "production/persistent/bin-v2"
            or constraint.get("allowed_units") != ["conscript"] or "conscript" not in constraint.get("persistent_units_verified", [])):
            raise ContractError("capability_unavailable")
        maximum = constraint.get("max_budget")
        minimum = constraint.get("reserve_floor")
        if (maximum is not None and limits.max_command_budget > maximum
            or minimum is not None and limits.reserve_floor < minimum):
            raise ContractError("capability_unavailable")
        # Check the named shared channel without opening/injecting an executor.
        win = _module("observe_production", ROOT / "production")
        win.k.OpenFileMappingW.argtypes = [win.w.DWORD, win.w.BOOL, win.w.LPCWSTR]
        win.k.OpenFileMappingW.restype = win.w.HANDLE
        mapping = win.k.OpenFileMappingW(4, False, "Local\\RA3ProductionPersistent_" + str(session["pid"]))
        if mapping:
            win.k.CloseHandle(mapping)
            raise ContractError("run_already_active")
        output = Path(session["run_directory"]).resolve() / "battle-host"
        if output.exists() and any(output.iterdir()):
            # Old exports are never interpreted as a permission to replay.
            raise ContractError("run_state_conflict")
        adapter = _module("http_adapter", ROOT / "strategy")
        try:
            protected = adapter.load_profile(Path(library_path), profile["profile_id"])
            applied = apply_commander_draft(protected, profile["draft"])
        except adapter.AdapterError:
            raise ContractError("credentials_unavailable") from None
        if applied.effective.effective_hash != profile["effective"]["effective_hash"]:
            raise ContractError("effective_profile_changed")
        summary["player_name"] = profile["name"]
        _module("model_backend", ROOT / "strategy").check_backend_available("pydantic")
        admission_hash = content_hash(dict(binding=binding.public(), footprint=footprint,
            profile_revision=profile["revision"], effective_hash=applied.effective.effective_hash,
            library_hash=profile["library_hash"], capabilities=evidence.catalog.catalog_hash,
            execution_constraints_hash=evidence.execution_constraints_hash, limits=limits.public(),
            protected_connection=content_hash(dict(endpoint=repr(protected.endpoint), credential=protected.key))))
        return Admission(binding, admission_hash, summary, dict(control_mode=CONTROL_MODE, supported_units=["conscript"],
             supported_foci=["infantry"], production=evidence.catalog.describe(),
             tactics_supported=False, runtime_tactical_supported=evidence.runtime is not None,
             runtime_recovery_supported=evidence.first_home_recovery is not None,
             runtime_purposes=["move_hold_return"] if evidence.runtime else [], model_response_received=False), False)


class NativeHostSpawner:
    """Detached OS process; command vector is constructed solely from trusted data."""
    test_only = False

    @staticmethod
    def identity(pid):
        if os.name != "nt":raise ContractError("session_unavailable")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:return None
        try:
            exit_code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:return None
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):return None
            ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return datetime.fromtimestamp((ticks - 116444736000000000) / 10000000, timezone.utc).isoformat()
        finally:
            kernel.CloseHandle(handle)

    def spawn(self, command, log_path, admission):
        if admission.test_only:
            raise ContractError("capability_unavailable")
        with Path(log_path).open("ab", buffering=0) as log:
            return subprocess.Popen(command, cwd=INTEGRATION, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


class DesktopBackend:
    def __init__(self, store, *, registration=None, checks=None, spawner=None, now_ms=None,
                 python_path=None, limits=None, registration_root=None, caller_alive=None, discovery=None):
        self.store = store
        self.discovery = discovery
        self.state_dir = store.state_dir
        self.registration = registration
        try:
            self._root_record = load_root(self.state_dir) if registration_root is None else None
        except ContractError:
            # Status/stop remain available for an already accepted run even if
            # a later bootstrap edit is invalid. Admission still fails closed.
            self._root_record = {"invalid": True}
        self._root_bootstrap = registration_root is None
        self.registration_root = Path(registration_root or (self._root_record or {}).get("session_root") or ROOT / "acceptance/runs").resolve()
        self.registration_path = self.state_dir / "session-registration.json"
        self.checks = checks if checks is not None else NativeChecks(acceptance_root=self.registration_root)
        self.spawner = spawner if spawner is not None else NativeHostSpawner()
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self.python_path = Path(python_path).resolve() if python_path else interpreter()
        self.limits = limits or ExecutionLimits()
        parent_pid = os.getppid()
        parent_start = NativeHostSpawner.identity(parent_pid) if os.name == "nt" else None
        self.caller_alive = caller_alive if caller_alive is not None else (
            lambda: parent_start is not None and NativeHostSpawner.identity(parent_pid) == parent_start)
        self.ledger_path = self.state_dir / "host-runtime.sqlite3"
        self.journal = CommandJournal(self.ledger_path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.state_dir / "desktop-launch-index.sqlite3"), isolation_level=None,
                                  check_same_thread=False, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL"); self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS readiness (token_hash TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,
              host_id TEXT NOT NULL, profile_id TEXT NOT NULL, revision INTEGER NOT NULL,
              effective_hash TEXT NOT NULL, admission_hash TEXT NOT NULL, expires_at INTEGER NOT NULL,
              binding_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS launches (run_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
              fingerprint TEXT NOT NULL, session_path TEXT NOT NULL, output_path TEXT NOT NULL,
              binding_json TEXT NOT NULL, channel_hash TEXT UNIQUE NOT NULL);
        """)
        self._children = {}

    def close(self):
        if self.discovery is not None:
            self.discovery.close()
            self.discovery = None
        self.journal.close(); self._db.close()

    @contextmanager
    def _transaction(self):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK"); raise

    def register_session(self, session_path, production_report=None, persistent_status=None, *, runtime_report=None, runtime_sha256=None,
                         runtime_recovery_report=None,runtime_recovery_sha256=None,macro_bundle=None):
        """Native-only registration; this method is deliberately absent from RPC."""
        with self._lock:
            registration = SessionRegistration.trusted(session_path, production_report, persistent_status, root=self.registration_root,
                runtime_report=runtime_report, runtime_sha256=runtime_sha256,
                runtime_recovery_report=runtime_recovery_report,runtime_recovery_sha256=runtime_recovery_sha256,macro_bundle=macro_bundle)
            paths = registration.evidence_paths()
            payload = dict(schema_version=2 if macro_bundle is not None else 1, **{name: str(path) for name, path in paths.items()},
                           content_hashes={name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()})
            if registration.runtime_report is not None:payload["runtime_sha256"] = registration.runtime_sha256
            if registration.runtime_recovery_report is not None:payload['runtime_recovery_sha256']=registration.runtime_recovery_sha256
            payload["registration_hash"] = content_hash(payload)
            _atomic(self.registration_path, payload)
            self.registration = registration
            self._db.execute("DELETE FROM readiness")

    def _registration(self):
        try:
            if self._root_bootstrap and load_root(self.state_dir) != self._root_record:
                self._db.execute("DELETE FROM readiness")
                raise ContractError("session_registration_changed")
            if self.registration_path.exists():
                value, _ = _object(self.registration_path)
                if value.get('schema_version')==2:
                    fields={'schema_version','session_file','macro_bundle','content_hashes','registration_hash'}
                    if set(value)!=fields or type(value['schema_version']) is not int:raise ValueError()
                    fingerprint=value.pop('registration_hash')
                    if content_hash(value)!=fingerprint:raise ValueError()
                    registration=SessionRegistration.trusted(value['session_file'],root=self.registration_root,macro_bundle=value['macro_bundle'])
                    if value['content_hashes']!={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in registration.evidence_paths().items()}:raise ValueError()
                    return registration
                fields = {"schema_version", "session_file", "production_report", "persistent_status", "content_hashes", "registration_hash"}
                basic={"runtime_report","runtime_sha256"};recovery={'runtime_recovery_report','runtime_recovery_sha256'}
                if set(value) not in (fields,fields|basic,fields|basic|recovery):
                    raise ValueError()
                fingerprint = value.pop("registration_hash")
                if type(value["schema_version"]) is not int or value["schema_version"] != 1 or content_hash(value) != fingerprint:
                    raise ValueError()
                registration = SessionRegistration.trusted(value["session_file"], value["production_report"],
                    value["persistent_status"], root=self.registration_root,
                    runtime_report=value.get("runtime_report"), runtime_sha256=value.get("runtime_sha256"),
                    runtime_recovery_report=value.get('runtime_recovery_report'),runtime_recovery_sha256=value.get('runtime_recovery_sha256'))
                paths = registration.evidence_paths()
                if value["content_hashes"] != {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}:
                    raise ValueError()
                return registration
            if isinstance(self.registration, SessionRegistration):
                return SessionRegistration.trusted(self.registration.session_path, self.registration.production_report,
                    self.registration.persistent_status, root=self.registration_root,
                    runtime_report=self.registration.runtime_report, runtime_sha256=self.registration.runtime_sha256,
                    runtime_recovery_report=self.registration.runtime_recovery_report,runtime_recovery_sha256=self.registration.runtime_recovery_sha256,macro_bundle=self.registration.macro_bundle)
        except ContractError:
            raise
        except (OSError, ValueError, TypeError):
            pass
        raise ContractError("session_unavailable")

    def session_discover(self, args, request_id):
        if self.discovery is None:
            raise ContractError('session_discovery_unavailable')
        return self.discovery.discover(args,request_id)

    def session_prepare(self, args, request_id):
        if self.discovery is None:
            raise ContractError('session_discovery_unavailable')
        with self._lock:
            result=self.discovery.prepare(args,request_id)
            # Only a successful trusted discovery registration can refresh this
            # service's root. Arbitrary external root edits still fail closed.
            root=load_root(self.state_dir)
            if root is None or Path(root['session_root'])!=self.discovery.policy.session_root:
                raise ContractError('session_root_invalid')
            self._root_record=root;self._root_bootstrap=True
            self.registration_root=Path(root['session_root'])
            if isinstance(self.checks,NativeChecks):
                self.checks.acceptance_root=self.registration_root
            self._db.execute('DELETE FROM readiness')
            self.registration=self._registration()
            registered,_=_object(self.registration.session_path)
            if result.get('registered') is not True or result.get('session_id')!=registered.get('session_id'):
                # An old idempotent receipt describes its original operation,
                # not a different registration installed by a later prepare.
                raise ContractError('session_preparation_changed')
            return dict(result,registration_reload_required=False)

    def run_resume(self, args, request_id):
        # The launch index is authoritative. No directory scan, registration
        # mutation, model call or new host is performed when reopening the UI.
        if args:
            raise ContractError('unexpected_fields')
        with self._lock:
            try:
                statuses=[self._status(row) for row in self._db.execute('SELECT * FROM launches ORDER BY rowid DESC').fetchall()]
            except (ContractError,ValueError,TypeError,KeyError,JournalError):
                raise ContractError('run_history_unverifiable') from None
            terminal={'stopped','completed','fault','result_candidate'}
            pending=[row for row in statuses if row.get('state') not in terminal or row.get('native_release_verified') is not True]
            selected=(pending or statuses)
            return dict(run=selected[0] if selected else None,observation_only=True,
                        other_unreleased_runs=max(0,len(pending)-1))

    def session_inspect(self, args, request_id):
        try:
            registration = self._registration()
            if "profile_id" in args:
                profile_id = args["profile_id"]
            else:
                session, _ = _object(registration.session_path)
                profile_id = identifier(session.get("scenario", {}).get("commander_id"))
            summary = self.checks.inspect(registration, profile_id, self.state_dir)
            profile = self.store.get_profile(profile_id)["profile"]
            summary = dict(summary, player_name=profile["name"])
            return dict(session=summary)
        except Exception:
            return dict(session=None, reason_code="session_unavailable")

    def run_check(self, profile, args, request_id):
        try:
            registration = self._registration()
            require_macro_evidence(registration)
            host_id = str(uuid.uuid4())
            admission = self.checks.check(registration, profile, host_id, self.state_dir, self.store.library_path, self.limits)
            if isinstance(admission, Admission) and admission.capabilities.get('native_macro') is True:
                from dataclasses import replace
                from .macro_strategic_client_v1 import preflight_capabilities
                admission=replace(admission,capabilities=preflight_capabilities(admission.capabilities))
            if not isinstance(admission, Admission):raise ContractError("session_not_ready")
            channel = admission.binding.public(); channel.pop("host_id")
            with self._lock:
                prior_launch = self._db.execute("SELECT 1 FROM launches WHERE channel_hash=?", (content_hash(channel),)).fetchone()
            if prior_launch is not None:raise ContractError("run_state_conflict")
            if self.journal.unresolved_for_session(admission.binding.public()):
                raise ContractError("run_state_conflict")
            token = secrets.token_urlsafe(32); run_id = str(uuid.uuid4()); expires = self.now_ms() + READINESS_MS
            with self._transaction():
                self._db.execute("DELETE FROM readiness WHERE expires_at<?", (self.now_ms(),))
                self._db.execute("INSERT INTO readiness VALUES (?,?,?,?,?,?,?,?,?)", (
                    hashlib.sha256(token.encode()).hexdigest(), run_id, host_id, profile["profile_id"], profile["revision"],
                    profile["effective"]["effective_hash"], admission.admission_hash, expires, canonical_json(admission.binding.public())))
            return dict(ready=True, session_id=admission.binding.session_id, ready_token=token, expires_at=expires,
                        capabilities=dict(admission.capabilities), session=dict(admission.session), execution_limits=self.limits.public())
        except ContractError as error:
            reason = error.code if error.code in {"session_unavailable", "session_mismatch", "session_not_ready", "run_already_active", "session_registration_changed", "session_root_invalid",
                "run_state_conflict", "capability_unavailable", "credentials_unavailable", "effective_profile_changed",
                "legacy_executor_player_unsupported", "macro_mode_rejects_unit_control_evidence",
                "model_context_capacity_exceeded_shorten_style", "model_context_capacity_provider_unavailable"} else "session_not_ready"
            return dict(ready=False, session_id=None, ready_token=None, expires_at=None, reason_code=reason)
        except Exception:
            return dict(ready=False, session_id=None, ready_token=None, expires_at=None, reason_code="session_not_ready")

    def _launch(self, run_id):
        identifier(run_id)
        with self._lock:
            row = self._db.execute("SELECT * FROM launches WHERE run_id=?", (run_id,)).fetchone()
        if row is None:raise ContractError("run_not_found")
        return row

    def run_start(self, profile, args, request_id):
        identifier(request_id)
        fingerprint = content_hash(dict(profile_id=profile["profile_id"], revision=profile["revision"],
            effective_hash=profile["effective"]["effective_hash"], args=dict(args)))
        with self._lock:
            existing = self._db.execute("SELECT * FROM launches WHERE request_id=?", (request_id,)).fetchone()
        if existing is not None:
            if existing["fingerprint"] != fingerprint:raise ContractError("request_id_conflict")
            return self.run_status(dict(run_id=existing["run_id"]), request_id)
        token_hash = hashlib.sha256(args["ready_token"].encode()).hexdigest()
        with self._lock:
            ready = self._db.execute("SELECT * FROM readiness WHERE token_hash=?", (token_hash,)).fetchone()
        if ready is None:raise ContractError("readiness_invalid")
        if self.now_ms() >= ready["expires_at"]:raise ContractError("readiness_expired")
        binding = SessionBinding.from_dict(json.loads(ready["binding_json"]))
        if (args["session_id"] != binding.session_id or ready["profile_id"] != profile["profile_id"]
            or ready["revision"] != profile["revision"] or ready["effective_hash"] != profile["effective"]["effective_hash"]):
            raise ContractError("session_changed")
        registration = self._registration()
        require_macro_evidence(registration)
        try:
            admission = self.checks.check(registration, profile, ready["host_id"], self.state_dir, self.store.library_path, self.limits)
            if isinstance(admission, Admission) and admission.capabilities.get('native_macro') is True:
                from dataclasses import replace
                from .macro_strategic_client_v1 import preflight_capabilities
                admission=replace(admission,capabilities=preflight_capabilities(admission.capabilities))
        except ContractError as error:
            if error.code in {"session_unavailable", "session_mismatch", "session_not_ready", "run_already_active",
                              "capability_unavailable", "credentials_unavailable", "effective_profile_changed", "run_state_conflict",
                              "legacy_executor_player_unsupported", "model_context_capacity_exceeded_shorten_style",
                              "model_context_capacity_provider_unavailable"}:
                raise
            raise ContractError("session_not_ready") from None
        except Exception:
            raise ContractError("session_not_ready") from None
        if admission.binding != binding or admission.admission_hash != ready["admission_hash"]:
            raise ContractError("session_changed")
        self._predispatch(profile, ready["expires_at"], registration)
        # The client knows this ID even if the start response is lost. A timeout
        # may query status(request_id); it must never resend a new start intent.
        run_id = request_id
        if self.journal.unresolved_for_session(binding.public(), exclude_run_id=run_id):
            raise ContractError("run_state_conflict")
        # The index stores only discovery metadata. All dispatch states and
        # receipts below are owned by the shared command journal.
        session, _ = _object(registration.session_path)
        output = Path(session["run_directory"]).resolve() / "battle-host"
        with self._transaction():
            # Source preparation takes this same index write lock. Re-read the
            # token and source after acquiring it; a completed earlier native
            # check cannot bridge a concurrent registration replacement.
            current_ready=self._db.execute('SELECT * FROM readiness WHERE token_hash=?',(token_hash,)).fetchone()
            if current_ready is None or dict(current_ready)!=dict(ready):
                raise ContractError('readiness_invalid')
            if self._registration()!=registration:
                raise ContractError('session_changed')
            collided = None
            try:
                channel = binding.public(); channel.pop("host_id")
                self._db.execute("INSERT INTO launches VALUES (?,?,?,?,?,?,?)", (run_id, request_id, fingerprint,
                    str(registration.session_path), str(output), ready["binding_json"], content_hash(channel)))
            except sqlite3.IntegrityError:
                collided = self._db.execute("SELECT * FROM launches WHERE request_id=?", (request_id,)).fetchone()
                if collided is None or collided["fingerprint"] != fingerprint:
                    raise ContractError("request_id_conflict") from None
        if collided is not None:
            return self._status(collided)
        try:
            return self._dispatch_launch(profile, request_id, run_id, binding, admission, registration, ready["expires_at"])
        except BaseException as error:
            # The run ID is already durable and must remain queryable even if
            # draft IO or journal claiming fails before Popen. The UI retains
            # this ID and queries; no subsequent call resumes this launch.
            try:
                cancelled=self._cancel_reserved_launch(self._launch(run_id),
                    error.code if isinstance(error,ContractError) else 'launch_preparation_failed')
                if cancelled:return self._status(self._launch(run_id))
            except JournalError:pass
            raise ContractError("run_state_conflict") from None

    def _cancel_reserved_launch(self,row,reason):
        command=self.journal.get_command(row['run_id'],row['request_id'])
        if command['operation']!='host_start' or command['status']!='reserved':return False
        # The journal's atomic transition refuses cancellation after dispatch
        # has been claimed. A racing launcher then cannot reach Popen.
        self.journal.record_outcome(row['run_id'],row['request_id'],'cancelled',dict(
            reason_code='host_launch_cancelled_before_dispatch',preparation_reason_code=reason,
            host_spawn_attempted=False,native_delivery_attempted=False))
        return True

    def _predispatch(self, profile, expires_at, registration=None):
        if self.now_ms() >= expires_at:raise ContractError("readiness_expired")
        if not self.caller_alive():raise ContractError("adapter_unavailable")
        current = self.store.get_profile(profile["profile_id"])["profile"]
        if (not current["validation"]["ok"] or current["revision"] != profile["revision"]
            or current["library_hash"] != profile["library_hash"]
            or current["effective"]["effective_hash"] != profile["effective"]["effective_hash"]):
            raise ContractError("effective_profile_changed")
        current=self._registration()
        if registration is not None and current!=registration:
            raise ContractError('session_changed')

    def _dispatch_launch(self, profile, request_id, run_id, binding, admission, registration, expires_at):
        require_macro_evidence(registration)
        self.journal.register_run(run_id, binding.public())
        self.journal.reserve_command(run_id, request_id, "host_start", dict(profile_id=profile["profile_id"],
            profile_revision=profile["revision"], effective_hash=profile["effective"]["effective_hash"], admission_hash=admission.admission_hash,
            execution_limits=self.limits.public(), session_summary=dict(admission.session),
            capabilities={key: admission.capabilities[key] for key in ("control_mode", "native_macro", "native_transport_protocol", "available_macro_actions", "macro_production_counts", "base_defense_granted", "base_defense_goal", "group_roles_granted", "supported_units", "supported_foci", "tactics_supported", "runtime_tactical_supported", "runtime_recovery_supported", "runtime_purposes")
                          if key in admission.capabilities}))
        draft_path = self.state_dir / "runs" / run_id / "commander-draft.json"
        # Resolve the same model before storing the host input; no credentials.
        _atomic(draft_path, dict(profile["draft"], model=profile["effective"]["model"]))
        if registration.macro_bundle is not None:
            _atomic(draft_path.with_name('binding.json'),binding.public())
            arguments=['--session',str(registration.session_path),'--macro-bundle',str(registration.macro_bundle),
                '--library',str(self.store.library_path),'--commander-draft',str(draft_path),
                '--profile-state-dir',str(self.state_dir),'--binding',str(draft_path.with_name('binding.json')),
                '--ledger',str(self.ledger_path),'--run-id',run_id]
            command=script_command(INTEGRATION/'macro_host.py',arguments,python=self.python_path)
        else:
            arguments = ["--control-mode", CONTROL_MODE, "--session", str(registration.session_path),
            "--acceptance-root", str(self.registration_root),
            "--commander", binding.commander_id, "--player", str(binding.player_id), "--library", str(self.store.library_path),
            "--commander-draft", str(draft_path), "--evidence", str(registration.production_report),
            "--persistent-evidence", str(registration.persistent_status), "--execute", "--runtime-ledger", str(self.ledger_path),
            "--runtime-run-id", run_id, "--runtime-host-id", binding.host_id,
            "--total-budget", str(self.limits.production_total_budget), "--reserve", str(self.limits.reserve_floor)]
            command = script_command(INTEGRATION / "battle_host.py", arguments, python=self.python_path)
        self._predispatch(profile, expires_at, registration)
        self.journal.mark_dispatching(run_id, request_id)
        try:
            if not self.caller_alive():raise ContractError("adapter_unavailable")
            child = self.spawner.spawn(command, draft_path.with_name("host.log"), admission)
            self._children[run_id] = child
            host_start = self.spawner.identity(child.pid)
            if not host_start:raise ContractError("run_state_conflict")
            self.journal.record_outcome(run_id, request_id, "started", dict(host_pid=int(child.pid),
                host_start_time=host_start, reason_code="host_process_spawned", profile_revision=profile["revision"],
                effective_hash=profile["effective"]["effective_hash"]))
        except BaseException:
            # Popen/pipe failure may follow successful process creation; delivery
            # is unknown, never mark safely failed or automatically retry.
            self.journal.record_outcome(run_id, request_id, "uncertain", dict(reason_code="host_launch_uncertain"))
            raise ContractError("run_state_conflict") from None
        return dict(run_id=run_id, session_id=binding.session_id, state="starting")

    def _release_receipt(self, run_id, binding, host_receipt):
        starts=self.journal.commands_for_run(run_id,operation='host_start')
        if any(row['payload'].get('capabilities',{}).get('native_macro') is True for row in starts):
            from .macro_desktop import released
            return released(self,run_id,binding,host_receipt)
        if self.journal.unresolved(run_id):return False
        from .runtime_epoch_release import projection_verified
        if projection_verified(self,run_id,binding,host_receipt):return True
        reviews=self.journal.commands_for_run(run_id,operation='review_idle_runtime_release')
        idle_operations={'host_start','host_stop','produce','stop','review_idle_runtime_release'}
        idle_only=all(r['operation'] in idle_operations for r in self.journal.commands_for_run(run_id))
        for review in reviews:
            receipt=review.get('receipt')or{}
            if (idle_only and review['status']=='released' and receipt.get('reason_code')=='idle_runtime_host_native_entries_independently_verified'
                    and receipt.get('binding_hash')==binding.binding_hash and receipt.get('host_pid')==host_receipt.get('host_pid')
                    and receipt.get('host_start_time')==host_receipt.get('host_start_time')
                    and receipt.get('native_release_verified') is True and receipt.get('no_control_acquired') is True):
                try:
                    path=self.state_dir/'runs'/run_id/'idle-runtime-release-review.json'
                    proof,digest=_object(path,4*1024*1024)
                    if (digest==receipt.get('review_sha256') and proof.get('kind')=='idle_runtime_host_release_review'
                            and proof.get('binding')==binding.public() and proof.get('run_id')==run_id
                            and proof.get('host_pid')==host_receipt.get('host_pid') and proof.get('host_start_time')==host_receipt.get('host_start_time')
                            and proof.get('native_release_verified') is True and proof.get('no_control_acquired') is True
                            and proof.get('physical_home_claimed') is False and proof.get('mission_effect_granted') is False):return True
                except (OSError,ValueError,TypeError):pass
        start = self.journal._db.execute("SELECT payload FROM commands WHERE run_id=? AND operation='host_start'",(run_id,)).fetchone()
        if start:
            capabilities = json.loads(start['payload']).get('capabilities',{})
            if capabilities.get('tactics_supported') or capabilities.get('runtime_tactical_supported'):return False
        rows = self.journal._db.execute("SELECT operation,receipt FROM commands WHERE run_id=? AND status='released'", (run_id,)).fetchall()
        for row in rows:
            receipt = json.loads(row['receipt'])
            facts = receipt.get('facts') or {}
            if (row['operation'] == 'stop' and receipt.get('reason_code') == 'native_receipt_verified'
                and facts.get('source') == 'native_persistent_production' and facts.get('production_release_verified') is True
                and facts.get('native_phase') == 2 and facts.get('native_error') == 0
                and facts.get('restore_mask') == 31 and facts.get('active_callbacks') == 0):
                return True
            if (row['operation'] == 'review_host_release'
                and receipt.get('reason_code') == 'unattached_host_native_entries_independently_verified'
                and receipt.get('binding_hash') == binding.binding_hash
                and receipt.get('host_pid') == host_receipt.get('host_pid')
                and receipt.get('host_start_time') == host_receipt.get('host_start_time')
                and receipt.get('native_release_verified') is True
                and isinstance(receipt.get('review_sha256'),str) and len(receipt['review_sha256']) == 64):
                return True
        return False

    def _status(self, row):
        binding = SessionBinding.from_dict(json.loads(row["binding_json"]))
        try:
            command = self.journal.get_command(row["run_id"], row["request_id"])
        except JournalError:
            return dict(run_id=row["run_id"], session_id=binding.session_id, state="uncertain", native_release_verified=False)
        result = dict(run_id=row["run_id"], session_id=binding.session_id,
                      state="uncertain" if command["status"] in ("reserved", "dispatching", "uncertain") else "starting",
                      native_release_verified=False)
        for key in ("profile_id", "profile_revision", "effective_hash", "execution_limits"):
            if key in command["payload"]:result[key] = command["payload"][key]
        if "session_summary" in command["payload"]:result["session"] = command["payload"]["session_summary"]
        if "capabilities" in command["payload"]:result["capabilities"] = command["payload"]["capabilities"]
        result["events"], result["events_cursor"] = recent_events(self.journal, row["run_id"],
            expected=command["payload"], binding=binding)
        receipt=command.get('receipt') or {}
        if (type(command['payload'].get('capabilities',{}).get('native_transport_protocol')) is int
                and command['payload']['capabilities']['native_transport_protocol'] in (5,6)
                and type(receipt.get('host_pid')) is int and isinstance(receipt.get('host_start_time'),str)
                and self.spawner.identity(receipt['host_pid'])!=receipt['host_start_time']):
            try:
                if command['payload']['capabilities']['native_transport_protocol']==6:
                    from .native6_recovery_route import recover_after_stop
                else:from .native5_orphan_return_v1 import recover_after_stop
                if recover_after_stop(self,row,binding,receipt,_atomic):
                    result.update(state='fault',reason_code='host_process_lost_control_returned',
                        host_process_alive=False,status_stale=True,native_release_verified=True)
                    return result
            except (OSError,ValueError,KeyError,TypeError,OverflowError,ContractError):
                # Missing or inaccessible evidence cannot be repaired into
                # success. Native state is only sampled again on a later query.
                pass
        if (command['operation']=='host_start' and command['status']=='cancelled'
                and receipt.get('reason_code')=='host_launch_cancelled_before_dispatch'
                and receipt.get('host_spawn_attempted') is False and receipt.get('native_delivery_attempted') is False
                and len(self.journal.commands_for_run(row['run_id']))==1):
            result.update(state='stopped',reason_code='host_launch_cancelled_before_dispatch',
                native_release_verified=True,no_native_execution_started=True)
            return result
        try:
            status, _ = _object(Path(row["output_path"]) / "host-status.json", 1024 * 1024)
            macro=command['payload'].get('capabilities',{}).get('native_macro') is True
            runtime = status.get('runtime_macro' if macro else "runtime_production", {})
            if (runtime.get("run_id") != row["run_id"] or runtime.get("binding_hash") != binding.binding_hash
                or status.get("session_id") != binding.session_id or status.get("pid") != binding.game_process_id
                or status.get("process_start") != binding.game_process_start):
                raise ValueError()
            receipt = command.get("receipt") or {}
            if status.get("host_pid") != receipt.get("host_pid") or status.get("host_start_time") != receipt.get("host_start_time"):
                raise ValueError()
            host_alive = self.spawner.identity(receipt["host_pid"]) == receipt["host_start_time"]
            if not host_alive and status.get("state") not in ("stopped", "fault", "result_candidate"):
                raise ValueError()
            result["state"] = status["state"]
            reason=status.get('reason_code')
            if isinstance(reason,str) and re.fullmatch(r'[a-z][a-z0-9_]{0,79}',reason):
                result['reason_code']=reason
            result['host_process_alive']=host_alive
            result['status_age_ms']=max(0,self.now_ms()-(Path(row['output_path'])/'host-status.json').stat().st_mtime_ns//1_000_000)
            result['status_stale']=not host_alive or result['status_age_ms']>=10_000
            if macro:
                result['current_plan']=project_plan(status.get('current_plan'))
                # Identity was checked above. This read-only record exposes
                # strategic authority and missing intents without inheriting
                # historical precision grants or changing dispatch/release.
                from .macro_strategic_client_v1 import project as project_strategic_client
                try:
                    result['strategic_client']=project_strategic_client(status, result.get('capabilities', {}))
                except ContractError:
                    result['strategic_client_unavailable']=True
                if status.get('macro_strategy') is not None:
                    try:
                        _module('macro_strategy',directory=ROOT/'strategy')
                        from .macro_strategy_public import project_macro_strategy_state
                        result['macro_strategy']=project_macro_strategy_state(status['macro_strategy'])
                    except (ContractError,ImportError):
                        # Reject only this optional record; never return raw
                        # strategy state or erase the independent run status.
                        result['macro_strategy_unavailable']=True
                if status.get('macro_unified_feedback') is not None:
                    from .strategic_unified_feedback_v5 import project_unified_feedback
                    try:result['macro_unified_feedback']=project_unified_feedback(status['macro_unified_feedback'])
                    except ContractError:result['macro_unified_feedback_unavailable']=True
                feedback=status.get('macro_feedback') or {}
                if feedback.get('status') in {'native_budget_adopted','native_budget_pending','native_delegation_observed','native_budget_clearing'}:
                    result['macro_feedback']=dict(status=feedback['status'],selected_policy=feedback.get('selected_policy')
                        if feedback.get('selected_policy') in ('budgeteconomy','budgetarmy','budgettech') else None)
                production=status.get('macro_production_feedback')
                if production:
                    from .macro_production_public import compact_production_feedback
                    try:result['macro_production_feedback']=compact_production_feedback(production,
                        status.get('latest_snapshot',{}).get('game_time_seconds',-100))
                    except ContractError:pass
                construction=status.get('macro_construction_feedback')
                if construction:
                    from .macro_construction_feedback import compact_construction_feedback
                    try:result['macro_construction_feedback']=compact_construction_feedback(construction,
                        status.get('latest_snapshot',{}).get('game_time_seconds',-100))
                    except ContractError:pass
                scouting=status.get('macro_scouting_feedback')
                if scouting:
                    from .macro_scouting import compact_scout_feedback
                    try:result['macro_scouting_feedback']=compact_scout_feedback(scouting,
                        status.get('latest_snapshot',{}).get('game_time_seconds',-100))
                    except ContractError:pass
                regional=status.get('macro_regional_feedback')
                if regional:
                    from .macro_regions import compact_regional_feedback
                    try:result['macro_regional_feedback']=compact_regional_feedback(regional,
                        status.get('latest_snapshot',{}).get('game_time_seconds',-100))
                    except ContractError:pass
                # These are bounded records, separate from run-level release
                # and from any authority to dispatch another request.
                from .macro_expansion_diagnostics_v4 import expansion_record,admission_record
                for key,project in (('macro_expansion_feedback',expansion_record),('macro_resource_feedback',admission_record)):
                    if status.get(key) is None:continue
                    try:result[key]=project(status[key])
                    except ContractError:result[key+'_unavailable']=True
                if status.get('macro_expansion_blocked') is not None:
                    from .macro_expansion_availability_v1 import availability_record
                    try:result['macro_expansion_availability']=availability_record(status['macro_expansion_blocked'])
                    except ContractError:result['macro_expansion_availability_unavailable']=True
            latest = status.get("latest_snapshot")
            if isinstance(latest, dict):
                public = {}
                for key in ("snapshot_id", "game_time_seconds"):
                    value = latest.get(key)
                    if type(value) in (int, float) and 0 <= value <= 2**53 - 1:public[key] = value
                if type(latest.get("paused")) is bool:public["paused"] = latest["paused"]
                credits = latest.get("resources", {}).get("credits") if isinstance(latest.get("resources"), dict) else None
                if type(credits) in (int, float) and 0 <= credits <= 2**53 - 1:public["resources"] = dict(credits=credits)
                result["latest_snapshot"] = public
            execution = status.get("execution")
            if isinstance(execution, dict):
                public = {key: execution[key] for key in ("enabled", "dry_run", "executor_connected") if type(execution.get(key)) is bool}
                if type(execution.get("remaining_budget")) is int and execution["remaining_budget"] >= 0:
                    public["remaining_budget"] = execution["remaining_budget"]
                result["execution"] = public
            if not host_alive and status["state"] in ("stopped", "fault", "result_candidate") and command["status"] == "started":
                self.journal.record_outcome(row["run_id"], row["request_id"], "completed",
                    dict(receipt, reason_code="host_process_ended", final_host_state=status["state"], native_release_verified=False))
            if not host_alive and status['state'] in ('stopped','fault','result_candidate'):
                result['native_release_verified'] = self._release_receipt(row['run_id'],binding,receipt)
            expected = command["payload"]
            for key in ("profile_application", "profile_consumption"):
                receipt = status.get(key)
                if receipt is not None:
                    if (not isinstance(receipt, dict) or receipt.get("profile_id") != expected["profile_id"]
                        or receipt.get("profile_revision") != expected["profile_revision"]
                        or receipt.get("effective_hash") != expected["effective_hash"]):
                        result["state"] = "fault"
                        result["reason_code"] = "effective_profile_changed"
                    else:result[key] = project_fields(receipt)
            if "metrics" in status:
                projected = project_fields(status["metrics"])
                result["metrics"] = {key: value for key, value in projected.items()
                    if key in {"requests", "accepted", "rejected", "timeouts", "adapter_errors", "plan_changes"}}
            result["tasks"], result["tasks_cursor"] = project_tasks(status.get("jobs", []))
            preparation=(status.get('runtime_model_tasks')or{}).get('preparation')
            if isinstance(preparation,dict):result['local_preparation']=project_fields(preparation)
            counters = project_fields(status.get("task_counters", {}))
            result["task_counters"] = {key: value for key, value in counters.items()
                                      if key in {"dispatches", "started", "completed", "failed", "blocked"}}
            consumption = result.get("profile_consumption")
            if consumption is not None:
                result["consumption"] = dict(calls_started=consumption.get("calls_started", 0),
                    responses_returned=consumption.get("responses_returned", 0),
                    model_response_received=consumption.get("model_response_received") is True and consumption.get("responses_returned", 0) > 0,
                    real_network_verified=consumption.get("real_network_verified", False))
        except (OSError, ValueError, TypeError, KeyError):
            child = self._children.get(row["run_id"])
            receipt = command.get("receipt") or {}
            if ((child is not None and child.poll() is not None) or
                command["status"] == "started" and self.spawner.identity(receipt.get("host_pid", 0)) != receipt.get("host_start_time")):
                result["state"] = "uncertain"
        return result

    def run_status(self, args, request_id):
        return self._status(self._launch(args["run_id"]))

    def run_stop(self, args, request_id):
        row = self._launch(args["run_id"])
        binding = SessionBinding.from_dict(json.loads(row["binding_json"]))
        if args["session_id"] != binding.session_id:raise ContractError("session_mismatch")
        session, _ = _object(row["session_path"])
        if (session.get("session_id") != binding.session_id or session.get("pid") != binding.game_process_id
            or session.get("start_time") != binding.game_process_start):raise ContractError("session_changed")
        try:
            if self._cancel_reserved_launch(row,'stop_requested_before_dispatch'):return self._status(row)
        except JournalError:pass
        record = self.journal.reserve_command(row["run_id"], request_id, "host_stop", dict(session_id=binding.session_id))
        if record["created"]:
            self.journal.mark_dispatching(row["run_id"], request_id)
            try:
                starts=self.journal.commands_for_run(row['run_id'],operation='host_start')
                unified=any(type(r['payload'].get('capabilities',{}).get('native_transport_protocol')) is int
                    and r['payload']['capabilities']['native_transport_protocol'] in (5,6) for r in starts)
                if unified:
                    from .strategic_stop_gate_v1 import StrategicStopGateV1
                    StrategicStopGateV1(row['run_id'],binding,Path(row['output_path'])).publish_stop(_atomic)
                else:_atomic(Path(row['output_path'])/'stop.json',dict(session_id=binding.session_id))
                self.journal.record_outcome(row["run_id"], request_id, "completed", dict(reason_code="host_stop_requested",
                    native_release_verified=False))
            except BaseException:
                self.journal.record_outcome(row["run_id"], request_id, "uncertain", dict(reason_code="host_stop_uncertain"))
                raise ContractError("run_state_conflict") from None
        return self._status(row)

    def diagnostics_export(self, args, request_id):
        row = self._launch(args["run_id"])
        try:
            command = self.journal.get_command(row["run_id"], row["request_id"])
            binding = SessionBinding.from_dict(json.loads(row["binding_json"]))
            run_dir = self.state_dir / "runs" / row["run_id"]
            profile = None
            try:
                candidate = normalize_profile(load_commander_draft(run_dir / "commander-draft.json")).public()
                if (candidate["profile_id"] == binding.commander_id and candidate["revision"] == command["payload"]["profile_revision"]
                    and candidate["effective_hash"] == command["payload"]["effective_hash"]):profile = candidate
            except ContractError:pass
            output = Path(row["output_path"])
            files = [("commander_draft", run_dir / "commander-draft.json", self.state_dir),
                     ("host_log", run_dir / "host.log", self.state_dir)]
            files.extend((name, output / filename, output) for name, filename in (
                ("host_status", "host-status.json"), ("host_events", "host-events.jsonl"), ("plans", "plans.jsonl"),
                ("jobs", "jobs.json"),('macro_feedback','macro-feedback.jsonl'),('macro_release','macro-release.json'),
                ('strategic_admission','strategic-admission.jsonl'),('strategic_stop','stop.json'),
                ('native_no_attachment','native-no-attachment.json')))
            files.extend((name, output / filename, output) for name, filename in (
                ('native_orphan_return','native-orphan-return.json'),
                ('native_orphan_journal','native-orphan-journal.bin')))
            session_dir = Path(row["session_path"]).parent
            files.extend((name, session_dir / filename, session_dir) for name, filename in (
                ("persistent_status", "persistent-production-status.json"), ("persistent_audit", "persistent-production.jsonl"),
                ("session", Path(row["session_path"]).name)))
            return create_export(self.state_dir, run_id=row["run_id"], request_id=request_id, binding=binding,
                                 profile=profile, status=self._status(row), journal=self.journal, raw_files=files)
        except (OSError, ValueError, KeyError):
            raise ContractError("diagnostics_unavailable") from None
