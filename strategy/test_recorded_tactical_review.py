"""Independent review and corruption tests using immutable recorded game traces.

Only JSON files are read. These do not run or import the game executor.
"""
import copy
import json
from pathlib import Path
import unittest

from review_tactical_report import review

RUNS=Path(__file__).resolve().parents[1]/"acceptance/runs"
OLD=RUNS/"20261024-220820-commander/tactical-lease-20261024-222530.json"
GOOD=RUNS/"20261024-223120-tactical-rematch/tactical-reusable-20261024-223317-1885442582.json"


@unittest.skipUnless(OLD.exists() and GOOD.exists(),"Recorded native experiments are local acceptance artifacts")
class RecordedReview(unittest.TestCase):
    def setUp(self):self.good=json.loads(GOOD.read_text(encoding="utf-8-sig"));self.old=json.loads(OLD.read_text(encoding="utf-8-sig"))

    def test_recorded_success_has_three_independent_arrivals_and_normal_pool_return(self):
        result=review(self.good,expected_session="65bb88da-f5dc-48be-a3c1-5b6ee83cb017",expected_commander="57e668b4-4d89-43bd-bc92-0dd436f046ef")
        self.assertTrue(result["move_and_return_primitive_verified"])
        self.assertEqual(result["arrival_samples_independent"],3)
        self.assertAlmostEqual(result["minimum_distance_independent"],5.558770275462861)
        self.assertEqual(result["recruitment_delay_frames"],2)
        self.assertTrue(all(not result[k] for k in ["raid_verified","attack_verified","combined_arms_verified"]))

    def test_recorded_failure_cannot_be_promoted_by_editing_producer_verdict(self):
        self.old["assessment"]={"status":"move_and_return_primitive_verified","raid_verified":True,"attack_verified":True,"combined_arms_verified":True}
        result=review(self.old)
        self.assertTrue(result["transfer_and_return_observed"]);self.assertFalse(result["move_and_return_primitive_verified"])
        self.assertIsNone(result["minimum_distance_independent"])
        self.assertEqual(result["arrival_samples_reported"],0)
        self.assertTrue(all(not result[k] for k in ["raid_verified","attack_verified","combined_arms_verified"]))

    def test_recorded_trace_binding_counter_target_and_restore_corruption_are_rejected(self):
        mutations=[lambda r:r["request"]["target"].__setitem__(0,r["request"]["target"][0]+999),lambda r:r["native"].__setitem__("arrival_samples",4),lambda r:r["native"].__setitem__("restore_mask",30),lambda r:r["native"].__setitem__("active",1),lambda r:r["native"].__setitem__("command_id","different"),lambda r:r["events"][0].__setitem__("owner",0),lambda r:r["native"].__setitem__("callback_thread",1)]
        for index,mutate in enumerate(mutations):
            report=copy.deepcopy(self.good);mutate(report)
            with self.subTest(index=index):self.assertFalse(review(report)["move_and_return_primitive_verified"])
        self.assertFalse(review(self.good,expected_session="another_session")["move_and_return_primitive_verified"])


if __name__=="__main__":unittest.main(verbosity=2)
