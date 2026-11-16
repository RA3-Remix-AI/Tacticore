"""Strategic timing changes preserve complete native execution definitions."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as E

from stage_commanders import q
from stage_strategic_expansion_v1 import normalized
import stage_strategic_timing_v1 as timing


class StrategicTiming(unittest.TestCase):
    def test_only_external_expansion_timing_and_native_raid_tactic_change(self):
        baseline = Path(__file__).parent / 'staging/strategic-raid-20261115-v5'
        stock = E.parse(timing.STOCK_PATH).getroot().find(
            q('AIStrategicStateDefinition') + "[@id='" + timing.STOCK_ID + "']")
        old = E.parse(baseline / 'MacroProbe.xml').getroot()
        xml, report = timing.generate((baseline / 'MacroProbe.xml').read_bytes(),
                                     json.loads((baseline / 'build-report.json').read_text()), stock)
        new = E.fromstring(xml)
        changed = {node.get('id') for node in new
                   if normalized(node) != normalized(next(item for item in old
                       if item.tag == node.tag and item.get('id') == node.get('id')))}
        self.assertEqual(changed, {timing.EXPANSION, timing.RAID})
        expansion = new.find(q('AIStrategicStateDefinition') + "[@id='" + timing.EXPANSION + "']")
        before = old.find(q('AIStrategicStateDefinition') + "[@id='" + timing.EXPANSION + "']")
        self.assertEqual(normalized(expansion.find(q('Tactic'))), normalized(before.find(q('Tactic'))))
        self.assertIsNone(expansion.find('.//' + q('OpeningMoveHeuristic')))
        self.assertIsNone(expansion.find('.//' + q('TimeSinceLastExpansionHeuristic')))
        self.assertIsNotNone(expansion.find('.//' + q('EnemyNearbyHeuristic')))
        raid = new.find(q('AIStrategicStateDefinition') + "[@id='" + timing.RAID + "']")
        tactic = raid.find(q('Tactic'))
        self.assertEqual(tactic.attrib.pop('EndIfStateTurnsOff'), 'true')
        self.assertEqual(normalized(tactic), normalized(stock.find(q('Tactic'))))
        self.assertFalse(tactic.findall('.//' + q('CreateUnits')))
        self.assertFalse(report['product_capability_granted'])


if __name__ == '__main__':
    unittest.main()
