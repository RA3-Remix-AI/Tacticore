"""Explicit readiness v2: mobile unit presence does not imply a producer wrapper.

The original observer and historical evidence remain unchanged. Named Sickle
and Bullfrog units retain unknown production permission; their +0x3b4 field
is never interpreted as the building producer wrapper. All original ownership,
status, module, health, identity and stability checks remain in force.
"""
import math
import struct
import macro_readiness_observation as baseline
from macro_readiness_observation import (TEMPLATES, STATUS_BITS, THING_VTABLE,
    _word, _read, _pointer, _unpack_module, registry_lookup, observe_power)

MOBILE_UNIT_TEMPLATES=frozenset((0x60f0b4e9,0x522bcb61))


def _producer_for_template(read,thing,statuses,template_hash):
    if template_hash in MOBILE_UNIT_TEMPLATES:
        return dict(production_interface_present=None,production_permitted=None,
            technology_unlocked=None,known_interface=False,
            reason_code='mobile_unit_producer_interface_unqualified')
    return baseline._producer_blockers(read,thing,statuses)


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
    producer = _producer_for_template(read, thing, statuses, template_hash)
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


class ReadinessObserverV2(baseline.ReadinessObserver):
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
        return dict(schema_version=2, kind='native_own_readiness_observation', frame=frame,
            power=power, own_objects=objects, own_perspective=True, enemy_details_read=False,
            native_calls=0, process_writes=0, field_verified=False, grants_capability=False,
            construction_completion_verified=False, operational_readiness_verified=False,
            production_permission_verified=False, technology_unlock_verified=False,
            coverage='named_soviet_templates_only')
