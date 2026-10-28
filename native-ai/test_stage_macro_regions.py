from pathlib import Path
import unittest
import xml.etree.ElementTree as E
from stage_commanders import q
from stage_macro_policy import generate_policy
from stage_macro_regions import generate_regions
from read_map_waypoints import starting_waypoints

class RegionStageTests(unittest.TestCase):
    def setUp(self):
        self.raw=(Path(__file__).resolve().parents[1]/'reports/macro-temple-map-20261028-v1/Maps5.map.inner').read_bytes()

    def test_public_waypoint_names_and_coordinates_parse_from_both_official_versions(self):
        points=starting_waypoints(self.raw)
        self.assertEqual([p['name'] for p in points],['Player_1_Start','Player_2_Start'])
        other=(Path(__file__).resolve().parents[1]/'reports/macro-temple-map-20261028-v1/MapsMultiplayer.map.inner').read_bytes()
        self.assertEqual(points,starting_waypoints(other))
        with self.assertRaises(ValueError):starting_waypoints(self.raw[:900])

    def test_only_deployment_custom_states_change_and_native_micro_stays_original(self):
        c='57e668b4-4d89-43bd-bc92-0dd436f046ef';old,_=generate_policy(c,3,[])
        xml,r=generate_regions(c,3,[],self.raw);a=E.fromstring(old);b=E.fromstring(xml)
        self.assertEqual(len(r['assets']),16);self.assertEqual(len(r['flags']),13)
        for target in b.findall(q('AITargetingHeuristic')):
            self.assertEqual(target.get('RequireUniqueTarget'),'false')
        def normalized(node):
            node=E.fromstring(E.tostring(node))
            for x in node.iter():x.text=(x.text or '').strip() or None;x.tail=None
            return E.tostring(node)
        for original in a:
            if original.tag==q('AIStrategicStateDefinition') and original.get('id','').endswith(('DeployAttack','DeployDefense')):continue
            match=next(n for n in b if n.tag==original.tag and n.get('id')==original.get('id'))
            self.assertEqual(normalized(original),normalized(match))
        for consumer in r['consumers']:
            if not consumer['action'].startswith('deploy'):continue
            self.assertFalse(consumer['field_verified']);self.assertFalse(consumer['unit_orders_exposed'])
            state=next(n for n in b if n.get('id')==consumer['state'].split(':')[1])
            tactic=state.find(q('Tactic'));self.assertEqual(tactic.get('EndIfStateTurnsOff'),'true')
            self.assertEqual(tactic.find(q('TeamTemplate')).get('MicroManager'),'GrowingAttacksMicroManager_MEDIUM')
            self.assertEqual(tactic.find(q('TeamTemplate')).get('Priority'),'HIGH')
            self.assertFalse(tactic.findall('.//'+q('CreateUnits')))

if __name__=='__main__':unittest.main()
