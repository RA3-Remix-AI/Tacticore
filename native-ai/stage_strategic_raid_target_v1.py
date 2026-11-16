"""Reuse the qualified native attack executor with an economic target preference."""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as E

from stage_commanders import q, safe_output
from stage_macro_probe import compile_probe, digest
from stage_native_enemy_attack_v1 import PREFIX, payload, reconstruct_base
from stage_strategic_expansion_v1 import canonical_sha, normalized
from validate_side_imports import read_stream

BASE_PACKAGE = '0c1cf8c501aef75b60d5e6b6419c70c659dd8042474eae2df09f57861a5d75e8'
RAID = PREFIX + '_RaidEconomy'
ATTACK = PREFIX + '_DeployAttack'


def generate(xml, report):
    root = E.fromstring(xml)
    report = copy.deepcopy(report)
    raid = root.find(q('AIStrategicStateDefinition') + "[@id='" + RAID + "']")
    attack = root.find(q('AIStrategicStateDefinition') + "[@id='" + ATTACK + "']")
    guard = raid.find(q('Heuristic'))
    specialized = guard.find(q('ObjectOfTypeExistsHeuristic'))
    expected = specialized.find(q('ObjectFilter'))
    if (specialized.attrib != {'PassIfExists': 'true'}
            or expected.attrib != {'Relationship': 'SAME_PLAYER', 'Rule': 'ANY'}
            or [item.text for item in expected] != ['SovietAntiInfantryVehicle']):
        raise ValueError('raid_previous_specialized_guard_required')
    guard.remove(specialized)
    target = raid.find(q('TargetHeuristic'))
    if target.attrib != {'TargetHeuristic': 'SafestToGroundHarvesterHeuristic', 'Priority': '10'}:
        raise ValueError('raid_native_economic_target_required')
    tactic = attack.find(q('Tactic'))
    if tactic.get('EndIfStateTurnsOff') != 'true':
        raise ValueError('raid_bounded_attack_executor_required')
    raid.remove(raid.find(q('Tactic')))
    raid.append(copy.deepcopy(tactic))
    if normalized(raid.find(q('Tactic'))) != normalized(tactic):
        raise ValueError('raid_existing_executor_changed')
    tactic_sha = canonical_sha(tactic)
    for row in report['consumers']:
        if row['action'] == 'raideconomy':
            row.update(native_executor_source=ATTACK,
                       qualified_attack_tactic_sha256=tactic_sha,
                       native_general_combat_recruitment=True,
                       specialized_unit_prerequisite=False)
            for key in ('stock_state', 'native_tactic_source', 'native_tactic_canonical_sha256'):
                row.pop(key, None)
    report.update(variant='native_raid_target_preference_v1',
                  raid_target_source_sha256=digest(__file__),
                  compiled=False, deployed=False, field_verified=False,
                  product_capability_granted=False)
    E.indent(root, space='  ')
    return E.tostring(root, encoding='utf-8', xml_declaration=True), report, tactic_sha


def audit(baseline, output, tactic_sha):
    streams = []
    for stem in ('mod', 'mod_M', 'mod_L'):
        before = read_stream(baseline / 'package/data' / (stem + '.manifest'))
        after = read_stream(output / 'package/data' / (stem + '.manifest'))
        old = {row['name']: row for row in before['rows']}
        new = {row['name']: row for row in after['rows']}
        if set(old) != set(new):
            raise ValueError('raid_target_asset_set_changed')
        changed = []
        for name, row in old.items():
            other = new[name]
            same = all(row[key] == other[key] for key in
                       ('refs', 'type_id', 'instance_id', 'type_hash', 'instance_hash', 'flags'))
            if not same or any(payload(before, row, ext) != payload(after, other, ext)
                               for ext in ('bin', 'imp', 'relo')):
                changed.append(name)
        if changed != ['AIStrategicStateDefinition:' + RAID]:
            raise ValueError('raid_target_unreviewed_compiled_change')
        streams.append(dict(stream=stem, changed_assets=changed,
                            all_game_object_assets_preserved=True,
                            original_autonomous_states_preserved=True,
                            original_micro_managers_preserved=True))
    stream_names = {stem + '.' + ext for stem in ('mod', 'mod_m', 'mod_l')
                    for ext in ('manifest', 'bin', 'imp', 'relo')}
    for path in (baseline / 'package').rglob('*'):
        if path.is_file() and path.name.lower() not in stream_names:
            if digest(path) != digest(output / 'package' / path.relative_to(baseline / 'package')):
                raise ValueError('raid_target_unrelated_archive_file_changed')
    return dict(kind='compiled_native_raid_target_derivation_v1',
                base_package_sha256=BASE_PACKAGE, package_sha256=digest(output / 'TFMacroProbe.big'),
                streams=streams, qualified_attack_executor=ATTACK,
                qualified_attack_tactic_sha256=tactic_sha,
                native_attack_executor_preserved=True,
                native_economic_target_preserved=True,
                specialized_unit_prerequisite_removed=True,
                field_verified=False, product_capability_granted=False)


def stage(baseline, output):
    if digest(baseline / 'TFMacroProbe.big') != BASE_PACKAGE:
        raise ValueError('raid_target_exact_baseline_required')
    output = safe_output(output)
    xml, report, tactic_sha = generate((baseline / 'MacroProbe.xml').read_bytes(),
        json.loads((baseline / 'build-report.json').read_text()))
    output.mkdir(parents=True)
    (output / 'MacroProbe.xml').write_bytes(xml)
    report['macro_xml_sha256'] = digest(output / 'MacroProbe.xml')
    compile_probe(output, report, reconstruct_base(baseline, output, copy.deepcopy(report)))
    (output / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result = audit(baseline, output, tactic_sha)
    (output / 'raid-target-audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.baseline, args.output)))
