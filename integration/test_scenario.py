"""The runtime-derived match scenario works for any map and seat layout."""

import unittest

from host_runtime.contracts import ContractError
from host_runtime.scenario import (
    MatchScenario,
    ScenarioPlayer,
    assign_teams,
    derive_scenario,
    own_base_point,
    region_for_point,
    start_by_vote,
)

COMMANDER = "57e668b4-4d89-43bd-bc92-0dd436f046ef"
FOUR_STARTS = [
    dict(name="Player_1_Start", xyz=[700.0, 700.0, 0.0]),
    dict(name="Player_2_Start", xyz=[3800.0, 700.0, 0.0]),
    dict(name="Player_3_Start", xyz=[700.0, 3800.0, 0.0]),
    dict(name="Player_4_Start", xyz=[3800.0, 3800.0, 0.0]),
]


def participant(player_id, kind, relation):
    return dict(player_id=player_id, kind=kind, relation=relation)


def derive(participants, alliances=(), starts=FOUR_STARTS, own=(3700.0, 800.0), allied_starts=(), **kwargs):
    return derive_scenario(
        map_id="some_custom_map",
        model_player_id=3,
        participants=participants,
        alliances=alliances,
        own_point=own,
        starts=starts,
        allied_starts=allied_starts,
        **kwargs,
    )


class RegionTests(unittest.TestCase):
    def test_regions_are_512_unit_cells(self):
        self.assertEqual(region_for_point(4404.1, 2016.0), "region_8_3")
        self.assertEqual(region_for_point(0.0, 511.9), "region_0_0")

    def test_invalid_points_are_rejected(self):
        for point in ((-1.0, 5.0), (float("nan"), 1.0), (True, 1.0), (1e9, 1.0)):
            with self.subTest(point=point), self.assertRaises(ContractError):
                region_for_point(*point)

    def test_own_base_requires_one_living_construction_yard(self):
        yard = dict(type_hash="0xc16ff13f", hp=100.0, xyz=[4404.0, 2016.0, 0.0])
        self.assertEqual(own_base_point(dict(own_objects=[yard])), (4404.0, 2016.0))
        for census in (dict(own_objects=[]), dict(own_objects=[yard, yard]), dict(own_objects=[dict(yard, hp=0.0)])):
            with self.subTest(census=census), self.assertRaises(ContractError):
                own_base_point(census)

    def test_start_vote_uses_most_objects(self):
        points = [(800.0, 3700.0), (900.0, 3600.0), (3700.0, 3700.0)]
        self.assertEqual(start_by_vote(points, FOUR_STARTS), "Player_3_Start")
        self.assertIsNone(start_by_vote([], FOUR_STARTS))


class TeamTests(unittest.TestCase):
    def test_allied_enemies_share_a_team_and_ffa_enemies_do_not(self):
        relations = {2: "ally", 4: "enemy", 5: "enemy"}
        self.assertEqual(assign_teams(3, relations, [[4, 5]]), {3: 1, 2: 1, 4: 2, 5: 2})
        self.assertEqual(assign_teams(3, relations, []), {3: 1, 2: 1, 4: 2, 5: 3})

    def test_neutral_relation_is_rejected(self):
        with self.assertRaises(ContractError):
            assign_teams(3, {4: "neutral"}, [])


class ModeTests(unittest.TestCase):
    def test_ai_versus_one_native_on_a_two_player_map(self):
        starts = FOUR_STARTS[:2]
        scenario = derive(
            [participant(3, "model_ai", "self"), participant(4, "native_ai", "enemy")],
            starts=starts,
            observer_player_ids=(2,),
        )
        self.assertEqual(scenario.mode, "ai_vs_native")
        self.assertEqual(scenario.own_region, "region_7_1")
        self.assertEqual(scenario.own_start_waypoint, "Player_2_Start")
        self.assertEqual(scenario.enemy_regions, ("region_1_1",))
        self.assertTrue(scenario.enemy_regions_exact)
        self.assertEqual(dict(scenario.regional_action_regions)["deployattack"], "region_1_1")
        self.assertEqual(scenario.observer_player_ids, (2,))

    def test_human_with_ai_versus_two_natives(self):
        scenario = derive(
            [
                participant(2, "human", "ally"),
                participant(3, "model_ai", "self"),
                participant(4, "native_ai", "enemy"),
                participant(5, "native_ai", "enemy"),
            ],
            alliances=[[4, 5]],
            allied_starts=("Player_1_Start",),
        )
        self.assertEqual(scenario.mode, "human_with_ai")
        self.assertEqual(scenario.ally_player_ids, (2,))
        self.assertEqual(scenario.enemy_player_ids, (4, 5))
        self.assertTrue(scenario.enemies_allied)
        self.assertEqual(scenario.enemy_regions, ("region_1_7", "region_7_7"))
        self.assertTrue(scenario.enemy_regions_exact)
        public = scenario.to_public_dict()
        self.assertEqual(public["mode"], "human_with_ai")
        self.assertEqual(public["players"][0], dict(player_id=2, kind="human", team=1, difficulty=None, faction=None))
        self.assertEqual(public["players"][1]["faction"], "Soviet")

    def test_human_versus_model_ai(self):
        scenario = derive(
            [participant(2, "human", "enemy"), participant(3, "model_ai", "self")], starts=FOUR_STARTS[:2]
        )
        self.assertEqual(scenario.mode, "human_vs_ai")
        self.assertEqual(scenario.enemy_player_ids, (2,))

    def test_humans_on_both_sides_is_other(self):
        scenario = derive(
            [
                participant(1, "human", "ally"),
                participant(2, "human", "enemy"),
                participant(3, "model_ai", "self"),
                participant(4, "native_ai", "enemy"),
            ]
        )
        self.assertEqual(scenario.mode, "other")

    def test_unused_starts_make_enemy_regions_candidates_only(self):
        scenario = derive([participant(3, "model_ai", "self"), participant(4, "native_ai", "enemy")])
        self.assertEqual(len(scenario.enemy_regions), 3)
        self.assertFalse(scenario.enemy_regions_exact)
        self.assertNotIn("deployattack", dict(scenario.regional_action_regions))

    def test_home_waypoint_actions_are_withheld_away_from_player_2_start(self):
        scenario = derive(
            [participant(3, "model_ai", "self"), participant(4, "native_ai", "enemy")], own=(800.0, 3700.0)
        )
        self.assertEqual(scenario.own_start_waypoint, "Player_3_Start")
        self.assertEqual(scenario.withheld_actions, ("regroup", "withdraw"))
        self.assertEqual({action for action, _ in scenario.regional_action_regions}, {"deploydefense", "reinforce"})

    def test_model_must_be_present_and_have_an_enemy(self):
        with self.assertRaises(ContractError):
            derive([participant(4, "native_ai", "enemy")])
        with self.assertRaises(ContractError):
            derive([participant(3, "model_ai", "self"), participant(4, "native_ai", "ally")])

    def test_difficulty_must_be_known_value_or_none(self):
        ScenarioPlayer(4, "native_ai", 2, difficulty="brutal")
        with self.assertRaises(ContractError):
            ScenarioPlayer(4, "native_ai", 2, difficulty="insane")


class SessionTests(unittest.TestCase):
    def scenario(self):
        return derive(
            [
                participant(2, "human", "ally"),
                participant(3, "model_ai", "self"),
                participant(4, "native_ai", "enemy"),
                participant(5, "native_ai", "enemy"),
            ],
            alliances=[[4, 5]],
            allied_starts=("Player_1_Start",),
        )

    def test_session_round_trip(self):
        scenario = self.scenario()
        session = scenario.to_session_dict(COMMANDER)
        self.assertEqual(session["opponent_player_indices"], [4, 5])
        self.assertEqual(session["participant_count"], 4)
        self.assertEqual(MatchScenario.from_session(session), scenario)

    def test_flat_fields_cannot_disagree_with_the_match_block(self):
        session = self.scenario().to_session_dict(COMMANDER)
        for key, value in (
            ("origin_region", "region_0_0"),
            ("opponent_player_indices", [4]),
            ("participant_count", 3),
            ("computer_player_index", 4),
        ):
            with self.subTest(key=key), self.assertRaises(ContractError):
                MatchScenario.from_session(dict(session, **{key: value}))
        match = dict(session["match"], mode="ai_vs_native")
        with self.assertRaises(ContractError):
            MatchScenario.from_session(dict(session, match=match))

    def test_legacy_one_versus_two_descriptor(self):
        legacy = dict(
            map_id="map_mp_4_stewart_1",
            commander_id=COMMANDER,
            computer_player_index=3,
            opponent_player_index=4,
            observer_player_index=2,
            participant_count=3,
            faction="Soviet",
            origin_region="region_7_1",
            opponent_player_indices=[4, 5],
            opponents_allied=True,
        )
        scenario = MatchScenario.from_session(legacy)
        self.assertEqual(scenario.enemy_player_ids, (4, 5))
        self.assertTrue(scenario.enemies_allied)
        self.assertEqual(scenario.mode, "ai_vs_native")
        self.assertEqual(scenario.observer_player_ids, (2,))
        self.assertIsNone(scenario.own_start_waypoint)
        for change in ({"participant_count": 2}, {"opponents_allied": False}, {"opponent_player_index": 5}):
            with self.subTest(change=change), self.assertRaises(ContractError):
                MatchScenario.from_session(dict(legacy, **change))

    def test_legacy_duel_descriptor(self):
        legacy = dict(
            map_id="map_mp_2_rao1",
            commander_id=COMMANDER,
            computer_player_index=3,
            opponent_player_index=4,
            participant_count=2,
            origin_region="region_7_4",
        )
        scenario = MatchScenario.from_session(legacy)
        self.assertEqual(scenario.display_map, "InfinityIsle")
        self.assertEqual(scenario.enemy_player_ids, (4,))


if __name__ == "__main__":
    unittest.main()
