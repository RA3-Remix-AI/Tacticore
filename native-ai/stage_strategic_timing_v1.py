"""Derive strategic timing and a native general-force economic raid.

The original autonomous states, GameObjects and micro managers remain intact.
The external expansion preference owns timing. Recruitment and execution come
from complete stock native tactics and never from model unit parameters.
"""
import argparse
import copy
import json
import xml.etree.ElementTree as E
from pathlib import Path

from stage_commanders import SDK, q, safe_output
from stage_macro_probe import compile_probe, digest
from stage_native_enemy_attack_v1 import PREFIX, payload, reconstruct_base
from stage_strategic_expansion_v1 import canonical_sha, normalized
from validate_side_imports import read_stream

BASE_PACKAGE = '4811342ec70c153ee8b2328797dc321e62b2770b53d5e6270b7f396c59dff29c'
EXPANSION = PREFIX + '_StockExpansionPreference'
RAID = PREFIX + '_RaidEconomy'
STOCK_PATH = SDK / 'SAGEXML/SkirmishAI/States/BalancedStates.xml'
STOCK_ID = 'GrowingAttacks_Land_MEDIUM'


def generate(xml, report, stock):
    root = E.fromstring(xml)
    report = copy.deepcopy(report)
    expansion = root.find(q('AIStrategicStateDefinition') + "[@id='" + EXPANSION + "']")
    heuristic = expansion.find(q('Heuristic'))
    opening = heuristic.find(q('OpeningMoveHeuristic'))
    cooldown = heuristic.find(q('TimeSinceLastExpansionHeuristic'))
    if opening.attrib != {'Complete': 'true'} or cooldown.attrib != {'Time': '240s'}:
        raise ValueError('strategic_expansion_original_timing_required')
    before = copy.deepcopy(expansion)
    heuristic.remove(opening)
    heuristic.remove(cooldown)
    restored = copy.deepcopy(expansion)
    restored_heuristic = restored.find(q('Heuristic'))
    restored_heuristic.insert(1, copy.deepcopy(opening))
    restored_heuristic.insert(2, copy.deepcopy(cooldown))
    if normalized(restored) != normalized(before):
        raise ValueError('strategic_expansion_execution_changed')
    if stock.get('id') != STOCK_ID:
        raise ValueError('strategic_raid_original_medium_task_required')
    raid = root.find(q('AIStrategicStateDefinition') + "[@id='" + RAID + "']")
    old_tactic = raid.find(q('Tactic'))
    tactic = copy.deepcopy(stock.find(q('Tactic')))
    tactic.set('EndIfStateTurnsOff', 'true')
    raid.remove(old_tactic)
    raid.append(tactic)
    check = copy.deepcopy(tactic)
    del check.attrib['EndIfStateTurnsOff']
    if normalized(check) != normalized(stock.find(q('Tactic'))):
        raise ValueError('strategic_raid_native_tactic_changed')
    for row in report['consumers']:
        if row['action'] == 'expand':
            row.update(removes_native_conditions=True, strategic_timing_owner='agent',
                       removed_strategic_conditions=['OpeningMoveHeuristic', 'TimeSinceLastExpansionHeuristic'],
                       native_target_and_tactic_preserved=True)
        if row['action'] == 'raideconomy':
            row.update(stock_state=STOCK_ID, native_tactic_source=str(STOCK_PATH),
                       native_tactic_canonical_sha256=canonical_sha(stock.find(q('Tactic'))),
                       original_specialized_tactic='SickleHarrassment_MEDIUM',
                       native_general_combat_recruitment=True)
    report.update(variant='strategic_timing_and_native_general_raid_v1',
                  strategic_timing_source_sha256=digest(__file__),
                  native_general_raid_source_sha256=digest(STOCK_PATH),
                  compiled=False, deployed=False, field_verified=False,
                  product_capability_granted=False, expansion_field_verified=False)
    E.indent(root, space='  ')
    return E.tostring(root, encoding='utf-8', xml_declaration=True), report


def audit(baseline, output, report):
    expected_changes = {'AIStrategicStateDefinition:' + EXPANSION,
                        'AIStrategicStateDefinition:' + RAID}
    streams = []
    for stem in ('mod', 'mod_M', 'mod_L'):
        before = read_stream(baseline / 'package/data' / (stem + '.manifest'))
        after = read_stream(output / 'package/data' / (stem + '.manifest'))
        old = {row['name']: row for row in before['rows']}
        new = {row['name']: row for row in after['rows']}
        if set(old) != set(new):
            raise ValueError('strategic_timing_asset_set_changed')
        changed = []
        for name, row in old.items():
            other = new[name]
            same = all(row[key] == other[key] for key in
                       ('refs', 'type_id', 'instance_id', 'type_hash', 'instance_hash', 'flags'))
            if not same or any(payload(before, row, ext) != payload(after, other, ext)
                               for ext in ('bin', 'imp', 'relo')):
                changed.append(name)
        if set(changed) != expected_changes:
            raise ValueError('strategic_timing_unreviewed_compiled_change')
        streams.append(dict(stream=stem, changed_assets=sorted(changed),
                            all_game_object_assets_preserved=True,
                            original_autonomous_states_preserved=True,
                            original_micro_managers_preserved=True))
    return dict(kind='compiled_strategic_timing_derivation_v1',
                base_package_sha256=BASE_PACKAGE, package_sha256=digest(output / 'TFMacroProbe.big'),
                streams=streams, expansion_target_and_tactic_preserved=True,
                raid_native_general_tactic_preserved=True,
                raid_tactic_source_sha256=report['native_general_raid_source_sha256'],
                raid_tactic_canonical_sha256=next(row['native_tactic_canonical_sha256']
                    for row in report['consumers'] if row['action'] == 'raideconomy'),
                field_verified=False, product_capability_granted=False)


def stage(baseline, output):
    if digest(baseline / 'TFMacroProbe.big') != BASE_PACKAGE:
        raise ValueError('strategic_timing_exact_baseline_required')
    output = safe_output(output)
    stock = E.parse(STOCK_PATH).getroot().find(q('AIStrategicStateDefinition') + "[@id='" + STOCK_ID + "']")
    xml, report = generate((baseline / 'MacroProbe.xml').read_bytes(),
                           json.loads((baseline / 'build-report.json').read_text()), stock)
    output.mkdir(parents=True)
    (output / 'MacroProbe.xml').write_bytes(xml)
    report['macro_xml_sha256'] = digest(output / 'MacroProbe.xml')
    compile_probe(output, report, reconstruct_base(baseline, output, copy.deepcopy(report)))
    (output / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result = audit(baseline, output, report)
    (output / 'strategic-timing-audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.baseline, args.output)))
