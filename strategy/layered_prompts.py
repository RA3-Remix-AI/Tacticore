"""System prompts of the three decision layers (commander, economy, tactical).

The user message is the layer's own slice of the shared WorldState (JSON). Each
prompt names only that layer's duty, its output shape and the commander persona
the reasoning must be written in. Nothing here grants execution: the host
validates the reply and the composer decides what reaches the native AI.
"""

import json

from layered_contract import (
    COMPOSITION_NEEDS,
    OVERRIDES,
    POSTURES,
    REASONING_MAX_CHARS,
    REVIEW_EVENTS,
    ROUTES,
)

LAYERS = ("commander", "economy", "tactical")


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _persona(profile):
    traits = getattr(profile, "traits", "") or ""
    return [
        "# Persona",
        traits.strip() or "A disciplined Soviet commander.",
        "Write reasoning as this commander speaking in the first person (Chinese), <="
        + str(REASONING_MAX_CHARS)
        + " characters, naming the fact that drove the choice.",
    ]


def _common():
    return [
        "# Rules",
        "- Return exactly one JSON object shaped like Example; no prose, no Markdown.",
        "- The user message is lawful own-view data only; unseen is not absent, old is not current.",
        "- The original native AI builds, places, produces, moves and fights. You set intents only.",
    ]


def _commander(context):
    options = context.get("options", {})
    lines = [
        "# Role",
        "You are the commander (总指挥) of player "
        + str(context.get("player_id"))
        + " in Red Alert 3. You choose the victory route, split resources and pick the primary enemy. "
        "Two staff officers follow your directive: economy (tech, expansion, gates) and tactical (army posture).",
        "# Directive fields",
        "- route: " + "|".join(ROUTES) + ".",
        "- resource_split: economy/army/tech/reserve shares 0..1 summing to 1; the largest of "
        "economy/army/tech becomes the native budget preference.",
        "- primary_enemy: one id from options.enemies or null.",
        "- overrides: hard limits for staff: " + "|".join(OVERRIDES) + ". all_in implies no_expansion and no_tech.",
        "- valid_for_s: 60..300 game seconds. review_when: events that make you decide again early: "
        + "|".join(REVIEW_EVENTS)
        + ".",
        "- habits: patterns the enemy can read from you; when flagged, change them for a reason.",
        "- staff: what your officers last proposed and what you vetoed.",
    ]
    if options.get("opening_variants"):
        lines.append(
            "- This is the pre-match call: also set opening_variant to one id of options.opening_variants "
            "for the first three minutes (scenario lists map, enemies and difficulty)."
        )
    example = dict(
        route="steady_growth",
        resource_split=dict(economy=0.4, army=0.4, tech=0.1, reserve=0.1),
        primary_enemy=(options.get("enemies") or [None])[0],
        overrides=[],
        reasoning="先看清战线，再集中突破。",
        valid_for_s=120,
        review_when=["base_under_attack", "enemy_defeated"],
    )
    if options.get("opening_variants"):
        example["opening_variant"] = options["opening_variants"][0]
    return lines, example


def _economy(context):
    lines = [
        "# Role",
        "You are the economy officer (经济参谋). Decide expansion and the native base-building and "
        "production gates inside the commander's directive. Power and ore-collector parity decide early games.",
        "# Fields",
        "- expand: now|hold|null (null = native default). Forbidden when directive.overrides has no_expansion.",
        "- construction / production: advance|pause|null. advance speeds native scheduling, pause saves credits.",
        "- Record-only for now (no executor yet, still stated honestly): tech_timing now|after_expansion|hold|null, "
        "capacity_target {war_factory, ore_collector, ...}, protocol_pick_preference [names], "
        "composition_answer satisfy|decline|null for tactical.composition_need.",
        "- valid_for_s: 20..90.",
    ]
    example = dict(
        expand="hold",
        construction="advance",
        production=None,
        tech_timing="after_expansion",
        capacity_target=dict(war_factory=2, ore_collector=6),
        protocol_pick_preference=[],
        composition_answer=None,
        reasoning="矿车数领先前不急着扩张，先把电和矿车补齐。",
        valid_for_s=60,
    )
    return lines, example


def _tactical(context):
    postures = context.get("options", {}).get("postures") or list(POSTURES)
    lines = [
        "# Role",
        "You are the tactical officer (战术参谋). Choose one army posture inside the commander's directive.",
        "# Fields",
        "- posture: " + "|".join(postures) + " (options.postures are executable now; patrol is record-only).",
        "- harass hits enemy ore collectors and must stop when escorted; all_in only under an all_in directive.",
        "- target {enemy, region}, composition_need [" + "|".join(COMPOSITION_NEEDS) + "], doctrine, "
        "power_usage aggressive|save_for_defense: record-only requests; production belongs to the economy officer.",
        "- valid_for_s: 10..60. Every attack or harassment has a time box; plan the exit.",
    ]
    example = dict(
        posture="scout",
        target=dict(enemy=(context.get("options", {}).get("enemies") or [None])[0], region=None),
        composition_need=[],
        doctrine=None,
        power_usage=None,
        reasoning="窗口太整齐了。先派人看一眼他们的退路。",
        valid_for_s=30,
    )
    return lines, example


_BUILDERS = dict(commander=_commander, economy=_economy, tactical=_tactical)


def system_prompt(profile, context):
    """Build the system prompt for context['decision_layer']."""
    layer = context.get("decision_layer")
    if layer not in _BUILDERS:
        raise ValueError("decision_layer_unknown")
    duty, example = _BUILDERS[layer](context)
    return "\n".join(duty + _common() + _persona(profile)) + "\nExample: " + _compact(example)
