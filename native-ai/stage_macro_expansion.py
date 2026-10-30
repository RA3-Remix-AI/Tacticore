"""Append seven unqualified C-line consumers to the unchanged role baseline.

Writes only a fresh staging directory. Optional compilation is offline and
append-only; no game is started, no package installed, no capability granted.
"""
import argparse
import copy
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as E

from stage_commanders import SDK, q, safe_output, manifest_rows, sage_hash
from stage_macro_group_roles import generate_group_roles
from stage_macro_probe import compile_probe, digest
from macro_expansion_contract import (COMMANDER, LEGACY_FLAG_ORDER,
    LEGACY_ACTION_ORDER, EXPANSION_ACTION_ORDER, candidate_definitions,
    canonical_digest, transport_contract)


def _exists(heuristic, template, present):
    condition = E.SubElement(heuristic, q('ObjectOfTypeExistsHeuristic'), PassIfExists=str(present).lower())
    filt = E.SubElement(condition, q('ObjectFilter'), Relationship='SAME_PLAYER', Rule='ANY')
    E.SubElement(filt, q('IncludeThing')).text = template


def static_source_audit():
    """Pin SDK templates/command permissions without inferring live readiness."""
    rows = []
    specs = [('Structures', name) for name in ('SovietPowerPlant', 'SovietBarracks',
        'SovietWarFactory', 'SovietRefinery', 'SovietPowerPlantAdvanced', 'SovietTechStructure')]
    specs += [('Units', 'SovietAntiInfantryVehicle'), ('Units', 'SovietAntiAirShip')]
    for folder, name in specs:
        path = SDK / 'SAGEXML/Soviet' / folder / (name + '.xml')
        nodes = E.parse(path).getroot().findall(q('GameObject'))
        for node in nodes:
            costs = [int(x.get('Amount')) for x in node.findall('.//' + q('BuildCost'))]
            rows.append(dict(template=node.get('id'), source=str(path), source_sha256=digest(path),
                inherit_from=node.get('inheritFrom'), production_queue_type=node.get('ProductionQueueType'),
                energy_production_static=node.get('EnergyProduction'),
                direct_required_objects=[x.text for x in node.findall('./' + q('GameDependency') + '/' + q('RequiredObject'))],
                static_build_cost=costs[0] if len(costs) == 1 else None,
                operational_status_verified=False, actual_payment_verified=False))
    commands = SDK / 'SAGEXML/GlobalData/LogicCommandSet.xml'
    factory = E.parse(commands).getroot().find(q('LogicCommandSet') + "[@id='SovietWarFactoryCommandSet']")
    actual_commands = [n.text for n in factory.findall(q('Cmd'))]
    required = ['Command_ConstructSovietAntiInfantryVehicle', 'Command_ConstructSovietAntiAirShip_Ground']
    if any(name not in actual_commands for name in required):
        raise ValueError('macro_expansion_native_vehicle_command_missing')
    return dict(kind='sdk_static_candidate_audit', templates=rows,
        war_factory_commands=dict(source=str(commands), source_sha256=digest(commands), confirmed=required),
        field_verified=False, capability_granted=False,
        limits=['Static dependencies are not live completion, power or unlock evidence.',
            'Inherited fields, game overrides and actual payment require separate qualification.'])


def generate_expansion(commander, slot, baselines, map_raw):
    if commander != COMMANDER or type(slot) is not int or slot != 3:
        raise ValueError('macro_expansion_fixed_profile_required')
    xml, report = generate_group_roles(commander, slot, baselines, map_raw)
    if list(report['flags'].values()) != list(LEGACY_FLAG_ORDER):
        raise ValueError('macro_expansion_legacy_flag_changed')
    by_flag = {r['flag']: r['action'] for r in report['consumers']}
    if [by_flag[f] for f in LEGACY_FLAG_ORDER] != list(LEGACY_ACTION_ORDER):
        raise ValueError('macro_expansion_legacy_action_changed')
    legacy = copy.deepcopy(report['consumers'])
    root = E.fromstring(xml)
    personality = root.find(q('AIPersonalityDefinition'))
    prefix = report['personality'].removesuffix('_Soviet')
    keys = {(int(a['type_id'], 0), int(a['instance_id'], 0)) for a in report['assets']}
    keys.update((a['type_id'], a['instance_id']) for a in baselines)
    candidates = []
    for definition in candidate_definitions():
        action = definition['action']; state_name = prefix + '_' + definition['suffix']
        key = sage_hash('AIBuildStateDefinition'), sage_hash(state_name.lower())
        if key in keys:
            raise ValueError('macro_expansion_asset_collision')
        keys.add(key)
        flag = '/' + prefix + '_' + action
        if action in report['flags'] or flag in report['flags'].values():
            raise ValueError('macro_expansion_flag_collision')
        report['flags'][action] = flag
        asset = dict(name='AIBuildStateDefinition:' + state_name, type_id=hex(key[0]), instance_id=hex(key[1]))
        report['assets'].append(asset)
        node = E.Element(q('AIBuildStateDefinition'), id=state_name)
        h = E.SubElement(node, q('Heuristic'))
        E.SubElement(h, q('ScriptedFlagHeuristic'), FlagName=flag)
        E.SubElement(h, q('OpeningMoveHeuristic'), Complete='true')
        E.SubElement(h, q('ConstantHeuristic'), Weight='100')
        if definition['only_if_target_absent']:
            _exists(h, definition['template'], False)
        for dependency in definition['required_own_templates']:
            _exists(h, dependency, True)
        if definition['domain'] == 'construction':
            E.SubElement(h, q('IsBuildingHeuristic'), KindOf='STRUCTURE', PassIfBuilding='false')
        if action == 'buildrefinery':
            E.SubElement(h, q('OpenNodeHeuristic'), Exists='true')
        E.SubElement(node, q('BuildEntry'), Build=definition['template'], Heuristic=definition['heuristic'], Score='100')
        root.insert(list(root).index(personality), node)
        E.SubElement(personality, q('BuildState'), id=state_name, State=state_name)
        candidate = dict(definition, flag=flag, state=asset['name'])
        report['consumers'].append(candidate); candidates.append(candidate)
    report.update(variant='expanded_macro_policy_v2', transport_protocol_version=2,
        expansion_schema_version=1, flag_count=20,
        legacy_flag_order=list(LEGACY_FLAG_ORDER), legacy_action_order=list(LEGACY_ACTION_ORDER),
        expansion_action_order=list(EXPANSION_ACTION_ORDER),
        legacy_consumer_semantics_sha256=canonical_digest(legacy),
        legacy_consumer_definitions=legacy, expansion_candidates=candidates,
        static_candidate_audit=static_source_audit(),
        expansion_field_verified=False, expansion_product_capability_granted=False,
        scope='20-gate append-only macro expansion candidate; fixed Soviet P3 TemplePrime; no capability grant')
    contract = transport_contract(report)
    report['transport_exclusive_masks'] = contract['exclusive_masks']
    report['transport_known_mask'] = contract['known_mask']
    E.indent(root, space='  ')
    return E.tostring(root, encoding='utf-8', xml_declaration=True), report


def audit_compiled_expansion(baseline, candidate, report):
    """Compare actual compiled streams and parse all seven native build entries."""
    from validate_side_imports import read_stream
    baseline = Path(baseline); candidate = Path(candidate)
    original = json.loads((baseline / 'build-report.json').read_text(encoding='utf8'))
    if (original.get('variant') != 'expanded_macro_policy_v1'
            or original.get('compiled') is not True
            or original.get('group_roles_candidate_revision') != 2
            or original['consumers'] != report['legacy_consumer_definitions']
            or digest(baseline / 'TFMacroProbe.big') != original['big_sha256']):
        raise ValueError('compiled_group_role_baseline_required')
    if report.get('compiled') is not True or digest(candidate / 'TFMacroProbe.big') != report.get('big_sha256'):
        raise ValueError('compiled_expansion_package_required')
    transport_contract(report)
    enum_path = SDK / 'Schemas/xsd/SkirmishAI/AssetTypeAIBuilderDefinition.xsd'
    ns = '{http://www.w3.org/2001/XMLSchema}'
    enumeration = E.parse(enum_path).getroot().find(ns + "simpleType[@name='AIBuildHeuristics']")
    heuristics = [n.get('value') for n in enumeration.iter(ns + 'enumeration')]
    added = {c['state'] for c in report['expansion_candidates']}
    personality = 'AIPersonalityDefinition:' + report['personality']
    streams = []; pins = {}
    for stem in ('mod', 'mod_M', 'mod_L'):
        a = read_stream(baseline / 'package/data' / (stem + '.manifest'))
        b = read_stream(candidate / 'package/data' / (stem + '.manifest'))
        am = {r['name']: r for r in a['rows']}; bm = {r['name']: r for r in b['rows']}
        if set(am) - set(bm) or set(bm) - set(am) != added:
            raise ValueError('macro_expansion_unreviewed_asset_set')
        changed = []
        for name, row in am.items():
            other = bm[name]
            same = all(row[k] == other[k] for k in ('refs', 'type_id', 'instance_id', 'type_hash', 'instance_hash', 'flags'))
            for ext, offset, size in (('bin', 'binary_offset', 'binary_size'), ('imp', 'imp_offset', 'imp_size'), ('relo', 'relo_offset', 'relo_size')):
                same = same and a['files'][ext][row[offset]:row[offset] + row[size]] == b['files'][ext][other[offset]:other[offset] + other[size]]
            if not same:
                changed.append(name)
        if changed != [personality]:
            raise ValueError('macro_expansion_legacy_compiled_asset_changed')
        entries = []
        for definition in report['expansion_candidates']:
            row = bm[definition['state']]
            raw = b['files']['bin'][row['binary_offset']:row['binary_offset'] + row['binary_size']]
            entries.append(parse_compiled_entry(raw, definition, heuristics))
        streams.append(dict(stream=stem, new_native_build_entries=entries,
            unchanged_original_and_legacy_assets=len(am) - 1, changed_common_assets=changed))
        for directory in (baseline, candidate):
            for ext in ('manifest', 'bin', 'imp', 'relo'):
                path = directory / 'package/data' / (stem + '.' + ext)
                pins[str(path.resolve())] = digest(path)
    return dict(kind='compiled_append_only_macro_expansion_audit',
        baseline_package_sha256=original['big_sha256'], package_sha256=report['big_sha256'],
        streams=streams, evidence=pins, qualified_consumer_semantics_preserved=True,
        original_micro_assets_preserved=True, field_verified=False, capability_granted=False)


def parse_compiled_entry(raw, definition, heuristics):
    """Inspect the actual single-entry native layout, never infer from XML."""
    if len(raw) < 20:
        raise ValueError('macro_expansion_compiled_entry_truncated')
    count, start = struct.unpack_from('<II', raw, 0xc)
    if count != 1 or start % 4 or start < 20 or start + 56 > len(raw):
        raise ValueError('macro_expansion_compiled_entry_layout')
    template, upgrade, heuristic = struct.unpack_from('<III', raw, start)
    score = struct.unpack_from('<f', raw, start + 0x30)[0]
    expected = sage_hash(definition['template'].lower())
    if (template != expected or upgrade != 0 or heuristic != heuristics.index(definition['heuristic'])
            or score != 100.0 or definition['flag'].encode('utf8') + b'\0' not in raw):
        raise ValueError('macro_expansion_compiled_entry_mismatch')
    return dict(action=definition['action'], template=definition['template'],
        template_hash=hex(template), heuristic=definition['heuristic'], score=score,
        flag_serialized_in_same_asset=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--decoded-map', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--baseline', type=Path, action='append', default=[])
    p.add_argument('--compile-base-big', type=Path)
    p.add_argument('--compiled-role-baseline', type=Path)
    a = p.parse_args()
    if bool(a.compile_base_big) != bool(a.compiled_role_baseline):
        p.error('--compile-base-big and --compiled-role-baseline must be supplied together')
    out = safe_output(a.output)
    paths = [SDK / 'BuiltMods/sagexml' / (n + '.manifest') for n in ('static', 'global', 'audio')] + a.baseline
    rows = [r for path in paths for r in manifest_rows(path)]
    xml, report = generate_expansion(COMMANDER, 3, rows, a.decoded_map.read_bytes())
    report.update(compiled=False, output=str(out), source_sha256=digest(__file__),
        contract_source_sha256=digest(Path(__file__).with_name('macro_expansion_contract.py')),
        regional_map_source=str(a.decoded_map.resolve()),
        collision_baselines=[dict(path=str(path), sha256=digest(path)) for path in paths])
    out.mkdir(parents=True); (out / 'MacroProbe.xml').write_bytes(xml)
    report['macro_xml_sha256'] = digest(out / 'MacroProbe.xml')
    (out / 'generation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    if a.compile_base_big:
        compile_probe(out, report, a.compile_base_big)
        audit = audit_compiled_expansion(a.compiled_role_baseline, out, report)
        (out / 'compiled-expansion-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf8')
        report['compiled_expansion_audit_sha256'] = digest(out / 'compiled-expansion-audit.json')
    (out / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(output=str(out), compiled=report['compiled'], flags=len(report['flags']),
        transport_protocol_version=2, expansion_schema_version=1,
        field_verified=False, product_capability_granted=False)))


if __name__ == '__main__':
    main()
