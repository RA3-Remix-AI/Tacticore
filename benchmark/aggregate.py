"""Evidence-aware benchmark aggregation. No game control or model calls."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

STYLES = {"assault", "economic", "raider"}
SOURCES = {"synthetic", "live_game"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
KINDS = {
    "decision_requested": {"request_id"},
    "decision_result": {"request_id", "status"},
    "plan_activated": {"plan_id", "intent_sha256"},
    "production_requested": {"production_id", "unit_type"},
    "queue_observed": {"production_id"},
    "spend_observed": {"production_id", "amount"},
    "unit_produced": {"production_id", "unit_id"},
    "production_failed": {"production_id"},
    "task_planned": {"task_id"},
    "task_started": {"task_id"},
    "task_result": {"task_id", "status"},
    "blind_vote": {"observer_id", "guessed_style"},
}

class EvidenceError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise EvidenceError(message)

def number(value, low=0, high=1e9):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high, "invalid_number")
    return value

def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value), "invalid_id")
    return value

def digest(value):
    require(isinstance(value, str) and HEX.fullmatch(value), "invalid_digest")
    return value

def canonical_uuid(value):
    try:
        require(isinstance(value, str) and str(uuid.UUID(value)) == value, "invalid_uuid")
    except (ValueError, AttributeError):
        raise EvidenceError("invalid_uuid") from None

MANIFEST_KEYS = {
    "schema_version", "run_id", "source_kind", "session_id", "player_id",
    "commander_id", "commander_name", "commander_profile_sha256", "style", "trial_index", "map_id",
    "faction", "opponent_profile", "difficulty", "game_sha256", "mod_sha256",
    "model_provider", "model_name", "prompt_sha256", "duration_game_seconds",
    "seed_control", "seed", "live_control_verified",
}

def validate_manifest(manifest):
    require(type(manifest) is dict and set(manifest) == MANIFEST_KEYS, "manifest_fields")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1, "schema_version")
    for field in ("run_id", "map_id", "faction", "opponent_profile", "difficulty", "model_provider", "model_name"):
        identifier(manifest[field])
    for field in ("session_id", "commander_id"):
        canonical_uuid(manifest[field])
    require(type(manifest["player_id"]) is int and 0 <= manifest["player_id"] <= 15, "player_id")
    require(type(manifest["trial_index"]) is int and manifest["trial_index"] >= 1, "trial_index")
    require(isinstance(manifest["commander_name"], str) and 1 <= len(manifest["commander_name"].strip()) <= 64, "commander_name")
    require(isinstance(manifest["style"], str) and manifest["style"] in STYLES and isinstance(manifest["source_kind"], str) and manifest["source_kind"] in SOURCES, "provenance_or_style")
    for field in ("game_sha256", "mod_sha256", "prompt_sha256", "commander_profile_sha256"):
        digest(manifest[field])
    number(manifest["duration_game_seconds"], .001)
    require(type(manifest["live_control_verified"]) is bool, "live_control_verified")
    if manifest["source_kind"] == "live_game":
        require(manifest["live_control_verified"], "live_control_not_verified")
    else:
        require(not manifest["live_control_verified"], "synthetic_cannot_claim_control")
    require(manifest["seed_control"] in ("uncontrolled", "recorded_controlled"), "seed_control")
    if manifest["seed_control"] == "uncontrolled":
        require(manifest["seed"] is None, "uncontrolled_seed_must_be_null")
    else:
        require(type(manifest["seed"]) is int and 0 <= manifest["seed"] < 2**32, "invalid_seed")
    return manifest

def verify_artifact(evidence, root):
    require(type(evidence) is dict and set(evidence) == {"path", "sha256"}, "evidence_fields")
    digest(evidence["sha256"])
    require(isinstance(evidence["path"], str) and len(evidence["path"]) <= 240, "evidence_path")
    candidate = Path(evidence["path"])
    require(not candidate.is_absolute(), "evidence_path_absolute")
    root = root.resolve()
    candidate = (root / candidate).resolve()
    require(candidate.is_relative_to(root) and candidate.is_file(), "evidence_outside_run_or_missing")
    require(candidate.stat().st_size <= 16 * 1024 * 1024, "evidence_too_large")
    require(hashlib.sha256(candidate.read_bytes()).hexdigest() == evidence["sha256"], "evidence_hash_mismatch")

def event_schema(event, manifest, root):
    common = {"event_id", "kind", "run_id", "session_id", "player_id", "commander_id", "source_kind", "game_time_seconds", "data", "evidence"}
    require(type(event) is dict and set(event) == common, "event_fields")
    identifier(event["event_id"])
    require(isinstance(event["kind"], str) and event["kind"] in KINDS, "event_kind")
    for field in ("run_id", "session_id", "player_id", "commander_id", "source_kind"):
        require(type(event[field]) is type(manifest[field]) and event[field] == manifest[field], "event_binding_or_source")
    number(event["game_time_seconds"], 0, manifest["duration_game_seconds"])
    require(type(event["data"]) is dict and set(event["data"]) == KINDS[event["kind"]], "event_data_fields")
    if manifest["source_kind"] == "live_game":
        verify_artifact(event["evidence"], root)
    else:
        require(event["evidence"] is None, "synthetic_evidence_must_be_null")
    return event["data"]

def ratio(numerator, denominator):
    return numerator / denominator if denominator else None

def aggregate(manifest, events, evidence_root=Path(".")):
    validate_manifest(manifest)
    requests, production, tasks, votes = {}, {}, {}, {}
    event_ids, plan_ids, unit_ids = set(), set(), set()
    last_time = -1
    previous_intent = None
    activations = changes = 0
    for event in events:
        data = event_schema(event, manifest, Path(evidence_root))
        require(event["event_id"] not in event_ids, "duplicate_event_id")
        event_ids.add(event["event_id"])
        require(event["game_time_seconds"] >= last_time, "time_reversal")
        last_time = event["game_time_seconds"]
        kind = event["kind"]
        if kind == "decision_requested":
            ident = identifier(data["request_id"])
            require(ident not in requests, "duplicate_request")
            requests[ident] = None
        elif kind == "decision_result":
            ident = identifier(data["request_id"])
            require(ident in requests and requests[ident] is None, "unmatched_or_duplicate_result")
            require(data["status"] in ("accepted", "rejected", "timeout", "adapter_error"), "decision_status")
            requests[ident] = data["status"]
        elif kind == "plan_activated":
            ident = identifier(data["plan_id"]); intent = digest(data["intent_sha256"])
            require(ident not in plan_ids, "duplicate_plan_activation")
            plan_ids.add(ident); activations += 1
            if previous_intent is not None and intent != previous_intent:
                changes += 1
            previous_intent = intent
        elif kind == "production_requested":
            ident = identifier(data["production_id"]); identifier(data["unit_type"])
            require(ident not in production, "duplicate_production_request")
            production[ident] = {"queued": False, "spend": None, "unit": None, "failed": False}
        elif kind in ("queue_observed", "spend_observed", "unit_produced", "production_failed"):
            ident = identifier(data["production_id"])
            require(ident in production, "unmatched_production")
            item = production[ident]
            require(not item["failed"], "production_already_failed")
            if kind == "queue_observed":
                require(not item["queued"] and item["unit"] is None, "duplicate_or_late_queue")
                item["queued"] = True
            elif kind == "spend_observed":
                require(item["spend"] is None, "duplicate_spend")
                item["spend"] = number(data["amount"], .000001)
            elif kind == "unit_produced":
                unit = identifier(data["unit_id"])
                require(item["queued"] and item["unit"] is None and unit not in unit_ids, "unit_without_queue_or_duplicate")
                item["unit"] = unit; unit_ids.add(unit)
            else:
                require(item["queued"] and item["unit"] is None, "unstarted_or_completed_production_cannot_fail")
                item["failed"] = True
        elif kind == "task_planned":
            ident = identifier(data["task_id"])
            require(ident not in tasks, "duplicate_task")
            tasks[ident] = "planned"
        elif kind == "task_started":
            ident = identifier(data["task_id"])
            require(tasks.get(ident) == "planned", "task_start_without_plan_or_duplicate")
            tasks[ident] = "started"
        elif kind == "task_result":
            ident = identifier(data["task_id"])
            require(tasks.get(ident) == "started", "unstarted_task_cannot_finish")
            require(data["status"] in ("completed", "failed", "cancelled"), "task_status")
            tasks[ident] = data["status"]
        elif kind == "blind_vote":
            ident = identifier(data["observer_id"])
            require(ident not in votes, "duplicate_observer_vote")
            require(isinstance(data["guessed_style"], str) and data["guessed_style"] in STYLES | {"unknown"}, "vote_style")
            votes[ident] = data["guessed_style"]

    accepted = sum(v == "accepted" for v in requests.values())
    rejected = sum(v == "rejected" for v in requests.values())
    queued = sum(v["queued"] for v in production.values())
    confirmed = sum(v["queued"] and v["spend"] is not None and v["unit"] is not None for v in production.values())
    failed_production = sum(v["failed"] for v in production.values())
    incomplete_evidence = sum(v["unit"] is not None and v["spend"] is None for v in production.values())
    completed_tasks = sum(v == "completed" for v in tasks.values())
    failed_tasks = sum(v == "failed" for v in tasks.values())
    return {
        "schema_version": 1, "run_id": manifest["run_id"], "source_kind": manifest["source_kind"],
        "real_game_acceptance_claim": False,
        "metrics": {
            "decision_requests": len(requests), "accepted_decisions": accepted, "rejected_decisions": rejected,
            "invalid_decision_rate_among_validated": ratio(rejected, accepted + rejected),
            "pending_decisions": sum(v is None for v in requests.values()),
            "timeouts": sum(v == "timeout" for v in requests.values()),
            "adapter_errors": sum(v == "adapter_error" for v in requests.values()),
            "plan_activations": activations, "strategy_changes_excluding_initial": changes,
            "strategy_changes_per_game_minute": changes / (manifest["duration_game_seconds"] / 60) if activations else None,
            "production_requested": len(production), "production_queued": queued,
            "production_confirmed": confirmed, "production_explicit_failures": failed_production,
            "production_pending": sum(v["queued"] and v["unit"] is None and not v["failed"] for v in production.values()),
            "production_unstarted": sum(not v["queued"] for v in production.values()),
            "produced_but_cost_unverified": incomplete_evidence,
            "production_completion_rate_known_outcomes": ratio(confirmed, confirmed + failed_production),
            "confirmed_output_per_queued_request": ratio(confirmed, queued),
            "verified_production_spend": sum(v["spend"] for v in production.values() if v["spend"] is not None) if any(v["spend"] is not None for v in production.values()) else None,
            "tasks_planned": len(tasks), "tasks_unstarted": sum(v == "planned" for v in tasks.values()),
            "tasks_pending": sum(v == "started" for v in tasks.values()), "tasks_completed": completed_tasks,
            "tasks_failed": failed_tasks, "tasks_cancelled": sum(v == "cancelled" for v in tasks.values()),
            "task_completion_rate_known_outcomes": ratio(completed_tasks, completed_tasks + failed_tasks),
            "blind_votes": len(votes), "blind_correct": sum(v == manifest["style"] for v in votes.values()),
            "blind_recognition_rate": ratio(sum(v == manifest["style"] for v in votes.values()), len(votes)),
        },
        "limits": ["Provenance labels and artifact hashes are integrity checks, not proof that telemetry semantics or live control are correct.",
                   "Unknown outcomes remain pending/null; strategy changes require canonical intent fingerprints from a trusted producer."]
    }

MATCH_FIELDS = ("map_id", "faction", "opponent_profile", "difficulty", "game_sha256", "mod_sha256", "model_provider", "model_name", "prompt_sha256", "duration_game_seconds", "seed_control")

def compare(runs):
    require(bool(runs), "no_runs")
    sources = {validate_manifest(m)["source_kind"] for m, _ in runs}
    require(len(sources) == 1, "cannot_mix_synthetic_and_live")
    keys = {tuple(m[k] for k in MATCH_FIELDS) for m, _ in runs}
    require(len(keys) == 1, "unmatched_experiment_conditions")
    seen = set()
    run_ids, sessions = set(), set()
    seeds_by_trial = {}
    profiles_by_commander = {}
    commander_counts = {}
    for manifest, summary in runs:
        require(summary["run_id"] == manifest["run_id"] and summary["source_kind"] == manifest["source_kind"], "summary_binding")
        require(manifest["run_id"] not in run_ids, "duplicate_run_id")
        require(manifest["session_id"] not in sessions, "shared_session_not_independent_run")
        run_ids.add(manifest["run_id"]);sessions.add(manifest["session_id"])
        key = (manifest["commander_id"], manifest["trial_index"])
        require(key not in seen, "duplicate_commander_trial")
        seen.add(key)
        profile = (manifest["style"], manifest["commander_profile_sha256"])
        require(manifest["commander_id"] not in profiles_by_commander or profiles_by_commander[manifest["commander_id"]] == profile, "commander_profile_changed")
        profiles_by_commander[manifest["commander_id"]] = profile
        commander_counts[manifest["commander_id"]] = commander_counts.get(manifest["commander_id"], 0) + 1
        trial = manifest["trial_index"]
        if manifest["seed_control"] == "recorded_controlled":
            require(trial not in seeds_by_trial or seeds_by_trial[trial] == manifest["seed"], "unmatched_trial_seeds")
            seeds_by_trial[trial] = manifest["seed"]
    by_style = {}
    for style in sorted(STYLES):
        selected = [(m, s["metrics"]) for m, s in runs if m["style"] == style]
        if not selected:
            continue
        def total(key): return sum(metrics[key] for _, metrics in selected)
        by_style[style] = {
            "run_count": len(selected), "independent_sessions": len(selected),
            "invalid_decision_rate_among_validated": ratio(total("rejected_decisions"), total("accepted_decisions") + total("rejected_decisions")),
            "strategy_changes_per_game_minute": ratio(total("strategy_changes_excluding_initial"), sum(m["duration_game_seconds"] for m, metric in selected if metric["plan_activations"] > 0) / 60),
            "runs_with_plan_observations": sum(metric["plan_activations"] > 0 for _, metric in selected),
            "production_completion_rate_known_outcomes": ratio(total("production_confirmed"), total("production_confirmed") + total("production_explicit_failures")),
            "production_pending": total("production_pending"),
            "production_unverified_terminal": total("produced_but_cost_unverified"),
            "task_completion_rate_known_outcomes": ratio(total("tasks_completed"), total("tasks_completed") + total("tasks_failed")),
            "tasks_unstarted": total("tasks_unstarted"), "tasks_pending": total("tasks_pending"),
            "blind_recognition_rate": ratio(total("blind_correct"), total("blind_votes")),
            "blind_votes": total("blind_votes"),
        }
    return {"source_kind": next(iter(sources)), "matched_run_count": len(runs),
            "styles_present": sorted({m["style"] for m, _ in runs}),
            "minimum_three_by_three_matrix_complete": all(any(profile[0] == style and commander_counts[commander] >= 3 for commander, profile in profiles_by_commander.items()) for style in STYLES),
            "by_style": by_style,
            "ready_for_real_style_conclusion": False,
            "note": "Matched runs can be inspected, but aggregate count alone does not establish style distinguishability or causal effects.",
            "runs": [s for _, s in runs]}

def parse_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise EvidenceError("nonfinite_json")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, TypeError) as error:
        if isinstance(error, EvidenceError):
            raise
        raise EvidenceError("invalid_json") from None

def load_events(path):
    require(path.stat().st_size <= 32 * 1024 * 1024, "events_too_large")
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        require(len(line) <= 65536, "event_too_large")
        if line.strip():
            result.append(parse_json(line))
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    root = args.run_directory.resolve()
    manifest = parse_json((root / "manifest.json").read_text(encoding="utf-8"))
    summary = aggregate(manifest, load_events(root / "events.jsonl"), root)
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
