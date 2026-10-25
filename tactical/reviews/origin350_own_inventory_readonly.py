"""Own-only inventory research. Never executes a game function or grants a permit.

The only process access is the existing Memory reader (OpenProcess 0x410).
Pure decoders are importable without loading any Windows process APIs.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
EXACT = {
    0xc16ff13f: 'SovietConstructionYard',
    0x80d4ea1e: 'SovietBarracks',
    0xcf8d9f20: 'SovietPowerPlant',
    0xc45aaeab: 'SovietRefinery',
}
PACKAGE = '2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665'
EXE = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
CAPTURE_ONLY_CONTAINS = {'EngineerContain', 'InfiltratorContain'}
FIRING_CONTAIN_NAMES = {
    'OpenContain', 'GarrisonContain', 'TransportContain', 'HordeContain',
    'HordeGarrisonContain', 'ContestableGarrisonContain',
}


def pointer(value):
    return isinstance(value, int) and 0x10000 <= value <= 0xfffffffc and value % 4 == 0


def code_pointer(value):
    return isinstance(value, int) and 0x401000 <= value < 0xbc1000


def native_name(memory, primary_vtable):
    """Decode only mov eax, imm32; ret, at primary vtable +8. No calls."""
    result = {'verified_constant_name_getter': False, 'native_name': None}
    try:
        if not 0xbc1000 <= primary_vtable < 0xd3b000:
            raise ValueError('primary_vtable_outside_pinned_image_data')
        getter = memory.u32(primary_vtable + 8)
        result['getter'] = hex(getter)
        if not code_pointer(getter):
            raise ValueError('name_getter_outside_pinned_text')
        code = memory.read(getter, 6)
        result['getter_bytes'] = code.hex()
        if len(code) != 6 or code[0] != 0xb8 or code[5] != 0xc3:
            raise ValueError('complex_name_getter_unknown_not_executed')
        name_pointer = struct.unpack_from('<I', code, 1)[0]
        result['name_pointer'] = hex(name_pointer)
        if not 0xbc1000 <= name_pointer < 0xd3b000:
            raise ValueError('name_string_outside_pinned_image_data')
        raw = memory.read(name_pointer, 96)
        if b'\0' not in raw:
            raise ValueError('unterminated_native_name')
        name = raw.split(b'\0', 1)[0].decode('ascii')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,94}', name):
            raise ValueError('invalid_native_name')
        result.update(native_name=name, verified_constant_name_getter=True)
    except Exception as error:
        result['error'] = str(error)
    return result


def module_inventory(memory, thing, limit=256):
    result = {'complete': False, 'all_names_decoded': False, 'modules': []}
    try:
        array = memory.u32(thing + 0x310)
        result['array'] = hex(array)
        if not pointer(array):
            raise ValueError('null_or_invalid_module_array_unknown')
        seen = set()
        for index in range(limit + 1):
            module = memory.u32(array + index * 4)
            if module == 0:
                result.update(complete=True, terminator_index=index)
                break
            if index == limit:
                raise ValueError('module_array_not_terminated_within_bound')
            if not pointer(module) or module in seen:
                raise ValueError('module_pointer_invalid_or_duplicate')
            seen.add(module)
            vtable = memory.u32(module)
            back = memory.u32(module + 8)
            row = {'index': index, 'module': hex(module), 'vtable': hex(vtable),
                   'thing_backpointer': hex(back), 'backpointer_ok': back == thing,
                   'behavior_vtable': hex(memory.u32(module + 0xc)),
                   'module_data': hex(memory.u32(module + 4))}
            row.update(native_name(memory, vtable))
            result['modules'].append(row)
            if back != thing:
                raise ValueError('module_thing_backpointer_mismatch')
        result['all_names_decoded'] = result['complete'] and all(
            row['verified_constant_name_getter'] for row in result['modules'])
        # A constructed Thing normally has modules. An empty array is not proof.
        result['nonempty_complete'] = result['complete'] and bool(result['modules'])
    except Exception as error:
        result['error'] = str(error)
    return result


def weapon_matrix(memory, thing, limit=64):
    result = {'matrix_complete': False, 'configuration_absence_proven': False,
              'slots': []}
    try:
        container = memory.u32(thing + 0x37c)
        result['container'] = hex(container)
        if container == 0:
            result['observation'] = 'null_registered_weapon_set_reference_not_absence_proof'
            return result
        if not pointer(container):
            raise ValueError('weapon_container_invalid')
        result['vtable'] = hex(memory.u32(container))
        result['thing_backpointer'] = hex(memory.u32(container + 8))
        if memory.u32(container + 8) != thing:
            raise ValueError('weapon_container_backpointer_mismatch')
        start, end, capacity = [memory.u32(container + off) for off in (0x24, 0x28, 0x2c)]
        result['vector'] = [hex(start), hex(end), hex(capacity)]
        if (not start or not pointer(start) or end < start or capacity < end
                or end - start > 4 * limit or (end - start) % 4
                or capacity - start > 0x10000 or capacity % 4):
            raise ValueError('weapon_slot_bounds_unknown')
        seen = set()
        for at in range(start, end, 4):
            slot = memory.u32(at)
            if not pointer(slot) or slot in seen:
                raise ValueError('invalid_or_duplicate_weapon_slot')
            seen.add(slot)
            vtable = memory.u32(slot)
            row = {'slot': hex(slot), 'vtable': hex(vtable), 'modes': []}
            result['slots'].append(row)
            if (vtable != 0xc3a6e0 or memory.u32(vtable + 0x24) != 0x6dbe80
                    or memory.u32(vtable + 0x28) != 0x6f88e0):
                raise ValueError('unverified_slot_class_or_getters')
            row['selected_index'] = memory.u32(slot + 0x14)
            if row['selected_index'] > 5:
                raise ValueError('unknown_selected_index')
            config, table = memory.u32(slot + 0xc), memory.u32(slot + 0x94)
            row.update(slot_config=hex(config), entry_table=hex(table))
            if not pointer(config) or not pointer(table):
                raise ValueError('slot_config_or_entry_table_null_unknown')
            row['slot_config_raw_first_0x1c'] = memory.read(config, 0x1c).hex()
            for mode in range(6):
                entry = memory.u32(table + mode * 4)
                item = {'mode': mode, 'entry': hex(entry)}
                row['modes'].append(item)
                if entry == 0:
                    item['semantics'] = 'no_current_entry_not_no_configured_weapon'
                    continue
                if not pointer(entry):
                    raise ValueError('weapon_entry_invalid')
                ev, template, back = [memory.u32(entry + off) for off in (0, 4, 8)]
                if ev != 0xc2e324 or back != slot or not pointer(template):
                    raise ValueError('weapon_entry_identity_mismatch')
                schema = memory.u32(template + 4)
                header = memory.u32(schema)
                if memory.u32(header) != 0x94d4d96e:
                    raise ValueError('weapon_asset_type_mismatch')
                item.update(vtable=hex(ev), slot_backpointer=hex(back),
                            template=hex(template), schema=hex(schema), header=hex(header),
                            asset_type=hex(memory.u32(header)), asset_id=hex(memory.u32(header + 4)),
                            ammo=memory.u32(entry + 0x1c))
        result['matrix_complete'] = True
        result['observation'] = ('empty_valid_slot_vector_not_configuration_proof' if not seen
                                 else 'all_current_entries_read_all_six_modes')
    except Exception as error:
        result['error'] = str(error)
    return result


def identity(memory, thing):
    template, body = memory.u32(thing + 4), memory.u32(thing + 0x33c)
    if not pointer(template) or not pointer(body):
        raise ValueError('missing_template_or_body')
    hp = memory.f32(body + 4)
    if not math.isfinite(hp):
        raise ValueError('nonfinite_hp')
    return {'address': hex(thing), 'vtable': hex(memory.u32(thing)),
            'object_id': memory.u32(thing + 0xdc), 'owner': hex(memory.u32(thing + 0x418)),
            'template': hex(template), 'type_hash': hex(memory.u32(template + 8)),
            'body': hex(body), 'hp': hp,
            'module_array': hex(memory.u32(thing + 0x310)),
            'weapon_container': hex(memory.u32(thing + 0x37c))}


def unit_pass(memory, thing):
    return {'identity': identity(memory, thing),
            'module_inventory': module_inventory(memory, thing),
            'weapon_matrix': weapon_matrix(memory, thing)}


def sample_unit(memory, thing, owner, object_id, type_hash, logic):
    result = {'observation_verified': False, 'exclusion_granted': False,
              'classification': 'unknown_keep_threat'}
    try:
        result['frame_start'] = memory.u32(logic + 0x50)
        first = unit_pass(memory, thing)
        second = unit_pass(memory, thing)
        result.update(first=first, second=second, final_identity=identity(memory, thing),
                      frame_end=memory.u32(logic + 0x50))
        expected = {'address': hex(thing), 'vtable': '0xc4db60', 'object_id': object_id,
                    'owner': hex(owner), 'type_hash': hex(type_hash)}
        ident = first['identity']
        named_weapon_modules = [row['module'] for row in first['module_inventory']['modules']
                                if row.get('native_name') == 'WeaponSetUpdate']
        cache_matches = (named_weapon_modules == [ident['weapon_container']]
                         if ident['weapon_container'] != '0x0' else not named_weapon_modules)
        checks = {'expected_identity': all(ident[k] == v for k, v in expected.items()),
                  'positive_frame': result['frame_start'] > 0,
                  'same_frame': result['frame_start'] == result['frame_end'],
                  'double_pass_equal': first == second,
                  'final_identity_equal': ident == result['final_identity'],
                  'alive': ident['hp'] > 0,
                  'module_inventory_complete': first['module_inventory'].get('nonempty_complete', False),
                  'all_module_names_decoded': first['module_inventory']['all_names_decoded'],
                  'weapon_reference_matches_named_module': cache_matches,
                  'weapon_matrix_read_valid': 'error' not in first['weapon_matrix'] and (
                      ident['weapon_container'] == '0x0' or first['weapon_matrix']['matrix_complete'])}
        result['checks'] = checks
        result['observation_verified'] = all(checks.values())
        if result['observation_verified']:
            names = [row['native_name'] for row in first['module_inventory']['modules']]
            contains = sorted({name for name in names if 'Contain' in name})
            result['observed_native_module_names'] = names
            result['facts'] = {
                'weapon_set_update_module_present': 'WeaponSetUpdate' in names,
                'contain_module_names': contains,
                'known_firing_contain_names_present': sorted(set(names) & FIRING_CONTAIN_NAMES),
                'no_contain_names_except_capture': set(contains) <= CAPTURE_ONLY_CONTAINS,
                'configured_weapon_absence_proven_by_entry_matrix': False,
                'passenger_count_read_or_proven_zero': False,
            }
    except Exception as error:
        result['error'] = str(error)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--session', type=Path, default=BRIDGE / 'acceptance/active-session.json')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--troop-controls', type=int, default=6)
    args = ap.parse_args()
    if not 1 <= args.troop_controls <= 32:
        ap.error('--troop-controls must be 1..32')
    # Import the established reader only in the explicitly invoked CLI.
    sys.path[:0] = [str(BRIDGE / 'production'), str(BRIDGE / 'integration')]
    from observe_production import Memory
    from own_candidates import own_candidates, load_catalog
    from session_package import verify_session_package
    report = {'schema_version': 1, 'status': 'unknown', 'mutations': False,
              'sdk_calls': 0, 'game_functions_executed': 0, 'player_id': 3,
              'scope': 'own_only_no_enemy_xyz_hp_or_module_reads', 'units': [],
              'exclusion_granted': False, 'classification': 'unknown_keep_threat',
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    memory = None
    try:
        session_raw = args.session.read_bytes()
        session = json.loads(session_raw.decode('utf-8-sig'))
        if session['mod_sha256'] != PACKAGE:
            raise ValueError('unsupported_exact_package')
        package = verify_session_package(session)
        report.update(session_id=session['session_id'], pid=session['pid'],
                      session_sha256=hashlib.sha256(session_raw).hexdigest(),
                      package_sha256=PACKAGE, executable_sha256=EXE)
        memory = Memory(session['pid'], session)
        report['process_start_timestamp'] = memory.start_timestamp
        logic = memory.u32(0xcd8ce4)
        if not pointer(logic) or memory.u32(logic) != 0xbeb630:
            raise ValueError('invalid_game_logic')
        report.update(frame_start=memory.u32(logic + 0x50), paused_start=memory.u32(logic + 0x15c))
        if report['frame_start'] == 0:
            raise ValueError('frame_zero_not_live_inventory_evidence')
        # Check the exact already-audited read paths before traversing layouts.
        for address, code in {
            0x775a11: '8bbe100300008b0785c0',
            0x775900: 'b8705ac400c3',
            0x6dbe80: '8b411483f8057409',
            0x6f88e0: '8b81940000008b4c24048b0488c20400',
        }.items():
            if memory.read(address, len(bytes.fromhex(code))) != bytes.fromhex(code):
                raise ValueError('native_layout_signature_mismatch_' + hex(address))
        own = own_candidates(memory, 3, load_catalog())
        troop_count = 0
        for unit in own['candidates']:
            h = int(unit['type_hash'], 0)
            if h in EXACT:
                role = 'exact_four_structure'
            elif unit['catalog'].get('cls') == 5:
                role = 'other_owned_structure_control'
            elif unit['catalog'].get('cls') == 1 and troop_count < args.troop_controls:
                role = 'armed_troop_candidate_control'
                troop_count += 1
            else:
                continue
            row = sample_unit(memory, int(unit['address'], 0), int(unit['owner_address'], 0),
                              unit['object_id'], h, logic)
            row.update(role=role, catalog=unit['catalog'], candidate_identity=unit)
            report['units'].append(row)
        report.update(frame_end=memory.u32(logic + 0x50), paused_end=memory.u32(logic + 0x15c),
                      logic_stable=memory.u32(0xcd8ce4) == logic,
                      session_stable=args.session.read_bytes() == session_raw,
                      package_stable=hashlib.sha256(package.read_bytes()).hexdigest() == PACKAGE)
        stable = (report['frame_start'] == report['frame_end'] and report['logic_stable']
                  and report['session_stable'] and report['package_stable'])
        report['group_same_frame_stable'] = stable
        report['status'] = ('same_frame_own_inventory_observation' if stable and report['units']
                            and all(r['observation_verified'] for r in report['units'])
                            else 'unknown_incomplete_or_unstable')
        verified = [r for r in report['units'] if r['observation_verified'] and stable]
        covered = {int(r['first']['identity']['type_hash'], 0) for r in verified}
        report['exact_types_missing_verified_sample'] = [name for h, name in EXACT.items() if h not in covered]
        armed_structures = [r for r in verified if r['role'] == 'other_owned_structure_control'
                            and r['facts']['weapon_set_update_module_present']
                            and r['first']['weapon_matrix']['matrix_complete']
                            and any(m.get('asset_id') for slot in r['first']['weapon_matrix']['slots']
                                    for m in slot['modes'])]
        garrisons = [r for r in verified if r['role'] == 'other_owned_structure_control'
                     and r['facts']['known_firing_contain_names_present']]
        report['control_coverage'] = {
            'armed_structure_observed': bool(armed_structures),
            'firing_contain_structure_observed': bool(garrisons),
            'missing_controls_are_research_gaps_not_absence_proof': True,
        }
    except Exception as error:
        report['error'] = str(error)
    finally:
        if memory is not None:
            memory.close()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'report': str(args.output.resolve()), 'status': report['status'],
                      'frame_start': report.get('frame_start'), 'frame_end': report.get('frame_end'),
                      'units': len(report['units']), 'error': report.get('error'),
                      'classification': report['classification']}, ensure_ascii=False))
    return 0 if report['status'] == 'same_frame_own_inventory_observation' else 2


if __name__ == '__main__':
    raise SystemExit(main())
