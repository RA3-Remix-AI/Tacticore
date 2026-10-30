"""Bounded named JSON-line RPC. Native caller supplies trusted library/state paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Mapping, Protocol

from .contracts import ContractError, canonical_json, identifier, integer, object_fields, sha256, text
from .profile_store import ProfileStore

MAX_LINE_BYTES = 65536
OPERATIONS = frozenset({"profiles.list", "profiles.get", "profiles.save", "connections.list", "session.inspect", "session.discover", "session.prepare",
                        "run.resume", "run.check", "run.start", "run.status", "run.stop", "diagnostics.export"})
BACKEND_ERROR_CODES = frozenset({"adapter_unavailable", "session_unavailable", "session_changed", "session_mismatch",
    "session_not_ready", "readiness_expired", "readiness_invalid", "profile_revision_conflict", "effective_profile_changed",
    "capability_unavailable", "credentials_unavailable", "run_not_found", "run_already_active", "run_state_conflict",
    "request_id_conflict", "backend_operation_failed", "diagnostics_unavailable",
    "discovery_policy_invalid", "discovery_source_unavailable", "discovery_source_changed",
    "session_discovery_unavailable", "session_discovery_too_many_processes", "session_scope_unsupported",
    "session_probe_invalid", "session_probe_unavailable", "session_paused", "session_candidate_expired",
    "run_history_unverifiable", "session_preparation_changed", "session_registration_uncertain",
    "macro_runtime_same_epoch_reattach_unsupported", "session_root_invalid", "session_root_conflict",
    "session_registration_conflict", "session_registration_changed", "macro_bundle_not_qualified",
    "model_context_capacity_exceeded_shorten_style", "model_context_capacity_provider_unavailable"})


class HostBackend(Protocol):
    def session_inspect(self, args: Mapping, request_id: str) -> dict: ...
    def session_discover(self, args: Mapping, request_id: str) -> dict: ...
    def session_prepare(self, args: Mapping, request_id: str) -> dict: ...
    def run_resume(self, args: Mapping, request_id: str) -> dict: ...
    def run_check(self, profile: Mapping, args: Mapping, request_id: str) -> dict: ...
    def run_start(self, profile: Mapping, args: Mapping, request_id: str) -> dict: ...
    def run_status(self, args: Mapping, request_id: str) -> dict: ...
    def run_stop(self, args: Mapping, request_id: str) -> dict: ...
    def diagnostics_export(self, args: Mapping, request_id: str) -> dict: ...


class UnavailableBackend:
    def _refuse(self, *_):
        raise ContractError("adapter_unavailable")
    session_inspect = session_discover = session_prepare = run_resume = run_check = run_start = run_status = run_stop = diagnostics_export = _refuse


def _result_safe(value, depth=0):
    if depth > 16:
        raise ContractError("backend_response_invalid")
    forbidden = {"key", "apikey", "authorization", "password", "secret", "clientsecret", "accesstoken", "refreshtoken",
                 "token", "credentials", "credentialvalue", "path", "cwd", "command", "commandline",
                 "executablepath", "processhandle", "address"}
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or re.sub(r"[-_]", "", key.lower()) in forbidden:
                raise ContractError("backend_response_sensitive")
            _result_safe(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _result_safe(item, depth + 1)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ContractError("backend_response_invalid")


class BridgeService:
    def __init__(self, store: ProfileStore, backend: HostBackend | None = None):
        self.store = store
        self.backend = backend if backend is not None else UnavailableBackend()

    def _invoke_backend(self, method, *args):
        try:
            return method(*args)
        except ContractError as error:
            # Backend failures must never turn rejected data into an error code.
            if error.code not in BACKEND_ERROR_CODES:
                raise ContractError("backend_error_invalid") from None
            raise

    def _profile(self, args):
        identifier(args["profile_id"]); integer(args["profile_revision"], 1, 2**53 - 1, "invalid_profile_revision")
        record = self.store.get_profile(args["profile_id"])["profile"]
        if record["revision"] != args["profile_revision"]:
            raise ContractError("profile_revision_conflict")
        if not record["validation"]["ok"]:
            raise ContractError(record["validation"]["reason_code"])
        if "effective_hash" in args:
            sha256(args["effective_hash"])
            if args["effective_hash"] != record["effective"]["effective_hash"]:
                raise ContractError("effective_profile_changed")
        return record

    def dispatch(self, operation, args, request_id):
        if operation not in OPERATIONS:
            raise ContractError("operation_unsupported")
        if operation in ("profiles.list", "connections.list"):
            object_fields(args, set())
            return self.store.list_profiles() if operation == "profiles.list" else self.store.list_connections()
        if operation == "profiles.get":
            value = object_fields(args, {"profile_id"})
            return self.store.get_profile(value["profile_id"])
        if operation == "profiles.save":
            value = object_fields(args, {"draft", "expected_revision"})
            return self.store.save_profile(request_id, value["draft"], value["expected_revision"])
        if operation in ("session.discover", "run.resume"):
            value = object_fields(args, set())
            method = self.backend.session_discover if operation == "session.discover" else self.backend.run_resume
            return self._invoke_backend(method, value, request_id)
        if operation == "session.prepare":
            value = object_fields(args, {"candidate_id"})
            identifier(value["candidate_id"])
            return self._invoke_backend(self.backend.session_prepare, value, request_id)
        if operation == "session.inspect":
            value = object_fields(args, set(), {"profile_id"})
            if "profile_id" in value:
                identifier(value["profile_id"])
            return self._invoke_backend(self.backend.session_inspect, value, request_id)
        if operation in ("run.check", "run.start"):
            required = {"profile_id", "profile_revision"}
            if operation == "run.start":
                required |= {"session_id", "ready_token"}
            value = object_fields(args, required, {"effective_hash"})
            if operation == "run.start":
                identifier(value["session_id"]); text(value["ready_token"], 256)
            profile = self._profile(value)
            method = self.backend.run_check if operation == "run.check" else self.backend.run_start
            return self._invoke_backend(method, profile, value, request_id)
        if operation == "run.stop":
            value = object_fields(args, {"run_id", "session_id"})
            identifier(value["run_id"]); identifier(value["session_id"])
            return self._invoke_backend(self.backend.run_stop, value, request_id)
        value = object_fields(args, {"run_id"}); identifier(value["run_id"])
        method = self.backend.run_status if operation == "run.status" else self.backend.diagnostics_export
        return self._invoke_backend(method, value, request_id)

    def handle(self, request) -> dict:
        request_id = None
        try:
            value = object_fields(request, {"schema_version", "request_id", "operation", "args"})
            request_id = identifier(value["request_id"])
            if type(value["schema_version"]) is not int or value["schema_version"] != 1:
                raise ContractError("unsupported_schema_version")
            if not isinstance(value["operation"], str):
                raise ContractError("operation_unsupported")
            result = self.dispatch(value["operation"], value["args"], request_id)
            if not isinstance(result, dict):
                raise ContractError("backend_response_invalid")
            _result_safe(result)
            canonical_json(result)
            return dict(schema_version=1, request_id=request_id, ok=True, result=result)
        except ContractError as error:
            code = error.code if isinstance(error.code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", error.code) else "backend_error_invalid"
            return dict(schema_version=1, request_id=request_id, ok=False, error=dict(code=code))
        except (OSError, sqlite3.Error):
            return dict(schema_version=1, request_id=request_id, ok=False, error=dict(code="local_state_unavailable"))
        except Exception:
            return dict(schema_version=1, request_id=request_id, ok=False, error=dict(code="bridge_operation_failed"))


def decode_request(raw: bytes):
    if len(raw) > MAX_LINE_BYTES:
        raise ContractError("request_too_large")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ContractError("duplicate_request_key")
            value[key] = item
        return value
    def constant(_):
        raise ContractError("invalid_request_number")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
    except ContractError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError("invalid_request_json") from None


def serve(service: BridgeService, source, target):
    while True:
        raw = source.readline(MAX_LINE_BYTES + 1)
        if not raw:
            return
        try:
            if len(raw) > MAX_LINE_BYTES:
                while raw and not raw.endswith(b"\n"):
                    raw = source.readline(MAX_LINE_BYTES + 1)
                raise ContractError("request_too_large")
            response = service.handle(decode_request(raw))
        except ContractError as error:
            response = dict(schema_version=1, request_id=None, ok=False, error=dict(code=error.code))
        encoded = (canonical_json(response) + "\n").encode("utf-8")
        if len(encoded) > MAX_LINE_BYTES:
            response = dict(schema_version=1, request_id=response.get("request_id"), ok=False, error=dict(code="response_too_large"))
            encoded = (canonical_json(response) + "\n").encode("utf-8")
        target.write(encoded); target.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    store = None
    backend = None
    fused = None
    try:
        store = ProfileStore(args.library, args.state_dir)
        from .desktop_backend import DesktopBackend
        backend = DesktopBackend(store)
        from .session_discovery_native import create_discovery
        # A missing/invalid discovery policy only disables new source preparation;
        # accepted runs retain their existing status, stop and resume paths.
        backend.discovery = create_discovery(backend)
        from .connection_config_rpc_v1 import ConnectionAwareBridgeV1
        fused = ConnectionAwareBridgeV1(store, backend, registration_path=args.state_dir.parent/'desktop-runtime-config.json')
        serve(fused, sys.stdin.buffer, sys.stdout.buffer)
    except (ContractError, OSError, sqlite3.Error):
        response = dict(schema_version=1, request_id=None, ok=False, error=dict(code="bridge_startup_failed"))
        sys.stdout.buffer.write((canonical_json(response) + "\n").encode("utf-8")); sys.stdout.buffer.flush()
        return 2
    finally:
        if fused is not None:
            fused.close()
        if backend is not None:
            backend.close()
        if store is not None:
            store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
