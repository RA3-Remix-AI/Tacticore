import unittest
from unittest.mock import patch
import match_participants as module


class ParticipantTests(unittest.TestCase):
    def setUp(self):
        self.words = {
            0xCE8C9C: 0x1000,
            0x1038: 0x2000,
            0x103C: 0x3000,
            0x1040: 0x4000,
            0x2000: 0xC5BCE0,
            0x2020: 2,
            0x2090: 0,
        }
        self.memory = type(
            "Memory", (), {"u32": lambda obj, address: self.words.get(address, 0), "read": lambda *args: None}
        )()
        self.state = {
            "victory_conditions": {
                "participants": [{"player_index": 3, "player": "0x3000"}, {"player_index": 4, "player": "0x4000"}]
            }
        }
        self.registry = {"commanders": [{"assets": [{"instance_id": "0x1234"}]}]}
        self.identities = {
            0x3000: {"player_index": 3, "instance_id": "0x1234"},
            0x4000: {"player_index": 4, "instance_id": "0x5678"},
        }

    def verify(self):
        with (
            patch.object(module, "inspect_player", side_effect=lambda read, address: self.identities[address]),
            patch.object(module, "read_player_relation", return_value=getattr(self, "relation", "enemy")),
        ):
            return module.verify_two_ai(self.memory, self.state, self.registry, 3, 4)

    def test_two_ai_and_separate_observer_accepted(self):
        self.assertTrue(self.verify()["opponent_native_ai_verified"])

    def test_idle_human_combatant_rejected(self):
        self.state["victory_conditions"]["participants"][1] = {"player_index": 2, "player": "0x2000"}
        with self.assertRaises(ValueError):
            self.verify()

    def test_native_opponent_cannot_be_another_registered_model(self):
        self.identities[0x4000]["instance_id"] = "0x1234"
        with self.assertRaises(ValueError):
            self.verify()

    def test_stale_pointer_rejected(self):
        self.words[0x1040] = 0x5000
        with self.assertRaises(ValueError):
            self.verify()

    def test_observer_with_ai_controller_rejected(self):
        self.words[0x2090] = 0x9000
        with self.assertRaises(ValueError):
            self.verify()

    def test_extra_participant_rejected(self):
        self.state["victory_conditions"]["participants"].append({"player_index": 5, "player": "0x5000"})
        with self.assertRaises(ValueError):
            self.verify()

    def test_allied_ai_players_are_not_accepted_as_opponents(self):
        self.relation = "ally"
        with self.assertRaises(ValueError):
            self.verify()


class GeneralParticipantTests(unittest.TestCase):
    """Any seats and teams; the model seat and native opponents keep their identity checks."""

    def setUp(self):
        ParticipantTests.setUp(self)
        self.words[0x1044] = 0x5000
        self.state["victory_conditions"]["participants"].append({"player_index": 5, "player": "0x5000"})
        self.identities[0x5000] = {"player_index": 5, "instance_id": "0x6789"}
        self.relations = {
            (3, 4): "enemy",
            (4, 3): "enemy",
            (3, 5): "enemy",
            (5, 3): "enemy",
            (4, 5): "ally",
            (5, 4): "ally",
        }

    def verify(self):
        def relation(memory, address, target):
            index = 2 if address == 0x2000 else self.identities[address]["player_index"]
            return self.relations[(index, target)]

        with (
            patch.object(module, "inspect_player", side_effect=lambda read, address: self.identities[address]),
            patch.object(module, "read_player_relation", side_effect=relation),
        ):
            return module.verify_participants(self.memory, self.state, self.registry, 3)

    def add_human(self, relation):
        self.state["victory_conditions"]["participants"].append({"player_index": 2, "player": "0x2000"})
        other = "ally" if relation == "enemy" else "enemy"
        self.relations.update(
            {(3, 2): relation, (2, 3): relation, (2, 4): other, (4, 2): other, (2, 5): other, (5, 2): other}
        )

    def kinds(self, result):
        return {row["player_id"]: (row["kind"], row["relation"]) for row in result["participants"]}

    def test_ai_versus_two_allied_natives(self):
        result = self.verify()
        self.assertEqual(
            self.kinds(result), {3: ("model_ai", "self"), 4: ("native_ai", "enemy"), 5: ("native_ai", "enemy")}
        )
        self.assertEqual(result["alliances"], [[4, 5]])

    def test_free_for_all_has_no_enemy_alliance(self):
        self.relations[(4, 5)] = self.relations[(5, 4)] = "enemy"
        self.assertEqual(self.verify()["alliances"], [])

    def test_human_teammate_is_a_combatant(self):
        self.add_human("ally")
        self.assertEqual(self.kinds(self.verify())[2], ("human", "ally"))

    def test_human_opponent_is_a_combatant(self):
        self.add_human("enemy")
        self.assertEqual(self.kinds(self.verify())[2], ("human", "enemy"))

    def test_one_way_relation_is_rejected(self):
        self.relations[(5, 3)] = "ally"
        with self.assertRaises(ValueError):
            self.verify()

    def test_neutral_combatant_is_rejected(self):
        self.relations[(3, 5)] = self.relations[(5, 3)] = "neutral"
        with self.assertRaises(ValueError):
            self.verify()

    def test_second_native_cannot_be_another_model_commander(self):
        self.identities[0x5000]["instance_id"] = "0x1234"
        with self.assertRaises(ValueError):
            self.verify()

    def test_model_seat_must_run_the_registered_personality(self):
        self.identities[0x3000]["instance_id"] = "0x9999"
        with self.assertRaises(ValueError):
            self.verify()

    def test_model_seat_cannot_be_human(self):
        self.words.update({0x3000: 0xC5BCE0, 0x3020: 3, 0x3090: 0})
        with self.assertRaises(ValueError):
            self.verify()

    def test_all_allies_means_no_enemy(self):
        self.relations.update({(3, 4): "ally", (4, 3): "ally", (3, 5): "ally", (5, 3): "ally"})
        with self.assertRaises(ValueError):
            self.verify()


class OneVsTwoResultTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "victory_conditions": {
                "participants": [
                    {"player_index": player, "manager_index": slot} for slot, player in enumerate((3, 4, 5))
                ]
            },
            "result_records": [
                {"native_index": slot, "victory_frame": 0, "defeat_frame": 0, "quit_frame": 0} for slot in range(6)
            ],
        }

    def result(self):
        return module.controlled_match_result(self.state, 3, (4, 5))

    def test_first_enemy_defeat_does_not_end_the_commanders_match(self):
        self.state["result_records"][1]["defeat_frame"] = 100
        result = self.result()
        self.assertFalse(result["terminal"])
        self.assertEqual(result["remaining_opponents"], 1)

    def test_both_enemy_defeats_await_controlled_victory(self):
        for row in self.state["result_records"][1:3]:
            row["defeat_frame"] = 100
        self.assertFalse(self.result()["terminal"])
        self.assertTrue(self.result()["all_opponents_defeated"])

    def test_controlled_victory_ends_the_match(self):
        self.state["result_records"][0]["victory_frame"] = 100
        self.assertTrue(self.result()["terminal"])
        self.assertEqual(self.result()["controlled_outcome"], "victory")

    def test_controlled_defeat_ends_the_match(self):
        self.state["result_records"][0]["defeat_frame"] = 100
        self.assertEqual(self.result()["controlled_outcome"], "defeat")

    def test_observer_or_unused_slot_does_not_end_the_match(self):
        self.state["result_records"][5]["defeat_frame"] = 100
        self.assertFalse(self.result()["terminal"])

    def test_allied_human_is_part_of_the_admitted_match(self):
        self.state["victory_conditions"]["participants"].append({"player_index": 2, "manager_index": 3})
        result = module.controlled_match_result(self.state, 3, (4, 5), participant_ids=(2, 3, 4, 5))
        self.assertIn("2", result["players"])
        with self.assertRaises(ValueError):
            self.result()

    def test_duplicate_result_mapping_is_rejected(self):
        self.state["victory_conditions"]["participants"][2]["manager_index"] = 1
        with self.assertRaises(ValueError):
            self.result()


if __name__ == "__main__":
    unittest.main()
