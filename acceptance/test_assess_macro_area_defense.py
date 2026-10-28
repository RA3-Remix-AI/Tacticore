import copy
import unittest
from assess_macro_area_defense import task_effect


def samples():
    return [dict(frame=f,state_scores={'flag':dict(group='state',score=100)},runtimes=[
        dict(group='state',native_execution_active=True,native_tactic_family='static_defense',address='task',
            owned_groups=[dict(found=True,all_members_resolved=True,native_id=1,members=[
                dict(owner='own',thing_id=9,xyz=[100,100,0])])])]) for f in (100,220,340)]


class AreaDefenseTests(unittest.TestCase):
    def test_native_defense_group_already_in_area_requires_no_move_orders(self):
        result=task_effect(samples(),'flag','own',90,400,[100,100],'static_defense')
        self.assertTrue(result['bounded_area_effect_verified'])
        self.assertEqual(result['own_members_progressing_toward_area'],0)
        self.assertFalse(result['combat_success_verified'])

    def test_state_score_without_owned_group_is_insufficient(self):
        rows=samples()
        for row in rows:row['runtimes'][0]['owned_groups']=[]
        self.assertFalse(task_effect(rows,'flag','own',90,400,[100,100],'static_defense')['bounded_area_effect_verified'])

    def test_foreign_owner_and_other_native_family_rejected(self):
        rows=samples();rows[0]['runtimes'][0]['owned_groups'][0]['members'][0]['owner']='foreign'
        with self.assertRaisesRegex(ValueError,'foreign_member'):task_effect(rows,'flag','own',90,400,[100,100],'static_defense')
        rows=samples();rows[0]['runtimes'][0]['native_tactic_family']='simple_attack'
        with self.assertRaisesRegex(ValueError,'native_family'):task_effect(rows,'flag','own',90,400,[100,100],'static_defense')


if __name__=='__main__':unittest.main()
