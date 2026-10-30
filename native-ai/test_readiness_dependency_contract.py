"""Artificial sparse native memory only; no game/process/model access."""
import struct
import unittest

import readiness_dependency_contract as d
import macro_readiness_observation as r
from test_macro_readiness_observation import fixture as readiness_fixture


def fixture():
    mem, p = readiness_fixture()
    for at, raw in d.PINS.items(): mem.put(at, bytes.fromhex(raw))
    for at, name in d.NATIVE_NAMES.items(): mem.put(at, name.encode()+b'\0')
    mem.zeros(p['owner'] + 0x110, 0x1158)
    factory, buckets, vector = 0x100000, 0x101000, 0x102000
    mem.zeros(factory, 0x34); mem.zeros(buckets, 8); mem.zeros(vector, 8)
    mem.word(d.TEMPLATE_FACTORY_GLOBAL, factory)
    mem.word(factory + 0x2c, buckets); mem.word(factory + 0x30, 1)
    mem.word(p['owner'] + 0x1260, vector); mem.word(p['owner'] + 0x1264, vector + 4)
    mem.word(vector, p['thing'])
    hashes = [value[0] for value in d.ACTIONS.values()] + [0xc16ff13f]
    templates = {}; definitions = {}; wrappers = {}; dependency_data = {}
    for i, key in enumerate(hashes):
        template = p['template'] if key == 0xcf8d9f20 else 0x200000 + i*0x1000
        definition, node = 0x300000+i*0x1000, 0x400000+i*0x1000
        wrapper, data = 0x500000+i*0x1000, 0x600000+i*0x1000
        mem.zeros(template, 0x31c); mem.zeros(definition, 0x244); mem.zeros(node, 12)
        mem.zeros(wrapper, 8); mem.zeros(data, 0x28)
        mem.word(template + 8, key); mem.word(template + 0x14, definition)
        mem.word(template + 0xd0, 1 << 21)
        mem.word(definition + 0x130, 2 if key in (0x60f0b4e9, 0x522bcb61) else 1)
        mem.put(node, struct.pack('<III', key, template, 0x400000+(i+1)*0x1000 if i+1<len(hashes) else 0))
        templates[key] = template; definitions[key] = definition
        wrappers[key] = wrapper; dependency_data[key] = data
        expected = next((expected for target, expected in d.ACTIONS.values() if target == key), ())
        if expected:
            mem.word(template + 0x318, wrapper); mem.word(definition + 0x194, data)
            mem.word(wrapper, d.DEPENDENCY_VTABLE); mem.word(wrapper + 4, data)
            mem.word(data + 0xc, len(expected)); mem.word(data + 0x10, data + 0x100)
            mem.put(data + 0x100, struct.pack('<'+'I'*len(expected), *expected))
    mem.word(buckets, 0x400000)
    mem.word(p['interface']-0x24, 0xc3fad0); mem.word(p['definition']+0x30, 2)
    p.update(factory=factory, owned_vector=vector, templates=templates, definitions=definitions,
        wrappers=wrappers, dependency_data=dependency_data)
    return mem, p


class DependencyTests(unittest.TestCase):
    def setUp(self): self.mem, self.p = fixture()
    def observer(self, read=None):
        return d.DependencyObserver(read or self.mem.read, self.p['owner'],
            executable_sha256=d.EXE_SHA256, expected_owner_index=3)
    def row(self, action='buildrefinery'):
        return self.observer().sample([action])['actions'][0]
    def status(self, index):
        self.mem.word(self.p['thing'] + 0x80 + 4*(index//32), 1 << (index%32))

    def test_native_bound_required_object_has_positive_subpredicate(self):
        row = self.row()
        self.assertTrue(row['native_required_objects_met']); self.assertTrue(row['prerequisite_met'])
        self.assertTrue(row['sdk_required_objects_match'])
        evidence = row['required_object_evidence'][0]
        self.assertEqual(evidence['witnesses'][0]['thing_id'], 17)
        self.assertIsNone(row['overall_production_permitted']); self.assertFalse(row['grants_capability'])

    def test_absent_native_dependency_is_positive_only_for_dependency_scope(self):
        for action in ['buildpower', 'buildbarracks', 'producesickle', 'producebullfrog']:
            row = self.row(action)
            self.assertTrue(row['prerequisite_met']); self.assertFalse(row['native_dependency_present'])
            self.assertIsNone(row['overall_production_permitted'])

    def test_each_native_status_exclusion_is_honored(self):
        for index in [2, 107, 162, 55, 145]:
            self.mem, self.p = fixture(); self.status(index)
            with self.subTest(index=index):
                row = self.row(); self.assertFalse(row['prerequisite_met'])
                self.assertTrue(row['required_object_evidence'][0]['excluded'][0]['blockers'])

    def test_unpack_filter_uses_actual_native_activate_kindof(self):
        self.status(162); self.mem.word(self.p['templates'][0xcf8d9f20] + 0xd0, 0)
        self.assertTrue(self.row()['prerequisite_met'])

    def test_emp_and_exclusion_bit_are_distinct_from_underpower(self):
        self.mem.word(self.p['thing'] + 0x26c, 1 << 6)
        row = self.row(); self.assertTrue(row['prerequisite_met'])
        self.assertTrue(row['required_object_evidence'][0]['witnesses'][0]['underpowered'])
        self.mem.word(self.p['thing'] + 0x26c, 1 << 2)
        self.assertFalse(self.row()['prerequisite_met'])
        self.mem.word(self.p['thing'] + 0x26c, 0); self.mem.put(self.p['thing'] + 0x471, b'\1')
        self.assertFalse(self.row()['prerequisite_met'])

    def test_wrong_type_or_no_owned_object_does_not_satisfy(self):
        self.mem.word(self.p['thing'] + 4, self.p['templates'][0x80d4ea1e])
        self.assertFalse(self.row()['prerequisite_met'])
        self.mem.word(self.p['owner'] + 0x1264, self.p['owned_vector'])
        self.assertFalse(self.row()['prerequisite_met'])

    def test_equivalent_template_lists_mirror_native_both_directions(self):
        self.mem.word(self.p['thing'] + 4, self.p['templates'][0x80d4ea1e])
        for key, alias in [(0x80d4ea1e, 0xcf8d9f20), (0xcf8d9f20, 0x80d4ea1e)]:
            definition = self.p['definitions'][key]
            self.mem.word(definition + 0x1bc, 1); self.mem.word(definition + 0x1c0, definition + 0x200)
            self.mem.word(definition + 0x200, alias)
            self.assertTrue(self.row()['prerequisite_met'])
            self.mem.word(definition + 0x1bc, 0)

    def test_other_conditions_never_silently_skipped(self):
        data = self.p['dependency_data'][0xc45aaeab]
        for at in [0, 4, 8, 0x14, 0x1c, 0x24]:
            self.mem, self.p = fixture(); data = self.p['dependency_data'][0xc45aaeab]
            if at in [0, 4, 8]:
                self.mem.word(data + at, data + 0x200); self.mem.zeros(data + 0x200, 60)
                self.mem.word(data + 0x200, 1)
            elif at == 0x24:
                self.mem.word(data + at, 0x700000); self.mem.zeros(0x700000, 0x64)
                self.mem.word(0x700004, 1)
            else: self.mem.word(data + at, 1)
            with self.subTest(at=at):
                row = self.row(); self.assertTrue(row['native_required_objects_met'])
                self.assertIsNone(row['prerequisite_met']); self.assertTrue(row['unsupported_dependency_conditions'])

    def test_empty_native_masks_do_not_force_unknown(self):
        data = self.p['dependency_data'][0xc45aaeab]
        for at in [0, 4, 8]: self.mem.word(data + at, data + 0x200)
        self.mem.zeros(data + 0x200, 60)
        self.assertTrue(self.row()['prerequisite_met'])

    def test_filter_native_noop_branch_is_mirrored_but_real_filter_unknown(self):
        data = self.p['dependency_data'][0xc45aaeab]
        self.mem.word(data + 0x24, 0x700000); self.mem.zeros(0x700000, 0x64)
        self.assertTrue(self.row()['prerequisite_met'])
        for at in (4, 0x10, 0x60):
            self.mem.zeros(0x700000, 0x64); self.mem.word(0x700000 + at, 1)
            self.assertIsNone(self.row()['prerequisite_met'])

    def test_sdk_expectation_is_a_crosscheck_not_substitute_native(self):
        data = self.p['dependency_data'][0xc45aaeab]
        self.mem.word(data + 0x100, 0x80d4ea1e)
        row = self.row(); self.assertFalse(row['sdk_required_objects_match']); self.assertFalse(row['prerequisite_met'])

    def test_wrapper_and_compiled_definition_must_bind(self):
        wrapper = self.p['wrappers'][0xc45aaeab]
        self.mem.word(wrapper + 4, 0x700000)
        with self.assertRaisesRegex(ValueError, 'compiled_binding'): self.row()
        self.mem, self.p = fixture(); self.mem.word(self.p['templates'][0xc45aaeab] + 0x318, 0)
        with self.assertRaisesRegex(ValueError, 'runtime_wrapper'): self.row()

    def test_foreign_object_rejected_before_template_or_status(self):
        self.mem.word(self.p['thing'] + 0x418, 0x21000)
        with self.assertRaisesRegex(ValueError, 'foreign'): self.row()
        self.assertFalse(any(at == self.p['thing'] + 4 or at == self.p['thing'] + 0x80 for at, _ in self.mem.reads))

    def test_registry_identity_vector_duplicates_and_bounds_fail_closed(self):
        self.mem.word(self.p['thing'] + 0xdc, 18)
        with self.assertRaisesRegex(ValueError, 'registry_link'): self.row()
        self.mem, self.p = fixture(); self.mem.word(self.p['owner'] + 0x1264, self.p['owned_vector']+8)
        self.mem.word(self.p['owned_vector']+4, self.p['thing'])
        with self.assertRaisesRegex(ValueError, 'duplicate_own'): self.row()
        self.mem.word(self.p['owner'] + 0x1264, self.p['owned_vector']+4100)
        with self.assertRaisesRegex(ValueError, 'vector_bounds'): self.row()

    def test_pins_and_enum_names_verified_before_dynamic_reads(self):
        for at in [next(iter(d.PINS)), next(iter(d.NATIVE_NAMES))]:
            self.mem, self.p = fixture(); self.mem.put(at, b'\xff')
            with self.assertRaisesRegex(ValueError, 'signature|enum'): self.observer()

    def test_unstable_dependency_memory_rejected(self):
        at = self.p['dependency_data'][0xc45aaeab]; calls = 0
        def changing(address, size):
            nonlocal calls
            raw = self.mem.read(address, size)
            if address == at and size == 0x28:
                calls += 1
                if calls == 2: return bytes([raw[0]^1])+raw[1:]
            return raw
        with self.assertRaisesRegex(ValueError, 'sample_changed'): self.observer(changing).sample(['buildrefinery'])

    def test_wrong_executable_and_invalid_action_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'exact_executable'):
            d.DependencyObserver(self.mem.read, self.p['owner'], executable_sha256='0'*64, expected_owner_index=3)
        for actions in [[], ['bogus'], ['buildpower', 'buildpower'], ('buildpower',), [{}], [True]]:
            with self.assertRaisesRegex(ValueError, 'actions'): self.observer().sample(actions)

    def test_normal_unit_enqueue_admission_can_be_positive_without_tech_or_operation_grant(self):
        self.mem.word(self.p['thing']+4, self.p['templates'][0xd50c222e])
        for action in ('producesickle', 'producebullfrog'):
            row = self.row(action); admission = row['enqueue_admission_candidates'][0]
            self.assertTrue(admission['native_enqueue_admission_met'])
            self.assertEqual(admission['native_enqueue_admission_return'], 0)
            self.assertIsNone(admission['overall_production_permitted'])
        self.mem.word(self.p['thing']+0x26c, 1 << 6)
        self.assertTrue(self.row('producesickle')['enqueue_admission_candidates'][0]['native_enqueue_admission_met'])

    def test_enqueue_admission_return_order_stopped_full_and_count_unknown(self):
        self.mem.word(self.p['thing']+4, self.p['templates'][0xd50c222e])
        self.mem.put(self.p['interface']+0x110, b'\1')
        self.assertEqual(self.row('producesickle')['enqueue_admission_candidates'][0]['native_enqueue_admission_return'], 3)
        self.mem.put(self.p['interface']+0x110, b'\0'); self.mem.word(self.p['interface']+0x1c, 5)
        self.assertEqual(self.row('producesickle')['enqueue_admission_candidates'][0]['native_enqueue_admission_return'], 4)
        self.mem.word(self.p['templates'][0x60f0b4e9]+0xe0, 1 << 10)
        self.assertIsNone(self.row('producesickle')['enqueue_admission_candidates'][0]['native_enqueue_admission_met'])
        self.mem.word(self.p['templates'][0x60f0b4e9]+0xe0, 0); self.mem.word(self.p['interface']+0x1c, 0)
        self.mem.put(self.p['definitions'][0x60f0b4e9]+0x242, b'\1\0')
        self.assertIsNone(self.row('producesickle')['enqueue_admission_candidates'][0]['native_enqueue_admission_met'])

    def test_construction_producer_and_native_category_must_match(self):
        self.assertEqual(self.row('producesickle')['enqueue_admission_candidates'], [])
        self.mem.word(self.p['thing']+4, self.p['templates'][0xc16ff13f])
        self.mem.word(self.p['definition']+0x30, 1)
        self.assertTrue(self.row('buildbarracks')['enqueue_admission_candidates'][0]['native_enqueue_admission_met'])
        self.mem.word(self.p['definition']+0x30, 2)
        self.assertEqual(self.row('buildbarracks')['enqueue_admission_candidates'], [])

    def test_producer_backlink_and_queue_bounds_are_checked(self):
        self.mem.word(self.p['thing']+4, self.p['templates'][0xd50c222e])
        self.mem.word(self.p['interface']-0x1c, 0x51000)
        with self.assertRaisesRegex(ValueError, 'production_owner'): self.row('producesickle')
        self.mem.word(self.p['interface']-0x1c, self.p['thing'])
        self.mem.word(self.p['definition']+8, 0)
        with self.assertRaisesRegex(ValueError, 'production_bounds'): self.row('producesickle')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.mem, self.p = fixture()
        self.observer = d.DependencyObserver(self.mem.read, self.p['owner'],
            executable_sha256=d.EXE_SHA256, expected_owner_index=3)
        self.tracker = d.ConstructionLifecycleTracker()
    def snapshot(self): return self.observer.sample(['buildrefinery'])
    def observe(self, snapshot=None, token='process-create-time/match-session-nonce'):
        return self.tracker.observe(snapshot or self.snapshot(), session_token=token)
    def start(self):
        self.mem.word(self.p['game'] + 0x50, 150)
        self.mem.word(self.p['thing'] + 0x80, 1 << 2)
        self.mem.word(self.p['thing'] + 0x94, 1 << 2)
        self.mem.put(self.p['unpack'] + 0x44, b'\1')
        return self.observe()
    def complete(self, frame=160):
        self.mem.word(self.p['game'] + 0x50, frame)
        self.mem.word(self.p['thing'] + 0x80, 0); self.mem.word(self.p['thing'] + 0x94, 0)
        self.mem.put(self.p['unpack'] + 0x44, b'\0'); self.mem.put(self.p['thing'] + 0x301, b'\1')

    def test_same_identity_native_callback_edge_is_positive_completion_evidence(self):
        self.assertFalse(self.start()['objects'][0]['construction_completed'])
        self.complete(); report = self.observe(); row = report['objects'][0]
        self.assertTrue(row['native_completion_transition_observed']); self.assertTrue(row['construction_completed'])
        self.assertTrue(row['native_required_object_eligible']); self.assertIsNone(row['operational'])
        self.assertIsNone(row['overall_production_permitted']); self.assertFalse(report['grants_capability'])
        self.mem.word(self.p['game'] + 0x50, 161)
        row = self.observe()['objects'][0]
        self.assertTrue(row['construction_completed']); self.assertFalse(row['native_completion_transition_observed'])

    def test_preexisting_true_notification_cannot_seed_completion(self):
        self.complete(); row = self.observe()['objects'][0]
        self.assertFalse(row['native_completion_transition_observed']); self.assertIsNone(row['construction_completed'])

    def test_elapsed_time_status_clear_and_inactive_module_are_insufficient(self):
        self.start(); self.complete(); self.mem.put(self.p['thing'] + 0x301, b'\0')
        row = self.observe()['objects'][0]; self.assertIsNone(row['construction_completed'])

    def test_frame_gap_out_of_order_and_token_change_reset_history(self):
        for frame, token in [(181, 'process-create-time/match-session-nonce'), (149, 'process-create-time/match-session-nonce'), (160, 'new-match')]:
            self.setUp(); self.start(); self.complete(frame)
            report = self.observe(token=token)
            self.assertTrue(report['sequence_reset']); self.assertIsNone(report['objects'][0]['construction_completed'])

    def test_changed_pointer_or_unpack_identity_does_not_complete(self):
        self.start(); self.complete(); snapshot = self.snapshot()
        snapshot['own_lifecycles'][0]['thing_address'] = '0x51000'
        self.assertIsNone(self.observe(snapshot)['objects'][0]['construction_completed'])
        self.setUp(); self.start(); self.complete()
        self.mem.word(self.p['unpack'] + 0x3c, 11)
        self.assertIsNone(self.observe()['objects'][0]['construction_completed'])

    def test_reconstruction_invalidates_completion_but_underpower_does_not_undo_event(self):
        self.start(); self.complete(); self.assertTrue(self.observe()['objects'][0]['construction_completed'])
        self.mem.word(self.p['game'] + 0x50, 161); self.mem.word(self.p['thing'] + 0x26c, 1 << 6)
        row = self.observe()['objects'][0]
        self.assertTrue(row['construction_completed']); self.assertFalse(row['operational'])
        self.mem.word(self.p['game'] + 0x50, 162); self.mem.word(self.p['thing'] + 0x80, 1 << 2)
        self.assertFalse(self.observe()['objects'][0]['construction_completed'])

    def test_missing_object_discards_persistent_proof(self):
        self.start(); self.complete(); self.observe()
        snapshot = self.snapshot(); snapshot['frame'] = 161; snapshot['own_lifecycles'] = []
        self.observe(snapshot)
        self.mem.word(self.p['game'] + 0x50, 162)
        self.assertIsNone(self.observe()['objects'][0]['construction_completed'])

    def test_missing_module_and_invalid_token_fail_closed(self):
        self.start(); self.complete(); snapshot = self.snapshot()
        snapshot['own_lifecycles'][0]['unpack']['native_unpack_in_progress'] = None
        self.assertIsNone(self.observe(snapshot)['objects'][0]['construction_completed'])
        with self.assertRaisesRegex(ValueError, 'session_token'): self.observe(token='')


if __name__ == '__main__': unittest.main()
