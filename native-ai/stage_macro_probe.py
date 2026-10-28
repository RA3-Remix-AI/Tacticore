"""Stage/compile isolated native AI macro states; never deploy or start a game.

The probe has one explicitly named commander/slot. Its flags are global within
a match, so duplicate copies of this personality MUST be refused by a future
runtime adapter. Compilation is not dynamic capability qualification.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import struct
import uuid
import xml.etree.ElementTree as E

from stage_commanders import ROOT, SDK, q, safe_output, manifest_rows, sage_hash

MOD = 'TFMacroProbe'
SOURCE_PATH = SDK / 'SAGEXML/SkirmishAI/States/SovietBaseStates.xml'
BASE_PERSONALITY = SDK / 'SAGEXML/SkirmishAI/Personalities/SovietBalanced.xml'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate(commander_id, slot, baselines):
    ident = str(uuid.UUID(commander_id))
    if type(slot) is not int or not 1 <= slot <= 6:
        raise ValueError('Explicit skirmish slot 1..6 required')
    prefix = '5TFMacro_' + uuid.UUID(ident).hex + '_P' + str(slot)
    personality = prefix + '_Soviet'
    specs = [('AIBuildStateDefinition', prefix + '_BuildAirfield'),
             ('AIStrategicStateDefinition', prefix + '_Scout'),
             ('AIPersonalityDefinition', personality)]
    occupied = {(r['type_id'], r['instance_id']): r['name'] for r in baselines}
    assets = []
    for kind, name in specs:
        key = sage_hash(kind), sage_hash(name.lower())
        if key in occupied:
            raise ValueError('Native asset collision: ' + name)
        occupied[key] = kind + ':' + name
        assets.append(dict(name=kind + ':' + name, type_id=hex(key[0]), instance_id=hex(key[1])))
    flags = dict(build_airfield='/' + prefix + '_build_airfield', scout='/' + prefix + '_scout')
    feedback = {phase: dict(key=prefix+'_Scout_'+phase, text_key='GUI:'+prefix+'_Scout_'+phase,
        text='Macro scout: '+phase.replace('_',' ')) for phase in
        ['team_gather_begin', 'execution_begin', 'execution_canceled', 'execution_complete']}
    root = E.Element(q('AssetDeclaration'))
    E.SubElement(root, q('Tags'))
    inc = E.SubElement(root, q('Includes'))
    E.SubElement(inc, q('Include'), type='instance', source='DATA:SkirmishAI/Personalities/SovietBalanced.xml')

    build = E.SubElement(root, q('AIBuildStateDefinition'), id=specs[0][1])
    heur = E.SubElement(build, q('Heuristic'))
    E.SubElement(heur, q('ScriptedFlagHeuristic'), FlagName=flags['build_airfield'])
    E.SubElement(heur, q('OpeningMoveHeuristic'), Complete='true')
    # Stop offering this build when owned or another structure is being built.
    # The native builder must still check placement, prerequisite and real funds.
    absent = E.SubElement(heur, q('ObjectOfTypeExistsHeuristic'), PassIfExists='false')
    filt = E.SubElement(absent, q('ObjectFilter'), Relationship='SAME_PLAYER', Rule='ANY')
    E.SubElement(filt, q('IncludeThing')).text = 'SovietAirfield'
    E.SubElement(heur, q('IsBuildingHeuristic'), KindOf='STRUCTURE', PassIfBuilding='false')
    E.SubElement(build, q('BuildEntry'), Build='SovietAirfield', Heuristic='CONSTANT', Score='100')

    source_tree = E.parse(SOURCE_PATH).getroot()
    original = source_tree.find(q('AIStrategicStateDefinition') + "[@id='SovietScout']")
    if original is None:
        raise ValueError('Stock scout state missing')
    scout = copy.deepcopy(original)
    scout.set('id', specs[1][1])
    scout.set('MaxTargets', '1')
    scout.set('MaxRunningCopies', '1')
    for attribute, phase in [('TeamGatherBeginFeedbackKey', 'team_gather_begin'),
            ('ExecutionBeginFeedbackKey', 'execution_begin'),
            ('ExecutionCanceledFeedbackKey', 'execution_canceled'),
            ('ExecutionCompleteFeedbackKey', 'execution_complete')]:
        scout.set(attribute, feedback[phase]['key'])
    heur = scout.find(q('Heuristic'))
    if len(heur) != 1 or heur[0].tag != q('TimerHeuristic'):
        raise ValueError('Unexpected stock scout gate; review source before adapting')
    heur.remove(heur[0])
    E.SubElement(heur, q('ScriptedFlagHeuristic'), FlagName=flags['scout'])
    tactic = scout.find(q('Tactic'))
    tactic.set('EndIfStateTurnsOff', 'true')
    team = tactic.find(q('TeamTemplate'))
    if team.get('MicroManager') != 'ScoutMicroManager' or team.get('MaxUnits') != '1':
        raise ValueError('Stock native scouting behavior changed')
    root.append(scout)

    node = E.SubElement(root, q('AIPersonalityDefinition'), id=personality,
        PersonalityType=personality, inheritFrom='1SovietBalanced', SkirmishPersonality='true',
        PersonalityUIName='Personality:TFMacroProbe')
    E.SubElement(node, q('StrategicState'), id=specs[1][1], State=specs[1][1])
    E.SubElement(node, q('BuildState'), id=specs[0][1], State=specs[0][1])
    for entry in feedback.values():
        E.SubElement(node, q('FeedbackEntry'), FeedbackKey=entry['key'], Text=entry['text_key'],
            FeedbackTo='ALLIES ENEMIES NEUTRAL', Timeout='1s')
    E.indent(root, space='  ')
    xml = E.tostring(root, encoding='utf-8', xml_declaration=True)
    report = dict(schema_version=1, kind='isolated_native_macro_probe', commander_id=ident,
        player_slot=slot, side='Soviet', personality=personality, flags=flags, assets=assets,
        native_feedback=feedback,
        scope='explicit empty script namespace; match-global; one owner only',
        runtime_requires=['exact session/PID/rawFILETIME/mod/commander/slot binding',
            'unique selected personality owner; refuse duplicates',
            'normal game-thread flag setter and independent readback',
            'bounded expiry/watchdog; clear flags on stop before acknowledging cleanup',
            'native state/queue attribution distinct from autonomous stock behavior',
            'real payment/prerequisite/placement and legal visibility checks'],
        stock_scout_source=str(SOURCE_PATH), stock_scout_sha256=digest(SOURCE_PATH),
        stock_personality_source=str(BASE_PERSONALITY), stock_personality_sha256=digest(BASE_PERSONALITY),
        stock_micro_manager_preserved=True, original_assets_replaced=0,
        field_verified=False, capability_granted=False, deployed=False)
    return xml, report


def compile_probe(output, report, base_big):
    # Reuse the append-only merger: it independently compares every original
    # asset payload/import/relo/ref with the baseline, including micro managers.
    from build_commander_package import merge_stream, big_entries, unpack_refpack, read_stream, csf, write_csf
    base_sha = digest(base_big)
    source = SDK / 'Mods' / MOD / 'data'
    source.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output / 'MacroProbe.xml', source / 'MacroProbe.xml')
    root = E.Element(q('AssetDeclaration')); E.SubElement(root, q('Tags'))
    inc = E.SubElement(root, q('Includes'))
    for name in ['static', 'global', 'audio']:
        E.SubElement(inc, q('Include'), type='reference', source='DATA:' + name + '.xml')
    E.SubElement(inc, q('Include'), type='all', source='DATA:' + MOD + '/data/MacroProbe.xml')
    E.ElementTree(root).write(source / 'Mod.xml', encoding='utf-8', xml_declaration=True)
    shutil.copy2(source / 'Mod.xml', output / 'Mod.xml')
    report['compiler_source_sha256'] = digest(source / 'Mod.xml')
    with (output / 'sdk-build.log').open('w', encoding='utf-8') as log:
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            str(SDK.parent / 'Build-Mod.ps1'), '-ModName', MOD, '-NoDeploy'],
            stdout=log, stderr=subprocess.STDOUT, check=True)
    compiled = SDK / 'BuiltMods/mods' / MOD / 'data'
    package = output / 'package'
    package.mkdir()
    baseline_entries = {}
    for name, raw in big_entries(base_big):
        name = name.replace('\\', '/'); target = (package / name).resolve()
        if not target.is_relative_to(package.resolve()) or name.lower() in baseline_entries:
            raise ValueError('Unsafe/duplicate archive entry')
        target.parent.mkdir(parents=True, exist_ok=True)
        data = unpack_refpack(raw); target.write_bytes(data)
        baseline_entries[name.lower()] = hashlib.sha256(data).hexdigest()
    if any('additionalmaps' in Path(name).parts for name in baseline_entries):
        raise ValueError('Baseline must not contain AdditionalMaps')
    expected = {a['name'] for a in report['assets']}
    report['streams'] = []
    for stem in ['mod', 'mod_M', 'mod_L']:
        target = package / 'data' / (stem + '.manifest')
        before = output / 'baseline' / 'data' / target.name
        before.parent.mkdir(parents=True, exist_ok=True)
        for ext in ['manifest', 'bin', 'imp', 'relo']:
            shutil.copy2(target.with_suffix('.' + ext), before.with_suffix('.' + ext))
        result = merge_stream(before, compiled / target.name, target, expected)
        merged=read_stream(target)
        rows = {r['name']: r for r in merged['rows']}
        for asset in report['assets']:
            row = rows[asset['name']]
            if (row['type_id'], row['instance_id']) != (int(asset['type_id'], 16), int(asset['instance_id'], 16)):
                raise ValueError('Predicted native IDs do not match compiler')
        # Both flag names must survive native serialization in each quality.
        blob = target.with_suffix('.bin').read_bytes()
        if not all(name.encode() + b'\0' in blob for name in report['flags'].values()):
            raise ValueError('Compiled scripted flags missing')
        # The native state definition holds optional StringHash pointers at
        # +20/+24/+28/+2c. Check actual serialized pointees, not XML presence.
        scout_name=next(a['name'] for a in report['assets'] if a['name'].startswith('AIStrategicStateDefinition:'))
        row=rows[scout_name]
        raw=merged['files']['bin'][row['binary_offset']:row['binary_offset']+row['binary_size']]
        feedback_values={}
        for offset,(phase,entry) in zip([0x20,0x24,0x28,0x2c],report['native_feedback'].items()):
            pointer=struct.unpack_from('<I',raw,offset)[0]
            if pointer%4 or not 0<pointer<=len(raw)-4:
                raise ValueError('Compiled feedback pointer invalid')
            value=struct.unpack_from('<I',raw,pointer)[0]
            if value!=sage_hash(entry['key']):
                raise ValueError('Compiled feedback hash mismatch')
            feedback_values[phase]=dict(key=entry['key'],hash=hex(value),pointer_offset=hex(offset),value_offset=hex(pointer))
        report['streams'].append(dict(stem=stem, compiled_flags_present=True, native_feedback=feedback_values, **result))
    strings_path = package / 'data/gamestrings.csf'
    original = csf(strings_path.read_bytes()); localized = dict(original)
    key = 'personality:tfmacroprobe'
    if key in localized:
        raise ValueError('Probe localization collision')
    localized[key] = 'MACRO PROBE P' + str(report['player_slot'])
    for entry in report['native_feedback'].values():
        key=entry['text_key'].lower()
        if key in localized:
            raise ValueError('Probe feedback localization collision')
        localized[key]=entry['text']
    write_csf(localized, strings_path)
    checked = csf(strings_path.read_bytes())
    if any(checked.get(k) != v for k, v in original.items()):
        raise ValueError('Original localization changed')
    allowed = {'data/gamestrings.csf'} | {'data/' + s.lower() + '.' + e
        for s in ['mod', 'mod_M', 'mod_L'] for e in ['manifest', 'bin', 'imp', 'relo']}
    preserved = 0
    for name, old_sha in baseline_entries.items():
        if name not in allowed:
            if digest(package / name) != old_sha:
                raise ValueError('Unrelated base entry changed')
            preserved += 1
    big = output / 'TFMacroProbe.big'
    with (output / 'makebig.log').open('w', encoding='utf-8') as log:
        subprocess.run([str(SDK / 'Tools/MakeBig.exe'), '-f', str(package), '-x:*.asset', '-o:' + str(big)],
            stdout=log, stderr=subprocess.STDOUT, check=True)
    archive = {n.replace('\\', '/').lower(): hashlib.sha256(unpack_refpack(b)).hexdigest() for n, b in big_entries(big)}
    for path in package.rglob('*'):
        if path.is_file() and archive.get(path.relative_to(package).as_posix().lower()) != digest(path):
            raise ValueError('Archive roundtrip mismatch')
    if digest(base_big) != base_sha:
        raise ValueError('Baseline archive changed')
    (output / 'TFMacroProbe_1.0.skudef').write_text('mod-game 1.12\nadd-big TFMacroProbe.big\n', encoding='ascii')
    report.update(compiled=True, big_sha256=digest(big), baseline_big=str(base_big.resolve()),
        baseline_big_sha256=base_sha, unchanged_other_base_entries=preserved,
        all_original_localization_preserved=True, big_roundtrip_verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commander-id', required=True)
    parser.add_argument('--slot', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, action='append', default=[])
    parser.add_argument('--compile-base-big', type=Path)
    args = parser.parse_args()
    output = safe_output(args.output)
    paths = [SDK / 'BuiltMods/sagexml' / (name + '.manifest') for name in ['static', 'global', 'audio']] + args.baseline
    rows = [row for path in paths for row in manifest_rows(path)]
    xml, report = generate(args.commander_id, args.slot, rows)
    report.update(compiled=False, output=str(output), source_sha256=digest(__file__),
        collision_baselines=[dict(path=str(p), sha256=digest(p)) for p in paths])
    output.mkdir(parents=True)
    (output / 'MacroProbe.xml').write_bytes(xml)
    report['macro_xml_sha256'] = digest(output / 'MacroProbe.xml')
    (output / 'generation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.compile_base_big:
        compile_probe(output, report, args.compile_base_big)
    (output / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output), compiled=report['compiled'], assets=len(report['assets']),
        deployed=False, field_verified=False, capability_granted=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
