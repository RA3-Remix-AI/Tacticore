import unittest
from .contracts import ContractError
from .macro_regions import RegionalFeedback,compact_regional_feedback
from .macro_group_role_contract import ROLE_GOALS,ROLE_FAMILIES
from .test_macro_base_defense import defense_sample


def role_sample(action,frame=1500,x=4410):
    obs,view,builder=defense_sample(frame)
    obs['runtimes'][-1]['native_tactic_family']=ROLE_FAMILIES[action]
    obs['runtimes'][-1]['owned_groups'][0]['members'][0]['xyz']=[x,2016,0]
    return obs,view,builder


def tracker(action,frame=1500,x=4410):
    obs,view,_=role_sample(action,frame,x)
    return RegionalFeedback(obs,view,(action,'region_8_3','private-region',4404,2016),
        family=ROLE_FAMILIES[action],goal=ROLE_GOALS[action])


class GroupRoleFeedbackTests(unittest.TestCase):
    def test_regroup_and_reinforce_return_separate_bounded_effects(self):
        regroup=compact_regional_feedback(tracker('regroup').public(),100.)
        reinforce=compact_regional_feedback(tracker('reinforce').public(),100.)
        self.assertEqual(regroup['groups_near_home_region'],1)
        self.assertEqual(reinforce['defender_groups_near_infrastructure'],1)
        self.assertEqual(reinforce['native_tactic_family'],'reactive_defense')
        self.assertFalse(regroup['mission_success_verified']);self.assertFalse(reinforce['mission_success_verified'])

    def test_withdrawal_requires_initial_forward_position_and_later_home_progress(self):
        t=tracker('withdraw',1500,3500);obs,view,_=role_sample('withdraw',1515,3600);t.observe(obs,view)
        value=compact_regional_feedback(t.public(),101.)
        self.assertEqual(value['withdrawing_native_groups'],1);self.assertEqual(value['groups_near_home_region'],0)
        self.assertFalse(value['arrival_verified'])
        near=tracker('withdraw',1500,4200);obs,view,_=role_sample('withdraw',1515,4300);near.observe(obs,view)
        self.assertEqual(near.public()['withdrawing_native_groups'],0)

    def test_pre_ack_or_expired_movement_cannot_supply_effect(self):
        t=tracker('withdraw',1500,3500);t.bind_native_window(1510,1600)
        obs,view,_=role_sample('withdraw',1510,3500);t.observe(obs,view)
        obs,view,_=role_sample('withdraw',1600,3600);t.observe(obs,view)
        self.assertEqual(t.public()['withdrawing_native_groups'],0)
        self.assertEqual(t.public()['moved_native_groups'],0)

    def test_new_role_cannot_reuse_point_goal_or_foreign_family(self):
        obs,view,_=role_sample('withdraw')
        with self.assertRaisesRegex(ContractError,'goal_family_binding'):
            RegionalFeedback(obs,view,('withdraw','region_8_3','private-region',4404,2016))
        value=tracker('reinforce').public();value['native_tactic_family']='simple_attack'
        with self.assertRaisesRegex(ContractError,'group_role_feedback_invalid'):compact_regional_feedback(value,100.)


if __name__=='__main__':unittest.main()
