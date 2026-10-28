"""Independent effects must precede native expiry and retain own identity."""
import unittest
from assess_macro_base_defense import defense_presence
from integration.host_runtime.macro_infrastructure import TEMPLATES


def observation(frame,owner=3):
    return dict(frame=frame,state_scores={'defense':dict(score=1,group=7)},
        construction_feedback=dict(frame=frame,enemy_details_read=False,
            own_objects=[dict(type_hash=next(iter(TEMPLATES.values())),hp=100,xyz=[0,0,0])]),
        runtimes=[dict(group=7,native_execution_active=True,native_tactic_family='static_defense',
            owned_groups=[dict(found=True,all_members_resolved=True,native_id=1,
                members=[dict(owner=owner,thing_id=2,xyz=[100,100,0])])])])


class DefenseEvidenceTests(unittest.TestCase):
    def test_native_expiry_excludes_late_presence(self):
        rows=[observation(f) for f in (901,910,920)]
        self.assertFalse(defense_presence(rows,'defense',3,1,901)['native_defender_presence_near_own_infrastructure_verified'])
        self.assertTrue(defense_presence(rows,'defense',3,1,921)['native_defender_presence_near_own_infrastructure_verified'])

    def test_foreign_member_cannot_supply_effect(self):
        with self.assertRaisesRegex(ValueError,'foreign_defender'):
            defense_presence([observation(10,4)],'defense',3,1,100)

    def test_sparse_single_sample_cannot_supply_effect(self):
        self.assertFalse(defense_presence([observation(10)],'defense',3,1,100)['native_defender_presence_near_own_infrastructure_verified'])


if __name__=='__main__':unittest.main()
