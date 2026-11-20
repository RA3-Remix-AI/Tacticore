"""Compare win rates of native-AI-only and model-commanded matches.

Input: completed run directories, each holding decisions.jsonl (written by the
macro host, or by record_result.py for native-only baseline matches) and an
optional eval-tag.json naming the configuration. Output: a JSON and Markdown
report per configuration (arm, prompt version, model, map, opponent difficulty)
with win rate and Wilson 95% interval, durations, decision outcome rates and
model latency, plus a baseline comparison (Fisher exact test).

Standard library only; no game, model or network access.

    python benchmark/eval/evaluate.py RUN_DIR [RUN_DIR ...] [--runs-root DIR] [--out PREFIX]
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "integration") not in sys.path:
    sys.path.append(str(ROOT / "integration"))

from host_runtime.decision_log import decision_log_path, read_run_log  # noqa: E402

TAG_FILE = "eval-tag.json"
ARMS = ("baseline_native", "model")
CONFIG_KEYS = ("arm", "prompt_version", "model", "map", "opponent_difficulty")
OUTCOME_STATUSES = ("applied", "rejected", "expired", "unknown")
Z_95 = 1.959963984540054


class EvaluationError(ValueError):
    """A run directory cannot be evaluated as given."""


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def wilson_interval(successes, trials, z=Z_95):
    """Wilson score interval for a binomial proportion; (None, None) without trials."""
    if trials <= 0:
        return None, None
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def fisher_exact_two_sided(a, b, c, d):
    """Two-sided Fisher exact p-value for the table [[a, b], [c, d]]."""
    row1, row2, col1 = a + b, c + d, a + c
    total = row1 + row2
    if total == 0:
        return None

    def probability(x):
        return math.comb(col1, x) * math.comb(total - col1, row1 - x) / math.comb(total, row1)

    observed = probability(a)
    low, high = max(0, col1 - row2), min(row1, col1)
    p_value = sum(probability(x) for x in range(low, high + 1) if probability(x) <= observed * (1 + 1e-9))
    return min(1.0, p_value)


def ratio(numerator, denominator):
    """Proportion, or None when there is no denominator (never a silent 0)."""
    return numerator / denominator if denominator else None


def percentile(values, fraction):
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def median(values):
    return statistics.median(values) if values else None


# ---------------------------------------------------------------------------
# Loading runs
# ---------------------------------------------------------------------------


def _tag_path(run_dir):
    """eval-tag.json in the run directory (or next to battle-host/ when given that)."""
    run_dir = Path(run_dir)
    candidates = [run_dir / TAG_FILE]
    if run_dir.name == "battle-host":
        candidates.append(run_dir.parent / TAG_FILE)
    return next((path for path in candidates if path.is_file()), None)


def load_config(run_dir, run_start):
    """Configuration from eval-tag.json, falling back to the log's run_start record."""
    run_start = run_start or {}
    config = dict(
        arm=None,
        prompt_version=run_start.get("prompt_version"),
        model=run_start.get("model"),
        map=run_start.get("map_id"),
        opponent_difficulty=run_start.get("opponent_difficulty"),
    )
    path = _tag_path(run_dir)
    if path is not None:
        tag = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(tag, dict):
            raise EvaluationError(str(path) + ": eval-tag.json must be an object")
        config.update({key: tag[key] for key in CONFIG_KEYS if key in tag})
        config["label"] = tag.get("label")
    if config["arm"] is None and run_start.get("model") is not None:
        config["arm"] = "model"
    if config["arm"] not in ARMS:
        raise EvaluationError(str(run_dir) + ": arm must be one of " + ", ".join(ARMS) + " (set eval-tag.json)")
    if config["arm"] == "baseline_native":
        config["prompt_version"] = None
        config["model"] = None
    return config


def summarize_run(run_dir):
    """Per-run facts used by the aggregation."""
    path = decision_log_path(run_dir)
    if not path.is_file():
        raise EvaluationError(str(run_dir) + ": decisions.jsonl not found")
    log = read_run_log(run_dir)
    config = load_config(run_dir, log["run"])
    end = log["match_end"]
    statuses = Counter(record.get("outcome", {}).get("status") for record in log["decisions"])
    models = [record.get("model") or {} for record in log["decisions"]]
    latencies = [m["latency_ms"] for m in models if type(m.get("latency_ms")) in (int, float)]
    return dict(
        run_dir=str(run_dir),
        run_id=(log["run"] or end or {}).get("run_id"),
        config=config,
        complete=end is not None,
        result=end.get("result", "unknown") if end else "unknown",
        duration_s=end.get("duration_s") if end else None,
        visually_confirmed=bool(end and end.get("visually_confirmed")),
        decisions=len(log["decisions"]),
        statuses={status: statuses.get(status, 0) for status in OUTCOME_STATUSES},
        model_errors=sum(1 for m in models if m.get("error")),
        latencies_ms=latencies,
        invalid_lines=log["invalid_lines"],
    )


def discover_runs(root):
    """Every directory below root that holds a decisions.jsonl."""
    found = set()
    for path in Path(root).rglob("decisions.jsonl"):
        directory = path.parent
        found.add(directory.parent if directory.name == "battle-host" else directory)
    return sorted(found)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def config_key(config):
    return tuple(config.get(key) for key in CONFIG_KEYS)


def aggregate_group(runs):
    """Metrics for runs sharing one configuration."""
    results = Counter(run["result"] for run in runs)
    wins, losses = results.get("victory", 0), results.get("defeat", 0)
    decided = wins + losses
    low, high = wilson_interval(wins, decided)
    durations = [run["duration_s"] for run in runs if type(run["duration_s"]) in (int, float)]
    decision_counts = [run["decisions"] for run in runs]
    total_decisions = sum(decision_counts)
    statuses = Counter()
    for run in runs:
        statuses.update(run["statuses"])
    latencies = [value for run in runs for value in run["latencies_ms"]]
    return dict(
        config=dict(runs[0]["config"]),
        runs=len(runs),
        victories=wins,
        defeats=losses,
        unknown_results=len(runs) - decided,
        incomplete_runs=sum(1 for run in runs if not run["complete"]),
        visually_confirmed=sum(1 for run in runs if run["visually_confirmed"]),
        win_rate=ratio(wins, decided),
        win_rate_ci95=[low, high],
        win_rate_counting_unknown_as_loss=ratio(wins, len(runs)),
        median_duration_s=median(durations),
        median_decisions_per_run=median(decision_counts),
        total_decisions=total_decisions,
        outcome_rates={status: ratio(statuses.get(status, 0), total_decisions) for status in OUTCOME_STATUSES},
        rejection_rate=ratio(statuses.get("rejected", 0) + statuses.get("expired", 0), total_decisions),
        unknown_rate=ratio(statuses.get("unknown", 0), total_decisions),
        model_error_rate=ratio(sum(run["model_errors"] for run in runs), total_decisions),
        latency_ms_median=median(latencies),
        latency_ms_p90=percentile(latencies, 0.9),
        run_ids=[run["run_id"] for run in runs],
    )


def compare_to_baseline(groups):
    """Pair each model configuration with the baseline on the same map and difficulty."""
    baselines = {
        (g["config"]["map"], g["config"]["opponent_difficulty"]): g
        for g in groups
        if g["config"]["arm"] == "baseline_native"
    }
    comparisons = []
    for group in groups:
        if group["config"]["arm"] != "model":
            continue
        setting = (group["config"]["map"], group["config"]["opponent_difficulty"])
        baseline = baselines.get(setting)
        entry = dict(
            model_config=group["config"],
            map=setting[0],
            opponent_difficulty=setting[1],
            baseline_available=baseline is not None,
        )
        if baseline is not None:
            p_value = fisher_exact_two_sided(
                group["victories"], group["defeats"], baseline["victories"], baseline["defeats"]
            )
            difference = (
                None
                if group["win_rate"] is None or baseline["win_rate"] is None
                else group["win_rate"] - baseline["win_rate"]
            )
            entry.update(
                model_win_rate=group["win_rate"],
                baseline_win_rate=baseline["win_rate"],
                win_rate_difference=difference,
                fisher_p_value=p_value,
                verdict=_verdict(difference, p_value),
            )
        comparisons.append(entry)
    return comparisons


def _verdict(difference, p_value):
    if difference is None or p_value is None:
        return "insufficient_data"
    if p_value >= 0.05:
        return "inconclusive"
    return "model_better" if difference > 0 else "model_worse"


def evaluate(run_dirs):
    """Full report dictionary for the given run directories."""
    runs = [summarize_run(run_dir) for run_dir in run_dirs]
    grouped = {}
    for run in runs:
        grouped.setdefault(config_key(run["config"]), []).append(run)
    groups = [aggregate_group(grouped[key]) for key in sorted(grouped, key=lambda k: tuple(str(v) for v in k))]
    return dict(
        schema_version=1,
        kind="tacticore_win_rate_evaluation",
        runs=len(runs),
        groups=groups,
        comparisons=compare_to_baseline(groups),
        per_run=[
            {
                key: run[key]
                for key in ("run_dir", "run_id", "result", "duration_s", "decisions", "complete", "invalid_lines")
            }
            for run in runs
        ],
    )


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def _pct(value):
    return "—" if value is None else format(value * 100, ".1f") + "%"


def _num(value, digits=0):
    return "—" if value is None else format(value, "." + str(digits) + "f")


def _label(config):
    if config["arm"] == "baseline_native":
        return "原生AI基线"
    return "模型 " + str(config.get("model")) + " / 提示 " + str(config.get("prompt_version"))


def render_markdown(report):
    lines = [
        "# Tacticore 胜率评估",
        "",
        "共 " + str(report["runs"]) + " 场。胜率只统计胜/负已判定的对局；结果未知的对局单列。",
        "",
        "## 各配置",
        "",
        "| 配置 | 地图 | 对手难度 | 场数 | 胜 | 负 | 未知 | 胜率 | 95%置信区间 | 中位时长(秒) "
        "| 中位决策数 | 拒绝率 | 未知率 | 模型错误率 | 延迟中位/P90(ms) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for group in report["groups"]:
        config = group["config"]
        low, high = group["win_rate_ci95"]
        interval = "—" if low is None else _pct(low) + " – " + _pct(high)
        lines.append(
            "| "
            + " | ".join(
                [
                    _label(config),
                    str(config["map"]),
                    str(config["opponent_difficulty"]),
                    str(group["runs"]),
                    str(group["victories"]),
                    str(group["defeats"]),
                    str(group["unknown_results"]),
                    _pct(group["win_rate"]),
                    interval,
                    _num(group["median_duration_s"]),
                    _num(group["median_decisions_per_run"], 1),
                    _pct(group["rejection_rate"]),
                    _pct(group["unknown_rate"]),
                    _pct(group["model_error_rate"]),
                    _num(group["latency_ms_median"]) + " / " + _num(group["latency_ms_p90"]),
                ]
            )
            + " |"
        )
    lines += ["", "## 与原生AI基线对比", ""]
    if not report["comparisons"]:
        lines.append("没有模型配置可比较。")
    for entry in report["comparisons"]:
        head = (
            "- "
            + _label(entry["model_config"])
            + "（"
            + str(entry["map"])
            + "，"
            + str(entry["opponent_difficulty"])
            + "）："
        )
        if not entry["baseline_available"]:
            lines.append(head + "缺少同地图同难度的基线对局。")
            continue
        lines.append(
            head
            + "模型胜率 "
            + _pct(entry["model_win_rate"])
            + "，基线 "
            + _pct(entry["baseline_win_rate"])
            + "，差值 "
            + _pct(entry["win_rate_difference"])
            + "，Fisher p="
            + _num(entry["fisher_p_value"], 3)
            + "，结论："
            + entry["verdict"]
        )
    lines += [
        "",
        "结论含义：model_better / model_worse 仅在 p<0.05 时给出；否则为 inconclusive（需更多对局）。",
        "原生结果槽判定的胜负仍需人工目视确认（visually_confirmed 字段）。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dirs", nargs="*", type=Path, help="completed run directories")
    parser.add_argument(
        "--runs-root", type=Path, action="append", default=[], help="also evaluate every run below this directory"
    )
    parser.add_argument("--out", type=Path, help="write PREFIX.json and PREFIX.md instead of printing")
    args = parser.parse_args(argv)
    run_dirs = list(args.run_dirs)
    for root in args.runs_root:
        run_dirs += discover_runs(root)
    if not run_dirs:
        parser.error("no run directories given")
    try:
        report = evaluate(run_dirs)
    except (EvaluationError, OSError, ValueError) as error:
        print("error: " + str(error), file=sys.stderr)
        return 2
    markdown = render_markdown(report)
    if args.out is None:
        sys.stdout.write(markdown)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Path(str(args.out) + ".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(str(args.out) + ".md").write_text(markdown, encoding="utf-8")
    print(str(args.out) + ".json")
    print(str(args.out) + ".md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
