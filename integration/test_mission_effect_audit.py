"""Offline replay of recorded raw evidence; no model or game commands."""
import json
import unittest

from audit_mission_effects import audit
import test_continuous_native_binding as native_fixture


class WholeMatchEffects(unittest.TestCase):
    def setUp(self):
        self.fixture = native_fixture.RecordedMissionBinding()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        f = self.fixture
        self.output = f.run / 'battle-host'
        self.output.mkdir()
        self.session = dict(f.host.session,
                            scenario=dict(commander_id=f.host.binding.commander_id))
        self.identity = dict(session_id=self.session['session_id'], pid=self.session['pid'],
                            binding=dict(commander_id=f.host.binding.commander_id,
                                         personality_binding_verified=True),
                            native=dict(player_index=3))
        f.entry.update(seq=1, terminal=True, mission_protocol='continuous_tactical_v1',
                       purpose='main_attack')
        self.receipt = dict(f.receipt, **{key: f.entry[key] for key in
            ('task_id', 'command_id', 'seq', 'module', 'purpose', 'object_ids')},
            session_id=self.session['session_id'], commander_id=f.host.binding.commander_id,
            player_id=3)
        self.write()

    def write(self):
        f = self.fixture
        for name, value in [('identity.json', self.identity),
                            ('tactical-status.json', dict(ledger=[self.receipt])),
                            ('tactical-dispatch-ledger.json', {f.entry['task_id']: f.entry})]:
            (self.output / name).write_text(json.dumps(value), encoding='utf-8')

    def test_one_recorded_effect_does_not_establish_all_three_purposes(self):
        result = audit(self.session)
        self.assertFalse(result['all_three_actual_effects_verified'])
        self.assertEqual(result['total_verified_damage'], 5)
        self.assertEqual(result['sustained_mission_count'], 0)
        self.assertFalse(result['verified_missions'][0]['sustained_engagement_verified'])
        self.assertEqual(result['verified_missions'][0]['observed_reload_count'], 0)
        self.assertEqual(len(result['missing_purposes']), 2)

    def test_cached_success_cannot_replace_raw_proof(self):
        self.fixture.entry['mission_qualification'] = dict(source_damage_amount=99999,
                                                         combined_arms_verified=True)
        self.receipt['unit_results'] = []
        self.write()
        result = audit(self.session)
        self.assertEqual(result['total_verified_damage'], 0)
        self.assertEqual(len(result['unproved_completion_claims']), 1)

    def test_other_session_identity_is_rejected(self):
        self.identity['session_id'] = 'foreign'
        self.write()
        with self.assertRaisesRegex(ValueError, 'identity'):
            audit(self.session)


if __name__ == '__main__':
    unittest.main()
