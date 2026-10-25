"""Read desktop commander-bindings.json and stage UUID-derived SDK assets.

Writes only a new directory below native-ai/staging. Never compiles, deploys,
changes SDK files, starts a game, or claims menu/Side binding is operational.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import uuid
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parent
SDK = Path(r'E:\RA3Modding\SDK')
HASH_SOURCE = ROOT.parent / 'reference/Ra3-Copilot/unit-codes/tools/sage_hash.py'
sys.path.insert(0, str(HASH_SOURCE.parent))
from sage_hash import sage_hash
NS = 'uri:ea.com:eala:asset'
E.register_namespace('', NS)
def q(name): return '{' + NS + '}' + name
TYPE = 'AIPersonalityDefinition'
SIDES = [('Allies', 'Allied', '1AlliedBalanced'),
         ('Soviet', 'Soviet', '1SovietBalanced'),
         ('Japan', 'Japan', '1JapanBalanced')]
FIELDS = {'id', 'name', 'connection_id', 'model_override', 'effective_model', 'personality'}


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def valid_xml_text(value):
    return all(c in '\t\n\r' or 0x20 <= ord(c) <= 0xd7ff
               or 0xe000 <= ord(c) <= 0xfffd or 0x10000 <= ord(c) <= 0x10ffff for c in value)


def normalized_uuid(value, field):
    if not isinstance(value, str):
        raise ValueError(field + ' must be a UUID string')
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError(field + ' must be a UUID string') from None


def validate_document(document):
    if not isinstance(document, dict) or type(document.get('schema_version')) is not int or document['schema_version'] != 1:
        raise ValueError('Expected desktop commander-bindings schema_version 1')
    if document.get('instance_key') != ['session_id', 'player_id', 'commander_id']:
        raise ValueError('Unexpected instance_key')
    rows = document.get('commanders')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('Expected 1..100 commanders')
    clean, ids, names = [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError('Unexpected commander fields; only desktop binding fields are accepted')
        ident = normalized_uuid(row['id'], 'id')
        connection = normalized_uuid(row['connection_id'], 'connection_id')
        name = row['name']
        if not isinstance(name, str) or not name.strip() or len(name) > 40 or not valid_xml_text(name):
            raise ValueError('Invalid display name or XML control character')
        if ident in ids or name.strip().casefold() in names:
            raise ValueError('Duplicate canonical commander UUID or display name')
        ids.add(ident); names.add(name.strip().casefold())
        if type(row['personality']) is not int or row['personality'] not in (0, 1, 2):
            raise ValueError('Invalid personality preset')
        for key in ['model_override', 'effective_model']:
            if not isinstance(row[key], str) or len(row[key]) > 200 or not valid_xml_text(row[key]):
                raise ValueError('Invalid model value')
        clean.append(dict(id=ident, name=name, connection_id=connection,
                          model_override=row['model_override'], effective_model=row['effective_model'],
                          personality=row['personality']))
    return sorted(clean, key=lambda row: row['id'])


def manifest_rows(path):
    """Read only IDs and names from a v6-style RA3 manifest, not its payloads."""
    raw = path.read_bytes()
    if len(raw) < 48:
        raise ValueError('Truncated baseline manifest')
    h = struct.unpack_from('<12I', raw)
    refs = 48 + h[3] * 48
    names = refs + h[8] + h[9]
    if names + h[10] + h[11] != len(raw):
        raise ValueError('Unsupported baseline manifest layout')
    rows = []
    for i in range(h[3]):
        a = struct.unpack_from('<12I', raw, 48 + i * 48)
        start = names + a[6]
        if not names <= start < names + h[10]:
            raise ValueError('Invalid baseline asset name offset')
        end = raw.index(0, start, names + h[10])
        rows.append(dict(type_id=a[0], instance_id=a[1], name=raw[start:end].decode('utf-8')))
    return rows


def make_registry(document, baselines, hash_fn=sage_hash):
    commanders = validate_document(document)
    type_id = hash_fn(TYPE)
    occupied = {}
    for row in baselines:
        key = row['type_id'], row['instance_id']
        occupied.setdefault(key, row['name'])
        if row['name'].startswith(TYPE + ':'):
            if row['type_id'] != sage_hash(TYPE) or row['instance_id'] != sage_hash(row['name'].split(':', 1)[1].lower()):
                raise ValueError('Hash implementation does not match baseline personality IDs')
    identities = []
    for commander in commanders:
        token = uuid.UUID(commander['id']).hex
        loc = 'Personality:LLM_' + token
        assets = []
        for side, suffix, base in SIDES + [('Random', 'Random', None)]:
            ident = '4LLM_' + token + '_' + suffix
            instance = hash_fn(ident.lower())
            key = type_id, instance
            if key in occupied:
                raise ValueError('32-bit asset hash collision: ' + ident + ' versus ' + occupied[key])
            occupied[key] = TYPE + ':' + ident
            assets.append(dict(side=side, asset_id=ident, personality_type=ident,
                               type_id='0x%08x' % type_id, instance_id='0x%08x' % instance,
                               localization_key=loc, inherit_from=base))
        commander['assets'] = assets
        identities.append(dict(commander_id=commander['id'], assets=assets))
    return dict(schema_version=1, naming_scheme='uuid32-v1',
                game_sync_verified=False, side_binding_verified=False,
                compiled_ids_verified=False, deployed=False,
                identity_revision=hashlib.sha256(canonical_json(identities)).hexdigest(),
                registry_revision=hashlib.sha256(canonical_json(commanders)).hexdigest(),
                commanders=commanders)


def emit_xml(registry, random_template):
    root = E.Element(q('AssetDeclaration'))
    E.SubElement(root, q('Tags'))
    inc = E.SubElement(root, q('Includes'))
    for _, suffix, _ in SIDES:
        E.SubElement(inc, q('Include'), type='instance',
                     source='DATA:SkirmishAI/Personalities/' + suffix + 'Balanced.xml')
    for commander in registry['commanders']:
        mapping = {asset['side']: asset for asset in commander['assets']}
        for asset in commander['assets']:
            attrs = dict(id=asset['asset_id'], PersonalityType=asset['personality_type'],
                         SkirmishPersonality='true', PersonalityUIName=asset['localization_key'])
            if asset['inherit_from']:
                E.SubElement(root, q(TYPE), inheritFrom=asset['inherit_from'], **attrs)
                # Do not append Side: the inherited array already contains one.
            else:
                node = copy.deepcopy(random_template)
                node.attrib.update(attrs)
                for item in node.findall(q('PersonalityMap')):
                    item.set('Personality', mapping[item.get('Side')]['asset_id'])
                root.append(node)
    E.indent(root, space='  ')
    return E.tostring(root, encoding='utf-8', xml_declaration=True)


def safe_output(path):
    path = path.resolve()
    staging = (ROOT / 'staging').resolve()
    if not staging.is_relative_to(ROOT.resolve()) or not path.is_relative_to(staging) or path == staging:
        raise ValueError('Output must be a new child directory of native-ai/staging')
    if path.exists():
        raise ValueError('Output already exists; choose a new staging directory')
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bindings', type=Path, required=True)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--baseline', type=Path, action='append', default=[],
                    help='Additional collision baseline, e.g. current mod.manifest; stock SDK baselines always checked')
    a = ap.parse_args()
    output = safe_output(a.output or ROOT / 'staging' / ('commanders-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]))
    if a.bindings.stat().st_size > 1024 * 1024:
        raise ValueError('Bindings file exceeds 1 MiB')
    raw = a.bindings.read_bytes()
    document = json.loads(raw.decode('utf-8-sig'))
    paths = [SDK / 'BuiltMods/sagexml' / (name + '.manifest') for name in ['static', 'global', 'audio']] + a.baseline
    baselines, provenance = [], []
    for path in paths:
        rows = manifest_rows(path)
        baselines.extend(rows)
        provenance.append(dict(path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), assets=len(rows)))
    registry = make_registry(document, baselines)
    template_file = SDK / 'SAGEXML/SkirmishAI/Personalities/RandomPersonalities.xml'
    template = E.parse(template_file).getroot().find(q(TYPE))
    if template is None:
        raise ValueError('Stock Random template missing')
    xml = emit_xml(registry, template)
    strings = {c['assets'][0]['localization_key']: c['name'] for c in registry['commanders']}
    # UTF-8 JSON carries arbitrary XML punctuation as data, never hand-concatenated
    # XML or .str syntax. Localized display names are not SDK identifiers.
    payloads = {'LLMCommanders.xml': xml,
                'localization.json': json.dumps(strings, ensure_ascii=False, indent=2).encode('utf-8'),
                'commander-registry.json': json.dumps(registry, ensure_ascii=False, indent=2).encode('utf-8')}
    report = dict(input=str(a.bindings.resolve()), input_sha256=hashlib.sha256(raw).hexdigest(),
                  input_read_only=True, output=str(output), commanders=len(registry['commanders']),
                  generated_assets=sum(len(c['assets']) for c in registry['commanders']),
                  collision_baselines=provenance, baseline_assets_checked=len(baselines),
                  hash_source=str(HASH_SOURCE), hash_source_sha256=hashlib.sha256(HASH_SOURCE.read_bytes()).hexdigest(),
                  random_template_sha256=hashlib.sha256(template_file.read_bytes()).hexdigest(),
                  compiled=False, deployed=False, game_sync_verified=False,
                  files={name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()})
    output.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        (output / name).write_bytes(data)
    (output / 'generation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(output=str(output), commanders=report['commanders'], assets=report['generated_assets'],
                          identity_revision=registry['identity_revision'], game_sync_verified=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
