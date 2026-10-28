import copy
import unittest
from assess_macro_base_defense import defense_presence


def sample(frame):
    return dict(frame=frame,state_scores={'flag':dict(group='own_state',score=100)},
        construction_feedback=dict(enemy_details_read=False,own_objects=[dict(type_hash='0xc16ff13f',hp=1000,xyz=[4400,2000,0])]),
        runtimes=[dict(group='own_state',native_execution_active=True,native_tactic_family='static_defense',
            owned_groups=[dict(native_id=1,found=True,all_members_resolved=True,
                members=[dict(thing_id=1,owner='own',xyz=[4400,2100,0])])])])


class BaseDefenseTests(unittest.TestCase):
    def test_stationed_defender_needs_no_extra_move_or_combat_gate(self):
        result=defense_presence([sample(f) for f in (110,120,130)],'flag','own',100,200)
        self.assertTrue(result['native_defender_presence_near_own_infrastructure_verified'])
        self.assertTrue(result['effect_within_model_maximum_60_seconds'])
        self.assertFalse(result['mission_success_verified'])

    def test_task_without_resolved_own_members_and_late_effect_do_not_qualify(self):
        rows=[sample(f) for f in (110,120,130)]
        for r in rows:r['runtimes'][0]['owned_groups']=[]
        self.assertFalse(defense_presence(rows,'flag','own',100,200)['native_defender_presence_near_own_infrastructure_verified'])
        result=defense_presence([sample(f) for f in (1100,1120,1140)],'flag','own',100,1200)
        self.assertFalse(result['effect_within_model_maximum_60_seconds'])

    def test_foreign_member_rejected_before_accepting_presence(self):
        row=sample(110);row['runtimes'][0]['owned_groups'][0]['members'][0]['owner']='enemy'
        with self.assertRaisesRegex(ValueError,'foreign_defender'):defense_presence([row],'flag','own',100,200)


if __name__=='__main__':unittest.main()
