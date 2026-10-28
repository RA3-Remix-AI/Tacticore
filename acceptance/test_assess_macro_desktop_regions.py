import copy
import unittest

from assess_macro_desktop_regions import tracks_in_window,progressing_members,reassigned_members


def observation(frame,point,*,owner='own',score=1,family='simple_attack'):
    return dict(frame=frame,state_scores={'flag':dict(group=7,score=score)},runtimes=[
        dict(group=7,native_execution_active=bool(score),native_tactic_family=family,address='runtime',
            owned_groups=[dict(found=True,all_members_resolved=True,native_id=4,
                members=[dict(owner=owner,thing_id=2,xyz=point)])])])


class RegionalEvidenceTests(unittest.TestCase):
    def test_movement_away_from_target_does_not_prove_progress(self):
        values=[observation(10,[100,0,0]),observation(20,[200,0,0])]
        tracks,active,_=tracks_in_window(values,'flag','own',10,30,(0,0))
        self.assertEqual(active,2);self.assertEqual(tracks[0]['displacement'],100)
        self.assertEqual(tracks[0]['progress_toward_public_target'],0)

    def test_only_active_window_and_matching_owner_count(self):
        values=[observation(9,[400,0,0]),observation(10,[200,0,0]),observation(20,[100,0,0]),
            observation(31,[0,0,0],score=0)]
        tracks,active,cleared=tracks_in_window(values,'flag','own',10,30,(0,0))
        self.assertEqual(tracks[0]['samples'],2);self.assertEqual(tracks[0]['progress_toward_public_target'],100)
        self.assertEqual((active,cleared),(2,1))
        foreign=copy.deepcopy(values);foreign[1]['runtimes'][0]['owned_groups'][0]['members'][0]['owner']='enemy'
        with self.assertRaisesRegex(ValueError,'foreign_regional_member'):
            tracks_in_window(foreign,'flag','own',10,30,(0,0))

    def test_wrong_native_tactic_family_cannot_be_regional_effect(self):
        with self.assertRaisesRegex(ValueError,'regional_native_family_mismatch'):
            tracks_in_window([observation(10,[0,0,0],family='scout')],'flag','own',10,30,(0,0))

    def reassignment_fixture(self):
        values=[observation(frame,[point,0,0]) for frame,point in ((10,300),(20,200),(25,400),(30,500),(40,700))]
        for row in values:
            member=row['runtimes'][0]['owned_groups'][0]['members'][0]
            member.update(address='own-object',type_hash='unit-template',hp=100.)
            row['construction_feedback']=dict(enemy_details_read=False,own_objects=[copy.deepcopy(member)])
        windows=[dict(plan_id='east',native_seq=1,target_region='east',
            members=progressing_members(values,'flag','own',10,21,(0,0))),
            dict(plan_id='west',native_seq=3,target_region='west',
            members=progressing_members(values,'flag','own',30,41,(1000,0)))]
        return values,windows

    def test_same_observed_live_members_progress_at_both_macro_destinations(self):
        values,windows=self.reassignment_fixture();result=reassigned_members(values,windows)[0]
        self.assertEqual(result['same_live_own_members_progressing_at_both_targets'],1)
        self.assertEqual(result['minimum_intervening_own_census_samples'],5)
        self.assertFalse(result['continuous_between_samples_verified'])
        self.assertNotIn('own-object',str(result));self.assertNotIn('unit-template',str(result))

    def test_missing_dead_or_reused_own_identity_breaks_reassignment_proof(self):
        for changed in ('missing','dead','reused','foreign'):
            values,windows=self.reassignment_fixture();census=values[2]['construction_feedback']
            if changed=='missing':census['own_objects']=[]
            elif changed=='dead':census['own_objects'][0]['hp']=0
            elif changed=='reused':census['own_objects'][0]['address']='different-object'
            else:census['enemy_details_read']=True
            self.assertEqual(reassigned_members(values,windows)[0]['same_live_own_members_progressing_at_both_targets'],0)

    def test_two_opposite_orders_without_progress_at_both_targets_are_insufficient(self):
        values,_=self.reassignment_fixture()
        self.assertEqual(progressing_members(values,'flag','own',10,21,(1000,0)),{})
        self.assertEqual(progressing_members(values,'flag','own',10,11,(0,0)),{})

    def test_repeated_same_target_is_not_a_region_reassignment(self):
        values,windows=self.reassignment_fixture();windows[1]['target_region']='east'
        self.assertEqual(reassigned_members(values,windows),[])


if __name__=='__main__':unittest.main()
