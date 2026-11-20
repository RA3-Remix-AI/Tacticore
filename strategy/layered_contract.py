"""Layered decision contract: Directive, EconomyIntent, TacticalIntent and domain ownership.

Each layer returns an intent, never an executable plan. The validators below are
strict on shape and enums; fields without an executor today are accepted and
reported as record-only. The composer (host side) turns intents into the native
actions listed here.
"""

from __future__ import annotations

import math
import re

ROUTES = ("rush", "steady_growth", "tech_pressure", "all_in", "defend_counter")
OVERRIDES = ("no_expansion", "no_tech", "no_attack", "no_harass")
REVIEW_EVENTS = (
    "enemy_defeated",
    "base_under_attack",
    "expansion_lost",
    "enemy_main_force_contact",
    "scouting_report",
    "tech_unlocked",
    "ore_collector_lost",
)
POSTURES = ("attack", "defend", "patrol", "harass", "all_in", "regroup", "withdraw", "scout")
COMPOSITION_NEEDS = ("anti_air", "anti_armor", "anti_infantry", "naval", "air", "detection")
POWER_USAGE = ("aggressive", "save_for_defense")
CAPACITY_KEYS = ("war_factory", "barracks", "ore_collector", "refinery", "power_plant", "airfield", "naval_yard")
RESOURCE_KEYS = ("economy", "army", "tech", "reserve")
REASONING_MAX_CHARS = 300

# Native domains and the single layer that owns each (plan section 4.4).
DOMAIN_OWNER = {
    "budget": "commander",
    "enemy_focus": "commander",
    "expansion": "economy",
    "construction_gate": "economy",
    "production_gate": "economy",
    "military": "tactical",
}
DOMAIN_ORDER = tuple(DOMAIN_OWNER)
POSTURE_ACTIONS = {
    "attack": ("attackenemy", "deployattack"),
    "all_in": ("attackenemy", "deployattack"),
    "harass": ("raideconomy",),
    "defend": ("deploydefense", "reinforce"),
    "regroup": ("regroup",),
    "withdraw": ("withdraw",),
    "scout": ("scout",),
    "patrol": (),
}
OVERRIDE_BLOCKS = {
    "no_expansion": frozenset({"expand"}),
    "no_tech": frozenset({"budgettech", "advanceconstruction"}),
    "no_attack": frozenset({"attackenemy", "deployattack", "raideconomy"}),
    "no_harass": frozenset({"raideconomy"}),
}
RECORD_ONLY = {
    "commander": (),
    "economy": ("tech_timing", "capacity_target", "protocol_pick_preference", "composition_answer"),
    "tactical": ("target", "composition_need", "doctrine", "power_usage"),
}
_TOKEN = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")


class LayerContractError(ValueError):
    """A fixed reason code for a layer response that is not a valid intent."""


def _fail(code):
    raise LayerContractError(code)


def _fields(raw, required, optional=(), code="layer_fields"):
    if type(raw) is not dict or not set(required) <= set(raw) or set(raw) - set(required) - set(optional):
        _fail(code)
    return raw


def _enum(value, allowed, code, *, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not str or value not in allowed:
        _fail(code)
    return value


def _seconds(value, low, high, code):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        _fail(code)
    return float(value)


def _unique(values, allowed, maximum, code):
    if type(values) is not list or len(values) > maximum or len(set(map(str, values))) != len(values):
        _fail(code)
    return [_enum(value, allowed, code) for value in values]


def reasoning_text(value):
    """Trimmed one-line rationale, at most 300 characters (longer text is shortened)."""
    if value is None:
        return None
    if type(value) is not str or len(value) > 4000:
        _fail("layer_reasoning")
    text = " ".join(value.split())
    if len(text) > REASONING_MAX_CHARS:
        text = text[: REASONING_MAX_CHARS - 1].rstrip() + "…"
    return text or None


def recorded_only(layer, intent):
    """Names of fields that were set but have no executor yet."""
    return [name for name in RECORD_ONLY[layer] if intent.get(name) not in (None, [], {})]


def validate_directive(raw, *, enemies, opening_variants=()):
    data = _fields(
        raw,
        ("route", "resource_split", "primary_enemy", "overrides", "reasoning", "valid_for_s"),
        ("review_when", "opening_variant"),
        "directive_fields",
    )
    route = _enum(data["route"], ROUTES, "directive_route")
    split = _fields(data["resource_split"], RESOURCE_KEYS, (), "directive_resource_split")
    shares = {key: _seconds(split[key], 0, 1, "directive_resource_split") for key in RESOURCE_KEYS}
    if abs(sum(shares.values()) - 1) > 0.02:
        _fail("directive_resource_split")
    enemy = data["primary_enemy"]
    if enemy is not None and (type(enemy) is not int or enemy not in enemies):
        _fail("directive_primary_enemy")
    overrides = _unique(data["overrides"], OVERRIDES, len(OVERRIDES), "directive_overrides")
    if route == "all_in":
        overrides = list(dict.fromkeys([*overrides, "no_expansion", "no_tech"]))
    review = _unique(data.get("review_when", []), REVIEW_EVENTS, len(REVIEW_EVENTS), "directive_review_when")
    variant = data.get("opening_variant")
    if variant is not None and variant not in opening_variants:
        _fail("directive_opening_variant")
    return dict(
        route=route,
        resource_split=shares,
        primary_enemy=enemy,
        overrides=overrides,
        reasoning=reasoning_text(data["reasoning"]),
        valid_for_s=_seconds(data["valid_for_s"], 60, 300, "directive_valid_for"),
        review_when=review,
        opening_variant=variant,
    )


def validate_economy_intent(raw):
    data = _fields(
        raw,
        ("expand", "construction", "production", "reasoning", "valid_for_s"),
        ("tech_timing", "capacity_target", "protocol_pick_preference", "composition_answer"),
        "economy_fields",
    )
    capacity = data.get("capacity_target")
    if capacity is not None:
        if type(capacity) is not dict or set(capacity) - set(CAPACITY_KEYS):
            _fail("economy_capacity_target")
        if any(type(value) is not int or not 0 <= value <= 20 for value in capacity.values()):
            _fail("economy_capacity_target")
    protocols = data.get("protocol_pick_preference") or []
    if type(protocols) is not list or len(protocols) > 5 or any(not _TOKEN.fullmatch(str(p)) for p in protocols):
        _fail("economy_protocol_pick")
    return dict(
        expand=_enum(data["expand"], ("now", "hold"), "economy_expand", nullable=True),
        construction=_enum(data["construction"], ("advance", "pause"), "economy_construction", nullable=True),
        production=_enum(data["production"], ("advance", "pause"), "economy_production", nullable=True),
        tech_timing=_enum(
            data.get("tech_timing"), ("now", "after_expansion", "hold"), "economy_tech_timing", nullable=True
        ),
        capacity_target=dict(capacity) if capacity else None,
        protocol_pick_preference=list(protocols),
        composition_answer=_enum(
            data.get("composition_answer"), ("satisfy", "decline"), "economy_composition_answer", nullable=True
        ),
        reasoning=reasoning_text(data["reasoning"]),
        valid_for_s=_seconds(data["valid_for_s"], 20, 90, "economy_valid_for"),
    )


def validate_tactical_intent(raw, *, enemies):
    data = _fields(
        raw,
        ("posture", "reasoning", "valid_for_s"),
        ("target", "composition_need", "doctrine", "power_usage"),
        "tactical_fields",
    )
    target = data.get("target")
    if target is not None:
        _fields(target, (), ("enemy", "region"), "tactical_target")
        enemy = target.get("enemy")
        region = target.get("region")
        if enemy is not None and (type(enemy) is not int or enemy not in enemies):
            _fail("tactical_target_enemy")
        if region is not None and (type(region) is not str or not re.fullmatch(r"region_\d{1,3}_\d{1,3}", region)):
            _fail("tactical_target_region")
        target = dict(enemy=enemy, region=region) if enemy is not None or region is not None else None
    doctrine = data.get("doctrine")
    if doctrine is not None and (type(doctrine) is not str or not _TOKEN.fullmatch(doctrine)):
        _fail("tactical_doctrine")
    return dict(
        posture=_enum(data["posture"], POSTURES, "tactical_posture"),
        target=target,
        composition_need=_unique(data.get("composition_need", []), COMPOSITION_NEEDS, 4, "tactical_composition"),
        doctrine=doctrine,
        power_usage=_enum(data.get("power_usage"), POWER_USAGE, "tactical_power_usage", nullable=True),
        reasoning=reasoning_text(data["reasoning"]),
        valid_for_s=_seconds(data["valid_for_s"], 10, 60, "tactical_valid_for"),
    )


def budget_action(resource_split):
    """The budget preset of the dominant spending share (reserve is not a preset)."""
    order = ("economy", "army", "tech")
    best = max(order, key=lambda key: (resource_split[key], -order.index(key)))
    return "budget" + best


def directive_actions(directive):
    actions = {"budget": budget_action(directive["resource_split"])}
    if directive.get("primary_enemy") is not None:
        actions["enemy_focus"] = "focusenemy" + str(directive["primary_enemy"])
    return actions


def economy_actions(intent):
    actions = {}
    if intent.get("expand") == "now":
        actions["expansion"] = "expand"
    if intent.get("construction"):
        actions["construction_gate"] = intent["construction"] + "construction"
    if intent.get("production"):
        actions["production_gate"] = intent["production"] + "production"
    return actions


def tactical_actions(intent):
    """Military candidates in preference order; the composer keeps the first offered one."""
    candidates = POSTURE_ACTIONS[intent["posture"]]
    return {"military": candidates} if candidates else {}


def blocked_by(overrides, action):
    """The first override that forbids an action, or None."""
    return next((name for name in overrides if action in OVERRIDE_BLOCKS.get(name, ())), None)
