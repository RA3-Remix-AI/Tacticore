import unittest
import xml.etree.ElementTree as E
from stage_macro_policy import generate_policy
from stage_commanders import q

COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'


class MacroPolicyTests(unittest.TestCase):
    def test_unique_bounded_profile_and_only_macro_assets(self):
        xml,r=generate_policy(COMMANDER,3,[])
        self.assertEqual(len(r['assets']),14);self.assertEqual(len(r['consumers']),13)
        self.assertEqual(len(set(r['flags'].values())),13)
        self.assertTrue(all(v.startswith('/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_') for v in r['flags'].values()))
        self.assertFalse(r['product_capability_granted']);self.assertEqual(r['original_assets_replaced'],0)
        root=E.fromstring(xml)
        allowed={'Tags','Includes','AIBuildStateDefinition','AIStrategicStateDefinition','AIBudgetStateDefinition','AIPersonalityDefinition'}
        self.assertTrue(all(n.tag.split('}')[-1] in allowed for n in root))

    def test_airport_has_reactor_precondition_and_state_priority(self):
        xml,r=generate_policy(COMMANDER,3,[]);root=E.fromstring(xml)
        airport=root.find(q('AIBuildStateDefinition'));h=airport.find(q('Heuristic'))
        self.assertEqual(h.find(q('ConstantHeuristic')).get('Weight'),'100')
        self.assertTrue(any(c.get('PassIfExists')=='true' and c.find('.//'+q('IncludeThing')).text=='SovietPowerPlantAdvanced'
            for c in h.findall(q('ObjectOfTypeExistsHeuristic'))))

    def test_native_budgets_are_complete_and_mutually_exclusive(self):
        xml,r=generate_policy(COMMANDER,3,[])
        budgets=[c for c in r['consumers'] if c['domain']=='budget'];self.assertEqual(len(budgets),3)
        for budget in budgets:
            self.assertEqual(sum(budget['account_shares'].values()),100)
            self.assertEqual(budget['exclusive_group'],'budget_policy')

    def test_deployment_keeps_native_team_micro_and_stops_without_forced_home(self):
        xml,r=generate_policy(COMMANDER,3,[]);root=E.fromstring(xml)
        for state in root.findall(q('AIStrategicStateDefinition')):
            for tactic in state.findall(q('Tactic')):
                self.assertEqual(tactic.get('EndIfStateTurnsOff'),'true')
                self.assertEqual(tactic.get('EndBehavior'),'DISBAND')
                for team in tactic.findall(q('TeamTemplate')):
                    self.assertTrue(team.get('MicroManager'))
        deployments=[c for c in r['consumers'] if c['action'].startswith('deploy')]
        self.assertEqual(len(deployments),2)
        self.assertTrue(all(c['arbitrary_region_selection_supported'] is False for c in deployments))

    def test_existing_asset_collision_refused(self):
        _,r=generate_policy(COMMANDER,3,[])
        a=r['assets'][-1]
        with self.assertRaisesRegex(ValueError,'collision'):
            generate_policy(COMMANDER,3,[dict(type_id=int(a['type_id'],0),instance_id=int(a['instance_id'],0),name=a['name'])])


if __name__=='__main__':unittest.main()
