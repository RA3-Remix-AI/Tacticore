"""Commander profiles: a named commander plus nine personality parameters (1..5).

Presets carry exactly the values of docs/commander-characters-tactics-20261120.md.
Drafts saved before the commander model existed (doctrine/preferences) load as
the Hammer preset; there is no migration step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .capabilities import CapabilityCatalog
from .contracts import (
    ContractError,
    SCHEMA_VERSION,
    content_hash,
    identifier,
    integer,
    object_fields,
    sha256,
    text,
)

PERSONALITY_KEYS = (
    "aggression",
    "risk",
    "persistence",
    "punish",
    "preserve",
    "deception",
    "grudge",
    "adaptability",
    "bait_awareness",
)
PERSONALITY_LABELS = dict(
    aggression="进攻性",
    risk="冒险",
    persistence="纠缠度",
    punish="惩罚意识",
    preserve="惜兵",
    deception="诡诈",
    grudge="记仇",
    adaptability="适应性",
    bait_awareness="识破诱饵",
)
COMMANDERS = {
    "hammer": dict(
        name="铁锤",
        full_name="维克托·莫罗佐夫",
        faction="Soviet",
        available=True,
        personality=(4, 3, 3, 5, 3, 2, 3, 4, 5),
    ),
    "bastion": dict(
        name="堡垒",
        full_name="伊芙琳·卡特",
        faction="Allied",
        available=False,
        personality=(2, 2, 2, 4, 5, 3, 2, 5, 4),
    ),
    "ghost": dict(
        name="幽灵",
        full_name="神崎凛",
        faction="Empire",
        available=False,
        personality=(3, 4, 5, 4, 4, 5, 3, 5, 3),
    ),
}
# A custom commander plays the only faction the model seat supports today.
CUSTOM = dict(name="自定义", full_name="自定义指挥官", faction="Soviet", available=True)
COMMANDER_IDS = (*COMMANDERS, "custom")
DEFAULT_COMMANDER = "hammer"
VOICE_NOTE_BYTE_LIMIT = 300
LEGACY_DRAFT_FIELDS = frozenset({"doctrine", "custom_traits", "preferences"})


def commanders_metadata() -> list[dict]:
    """Public commander list for the desktop UI."""
    rows = [
        dict(id=ident, name=row["name"], full_name=row["full_name"], faction=row["faction"], available=row["available"])
        for ident, row in COMMANDERS.items()
    ]
    rows.append(dict(id="custom", **CUSTOM))
    return rows


def commander_info(commander_id: str) -> dict:
    return COMMANDERS.get(commander_id) or CUSTOM


def commander_available(commander_id: str) -> bool:
    return commander_info(commander_id)["available"] is True


def personality_dict(values) -> dict:
    return dict(zip(PERSONALITY_KEYS, values))


def preset_personality(commander_id: str = DEFAULT_COMMANDER) -> dict:
    return personality_dict(COMMANDERS[commander_id]["personality"])


def _personality(commander_id, raw) -> tuple[int, ...]:
    data = object_fields(raw, set(PERSONALITY_KEYS))
    values = tuple(integer(data[key], 1, 5, "invalid_personality_level") for key in PERSONALITY_KEYS)
    if commander_id in COMMANDERS and values != COMMANDERS[commander_id]["personality"]:
        raise ContractError("preset_personality_mismatch")
    return values


def persona_text(commander_id: str, values, voice_note: str) -> str:
    """One-line persona used as the single-call prompt's Style and as layer voice."""
    info = commander_info(commander_id)
    levels = " ".join(PERSONALITY_LABELS[key] + str(value) for key, value in zip(PERSONALITY_KEYS, values))
    line = "指挥官" + info["name"] + "（" + info["full_name"] + "）：" + levels + "。"
    return line + ("\n" + voice_note if voice_note else "")


def style_index(values) -> int:
    """Legacy Style label for the single-call prompt: 0 assault, 1 fortifier, 2 raider."""
    traits = personality_dict(values)
    if traits["aggression"] >= 4:
        return 0
    if traits["preserve"] >= 4 and traits["aggression"] <= 2:
        return 1
    return 2


def _mapped_id(value, mapping: Mapping | None) -> str:
    if mapping is None:
        return identifier(value)
    if not isinstance(mapping, Mapping):
        raise ContractError("invalid_id_map")
    for mapped in mapping.values():
        identifier(mapped)
    if len(set(mapping.values())) != len(mapping):
        raise ContractError("duplicate_mapped_id")
    try:
        return identifier(mapping[value])
    except (KeyError, TypeError):
        raise ContractError("unmapped_profile_id") from None


def _voice_note(value) -> str:
    note = text(value, VOICE_NOTE_BYTE_LIMIT, empty=True, code="invalid_voice_note")
    if len(note.encode("utf-8")) > VOICE_NOTE_BYTE_LIMIT:
        raise ContractError("voice_note_too_long")
    return note


@dataclass(frozen=True)
class EffectiveProfile:
    schema_version: int
    profile_id: str
    name: str
    revision: int
    connection_id: str
    model: str
    commander_id: str
    personality: tuple[int, ...]
    voice_note: str
    traits: str
    traits_bytes: int
    capability_catalog_hash: str
    capability_binding_hash: str | None
    effective_hash: str = ""

    @property
    def style_index(self) -> int:
        return style_index(self.personality)

    def personality_dict(self) -> dict:
        return personality_dict(self.personality)

    def _content(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "name": self.name,
            "revision": self.revision,
            "connection_id": self.connection_id,
            "model": self.model,
            "commander_id": self.commander_id,
            "commander_name": commander_info(self.commander_id)["name"],
            "personality": self.personality_dict(),
            "voice_note": self.voice_note,
            "traits": self.traits,
            "traits_bytes": self.traits_bytes,
            "traits_truncated": False,
            "capability_catalog_hash": self.capability_catalog_hash,
            "capability_binding_hash": self.capability_binding_hash,
        }

    def public(self) -> dict:
        return {**self._content(), "effective_hash": self.effective_hash}

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported_schema_version")
        identifier(self.profile_id)
        identifier(self.connection_id)
        integer(self.revision, 1, 2**53 - 1, "invalid_profile_revision")
        if self.commander_id not in COMMANDER_IDS:
            raise ContractError("invalid_commander")
        if type(self.personality) is not tuple:
            raise ContractError("invalid_personality_level")
        _personality(self.commander_id, personality_dict(self.personality))
        text(self.name, 24)
        text(self.model, 200, empty=True)
        _voice_note(self.voice_note)
        if self.traits != persona_text(self.commander_id, self.personality, self.voice_note):
            raise ContractError("traits_content_mismatch")
        if type(self.traits_bytes) is not int or self.traits_bytes != len(self.traits.encode("utf-8")):
            raise ContractError("traits_budget_exceeded")
        sha256(self.capability_catalog_hash)
        if self.capability_binding_hash is not None:
            sha256(self.capability_binding_hash)
        if self.effective_hash == "":
            object.__setattr__(self, "effective_hash", content_hash(self._content()))
        sha256(self.effective_hash)
        if content_hash(self._content()) != self.effective_hash:
            raise ContractError("effective_profile_hash_mismatch")


def _commander_fields(data) -> tuple[str, tuple[int, ...], str]:
    """(commander_id, personality, voice_note) of a draft; legacy drafts load as Hammer."""
    if "commander_id" not in data:
        if not {"doctrine", "custom_traits"} <= set(data):
            raise ContractError("unexpected_fields")
        return DEFAULT_COMMANDER, COMMANDERS[DEFAULT_COMMANDER]["personality"], ""
    # A client may keep old doctrine fields beside the commander fields; they are ignored.
    if not {"personality", "voice_note"} <= set(data):
        raise ContractError("unexpected_fields")
    commander = data["commander_id"]
    if not isinstance(commander, str) or commander not in COMMANDER_IDS:
        raise ContractError("invalid_commander")
    return commander, _personality(commander, data["personality"]), _voice_note(data["voice_note"])


def normalize_profile(
    draft: Mapping,
    *,
    capability_catalog: CapabilityCatalog | None = None,
    profile_ids: Mapping | None = None,
    connection_ids: Mapping | None = None,
) -> EffectiveProfile:
    required = {"schema_version", "profile_id", "name", "revision", "connection_id", "model"}
    optional = {"commander_id", "personality", "voice_note", *LEGACY_DRAFT_FIELDS}
    data = object_fields(draft, required, optional)
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ContractError("unsupported_schema_version")
    commander, values, voice = _commander_fields(data)
    profile_id = _mapped_id(data["profile_id"], profile_ids)
    connection_id = _mapped_id(data["connection_id"], connection_ids)
    name = text(data["name"], 24).strip()
    revision = integer(data["revision"], 1, 2**53 - 1, "invalid_profile_revision")
    model = text(data["model"], 200, empty=True).strip()
    traits = persona_text(commander, values, voice)
    catalog = capability_catalog if capability_catalog is not None else CapabilityCatalog()
    if not isinstance(catalog, CapabilityCatalog):
        raise ContractError("invalid_capability_catalog")
    if catalog.binding is not None and catalog.binding.commander_id != profile_id:
        raise ContractError("profile_capability_binding_mismatch")
    return EffectiveProfile(
        schema_version=1,
        profile_id=profile_id,
        name=name,
        revision=revision,
        connection_id=connection_id,
        model=model,
        commander_id=commander,
        personality=values,
        voice_note=voice,
        traits=traits,
        traits_bytes=len(traits.encode("utf-8")),
        capability_catalog_hash=catalog.catalog_hash,
        capability_binding_hash=catalog.binding_hash,
    )


def normalize_desktop_profile(
    commander: Mapping,
    *,
    profile_ids: Mapping,
    connection_ids: Mapping,
    capability_catalog: CapabilityCatalog | None = None,
) -> EffectiveProfile:
    """Old desktop commander record (doctrine/traits); it loads as the Hammer preset."""
    data = object_fields(
        commander,
        {"id", "name", "callsign", "doctrine", "traits", "connectionId", "modelOverride", "revision"},
        {"preferences"},
    )
    text(data["callsign"], 16, empty=True)
    draft = {
        "schema_version": 1,
        "profile_id": data["id"],
        "name": data["name"],
        "revision": data["revision"],
        "connection_id": data["connectionId"],
        "model": data["modelOverride"],
        "doctrine": data["doctrine"],
        "custom_traits": data["traits"],
    }
    return normalize_profile(
        draft, profile_ids=profile_ids, connection_ids=connection_ids, capability_catalog=capability_catalog
    )
