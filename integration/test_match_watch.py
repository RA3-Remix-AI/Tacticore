import unittest
from watch_match import Recorder

def state(frame,defeated=False,mode=2):
    return dict(simulation_frame=frame,mode_raw=mode,result_records=[{'defeat_frame':frame if defeated else 0}],victory_conditions={'participants':[{'player_index':4,'defeated_flag_raw':int(defeated)}] if frame else []})

class WatchTests(unittest.TestCase):
    def test_menu_does_not_destroy_final_native_evidence(self):
        recorder=Recorder();recorder.observe(state(100));recorder.observe(state(300,True))
        flags=recorder.observe(state(0,mode=9))
        self.assertTrue(flags['lifecycle_ended'])
        self.assertEqual(recorder.last_live['simulation_frame'],300)
        self.assertEqual(recorder.candidate['simulation_frame'],300)
    def test_pre_game_menu_is_not_a_result(self):
        recorder=Recorder();flags=recorder.observe(state(0,mode=9))
        self.assertFalse(flags['lifecycle_ended']);self.assertIsNone(recorder.candidate)

if __name__=='__main__':unittest.main()
