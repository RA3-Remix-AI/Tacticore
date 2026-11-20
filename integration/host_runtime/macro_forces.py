"""Own roster locations for macro planning; presence never grants recruitment."""

import math
import re

from .contracts import ContractError

MOBILE_ROLES = ("infantry", "armor", "anti_air", "anti_armor", "air", "naval")
NAMED_UNITS = {
    "conscript": ("0x19ab11af", "SovietAntiInfantryInfantry"),
    "flak_trooper": ("0x2c358c61", "SovietAntiVehicleInfantry"),
    "hammer_tank": ("0x94b3590b", "SovietAntiVehicleVehicleTech1"),
    "war_bear": ("0x33026fa1", "SovietScoutInfantry"),
}
NAMED_BUILDINGS = {
    "construction_yard": ("0xc16ff13f", "SovietConstructionYard"),
    "power_plant": ("0xcf8d9f20", "SovietPowerPlant"),
    "barracks": ("0x80d4ea1e", "SovietBarracks"),
    "war_factory": ("0xd50c222e", "SovietWarFactory"),
    "refinery": ("0xc45aaeab", "SovietRefinery"),
    "super_reactor": ("0x524bbd01", "SovietPowerPlantAdvanced"),
    "battle_lab": ("0xb7377639", "SovietTechStructure"),
}
# Exact inherited Core11 definitions, with Core12 alias and all active Mod
# streams checked in own-miner-compiled-identity-audit-v1.json. Owned census
# only. These identities never extend the enemy visibility allowlist.
OWN_ORE_COLLECTOR_TEMPLATES = frozenset(("0xf6dac2a4", "0x951764b9"))
MAX_REGIONS = 4


def observe_forces(census, safety):
    if (
        type(census) is not dict
        or census.get("enemy_details_read") is not False
        or type(census.get("frame")) is not int
        or not 0 < census["frame"] <= 0xFFFFFFFF
        or type(census.get("own_objects")) is not list
        or len(census["own_objects"]) > 8192
        or type(safety) is not dict
        or type(safety.get("templates")) is not dict
    ):
        raise ContractError("macro_forces_source")
    templates = safety["templates"]
    roles = {}
    named = dict.fromkeys(NAMED_UNITS, 0)
    unit_types = {}
    buildings = {
        name: 0
        for name, (template, asset) in NAMED_BUILDINGS.items()
        if templates.get(template, {}).get("source_audited_no_intrinsic_stealth") is True
        and templates[template].get("template") == asset
    }
    regions = {}
    economic_regions = {}
    seen = set()
    unclassified = 0
    unlocated = 0
    ore_collectors = 0
    for row in census["own_objects"]:
        if type(row) is not dict:
            raise ContractError("macro_forces_shape")
        oid = row.get("thing_id")
        hp = row.get("hp")
        xyz = row.get("xyz")
        if (
            type(oid) is not int
            or not 0 < oid <= 0xFFFFFFFF
            or oid in seen
            or type(hp) not in (int, float)
            or not math.isfinite(hp)
            or hp <= 0
            or type(xyz) is not list
            or len(xyz) != 3
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in xyz)
        ):
            raise ContractError("macro_forces_own_identity_or_position")
        seen.add(oid)
        if row.get("type_hash") in OWN_ORE_COLLECTOR_TEMPLATES:
            ore_collectors += 1
            if 0 <= xyz[0] < 65536 and 0 <= xyz[1] < 65536:
                region = "region_" + str(int(xyz[0] // 512)) + "_" + str(int(xyz[1] // 512))
                mining = economic_regions.setdefault(region, dict(ore_collectors=0, health_total=0.0))
                mining["ore_collectors"] += 1
                mining["health_total"] += hp
            continue
        safe = templates.get(row.get("type_hash"))
        if not safe or safe.get("source_audited_no_intrinsic_stealth") is not True:
            unclassified += 1
            continue
        role = safe.get("role")
        if role not in MOBILE_ROLES and role not in ("structure", "economy"):
            raise ContractError("macro_forces_template_role")
        if role in MOBILE_ROLES:
            roles[role] = roles.get(role, 0) + 1
            asset = safe.get("template")
            if type(asset) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", asset):
                unit_types[asset] = unit_types.get(asset, 0) + 1
        for name, (template, unit) in NAMED_UNITS.items():
            if row["type_hash"] == template:
                if safe.get("template") != unit:
                    raise ContractError("macro_forces_template_binding")
                named[name] += 1
        for name, (template, asset) in NAMED_BUILDINGS.items():
            if row["type_hash"] == template:
                if safe.get("template") != asset:
                    raise ContractError("macro_forces_template_binding")
                buildings[name] += 1
        if not (0 <= xyz[0] < 65536 and 0 <= xyz[1] < 65536):
            unlocated += 1
            continue
        region = "region_" + str(int(xyz[0] // 512)) + "_" + str(int(xyz[1] // 512))
        counts = regions.setdefault(region, dict(mobile=0, construction_yards=0))
        counts["mobile"] += int(role in MOBILE_ROLES)
        counts["construction_yards"] += int(safe.get("template") == "SovietConstructionYard")
    # Prioritize known home regions, then concentrations. Omission is explicit.
    ordered = sorted(regions, key=lambda r: (-regions[r]["construction_yards"], -regions[r]["mobile"], r))
    retained = [dict(region_id=r, **regions[r]) for r in ordered[:MAX_REGIONS]]
    return dict(
        source="bound_own_force_presence",
        observed_frame=census["frame"],
        own_perspective=True,
        enemy_details_read=False,
        mobile_role_counts=roles,
        named_unit_counts=named,
        regions=retained,
        unit_type_counts=unit_types,
        building_presence_counts=buildings,
        presence_includes_unfinished_foundations=True,
        building_operation_verified=False,
        economic_unit_presence_counts=dict(ore_collector=ore_collectors),
        economic_unit_regions=[
            dict(region_id=region, **economic_regions[region]) for region in sorted(economic_regions)[:16]
        ],
        omitted_economic_region_count=max(0, len(economic_regions) - 16),
        income_verified=False,
        omitted_region_count=max(0, len(regions) - MAX_REGIONS),
        unclassified_objects=unclassified,
        unlocated_classified_objects=unlocated,
        coverage="audited_template_presence_only",
        ready_for_combat_verified=False,
        recruitability_verified=False,
        unit_operation_policy="native_ai",
    )


def compact_forces(value, game_seconds):
    if (
        type(value) is not dict
        or value.get("source") != "bound_own_force_presence"
        or value.get("own_perspective") is not True
        or value.get("enemy_details_read") is not False
    ):
        raise ContractError("macro_forces_source")
    frame = value.get("observed_frame")
    if (
        type(game_seconds) not in (int, float)
        or not math.isfinite(game_seconds)
        or type(frame) is not int
        or not 0 < frame <= 0xFFFFFFFF
        or not -15 <= game_seconds * 15 - frame <= 30
    ):
        raise ContractError("macro_forces_stale")

    def count(v):
        if type(v) is not int or not 0 <= v <= 8192:
            raise ContractError("macro_forces_count")
        return v

    roles = value.get("mobile_role_counts")
    named = value.get("named_unit_counts")
    regions = value.get("regions")
    if (
        type(roles) is not dict
        or set(roles) - set(MOBILE_ROLES)
        or type(named) is not dict
        or set(named) != set(NAMED_UNITS)
        or type(regions) is not list
        or len(regions) > MAX_REGIONS
    ):
        raise ContractError("macro_forces_shape")
    public = []
    seen = set()
    for row in regions:
        if type(row) is not dict:
            raise ContractError("macro_forces_shape")
        region = row.get("region_id")
        if (
            type(region) is not str
            or re.fullmatch(r"region_(?:0|[1-9][0-9]{0,2})_(?:0|[1-9][0-9]{0,2})", region) is None
            or region in seen
        ):
            raise ContractError("macro_forces_region")
        if any(int(v) >= 128 for v in region.split("_")[1:]):
            raise ContractError("macro_forces_region")
        seen.add(region)
        public.append(
            dict(
                region_id=region,
                mobile=count(row.get("mobile")),
                construction_yards=count(row.get("construction_yards")),
            )
        )
    total = sum(count(v) for v in roles.values())
    if total > 8192 or sum(r["mobile"] for r in public) > total or sum(count(v) for v in named.values()) > total:
        raise ContractError("macro_forces_count_consistency")
    result = dict(
        source="bound_own_force_presence",
        observed_frame=frame,
        own_perspective=True,
        enemy_details_read=False,
        mobile_role_counts={k: count(v) for k, v in roles.items()},
        named_unit_counts={k: count(v) for k, v in named.items()},
        regions=public,
        **{
            k: count(value.get(k))
            for k in ("omitted_region_count", "unclassified_objects", "unlocated_classified_objects")
        },
        coverage="audited_template_presence_only",
        ready_for_combat_verified=False,
        recruitability_verified=False,
        unit_operation_policy="native_ai",
    )
    if "unit_type_counts" in value:
        unit_types = value["unit_type_counts"]
        if (
            type(unit_types) is not dict
            or len(unit_types) > 64
            or any(
                type(asset) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", asset) is None
                for asset in unit_types
            )
        ):
            raise ContractError("macro_forces_unit_types")
        counts = {asset: count(number) for asset, number in unit_types.items()}
        if sum(counts.values()) > total:
            raise ContractError("macro_forces_count_consistency")
        result["unit_type_counts"] = counts
    # Older saved observations have no building projection. Absence remains
    # unknown, while an audited template with no own occurrence may report zero.
    if "building_presence_counts" in value:
        buildings = value["building_presence_counts"]
        if type(buildings) is not dict or set(buildings) - set(NAMED_BUILDINGS):
            raise ContractError("macro_forces_shape")
        counts = {name: count(number) for name, number in buildings.items()}
        if sum(counts.values()) > 8192:
            raise ContractError("macro_forces_count_consistency")
        result.update(
            building_presence_counts=counts,
            presence_includes_unfinished_foundations=True,
            building_operation_verified=False,
        )
    if "economic_unit_presence_counts" in value:
        economic = value["economic_unit_presence_counts"]
        if type(economic) is not dict or set(economic) != {"ore_collector"}:
            raise ContractError("macro_forces_shape")
        result.update(
            economic_unit_presence_counts={"ore_collector": count(economic["ore_collector"])}, income_verified=False
        )
        if "economic_unit_regions" in value:
            rows = value["economic_unit_regions"]
            if type(rows) is not list or len(rows) > 16:
                raise ContractError("macro_forces_economic_regions")
            economic_public = []
            seen = set()
            for row in rows:
                if type(row) is not dict:
                    raise ContractError("macro_forces_economic_regions")
                region = row.get("region_id")
                health = row.get("health_total")
                if (
                    type(region) is not str
                    or re.fullmatch(r"region_(?:0|[1-9][0-9]{0,2})_(?:0|[1-9][0-9]{0,2})", region) is None
                    or any(int(v) >= 128 for v in region.split("_")[1:])
                    or region in seen
                    or type(health) not in (int, float)
                    or not math.isfinite(health)
                    or not 0 < health <= 1e9
                ):
                    raise ContractError("macro_forces_economic_regions")
                seen.add(region)
                economic_public.append(
                    dict(
                        region_id=region, ore_collectors=count(row.get("ore_collectors")), health_total=round(health, 2)
                    )
                )
            if sum(row["ore_collectors"] for row in economic_public) > economic["ore_collector"]:
                raise ContractError("macro_forces_count_consistency")
            result.update(
                economic_unit_regions=economic_public,
                omitted_economic_region_count=count(value.get("omitted_economic_region_count")),
            )
    return result
