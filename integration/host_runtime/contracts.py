"""Versioned, non-secret host contracts. No game access or execution authority."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping
import uuid

SCHEMA_VERSION = 1


class ContractError(ValueError):
    """Stable error codes only; rejected input is never included in the error."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def object_fields(value: Any, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, Mapping) or not all(isinstance(k, str) for k in value):
        raise ContractError("invalid_object")
    if not required <= set(value) or set(value) - required - (optional or set()):
        raise ContractError("unexpected_fields")
    return dict(value)


def integer(value: Any, low: int, high: int, code: str = "invalid_integer") -> int:
    if type(value) is not int or not low <= value <= high:
        raise ContractError(code)
    return value


def text(value: Any, maximum: int, *, empty: bool = False, code: str = "invalid_text") -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ContractError(code)
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ContractError(code)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ContractError(code) from None
    return value


def identifier(value: Any) -> str:
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ContractError("invalid_uuid") from None
    return value


def sha256(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError("invalid_sha256")
    return value


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeError):
        raise ContractError("invalid_json_value") from None


def content_hash(value: Any) -> str:
    try:
        return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        raise ContractError("invalid_json_value") from None


@dataclass(frozen=True)
class SessionBinding:
    schema_version: int
    session_id: str
    player_id: int
    commander_id: str
    game_process_id: int
    game_process_start: str
    host_id: str
    game_sha256: str
    mod_sha256: str

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported_schema_version")
        identifier(self.session_id); identifier(self.commander_id); identifier(self.host_id)
        integer(self.player_id, 0, 15, "invalid_player_id")
        integer(self.game_process_id, 1, 2**32 - 1, "invalid_process_id")
        text(self.game_process_start, 128, code="invalid_process_start")
        try:
            started = datetime.fromisoformat(self.game_process_start.replace("Z", "+00:00"))
            if started.tzinfo is None:
                raise ValueError()
        except ValueError:
            raise ContractError("invalid_process_start") from None
        sha256(self.game_sha256); sha256(self.mod_sha256)

    @classmethod
    def from_dict(cls, value: Mapping) -> "SessionBinding":
        return cls(**object_fields(value, set(cls.__dataclass_fields__)))

    def public(self) -> dict:
        return asdict(self)

    @property
    def binding_hash(self) -> str:
        return content_hash(self.public())


@dataclass(frozen=True)
class ProfileApplication:
    """Receipt factory after host application; not proof of model/game effects."""
    schema_version: int
    request_id: str
    profile_id: str
    profile_revision: int
    effective_hash: str
    session_binding_hash: str
    status: str
    reason_code: str

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported_schema_version")
        identifier(self.request_id); identifier(self.profile_id)
        integer(self.profile_revision, 1, 2**53 - 1, "invalid_profile_revision")
        sha256(self.effective_hash); sha256(self.session_binding_hash)
        if self.status not in ("host_accepted", "rejected"):
            raise ContractError("invalid_application_status")
        if not isinstance(self.reason_code, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,79}", self.reason_code) is None:
            raise ContractError("invalid_reason_code")
        if self.status == "host_accepted" and self.reason_code != "ok":
            raise ContractError("invalid_application_reason")
        if self.status == "rejected" and self.reason_code == "ok":
            raise ContractError("invalid_application_reason")

    @classmethod
    def accept(cls, profile, binding: SessionBinding, request_id: str) -> "ProfileApplication":
        if profile.profile_id != binding.commander_id:
            raise ContractError("profile_commander_mismatch")
        if profile.capability_binding_hash is not None and profile.capability_binding_hash != binding.binding_hash:
            raise ContractError("profile_capability_binding_mismatch")
        return cls(SCHEMA_VERSION, request_id, profile.profile_id, profile.revision,
                   profile.effective_hash, binding.binding_hash, "host_accepted", "ok")

    @classmethod
    def reject(cls, profile, binding: SessionBinding, request_id: str, reason_code: str) -> "ProfileApplication":
        return cls(SCHEMA_VERSION, request_id, profile.profile_id, profile.revision,
                   profile.effective_hash, binding.binding_hash, "rejected", reason_code)

    @classmethod
    def from_dict(cls, value: Mapping) -> "ProfileApplication":
        data = object_fields(value, set(cls.__dataclass_fields__), {"model_consumed", "behavior_verified"})
        for flag in ("model_consumed", "behavior_verified"):
            if data.pop(flag, False) is not False:
                raise ContractError("unsupported_application_claim")
        return cls(**data)

    def public(self) -> dict:
        return {**asdict(self), "model_consumed": False, "behavior_verified": False}
