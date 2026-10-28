from pathlib import Path
import unittest
import xml.etree.ElementTree as E
from stage_commanders import q
from stage_macro_regions import generate_regions
from stage_macro_base_defense import generate_area_defense


class AreaDefenseCandidateTests(unittest.TestCase):
    def test_only_custom_east_tactic_changes_with_stock_native_micro_untouched(self):
        raw=(Path(__file__).resolve().parents[1]/'reports/macro-temple-map-20261028-v1/Maps5.map.inner').read_bytes()
        ident='57e668b4-4d89-43bd-bc92-0dd436f046ef'
        old,_=generate_regions(ident,3,[],raw);xml,report=generate_area_defense(ident,3,[],raw)
        before=E.fromstring(old);after=E.fromstring(xml)
        def normalize(node):
            node=E.fromstring(E.tostring(node))
            for child in node.iter():child.text=(child.text or '').strip() or None;child.tail=None
            return E.tostring(node)
        for node in before:
            match=next(n for n in after if n.tag==node.tag and n.get('id')==node.get('id'))
            if node.get('id','').endswith('_DeployDefense'):
                tactic=match.find(q('Tactic'));self.assertEqual(tactic.get('Tactic'),'StaticDefense')
                self.assertEqual(tactic.get('Distance'),'500')
                self.assertEqual(tactic.find(q('TeamTemplate')).get('MicroManager'),'DefenseMicroManager')
                self.assertFalse(tactic.find(q('TeamTemplate')).findall(q('CreateUnits')))
                self.assertEqual(normalize(node.find(q('Heuristic'))),normalize(match.find(q('Heuristic'))))
                self.assertEqual(match.find(q('TargetHeuristic')).get('TargetHeuristic'),'FriendlyLandStructureHeuristic')
            else:self.assertEqual(normalize(node),normalize(match))
        self.assertEqual(len(report['flags']),13);self.assertEqual(len(report['assets']),16)
        self.assertFalse(report['area_defense_field_verified']);self.assertFalse(report['area_defense_product_capability_granted'])


if __name__=='__main__':unittest.main()
