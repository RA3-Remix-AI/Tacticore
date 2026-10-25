"""Pure decoder boundary tests; no process access, SDK, or GUI."""
import struct
import unittest
import origin350_own_inventory_readonly as reader


class BytesMemory:
    def __init__(self):
        self.data = {}

    def put(self, address, raw):
        for i, value in enumerate(raw):
            self.data[address + i] = value

    def word(self, address, value):
        self.put(address, struct.pack('<I', value))

    def read(self, address, size):
        return bytes(self.data[address + i] for i in range(size))

    def u32(self, address):
        return struct.unpack('<I', self.read(address, 4))[0]

    def f32(self, address):
        return struct.unpack('<f', self.read(address, 4))[0]


def module_fixture(name='EngineerContain'):
    m = BytesMemory()
    m.word(0x10310, 0x20000)
    m.word(0x20000, 0x30000)
    m.word(0x20004, 0)
    m.word(0x30000, 0xc31210)
    m.word(0x30004, 0x40000)
    m.word(0x30008, 0x10000)
    m.word(0x3000c, 0xc31000)
    m.word(0xc31218, 0x7078c0)
    m.put(0x7078c0, b'\xb8' + struct.pack('<I', 0xc31268) + b'\xc3')
    m.put(0xc31268, name.encode('ascii') + bytes(96 - len(name)))
    return m


def weapon_fixture(selected=5):
    m = BytesMemory()
    m.word(0x1037c, 0x50000)
    for off, value in {0: 0xc45a18, 8: 0x10000, 0x24: 0x51000,
                       0x28: 0x51004, 0x2c: 0x51004}.items():
        m.word(0x50000 + off, value)
    m.word(0x51000, 0x52000)
    m.word(0x52000, 0xc3a6e0)
    m.word(0xc3a704, 0x6dbe80)
    m.word(0xc3a708, 0x6f88e0)
    m.word(0x52014, selected)
    m.word(0x5200c, 0x53000)
    m.put(0x53000, bytes(0x1c))
    m.word(0x52094, 0x54000)
    for i in range(6):
        m.word(0x54000 + 4 * i, 0)
    # Only the dormant mode1 entry exists. Even index5 must not hide it.
    m.word(0x54004, 0x55000)
    for off, value in {0: 0xc2e324, 4: 0x56000, 8: 0x52000, 0x1c: 1}.items():
        m.word(0x55000 + off, value)
    m.word(0x56004, 0x57000)
    m.word(0x57000, 0x58000)
    m.word(0x58000, 0x94d4d96e)
    m.word(0x58004, 0x41872ecc)
    return m


def unit_fixture():
    m = module_fixture()
    for address, value in {
        0x10000: 0xc4db60, 0x10004: 0x70000, 0x70008: 0xc16ff13f,
        0x100dc: 763, 0x10418: 0x90000, 0x1033c: 0x71000,
        0x1037c: 0, 0x60050: 100,
    }.items():
        m.word(address, value)
    m.put(0x71004, struct.pack('<f', 100.0))
    return m


class DecoderBoundaryTests(unittest.TestCase):
    def test_constant_name_uses_primary_vtable_plus8(self):
        m = module_fixture()
        self.assertEqual(reader.native_name(m, 0xc31210)['native_name'], 'EngineerContain')

    def test_complex_getter_is_unknown(self):
        m = module_fixture()
        m.put(0x7078c0, bytes.fromhex('e900000000c3'))
        r = reader.native_name(m, 0xc31210)
        self.assertFalse(r['verified_constant_name_getter'])
        self.assertIn('complex', r['error'])

    def test_full_array_and_backpointer(self):
        r = reader.module_inventory(module_fixture(), 0x10000)
        self.assertTrue(r['nonempty_complete'])
        self.assertTrue(r['all_names_decoded'])
        self.assertEqual(r['terminator_index'], 1)

    def test_broken_backpointer_fails_closed(self):
        m = module_fixture()
        m.word(0x30008, 0x10004)
        r = reader.module_inventory(m, 0x10000)
        self.assertFalse(r['complete'])

    def test_duplicate_module_fails_closed(self):
        m = module_fixture()
        m.word(0x20004, 0x30000)
        self.assertIn('duplicate', reader.module_inventory(m, 0x10000)['error'])

    def test_unterminated_array_fails_closed(self):
        m = module_fixture()
        r = reader.module_inventory(m, 0x10000, limit=0)
        self.assertFalse(r['complete'])

    def test_null_array_does_not_prove_absence(self):
        m = module_fixture()
        m.word(0x10310, 0)
        r = reader.module_inventory(m, 0x10000)
        self.assertFalse(r['complete'])

    def test_empty_array_is_not_completed_thing_inventory(self):
        m = module_fixture()
        m.word(0x20000, 0)
        r = reader.module_inventory(m, 0x10000)
        self.assertTrue(r['complete'])
        self.assertFalse(r['nonempty_complete'])

    def test_garrison_positive_name_is_not_capture(self):
        r = reader.module_inventory(module_fixture('GarrisonContain'), 0x10000)
        name = r['modules'][0]['native_name']
        self.assertIn(name, reader.FIRING_CONTAIN_NAMES)
        self.assertNotIn(name, reader.CAPTURE_ONLY_CONTAINS)

    def test_null_weapon_container_is_unknown(self):
        m = BytesMemory()
        m.word(0x1037c, 0)
        r = reader.weapon_matrix(m, 0x10000)
        self.assertFalse(r['matrix_complete'])
        self.assertFalse(r['configuration_absence_proven'])

    def test_index_five_still_reads_dormant_mode(self):
        r = reader.weapon_matrix(weapon_fixture(), 0x10000)
        self.assertTrue(r['matrix_complete'])
        self.assertEqual(r['slots'][0]['modes'][1]['asset_id'], '0x41872ecc')
        self.assertFalse(r['configuration_absence_proven'])

    def test_six_null_entries_do_not_prove_configuration_absence(self):
        m = weapon_fixture()
        m.word(0x54004, 0)
        r = reader.weapon_matrix(m, 0x10000)
        self.assertTrue(r['matrix_complete'])
        self.assertFalse(r['configuration_absence_proven'])

    def test_other_slot_class_is_unknown(self):
        m = weapon_fixture()
        m.word(0x52000, 0xc30000)
        self.assertFalse(reader.weapon_matrix(m, 0x10000)['matrix_complete'])

    def test_entry_backpointer_mismatch_is_unknown(self):
        m = weapon_fixture()
        m.word(0x55008, 0x52004)
        self.assertFalse(reader.weapon_matrix(m, 0x10000)['matrix_complete'])

    def test_same_frame_double_inventory_never_grants_exclusion(self):
        r = reader.sample_unit(unit_fixture(), 0x10000, 0x90000, 763, 0xc16ff13f, 0x60000)
        self.assertTrue(r['observation_verified'])
        self.assertTrue(r['facts']['no_contain_names_except_capture'])
        self.assertFalse(r['exclusion_granted'])
        self.assertEqual(r['classification'], 'unknown_keep_threat')

    def test_frame_change_fails_observation(self):
        m = unit_fixture()
        base_read = m.u32
        count = [0]
        def advancing(address):
            if address == 0x60050:
                count[0] += 1
                return 100 + count[0] - 1
            return base_read(address)
        m.u32 = advancing
        r = reader.sample_unit(m, 0x10000, 0x90000, 763, 0xc16ff13f, 0x60000)
        self.assertFalse(r['observation_verified'])
        self.assertFalse(r['checks']['same_frame'])

    def test_module_array_changes_between_passes_fail_observation(self):
        m = unit_fixture()
        base_read = m.u32
        count = [0]
        def changing(address):
            if address == 0x20000:
                count[0] += 1
                return 0x30000 if count[0] == 1 else 0
            return base_read(address)
        m.u32 = changing
        r = reader.sample_unit(m, 0x10000, 0x90000, 763, 0xc16ff13f, 0x60000)
        self.assertFalse(r['observation_verified'])
        self.assertFalse(r['checks']['double_pass_equal'])

    def test_wrong_owner_fails_observation(self):
        r = reader.sample_unit(unit_fixture(), 0x10000, 0x90004, 763, 0xc16ff13f, 0x60000)
        self.assertFalse(r['observation_verified'])
        self.assertFalse(r['checks']['expected_identity'])


if __name__ == '__main__':
    unittest.main()
