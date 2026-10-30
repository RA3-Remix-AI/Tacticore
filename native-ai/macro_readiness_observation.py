"""Signature-pinned, read-only own readiness facts; unknowns never grant access.

No process-opening, engine-call, ctypes, model or filesystem work occurs on
import. The caller supplies an already session-pinned read(address, size).
Power, ObjectStatus and selected producer blockers have static native meaning.
Completion, operational readiness and technology permissions remain separate.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

EXE_SHA256 = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PLAYER_VTABLE = 0xc5bce0
ENERGY_VTABLE = 0xc5bb94
THING_VTABLE = 0xc4db60
UNPACK_VTABLE = 0xc2c9a0
PRODUCTION_INTERFACE_VTABLE = 0xc3f8c8
GAME_GLOBAL = 0xcd8ce4

# Exact-byte anchors from the reviewed executable, never executed here.
PINS = {
    0x7274c0: '5356578b7c24108bc18bcf83e11f807c241400',  # indexed ObjectStatus setter
    0x7274e1: '85b488800000000f94c309b48880000000',      # Thing + 0x80 status OR
    0x727500: '8594b080000000f7d20f95c32194b080000000',  # corresponding clear
    0x727542: '8dab80000000b9070000008bf58d7c2410f3a5',  # seven status words
    0x4d7133: 'c1ea052384966c0200005ef7d81bc0f7d8c2',  # disabled flags Thing+26c
    0x857dac: 'c706e0bcc500',                          # Player constructor identity
    0x857e4f: 'c70094bbc500',                          # Energy constructor identity
    0x857e75: '8d8ea8000000894674895e78',               # Player+74 owns Energy
    0x850488: '8b54813089571c',                        # Energy+1c Player back link
    0x83b0a0: '8d41203900750e8b41043b41087c06b801000000c333c0c3',  # native sufficient
    0x84c713: '50e897c9ffffc20800807c2408007402f7d850e8d5c9ffff',
    0x84c745: '8bb28c0000006a00',                     # signed template energy input
    0x84c771: '85f67d0ff7de568bcfe881c9ffff5e5fc204007e08568bcfe822c9ffff',
    0x845344: '38860c010000',                          # compare Player low power
    0x845373: '888e0c010000',                          # write Player low power
    0x6f6b94: 'c706a0c9c200c7460c70c8c200',            # StructureUnpack module
    0x6f6bb6: '894e30c7463401000000894e38894e3c894e40884e44884e45',
    0x6dd952: '8bb1100300008b0e33db85c9',              # Thing module vector
    0x6dd965: '8b018b5010ffd23bc774128b4e0483c60485c975eb',
    0x6f6e80: '5180794400747ea1e48ccd008b5140568b70508bc62b413c80794500578b7938',
    0x7752f5: '68a20000008bcee8dff1d5ff6a028bcee8d6f1d5ff',  # native unpack ends statuses
    0x775397: '0f57c0c6473400',                        # module+10 interface, clear +44
    0x6f48f3: '80bb1001000000',                        # producer stop gate
    0x6f4903: '8b8894000000c1e902f6c1010f85c3000000',  # producer unpack blocker
    0x6da700: '8b41e08b491c3b48081bc083c001c3',         # native full-queue getter
    0x504e1d: '8b79088bc6f7f7',                        # authoritative Thing-ID registry
    0x504e35: '8b4008',
    0x6f6fb2: '8b497485c9f30f',                        # unpack time uses Player energy
    0xbdf9b8: '6864bd0006000000',                      # native DisabledType UNDERPOWERED=6
    0xbdf9d8: '4064bd000a000000',                      # SCRIPT_UNDERPOWERED=10
    0x7c1e41: '889d00030000889d01030000',              # Thing construction initializes +301=false
    0x77531d: 'e8ae3efaff8bcee8575ff8ff',              # unpack callback -> energy refresh -> completion notify
    0x6fb2c0: '8a8671040000a820c686010300000175178b8e180400008b49740c2056888671040000e8481415005f5e',
    0x71926f: 'f6c101740980b80103000000741cf6807104000001751384d274',
    0x71929b: '8a88710400008ad9c0eb0580e3015e3ada5b742a84d250741580c9208888710400008bcfe86c3413005f59c2040080e1df8888710400008bcfe8c73413005f59c2',
    0x84c7a0: '8b44240485c074268b40048b50148b828c00000085c07d09',  # unregister template energy
}

# Confirmed in the engine's own name/value table, not guessed XSD ordinals.
STATUS_BITS = {
    'destroyed': (0, 0xbe1168, 0xbdb85c, 'DESTROYED'),
    'under_construction': (2, 0xbe1178, 0xbdc274, 'UNDER_CONSTRUCTION'),
    'sold': (21, 0xbe1210, 0xbda52c, 'SOLD'),
    'reconstructing': (23, 0xbe1220, 0xbdbfc8, 'RECONSTRUCTING'),
    'not_in_world': (55, 0xbe1320, 0xbdbdd8, 'NOT_IN_WORLD'),
    'pending_construction': (90, 0xbe1438, 0xbdbef8, 'PENDING_CONSTRUCTION'),
    'user_powered_down': (107, 0xbe14c0, 0xbdc2f8, 'USER_POWERED_DOWN'),
    'powered_down_emp': (141, 0xbe15d0, 0xbdbf94, 'POWERED_DOWN_EMP'),
    'unpacking': (162, 0xbe1678, 0xbda954, 'UNPACKING'),
}

TEMPLATES = {
    0xc16ff13f: 'construction_yard', 0xcf8d9f20: 'power_plant',
    0x80d4ea1e: 'barracks', 0xd50c222e: 'war_factory',
    0xc45aaeab: 'refinery', 0x524bbd01: 'super_reactor',
    0xb7377639: 'battle_lab', 0x60f0b4e9: 'sickle', 0x522bcb61: 'bullfrog',
}


def _pointer(value, size=4):
    if type(value) is not int or value % 4 or not 0x10000 <= value <= 0x100000000 - size:
        raise ValueError('readiness_pointer_bounds')
    return value


def _read(read, address, size):
    if type(size) is not int or not 1 <= size <= 0x2000:
        raise ValueError('readiness_read_bounds')
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('readiness_short_read')
    return raw


def _word(read, address):
    return struct.unpack('<I', _read(read, address, 4))[0]


def verify_pins(read, executable_sha256):
    if executable_sha256 != EXE_SHA256:
        raise ValueError('readiness_exact_executable_required')
    for address, expected in PINS.items():
        raw = bytes.fromhex(expected)
        if _read(read, address, len(raw)) != raw:
            raise ValueError('readiness_signature_changed')
    for index, entry, name_pointer, name in STATUS_BITS.values():
        if _read(read, entry, 8) != struct.pack('<II', name_pointer, index):
            raise ValueError('readiness_status_enum_changed')
        if _read(read, name_pointer, len(name) + 1) != name.encode() + b'\0':
            raise ValueError('readiness_status_name_changed')


def registry_lookup(read, game, ident):
    """Copy the reviewed integer lookup; never call the game or scan its heap."""
    if type(ident) is not int or not 0 < ident <= 0xffffffff:
        raise ValueError('readiness_thing_id')
    table = _pointer(game + 0xbc, 12)
    header = _read(read, table + 4, 8); buckets, count = struct.unpack('<II', header)
    if not 1 <= count <= 65536:
        raise ValueError('readiness_registry_bounds')
    _pointer(buckets, 4 * (count + 1))
    slot = buckets + 4 * (ident % count)
    first = _read(read, slot, 4); sentinel = _read(read, buckets + 4 * count, 4)
    at = struct.unpack('<I', first)[0]; end = struct.unpack('<I', sentinel)[0]
    seen = set(); copies = []; result = 0
    while at and at != end:
        _pointer(at, 12)
        if at in seen or len(seen) >= 128:
            raise ValueError('readiness_registry_cycle')
        seen.add(at); raw = _read(read, at, 12)
        key, value, following = struct.unpack('<III', raw)
        if key % count != ident % count:
            raise ValueError('readiness_registry_bucket')
        copies.append((at, raw))
        if key == ident:
            result = _pointer(value); break
        at = following
    if (_read(read, table + 4, 8) != header or _read(read, slot, 4) != first
            or _read(read, buckets + 4 * count, 4) != sentinel
            or any(_read(read, p, 12) != raw for p, raw in copies)):
        raise ValueError('readiness_registry_changed')
    return result


def observe_power(read, owner):
    """Mirror 0x83b0a0; scalar balance and forced-outage list are separate."""
    _pointer(owner, 0x110)
    if _word(read, owner) != PLAYER_VTABLE:
        raise ValueError('readiness_player_signature')
    energy = _pointer(_word(read, owner + 0x74), 0x2c)
    raw = _read(read, energy, 0x2c)
    if struct.unpack_from('<I', raw)[0] != ENERGY_VTABLE or struct.unpack_from('<I', raw, 0x1c)[0] != owner:
        raise ValueError('readiness_energy_owner')
    supply, demand = struct.unpack_from('<ii', raw, 4)
    if not 0 <= supply <= 10000000 or not 0 <= demand <= 10000000:
        raise ValueError('readiness_energy_bounds')
    first, last = struct.unpack_from('<II', raw, 0x20)
    head = energy + 0x20
    _pointer(first); _pointer(last)
    if (first == head) != (last == head):
        raise ValueError('readiness_energy_list')
    low = _read(read, owner + 0x10c, 1)[0]
    if low not in (0, 1):
        raise ValueError('readiness_low_power_boolean')
    sufficient = first == head and supply >= demand
    if (_word(read, owner + 0x74) != energy or _read(read, energy, 0x2c) != raw
            or _read(read, owner + 0x10c, 1)[0] != low):
        raise ValueError('readiness_energy_changed')
    return dict(native_supply=supply, native_demand=demand, native_surplus=supply - demand,
        native_outage_list_empty=first == head, native_energy_sufficient=sufficient,
        native_reported_low_power=bool(low), reported_state_agrees=bool(low) == (not sufficient),
        source='native_energy_getter_mirror', per_facility_operational_verified=False,
        actual_payment_verified=False, field_verified=False, grants_capability=False)


def _unpack_module(read, thing, frame):
    array = _word(read, thing + 0x310)
    if not array:
        return dict(module_present=False, native_unpack_in_progress=None,
            native_unpack_end_state_candidate=None, construction_completed=None)
    _pointer(array, 4)
    copies = []; found = []; slots = []
    for i in range(256):
        slot = array + 4 * i; value = _word(read, slot); slots.append((slot, value))
        if not value:
            break
        _pointer(value, 0x46)
        if _word(read, value + 8) != thing:
            raise ValueError('readiness_module_owner')
        if _word(read, value) != UNPACK_VTABLE:
            continue
        raw = _read(read, value, 0x46); copies.append((value, raw))
        duration, started, paused_at = struct.unpack_from('<III', raw, 0x38)
        active, paused = raw[0x44], raw[0x45]
        if active not in (0, 1) or paused not in (0, 1):
            raise ValueError('readiness_unpack_boolean')
        if duration > 15 * 3600 or started > frame or paused and paused_at > frame:
            raise ValueError('readiness_unpack_time')
        if active and duration == 0:
            raise ValueError('readiness_unpack_duration_unknown')
        elapsed = max(0, frame - started - (frame - paused_at if paused else 0))
        ratio = min(1.0, elapsed / duration) if active and duration else None
        found.append(dict(module_present=True, native_unpack_in_progress=bool(active),
            native_unpack_paused=bool(paused), native_unpack_duration_frames=duration,
            native_unpack_started_frame=started, native_unpack_pause_frame=paused_at,
            native_unpack_progress_ratio=ratio,
            native_unpack_end_state_candidate=not active and duration > 0 and started > 0 and elapsed >= duration,
            construction_completed=None))
    else:
        raise ValueError('readiness_module_vector_unterminated')
    if len(found) > 1:
        raise ValueError('readiness_duplicate_unpack_module')
    if (_word(read, thing + 0x310) != array or any(_word(read, p) != v for p, v in slots)
            or any(_read(read, p, 0x46) != raw for p, raw in copies)):
        raise ValueError('readiness_unpack_changed')
    return found[0] if found else dict(module_present=False, native_unpack_in_progress=None,
        native_unpack_end_state_candidate=None, construction_completed=None)


def _producer_blockers(read, thing, statuses):
    wrapper = _word(read, thing + 0x3b4)
    if not wrapper:
        return dict(production_interface_present=False, production_permitted=None, technology_unlocked=None)
    _pointer(wrapper, 0x18); interface = _word(read, wrapper + 0x14)
    if not interface:
        return dict(production_interface_present=False, production_permitted=None, technology_unlocked=None)
    _pointer(interface - 0x24, 0x138)
    if (_word(read, interface) != PRODUCTION_INTERFACE_VTABLE
            or _word(read, interface - 0x1c) != thing):
        return dict(production_interface_present=True, known_interface=False,
            production_permitted=None, technology_unlocked=None)
    definition = _pointer(_word(read, interface - 0x20), 12)
    capacity = _word(read, definition + 8); occupied = _word(read, interface + 0x1c)
    stopped = _read(read, interface + 0x110, 1)[0]
    if stopped not in (0, 1) or capacity > 1024 or occupied > 1024:
        raise ValueError('readiness_production_bounds')
    blockers = []
    if stopped: blockers.append('native_production_stop_flag')
    if statuses['unpacking']: blockers.append('native_structure_unpacking')
    if occupied >= capacity: blockers.append('native_queue_full')
    if (_word(read, thing + 0x3b4) != wrapper or _word(read, wrapper + 0x14) != interface
            or _word(read, interface - 0x1c) != thing or _word(read, interface - 0x20) != definition
            or _word(read, definition + 8) != capacity or _word(read, interface + 0x1c) != occupied
            or _read(read, interface + 0x110, 1)[0] != stopped):
        raise ValueError('readiness_production_changed')
    return dict(production_interface_present=True, known_interface=True,
        native_queue_capacity=capacity, native_queue_occupied=occupied,
        known_production_blockers=blockers, production_permitted=False if blockers else None,
        technology_unlocked=None, all_native_admission_checks_mirrored=False)


def observe_own_object(read, game, owner, ident, frame):
    thing = registry_lookup(read, game, ident)
    if not thing:
        return dict(thing_id=ident, currently_registered=False, construction_completed=None,
            operational=None, production_permitted=None, technology_unlocked=None)
    if _word(read, thing) != THING_VTABLE:
        raise ValueError('readiness_thing_signature')
    # Ownership precedes enemy template, health, status, or module access.
    if _word(read, thing + 0x418) != owner:
        raise ValueError('readiness_foreign_thing')
    if _word(read, thing + 0xdc) != ident:
        raise ValueError('readiness_thing_identity')
    template = _pointer(_word(read, thing + 4), 12)
    template_hash = _word(read, template + 8)
    if template_hash not in TEMPLATES:
        return dict(thing_id=ident, currently_registered=True, named_template_supported=False,
            construction_completed=None, operational=None, production_permitted=None, technology_unlocked=None)
    raw = _read(read, thing + 0x80, 28)
    words = struct.unpack('<7I', raw)
    statuses = {name: bool(words[index // 32] & (1 << (index % 32)))
        for name, (index, *_rest) in STATUS_BITS.items()}
    disabled_raw = _read(read, thing + 0x26c, 4); disabled = struct.unpack('<I', disabled_raw)[0]
    notified_raw = _read(read, thing + 0x301, 1)
    if notified_raw[0] not in (0, 1):
        raise ValueError('readiness_completion_notification_boolean')
    energy_flags_raw = _read(read, thing + 0x471, 1)
    body = _pointer(_word(read, thing + 0x33c), 8)
    hp_raw = _read(read, body + 4, 4); hp = struct.unpack('<f', hp_raw)[0]
    if not math.isfinite(hp) or not 0 <= hp <= 1e9:
        raise ValueError('readiness_own_health')
    unpack = _unpack_module(read, thing, frame)
    producer = _producer_blockers(read, thing, statuses)
    blockers = [name for name in ('destroyed', 'under_construction', 'sold', 'reconstructing',
        'not_in_world', 'pending_construction', 'user_powered_down', 'powered_down_emp', 'unpacking') if statuses[name]]
    if disabled: blockers.append('native_disabled')
    if hp <= 0: blockers.append('not_alive')
    if (registry_lookup(read, game, ident) != thing or _word(read, thing + 0x418) != owner
            or _word(read, thing + 0xdc) != ident or _word(read, thing + 4) != template
            or _word(read, template + 8) != template_hash or _read(read, thing + 0x80, 28) != raw
            or _read(read, thing + 0x26c, 4) != disabled_raw or _word(read, thing + 0x33c) != body
            or _read(read, thing + 0x301, 1) != notified_raw
            or _read(read, thing + 0x471, 1) != energy_flags_raw
            or _read(read, body + 4, 4) != hp_raw):
        raise ValueError('readiness_own_object_changed')
    return dict(thing_id=ident, currently_registered=True, named_template_supported=True,
        template=TEMPLATES[template_hash], type_hash=hex(template_hash), hp=hp,
        object_status=statuses, native_disabled_any=bool(disabled),
        native_unpack_completion_notified=bool(notified_raw[0]),
        native_template_energy_registered=bool(energy_flags_raw[0] & 0x20),
        native_underpowered=bool(disabled & (1 << 6)), native_script_underpowered=bool(disabled & (1 << 10)),
        unknown_disabled_bits=bool(disabled & ~0xfff), known_operational_blockers=blockers,
        construction_completed=False if statuses['under_construction'] or statuses['pending_construction'] or statuses['unpacking'] else None,
        operational=False if blockers else None, unpack=unpack, producer=producer,
        production_permitted=producer['production_permitted'], technology_unlocked=None,
        payment_verified=False, grants_capability=False, field_verified=False)


class ReadinessObserver:
    def __init__(self, read, owner, *, executable_sha256, expected_owner_index):
        verify_pins(read, executable_sha256)
        self.read = read; self.owner = _pointer(owner, 0x110)
        if type(expected_owner_index) is not int or not 0 <= expected_owner_index < 16:
            raise ValueError('readiness_owner_index')
        self.owner_index = expected_owner_index
        self.game = _pointer(_word(read, GAME_GLOBAL), 0xc8)
        self._identity()

    def _identity(self):
        if (_word(self.read, self.owner) != PLAYER_VTABLE
                or _word(self.read, self.owner + 0x20) != self.owner_index
                or _word(self.read, GAME_GLOBAL) != self.game):
            raise ValueError('readiness_session_changed')

    def sample(self, own_thing_ids):
        if (type(own_thing_ids) is not list or len(own_thing_ids) > 128
                or any(type(i) is not int or not 0 < i <= 0xffffffff for i in own_thing_ids)
                or len(set(own_thing_ids)) != len(own_thing_ids)):
            raise ValueError('readiness_input_bounds')
        self._identity(); frame = _word(self.read, self.game + 0x50)
        if not frame:
            raise ValueError('readiness_game_not_running')
        power = observe_power(self.read, self.owner)
        objects = [observe_own_object(self.read, self.game, self.owner, i, frame) for i in own_thing_ids]
        self._identity()
        if not 0 <= _word(self.read, self.game + 0x50) - frame <= 2:
            raise ValueError('readiness_frame_changed')
        return dict(schema_version=1, kind='native_own_readiness_observation', frame=frame,
            power=power, own_objects=objects, own_perspective=True, enemy_details_read=False,
            native_calls=0, process_writes=0, field_verified=False, grants_capability=False,
            construction_completion_verified=False, operational_readiness_verified=False,
            production_permission_verified=False, technology_unlock_verified=False,
            coverage='named_soviet_templates_only')


def audit_executable(path):
    """Offline PE byte/enum audit. It does not open a process or call native code."""
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXE_SHA256:
        raise ValueError('readiness_exact_executable_required')
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    base = struct.unpack_from('<I', raw, pe + 52)[0]
    section = pe + 24 + struct.unpack_from('<H', raw, pe + 20)[0]
    count = struct.unpack_from('<H', raw, pe + 6)[0]
    sections = [struct.unpack_from('<IIII', raw, section + i * 40 + 8) for i in range(count)]
    def read(address, size):
        for virtual_size, virtual_address, file_size, offset in sections:
            relative = address - base - virtual_address
            if 0 <= relative and relative + size <= min(virtual_size, file_size):
                return raw[offset + relative:offset + relative + size]
        raise ValueError('readiness_pe_unbacked_range')
    verify_pins(read, digest)
    return dict(schema_version=1, kind='native_readiness_static_audit', executable_sha256=digest,
        observer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        byte_checks=[dict(address=hex(at), bytes=value) for at, value in PINS.items()],
        status_enums={name: dict(index=index, table_address=hex(entry), native_name=label)
            for name, (index, entry, _pointer_value, label) in STATUS_BITS.items()},
        native_processes_opened=0, native_calls=0, process_writes=0,
        field_verified=False, capability_granted=False,
        completion_operational_and_unlock_claims=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit-executable', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); result = audit_executable(a.audit_executable)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(dict(output=str(a.output), byte_checks=len(PINS), field_verified=False, capability_granted=False)))


if __name__ == '__main__': main()
