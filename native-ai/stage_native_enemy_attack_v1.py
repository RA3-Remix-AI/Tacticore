"""Compile a fresh native-target attack candidate and audit its exact changes."""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as E

from stage_commanders import SDK, q, safe_output, sage_hash
from stage_macro_probe import compile_probe, digest
from validate_side_imports import read_stream

BASE_PACKAGE = '66025609e788ed18f8eb55b1722e6c197a373f387137b69e6b04118d0a5278f0'
BASE_XML = '825c169bf2351df26d1211f60524cfcb189577e41314362864230f6387c5451a'
PREFIX = '5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3'
ATTACK = 'AIStrategicStateDefinition:' + PREFIX + '_DeployAttack'
OLD_TARGET = 'AITargetingHeuristic:' + PREFIX + '_Waypoint_Player_1_Start'
NATIVE_TARGET = 'ClosestGroundStructureHeuristicAllEnemies'
CANDIDATE_TARGET = PREFIX + '_NativeEnemyStructureTarget'


def payload(stream, row, extension):
    offset, size = {'bin': ('binary_offset', 'binary_size'),
                    'imp': ('imp_offset', 'imp_size'),
                    'relo': ('relo_offset', 'relo_size')}[extension]
    return stream['files'][extension][row[offset]:row[offset] + row[size]]


def audit(baseline, candidate):
    streams = []
    old_key = (sage_hash('AITargetingHeuristic'), sage_hash(OLD_TARGET.split(':', 1)[1].lower()))
    new_name='AITargetingHeuristic:'+CANDIDATE_TARGET
    new_key = (sage_hash('AITargetingHeuristic'), sage_hash(CANDIDATE_TARGET.lower()))
    for stem in ('mod', 'mod_M', 'mod_L'):
        before = read_stream(baseline / 'package/data' / (stem + '.manifest'))
        after = read_stream(candidate / 'package/data' / (stem + '.manifest'))
        old = {row['name']: row for row in before['rows']}
        new = {row['name']: row for row in after['rows']}
        if set(old) - set(new) != {OLD_TARGET} or set(new) - set(old) != {new_name}:
            raise ValueError('native_attack_asset_set_changed')
        changed = []
        for name in new:
            if name==new_name:continue
            a, b = old[name], new[name]
            metadata = ('refs', 'type_id', 'instance_id', 'type_hash', 'instance_hash', 'flags')
            same = all(a[key] == b[key] for key in metadata)
            same = same and all(payload(before, a, ext) == payload(after, b, ext)
                                for ext in ('bin', 'imp', 'relo'))
            if not same:
                changed.append(name)
        if changed != [ATTACK]:
            raise ValueError('native_attack_unreviewed_asset_change')
        a, b = old[ATTACK], new[ATTACK]
        expected_refs = [new_key if tuple(ref) == old_key else tuple(ref) for ref in a['refs']]
        if sum(tuple(ref) == old_key for ref in a['refs']) != 1 or list(map(tuple, b['refs'])) != expected_refs:
            raise ValueError('native_attack_target_reference_changed')
        if any(payload(before, a, ext) != payload(after, b, ext) for ext in ('bin', 'imp', 'relo')):
            raise ValueError('native_attack_tactic_payload_changed')
        streams.append(dict(stream=stem, unchanged_assets=len(new) - 2,
                            changed_assets=changed, removed_assets=[OLD_TARGET],
                            added_assets=[new_name],
                            target_reference_before=list(old_key), target_reference_after=list(new_key),
                            tactic_payload_preserved=True, all_game_object_assets_preserved=True))
    preserved_files=0
    stream_names={stem+'.'+ext for stem in ('mod','mod_m','mod_l') for ext in ('manifest','bin','imp','relo')}
    for path in (baseline/'package').rglob('*'):
        if path.is_file() and path.name.lower() not in stream_names:
            relative=path.relative_to(baseline/'package')
            if digest(path)!=digest(candidate/'package'/relative):
                raise ValueError('native_attack_unrelated_archive_file_changed')
            preserved_files+=1
    return dict(kind='compiled_native_enemy_target_change_v1',
                base_package_sha256=digest(baseline / 'TFMacroProbe.big'),
                package_sha256=digest(candidate / 'TFMacroProbe.big'), streams=streams,
                native_target=NATIVE_TARGET, primary_then_secondary_enemy_fallback=True,
                preserved_other_archive_files=preserved_files,
                field_verified=False, product_capability_granted=False)


def audit_stock_target(candidate,game_root=Path('E:/RedRar3')):
    from compiled_stock_expansion_validator_v1 import config_archives, Archive, manifest, stream_assets, file_sha
    name='AITargetingHeuristic:'+NATIVE_TARGET
    streams={stem:read_stream(candidate/'package/data'/(stem+'.manifest')) for stem in ('mod','mod_M','mod_L')}
    paths,_=config_archives(game_root)
    for path in paths:
        archive=Archive(path)
        for entry in archive.index:
            if re.fullmatch(r'data/global(?:_[lm])?(?:\.\d+)?\.manifest',entry) is None:continue
            rows=[row for row in manifest(archive.entry(entry)) if row['name']==name and row['binary_size']]
            if not rows:continue
            assets,_=stream_assets(archive,entry[:-9]);native=assets[name]
            for stream in streams.values():
                row=next(row for row in stream['rows'] if row['name']=='AITargetingHeuristic:'+CANDIDATE_TARGET)
                if (payload(stream,row,'bin')!=native.payload or payload(stream,row,'imp')!=native.imports
                        or payload(stream,row,'relo')!=native.relocations or tuple(row['refs'])!=native.refs):
                    raise ValueError('native_attack_stock_target_payload_changed')
            return dict(archive=str(path),archive_sha256=file_sha(path),manifest=entry,
                        key=list(native.key),all_candidate_quality_payloads_identical=True)
    raise ValueError('native_attack_stock_target_missing')


def reconstruct_base(baseline, output, report):
    """Repack retained pre-append streams alongside the preserved archive files."""
    from build_commander_package import csf, write_csf
    package=output/'reconstructed-base'
    shutil.copytree(baseline/'package',package)
    for path in (baseline/'baseline/data').iterdir():
        shutil.copy2(path,package/'data'/path.name)
    strings_path=package/'data/gamestrings.csf'
    strings=csf(strings_path.read_bytes())
    keys=['personality:tfmacroprobe',*(row['text_key'].lower() for row in report['native_feedback'].values())]
    for key in keys:
        del strings[key]
    write_csf(strings,strings_path)
    archive=output/'reconstructed-base.big'
    with (output/'reconstruct-base.log').open('w',encoding='utf-8') as log:
        subprocess.run([str(SDK/'Tools/MakeBig.exe'),'-f',str(package),'-x:*.asset','-o:'+str(archive)],
                       stdout=log,stderr=subprocess.STDOUT,check=True)
    report['base_reconstruction']=dict(retained_streams=str(baseline/'baseline/data'),
        original_archive_available=False, reconstructed_archive_sha256=digest(archive),
        current_package_preservation_requires_compiled_audit=True)
    return archive


def stage(baseline, output):
    output = safe_output(output)
    if digest(baseline / 'TFMacroProbe.big') != BASE_PACKAGE or digest(baseline / 'MacroProbe.xml') != BASE_XML:
        raise ValueError('native_attack_exact_baseline_required')
    report = copy.deepcopy(json.loads((baseline / 'build-report.json').read_text(encoding='utf-8-sig')))
    root = E.fromstring((baseline / 'MacroProbe.xml').read_bytes())
    attack = next(node for node in root if node.tag == q('AIStrategicStateDefinition')
                  and node.get('id') == ATTACK.split(':', 1)[1])
    target = attack.find(q('TargetHeuristic'))
    if target.get('TargetHeuristic') != OLD_TARGET.split(':', 1)[1]:
        raise ValueError('native_attack_original_target_required')
    target.set('TargetHeuristic', CANDIDATE_TARGET)
    root.remove(next(node for node in root if node.get('id') == OLD_TARGET.split(':', 1)[1]))
    source=SDK/'SAGEXML/SkirmishAI/AITargetHeuristicLibrary.xml'
    native=next(node for node in E.parse(source).getroot() if node.get('id')==NATIVE_TARGET)
    if (native.get('HighestPriorityEnemyPlayersOnly')!='false' or native.get('HeuristicType')!='EnemyStructure'
            or native.get('SortType')!='Distance' or native.get('Location')!='Land'):
        raise ValueError('native_attack_stock_target_source_changed')
    clone=copy.deepcopy(native);clone.set('id',CANDIDATE_TARGET);root.append(clone)
    asset=next(row for row in report['assets'] if row['name']==OLD_TARGET)
    asset.update(name='AITargetingHeuristic:'+CANDIDATE_TARGET,instance_id=hex(sage_hash(CANDIDATE_TARGET.lower())))
    report['strategic_actions'] = ['attackenemy' if action == 'deployattack' else action
                                   for action in report['strategic_actions']]
    report['flags']['attackenemy'] = report['flags'].pop('deployattack')
    consumer = next(row for row in report['consumers'] if row['action'] == 'deployattack')
    for name in ('waypoint_name', 'waypoint_xyz', 'region_id', 'bounded_region_selection_supported',
                 'native_waypoint_require_unique_target', 'legacy_action_name_is_not_mission_purpose'):
        consumer.pop(name, None)
    consumer.update(action='attackenemy', domain='native_attack',
                    target_policy='original_native_closest_ground_structure_all_enemies',
                    target_heuristic=CANDIDATE_TARGET, stock_target_heuristic=NATIVE_TARGET,
                    primary_then_secondary_enemy_fallback=True)
    report.update(variant='native_enemy_attack_candidate_v1', field_verified=False,
                  compiled=False, deployed=False, product_capability_granted=False,
                  base_candidate_package_sha256=BASE_PACKAGE)
    output.mkdir(parents=True)
    E.indent(root, space='  ')
    E.ElementTree(root).write(output / 'MacroProbe.xml', encoding='utf-8', xml_declaration=True)
    report['macro_xml_sha256'] = digest(output / 'MacroProbe.xml')
    compile_probe(output, report, reconstruct_base(baseline,output,report))
    (output / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    review = audit(baseline, output)
    review['effective_stock_target']=audit_stock_target(output)
    (output / 'native-target-audit.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
    return review


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.baseline, args.output)))
