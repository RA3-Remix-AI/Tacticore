"""Negative boundaries using saved own rows; visibility below is synthetic only."""
import copy
import json
from pathlib import Path
import unittest
import origin350_exact_structure_classification as c


class ClassificationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((Path(__file__).parent / 'origin350-own-inventory-fresh01.json')
                                .read_text(encoding='utf-8'))
        cls.rows = [r for r in cls.report['units'] if r['role'] == 'exact_four_structure']

    def fixture(self, index=0, visibility=True):
        row = copy.deepcopy(self.rows[index]); ident = row['first']['identity']
        v = dict(ident, source='VisibilityCollector.private_targets',
                 session_id=self.report['session_id'], pid=self.report['pid'],
                 observed_frame=row['frame_start'], observer_player_id=3,
                 owner_player_id=4, relation='enemy', full_footprint_verified=True,
                 runtime_stealth_safe=True, fixture_is_synthetic=True)
        return c.facts_from_sample(self.report, row, v if visibility else None)

    def both(self, facts, mutate):
        row = facts['sample']
        mutate(row['first'])
        row['second'] = copy.deepcopy(row['first'])
        row['final_identity'] = copy.deepcopy(row['first']['identity'])

    def test_four_independent_frames_preserved(self):
        self.assertNotEqual(self.report['frame_start'], self.report['frame_end'])
        for i in range(4):
            self.assertTrue(c.instance_evidence(self.fixture(i))['verified'])

    def test_matching_synthetic_fov_only_narrow_result(self):
        for i in range(4):
            r = c.classify(self.fixture(i))
            self.assertTrue(r['exclude_from_immediate_direct_fire_only'])
            self.assertFalse(r['safe_origin_verified'])
            self.assertFalse(r['zero_occupants_proven'])
            self.assertFalse(r['capability_granted'])
            self.assertTrue(r['conditional_hazards'])
            self.assertEqual(r['radius_unchanged'], 350)

    def test_real_own_rows_without_enemy_fov_are_no_permit(self):
        self.assertFalse(c.classify(self.fixture(visibility=False))['exclude_from_immediate_direct_fire_only'])

    def test_wrong_package(self):
        f = self.fixture(); f['package_sha256'] = '0' * 64
        self.assertFalse(c.classify(f)['exclude_from_immediate_direct_fire_only'])

    def test_mobile_type_remains_threat(self):
        f = self.fixture()
        self.both(f, lambda p: p['identity'].update(type_hash='0x19ab11af'))
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_added_garrison_even_with_container_zero_remains_threat(self):
        f = self.fixture()
        def add(p):
            m = copy.deepcopy(p['module_inventory']['modules'][-1])
            m.update(native_name='GarrisonContain', index=len(p['module_inventory']['modules']),
                     module='0x7770000')
            p['module_inventory']['modules'].append(m)
            p['module_inventory']['terminator_index'] += 1
        self.both(f, add)
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_complex_getter(self):
        f = self.fixture()
        self.both(f, lambda p: p['module_inventory']['modules'][0].update(getter_bytes='e900000000c3'))
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_nonzero_weapon_reference(self):
        f = self.fixture()
        self.both(f, lambda p: p['identity'].update(weapon_container='0x7650000'))
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_changed_second_pass(self):
        f = self.fixture(); f['sample']['second']['identity']['hp'] -= 1
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_stale_fov(self):
        f = self.fixture(); f['current_visibility']['observed_frame'] -= 1
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_owner_mismatch(self):
        f = self.fixture(); f['current_visibility']['owner'] = '0x5550000'
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_partial_footprint(self):
        f = self.fixture(); f['current_visibility']['full_footprint_verified'] = False
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_relation_not_enemy(self):
        f = self.fixture(); f['current_visibility']['relation'] = 'self'
        self.assertTrue(c.classify(f)['immediate_direct_fire_threat'])

    def test_malformed_input(self):
        self.assertTrue(c.classify(None)['immediate_direct_fire_threat'])


if __name__ == '__main__':
    unittest.main()
