"""Strategic delegation prompt v2: structured natural-language instructions.

Same output schema and call signature as v1. The text is built only from the
offered actions, their public catalog and the sections present in the request,
so new actions or opponents (for example focusenemy<player_id>) need no edit
here. Everything after the instructions (RegionMap, Enums, Example, Style) stays
machine-readable JSON, exactly as in v1.
"""

import json

PROMPT_VERSION = "v2"
REASONING_MAX_CHARS = 300
_EXAMPLE_REASONING = "No threat seen; keep native baseline."

_GROUP_HELP = {
    "work": "military intent",
    "development": "extra expansion, may join a military intent",
    "budget": "spending priority, no upfront cost",
    "construction_gate": "native base building",
    "production_gate": "native unit production",
    "enemy_focus": "preferred enemy player",
}
_GROUP_ORDER = ("work", "development", "budget", "enemy_focus", "construction_gate", "production_gate")


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def action_group(action, *, independent):
    """Classify one offered action into its at-most-one-per-plan group."""
    from native_unified_contract_v5 import FOCUS_PREFIX, GATE_ACTIONS

    if action.startswith(FOCUS_PREFIX):
        return "enemy_focus"
    if action.startswith("budget"):
        return "budget"
    if action in GATE_ACTIONS:
        return "construction_gate" if "construction" in action else "production_gate"
    if action == "expand" and independent:
        return "development"
    return "work"


def action_groups(offered, *, independent):
    """Return {group: [actions]} in a stable display order, omitting empty groups."""
    groups = {}
    for action in offered:
        groups.setdefault(action_group(action, independent=independent), []).append(action)
    return {name: groups[name] for name in _GROUP_ORDER if name in groups}


def _present(offered, *names):
    """Join the offered subset of names with '/', or return None."""
    found = [name for name in names if name in offered]
    return "/".join(found) if found else None


def _focus_player(action, catalog):
    """Enemy player of a focus intent: catalog target, else the focusenemy<id> grammar."""
    from native_unified_contract_v5 import FOCUS_ACTIONS

    player = catalog.get(action, {}).get("target_player_id")
    return player if player is not None else FOCUS_ACTIONS.get(action)


def _actions_section(groups, catalog):
    lines = ["# Your intents", "macro_actions holds exact strings, at most one per group:"]
    for name, actions in groups.items():
        listed = []
        for action in actions:
            player = _focus_player(action, catalog) if name == "enemy_focus" else None
            listed.append(action if player is None else action + "=player " + str(player))
        lines.append("- " + name + " (" + _GROUP_HELP[name] + "): " + "|".join(listed))
    lines.append(
        "A plan replaces all earlier intents, so repeat any intent you keep. "
        "[] restores native baseline execution. macro_policy_catalog explains each action."
    )
    return lines


def _situation_section(context):
    lines = [
        "# Situation",
        "- economy, own_forces: credits and audited own presence (foundations included; "
        "income, losses and building operation unverified).",
        "- battlefield contacts: lawful observations with owner, visibility and age; unseen is not absent.",
    ]
    if context.get("battlefield_summary") is not None:
        lines.append("- battlefield_summary: enemy units near home and mining (grid cells; counts include scouts).")
    match = context.get("working_memory", {}).get("match_state")
    if isinstance(match, dict):
        lines.append("- match_state: opponents, alliances and announced defeats.")
        if match.get("ally_player_ids"):
            lines.append(
                "- Allies "
                + ", ".join(str(pid) for pid in match["ally_player_ids"])
                + " fight on your side; pressure the enemies they are fighting."
            )
    lines.append(
        "- *_feedback: what the native AI did with your last intents, not mission success; "
        "native_account_shares are current spending weights."
    )
    return lines


def _choosing_section(offered, groups):
    """Winning heuristics that name only actions offered in this request."""
    steps = []
    defend = _present(offered, "deploydefense", "regroup", "withdraw")
    army = _present(offered, "budgetarmy")
    if defend:
        steps.append(
            "Danger first: enemies at home or mining -> "
            + defend
            + (" + " + army if army else "")
            + "; distant contact alone is no emergency."
        )
    grow = _present(offered, "expand", "budgeteconomy")
    tech = _present(offered, "budgettech")
    if grow or tech:
        parts = [grow + " early and when safe"] if grow else []
        if tech:
            parts.append(tech + " once the economy is stable")
        steps.append("Grow: " + "; ".join(parts) + ".")
    strike = _present(offered, "attackenemy", "deployattack")
    raid = _present(offered, "raideconomy")
    if strike or raid:
        parts = [strike] if strike else []
        if raid:
            parts.append(raid + " hits miners")
        steps.append("Strike when stronger or their army is away: " + "; ".join(parts) + ".")
    scout = _present(offered, "scout")
    if scout:
        steps.append(scout + " when enemy positions are unknown or old.")
    if "enemy_focus" in groups:
        steps.append("Focus the weakest or most dangerous enemy; re-focus after an elimination.")
    if "construction_gate" in groups or "production_gate" in groups:
        steps.append("Gates: pause to save credits, advance to recover.")
    steps.append(
        "Re-plan when credits pile up, the army stops growing or feedback shows no effect; "
        "never repeat failures. Unknown delivery forbids replay."
    )
    return ["# How to win"] + [str(number) + ". " + step for number, step in enumerate(steps, 1)]


def _output_section(context, groups, offered):
    lines = [
        "# Output",
        "One JSON object shaped like Example. Copy binding IDs and based_on_game_time_seconds; keep "
        "production_focus, macro_production, tactical_tasks and runtime_task as in Example. "
        "macro_actions length<=" + str(len(groups)) + "; objective_region=RegionMap[work action] or null.",
        "valid_for_game_seconds 5..60 from based_on_game_time_seconds, including inference and dispatch "
        "time; 60 for sustained intents. Expiry is never extended automatically.",
        "budget economy/army/tech/reserve each 0..1, sum 1, reserve 0.05..0.6. "
        "reasoning: your rationale, <=" + str(REASONING_MAX_CHARS) + " chars.",
    ]
    if isinstance(context.get("macro_strategy"), dict):
        from macro_policy import strategic_default_prompt

        defaults = (
            "Schema-masked verification flags, automatic_retry_allowed and grants_capability default "
            "false. Explicit values prevail."
            if "attackenemy" in offered
            else strategic_default_prompt(strategic_only=True)
        )
        lines.append(
            "Always include macro_strategy: strategy_id=null for a new or changed objective, else copy "
            "macro_strategy.current_strategy.strategy_id; 1..4 fact_catalog refs; condition lists 1..3 "
            "unique Enums.conditions; priorities 0..1, sum 1. " + defaults
        )
    lines.append("Style grants no authority.")
    return lines


def _example(context, example):
    example = dict(example, valid_for_game_seconds=60, reasoning=_EXAMPLE_REASONING)
    if not isinstance(context.get("macro_strategy"), dict):
        return example, {}
    from macro_strategy import STRATEGY_DECLARATION_SCHEMA

    schema = STRATEGY_DECLARATION_SCHEMA
    facts = context["macro_strategy"].get("fact_catalog", {})
    # The SDK sorts context keys. Keep preparation and send-time prompts identical.
    if facts.get("own.credits") is not None:
        ref = "own.credits"
    else:
        known = [key for key in sorted(facts) if facts[key] is not None]
        ref = known[0] if known else next(iter(sorted(facts)), None)
    example["macro_strategy"] = dict(
        strategy_id=None,
        objective="hold",
        phase="wait",
        public_fact_refs=[ref],
        expected_observation="no_change",
        continue_conditions=["capability_available"],
        replan_conditions=["facts_changed"],
        resource_priorities=dict(example["budget"]),
    )
    enums = {key: "|".join(schema[key]) for key in ("objective", "phase", "expected_observation")}
    enums["conditions"] = "|".join(schema["condition_values"])
    return example, enums


def prompt(profile, context, example, allowed, preferences):
    """Build the v2 system prompt; signature and trailing sections match v1."""
    from macro_policy import restore_public_defaults
    from native_unified_contract_v5 import INDEPENDENT_DEVELOPMENT_CONTRACT

    offered = list(context.get("allowed_macro_actions", []))
    catalog = restore_public_defaults(context).get("macro_policy_catalog", {})
    independent = context.get("macro_intent_contract") == INDEPENDENT_DEVELOPMENT_CONTRACT
    groups = action_groups(offered, independent=independent)
    region_map = {
        action: catalog[action]["target_region"]
        for action in offered
        if isinstance(catalog.get(action), dict) and "target_region" in catalog[action]
    }
    lines = [
        "# Role",
        "You are the strategic commander of player "
        + str(context.get("player_id"))
        + " in Red Alert 3. Goal: natural match victory - out-grow the enemies, keep your base, "
        "then destroy them. The original native AI owns ALL building, production, unit, movement, "
        "combat and skill details; you never choose templates, quantities, coordinates or unit orders.",
    ]
    lines += _actions_section(groups, catalog)
    lines += _situation_section(context)
    lines += _choosing_section(offered, groups)
    lines += _output_section(context, groups, offered)
    shaped, strategy_enums = _example(context, example)
    enums = {key: "|".join(value) if isinstance(value, list) else value for key, value in allowed.items()}
    enums.pop("production_focus", None)
    enums.update(strategy_enums)
    return (
        "\n".join(lines)
        + "\nRegionMap: "
        + _compact(region_map)
        + "\nEnums: "
        + _compact(enums)
        + "\nExample: "
        + _compact(shaped)
        + "\nStyle: "
        + _compact(preferences)
    )
