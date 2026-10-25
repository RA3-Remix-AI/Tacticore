"""Offline functional acceptance, not a native capability source."""
import unittest
from remembered_approach import qualify


def event(frame, x, visible=0, seen=100, target=(1000., 0., 210.)):
    return dict(kind=3, frame=frame, mission_stage=2, current_visible=visible,
                target_last_seen_frame=frame if visible else seen,
                remembered_target_xyz=list(target), x=x, y=0., z=210.)


class RememberedMovement(unittest.TestCase):
    def test_real_displacement_and_reacquisition_both_required(self):
        events=[event(101,0),event(140,70),event(180,150),event(181,151,1)]
        result=qualify(dict(events=events))
        self.assertTrue(result['hidden_approach_verified'])
        self.assertEqual(result['maximum_hidden_displacement'],150)
        self.assertFalse(qualify(dict(events=events[:-1]))['hidden_approach_verified'])
        self.assertEqual(qualify(dict(events=events[:-1]))['maximum_hidden_displacement'],150)

    def test_stationary_hidden_wait_and_duplicate_frame_do_not_establish_movement(self):
        for events in ([event(101,0),event(140,0),event(180,0),event(181,0,1)],
                       [event(101,0),event(101,70),event(101,150),event(102,151,1)]):
            self.assertFalse(qualify(dict(events=events))['hidden_approach_verified'])

    def test_unseen_point_drift_or_expired_memory_cannot_extend_a_block(self):
        events=[event(101,0),event(140,70),event(180,150,target=(999.,0.,210.)),event(181,151,1)]
        self.assertFalse(qualify(dict(events=events))['hidden_approach_verified'])
        events=[event(101,0),event(140,70),event(1001,150),event(1002,151,1)]
        self.assertFalse(qualify(dict(events=events))['hidden_approach_verified'])


if __name__=='__main__':unittest.main()
