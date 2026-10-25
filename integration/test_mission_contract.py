import copy
import unittest
from continuous_contract import MAX_DURATION_FRAMES,PROTOCOL,mission_limits,progress_from_receipt,retreat_context


class MissionBoundaries(unittest.TestCase):
    def setUp(self):
        self.task='57e668b4-4d89-43bd-bc92-0dd436f046ef'
        self.entry=dict(task_id=self.task,dispatch_frame=100,expires_frame=4600,mission_protocol=PROTOCOL)
        self.progress=dict(mission_id=self.task,stage='approach',revision=1,observed_frame=120,deadline_frame=4600,approach_distance=800.,own_hp=100.,damage=0.,reason='active')

    def test_legacy_primitive_cannot_authorize_continuous_mission(self):
        self.assertIsNone(mission_limits(dict(stop_schema=dict(lease_frames=180))))
        with self.assertRaises(ValueError):progress_from_receipt(dict(mission=self.progress),dict(self.entry,mission_protocol=None))

    def test_duration_requires_explicit_bounded_grant(self):
        for duration in (True,0,MAX_DURATION_FRAMES+1,float('inf')):
            with self.assertRaises(ValueError):mission_limits(dict(stop_schema=dict(mission_protocol=PROTOCOL,mission_duration_frames=duration)))
        self.assertEqual(mission_limits(dict(stop_schema=dict(mission_protocol=PROTOCOL,mission_duration_frames=4500)))['duration_frames'],4500)

    def test_task_clock_and_closed_schema(self):
        self.assertEqual(progress_from_receipt(dict(mission=self.progress),self.entry),self.progress)
        for patch in (dict(mission_id='00000000-0000-0000-0000-000000000001'),dict(deadline_frame=4601),dict(observed_frame=99),dict(observed_frame=4601),dict(xyz=[1,2,3]),dict(own_hp=True),dict(damage=float('nan')),dict(reason='raw response / secret')):
            with self.subTest(patch=patch),self.assertRaises(ValueError):progress_from_receipt(dict(mission=dict(self.progress,**patch)),self.entry)

    def test_progress_replay_is_idempotent_but_revision_conflict_rejected(self):
        entry=dict(self.entry,last_mission_progress=copy.deepcopy(self.progress))
        self.assertEqual(progress_from_receipt(dict(mission=self.progress),entry),self.progress)
        with self.assertRaises(ValueError):progress_from_receipt(dict(mission=dict(self.progress,own_hp=90.)),entry)

    def test_retreat_cannot_reengage_or_erase_attributed_damage(self):
        previous=dict(self.progress,stage='retreat',revision=3,observed_frame=400,damage=5.)
        for value in (dict(previous,stage='engage',revision=4),dict(previous,revision=4,damage=0.),dict(previous,revision=2)):
            with self.assertRaises(ValueError):progress_from_receipt(dict(mission=value),dict(self.entry,last_mission_progress=previous))

    def test_retreat_point_preserves_observed_coordinates_and_age(self):
        known=dict(home_base=dict(xyz=[100.,200.,260.],observed_frame=100))
        options=dict(home_object_id=27,own_positions=[[200.,200.,260.]])
        result=retreat_context(known,120,**options)
        self.assertEqual(result['retreat_point']['xyz'],[200.,200.,260.])
        self.assertEqual(result['retreat_point']['source'],'own_home_base')
        self.assertEqual(result['retreat_point']['anchor_object_id'],27)
        self.assertIsNone(retreat_context(known,161,**options))
        self.assertIsNone(retreat_context(known,99,**options))
        self.assertIsNone(retreat_context(dict(enemy=dict(xyz=[1,2,3],observed_frame=100)),120,**options))
        self.assertIsNone(retreat_context(known,120,home_object_id=27,own_positions=[[100.,200.,260.]]))


if __name__=='__main__':unittest.main()
