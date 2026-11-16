"""Economic raids reuse the existing executor without new unit templates."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as E

from stage_commanders import q
from stage_strategic_expansion_v1 import normalized
import stage_strategic_raid_target_v1 as raid


class RaidTarget(unittest.TestCase):
    def test_only_raid_state_changes_and_executor_is_identical(self):
        baseline = Path(__file__).parent / 'staging/strategic-timing-20261116-v4'
        old = E.parse(baseline / 'MacroProbe.xml').getroot()
        xml, report, tactic_sha = raid.generate((baseline / 'MacroProbe.xml').read_bytes(),
            json.loads((baseline / 'build-report.json').read_text()))
        new = E.fromstring(xml)
        changed = {node.get('id') for node in new
                   if normalized(node) != normalized(next(item for item in old
                       if item.tag == node.tag and item.get('id') == node.get('id')))}
        self.assertEqual(changed, {raid.RAID})
        state = new.find(q('AIStrategicStateDefinition') + "[@id='" + raid.RAID + "']")
        attack = old.find(q('AIStrategicStateDefinition') + "[@id='" + raid.ATTACK + "']")
        self.assertEqual(normalized(state.find(q('Tactic'))), normalized(attack.find(q('Tactic'))))
        self.assertIsNone(state.find('.//' + q('ObjectOfTypeExistsHeuristic')))
        self.assertFalse(state.findall('.//' + q('CreateUnits')))
        self.assertEqual(state.find(q('TargetHeuristic')).get('TargetHeuristic'), 'SafestToGroundHarvesterHeuristic')
        self.assertEqual(tactic_sha, '8579781576b71f82ff944b609fe7b6d6b9458c8c9d4b82e072e75fd644509e41')
        self.assertFalse(report['product_capability_granted'])


if __name__ == '__main__':
    unittest.main()
