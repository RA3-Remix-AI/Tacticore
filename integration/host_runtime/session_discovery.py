"""Trusted, read-only session discovery and durable source preparation.

The native bootstrap supplies fixed paths, process enumeration and a read-only
match probe. RPC callers supply only an opaque candidate ID. This broker never
starts a game, launches a host or grants a capability; run.check remains required.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Callable, Iterable, Mapping
import uuid

from .contracts import ContractError, canonical_json, identifier, object_fields, sha256

TERMINAL = frozenset({'stopped', 'completed', 'fault', 'result_candidate'})
MAX_CANDIDATES = 8


@dataclass(frozen=True)
class TrustedFiles:
    game: Path
    game_sha256: str
    mod_config: Path
    mod_config_sha256: str
    mod_big: Path
    mod_sha256: str
    registry: Path
    registry_sha256: str
    macro_bundle: Path
    macro_bundle_sha256: str
    package_report: Path
    package_report_sha256: str


@dataclass(frozen=True)
class DiscoveryPolicy:
    files: TrustedFiles
    session_root: Path
    state_dir: Path
    commander_id: str
    origin_region: str
    native_epoch: int
    map_id: str = 'map_mp_2_black1b'
    display_map: str = 'TemplePrime'
    faction: str = 'Soviet'
    player_id: int = 3
    opponent_player_id: int = 4
    observer_player_id: int = 2
    candidate_ttl_seconds: int = 90


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    creation_filetime: int
    start_time: str
    executable: Path
    mod_config: Path


@dataclass(frozen=True)
class MatchObservation:
    pid: int
    creation_filetime: int
    game_instance_id: str
    map_id: str
    faction: str
    player_id: int
    opponent_player_id: int
    observer_player_id: int
    commander_id: str
    origin_region: str
    native_epoch: int
    ready: bool
    paused: bool = False
    ended: bool = False


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    state: str
    native_release_verified: bool
    unresolved_count: int
    pid: int
    creation_filetime: int|None
    native_epoch: int|None
    native_delivery_attempted: bool = True
    history_protocol:str='macro_transport_epoch_v1'
    history_review_sha256:str|None=None
    original_process_start:str|None=None
    historical_unknown_count:int=0


def _fail(code):
    raise ContractError(code)


def _int(value, minimum=1):
    return type(value) is int and minimum <= value < 2**64


def _local_path(value, *, directory=False):
    path = Path(value)
    if not path.is_absolute() or str(path).startswith('\\\\'):
        _fail('discovery_policy_invalid')
    try:
        if path.resolve(strict=True) != path or (not path.is_dir() if directory else not path.is_file()):
            _fail('discovery_policy_invalid')
        for item in (path, *path.parents):
            if item.is_symlink() or getattr(item.lstat(), 'st_file_attributes', 0) & 0x400:
                _fail('discovery_policy_invalid')
    except OSError:
        _fail('discovery_source_unavailable')
    return path


def _digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def _hash(value):
    return hashlib.sha256(canonical_json(value).encode('utf8')).hexdigest()


def _identity(value):
    if not isinstance(value, ProcessIdentity):
        _fail('session_probe_invalid')
    if not _int(value.pid) or not _int(value.creation_filetime):
        _fail('session_probe_invalid')
    try:
        if not isinstance(value.start_time, str) or len(value.start_time) > 64:
            raise ValueError()
        parsed = datetime.fromisoformat(value.start_time)
        if parsed.tzinfo is None:
            raise ValueError()
    except ValueError:
        _fail('session_probe_invalid')
    return dict(pid=value.pid, creation_filetime=value.creation_filetime, start_time=value.start_time,
                executable=str(value.executable), mod_config=str(value.mod_config))


class SessionDiscovery:
    def __init__(self, policy: DiscoveryPolicy,
                 enumerate_processes: Callable[[], Iterable[ProcessIdentity]],
                 probe_match: Callable[[ProcessIdentity, DiscoveryPolicy], MatchObservation],
                 register_source: Callable[[Path, Path], Mapping],
                 run_records: Callable[[], Iterable[RunRecord]], *, clock=time.monotonic):
        self.policy = policy
        self.enumerate_processes = enumerate_processes
        self.probe_match = probe_match
        self.register_source = register_source
        self.run_records = run_records
        self.clock = clock
        self._lock = threading.RLock()
        self._candidates = {}
        self._validate_policy()
        database = policy.state_dir / 'session-discovery.sqlite3'
        if database.exists() or database.is_symlink():
            _local_path(database)
        self._db = sqlite3.connect(database)
        self._db.row_factory = sqlite3.Row
        self._db.execute('CREATE TABLE IF NOT EXISTS preparations '
                         '(request_id TEXT PRIMARY KEY,args_hash TEXT NOT NULL,candidate_json TEXT NOT NULL,'
                         'state TEXT NOT NULL,session_sha256 TEXT,receipt_json TEXT)')
        self._db.execute('CREATE UNIQUE INDEX IF NOT EXISTS preparations_snapshot ON preparations(candidate_json)')
        self._db.execute('CREATE TABLE IF NOT EXISTS preparation_requests '
                         '(request_id TEXT PRIMARY KEY,args_hash TEXT NOT NULL,preparation_id TEXT NOT NULL)')
        self._db.commit()

    def close(self):
        self._db.close()

    def _validate_policy(self):
        p = self.policy
        if not isinstance(p, DiscoveryPolicy) or not isinstance(p.files, TrustedFiles):
            _fail('discovery_policy_invalid')
        identifier(p.commander_id)
        if (p.map_id != 'map_mp_2_black1b' or p.display_map != 'TemplePrime' or p.faction != 'Soviet'
                or (p.player_id, p.opponent_player_id, p.observer_player_id) != (3, 4, 2)
                or not _int(p.native_epoch) or type(p.candidate_ttl_seconds) is not int
                or not 1 <= p.candidate_ttl_seconds <= 300
                or not isinstance(p.origin_region, str) or len(p.origin_region) > 64
                or not p.origin_region.startswith('region_')):
            _fail('discovery_policy_invalid')
        _local_path(p.session_root, directory=True)
        _local_path(p.state_dir, directory=True)
        self._source_pins()

    def _source_pins(self):
        _local_path(self.policy.session_root, directory=True)
        _local_path(self.policy.state_dir, directory=True)
        f = self.policy.files
        pins = {}
        for name, digest_name in (('game', 'game_sha256'), ('mod_config', 'mod_config_sha256'),
                                  ('mod_big', 'mod_sha256'), ('registry', 'registry_sha256'),
                                  ('macro_bundle', 'macro_bundle_sha256'), ('package_report', 'package_report_sha256')):
            path, expected = _local_path(getattr(f, name)), getattr(f, digest_name)
            sha256(expected)
            try:
                actual = _digest(path)
            except OSError:
                _fail('discovery_source_unavailable')
            if actual != expected:
                _fail('discovery_source_changed')
            pins[name] = dict(source=str(path), sha256=actual)
        # Pin the non-file qualification fields as well: no silent broadening.
        pins['scope'] = dict(commander_id=self.policy.commander_id, origin_region=self.policy.origin_region,
                             native_epoch=self.policy.native_epoch, map_id=self.policy.map_id,
                             player_id=self.policy.player_id, faction=self.policy.faction)
        return _hash(pins)

    def _processes(self):
        try:
            rows = list(self.enumerate_processes())
        except Exception:
            _fail('session_discovery_unavailable')
        if len(rows) > MAX_CANDIDATES:
            _fail('session_discovery_too_many_processes')
        result, seen = [], set()
        for value in rows:
            row = _identity(value)
            if row['pid'] in seen:
                _fail('session_probe_invalid')
            seen.add(row['pid'])
            if (Path(value.executable) != self.policy.files.game
                    or Path(value.mod_config) != self.policy.files.mod_config):
                continue
            result.append(value)
        return result

    def _observe(self, process):
        try:
            value = self.probe_match(process, self.policy)
        except ContractError:
            raise
        except Exception:
            _fail('session_probe_unavailable')
        if not isinstance(value, MatchObservation):
            _fail('session_probe_invalid')
        if (value.pid != process.pid or type(value.pid) is not int
                or value.creation_filetime != process.creation_filetime or type(value.creation_filetime) is not int
                or not isinstance(value.game_instance_id, str) or not 1 <= len(value.game_instance_id) <= 128
                or any(type(getattr(value, name)) is not bool for name in ('ready', 'paused', 'ended'))):
            _fail('session_probe_invalid')
        expected = dict(map_id=self.policy.map_id, faction=self.policy.faction, player_id=3,
                        opponent_player_id=4, observer_player_id=2, commander_id=self.policy.commander_id,
                        origin_region=self.policy.origin_region, native_epoch=self.policy.native_epoch)
        if any(getattr(value, key) != item or type(getattr(value, key)) is not type(item)
               for key, item in expected.items()):
            _fail('session_scope_unsupported')
        if not value.ready or value.ended:
            _fail('session_not_ready')
        if value.paused:
            _fail('session_paused')
        return value

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            _fail('session_discovery_unavailable')
        return value

    def _public(self, candidate_id, expires_at):
        return dict(candidate_id=candidate_id, display_name='TemplePrime / P3 苏军',
                    map=self.policy.display_map, faction=self.policy.faction,
                    player_id=self.policy.player_id, expires_in_seconds=max(0, int(expires_at-self._now())),
                    requires_preflight=True)

    def discover(self, args=None, request_id=None):
        object_fields({} if args is None else args, set())
        if request_id is not None:
            identifier(request_id)
        with self._lock:
            pin = self._source_pins()
            self._candidates = {key: value for key, value in self._candidates.items()
                                if value['expires_at'] > self._now()}
            found, issues = [], set()
            for process in self._processes():
                try:
                    observation = self._observe(process)
                except ContractError as error:
                    # A probe exception is never allowed to leak path/address/message.
                    code = error.code if error.code in {'session_scope_unsupported', 'session_not_ready',
                        'session_paused', 'session_probe_invalid'} else 'session_probe_unavailable'
                    issues.add(code)
                    continue
                snapshot = dict(process=_identity(process), observation=asdict(observation), source_pin=pin)
                existing = next((key for key, value in self._candidates.items()
                                 if value['snapshot'] == snapshot), None)
                key = existing or str(uuid.uuid4())
                if not existing:
                    self._candidates[key] = dict(snapshot=snapshot, expires_at=self._now()+self.policy.candidate_ttl_seconds)
                found.append(self._public(key, self._candidates[key]['expires_at']))
            # Keep only currently discovered candidates, never an unbounded history.
            visible = {row['candidate_id'] for row in found}
            self._candidates = {key: value for key, value in self._candidates.items() if key in visible}
            return dict(schema_version=1, candidates=found, issues=sorted(issues),
                        state='select_session' if found else 'waiting_for_supported_session',
                        native_execution_started=False)

    def _revalidate(self, snapshot):
        if self._source_pins() != snapshot['source_pin']:
            _fail('discovery_source_changed')
        processes = [row for row in self._processes() if _identity(row) == snapshot['process']]
        if len(processes) != 1:
            _fail('session_changed')
        if asdict(self._observe(processes[0])) != snapshot['observation']:
            _fail('session_changed')
        self._require_released(processes[0])
        return processes[0]

    def _require_released(self, process):
        try:
            rows = list(self.run_records())
        except Exception:
            _fail('run_history_unverifiable')
        seen = set()
        for row in rows:
            if (not isinstance(row, RunRecord) or not isinstance(row.run_id, str) or row.run_id in seen or not isinstance(row.state, str)
                    or type(row.native_release_verified) is not bool or type(row.native_delivery_attempted) is not bool
                    or not _int(row.pid)
                    or not _int(row.unresolved_count, 0)):
                _fail('run_history_unverifiable')
            if row.history_protocol=='macro_transport_epoch_v1':
                if not _int(row.creation_filetime) or not _int(row.native_epoch):_fail('run_history_unverifiable')
            elif row.history_protocol in ('independently_released_legacy_native_v1','trusted_never_dispatched_host_v1'):
                try:
                    sha256(row.history_review_sha256)
                    original=datetime.fromisoformat(row.original_process_start)
                    if original.tzinfo is None or row.native_epoch is not None:raise ValueError()
                    if row.creation_filetime is not None and not _int(row.creation_filetime):raise ValueError()
                    if row.history_protocol=='trusted_never_dispatched_host_v1' and row.native_delivery_attempted:raise ValueError()
                except (ValueError,TypeError):_fail('run_history_unverifiable')
            else:_fail('run_history_unverifiable')
            try:
                identifier(row.run_id)
            except ContractError:
                _fail('run_history_unverifiable')
            seen.add(row.run_id)
            if row.state not in TERMINAL or not row.native_release_verified or row.unresolved_count != 0:
                _fail('run_state_conflict')
            if (row.native_delivery_attempted and row.pid == process.pid
                    and (row.creation_filetime is None or row.creation_filetime == process.creation_filetime)):
                # Changing a trusted build's epoch number is not proof that this
                # process can safely terminate its retained old native channel.
                _fail('macro_runtime_same_epoch_reattach_unsupported')

    def _session(self, snapshot, request_id):
        process, observation, p = snapshot['process'], snapshot['observation'], self.policy
        folder = p.session_root / ('desktop-'+request_id)
        record = dict(schema_version=1, session_id=str(uuid.uuid5(uuid.UUID(request_id), snapshot['source_pin'])),
                      pid=process['pid'], start_time=process['start_time'],
                      process_creation_filetime=process['creation_filetime'], run_directory=str(folder),
                      game=str(p.files.game), mod_config=str(p.files.mod_config), mod_big=str(p.files.mod_big),
                      mod_sha256=p.files.mod_sha256, registry=str(p.files.registry),
                      macro_package_report=str(p.files.package_report), phase='desktop_macro_session',
                      seed_controlled=False, real_model_calls=0, full_goal_complete=False,
                      discovery=dict(game_instance_id=observation['game_instance_id'], native_epoch=p.native_epoch,
                                     source_fingerprint=snapshot['source_pin']),
                      scenario=dict(map_id=p.map_id, commander_id=p.commander_id, computer_player_index=3,
                                    opponent_player_index=4, observer_player_index=2, participant_count=2,
                                    faction=p.faction, origin_region=p.origin_region))
        return folder/'session.json', record

    def prepare(self, args, request_id):
        value = object_fields(args, {'candidate_id'})
        identifier(value['candidate_id']); identifier(request_id)
        args_hash = _hash(value)
        with self._lock:
            request = self._db.execute('SELECT * FROM preparation_requests WHERE request_id=?', (request_id,)).fetchone()
            if request is not None:
                if request['args_hash'] != args_hash:
                    _fail('request_id_conflict')
                prior = self._db.execute('SELECT * FROM preparations WHERE request_id=?',
                                         (request['preparation_id'],)).fetchone()
                if prior is None:
                    _fail('session_preparation_changed')
                if prior['state'] == 'registered':
                    return json.loads(prior['receipt_json'])
                snapshot = json.loads(prior['candidate_json'])
                preparation_id = prior['request_id']
            else:
                prior = None
                candidate = self._candidates.get(value['candidate_id'])
                if candidate is None or candidate['expires_at'] <= self._now():
                    _fail('session_candidate_expired')
                snapshot = candidate['snapshot']
                preparation_id = request_id
            self._revalidate(snapshot)
            snapshot_json = canonical_json(snapshot)
            if prior is None:
                # Serialize duplicate clicks across backend instances as well as threads.
                with self._db:
                    self._db.execute('BEGIN IMMEDIATE')
                    prior = self._db.execute('SELECT * FROM preparations WHERE candidate_json=?', (snapshot_json,)).fetchone()
                    if prior is None:
                        path, record = self._session(snapshot, preparation_id)
                        digest = _hash(record)
                        self._db.execute('INSERT INTO preparations VALUES (?,?,?,?,?,NULL)',
                                         (preparation_id,args_hash,snapshot_json,'reserved',digest))
                    else:
                        preparation_id = prior['request_id']
                    self._db.execute('INSERT INTO preparation_requests VALUES (?,?,?)',
                                     (request_id,args_hash,preparation_id))
                if prior is not None and prior['state'] == 'registered':
                    return json.loads(prior['receipt_json'])
            path, record = self._session(snapshot, preparation_id)
            digest = _hash(record)
            if prior is not None and prior['session_sha256'] != digest:
                _fail('session_preparation_changed')
            raw = (canonical_json(record)+'\n').encode('utf8')
            file_digest = hashlib.sha256(raw).hexdigest()
            folder = path.parent
            try:
                folder.mkdir()
            except FileExistsError:
                pass
            _local_path(folder, directory=True)
            try:
                with path.open('xb') as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            except FileExistsError:
                _local_path(path)
                if _digest(path) != file_digest:
                    _fail('session_preparation_changed')
            # A PID, match, package or prior-run change while writing cannot be registered.
            self._revalidate(snapshot)
            with self._db:
                self._db.execute("UPDATE preparations SET state='registering' WHERE request_id=?", (preparation_id,))
            # Registration is idempotent metadata binding, never a game/host dispatch.
            # Replaying an interrupted prepare only retries this exact source binding.
            try:
                result = self.register_source(path, self.policy.files.macro_bundle)
            except ContractError:
                raise
            except Exception:
                _fail('session_registration_uncertain')
            if not isinstance(result, Mapping) or result.get('registered') is not True:
                _fail('session_registration_uncertain')
            receipt = dict(schema_version=1, registered=True, session_id=record['session_id'],
                           candidate_id=value['candidate_id'], requires_preflight=True,
                           registration_reload_required=result.get('restart_required') is True,
                           session=dict(id=record['session_id'], map=self.policy.display_map,
                                        faction=self.policy.faction, player_name=self.policy.commander_id),
                           native_execution_started=False)
            with self._db:
                self._db.execute("UPDATE preparations SET state='registered',receipt_json=? WHERE request_id=?",
                                 (canonical_json(receipt),preparation_id))
            return receipt
