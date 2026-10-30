"""Artificial owned-memory fixtures; never attach a game or call native code."""
import struct
import unittest

import macro_readiness_observation as m


class Memory:
    def __init__(self):
        self.data = {}; self.reads = []
    def put(self, address, raw):
        for i, value in enumerate(raw): self.data[address + i] = value
    def zeros(self, address, size): self.put(address, bytes(size))
    def word(self, address, value): self.put(address, struct.pack('<I', value))
    def read(self, address, size):
        self.reads.append((address, size))
        try: return bytes(self.data[address + i] for i in range(size))
        except KeyError: raise ValueError('fixture_unmapped_read') from None


def fixture():
    mem = Memory()
    for at, value in m.PINS.items(): mem.put(at, bytes.fromhex(value))
    for index, entry, pointer, label in m.STATUS_BITS.values():
        mem.put(entry, struct.pack('<II', pointer, index)); mem.put(pointer, label.encode() + b'\0')
    owner, game, energy, thing, unpack, template, body = 0x20000, 0x30000, 0x40000, 0x50000, 0x60000, 0x70000, 0x80000
    buckets, node, vector, wrapper, interface, definition = 0x90000, 0xa0000, 0xb0000, 0xc0000, 0xd0024, 0xe0000
    for at, size in [(owner, 0x110), (game, 0xc8), (energy, 0x2c), (thing, 0x474),
            (unpack, 0x46), (template, 12), (body, 8), (buckets, 8), (node, 12),
            (vector, 8), (wrapper, 0x18), (interface - 0x24, 0x138), (definition, 12)]:
        mem.zeros(at, size)
    mem.word(m.GAME_GLOBAL, game); mem.word(owner, m.PLAYER_VTABLE)
    mem.word(owner + 0x20, 3); mem.word(owner + 0x74, energy)
    mem.word(game + 0x50, 100); mem.word(game + 0xc0, buckets); mem.word(game + 0xc4, 1)
    mem.word(energy, m.ENERGY_VTABLE); mem.word(energy + 4, 100); mem.word(energy + 8, 50)
    mem.word(energy + 0x1c, owner); mem.word(energy + 0x20, energy + 0x20); mem.word(energy + 0x24, energy + 0x20)
    mem.word(buckets, node); mem.put(node, struct.pack('<III', 17, thing, 0))
    mem.word(thing, m.THING_VTABLE); mem.word(thing + 0x418, owner); mem.word(thing + 0xdc, 17)
    mem.word(thing + 4, template); mem.word(template + 8, 0xcf8d9f20)
    mem.word(thing + 0x33c, body); mem.put(body + 4, struct.pack('<f', 100.0))
    mem.word(thing + 0x310, vector); mem.word(vector, unpack)
    mem.word(unpack, m.UNPACK_VTABLE); mem.word(unpack + 8, thing)
    mem.word(unpack + 0x38, 150); mem.word(unpack + 0x3c, 10)
    mem.word(thing + 0x3b4, wrapper); mem.word(wrapper + 0x14, interface)
    mem.word(interface, m.PRODUCTION_INTERFACE_VTABLE); mem.word(interface - 0x1c, thing)
    mem.word(interface - 0x20, definition); mem.word(definition + 8, 5)
    return mem, dict(owner=owner, game=game, energy=energy, thing=thing, unpack=unpack,
        template=template, body=body, buckets=buckets, node=node, vector=vector,
        wrapper=wrapper, interface=interface, definition=definition)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.mem, self.p = fixture()
    def observer(self, read=None):
        return m.ReadinessObserver(read or self.mem.read, self.p['owner'],
            executable_sha256=m.EXE_SHA256, expected_owner_index=3)
    def object(self): return self.observer().sample([17])['own_objects'][0]
    def status(self, name):
        index = m.STATUS_BITS[name][0]
        self.mem.word(self.p['thing'] + 0x80 + 4 * (index // 32), 1 << (index % 32))

    def test_balanced_power_uses_native_list_and_totals_without_grant(self):
        report = self.observer().sample([17]); power = report['power']
        self.assertEqual((power['native_supply'], power['native_demand'], power['native_surplus']), (100, 50, 50))
        self.assertTrue(power['native_energy_sufficient']); self.assertTrue(power['reported_state_agrees'])
        self.assertFalse(report['field_verified']); self.assertFalse(report['grants_capability'])
        self.assertIsNone(report['own_objects'][0]['operational'])

    def test_deficit_and_forced_outage_are_distinct(self):
        self.mem.word(self.p['energy'] + 4, 25); self.mem.put(self.p['owner'] + 0x10c, b'\1')
        power = self.observer().sample([])['power']
        self.assertFalse(power['native_energy_sufficient']); self.assertTrue(power['native_outage_list_empty'])
        self.assertTrue(power['reported_state_agrees'])
        self.mem.word(self.p['energy'] + 4, 100)
        self.mem.word(self.p['energy'] + 0x20, 0xf0000); self.mem.word(self.p['energy'] + 0x24, 0xf0000)
        power = self.observer().sample([])['power']
        self.assertFalse(power['native_energy_sufficient']); self.assertFalse(power['native_outage_list_empty'])
        self.assertGreater(power['native_surplus'], 0)

    def test_reported_power_lag_is_visible_not_silently_corrected(self):
        self.mem.put(self.p['owner'] + 0x10c, b'\1')
        power = self.observer().sample([])['power']
        self.assertFalse(power['reported_state_agrees']); self.assertTrue(power['native_reported_low_power'])
        self.assertTrue(power['native_energy_sufficient'])

    def test_changed_executable_signature_enum_and_name_are_rejected(self):
        for address in [next(iter(m.PINS)), m.STATUS_BITS['under_construction'][1], m.STATUS_BITS['unpacking'][2]]:
            mem, p = fixture(); mem.put(address, b'\xff')
            with self.subTest(address=hex(address)):
                with self.assertRaisesRegex(ValueError, 'signature|enum|name'):
                    m.ReadinessObserver(mem.read, p['owner'], executable_sha256=m.EXE_SHA256, expected_owner_index=3)

    def test_wrong_executable_rejected_before_any_memory_read(self):
        with self.assertRaisesRegex(ValueError, 'exact_executable'):
            m.ReadinessObserver(self.mem.read, self.p['owner'], executable_sha256='0'*64, expected_owner_index=3)
        self.assertEqual(self.mem.reads, [])

    def test_foreign_thing_rejected_before_enemy_template_health_or_status_read(self):
        self.mem.word(self.p['thing'] + 0x418, 0x21000)
        with self.assertRaisesRegex(ValueError, 'foreign_thing'): self.object()
        for at in [self.p['thing'] + 4, self.p['thing'] + 0x80, self.p['thing'] + 0x33c]:
            self.assertFalse(any(address == at for address, _ in self.mem.reads))

    def test_missing_object_and_unnamed_template_preserve_unknown(self):
        report = self.observer().sample([18]); row = report['own_objects'][0]
        self.assertFalse(row['currently_registered']); self.assertIsNone(row['construction_completed'])
        self.mem.word(self.p['template'] + 8, 0x12345678)
        row = self.object(); self.assertFalse(row['named_template_supported']); self.assertIsNone(row['operational'])

    def test_under_construction_is_negative_readiness_not_completion(self):
        self.status('under_construction'); row = self.object()
        self.assertTrue(row['object_status']['under_construction'])
        self.assertFalse(row['construction_completed']); self.assertFalse(row['operational'])

    def test_clear_status_hp_or_inactive_unpack_alone_never_proves_completed(self):
        row = self.object()
        self.assertEqual(row['hp'], 100.0)
        self.assertFalse(row['unpack']['native_unpack_in_progress'])
        self.assertIsNone(row['construction_completed']); self.assertIsNone(row['operational'])
        self.assertIsNone(row['technology_unlocked']); self.assertIsNone(row['production_permitted'])

    def test_completion_notification_and_energy_registration_are_independent_native_facts(self):
        self.mem.put(self.p['thing'] + 0x301, b'\1')
        row = self.object()
        self.assertTrue(row['native_unpack_completion_notified'])
        self.assertFalse(row['native_template_energy_registered'])
        self.assertIsNone(row['construction_completed']); self.assertIsNone(row['operational'])
        self.mem.put(self.p['thing'] + 0x471, b'\x20')
        row = self.object(); self.assertTrue(row['native_template_energy_registered'])
        self.assertIsNone(row['technology_unlocked']); self.assertIsNone(row['production_permitted'])
        self.status('under_construction')
        self.assertFalse(self.object()['construction_completed'])

    def test_bad_or_unstable_completion_marker_rejected(self):
        self.mem.put(self.p['thing'] + 0x301, b'\2')
        with self.assertRaisesRegex(ValueError, 'notification_boolean'): self.object()
        for offset in (0x301, 0x471):
            self.mem, self.p = fixture(); count = 0
            def changing(address, size):
                nonlocal count
                if address == self.p['thing'] + offset and size == 1:
                    count += 1
                    if count == 2: return b'\x20' if offset == 0x471 else b'\1'
                return self.mem.read(address, size)
            with self.subTest(offset=hex(offset)):
                with self.assertRaisesRegex(ValueError, 'object_changed'):
                    self.observer(changing).sample([17])

    def test_live_unpack_ratio_and_pause_mirror_native_frame_formula(self):
        self.mem.put(self.p['unpack'] + 0x44, b'\1'); self.status('unpacking')
        row = self.object(); self.assertAlmostEqual(row['unpack']['native_unpack_progress_ratio'], 0.6)
        self.assertFalse(row['construction_completed']); self.assertFalse(row['production_permitted'])
        self.mem.put(self.p['unpack'] + 0x45, b'\1'); self.mem.word(self.p['unpack'] + 0x40, 50)
        self.assertAlmostEqual(self.object()['unpack']['native_unpack_progress_ratio'], 40 / 150)

    def test_expired_inactive_unpack_is_only_a_candidate(self):
        self.mem.word(self.p['game'] + 0x50, 200)
        row = self.object(); self.assertTrue(row['unpack']['native_unpack_end_state_candidate'])
        self.assertIsNone(row['unpack']['construction_completed']); self.assertIsNone(row['construction_completed'])

    def test_disabled_power_emp_sold_and_pending_are_separate_facts(self):
        for name in ('powered_down_emp', 'sold', 'pending_construction', 'not_in_world', 'user_powered_down'):
            mem, p = fixture(); self.mem, self.p = mem, p; self.status(name)
            row = self.object(); self.assertTrue(row['object_status'][name]); self.assertFalse(row['operational'])
        self.mem, self.p = fixture(); self.mem.word(self.p['thing'] + 0x26c, (1 << 6) | (1 << 10))
        row = self.object(); self.assertTrue(row['native_underpowered']); self.assertTrue(row['native_script_underpowered'])

    def test_native_queue_stop_and_full_are_blockers_not_all_admission(self):
        self.mem.put(self.p['interface'] + 0x110, b'\1')
        row = self.object(); self.assertFalse(row['production_permitted'])
        self.assertIn('native_production_stop_flag', row['producer']['known_production_blockers'])
        self.mem.put(self.p['interface'] + 0x110, b'\0')
        self.mem.word(self.p['interface'] + 0x1c, 5)
        row = self.object(); self.assertFalse(row['production_permitted'])
        self.assertIn('native_queue_full', row['producer']['known_production_blockers'])
        self.mem.word(self.p['interface'] + 0x1c, 0)
        self.assertIsNone(self.object()['production_permitted'])

    def test_missing_or_other_native_interface_never_infers_permission(self):
        self.mem.word(self.p['thing'] + 0x3b4, 0)
        row = self.object(); self.assertFalse(row['producer']['production_interface_present']); self.assertIsNone(row['production_permitted'])
        self.mem.word(self.p['thing'] + 0x3b4, self.p['wrapper'])
        self.mem.word(self.p['interface'], 0x123400)
        row = self.object(); self.assertFalse(row['producer']['known_interface']); self.assertIsNone(row['production_permitted'])

    def test_unknown_disabled_bit_still_blocks_and_is_not_renamed(self):
        self.mem.word(self.p['thing'] + 0x26c, 1 << 20)
        row = self.object(); self.assertTrue(row['unknown_disabled_bits']); self.assertFalse(row['operational'])
        self.assertFalse(row['native_underpowered'])

    def test_module_owner_duplicate_and_unterminated_vectors_are_rejected(self):
        self.mem.word(self.p['unpack'] + 8, 0x51000)
        with self.assertRaisesRegex(ValueError, 'module_owner'): self.object()
        self.mem, self.p = fixture(); self.mem.word(self.p['vector'] + 4, self.p['unpack']); self.mem.word(self.p['vector'] + 8, 0)
        with self.assertRaisesRegex(ValueError, 'duplicate_unpack'): self.object()
        self.mem, self.p = fixture()
        for i in range(256): self.mem.word(self.p['vector'] + i * 4, self.p['unpack'])
        with self.assertRaisesRegex(ValueError, 'unterminated'): self.object()

    def test_invalid_unpack_time_and_boolean_fail_closed(self):
        for offset, raw in [(0x44, b'\2'), (0x3c, struct.pack('<I', 101)), (0x38, struct.pack('<I', 54001))]:
            self.mem, self.p = fixture(); self.mem.put(self.p['unpack'] + offset, raw)
            with self.assertRaisesRegex(ValueError, 'unpack'): self.object()

    def test_invalid_energy_identity_bounds_and_list_rejected(self):
        for offset, value in [(0, 0x1234), (0x1c, 0x21000), (4, 0xffffffff), (0x20, 0xf0000)]:
            self.mem, self.p = fixture(); self.mem.word(self.p['energy'] + offset, value)
            with self.assertRaisesRegex(ValueError, 'energy'): self.observer().sample([])

    def test_nonfinite_hp_and_invalid_producer_numbers_rejected(self):
        self.mem.put(self.p['body'] + 4, struct.pack('<f', float('nan')))
        with self.assertRaisesRegex(ValueError, 'health'): self.object()
        self.mem, self.p = fixture(); self.mem.word(self.p['definition'] + 8, 1025)
        with self.assertRaisesRegex(ValueError, 'production_bounds'): self.object()

    def test_registry_recycle_wrong_identity_and_cycles_fail_closed(self):
        self.mem.word(self.p['thing'] + 0xdc, 18)
        with self.assertRaisesRegex(ValueError, 'thing_identity'): self.object()
        self.mem, self.p = fixture(); self.mem.put(self.p['node'], struct.pack('<III', 19, self.p['thing'], self.p['node']))
        with self.assertRaisesRegex(ValueError, 'registry_cycle'): self.object()

    def test_owner_game_and_frame_changes_are_not_mixed(self):
        observer = self.observer(); self.mem.word(m.GAME_GLOBAL, self.p['game'] + 0x1000)
        with self.assertRaisesRegex(ValueError, 'session_changed'): observer.sample([])
        self.mem, self.p = fixture(); count = 0
        def changing(address, size):
            nonlocal count
            if address == self.p['game'] + 0x50:
                count += 1
                if count == 2: return struct.pack('<I', 104)
            return self.mem.read(address, size)
        with self.assertRaisesRegex(ValueError, 'frame_changed'): self.observer(changing).sample([])

    def test_changed_energy_during_sample_is_rejected(self):
        count = 0
        def changing(address, size):
            nonlocal count
            if address == self.p['energy'] and size == 0x2c:
                count += 1
                if count == 2:
                    raw = bytearray(self.mem.read(address, size)); raw[4] ^= 1; return bytes(raw)
            return self.mem.read(address, size)
        with self.assertRaisesRegex(ValueError, 'energy_changed'): self.observer(changing).sample([])

    def test_input_bounds_and_short_reads_rejected(self):
        for ids in ([17, 17], [True], [0], list(range(1, 130)), (17,)):
            with self.assertRaisesRegex(ValueError, 'input_bounds'): self.observer().sample(ids)
        with self.assertRaisesRegex(ValueError, 'short_read'):
            m.verify_pins(lambda _at, _size: b'', m.EXE_SHA256)


if __name__ == '__main__': unittest.main()
