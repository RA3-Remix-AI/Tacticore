"""Mirror the native RequiredObject subpredicate; do not call the engine.

This independent extension leaves the frozen readiness observer unchanged.
Positive prerequisite facts are deliberately narrower than production permission.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import macro_readiness_observation as readiness

EXE_SHA256 = readiness.EXE_SHA256
TEMPLATE_FACTORY_GLOBAL = 0xce6c58
DEPENDENCY_VTABLE = 0xbe8ffc
PINS = {
    0x7e4234: '8d71288d442410508d4c2408518bcee8c80bd2ff',
    0x7ed58d: '399e940100005f74266a08e80394c2ff83c4043bc374108b8e94010000518bc8e82e7dceffeb0233c0898518030000',
    0x4d52e0: '8bc18b4c2404c700fc8fbe00894804c20400',
    0x4d7d70: '8b410483ec0885c053555657740b8b480c8b50108d2c8aeb0233ed85c074058b4010eb0233c03bc58bf0b30174498b7c241c8b068b0d586cce0050e880c43000807f08008d5424100f94c152884c24168b0f50885c2418885c2419885c241b885c241c885c241de86439360084c07413',
    0x83b741: '8b8164120000558ba9601200003be856578944240c0f84bd0000008b',
    0x83b778: '803f00740df68671040000010f8582000000807f0100740e8b8e80000000c1e902f6c101756e',
    0x83b79e: '807f0200740e8b968c000000c1ea0bf6c201755a807f0300741f8b46048b88d0000000c1e915f6c101740e8b9694000000c1ea02f6c2017535',
    0x83b7d7: '807f0500740d8b866c020000c1e802a8017522807f0400740e8b8e84000000c1e917f6c101750e8b9690000000c1ea11f6c201741683c5',
    0x7e43f9: '8b55083bd1535657894c2414750bb0015f5e5b8be55dc20400',
    0x7e441a: '8b411483b8bc0100000074628bb0c00100008b88bc0100008bc68d1c883b',
    0x7e4488: '8b4a1483b9bc0100000074668bc18bb0c00100008b90bc0100008bc68d1c',
    0x6f4bba: '75498b4e1085c9745a83b918030000007451807e4e00754b8b46048b40088b90180400008944240c8d44240889542408c6442410008b891803000050e815e0deff83f806',
    0x4db800: '83ec08568b710485f60f84170100008b562485d20f840c0100008b420483f801742883f802742333c08d4a108d642400833900751583c00183c10483f80972f0837a60000f84dc000000',
    0x6f48f0: '538bd980bb10010000000f85d80000008b43e48b8894000000c1e902f6c1010f85c3000000558b6c240c8b95e0000000c1ea0af6c201565774408b88180400008b91181300003b91141300007d6d8bb8100300008b0785c074208d9b000000008d480c8b018b5044ffd28bf085f675268b470483c70485c075e68b138b82880000008bcbffd084c0743d5f5e5db8040000005bc204008b068b10558bceffd284c074d78b43e48b80180400008b16508b4208558bceffd084c075bf5f5e5db8050000005bc204008b4be48b81180400005550e8794de5ff83c408f6d85f5e5d5b1bc083e006c20400b8030000005bc20400',
    0x549748: '85ff74158b44241485c0740d8b48146683b94202000000750732c05f83c408c3',
    0x6da6b0: '8b41e08b4030c3',
    0x7df7a0: '8b41148b8030010000c3',
    0xc3f8c8: 'f0486f00301e7700',
    0xc3f950: '00a76d00',
    0xc3f974: 'b0a66d00',
    0xbe15f0: '8464bd0091000000',  # USER_PARALYZED=145
    0xbdf998: '0064bd0002000000',  # DisabledType EMP=2
    0xbdfe90: 'b86dbd0095000000',  # KindOf ACTIVATE_AFTER_UNPACK=149
    0xbe0238: 'ec78bd000a010000',  # KindOf LIMITED_PRODUCTION_AIRCRAFT=266
}
NATIVE_NAMES = {0xbd6484: 'USER_PARALYZED', 0xbd6400: 'EMP',
    0xbd6db8: 'ACTIVATE_AFTER_UNPACK', 0xbd78ec: 'LIMITED_PRODUCTION_AIRCRAFT'}

# Expected SDK prerequisites are cross-checked against the native definition,
# never substituted for it. CommandSet qualification is a different fact.
ACTIONS = {
    'buildpower': (0xcf8d9f20, ()),
    'buildbarracks': (0x80d4ea1e, ()),
    'buildfactory': (0xd50c222e, (0xc45aaeab,)),
    'buildrefinery': (0xc45aaeab, (0xcf8d9f20,)),
    'buildbattlelab': (0xb7377639, (0x524bbd01,)),
    'producesickle': (0x60f0b4e9, ()),
    'producebullfrog': (0x522bcb61, ()),
    'buildreactor': (0x524bbd01, (0xc45aaeab,)),
}


def verify_pins(read, executable_sha256):
    readiness.verify_pins(read, executable_sha256)
    for address, expected in PINS.items():
        raw = bytes.fromhex(expected)
        if readiness._read(read, address, len(raw)) != raw:
            raise ValueError('dependency_signature_changed')
    for address, name in NATIVE_NAMES.items():
        if readiness._read(read, address, len(name) + 1) != name.encode() + b'\0':
            raise ValueError('dependency_native_enum_name_changed')


class StableRead:
    """Bound a sample and recheck every consulted byte range before publishing."""
    def __init__(self, read): self.read = read; self.copies = {}
    def __call__(self, address, size):
        raw = readiness._read(self.read, address, size)
        key = (address, size)
        if key in self.copies and self.copies[key] != raw:
            raise ValueError('dependency_sample_changed')
        if len(self.copies) >= 16000:
            raise ValueError('dependency_sample_read_bound')
        self.copies[key] = raw
        return raw
    def finish(self):
        if any(readiness._read(self.read, at, size) != raw for (at, size), raw in self.copies.items()):
            raise ValueError('dependency_sample_changed')


def _word(read, at): return readiness._word(read, at)
def _ptr(value, size=4): return readiness._pointer(value, size)


def _lookup(read, table, key):
    """The same integer hash lookup used by native 0x7e4230/0x504e10."""
    buckets, count = struct.unpack('<II', read(table + 4, 8))
    if not 1 <= count <= 65536: raise ValueError('dependency_template_table_bounds')
    _ptr(buckets, 4 * (count + 1))
    at = _word(read, buckets + 4 * (key % count)); end = _word(read, buckets + 4 * count)
    seen = set()
    while at and at != end:
        _ptr(at, 12)
        if at in seen or len(seen) >= 128: raise ValueError('dependency_template_chain_cycle')
        seen.add(at)
        found, value, at = struct.unpack('<III', read(at, 12))
        if found % count != key % count: raise ValueError('dependency_template_bucket')
        if found == key: return _ptr(value, 0x31c)
    return 0


class DependencyObserver:
    def __init__(self, read, owner, *, executable_sha256, expected_owner_index):
        verify_pins(read, executable_sha256)
        self.base = readiness.ReadinessObserver(read, owner,
            executable_sha256=executable_sha256, expected_owner_index=expected_owner_index)
        self.read = read; self.owner = self.base.owner
        self.factory = _ptr(_word(read, TEMPLATE_FACTORY_GLOBAL), 0x34)

    def _template(self, read, key):
        template = _lookup(read, self.factory + 0x28, key)
        if template and _word(read, template + 8) != key:
            raise ValueError('dependency_template_identity')
        return template

    def _equivalent(self, read, left, right):
        # Mirror both equivalence lists from 0x7e43f0; this is not inheritance.
        if left == right: return True
        for source, target in ((left, right), (right, left)):
            definition = _ptr(_word(read, source + 0x14), 0x1c4)
            count, array = struct.unpack('<II', read(definition + 0x1bc, 8))
            if count > 64: raise ValueError('dependency_equivalence_bounds')
            if count:
                raw = read(_ptr(array, 4 * count), 4 * count)
                if any(self._template(read, key) == target for key in struct.unpack('<' + 'I' * count, raw)):
                    return True
        return False

    def _owned(self, read):
        start, end = struct.unpack('<II', read(self.owner + 0x1260, 8))
        if end < start or (end-start) % 4 or end-start > 4096 or bool(start) != bool(end):
            raise ValueError('dependency_own_vector_bounds')
        if not start: return []
        raw = read(_ptr(start, max(4, end-start)), end-start) if end > start else b''
        addresses = struct.unpack('<' + 'I' * ((end-start)//4), raw) if raw else ()
        if len(set(addresses)) != len(addresses): raise ValueError('dependency_duplicate_own_object')
        rows = []
        for thing in addresses:
            _ptr(thing, 0x474)
            if _word(read, thing) != readiness.THING_VTABLE: raise ValueError('dependency_thing_signature')
            if _word(read, thing + 0x418) != self.owner: raise ValueError('dependency_foreign_thing')
            ident = _word(read, thing + 0xdc)
            if readiness.registry_lookup(read, self.base.game, ident) != thing:
                raise ValueError('dependency_own_registry_link')
            template = _ptr(_word(read, thing + 4), 0x31c)
            rows.append((thing, ident, template))
        return rows

    def _required_object(self, read, target, owned):
        witnesses = []; excluded = []
        for thing, ident, template in owned:
            if not self._equivalent(read, template, target): continue
            words = struct.unpack('<7I', read(thing + 0x80, 28))
            has = lambda index: bool(words[index//32] & (1 << (index%32)))
            flags = read(thing + 0x471, 1)[0]
            disabled = _word(read, thing + 0x26c)
            activate_after_unpack = bool(_word(read, template + 0xd0) & (1 << 21))
            blockers = []
            if flags & 1: blockers.append('native_exclusion_flag_471_bit0')
            for name, index in [('under_construction', 2), ('user_powered_down', 107),
                    ('not_in_world', 55), ('user_paralyzed', 145)]:
                if has(index): blockers.append(name)
            if activate_after_unpack and has(162): blockers.append('activate_after_unpack_still_unpacking')
            if disabled & (1 << 2): blockers.append('native_emp_disabled')
            row = dict(thing_id=ident, thing_address=hex(thing), template_address=hex(template),
                type_hash=hex(_word(read, template + 8)), blockers=blockers,
                native_required_object_eligible=not blockers,
                underpowered=bool(disabled & (1 << 6)),
                native_template_energy_registered=bool(flags & 0x20))
            (excluded if blockers else witnesses).append(row)
        return dict(required_type_hash=hex(_word(read, target + 8)),
            native_required_object_met=bool(witnesses), witnesses=witnesses, excluded=excluded,
            predicate='0x4d7d70_context_flag8_false_to_0x83b740')

    def _dependency(self, read, action, owned):
        target_hash, expected = ACTIONS[action]
        template = self._template(read, target_hash)
        common = dict(action=action, target_type_hash=hex(target_hash),
            overall_production_permitted=None, field_verified=False, grants_capability=False)
        if not template: return dict(common, target_template_loaded=False, prerequisite_met=None)
        definition = _ptr(_word(read, template + 0x14), 0x1c4)
        wrapper = _word(read, template + 0x318)
        compiled = _word(read, definition + 0x194)
        if not wrapper:
            if compiled: raise ValueError('dependency_missing_runtime_wrapper')
            return dict(common, target_template_loaded=True, native_dependency_present=False,
                native_required_objects=[], prerequisite_met=True, native_required_objects_met=True,
                sdk_required_objects_match=not expected, source='native_dependency_absent')
        _ptr(wrapper, 8)
        if _word(read, wrapper) != DEPENDENCY_VTABLE: raise ValueError('dependency_wrapper_signature')
        data = _word(read, wrapper + 4)
        if not data or data != compiled: raise ValueError('dependency_compiled_binding')
        raw = read(_ptr(data, 0x28), 0x28)
        model_any, model_forbidden, status_any, required_count, required_array, forbidden_count, forbidden_array, needed_count, needed_array, filter_ptr = struct.unpack('<10I', raw)
        if max(required_count, forbidden_count, needed_count) > 32: raise ValueError('dependency_definition_bounds')
        required = struct.unpack('<'+'I'*required_count, read(_ptr(required_array, required_count*4), required_count*4)) if required_count else ()
        if len(set(required)) != len(required): raise ValueError('dependency_duplicate_required_type')
        objects = []
        for key in required:
            native_target = self._template(read, key)
            if not native_target: raise ValueError('dependency_required_template_missing')
            objects.append(self._required_object(read, native_target, owned))
        def zero_mask(pointer, count):
            return not pointer or not any(read(_ptr(pointer, count*4), count*4))
        unsupported = []
        if not zero_mask(model_any, 15): unsupported.append('required_model_conditions')
        if not zero_mask(model_forbidden, 15): unsupported.append('forbidden_model_conditions')
        if not zero_mask(status_any, 7): unsupported.append('required_object_status_any')
        if forbidden_count: unsupported.append('forbidden_upgrades')
        if needed_count: unsupported.append('needed_upgrades')
        # Mirror only the native filter's explicit no-op early return. A real
        # filter may scan shared/allied objects and remains outside this scope.
        if filter_ptr:
            filter_raw = read(_ptr(filter_ptr, 0x64), 0x64)
            native_noop = (struct.unpack_from('<I', filter_raw, 4)[0] not in (1, 2)
                and not any(filter_raw[0x10:0x34])
                and struct.unpack_from('<I', filter_raw, 0x60)[0] == 0)
            if not native_noop: unsupported.append('object_filter')
        met = all(row['native_required_object_met'] for row in objects)
        return dict(common, target_template_loaded=True, native_dependency_present=True,
            native_required_objects=[hex(i) for i in required],
            native_required_objects_met=met, required_object_evidence=objects,
            prerequisite_met=False if not met else (None if unsupported else True),
            unsupported_dependency_conditions=unsupported,
            sdk_required_objects_match=tuple(required) == expected,
            source='native_bound_game_dependency_definition')

    def _enqueue_admission(self, read, action, owned):
        target = self._template(read, ACTIONS[action][0])
        if not target: return []
        target_definition = _ptr(_word(read, target + 0x14), 0x244)
        target_category = _word(read, target_definition + 0x130)
        limited_aircraft = bool(_word(read, target + 0xe0) & (1 << 10))
        maximum = struct.unpack('<H', read(target_definition + 0x242, 2))[0]
        expected_producer = 0xd50c222e if action in ('producesickle', 'producebullfrog') else 0xc16ff13f
        result = []
        for thing, ident, template in owned:
            if _word(read, template + 8) != expected_producer: continue
            wrapper = _word(read, thing + 0x3b4)
            if not wrapper: continue
            interface = _word(read, _ptr(wrapper, 0x18) + 0x14)
            if not interface or _word(read, _ptr(interface, 0x114)) != readiness.PRODUCTION_INTERFACE_VTABLE:
                continue
            if _word(read, interface-0x24) != 0xc3fad0 or _word(read, interface-0x1c) != thing:
                raise ValueError('dependency_production_owner')
            definition = _ptr(_word(read, interface-0x20), 0x34)
            category = _word(read, definition+0x30)
            if category != target_category: continue
            capacity, occupied = _word(read, definition+8), _word(read, interface+0x1c)
            stopped = read(interface+0x110, 1)[0]
            if not 1 <= capacity <= 1024 or occupied > 1024 or stopped not in (0, 1):
                raise ValueError('dependency_production_bounds')
            unpacking = bool(_word(read, thing+0x94) & 4)
            # Full mirror of 0x6f48f0 for its normal non-aircraft, max-count=0
            # branch. Return order matters: aircraft restrictions precede full.
            unresolved = []; native_return = None
            if stopped or unpacking: native_return = 3
            elif limited_aircraft: unresolved.append('limited_aircraft_module_and_player_capacity')
            elif occupied >= capacity: native_return = 4
            elif maximum: unresolved.append('maximum_simultaneous_count')
            else: native_return = 0
            result.append(dict(producer_thing_id=ident, producer_thing_address=hex(thing),
                producer_type_hash=hex(expected_producer), native_factory_category=category,
                native_factory_category_match=True, queue_capacity=capacity, queue_occupied=occupied,
                native_stop=bool(stopped), native_unpacking=unpacking,
                native_enqueue_admission_return=native_return,
                native_enqueue_admission_met=None if native_return is None else native_return == 0,
                unresolved_admission_conditions=unresolved,
                native_target_maximum_simultaneous=maximum,
                target_limited_aircraft=limited_aircraft,
                overall_production_permitted=None, field_verified=False, grants_capability=False,
                source='0x6f48f0_restricted_branch_readonly_mirror'))
        return result

    def sample(self, actions=None):
        actions = list(ACTIONS) if actions is None else actions
        if type(actions) is not list or not actions or len(actions) > 8 or any(type(a) is not str or a not in ACTIONS for a in actions) or len(set(actions)) != len(actions):
            raise ValueError('dependency_actions')
        self.base._identity()
        if _word(self.read, TEMPLATE_FACTORY_GLOBAL) != self.factory: raise ValueError('dependency_factory_changed')
        frame = _word(self.read, self.base.game + 0x50)
        if not frame: raise ValueError('dependency_game_not_running')
        read = StableRead(self.read)
        owned = self._owned(read)
        rows = [self._dependency(read, action, owned) for action in actions]
        for row in rows:
            row['enqueue_admission_candidates'] = self._enqueue_admission(read, row['action'], owned)
        lifecycles = []
        for thing, ident, template in owned:
            key = _word(read, template + 8)
            if key not in readiness.TEMPLATES or readiness.TEMPLATES[key] in ('sickle', 'bullfrog'):
                continue
            state = readiness.observe_own_object(read, self.base.game, self.owner, ident, frame)
            state.update(thing_address=hex(thing), template_address=hex(template),
                native_required_object_eligible=self._required_object(read, template, [(thing, ident, template)])['native_required_object_met'])
            lifecycles.append(state)
        read.finish(); self.base._identity()
        if _word(self.read, TEMPLATE_FACTORY_GLOBAL) != self.factory or not 0 <= _word(self.read, self.base.game + 0x50)-frame <= 2:
            raise ValueError('dependency_session_or_frame_changed')
        return dict(schema_version=1, kind='native_required_object_dependency_observation', frame=frame,
            owner_index=self.base.owner_index, own_vector_count=len(owned), actions=rows,
            session_identity=dict(game=hex(self.base.game), owner=hex(self.owner),
                owner_index=self.base.owner_index, template_factory=hex(self.factory)),
            own_lifecycles=lifecycles,
            native_calls=0, process_writes=0, enemy_details_read=False,
            field_verified=False, grants_capability=False, overall_production_permission_verified=False)


class ConstructionLifecycleTracker:
    """Recognize the pinned callback's 0->1 notification across one identity.

    A preexisting true marker cannot seed completion. Losing sequence, identity,
    or a bounded observation gap discards the previous completion proof.
    """
    def __init__(self, *, maximum_frame_gap=30):
        if type(maximum_frame_gap) is not int or not 1 <= maximum_frame_gap <= 30:
            raise ValueError('dependency_lifecycle_gap_bound')
        self.maximum_frame_gap = maximum_frame_gap
        self.previous = {}; self.completed = set(); self.session = None; self.frame = None

    def observe(self, snapshot, *, session_token):
        if type(session_token) is not str or not session_token or len(session_token) > 256:
            raise ValueError('dependency_lifecycle_session_token')
        if type(snapshot) is not dict or snapshot.get('kind') != 'native_required_object_dependency_observation':
            raise ValueError('dependency_lifecycle_snapshot')
        frame, session, rows = snapshot.get('frame'), snapshot.get('session_identity'), snapshot.get('own_lifecycles')
        if type(frame) is not int or frame <= 0 or type(session) is not dict or type(rows) is not list or len(rows) > 1024:
            raise ValueError('dependency_lifecycle_snapshot')
        session_key = (('caller_session_token', session_token),) + tuple((key, session.get(key)) for key in ('game', 'owner', 'owner_index', 'template_factory'))
        if any(value is None for _key, value in session_key): raise ValueError('dependency_lifecycle_session')
        reset = self.session != session_key or self.frame is None or not 0 < frame-self.frame <= self.maximum_frame_gap
        previous = {} if reset else self.previous
        completed = set() if reset else set(self.completed)
        current = {}; result = []; ids = set()
        for row in rows:
            if type(row) is not dict: raise ValueError('dependency_lifecycle_object')
            ident = row.get('thing_id')
            if type(ident) is not int or not ident or ident in ids: raise ValueError('dependency_lifecycle_identity')
            ids.add(ident)
            key = (ident, row.get('thing_address'), row.get('template_address'), row.get('type_hash'))
            if any(value is None for value in key): raise ValueError('dependency_lifecycle_identity')
            statuses = row.get('object_status'); unpack = row.get('unpack')
            if type(statuses) is not dict or type(unpack) is not dict: raise ValueError('dependency_lifecycle_state')
            active, notified = unpack.get('native_unpack_in_progress'), row.get('native_unpack_completion_notified')
            if type(active) is not bool or type(notified) is not bool:
                # Missing module/state cannot extend a positive lifecycle claim.
                completed.discard(key)
                result.append(dict(thing_id=ident, construction_completed=None,
                    native_completion_transition_observed=False, source='unpack_state_unavailable'))
                continue
            negative = any(statuses.get(name) for name in ('under_construction', 'pending_construction', 'unpacking', 'reconstructing'))
            valid = row.get('currently_registered') is True and row.get('named_template_supported') is True
            valid = valid and not any(statuses.get(name) for name in ('destroyed', 'sold', 'not_in_world')) and row.get('hp', 0) > 0
            before = previous.get(key)
            event = bool(valid and not negative and not active and notified and before
                and before['active'] and not before['notified'] and before['negative']
                and before['duration'] > 0 and before['started'] > 0
                and before['duration'] == unpack.get('native_unpack_duration_frames')
                and before['started'] == unpack.get('native_unpack_started_frame'))
            if event: completed.add(key)
            if not valid or negative or active or not notified: completed.discard(key)
            current[key] = dict(active=active, notified=notified, negative=negative,
                duration=unpack.get('native_unpack_duration_frames', 0),
                started=unpack.get('native_unpack_started_frame', 0))
            result.append(dict(thing_id=ident, thing_address=row['thing_address'],
                construction_completed=False if negative else (True if key in completed else None),
                native_completion_transition_observed=event,
                native_required_object_eligible=row.get('native_required_object_eligible'),
                operational=False if row.get('known_operational_blockers') else None,
                overall_production_permitted=None, technology_unlocked=None,
                field_verified=False, grants_capability=False,
                source='same_identity_pinned_native_completion_notification_transition'))
        self.session = session_key; self.frame = frame; self.previous = current
        self.completed = completed.intersection(current)
        return dict(schema_version=1, kind='construction_lifecycle_evidence', frame=frame,
            sequence_reset=reset, objects=result, field_verified=False, grants_capability=False,
            completion_scope='observed_same_identity_native_unpack_completion_transition')


def audit_executable(path):
    # Reuse the frozen observer's offline PE verification, then check extensions.
    result = readiness.audit_executable(path)
    raw = Path(path).read_bytes()
    for at, expected in PINS.items():
        # Reviewed addresses all lie in file-backed .text/.rdata with this mapping.
        wanted = bytes.fromhex(expected)
        if raw[at-0x400000:at-0x400000+len(wanted)] != wanted:
            raise ValueError('dependency_offline_pin_changed')
    for at, name in NATIVE_NAMES.items():
        wanted = name.encode()+b'\0'
        if raw[at-0x400000:at-0x400000+len(wanted)] != wanted:
            raise ValueError('dependency_offline_enum_changed')
    return dict(result, kind='native_dependency_static_audit',
        dependency_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependency_byte_checks=[dict(address=hex(at), bytes=value) for at, value in PINS.items()],
        positive_scope=['native_required_object_subpredicate',
            'native_game_dependency_with_only_mirrored_noop_other_conditions',
            'native_enqueue_admission_nonlimited_zero_maximum_branch',
            'same_identity_observed_native_completion_notification_transition'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-executable', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = audit_executable(args.audit_executable)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(dict(output=str(args.output), extension_pins=len(PINS), field_verified=False)))


if __name__ == '__main__': main()
