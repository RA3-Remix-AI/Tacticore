"""Normalize desktop styles for host application without truncation or secret export."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from .capabilities import CapabilityCatalog
from .contracts import (ContractError, SCHEMA_VERSION, canonical_json, content_hash,
                        identifier, integer, object_fields, sha256, text)

AXES = ("attack", "risk", "economy", "scouting", "pursuit")
DOCTRINES = {"assault": 0, "defense": 1, "maneuver": 2}
PRESETS = {
    "steady": ("defense", (2, 1, 4, 3, 1)),
    "balanced": ("defense", (3, 3, 3, 3, 3)),
    "pressure": ("assault", (4, 4, 2, 3, 4)),
    "flank": ("maneuver", (3, 2, 3, 5, 2)),
}
DESCRIPTIONS = {
    "attack": ("优先巩固阵线，出现明确优势再进攻。", "先确认兵力与情报，再寻找交战机会。", "根据敌情与资源，平衡推进和准备。", "更早寻找施压窗口，同时保留基础防守。", "积极创造交战机会，争取持续掌握节奏。"),
    "risk": ("倾向保留主力，遇到不利局面尽早脱离。", "谨慎投入兵力，预留撤退与接应空间。", "结合目标价值判断是否值得投入。", "愿为重要目标接受有限损失。", "高价值窗口出现时，倾向接受更大的兵力交换。"),
    "economy": ("优先补充当前作战力量，经济扩张靠后。", "先满足必要兵力，再逐步发展经济。", "保持作战与经济投入的平衡。", "保留基础防守后，更重视经济增长。", "局势允许时优先扩张，积累后续资源。"),
    "scouting": ("围绕当前任务补充必要情报。", "在投入主力前确认关键区域。", "定期更新关键方向的可见信息。", "更主动确认侧翼、威胁与行动窗口。", "持续寻找侦察机会，优先减少未知信息。"),
    "pursuit": ("达成当前目标后倾向收队整补。", "限制追击距离，优先保持队形与退路。", "根据视野和接应条件决定是否继续。", "条件允许时继续施压，争取扩大优势。", "积极利用胜势，但仍受视野、时效和执行限制。"),
}
TRAITS_BYTE_LIMIT = 1200


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


def _preferences(raw, doctrine: str) -> tuple[str, tuple[int, ...]]:
    if raw is None:
        preset = next(name for name, (base, _) in PRESETS.items() if base == doctrine)
        return preset, PRESETS[preset][1]
    data = object_fields(raw, {"preset", *AXES})
    preset = data["preset"]
    if not isinstance(preset, str) or preset not in {*PRESETS, "custom"}:
        raise ContractError("invalid_preference_preset")
    levels = tuple(integer(data[a], 1, 5, "invalid_preference_level") for a in AXES)
    if preset in PRESETS and (PRESETS[preset][0] != doctrine or PRESETS[preset][1] != levels):
        raise ContractError("preset_doctrine_or_values_mismatch")
    return preset, levels


@dataclass(frozen=True)
class EffectiveProfile:
    schema_version: int
    profile_id: str
    name: str
    revision: int
    connection_id: str
    model: str
    personality: int
    preset: str
    levels: tuple[int, ...]
    generated_traits: str
    custom_traits: str
    traits: str
    traits_bytes: int
    axis_support_json: str
    capability_catalog_hash: str
    capability_binding_hash: str | None
    effective_hash: str = ""

    def _content(self) -> dict:
        return {"schema_version": self.schema_version, "profile_id": self.profile_id, "name": self.name,
                "revision": self.revision, "connection_id": self.connection_id, "model": self.model,
                "personality": self.personality, "personality_name": ("assault", "fortifier", "raider")[self.personality],
                "preferences": {"preset": self.preset, **dict(zip(AXES, self.levels))},
                "generated_traits": self.generated_traits, "custom_traits": self.custom_traits,
                "traits": self.traits, "traits_bytes": self.traits_bytes, "traits_truncated": False,
                "axis_support": json.loads(self.axis_support_json), "capability_catalog_hash": self.capability_catalog_hash,
                "capability_binding_hash": self.capability_binding_hash}

    def public(self) -> dict:
        return {**self._content(), "effective_hash": self.effective_hash}

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported_schema_version")
        identifier(self.profile_id); identifier(self.connection_id)
        integer(self.revision, 1, 2**53 - 1, "invalid_profile_revision")
        integer(self.personality, 0, 2, "invalid_personality")
        if type(self.levels) is not tuple or len(self.levels) != 5:
            raise ContractError("invalid_preference_levels")
        for level in self.levels:
            integer(level, 1, 5, "invalid_preference_level")
        doctrine = next(d for d, p in DOCTRINES.items() if p == self.personality)
        _preferences({"preset": self.preset, **dict(zip(AXES, self.levels))}, doctrine)
        text(self.name, 24); text(self.model, 200, empty=True)
        text(self.generated_traits, 1000); text(self.custom_traits, 800, empty=True)
        generated = "".join(DESCRIPTIONS[a][level - 1] for a, level in zip(AXES, self.levels))
        if self.generated_traits != generated:
            raise ContractError("generated_traits_mismatch")
        if self.traits != self.generated_traits + ("\n" + self.custom_traits if self.custom_traits else ""):
            raise ContractError("traits_content_mismatch")
        if type(self.traits_bytes) is not int or self.traits_bytes != len(self.traits.encode("utf-8")) or self.traits_bytes > TRAITS_BYTE_LIMIT:
            raise ContractError("traits_budget_exceeded")
        try:
            support = json.loads(self.axis_support_json)
            object_fields(support, set(AXES))
            for row in support.values():
                object_fields(row, {"mode", "model_advice", "execution_status", "missing_capabilities", "required_capabilities", "verified_scopes"})
                if row["mode"] not in ("advisory", "executable") or row["model_advice"] is not True:
                    raise ContractError("invalid_axis_support")
                if row["execution_status"] not in ("verified_scope", "unsupported"):
                    raise ContractError("invalid_axis_support")
            if canonical_json(support) != self.axis_support_json:
                raise ContractError("invalid_axis_support")
        except (ValueError, TypeError, AttributeError):
            raise ContractError("invalid_axis_support") from None
        sha256(self.capability_catalog_hash)
        if self.capability_binding_hash is not None:
            sha256(self.capability_binding_hash)
        if self.effective_hash == "":
            object.__setattr__(self, "effective_hash", content_hash(self._content()))
        sha256(self.effective_hash)
        if content_hash(self._content()) != self.effective_hash:
            raise ContractError("effective_profile_hash_mismatch")


def normalize_profile(draft: Mapping, *, capability_catalog: CapabilityCatalog | None = None,
                      profile_ids: Mapping | None = None, connection_ids: Mapping | None = None) -> EffectiveProfile:
    required = {"schema_version", "profile_id", "name", "revision", "connection_id", "model", "doctrine", "custom_traits"}
    data = object_fields(draft, required, {"preferences"})
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ContractError("unsupported_schema_version")
    doctrine = data["doctrine"]
    if not isinstance(doctrine, str) or doctrine not in DOCTRINES:
        raise ContractError("invalid_doctrine")
    profile_id = _mapped_id(data["profile_id"], profile_ids)
    connection_id = _mapped_id(data["connection_id"], connection_ids)
    name = text(data["name"], 24).strip()
    revision = integer(data["revision"], 1, 2**53 - 1, "invalid_profile_revision")
    model = text(data["model"], 200, empty=True).strip()
    custom = text(data["custom_traits"], 800, empty=True)
    preset, levels = _preferences(data.get("preferences"), doctrine)
    generated = "".join(DESCRIPTIONS[a][level - 1] for a, level in zip(AXES, levels))
    traits = generated + ("\n" + custom if custom else "")
    size = len(traits.encode("utf-8"))
    if size > TRAITS_BYTE_LIMIT:
        raise ContractError("traits_budget_exceeded")
    catalog = capability_catalog if capability_catalog is not None else CapabilityCatalog()
    if not isinstance(catalog, CapabilityCatalog):
        raise ContractError("invalid_capability_catalog")
    if catalog.binding is not None and catalog.binding.commander_id != profile_id:
        raise ContractError("profile_capability_binding_mismatch")
    support_json = canonical_json(catalog.describe_axes())
    kwargs = dict(schema_version=1, profile_id=profile_id, name=name, revision=revision,
                  connection_id=connection_id, model=model, personality=DOCTRINES[doctrine],
                  preset=preset, levels=levels, generated_traits=generated, custom_traits=custom,
                  traits=traits, traits_bytes=size, axis_support_json=support_json,
                  capability_catalog_hash=catalog.catalog_hash, capability_binding_hash=catalog.binding_hash)
    return EffectiveProfile(**kwargs)


def normalize_desktop_profile(commander: Mapping, *, profile_ids: Mapping, connection_ids: Mapping,
                              capability_catalog: CapabilityCatalog | None = None) -> EffectiveProfile:
    data = object_fields(commander, {"id", "name", "callsign", "doctrine", "traits", "connectionId", "modelOverride", "revision"}, {"preferences"})
    text(data["callsign"], 16, empty=True)
    draft = {"schema_version": 1, "profile_id": data["id"], "name": data["name"], "revision": data["revision"],
             "connection_id": data["connectionId"], "model": data["modelOverride"], "doctrine": data["doctrine"],
             "custom_traits": data["traits"]}
    if "preferences" in data:
        draft["preferences"] = data["preferences"]
    return normalize_profile(draft, profile_ids=profile_ids, connection_ids=connection_ids,
                             capability_catalog=capability_catalog)
