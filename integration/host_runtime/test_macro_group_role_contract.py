import unittest
from integration.host_runtime.macro_group_role_contract import group_role_catalog_overrides,ROLE_GOALS,ROLE_FAMILIES
from integration.host_runtime.macro_base_defense_scope import defense_catalog_override


class GroupRoleContractTests(unittest.TestCase):
    def test_role_catalog_does_not_promise_micro_or_task_success(self):
        catalog=group_role_catalog_overrides()
        self.assertEqual(catalog['deploydefense'],defense_catalog_override()['deploydefense'])
        self.assertEqual(set(catalog),{'deploydefense','regroup','withdraw','reinforce'})
        self.assertEqual(ROLE_FAMILIES['reinforce'],'reactive_defense')
        for action,goal in ROLE_GOALS.items():
            self.assertEqual(catalog[action]['goal'],goal)
            self.assertEqual(catalog[action]['maximum_duration_seconds'],60)
            self.assertFalse(catalog[action]['arrival_and_mission_success_guaranteed'])
            self.assertFalse(catalog[action]['arbitrary_unit_selection_supported'])
        self.assertTrue(catalog['withdraw']['requires_existing_forward_force'])


if __name__=='__main__':unittest.main()
