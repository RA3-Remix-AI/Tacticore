"""Shared situation for the decision layers, derived once from the lawful request context.

WorldState reads only what the existing prepared context already holds (own
economy and forces, lawful contact groups, battlefield_summary, match_state).
EventDetector turns two consecutive WorldStates into edge-triggered events.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TECH_BUILDINGS = ("super_reactor", "battle_lab")
NON_COMBAT_ROLES = ("structure", "economy")
# Enemy combat observations near our home that count as an attack on the base.
BASE_ATTACK_MIN = 3
# Visible enemy combat observations that count as their main force.
MAIN_FORCE_MIN = 6
MAX_ENEMIES = 8
MAX_REGIONS = 4


def _restore(context):
    try:
        from macro_policy import restore_public_defaults

        return restore_public_defaults(context)
    except (ImportError, ValueError):
        return dict(context)


def _count(value):
    return value if type(value) is int and value >= 0 else 0


@dataclass
class WorldState:
    """Own-view facts at one game time; slices feed the three layers."""

    game_time: float
    snapshot_id: int | None
    credits: float | None
    power_balance: float | None
    own_mobile: int
    own_roles: dict
    ore_collectors: int
    refineries: int
    bases: int
    buildings: dict
    tech_buildings: tuple
    mining_regions: list
    home_region: str | None
    near_home_enemy: int | None
    enemies: dict
    enemy_visible_combat: int
    enemy_newest_age_s: float | None
    opponents: tuple
    defeated: tuple
    allies: tuple
    allowed_actions: tuple
    feedback: dict = field(default_factory=dict)

    @property
    def mining_threat(self):
        return max((row.get("nearby_enemy") or 0 for row in self.mining_regions), default=0)

    @property
    def remaining_enemies(self):
        return tuple(pid for pid in self.opponents if pid not in self.defeated)

    def enemy_rows(self):
        """Bounded per-enemy view for prompts: at most 8 players, 4 base and 4 mining regions each."""
        return [
            dict(id=pid, **dict(row, bases=row["bases"][:MAX_REGIONS], mining=row["mining"][:MAX_REGIONS]))
            for pid, row in sorted(self.enemies.items())[:MAX_ENEMIES]
        ]

    def force_ratio(self):
        """Own mobile presence over visible enemy combat observations (None when no enemy is seen)."""
        if self.enemy_visible_combat <= 0:
            return None
        return round(self.own_mobile / self.enemy_visible_combat, 2)

    def public(self):
        return dict(
            t=round(self.game_time, 1),
            credits=self.credits,
            power=self.power_balance,
            own=dict(
                mobile=self.own_mobile,
                roles=self.own_roles,
                ore_collectors=self.ore_collectors,
                refineries=self.refineries,
                bases=self.bases,
                tech=list(self.tech_buildings),
            ),
            home=self.home_region,
            threat=dict(near_home=self.near_home_enemy, at_mining=self.mining_threat),
            enemies=self.enemy_rows(),
            enemy_visible_combat=self.enemy_visible_combat,
            enemy_info_age_s=self.enemy_newest_age_s,
            force_ratio=self.force_ratio(),
            match=dict(remaining=list(self.remaining_enemies), defeated=list(self.defeated), allies=list(self.allies)),
        )

    def economy_slice(self):
        return dict(
            t=round(self.game_time, 1),
            credits=self.credits,
            power=self.power_balance,
            ore_collectors=self.ore_collectors,
            refineries=self.refineries,
            bases=self.bases,
            buildings=self.buildings,
            tech=list(self.tech_buildings),
            mining=self.mining_regions,
            threat=dict(near_home=self.near_home_enemy, at_mining=self.mining_threat),
            native_feedback={a: s for a, s in self.feedback.items() if a in ECONOMY_FEEDBACK},
        )

    def tactical_slice(self):
        return dict(
            t=round(self.game_time, 1),
            own=dict(mobile=self.own_mobile, roles=self.own_roles, ore_collectors=self.ore_collectors),
            home=self.home_region,
            threat=dict(near_home=self.near_home_enemy, at_mining=self.mining_threat),
            enemies=self.enemy_rows(),
            enemy_visible_combat=self.enemy_visible_combat,
            enemy_info_age_s=self.enemy_newest_age_s,
            force_ratio=self.force_ratio(),
            native_feedback={a: s for a, s in self.feedback.items() if a not in ECONOMY_FEEDBACK},
        )


ECONOMY_FEEDBACK = frozenset(
    {"expand", "advanceconstruction", "pauseconstruction", "advanceproduction", "pauseproduction"}
)


def _enemy_view(battlefield, at):
    """Per enemy player: visible combat count, newest sighting, base and mining regions seen."""
    enemies = {}
    newest = None
    visible_combat = 0
    for row in battlefield.get("contact_groups", []) if isinstance(battlefield, dict) else []:
        if not isinstance(row, dict) or row.get("relation") != "enemy":
            continue
        owner = row.get("owner_player_id")
        seen = row.get("newest_game_seconds")
        entry = enemies.setdefault(owner, dict(visible_combat=0, last_seen_s=None, bases=[], mining=[]))
        if type(seen) in (int, float):
            entry["last_seen_s"] = max(entry["last_seen_s"] or 0, round(seen, 1))
            newest = seen if newest is None else max(newest, seen)
        role = row.get("role")
        count = _count(row.get("observations"))
        if role == "structure" and row.get("region_id") not in entry["bases"]:
            entry["bases"].append(row.get("region_id"))
        elif role == "economy" and row.get("region_id") not in entry["mining"]:
            entry["mining"].append(row.get("region_id"))
        elif role not in NON_COMBAT_ROLES and row.get("currently_visible") is True:
            entry["visible_combat"] += count
            visible_combat += count
    for row in battlefield.get("regions", []) if isinstance(battlefield, dict) else []:
        if not isinstance(row, dict) or row.get("relation") != "enemy":
            continue
        roles = row.get("role_counts") or {}
        seen = row.get("observed_at_game_seconds")
        if type(seen) in (int, float):
            newest = seen if newest is None else max(newest, seen)
        entry = enemies.setdefault(None, dict(visible_combat=0, last_seen_s=None, bases=[], mining=[]))
        if _count(roles.get("structure")) and row.get("region_id") not in entry["bases"]:
            entry["bases"].append(row.get("region_id"))
        if _count(roles.get("economy")) and row.get("region_id") not in entry["mining"]:
            entry["mining"].append(row.get("region_id"))
    if None in enemies and not any(enemies[None].values()):
        del enemies[None]
    age = round(at - newest, 1) if newest is not None else None
    return {key if key is not None else -1: value for key, value in enemies.items()}, visible_combat, age


def build_world_state(context) -> WorldState:
    """Derive the shared situation from one prepared (or public) request context."""
    public = _restore(context)
    at = float(public.get("game_time_seconds") or 0.0)
    working = public.get("working_memory", {}) if isinstance(public.get("working_memory"), dict) else {}
    economy = working.get("economy", {}) if isinstance(working.get("economy"), dict) else {}
    forces = public.get("own_forces", {}) if isinstance(public.get("own_forces"), dict) else {}
    summary = public.get("battlefield_summary") if isinstance(public.get("battlefield_summary"), dict) else {}
    match = working.get("match_state", {}) if isinstance(working.get("match_state"), dict) else {}
    buildings = {k: _count(v) for k, v in (forces.get("building_presence_counts") or {}).items()}
    roles = {k: _count(v) for k, v in (forces.get("mobile_role_counts") or {}).items()}
    if not roles:
        roles = {k: _count(v) for k, v in (economy.get("own_roles") or {}).items() if k not in NON_COMBAT_ROLES}
    regions = forces.get("regions") or []
    bases = sum(_count(row.get("construction_yards")) for row in regions if isinstance(row, dict))
    mining = [
        dict(
            region=row.get("region_id"),
            ore_collectors=_count(row.get("ore_collectors")),
            nearby_enemy=row.get("nearby_enemy_mobile_observations"),
        )
        for row in summary.get("mining_regions", [])
        if isinstance(row, dict)
    ]
    catalog = public.get("macro_policy_catalog", {}) if isinstance(public.get("macro_policy_catalog"), dict) else {}
    home = summary.get("home_region") or (catalog.get("deploydefense") or {}).get("target_region")
    enemies, visible_combat, age = _enemy_view(working.get("battlefield", {}), at)
    feedback = {
        row.get("action"): row.get("status")
        for row in (public.get("macro_unified_feedback") or {}).get("observations", [])
        if isinstance(row, dict)
    }
    return WorldState(
        game_time=at,
        snapshot_id=public.get("snapshot_id"),
        credits=economy.get("credits"),
        power_balance=economy.get("power_balance"),
        own_mobile=sum(roles.values()),
        own_roles=roles,
        ore_collectors=_count((forces.get("economic_unit_presence_counts") or {}).get("ore_collector")),
        refineries=buildings.get("refinery", 0),
        bases=bases or buildings.get("construction_yard", 0),
        buildings=buildings,
        tech_buildings=tuple(name for name in TECH_BUILDINGS if buildings.get(name)),
        mining_regions=mining,
        home_region=home,
        near_home_enemy=summary.get("nearby_home_enemy_mobile_observations"),
        enemies=enemies,
        enemy_visible_combat=visible_combat,
        enemy_newest_age_s=age,
        opponents=tuple(match.get("opponent_player_ids") or ()),
        defeated=tuple(match.get("defeated_opponent_ids") or ()),
        allies=tuple(match.get("ally_player_ids") or ()),
        allowed_actions=tuple(public.get("allowed_macro_actions") or ()),
        feedback=feedback,
    )


class EventDetector:
    """Edge-triggered events between consecutive WorldStates; each fires once per occurrence."""

    def __init__(self):
        self.previous = None
        self.seen_bases = set()
        self.seen_mining = set()
        self.main_force = False
        self.base_attack = False

    def detect(self, world: WorldState) -> list[dict]:
        events = []

        def emit(kind, **facts):
            events.append(dict(kind=kind, at=round(world.game_time, 1), **facts))

        threshold = max(MAIN_FORCE_MIN, world.own_mobile // 2)
        if not self.main_force and world.enemy_visible_combat >= threshold:
            self.main_force = True
            emit("enemy_main_force_contact", visible_combat=world.enemy_visible_combat)
        elif self.main_force and world.enemy_visible_combat < threshold // 2:
            self.main_force = False
        near = world.near_home_enemy or 0
        if not self.base_attack and near >= BASE_ATTACK_MIN:
            self.base_attack = True
            emit("base_under_attack", near_home=near)
        elif self.base_attack and near == 0:
            self.base_attack = False
        for pid, row in sorted(world.enemies.items()):
            for region in row["bases"]:
                if (pid, region) not in self.seen_bases:
                    self.seen_bases.add((pid, region))
                    emit("scouting_report", found="enemy_base", player=pid, region=region)
            for region in row["mining"]:
                if (pid, region) not in self.seen_mining:
                    self.seen_mining.add((pid, region))
                    emit("scouting_report", found="enemy_mining", player=pid, region=region)
        previous = self.previous
        if previous is not None:
            if world.ore_collectors < previous.ore_collectors:
                emit("ore_collector_lost", lost=previous.ore_collectors - world.ore_collectors)
            for pid in world.defeated:
                if pid not in previous.defeated:
                    emit("enemy_defeated", player=pid)
            for name in world.tech_buildings:
                if name not in previous.tech_buildings:
                    emit("tech_unlocked", building=name)
            for name in ("bases", "refineries"):
                before, after = getattr(previous, name), getattr(world, name)
                if after != before:
                    emit("expansion_changed", what=name, direction="gained" if after > before else "lost")
        self.previous = world
        return events
