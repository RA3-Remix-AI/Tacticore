"""User-authorized strategic boundary, shared by request and dispatch gates.

This can only remove authority from an already qualified native scope. It never
maps broad intent to an exact building, unit template, quantity or unit order.
"""

import copy
import re

from .contracts import ContractError
from .strategic_contract import FOCUS_ACTIONS

KIND = "native_ai_details_v1"
STRATEGIC_ACTIONS = frozenset(
    {
        "budgeteconomy",
        "budgetarmy",
        "budgettech",
        "scout",
        "deployattack",
        "attackenemy",
        "raideconomy",
        "deploydefense",
        "regroup",
        "withdraw",
        "reinforce",
        "expand",
        "pauseconstruction",
        "advanceconstruction",
        "pauseproduction",
        "advanceproduction",
    }
) | frozenset(FOCUS_ACTIONS)


def battlefield_summary(context):
    """Summarize spatial evidence without selecting an action or a unit."""
    from macro_policy import restore_public_defaults

    public = restore_public_defaults(context)
    forces = public.get("own_forces", {})
    battlefield = public.get("working_memory", {}).get("battlefield", {})
    home = public.get("macro_policy_catalog", {}).get("deploydefense", {}).get("target_region")

    def cell(region):
        if type(region) is str and re.fullmatch(r"region_\d{1,3}_\d{1,3}", region):
            return tuple(int(value) for value in region.split("_")[1:])
        return None

    home_cell = cell(home)
    if (
        forces.get("source") != "bound_own_force_presence"
        or home_cell is None
        or battlefield.get("visibility_verified") is not True
    ):
        return None
    at = public["game_time_seconds"]
    fresh = [
        row
        for row in battlefield.get("regions", [])
        if row["relation"] == "enemy"
        and row["currently_visible"]
        and 0 <= at - row["observed_at_game_seconds"] <= 3
        and cell(row["region_id"]) is not None
    ]

    def nearby(region):
        anchor = cell(region)
        if anchor is None:
            return None
        return sum(
            sum(count for role, count in row["role_counts"].items() if role not in ("structure", "economy"))
            for row in fresh
            if max(abs(a - b) for a, b in zip(anchor, cell(row["region_id"]))) <= 1
        )

    mining = [
        dict(
            region_id=row["region_id"],
            ore_collectors=row["ore_collectors"],
            health_total=row["health_total"],
            nearby_enemy_mobile_observations=nearby(row["region_id"]),
        )
        for row in forces.get("economic_unit_regions", [])
    ]
    types = forces.get("unit_type_counts", {})
    scouts = sum(count for name, count in types.items() if name.endswith("ScoutInfantry"))
    engineers = sum(count for name, count in types.items() if name.endswith("Engineer"))
    return dict(
        source="current_lawful_regions_and_own_census",
        home_region=home,
        nearby_home_enemy_mobile_observations=nearby(home),
        mining_regions=mining,
        own_mobile_observations=sum(forces["mobile_role_counts"].values()),
        own_identified_scouts=scouts,
        own_identified_engineers=engineers,
        proximity="same_or_adjacent_512_cell_including_diagonals",
        distance_is_path_or_reachability=False,
        enemy_coverage="current_observations_only",
        zero_proves_area_clear=False,
        mobile_counts_include_scouts=True,
    )


def strategic_actions(actions):
    return tuple(action for action in actions if action in STRATEGIC_ACTIONS)


def restrict_snapshot(snapshot):
    result = copy.deepcopy(snapshot)
    control = result.get("macro_control")
    if type(control) is not dict:
        raise ContractError("strategic_boundary_macro_control_required")
    control["available_actions"] = list(strategic_actions(control["available_actions"]))
    control["production_counts"] = {}
    if "region_targets" in control:
        control["region_targets"] = {
            key: value for key, value in control["region_targets"].items() if key in control["available_actions"]
        }
    result["capabilities"]["production_focus"] = ["native_baseline"]
    return result


def restrict_context(context):
    result = copy.deepcopy(context)
    actions = strategic_actions(result.get("allowed_macro_actions", ()))
    result["allowed_macro_actions"] = list(actions)
    result["allowed_production_focus"] = ["native_baseline"]
    result["macro_policy_catalog"] = {
        key: value for key, value in result.get("macro_policy_catalog", {}).items() if key in actions
    }
    # Keep legitimate own infrastructure/forces and strategic observations,
    # but do not spend model input on precise queue/monetary execution contracts.
    for key in (
        "macro_production_feedback",
        "macro_construction_feedback",
        "macro_expansion_feedback",
        "macro_resource_feedback",
    ):
        result.pop(key, None)
    battlefield = result.get("working_memory", {}).get("battlefield")
    if (
        type(battlefield) is dict
        and type(battlefield.get("contacts")) is list
        and (battlefield["contacts"] or "contact_groups" not in battlefield)
    ):
        # Strategic decisions need lawful concentrations and observation ages,
        # not individually addressable targets. Keep visible/last-seen groups
        # separate and both age bounds; never rejuvenate an old observation.
        groups = {}
        for row in battlefield["contacts"]:
            owner = row.get("owner_player_id")
            if owner is not None and (type(owner) is not int or not 0 <= owner < 20):
                raise ContractError("strategic_boundary_contact_owner_invalid")
            unit_type = row.get("unit_type")
            if unit_type is not None and (
                type(unit_type) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", unit_type) is None
            ):
                raise ContractError("strategic_boundary_contact_type_invalid")
            key = (row["region_id"], row["role"], row["relation"], row["currently_visible"], owner, unit_type)
            at = row["observed_at_game_seconds"]
            if key not in groups:
                groups[key] = dict(
                    region_id=key[0],
                    role=key[1],
                    relation=key[2],
                    currently_visible=key[3],
                    observations=0,
                    oldest_game_seconds=at,
                    newest_game_seconds=at,
                    **({"owner_player_id": owner} if owner is not None else {}),
                    **({"unit_type": unit_type} if unit_type is not None else {}),
                )
            group = groups[key]
            group["observations"] += 1
            group["oldest_game_seconds"] = min(group["oldest_game_seconds"], at)
            group["newest_game_seconds"] = max(group["newest_game_seconds"], at)
        battlefield["contacts"] = []
        battlefield["contact_groups"] = list(groups.values())
    summary = battlefield_summary(result)
    if summary is not None:
        result["battlefield_summary"] = summary
    # Consecutive frame-only budget samples otherwise crowd out strategy memory
    # and lawful contact details. Preserve state changes and the latest sample.
    working = result.get("working_memory", {})
    feedback = working.get("recent_execution_feedback", [])
    compact = []
    for row in feedback:
        if compact and {key: value for key, value in compact[-1].items() if key != "observed_frame"} == {
            key: value for key, value in row.items() if key != "observed_frame"
        }:
            compact[-1] = row
        else:
            compact.append(row)
    if "recent_execution_feedback" in working:
        working["recent_execution_feedback"] = compact
    result["native_delegation"] = dict(
        kind=KIND,
        details_owner="native_ai",
        construction_and_production="native_ai_selects_and_executes",
        empty_actions="release_extra_preferences_not_global_native_stop",
        budget_actions="priority_preferences_not_construction_or_expansion_permission",
        exact_templates_quantities_coordinates_unit_orders=False,
    )
    strategy = result.get("macro_strategy")
    if type(strategy) is dict and type(strategy.get("fact_catalog")) is dict:
        if "capabilities.actions" in strategy["fact_catalog"]:
            strategy["fact_catalog"]["capabilities.actions"] = list(actions)
    return result


def validate_policy(policy):
    value = policy.public() if hasattr(policy, "public") else policy
    if type(value) is not dict:
        raise ContractError("strategic_boundary_policy_required")
    actions = value.get("macro_actions")
    if type(actions) not in (list, tuple) or any(
        type(action) is not str or action not in STRATEGIC_ACTIONS for action in actions
    ):
        raise ContractError("strategic_boundary_detailed_action_refused")
    if value.get("macro_production") is not None:
        raise ContractError("strategic_boundary_quantity_refused")
    if value.get("production_focus") != "native_baseline":
        raise ContractError("strategic_boundary_composition_refused")
    if value.get("tactical_tasks") not in (None, [], ()) or value.get("runtime_task") is not None:
        raise ContractError("strategic_boundary_unit_orders_refused")
    return policy
