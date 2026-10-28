"""Pin native call/copy ABI clues from the actual game file; never open a process.

These are static bytes and disassembly, not an execution or firing grant.
"""
import argparse
import hashlib
import json
import struct
import subprocess
from datetime import datetime
from pathlib import Path

EXPECTED_GAME = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
ROOT = Path(__file__).resolve().parents[2]
RANGES = {
    'attack_facade': (0x572280, 0x572310),
    'attack_dispatch_method': (0x785D20, 0x785DDA),
    'attack_private': (0x76E690, 0x76E7A1),
    'command_copy': (0x830220, 0x830312),
    'command_unpack': (0x830320, 0x8304D0),
    'weapon_selector': (0x6F7C60, 0x6F7CA7),
    'weapon_slot_active': (0x6DBE80, 0x6DBE94),
    'weapon_slot_entry': (0x6F88E0, 0x6F88F0),
    'body_damage_entry': (0x764E20, 0x764E80),
    'weapon_state_machine_constructor': (0x6F8D80, 0x6F8F96),
    'weapon_state_id_reader': (0x6DED70, 0x6DED8B),
    'weapon_ready_name_getter': (0x6DC180, 0x6DC186),
    'weapon_ready_update': (0x6DC190, 0x6DC1B8),
    'weapon_fire_enter': (0x7AD5F0, 0x7AD680),
    'weapon_fire_scope_candidate': (0x79BDE0, 0x79BF83),
    'weapon_object_fire_candidate': (0x790F30, 0x790FC0),
    'weapon_compiled_base_range_getter': (0x6DC370, 0x6DC377),
    'weapon_compiled_minimum_range_getter': (0x6DC340, 0x6DC368),
    'weapon_height_adjusted_range': (0x6F92F0, 0x6F938F),
    'weapon_range_native_consumer': (0x86C9EA, 0x86CA31),
    'weapon_actual_fire_core': (0x790D80, 0x790F26),
    'weapon_normal_nugget_dispatch': (0x75A5D0, 0x75A68A),
    'weapon_direct_nugget_dispatch': (0x714170, 0x7141EE),
    'body_damage_full_callback': (0x764E20, 0x765180),
}
PROBES = {
    'facade_opcode_11': (0x57228D, '6a0b'),
    'facade_target_at_command_14': (0x5722A2, '894c2418'),
    'facade_requested_count_at_command_44': (0x5722AA, '89542448'),
    'copy_target_pointer_to_object_id': (0x83024D, '8b80dc000000'),
    'copy_target_id_at_stored_14': (0x830257, '894614'),
    'copy_count_command44_to_stored48': (0x8302AA, '8b5744895648'),
    'unpack_target_id_load': (0x830327, '8b4614'),
    'unpack_target_pointer_at_command14': (0x830398, '895f14'),
    'private_ground_selector_minus_one': (0x76E6BD, '6aff8bcb'),
    'private_count_into_selected_entry24': (0x76E740, '8b442418894724'),
    'private_thiscall_three_stack_arguments': (0x76E79E, 'c20c00'),
    'slot_current_index_five_is_none': (0x6DBE80, '8b411483f8057409'),
    'slot_entry_table_index': (0x6F88E0, '8b81940000008b4c24048b0488c20400'),
    'damage_source_id_info_plus8': (0x764E64, '8b4b08'),
    'weapon_fsm_vtable': (0x6F8DA4, 'c70650fcc100'),
    'weapon_fsm_entry_backpointer80': (0x6F8DAA, '899680000000'),
    'weapon_ready_state_vtable': (0x6F8E23, 'c70718fdc100'),
    'weapon_ready_registered_id0': (0x6F8E2D, '536a016a015753'),
    'weapon_ready_name_pointer': (0x6DC180, 'b86cfdc100c3'),
    'weapon_ready_name_text': (0xC1FD6C, '576561706f6e5265616479537461746500'),
    'weapon_fire_state_vtable': (0x6F8EA6, 'c707e8fdc100'),
    'weapon_fire_name_text': (0xC1FE3C, '576561706f6e46697265537461746500'),
    'weapon_base_range_schema_plus4': (0x6DC370, '8b4104d94004c3'),
    'weapon_minimum_range_schema_plus8': (0x6DC341, '8b4104f30f104008'),
    'weapon_height_range_base_schema_plus4': (0x6F9307, '8b4104f30f104004'),
    'weapon_height_bonus_schema_plus0c': (0x6F931B, '0f2f500c'),
    'weapon_height_bonus_schema_plus10_14': (0x6F9335, 'f30f595014f30f104810'),
    'weapon_entry_template_to_range_getter': (0x86C9F7, '8b4804e871f9e6ff'),
    'fire_core_entry_signature': (0x790D80, '83ec0856578b7c2414'),
    'fire_core_actor_context_plus4': (0x790E55, '8b4704'),
    'fire_core_requires_ammo': (0x790E44, '837e1c00'),
    'fire_core_context_weapon_entry': (0x790EC2, '89771889472c'),
    'fire_core_ammo_limit_burst_decrement': (0x790ED1, '83c8ff01461c01462401462c'),
    'nugget_context_target_plus1c': (0x75A5EB, '8b461c'),
    'body_callback_entry_signature': (0x764E20, '83ec1455578bf98b47f0'),
    'body_callback_actor_reverse_link': (0x764E39, '8b6ff8'),
    'body_reported_damage_info90': (0x765059, 'f30f104708f30f5c4704f30f118390000000'),
}


def audit(game: Path, output: Path):
    raw = game.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_GAME:
        raise ValueError('exact_game_hash_required')
    pe = struct.unpack_from('<I', raw, 0x3C)[0]
    if raw[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', raw, pe + 4)[0] != 0x14C:
        raise ValueError('exact_x86_pe_required')
    section_count = struct.unpack_from('<H', raw, pe + 6)[0]
    optional_size = struct.unpack_from('<H', raw, pe + 20)[0]
    image_base = struct.unpack_from('<I', raw, pe + 24 + 28)[0]
    sections = []
    for i in range(section_count):
        header = pe + 24 + optional_size + 40 * i
        _, va, size, pointer = struct.unpack_from('<4I', raw, header + 8)
        sections.append((image_base + va, size, pointer))

    def read(address, length):
        for va, size, pointer in sections:
            if va <= address and address + length <= va + size:
                return raw[pointer + address - va:pointer + address - va + length]
        raise ValueError('address_not_in_file_section')

    checked = []
    for name, (address, expected) in PROBES.items():
        actual = read(address, len(bytes.fromhex(expected)))
        if actual.hex() != expected:
            raise ValueError('native_byte_probe_failed:' + name)
        checked.append(dict(name=name, address=hex(address), bytes=actual.hex()))
    for name, site, target in [('private_weapon_getter', 0x76E6C1, 0x6F7C60),
                               ('normal_dispatch_private_attack', 0x785DCB, 0x76E690),
                               ('normal_core_nugget_dispatch', 0x790ECC, 0x75A5D0),
                               ('direct_core_nugget_dispatch', 0x790EA8, 0x714170)]:
        instruction = read(site, 5)
        if instruction[0] != 0xE8 or site + 5 + struct.unpack_from('<i', instruction, 1)[0] != target:
            raise ValueError('native_call_target_failed:' + name)
        checked.append(dict(name=name, address=hex(site), bytes=instruction.hex(), target=hex(target), return_address=hex(site + 5)))
    tool = ROOT / 'toolchain/w64devkit/bin/objdump.exe'
    tool_digest = hashlib.sha256(tool.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    ranges = []
    for name, (start, end) in RANGES.items():
        text = subprocess.run([str(tool), '-d', f'--start-address={start:#x}', f'--stop-address={end:#x}', str(game)],
                              check=True, capture_output=True, timeout=30).stdout
        path = output / (name + '.txt')
        path.write_bytes(text)
        ranges.append(dict(name=name, start=hex(start), end_exclusive=hex(end),
                           code_sha256=hashlib.sha256(read(start, end-start)).hexdigest(),
                           disassembly_file=path.name, disassembly_sha256=hashlib.sha256(text).hexdigest()))
    if hashlib.sha256(game.read_bytes()).hexdigest()!=EXPECTED_GAME or hashlib.sha256(tool.read_bytes()).hexdigest()!=tool_digest:
        raise ValueError('native_audit_inputs_changed_during_disassembly')
    result = dict(kind='near_combat_exact_native_static_audit', created_at=datetime.now().astimezone().isoformat(),
                  game=str(game.resolve()), game_sha256=EXPECTED_GAME, machine='x86', image_base=hex(image_base),
                  tool_sha256=tool_digest,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), checked=checked, ranges=ranges,
                  process_opened=False, native_game_calls=0, field_verified=False, capability_granted=False,
                  conclusions=[
                      'Normal attack facade builds opcode 11 with target pointer at +0x14 and requested count at +0x44.',
                      'Native deferred copy stores target object ID at +0x14 and count at +0x48; pointer equality is not a valid copy invariant.',
                      'Unpack resolves target ID back to a pointer before dispatch; fresh identity and visibility must be checked again.',
                      'Private attack receives target/count/source; verified normal method return caller is 0x785dd0.',
                      'Private attack writes requested count into its then-selected weapon entry +0x24. This does not prove actual finite firing or shot/damage attribution.',
                      'Damage source object ID alone does not establish a shot-command link.',
                      'WeaponReadyState is native state0/vtable0xc1fd18. Its reverse links and request flag must be read; ammo alone is insufficient.',
                      'Fire-state entry calls 0x79bde0 with target mode0 (object) or mode1 (position), not a target object ID. This is only a future correlation hook candidate.',
                  ])
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output.resolve()), probes=len(checked), ranges=len(ranges), field_verified=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=Path('E:/RedRar3/Data/RA3_1.12.game'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.game, args.output)
