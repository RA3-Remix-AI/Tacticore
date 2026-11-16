"""A four-player map cannot inherit a two-player match descriptor."""
import unittest

from host_runtime.contracts import ContractError
from host_runtime.native6_scenarios import FOUR_PLAYER_1V2, INFINITY_ISLE, scenario_for_session


class OneVsTwoScenarioTests(unittest.TestCase):
    def setUp(self):
        self.scenario = dict(map_id=FOUR_PLAYER_1V2.map_id,
                             origin_region=FOUR_PLAYER_1V2.own_region, faction='Soviet',
                             participant_count=3, opponent_player_indices=[4, 5],
                             opponents_allied=True)

    def test_explicit_one_vs_two_descriptor(self):
        self.assertEqual(scenario_for_session(self.scenario), FOUR_PLAYER_1V2)
        from host_runtime.macro_group_role_contract import native6_group_role_catalog_overrides
        catalog = native6_group_role_catalog_overrides(FOUR_PLAYER_1V2.own_region)
        self.assertEqual(catalog['deploydefense']['target_region'], FOUR_PLAYER_1V2.own_region)

    def test_incorrect_alliance_count_or_players_rejected(self):
        for field, value in [('opponents_allied', False), ('participant_count', 2),
                             ('participant_count', 3.), ('opponent_player_indices', [4]),
                             ('opponent_player_indices', [4., 5]), ('opponent_player_indices', [4, 6])]:
            with self.subTest(field=field, value=value), self.assertRaises(ContractError):
                scenario_for_session(dict(self.scenario, **{field: value}))

    def test_incorrect_own_start_rejected(self):
        with self.assertRaises(ContractError):
            scenario_for_session(dict(self.scenario, origin_region='region_8_3'))

    def test_infinity_does_not_inherit_extra_opponent(self):
        scenario = dict(self.scenario, map_id=INFINITY_ISLE.map_id, origin_region=INFINITY_ISLE.own_region)
        with self.assertRaises(ContractError):
            scenario_for_session(scenario)


if __name__ == '__main__':
    unittest.main()
