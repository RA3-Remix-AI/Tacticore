import copy
import unittest
import xml.etree.ElementTree as E

from stage_commanders import q
from stage_strategic_expansion_v1 import normalized
from stage_strategic_raid_v1 import generate, STOCK_PATH, STOCK_ID, STATE, FLAG, CANDIDATE_TARGET


class NativeRaidTests(unittest.TestCase):
    def test_native_target_recruitment_and_threat_rules_are_preserved(self):
        stock = E.parse(STOCK_PATH).getroot().find(q("AIStrategicStateDefinition") + "[@id='" + STOCK_ID + "']")
        root = E.Element(q("AssetDeclaration"))
        E.SubElement(root, q("AIPersonalityDefinition"), id="Commander")
        E.SubElement(root, q("AITargetingHeuristic"), id=CANDIDATE_TARGET, HighestPriorityEnemyPlayersOnly="false")
        report = dict(flags={}, assets=[], strategic_actions=["attackenemy"], consumers=[dict(action="attackenemy")])
        old = copy.deepcopy(report)
        xml, result = generate(E.tostring(root), report, stock)
        self.assertEqual(report, old)
        raid = E.fromstring(xml).find(q("AIStrategicStateDefinition"))
        self.assertEqual(raid.get("id"), STATE)
        self.assertEqual(raid.find(".//" + q("ScriptedFlagHeuristic")).get("FlagName"), FLAG)
        self.assertEqual(
            normalized(raid.find(".//" + q("TeamTemplate"))), normalized(stock.find(".//" + q("TeamTemplate")))
        )
        self.assertEqual(normalized(raid.find(q("TargetHeuristic"))), normalized(stock.find(q("TargetHeuristic"))))
        self.assertIsNone(raid.find(".//" + q("EnemyNearbyHeuristic")))
        self.assertIsNone(raid.find(".//" + q("TimerHeuristic")))
        self.assertEqual(
            normalized(raid.find(".//" + q("ObjectOfTypeExistsHeuristic"))),
            normalized(stock.find(".//" + q("ObjectOfTypeExistsHeuristic"))),
        )
        self.assertEqual(raid.find(q("Tactic")).get("EndIfStateTurnsOff"), "true")
        self.assertEqual(
            E.fromstring(xml).find(q("AITargetingHeuristic")).get("HighestPriorityEnemyPlayersOnly"), "true"
        )
        self.assertTrue(result["raid_native_task_preserved"])
        self.assertFalse(result["product_capability_granted"])


if __name__ == "__main__":
    unittest.main()
