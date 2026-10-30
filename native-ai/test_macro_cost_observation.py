"""Sparse artificial memory; no game process, model or native calls."""
import struct
import unittest

import macro_cost_observation as c
import readiness_dependency_contract as d
from test_readiness_dependency_contract import fixture as dependency_fixture


def fixture():
    mem, p = dependency_fixture()
    for at, raw in c.PINS.items(): mem.put(at, bytes.fromhex(raw))
    mem.put(0xbd7078, b'BUILD_FOR_FREE\0')
    mem.zeros(p['owner'] + 0x1290, 0x18)
    sentinel = p['owner'] + 0x1294
    for off in (4, 8): mem.word(p['owner'] + 0x1290 + off, sentinel)
    mem.zeros(p['definition'], 0x4c)
    mem.word(p['thing'] + 4, p['templates'][0xd50c222e])
    mem.word(p['thing'] + 0x3c0, 0x720000)
    for key, template in p['templates'].items():
        mem.put(template + 0x304, struct.pack('<H', 937))
    account, vector, manager = 0x730000, 0x731000, 0x732000
    mem.zeros(account, 0x18); mem.zeros(vector, 4); mem.zeros(manager, 0x70)
    mem.word(p['owner'] + 0xe4, vector); mem.word(p['owner'] + 0xe8, vector + 4)
    mem.word(vector, account); mem.word(account + 0xc, 3)
    mem.word(account + 4, 1200); mem.word(account + 0x14, 35)
    mem.word(c.PLAYER_MANAGER_GLOBAL, manager); mem.word(manager + 0x3c, p['owner'])
    p.update(account=account, resource_vector=vector, player_manager=manager)
    return mem, p


class CostTests(unittest.TestCase):
    def setUp(self): self.mem, self.p = fixture()
    def observer(self, read=None):
        return c.NativeCostObserver(read or self.mem.read, self.p['owner'],
            executable_sha256=c.EXE_SHA256, expected_owner_index=3)
    def sample(self, action='producesickle', read=None):
        return self.observer(read).sample(action, producer_thing_id=17)
    def own_bonus(self, bonus=-0.25, source=3):
        tree = self.p['owner'] + 0x1290; node = 0x740000; sentinel = tree + 4
        for off in (4, 8, 12): self.mem.word(tree + off, node)
        self.mem.word(tree + 0x14, 1)
        self.mem.put(node, struct.pack('<5If', 0, 0, sentinel, 1, source, bonus))
        return node
    def pool(self, count=0):
        pool = 0x750000; self.mem.zeros(pool, 0x3c)
        self.mem.word(self.p['thing'] + 0x36c, pool)
        self.mem.word(pool, c.ATTRIBUTE_POOL_VTABLE)
        self.mem.word(pool + 4, self.p['templates'][0xd50c222e])
        self.mem.word(pool + 0x38, self.p['thing'])
        if count:
            self.mem.word(pool + 0x28, 0x751000); self.mem.word(pool + 0x2c, 0x751000+16*count)
        return pool

    def test_current_native_runtime_quote_not_reservation_or_payment(self):
        row = self.sample()
        self.assertEqual(row['native_runtime_base_cost'], 937)
        self.assertEqual(row['native_getter_quote'], 937)
        self.assertEqual(row['ordinary_unit_enqueue_cost'], 937)
        self.assertIsNone(row['upper_cost']); self.assertIsNone(row['native_reserved_credits'])
        self.assertIsNone(row['actual_paid']); self.assertIsNone(row['actual_construction_cost'])
        for field in ['upper_cost_verified', 'native_reserved_credits_verified', 'reservation_usable',
                'future_quote_validity_verified', 'field_verified', 'grants_capability', 'enemy_details_read']:
            self.assertFalse(row[field])
        self.assertEqual(row['native_calls'], 0); self.assertEqual(row['process_writes'], 0)

    def test_native_payment_balance_additional_is_spendable_not_reserved(self):
        balance = self.sample()['current_payment_balance']
        self.assertEqual(balance['credits'], 1235); self.assertTrue(balance['credits_verified'])
        self.assertEqual(balance['native_additional_spendable'], 35)
        self.assertIsNone(balance['native_reserved_credits'])

    def test_single_own_technology_bonus_and_sse_truncation(self):
        self.own_bonus()
        row = self.sample()
        self.assertEqual(row['producer_multiplier']['multiplier'], 0.75)
        self.assertEqual(row['native_getter_quote'], 702)
        self.assertEqual(row['ordinary_unit_enqueue_cost'], 702)

    def test_ignored_provider_bonus_does_not_apply(self):
        self.own_bonus(); self.mem.put(self.p['owner'] + 0x123c, b'\1')
        self.assertEqual(self.sample()['native_getter_quote'], 937)

    def test_negative_total_bonus_clamps_to_zero(self):
        self.own_bonus(-2.0)
        self.assertEqual(self.sample()['native_getter_quote'], 0)

    def test_foreign_bonus_never_follows_foreign_player(self):
        self.own_bonus(source=4)
        row = self.sample()
        self.assertIsNone(row['native_getter_quote'])
        self.assertEqual(row['native_runtime_base_cost'], 937)
        self.assertFalse(any(at == self.p['player_manager'] + 0x40 for at, _ in self.mem.reads))

    def test_multiple_providers_remain_unknown(self):
        self.mem.word(self.p['owner'] + 0x12a4, 2)
        self.assertIsNone(self.sample()['native_getter_quote'])

    def test_non_native_sentinel_children_do_not_fake_singleton_iteration(self):
        node = self.own_bonus()
        self.mem.word(node, self.p['owner'] + 0x1294)
        with self.assertRaisesRegex(ValueError, 'single_bonus_node'): self.sample()

    def test_conditional_production_modifier_not_assumed_one(self):
        self.mem.word(self.p['definition'] + 0x44, 1)
        row = self.sample()
        self.assertIsNone(row['native_getter_quote']); self.assertIsNone(row['ordinary_unit_enqueue_cost'])

    def test_null_native_interface_guard_skips_player_bonus(self):
        self.own_bonus(source=4); self.mem.word(self.p['thing'] + 0x3c0, 0)
        self.assertEqual(self.sample()['native_getter_quote'], 937)

    def test_empty_native_attribute_pool_keeps_current_unit_quote(self):
        self.pool(); row = self.sample()
        self.assertEqual(row['ordinary_unit_enqueue_cost'], 937)
        self.assertTrue(row['producer_attribute_evidence']['cost_adjustment_absent'])

    def test_active_attribute_pool_never_skipped(self):
        self.pool(1); row = self.sample()
        self.assertEqual(row['native_getter_quote'], 937)
        self.assertIsNone(row['ordinary_unit_enqueue_cost'])

    def test_build_for_free_bypasses_getter_only_with_no_attribute_adjustment(self):
        template = self.p['templates'][0x60f0b4e9]
        self.mem.word(template + 0xd0, 1 << 26)
        self.assertEqual(self.sample()['ordinary_unit_enqueue_cost'], 0)
        self.pool(1)
        self.assertIsNone(self.sample()['ordinary_unit_enqueue_cost'])

    def test_each_building_getter_quote_is_not_actual_construction_cost(self):
        self.mem.word(self.p['thing'] + 4, self.p['templates'][0xc16ff13f])
        for action in d.ACTIONS:
            if action.startswith('produce'): continue
            with self.subTest(action=action):
                row = self.sample(action)
                self.assertEqual(row['native_getter_quote'], 937)
                self.assertIsNone(row['ordinary_unit_enqueue_cost'])
                self.assertIsNone(row['actual_construction_cost'])

    def test_wrong_producer_type_rejected(self):
        with self.assertRaisesRegex(ValueError, 'wrong_producer'): self.sample('buildrefinery')

    def test_foreign_thing_rejected_before_template_discounts_and_credits(self):
        self.mem.word(self.p['thing'] + 0x418, 0x21000)
        with self.assertRaisesRegex(ValueError, 'foreign_producer'): self.sample()
        self.assertFalse(any(at in [self.p['thing']+4, self.p['owner']+0xe4] for at, _ in self.mem.reads))

    def test_missing_or_reused_registry_identity_rejected(self):
        self.mem.word(self.p['thing'] + 0xdc, 18)
        with self.assertRaisesRegex(ValueError, 'registry_identity'): self.sample()

    def test_resource_foreign_owner_rejected(self):
        self.mem.word(self.p['account'] + 0xc, 4)
        with self.assertRaisesRegex(ValueError, 'account_owner'): self.sample()

    def test_absent_resource_slot_is_unknown_not_zero(self):
        self.mem.word(self.p['owner'] + 0xe4, 0); self.mem.word(self.p['owner'] + 0xe8, 0)
        row = self.sample()['current_payment_balance']
        self.assertIsNone(row['credits']); self.assertFalse(row['credits_verified'])

    def test_corrupt_account_balance_rejected(self):
        self.mem.word(self.p['account'] + 4, 0xffffffff)
        with self.assertRaisesRegex(ValueError, 'balance_overflow'): self.sample()

    def test_nonfinite_bonus_rejected(self):
        self.own_bonus(float('nan'))
        with self.assertRaisesRegex(ValueError, 'nonfinite'): self.sample()

    def test_changed_pool_identity_rejected(self):
        pool = self.pool(); self.mem.word(pool + 0x38, 0x51000)
        with self.assertRaisesRegex(ValueError, 'pool_identity'): self.sample()

    def test_wrong_executable_rejected_without_memory_access(self):
        with self.assertRaisesRegex(ValueError, 'exact_executable'):
            c.NativeCostObserver(self.mem.read, self.p['owner'], executable_sha256='0'*64,
                expected_owner_index=3)
        self.assertEqual(self.mem.reads, [])

    def test_changed_native_cost_signature_rejected(self):
        self.mem.put(0x7df7e0, b'\x00')
        with self.assertRaisesRegex(ValueError, 'cost_signature'): self.observer()

    def test_dynamic_cost_mutation_cannot_publish_coherent_quote(self):
        observer = self.observer(); calls = 0
        def changing(at, size):
            nonlocal calls
            if at == self.p['templates'][0x60f0b4e9] + 0x304:
                calls += 1
                if calls > 1: return struct.pack('<H', 938)
            return self.mem.read(at, size)
        observer.read = changing
        with self.assertRaisesRegex(ValueError, 'sample_changed'):
            observer.sample('producesickle', producer_thing_id=17)

    def test_factory_change_and_frame_gap_rejected(self):
        observer = self.observer()
        self.mem.word(d.TEMPLATE_FACTORY_GLOBAL, 0x110000)
        with self.assertRaisesRegex(ValueError, 'factory_changed'):
            observer.sample('producesickle', producer_thing_id=17)
        self.mem.word(d.TEMPLATE_FACTORY_GLOBAL, self.p['factory'])
        calls = 0
        def delayed(at, size):
            nonlocal calls
            if at == self.p['game'] + 0x50:
                calls += 1
                if calls > 1: return struct.pack('<I', 103)
            return self.mem.read(at, size)
        observer.read = delayed
        with self.assertRaisesRegex(ValueError, 'session_or_frame'):
            observer.sample('producesickle', producer_thing_id=17)


if __name__ == '__main__': unittest.main()
