import copy
import unittest

from host_runtime.orchestration import OrchestrationConfig
from host_runtime.replay import replay
from test_host_runtime_orchestration import BINDING,observation


class ReplayTests(unittest.TestCase):
    def test_same_input_same_digest_and_sequence(self):
        rows=[observation(contacts=[]),observation(101,10)]
        before=copy.deepcopy(rows)
        a=replay(BINDING,rows);b=replay(BINDING,copy.deepcopy(rows))
        self.assertEqual(a.digest,b.digest);self.assertEqual(a.intents,b.intents)
        self.assertEqual(rows,before)
        self.assertEqual(len(a.intents),1)
        self.assertEqual(a.events[0]["reason_code"],"no_eligible_target")

    def test_changed_observation_changes_digest(self):
        a=replay(BINDING,[observation()]);b=replay(BINDING,[observation(contacts=[])])
        self.assertNotEqual(a.digest,b.digest)
        self.assertEqual(b.intents,())

    def test_second_task_has_distinct_request_and_lease_identity(self):
        config=OrchestrationConfig(require_plan=False)
        a=replay(BINDING,[observation()],config,task_id="task-a",generation=1)
        b=replay(BINDING,[observation()],config,task_id="task-b",generation=2)
        self.assertNotEqual(a.intents[0]["request_id"],b.intents[0]["request_id"])
        self.assertNotEqual(a.final_state["lease_id"],b.final_state["lease_id"])

    def test_recorded_label_never_grants_field_authority(self):
        out=replay(BINDING,[observation()],source="recorded")
        self.assertFalse(out.final_state["authority_granted"])
        self.assertFalse(out.intents[0]["authority_granted"])
        self.assertEqual(out.source,"recorded")

    def test_invalid_source_and_regressing_clock_rejected(self):
        with self.assertRaises(ValueError):replay(BINDING,[],source="live_verified")
        with self.assertRaises(ValueError):replay(BINDING,[observation(),observation(99,1)])


if __name__=="__main__":unittest.main()
