"""Build an isolated strategic-only package with a stock expansion preference.

No deployment, native transport, game access or capability grant. Exact build
and production consumers are removed, not repurposed as strategic aliases.
The added state preserves every stock MEDIUM expansion condition and tactic.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as E

from stage_commanders import SDK, q, safe_output, manifest_rows, sage_hash
from stage_macro_group_roles import generate_group_roles
from stage_macro_probe import compile_probe, digest

ROOT = Path(__file__).resolve().parents[1]
COMMANDER = '57e668b4-4d89-43bd-bc92-0dd436f046ef'
STOCK_ID = 'SovietExpansion_MEDIUM'
ACTION = 'expand'
STRATEGIC = ('regroup', 'scout', 'withdraw', 'reinforce', 'budgeteconomy',
             'budgetarmy', 'budgettech', 'deployattack', 'deploydefense', ACTION)
REMOVED = ('buildreactor', 'produceconscript', 'produceflak', 'producetank')
STOCK_PATH = SDK/'SAGEXML/SkirmishAI/States/SovietBaseStates.xml'


def normalized(node):
    result = copy.deepcopy(node)
    for child in result.iter():
        child.text = (child.text or '').strip() or None
        child.tail = None
    return E.tostring(result)


def canonical_sha(node):
    return hashlib.sha256(normalized(node)).hexdigest()


def stock_state():
    node = E.parse(STOCK_PATH).getroot().find(q('AIStrategicStateDefinition')+"[@id='"+STOCK_ID+"']")
    if (node is None or node.find(q('Tactic')).get('Tactic') != 'SimpleExpansion'
            or node.find(q('TargetHeuristic')).get('TargetHeuristic') != 'ExpansionHeuristic'
            or node.find('.//'+q('TeamTemplate')).get('MicroManager') != 'ExpansionMicroManager'):
        raise ValueError('stock_expansion_strategy_required')
    return node


def validate_added_state(node, original, flag):
    """Allow exactly identity, one external flag, and a preference weight.

    No changed target, creation rule, cooldown, danger gate or task lifecycle.
    Turning off the flag withdraws the extra preference, not committed work.
    """
    check = copy.deepcopy(node)
    check.set('id', original.get('id'))
    heuristic = check.find(q('Heuristic'))
    flags = heuristic.findall(q('ScriptedFlagHeuristic'))
    weights = heuristic.findall(q('ConstantHeuristic'))
    if (len(flags) != 1 or flags[0].attrib != {'FlagName': flag}
            or len(weights) != 1 or weights[0].attrib != {'Weight': '100'}):
        raise ValueError('expansion_exact_additional_preference_required')
    heuristic.remove(flags[0]); heuristic.remove(weights[0])
    if normalized(check) != normalized(original):
        raise ValueError('stock_expansion_semantics_changed')


def generate(commander, slot, baselines, map_raw):
    if commander != COMMANDER or type(slot) is not int or slot != 3:
        raise ValueError('strategic_expansion_fixed_profile_required')
    xml, report = generate_group_roles(commander, slot, baselines, map_raw)
    root = E.fromstring(xml)
    personality = root.find(q('AIPersonalityDefinition'))
    before = copy.deepcopy(report['consumers'])
    removed = [row for row in before if row['action'] in REMOVED]
    if len(removed) != 4:
        raise ValueError('exact_historical_precision_set_required')
    for row in removed:
        kind, name = row['state'].split(':', 1)
        node = root.find(q(kind)+"[@id='"+name+"']")
        link = personality.find(q('BuildState')+"[@State='"+name+"']")
        if kind != 'AIBuildStateDefinition' or node is None or link is None:
            raise ValueError('historical_precision_state_mismatch')
        root.remove(node); personality.remove(link)
    removed_names = {row['state'] for row in removed}
    removed_flags = {row['flag'] for row in removed}
    report['assets'] = [row for row in report['assets'] if row['name'] not in removed_names]
    report['consumers'] = [row for row in before if row['action'] not in REMOVED]
    report['flags'] = {key:value for key,value in report['flags'].items() if value not in removed_flags}
    original = stock_state()
    prefix = report['personality'].removesuffix('_Soviet')
    name = prefix+'_StockExpansionPreference'
    flag = '/'+prefix+'_expand'
    key = sage_hash('AIStrategicStateDefinition'), sage_hash(name.lower())
    occupied = {(row['type_id'], row['instance_id']) for row in baselines}
    occupied.update((int(row['type_id'], 0), int(row['instance_id'], 0)) for row in report['assets'])
    if key in occupied:
        raise ValueError('strategic_expansion_asset_collision')
    node = copy.deepcopy(original); node.set('id', name)
    heuristic = node.find(q('Heuristic'))
    heuristic.insert(0, E.Element(q('ScriptedFlagHeuristic'), FlagName=flag))
    E.SubElement(heuristic, q('ConstantHeuristic'), Weight='100')
    validate_added_state(node, original, flag)
    root.insert(list(root).index(personality), node)
    E.SubElement(personality, q('StrategicState'), id=name, State=name)
    asset = dict(name='AIStrategicStateDefinition:'+name, type_id=hex(key[0]), instance_id=hex(key[1]))
    report['assets'].append(asset); report['flags'][ACTION] = flag
    report['consumers'].append(dict(action=ACTION, flag=flag, state=asset['name'], domain='expansion',
        stock_source_state=STOCK_ID, native_tactic='SimpleExpansion', target_policy='original_native_expansion_target_selection',
        native_micro_manager='ExpansionMicroManager', details_owner='native_ai',
        additional_preference_only=True, removes_native_conditions=False,
        release_cancels_committed_work=False, release_blocks_autonomous_expansion=False,
        field_verified=False, capability_granted=False))
    actual = tuple(row['action'] for row in report['consumers'])
    if actual != STRATEGIC or root.findall(q('AIBuildStateDefinition')):
        raise ValueError('strategic_only_consumer_set_required')
    count = len(actual)
    budget = sum(1 << i for i, action in enumerate(actual) if action.startswith('budget'))
    report.update(variant='strategic_stock_expansion_candidate_v1', flag_count=count,
        strategic_actions=list(STRATEGIC), removed_precision_consumers=removed,
        transport_profile_revision=1, transport_known_mask=(1 << count)-1,
        transport_exclusive_masks=[budget, ((1 << count)-1) ^ budget],
        stock_expansion_source=str(STOCK_PATH), stock_expansion_source_sha256=digest(STOCK_PATH),
        stock_expansion_canonical_sha256=canonical_sha(original),
        stock_expansion_target_and_tactic_preserved=True,
        expansion_field_verified=False, product_capability_granted=False,
        transport_attached=False, scope='Strategic-only isolated stock expansion preference; no runtime qualification')
    E.indent(root, space='  ')
    return E.tostring(root, encoding='utf-8', xml_declaration=True), report


def audit_package(directory, report):
    """Read actual emitted asset sets and archive roundtrip after compilation."""
    from validate_side_imports import read_stream
    import importlib.util
    spec = importlib.util.spec_from_file_location('old_macro_archive_verifier', ROOT/'native-ai/macro-policy-runtime-v2/build.py')
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    verifier.verify_archive(directory)
    expected = {row['name'] for row in report['assets']}
    streams = []
    expansion = report['consumers'][-1]
    for stem in ('mod', 'mod_M', 'mod_L'):
        before = read_stream(directory/'baseline/data'/(stem+'.manifest'))
        after = read_stream(directory/'package/data'/(stem+'.manifest'))
        a = {row['name']:row for row in before['rows']}
        b = {row['name']:row for row in after['rows']}
        if set(b)-set(a) != expected or set(a)-set(b):
            raise ValueError('strategic_compiled_asset_set')
        if any(name.startswith('AIBuildStateDefinition:') for name in expected):
            raise ValueError('strategic_compiled_precision_state')
        unchanged = 0
        for name, old in a.items():
            new = b[name]
            if any(old[k] != new[k] for k in ['refs','type_id','instance_id','type_hash','instance_hash','flags']):
                raise ValueError('strategic_original_refs_changed')
            for ext, offset, size in [('bin','binary_offset','binary_size'),('imp','imp_offset','imp_size'),('relo','relo_offset','relo_size')]:
                if before['files'][ext][old[offset]:old[offset]+old[size]] != after['files'][ext][new[offset]:new[offset]+new[size]]:
                    raise ValueError('strategic_original_payload_changed')
            unchanged += 1
        row = b[expansion['state']]
        raw = after['files']['bin'][row['binary_offset']:row['binary_offset']+row['binary_size']]
        if expansion['flag'].encode()+b'\0' not in raw:
            raise ValueError('strategic_expansion_compiled_flag_missing')
        streams.append(dict(stream=stem, original_assets_unchanged=unchanged, added_assets=len(expected),
                            expansion_asset_sha256=hashlib.sha256(raw).hexdigest(), expansion_flag_serialized=True))
    return dict(kind='strategic_stock_expansion_compiled_review_v1', streams=streams,
                package_sha256=digest(directory/'TFMacroProbe.big'),
                archive_roundtrip_verified=True, original_assets_unchanged=True,
                stock_xml_semantics_verified=True, compiled_expansion_fields_decoded=False,
                field_verified=False, product_capability_granted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decoded-map', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compile-base-big', type=Path)
    args = parser.parse_args()
    output = safe_output(args.output)
    paths = [SDK/'BuiltMods/sagexml'/(stem+'.manifest') for stem in ('static','global','audio')]
    baselines = [row for path in paths for row in manifest_rows(path)]
    xml, report = generate(COMMANDER, 3, baselines, args.decoded_map.read_bytes())
    report.update(compiled=False, source_sha256=digest(__file__), regional_map_source=str(args.decoded_map.resolve()),
                  collision_baselines=[dict(path=str(path), sha256=digest(path)) for path in paths])
    output.mkdir(parents=True); (output/'MacroProbe.xml').write_bytes(xml)
    report['macro_xml_sha256'] = digest(output/'MacroProbe.xml')
    if args.compile_base_big:
        compile_probe(output, report, args.compile_base_big)
        audit = audit_package(output, report)
        (output/'compiled-strategic-audit.json').write_text(json.dumps(audit, indent=2)+'\n', encoding='utf8')
        report['compiled_strategic_audit_sha256'] = digest(output/'compiled-strategic-audit.json')
    (output/'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(output=str(output), compiled=report['compiled'], actions=report['strategic_actions'],
                         field_verified=False, product_capability_granted=False)))


if __name__ == '__main__':
    main()
