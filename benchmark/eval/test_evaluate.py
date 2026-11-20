"""Evaluation harness on synthetic run directories (no game, model or network)."""

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# Append, never prepend: benchmark/ has modules (demo.py) that strategy/ shadows.
for folder in (HERE, ROOT / "integration", ROOT / "strategy"):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

import evaluate  # noqa: E402
import record_result  # noqa: E402
from host_runtime.decision_log import DecisionLogWriter, read_run_log  # noqa: E402
from engine import Decision  # noqa: E402

MAP = "map_mp_2_feasel6"


def model_run(root, name, result, *, rejected=0, applied=2, duration=600.0, prompt="v2", latency=2.0):
    """A host-like run: battle-host/decisions.jsonl written by the real writer."""
    output = Path(root) / name / "battle-host"
    output.mkdir(parents=True)
    clock = [0.0]
    writer = DecisionLogWriter(
        output,
        name,
        prompt_version=prompt,
        provider="DeepSeek",
        model="m1",
        map_id=MAP,
        opponent_difficulty="brutal",
        monotonic=lambda: clock[0],
    )
    writer.start()
    for index in range(applied + rejected):
        writer.observe_event("model_macro_request_context", dict(context=dict(game_time_seconds=60.0 * index)))
        writer.observe_event("commander_model_call_started", {})
        clock[0] += latency
        writer.observe_event("commander_model_response_returned", {})
        writer.decided(Decision("local_fallback", "policy_fields", None))
    outcome = {"victory": "victory", "defeat": "defeat"}.get(result)
    match = dict(terminal=True, controlled_outcome=outcome, players={"3": dict(outcome=outcome)}) if outcome else None
    writer.finish(match_result=match, game_time_s=duration, reason_code="test")
    return output.parent


def baseline_run(root, name, result, duration=700.0):
    run = Path(root) / name
    run.mkdir(parents=True)
    record_result.write_tag(run, arm="baseline_native", map_id=MAP, opponent_difficulty="brutal")
    record_result.record_match_end(
        run,
        record_result.manual_result(result),
        duration_s=duration,
        source="manual_entry",
        visually_confirmed=True,
        map_id=MAP,
        opponent_difficulty="brutal",
    )
    return run


class StatisticsTests(unittest.TestCase):
    def test_wilson_interval(self):
        self.assertEqual(evaluate.wilson_interval(0, 0), (None, None))
        low, high = evaluate.wilson_interval(5, 10)
        self.assertAlmostEqual(low, 0.2366, places=4)
        self.assertAlmostEqual(high, 0.7634, places=4)
        low, high = evaluate.wilson_interval(10, 10)
        self.assertAlmostEqual(high, 1.0)
        self.assertGreater(low, 0.69)

    def test_fisher_exact(self):
        self.assertAlmostEqual(evaluate.fisher_exact_two_sided(3, 1, 1, 3), 0.4857142857, places=6)
        self.assertAlmostEqual(evaluate.fisher_exact_two_sided(10, 0, 0, 10), 1.0825e-05, places=8)
        self.assertIsNone(evaluate.fisher_exact_two_sided(0, 0, 0, 0))

    def test_percentile_and_ratio(self):
        self.assertEqual(evaluate.percentile([5, 1, 3, 2, 4], 0.9), 5)
        self.assertIsNone(evaluate.percentile([], 0.5))
        self.assertIsNone(evaluate.ratio(1, 0))


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def corpus(self):
        runs = [
            model_run(self.root, "m1", "victory", duration=500),
            model_run(self.root, "m2", "victory", rejected=1, duration=700),
            model_run(self.root, "m3", "defeat", duration=900),
            model_run(self.root, "v1-run", "defeat", prompt="v1"),
        ]
        runs += [
            baseline_run(self.root, "b1", "victory"),
            baseline_run(self.root, "b2", "defeat"),
            baseline_run(self.root, "b3", "defeat"),
            baseline_run(self.root, "b4", "unknown"),
        ]
        return runs

    def group(self, report, arm, prompt=None):
        return next(
            g for g in report["groups"] if g["config"]["arm"] == arm and g["config"]["prompt_version"] == prompt
        )

    def test_groups_rates_and_baseline_comparison(self):
        report = evaluate.evaluate(self.corpus())
        self.assertEqual(report["runs"], 8)
        model = self.group(report, "model", "v2")
        self.assertEqual((model["runs"], model["victories"], model["defeats"]), (3, 2, 1))
        self.assertAlmostEqual(model["win_rate"], 2 / 3)
        self.assertEqual(model["median_duration_s"], 700)
        self.assertEqual(model["total_decisions"], 7)
        self.assertAlmostEqual(model["rejection_rate"], 1.0)
        self.assertEqual(model["latency_ms_median"], 2000)
        self.assertEqual(model["config"]["model"], "m1")
        baseline = self.group(report, "baseline_native")
        self.assertEqual((baseline["victories"], baseline["defeats"], baseline["unknown_results"]), (1, 2, 1))
        self.assertAlmostEqual(baseline["win_rate"], 1 / 3)
        self.assertAlmostEqual(baseline["win_rate_counting_unknown_as_loss"], 0.25)
        self.assertEqual(baseline["visually_confirmed"], 4)
        self.assertIsNone(baseline["rejection_rate"])
        comparisons = {c["model_config"]["prompt_version"]: c for c in report["comparisons"]}
        self.assertTrue(comparisons["v2"]["baseline_available"])
        self.assertAlmostEqual(comparisons["v2"]["win_rate_difference"], 1 / 3)
        self.assertEqual(comparisons["v2"]["verdict"], "inconclusive")
        self.assertIn("Tacticore 胜率评估", evaluate.render_markdown(report))

    def test_clear_difference_is_reported_as_significant(self):
        runs = [model_run(self.root, "w" + str(i), "victory") for i in range(12)]
        runs += [baseline_run(self.root, "l" + str(i), "defeat") for i in range(12)]
        comparison = evaluate.evaluate(runs)["comparisons"][0]
        self.assertEqual(comparison["verdict"], "model_better")
        self.assertLess(comparison["fisher_p_value"], 0.001)

    def test_tag_overrides_and_missing_arm_is_refused(self):
        run = model_run(self.root, "tagged", "victory")
        record_result.write_tag(
            run, arm="model", map_id="other_map", opponent_difficulty="hard", prompt_version="v2", model="m2"
        )
        config = evaluate.summarize_run(run)["config"]
        self.assertEqual((config["map"], config["model"], config["opponent_difficulty"]), ("other_map", "m2", "hard"))
        bare = self.root / "bare"
        bare.mkdir()
        (bare / "decisions.jsonl").write_text("", encoding="utf-8")
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.summarize_run(bare)
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.summarize_run(self.root / "absent")

    def test_cli_discovers_runs_and_writes_both_reports(self):
        self.corpus()
        prefix = self.root / "out" / "report"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(evaluate.main(["--runs-root", str(self.root), "--out", str(prefix)]), 0)
        report = json.loads(Path(str(prefix) + ".json").read_text(encoding="utf-8"))
        self.assertEqual(report["runs"], 8)
        self.assertIn("与原生AI基线对比", Path(str(prefix) + ".md").read_text(encoding="utf-8"))


class RecordResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_manual_baseline_result_via_cli(self):
        run = self.root / "baseline-1"
        with redirect_stdout(io.StringIO()):
            code = record_result.main(
                [
                    str(run),
                    "--arm",
                    "baseline_native",
                    "--map",
                    MAP,
                    "--opponent-difficulty",
                    "brutal",
                    "--result",
                    "defeat",
                    "--duration-s",
                    "812",
                    "--visually-confirmed",
                ]
            )
        self.assertEqual(code, 0)
        end = read_run_log(run)["match_end"]
        self.assertEqual((end["result"], end["duration_s"], end["result_source"]), ("defeat", 812, "manual_entry"))
        self.assertTrue(end["visually_confirmed"])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            again = record_result.main(
                [
                    str(run),
                    "--arm",
                    "baseline_native",
                    "--map",
                    MAP,
                    "--opponent-difficulty",
                    "brutal",
                    "--result",
                    "victory",
                ]
            )
        self.assertEqual(again, 2)

    def test_native_state_result_uses_the_participant_mapping(self):
        state = dict(
            simulation_frame=9000,
            victory_conditions=dict(
                participants=[dict(player_index=3, manager_index=0), dict(player_index=4, manager_index=1)]
            ),
            result_records=[dict(native_index=0, victory_frame=8990), dict(native_index=1, defeat_frame=8990)],
        )
        path = self.root / "result-candidate.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        # match_participants imports Windows-only memory readers at import time;
        # the result mapping itself is pure, so stub only those readers here.
        stubs = {
            "read_selected_personality": types.SimpleNamespace(inspect_player=None),
            "native_read": types.SimpleNamespace(read_player_relation=None),
        }
        with patch.dict(sys.modules, stubs):
            sys.modules.pop("match_participants", None)
            result, seconds = record_result.result_from_native_state(path, player_id=3, opponent_ids=(4,))
            sys.modules.pop("match_participants", None)
        self.assertEqual((result["controlled_outcome"], seconds), ("victory", 600.0))

    def test_crashed_host_log_gets_the_recorded_result_appended(self):
        run = self.root / "crashed"
        (run / "battle-host").mkdir(parents=True)
        writer = DecisionLogWriter(run / "battle-host", "crashed-run", prompt_version="v2", model="m1")
        writer.start()
        record_result.record_match_end(
            run, record_result.manual_result("victory"), duration_s=400, source="manual_entry", visually_confirmed=True
        )
        log = read_run_log(run)
        self.assertEqual(log["match_end"]["run_id"], "crashed-run")
        self.assertFalse((run / "decisions.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
