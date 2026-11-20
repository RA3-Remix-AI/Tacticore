"""Compile a strategic raid preference using the original Medium native task."""

import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as E

from stage_commanders import SDK, q, safe_output, sage_hash
from stage_macro_probe import compile_probe, digest
from stage_strategic_expansion_v1 import normalized, canonical_sha
from stage_native_enemy_attack_v1 import payload, reconstruct_base, PREFIX, CANDIDATE_TARGET
from validate_side_imports import read_stream

BASE_PACKAGE = "ef94fe04a8c51d65d24498e37bc40f1cc5f2b28daa5a1acb74f2d54ae89fb1ea"
STOCK_PATH = SDK / "SAGEXML/SkirmishAI/States/SovietBaseStates.xml"
STOCK_ID = "SickleHarrassment_MEDIUM"
ACTION = "raideconomy"
STATE = PREFIX + "_RaidEconomy"
FLAG = "/" + PREFIX + "_raideconomy"


def generate(xml, report, stock):
    root = E.fromstring(xml)
    report = copy.deepcopy(report)
    if (
        stock.get("id") != STOCK_ID
        or stock.find(q("TargetHeuristic")).get("TargetHeuristic") != "SafestToGroundHarvesterHeuristic"
    ):
        raise ValueError("raid_original_native_task_required")
    raid = copy.deepcopy(stock)
    raid.set("id", STATE)
    raid.set("MaxRunningCopies", "1")
    heur = raid.find(q("Heuristic"))
    # Commander owns the strategic decision to send a raid. Keep native task
    # readiness/recruitment/combat rules, replacing only stock timing and the
    # strategic preference to wait while enemies are near the base.
    for name in ("TimerHeuristic", "EnemyNearbyHeuristic"):
        node = heur.find(q(name))
        if node is None:
            raise ValueError("raid_stock_strategic_guard_changed")
        heur.remove(node)
    E.SubElement(heur, q("ScriptedFlagHeuristic"), FlagName=FLAG)
    E.SubElement(heur, q("ConstantHeuristic"), Weight="100")
    raid.find(q("Tactic")).set("EndIfStateTurnsOff", "true")
    # Audit the complete native recruitment, target, threat, timer and micro
    # rules after removing only the explicit external preference/lifecycle.
    check = copy.deepcopy(raid)
    check.set("id", STOCK_ID)
    del check.attrib["MaxRunningCopies"]
    del check.find(q("Tactic")).attrib["EndIfStateTurnsOff"]
    gate = check.find(q("Heuristic"))
    gate.remove(gate.find(q("ScriptedFlagHeuristic")))
    gate.remove(gate.find(q("ConstantHeuristic")))
    expected = copy.deepcopy(stock)
    for name in ("TimerHeuristic", "EnemyNearbyHeuristic"):
        gate = expected.find(q("Heuristic"))
        gate.remove(gate.find(q(name)))
    if normalized(check) != normalized(expected):
        raise ValueError("raid_native_execution_changed")
    personality = root.find(q("AIPersonalityDefinition"))
    E.SubElement(personality, q("StrategicState"), id=STATE, State=STATE)
    root.append(raid)
    # Ordinary attack also needs to honor the native enemy selector. The
    # existing all-enemy target explicitly bypasses the selector preference.
    target = next(node for node in root if node.get("id") == CANDIDATE_TARGET)
    if target.get("HighestPriorityEnemyPlayersOnly") != "false":
        raise ValueError("raid_baseline_target_changed")
    target.set("HighestPriorityEnemyPlayersOnly", "true")
    report["flags"][ACTION] = FLAG
    report["strategic_actions"].append(ACTION)
    report["assets"].append(
        dict(
            name="AIStrategicStateDefinition:" + STATE,
            type_id=hex(sage_hash("AIStrategicStateDefinition")),
            instance_id=hex(sage_hash(STATE.lower())),
        )
    )
    report["consumers"].append(
        dict(
            action=ACTION,
            domain="native_attack",
            flag=FLAG,
            state="AIStrategicStateDefinition:" + STATE,
            target_policy="original_native_safest_ground_harvester",
            stock_state=STOCK_ID,
            stock_target="SafestToGroundHarvesterHeuristic",
            native_ai_selects_and_operates_group=True,
            native_task_readiness_preserved=True,
            dispatch_timing_owner="agent",
            exact_composition_parameters_exposed=False,
            mission_success_verified=False,
        )
    )
    attack = next(row for row in report["consumers"] if row["action"] == "attackenemy")
    attack.update(
        target_policy="native_closest_ground_structure_preferred_enemy", primary_then_secondary_enemy_fallback=False
    )
    report.update(
        variant="strategic_raid_and_independent_development_v1",
        field_verified=False,
        compiled=False,
        deployed=False,
        product_capability_granted=False,
        flag_count=11,
        transport_profile_revision=7,
        transport_known_mask=2047,
        transport_exclusive_masks=[0x70, 0x58F],
        source_sha256=digest(__file__),
        raid_stock_source=str(STOCK_PATH),
        raid_stock_source_sha256=digest(STOCK_PATH),
        raid_stock_canonical_sha256=canonical_sha(stock),
        raid_native_task_preserved=True,
        raid_task_cancel_on_preference_off=True,
    )
    E.indent(root, space="  ")
    return E.tostring(root, encoding="utf-8", xml_declaration=True), report


def audit(baseline, output, report):
    added = "AIStrategicStateDefinition:" + STATE
    allowed = {"AIPersonalityDefinition:" + report["personality"], "AITargetingHeuristic:" + CANDIDATE_TARGET}
    streams = []
    for stem in ("mod", "mod_M", "mod_L"):
        before = read_stream(baseline / "package/data" / (stem + ".manifest"))
        after = read_stream(output / "package/data" / (stem + ".manifest"))
        old = {row["name"]: row for row in before["rows"]}
        new = {row["name"]: row for row in after["rows"]}
        if set(new) - set(old) != {added} or set(old) - set(new):
            raise ValueError("raid_asset_set_changed")
        changed = []
        for name, row in old.items():
            other = new[name]
            same = all(
                row[key] == other[key]
                for key in ("refs", "type_id", "instance_id", "type_hash", "instance_hash", "flags")
            )
            same = same and all(
                payload(before, row, ext) == payload(after, other, ext) for ext in ("bin", "imp", "relo")
            )
            if not same:
                changed.append(name)
        if set(changed) != allowed:
            raise ValueError("raid_unreviewed_compiled_change")
        raid = new[added]
        if FLAG.encode() + b"\0" not in payload(after, raid, "bin"):
            raise ValueError("raid_compiled_gate_missing")
        streams.append(
            dict(
                stream=stem,
                added_assets=[added],
                changed_assets=sorted(changed),
                unchanged_assets=len(old) - len(changed),
                all_game_object_assets_preserved=True,
                original_micro_managers_preserved=True,
                compiled_flag_present=True,
            )
        )
    stream_names = {
        stem + "." + ext for stem in ("mod", "mod_m", "mod_l") for ext in ("manifest", "bin", "imp", "relo")
    }
    for path in (baseline / "package").rglob("*"):
        if path.is_file() and path.name.lower() not in stream_names:
            if digest(path) != digest(output / "package" / path.relative_to(baseline / "package")):
                raise ValueError("raid_unrelated_archive_file_changed")
    return dict(
        kind="compiled_strategic_raid_derivation_v1",
        base_package_sha256=BASE_PACKAGE,
        package_sha256=digest(output / "TFMacroProbe.big"),
        streams=streams,
        stock_task_canonical_sha256=report["raid_stock_canonical_sha256"],
        native_team_template_and_micro_preserved=True,
        native_task_readiness_preserved=True,
        commander_owns_strategic_dispatch_timing=True,
        preferred_enemy_target_selection=True,
        field_verified=False,
        product_capability_granted=False,
    )


def stage(baseline, output):
    if digest(baseline / "TFMacroProbe.big") != BASE_PACKAGE:
        raise ValueError("raid_exact_baseline_required")
    output = safe_output(output)
    old = json.loads((baseline / "build-report.json").read_text(encoding="utf-8-sig"))
    stock = E.parse(STOCK_PATH).getroot().find(q("AIStrategicStateDefinition") + "[@id='" + STOCK_ID + "']")
    xml, report = generate((baseline / "MacroProbe.xml").read_bytes(), old, stock)
    output.mkdir(parents=True)
    (output / "MacroProbe.xml").write_bytes(xml)
    report["macro_xml_sha256"] = digest(output / "MacroProbe.xml")
    # The baseline's retained pre-append archive contains the original stock
    # assets. Recompile the complete custom declaration against that archive.
    compile_probe(output, report, reconstruct_base(baseline, output, copy.deepcopy(old)))
    (output / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review = audit(baseline, output, report)
    (output / "strategic-raid-audit.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    return review


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.baseline, args.output)))
