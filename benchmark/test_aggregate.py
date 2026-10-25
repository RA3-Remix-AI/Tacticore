import copy
import hashlib
import tempfile
from pathlib import Path
import unittest
from aggregate import EvidenceError, aggregate, compare, parse_json
from demo import manifest, events

class BenchmarkTests(unittest.TestCase):
    def test_complete_synthetic_run(self):
        m=manifest();s=aggregate(m,events(m))["metrics"]
        self.assertEqual(s["invalid_decision_rate_among_validated"],.5)
        self.assertEqual(s["production_confirmed"],1)
        self.assertEqual(s["production_completion_rate_known_outcomes"],1)
        self.assertEqual(s["tasks_unstarted"],1)
        self.assertEqual(s["tasks_failed"],0)
        self.assertEqual(s["strategy_changes_excluding_initial"],0)

    def test_missing_denominators_are_null(self):
        s=aggregate(manifest(),[])["metrics"]
        for key in ("invalid_decision_rate_among_validated","production_completion_rate_known_outcomes","task_completion_rate_known_outcomes","blind_recognition_rate","verified_production_spend","strategy_changes_per_game_minute"):
            self.assertIsNone(s[key],key)

    def test_unstarted_task_cannot_be_failure(self):
        m=manifest();e=events(m)
        extra=copy.deepcopy(e[-1]);extra.update(event_id="bad",kind="task_result",game_time_seconds=70,data={"task_id":"never-started","status":"failed"});e.append(extra)
        with self.assertRaisesRegex(EvidenceError,"unstarted_task"):aggregate(m,e)

    def test_pending_not_failure(self):
        m=manifest();e=events(m)[:9];s=aggregate(m,e)["metrics"]
        self.assertEqual(s["tasks_pending"],1);self.assertEqual(s["tasks_failed"],0)
        self.assertIsNone(s["task_completion_rate_known_outcomes"])

    def test_production_missing_cost_not_confirmed(self):
        m=manifest();e=[r for r in events(m) if r["kind"]!="spend_observed"]
        s=aggregate(m,e)["metrics"]
        self.assertEqual(s["production_confirmed"],0);self.assertEqual(s["produced_but_cost_unverified"],1)
        self.assertIsNone(s["production_completion_rate_known_outcomes"])

    def test_production_requires_queue(self):
        m=manifest();e=[r for r in events(m) if r["kind"]!="queue_observed"]
        with self.assertRaisesRegex(EvidenceError,"unit_without_queue"):aggregate(m,e)

    def test_unqueued_production_cannot_fail(self):
        m=manifest();e=events(m)[:6];extra=copy.deepcopy(e[-1]);extra.update(event_id="bad",kind="production_failed",game_time_seconds=7,data={"production_id":"production-1"});e.append(extra)
        with self.assertRaisesRegex(EvidenceError,"unstarted_or_completed"):aggregate(m,e)

    def test_duplicate_unit_rejected(self):
        m=manifest();e=events(m);extra=copy.deepcopy(e[8]);extra.update(event_id="bad",game_time_seconds=90);e.append(extra)
        with self.assertRaisesRegex(EvidenceError,"unit_without_queue_or_duplicate"):aggregate(m,e)

    def test_duplicate_result_rejected(self):
        m=manifest();e=events(m);extra=copy.deepcopy(e[1]);extra.update(event_id="bad",game_time_seconds=90);e.append(extra)
        with self.assertRaisesRegex(EvidenceError,"unmatched_or_duplicate"):aggregate(m,e)

    def test_binding_isolation(self):
        m=manifest();e=events(m);e[0]["commander_id"]="10000000-0000-4000-8000-000000000099"
        with self.assertRaisesRegex(EvidenceError,"event_binding"):aggregate(m,e)

    def test_mixed_event_provenance_rejected(self):
        m=manifest();e=events(m);e[0]["source_kind"]="live_game"
        with self.assertRaisesRegex(EvidenceError,"event_binding"):aggregate(m,e)

    def test_live_control_gate(self):
        m=manifest();m["source_kind"]="live_game"
        with self.assertRaisesRegex(EvidenceError,"live_control_not_verified"):aggregate(m,[])

    def test_live_requires_artifact(self):
        m=manifest();m.update(source_kind="live_game",live_control_verified=True);e=events(m)
        with self.assertRaisesRegex(EvidenceError,"evidence_fields"):aggregate(m,e)

    def test_live_artifact_hash_and_path(self):
        m=manifest();m.update(source_kind="live_game",live_control_verified=True);e=events(m)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"capture.json").write_text("verified-source-fixture",encoding="utf-8")
            digest=hashlib.sha256((root/"capture.json").read_bytes()).hexdigest()
            for event in e:event["evidence"]={"path":"capture.json","sha256":digest}
            s=aggregate(m,e,root);self.assertFalse(s["real_game_acceptance_claim"])
            e[0]["evidence"]["sha256"]="0"*64
            with self.assertRaisesRegex(EvidenceError,"evidence_hash_mismatch"):aggregate(m,e,root)
            e[0]["evidence"]={"path":"../outside.json","sha256":digest}
            with self.assertRaisesRegex(EvidenceError,"evidence_outside"):aggregate(m,e,root)

    def test_compare_rejects_mixed_sources(self):
        a=manifest();b=manifest("economic");b.update(source_kind="live_game",live_control_verified=True)
        with self.assertRaisesRegex(EvidenceError,"cannot_mix"):compare([(a,aggregate(a,[])),(b,aggregate(b,[]))])

    def test_compare_rejects_changed_conditions(self):
        a=manifest();b=manifest("economic");b["mod_sha256"]="d"*64
        with self.assertRaisesRegex(EvidenceError,"unmatched_experiment"):compare([(a,aggregate(a,[])),(b,aggregate(b,[]))])

    def test_commander_profile_cannot_drift_between_trials(self):
        a=manifest();b=manifest(trial=2);b["commander_profile_sha256"]="0"*64
        with self.assertRaisesRegex(EvidenceError,"commander_profile_changed"):compare([(a,aggregate(a,[])),(b,aggregate(b,[]))])

    def test_compare_rejects_duplicate_trial(self):
        a=manifest();s=aggregate(a,[])
        b=manifest();b["run_id"]="duplicate-trial-different-run";b["session_id"]="00000000-0000-4000-8000-000000000123"
        with self.assertRaisesRegex(EvidenceError,"duplicate_commander_trial"):compare([(a,s),(b,aggregate(b,[]))])

    def test_shared_session_not_independent(self):
        a=manifest();b=manifest("economic");b["session_id"]=a["session_id"]
        with self.assertRaisesRegex(EvidenceError,"shared_session"):compare([(a,aggregate(a,[])),(b,aggregate(b,[]))])

    def test_three_by_three_synthetic_not_live_conclusion(self):
        runs=[]
        for trial in range(1,4):
            for style in ("assault","economic","raider"):
                m=manifest(style,trial);runs.append((m,aggregate(m,events(m))))
        result=compare(runs)
        self.assertTrue(result["minimum_three_by_three_matrix_complete"])
        self.assertFalse(result["ready_for_real_style_conclusion"])
        self.assertEqual(result["by_style"]["assault"]["invalid_decision_rate_among_validated"],.5)

    def test_uncontrolled_seed_not_invented(self):
        m=manifest();m["seed"]=123
        with self.assertRaisesRegex(EvidenceError,"uncontrolled_seed"):aggregate(m,[])

    def test_controlled_pair_seed_must_match(self):
        a=manifest();b=manifest("economic")
        a.update(seed_control="recorded_controlled",seed=1);b.update(seed_control="recorded_controlled",seed=2)
        with self.assertRaisesRegex(EvidenceError,"unmatched_trial_seeds"):compare([(a,aggregate(a,[])),(b,aggregate(b,[]))])

    def test_plan_changes_exclude_initial_and_refresh(self):
        m=manifest();e=events(m);template=copy.deepcopy(e[2])
        for i,fingerprint in enumerate(("1"*64,"2"*64),1):
            extra=copy.deepcopy(template);extra.update(event_id="refresh-"+str(i),game_time_seconds=100+i,data={"plan_id":"plan-"+str(i+1),"intent_sha256":fingerprint});e.append(extra)
        s=aggregate(m,e)["metrics"];self.assertEqual(s["plan_activations"],3);self.assertEqual(s["strategy_changes_excluding_initial"],1);self.assertEqual(s["strategy_changes_per_game_minute"],.2)

    def test_blind_vote_unknown_is_not_correct(self):
        m=manifest();e=events(m)
        for i,guess in enumerate(("assault","unknown"),1):
            extra=copy.deepcopy(e[0]);extra.update(event_id="vote-"+str(i),kind="blind_vote",game_time_seconds=300,data={"observer_id":"anonymous-"+str(i),"guessed_style":guess});e.append(extra)
        self.assertEqual(aggregate(m,e)["metrics"]["blind_recognition_rate"],.5)

    def test_duplicate_json_and_nonfinite_rejected(self):
        for text in ('{"x":1,"x":2}','{"x":NaN}'):
            with self.assertRaises(EvidenceError):parse_json(text)

    def test_unknown_fields_rejected(self):
        m=manifest();e=events(m);e[0]["api_key"]="must-not-be-accepted"
        with self.assertRaisesRegex(EvidenceError,"event_fields"):aggregate(m,e)

    def test_time_reversal_rejected(self):
        m=manifest();e=events(m);e[2]["game_time_seconds"]=0
        with self.assertRaisesRegex(EvidenceError,"time_reversal"):aggregate(m,e)

if __name__=="__main__":unittest.main()
