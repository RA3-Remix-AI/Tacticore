"""Synthetic fixtures; no live game observations or real model credentials."""
from engine import Binding

SESSION = "45b37922-a953-4d54-bc3b-4a34804c1c56"
COMMANDER = "5cfc416a-8b8f-405a-9832-c163f8c1792b"
CONNECTION = "93190523-f22e-4ed5-8ddd-0327c6754297"


def binding(player=3, commander=COMMANDER):
    return Binding(SESSION, player, commander, "演练 · 突击指挥官", CONNECTION)


def snapshot(ident=1, at=100.0, player=3, **changes):
    result = {
        "schema_version": 1, "session_id": SESSION, "player_id": player,
        "snapshot_id": ident, "game_time_seconds": at, "source": "simulated", "paused": False,
        "resources": {"credits": 4000, "power_balance": 50},
        "capabilities": {"production_focus": ["native_baseline", "balanced", "anti_air", "anti_armor", "economy"], "regions": ["home_base", "north_expansion", "east_ore"]},
        "production": {"queued_count": 2, "idle_producers": 1, "own_roles": {"infantry": 8, "anti_air": 0}},
        "enemy_observations": [{"role": "air", "count": 3, "observed_at_game_seconds": at - 2, "currently_visible": True}],
        "events": ["enemy_air_seen"],
    }
    result.update(changes)
    return result


def policy(context, **changes):
    result = {
        "schema_version": 1, "commander_id": context["commander_id"],
        "session_id": context["session_id"], "player_id": context["player_id"],
        "snapshot_id": context["snapshot_id"], "based_on_game_time_seconds": context["game_time_seconds"],
        "valid_for_game_seconds": 30, "stance": "defend", "production_focus": "anti_air",
        "economy_policy": "stabilize", "tech_policy": "hold_current_tier",
        "budget": {"economy": .25, "army": .5, "tech": .05, "reserve": .2},
        "objective_region": "home_base", "reason_code": "air_threat",
    }
    result.update(changes)
    return result
