"""Explicit local configuration-library registration, outside the WebView RPC.

This records a reference and byte identity only. It neither copies credentials
nor silently searches historical directories. Changing a registered source is
deliberately refused until a separate stopped-session migration is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

from .contracts import ContractError, identifier, object_fields, sha256
from .profile_store import ProfileStore

CONFIG_NAME = "desktop-runtime-config.json"


def _library_bytes(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
    except OSError:
        raise ContractError("profile_library_unavailable") from None
    if len(raw) > 1024 * 1024:
        raise ContractError("profile_library_too_large")
    return raw


def load_registration(home: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate_registration_key")
            result[key] = value
        return result
    try:
        with (Path(home) / CONFIG_NAME).open("rb") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ContractError("runtime_configuration_invalid")
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
        object_fields(record, {"schema_version", "registration_id", "library_path", "library_sha256"})
        if type(record["schema_version"]) is not int or record["schema_version"] != 1:
            raise ContractError("runtime_configuration_invalid")
        identifier(record["registration_id"])
        sha256(record["library_sha256"])
        path = record["library_path"]
        if not isinstance(path, str) or not Path(path).is_absolute() or path.startswith("\\\\"):
            raise ContractError("runtime_configuration_invalid")
        if hashlib.sha256(_library_bytes(path)).hexdigest() != record["library_sha256"]:
            raise ContractError("registered_library_changed")
        return record
    except ContractError:
        raise
    except (OSError, ValueError, UnicodeError, TypeError, RecursionError):
        raise ContractError("runtime_configuration_invalid") from None


def register_library(library: Path, home: Path) -> dict:
    try:
        library = Path(library).resolve(strict=True)
    except OSError:
        raise ContractError("profile_library_unavailable") from None
    if not library.is_file() or str(library).startswith("\\\\"):
        raise ContractError("profile_library_unavailable")
    before = _library_bytes(library)
    digest = hashlib.sha256(before).hexdigest()
    # Projection validates the exact schema and never opens DPAPI files.
    with tempfile.TemporaryDirectory(prefix="tacticore-library-check-") as temp:
        store = ProfileStore(library, Path(temp))
        try:
            count = len(store.list_profiles()["profiles"])
            store.list_connections()
        finally:
            store.close()
    if _library_bytes(library) != before:
        raise ContractError("registered_library_changed")
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    config = home / CONFIG_NAME
    if config.exists():
        existing = load_registration(home)
        if existing["library_path"] != str(library) or existing["library_sha256"] != digest:
            raise ContractError("runtime_registration_conflict")
        record = existing
    else:
        record = dict(schema_version=1, registration_id=str(uuid.uuid4()),
                      library_path=str(library), library_sha256=digest)
        try:
            with config.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
                stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        except FileExistsError:
            raise ContractError("runtime_registration_conflict") from None
    return dict(schema_version=1, registered=True, registration_id=record["registration_id"],
                library_sha256=digest, profile_count=count, credential_material_copied=False,
                restart_required=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    args = parser.parse_args(argv)
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        parser.error("LOCALAPPDATA is unavailable")
    try:
        result = register_library(args.library, Path(local) / "Tacticore")
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except ContractError as error:
        print(json.dumps(dict(registered=False, reason_code=error.code)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
