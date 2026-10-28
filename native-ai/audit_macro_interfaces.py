"""Exact-file macro interface research; no process, injection or native calls.

Static evidence identifies consumers and ABI candidates, never a field grant.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GAME_SHA256 = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PROBES = {
    'directive_entry': (0x8a0940, '83ec0c538bd98b83ec080000'),
    'directive_enum_native_write': (0x8a094e, '8b4c2414898bec080000'),
    'directive_native_expiry_reset': (0x8a0a6e, 'c783f4080000ffffff7f'),
    'directive_thiscall_one_argument': (0x8a0a8b, 'c20400'),
    'make_base_player_ai': (0x584273, '8bb090000000'),
    'make_base_ai_embedded_manager': (0x584295, '8d8e58040000'),
    'make_base_wrapper_two_arguments': (0x5842a1, 'c20800'),
    'base_manager_entry': (0x8b5770, '558bec83e4f883ec44'),
    'game_action_dispatch': (0x5a2b70, 'ff24856cd05a00'),
    'game_set_flag_case_is_noop': (0x5ad070, '5ed05a00'),
    'common_action_remap': (0x5ae215, '0fb68894e45a00ff248d44e45a00'),
    'common_set_flag_case': (0x5ae289, '53568bcfe8aecffdff'),
    'normal_flag_bool_write': (0x58b2a9, '8b4510837808000f95c088075f5e5d5bc20800'),
    'flag_lookup_map': (0x573b9c, '8d8fe46c0100'),
    'flag_lookup_present_or_null': (0x573bcf, '5f8d46185e83c410c204005f33c05e83c410c20400'),
    'ai_flag_query_entry': (0x889bf0, '8bc18b40048b5008518bcc52e80f2dc4ff'),
    'ai_flag_query_binary_result': (0x889c0c, '85c0740a8038007405d9e8c20800d9eec20800'),
    'flag_scope_separator': (0x85d2c4, '0fbe04313c2f741d'),
}
CALLS = {
    'directive_old_coop_relationship_cleanup': (0x8a09b2, 0x83b330),
    'directive_event_side_effect': (0x8a0a69, 0x923a20),
    'directive_feedback_wrapper': (0x8a0aad, 0x8a0940),
    'make_base_script_case': (0x5ac05f, 0x584250),
    'make_base_resolve_waypoint': (0x584288, 0x85f680),
    'make_base_native_manager': (0x58429b, 0x8b5770),
    'common_script_normal_set_flag': (0x5ae28d, 0x58b240),
    'normal_flag_native_get_or_create': (0x58b265, 0x58a8f0),
    'flag_map_insert_or_existing': (0x58a994, 0x5765b0),
    'flag_read_only_lookup': (0x573baa, 0x571370),
    'ai_query_uses_read_only_flag_lookup': (0x889c07, 0x573b10),
    'ai_query_constructs_native_string': (0x889bfc, 0x4cc910),
}
RANGES = {
    'directive_native_setter': (0x8a0940, 0x8a0ab7),
    'make_base_script_case': (0x5ac025, 0x5ac089),
    'make_base_script_wrapper': (0x584250, 0x5842a4),
    'base_manager_operation_candidate': (0x8b5770, 0x8b5b80),
    'coop_beacon_receiver_restrictions': (0x4f5100, 0x4f5300),
    'lua_execute_action_generic_dispatch': (0x582c50, 0x582eb0),
    'game_action_dispatch_noop': (0x5ad05e, 0x5ad07c),
    'common_script_action_executor': (0x5ae1a0, 0x5ae54c),
    'normal_script_flag_setter': (0x58b240, 0x58b2d6),
    'native_flag_get_or_create': (0x58a8f0, 0x58a9ba),
    'native_flag_map_insert_or_existing': (0x5765b0, 0x576672),
    'native_flag_read_only_lookup': (0x573b10, 0x573be4),
    'native_ai_script_flag_query_candidate': (0x889bf0, 0x889c1f),
    'native_script_name_scope_resolution': (0x85d2a0, 0x85d324),
}
SCHEMAS = ('AIStrategicDirective.xsd', 'AssetTypeAIBuilderDefinition.xsd',
           'AssetTypeAIStateDefinition.xsd', 'AssetTypeAITeamTemplate.xsd',
           'AssetTypeAIPersonalityDefinition.xsd', 'AIBank.xsd')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def audit(game, schema_root, output):
    if output.exists() or not output.resolve().is_relative_to(ROOT/'reports'):
        raise ValueError('Fresh local reports directory required')
    raw = game.read_bytes()
    if hashlib.sha256(raw).hexdigest() != GAME_SHA256:
        raise ValueError('Exact game hash required')
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    if raw[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', raw, pe+4)[0] != 0x14c:
        raise ValueError('Exact x86 PE required')
    sections = pe + 24 + struct.unpack_from('<H', raw, pe+20)[0]
    count = struct.unpack_from('<H', raw, pe+6)[0]
    base = struct.unpack_from('<I', raw, pe+24+28)[0]

    def read(va, size):
        rva = va-base
        for i in range(count):
            header = sections+40*i
            virtual_size, start, extent, offset = struct.unpack_from('<IIII', raw, header+8)
            if start <= rva and rva+size <= start+min(virtual_size, extent):
                return raw[offset+rva-start:offset+rva-start+size]
        raise ValueError('Unbacked PE range')

    checked = []
    for name, (va, value) in PROBES.items():
        expected = bytes.fromhex(value)
        if read(va, len(expected)) != expected:
            raise ValueError('Macro byte mismatch: '+name)
        checked.append(dict(name=name, address=hex(va), bytes=value))
    for name, (va, target) in CALLS.items():
        value = read(va, 5)
        if value[0] != 0xe8 or va+5+struct.unpack_from('<i', value, 1)[0] != target:
            raise ValueError('Macro call mismatch: '+name)
        checked.append(dict(name=name, address=hex(va), bytes=value.hex(), target=hex(target)))

    remap = read(0x5ae494, 1)[0]  # SET_FLAG action 1, common loop subtracts 1.
    common_case = struct.unpack('<I', read(0x5ae444+remap*4, 4))[0]
    game_case = struct.unpack('<I', read(0x5ad06c+1*4, 4))[0]
    if common_case != 0x5ae289 or game_case != 0x5ad05e:
        raise ValueError('SET_FLAG common/game dispatch distinction changed')
    flag_dispatch = dict(action_index=1, common_case=hex(common_case), game_case=hex(game_case),
        lua_execute_action_ack_is_effect_proof=False, normal_setter=hex(0x58b240),
        read_only_lookup=hex(0x573b10), ai_query_candidate=hex(0x889bf0),
        map_offset=hex(0x16ce4), node_key_offset=hex(0x10), node_value_offset=hex(0x18),
        hash_algorithm='FNV-1-32: multiply then xor; two unsigned words (scope, name)',
        name_scope='First slash selects explicit scope and strips it from name; no slash uses current script context.',
        ai_class_factory_binding_verified=False, runtime_abi_verified=False)

    schema_rows = []
    ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
    for name in SCHEMAS:
        path = schema_root/name
        tree = ET.fromstring(path.read_bytes())
        declarations = []
        for node in tree:
            if node.tag.endswith(('complexType', 'simpleType')):
                declarations.append(dict(name=node.get('name'),
                    enumerations=[n.get('value') for n in node.findall('.//xs:enumeration', ns)],
                    enumeration_attributes=[n.attrib for n in node.findall('.//xs:enumeration', ns)],
                    elements=[n.attrib for n in node.findall('.//xs:element', ns)],
                    attributes=[n.attrib for n in node.findall('.//xs:attribute', ns)]))
        schema_rows.append(dict(path=str(path), sha256=sha(path), declarations=declarations))
    directive = next(row for row in schema_rows if row['path'].endswith('AIStrategicDirective.xsd'))
    values = next(d['enumerations'] for d in directive['declarations'] if d['name']=='AIStrategicDirective')
    invalid = next(d['enumeration_attributes'][0] for d in directive['declarations'] if d['name']=='AIStrategicDirective')
    if (values != ['Invalid','Normal','Assault','HoldPosition','HoldObject','Help']
            or invalid.get('{uri:ea.com:eala:asset:schema}forceValue') != '-1'):
        raise ValueError('Unexpected directive enum')
    objdump = ROOT/'toolchain/w64devkit/bin/objdump.exe'
    output.mkdir()
    ranges = []
    for name, (start, end) in RANGES.items():
        text = subprocess.check_output([str(objdump), '-d', '--start-address='+hex(start),
                                        '--stop-address='+hex(end), str(game)], timeout=20)
        path = output/(name+'.txt');path.write_bytes(text)
        ranges.append(dict(name=name, start=hex(start), end=hex(end), file=path.name, sha256=sha(path)))
    report = dict(kind='native_macro_interface_static_audit', created_at=datetime.now().astimezone().isoformat(),
        game=str(game), game_sha256=GAME_SHA256, source_sha256=sha(__file__),
        objdump_sha256=sha(objdump), probes=checked, ranges=ranges, schemas=schema_rows,
        scripted_flag_dispatch=flag_dispatch,
        process_opened=False, native_game_calls=0, unit_control=False, field_verified=False,
        capability_granted=False, full_goal_complete=False,
        conclusions=[
            'Directive enum and native setter have state/event/timer side effects; a raw enum write is not equivalent.',
            'Co-op beacon reception and prior-directive cleanup have relationship constraints; no standalone computer control is granted.',
            'MAKE_BASE resolves a named waypoint and delegates to AI+0x458 native manager; it is not an arbitrary building/placement API.',
            'Builder states, budget states, strategic states and native team/micro definitions exist in the local SDK.',
            'SDK declarations and exact static consumers do not prove dynamic selection, construction, scouting or deployment effects.'
            ,'Lua ExecuteAction dispatches to the game-specific SET_FLAG no-op; its true acknowledgement is not flag mutation proof.'
            ,'Normal common scripts use the real flag setter; native AI has a flag-query candidate using the same read-only table lookup.'
            ,'Explicit slash scope avoids dependence on current script context; this does not solve duplicate-personality owner isolation.'
        ])
    (output/'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(probes=len(checked), ranges=len(ranges), schemas=len(schema_rows),
                         process_opened=False, field_verified=False, audit_sha256=sha(output/'audit.json'))))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game',type=Path,default=Path('E:/RedRar3/Data/RA3_1.12.game'))
    parser.add_argument('--schemas',type=Path,default=Path('E:/RA3Modding/SDK/Schemas/xsd/SkirmishAI'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();audit(args.game,args.schemas,args.output)
