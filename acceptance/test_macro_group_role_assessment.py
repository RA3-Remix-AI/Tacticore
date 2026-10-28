import unittest
from assess_macro_group_roles import tracks


def sample(frame,*,census_frame=None,owner=3):
    return dict(frame=frame,state_scores={'role':dict(score=1,group='own-state')},
        construction_feedback=dict(frame=frame if census_frame is None else census_frame,enemy_details_read=False,own_objects=[]),
        runtimes=[dict(group='own-state',native_execution_active=True,native_tactic_family='simple_attack',
            owned_groups=[dict(found=True,all_members_resolved=True,members=[dict(owner=owner,thing_id=1,
                address='own-object',type_hash='own-type',xyz=[100,100,0])])])])


class NativeRoleEvidenceTests(unittest.TestCase):
    def test_samples_at_deadline_are_excluded(self):
        members,active,_,_=tracks([sample(99),sample(100)],'role',3,1,100,'simple_attack')
        self.assertEqual(active,1);self.assertEqual(len(next(iter(members.values()))),1)

    def test_unpaired_samples_are_discarded_and_counted(self):
        members,active,_,discarded=tracks([sample(20,census_frame=80)],'role',3,1,100,'simple_attack')
        self.assertEqual((members,active,discarded),({},0,1))

    def test_foreign_member_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'foreign_role_member'):
            tracks([sample(20,owner=4)],'role',3,1,100,'simple_attack')


if __name__=='__main__':unittest.main()
