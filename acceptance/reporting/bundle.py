"""Build a bounded public index of explicitly pinned, frozen evidence.

The host_diagnostics_v1 adapter reads the real client's diagnostics format.
It does not turn host assertions, hashes or source labels into field proof.
Raw files, filenames, free text and provider payloads never enter the bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid

LAYERS = ("configuration", "model_consumption", "production", "task", "effect",
          "physical_home", "control_release", "natural_settlement")
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_SOURCES = 128
MAX_RECORDS = 100000
MAX_TOTAL_INPUT_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 32 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_ID = re.compile(r"source_[0-9]{3,6}\Z")
_EVENT_LAYERS = {
    "commander_profile_applied": "configuration",
    "commander_model_response_returned": "model_consumption",
    "task_proposed": "task", "task_feedback": "task",
    "runtime_model_task_feedback": "task",
    "native_result_candidate": "natural_settlement",
    "native_result_candidate_after_cleanup": "natural_settlement",
}
_FACT_BOOLS = frozenset({"model_consumed", "model_response_received", "real_network_verified",
    "physical_home", "control_released", "native_release_verified", "mission_effect_verified",
    "goal_observed", "restoration_verified", "traits_truncated"})
_FACT_NUMBERS = frozenset({"amount", "spent", "paid", "damage", "source_damage_amount", "game_frame",
    "at_game_seconds", "call_sequence", "responses_returned", "calls_started", "profile_revision"})
_FACT_IDS = frozenset({"task_id", "request_id", "command_id", "plan_id", "session_id", "commander_id"})
_ENUMS = {
    "status": {"accepted", "started", "completed", "failed", "cancelled", "rejected", "released", "uncertain", "blocked"},
    "state": {"idle", "starting", "running", "stopping", "stopped", "fault", "unknown"},
    "purpose": {"main_attack", "harass_economy", "coordinate_force", "move_hold_return", "reconcile_return_home"},
    "module": {"attack", "raid", "combined_arms", "build"},
    "source": {"synthetic", "simulated", "game_bridge", "live_game", "native", "model", "script"},
}


class BundleError(ValueError):
    """Only fixed reason codes; filenames and rejected payloads are not echoed."""


def _require(ok, code):
    if not ok:
        raise BundleError(code)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            _require(key not in obj, "duplicate_json_key")
            obj[key] = value
        return obj
    def constant(_):
        raise BundleError("nonfinite_json")
    try:
        result = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
        # JSON exponent overflow is not handled by parse_constant.
        def walk(item, depth=0):
            _require(depth <= 64, "json_too_deep")
            if isinstance(item, float):
                _require(math.isfinite(item), "nonfinite_json")
            elif isinstance(item, dict):
                for v in item.values(): walk(v, depth + 1)
            elif isinstance(item, list):
                for v in item: walk(v, depth + 1)
        walk(result)
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise BundleError("invalid_json") from None


def _uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0
    except (ValueError, AttributeError):
        return False


def _binding(value):
    fields = {"run_id", "session_id", "player_id", "commander_id", "profile_revision", "effective_hash"}
    _require(type(value) is dict and set(value) == fields, "invalid_binding")
    _require(all(_uuid(value[k]) for k in ("run_id", "session_id", "commander_id")), "invalid_binding")
    _require(type(value["player_id"]) is int and 0 <= value["player_id"] <= 15, "invalid_binding")
    _require(type(value["profile_revision"]) is int and value["profile_revision"] > 0, "invalid_binding")
    _require(isinstance(value["effective_hash"], str) and _HASH.fullmatch(value["effective_hash"]), "invalid_binding")
    return dict(value)


def _not_link(path):
    """Reject symlinks and Windows junction/reparse points in every existing component."""
    path = Path(os.path.abspath(path))
    for item in [*reversed(path.parents), path]:
        try: info = item.lstat()
        except FileNotFoundError: continue
        _require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400), "symlink_or_reparse_point")
    return path


def _source_path(root, relative):
    _require(isinstance(relative, str) and 0 < len(relative) <= 1024 and "\\" not in relative and ":" not in relative and all(ord(c) >= 32 for c in relative), "invalid_source_path")
    part = PurePosixPath(relative)
    _require(not part.is_absolute() and all(x not in ("", ".", "..") for x in relative.split("/")), "source_path_outside_root")
    path = _not_link(root.joinpath(*part.parts))
    _require(path.is_relative_to(root), "source_path_outside_root")
    return path


def _read(path, maximum):
    _not_link(path)
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            _require(stat.S_ISREG(before.st_mode), "source_not_regular_file")
            _require(before.st_size <= maximum, "source_too_large")
            raw = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
        mark = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        _require(mark(before) == mark(after) and len(raw) == before.st_size, "source_changed")
        return raw
    except FileNotFoundError:
        raise BundleError("source_missing") from None
    except OSError:
        raise BundleError("source_unreadable") from None


def _check_present_binding(value, expected):
    if not isinstance(value, dict): return
    for key, wanted in expected.items():
        if key in value:
            _require(type(value[key]) is type(wanted) and value[key] == wanted, "source_binding_mismatch")


def _project_facts(value):
    """Positive projection only. Caller strings, file paths and raw text are excluded."""
    if not isinstance(value, dict): return {}
    out = {}
    for key, item in value.items():
        if key in _FACT_BOOLS and type(item) is bool: out[key] = item
        elif key in _FACT_NUMBERS and type(item) in (int, float) and math.isfinite(item) and 0 <= item <= 2**53 - 1: out[key] = item
        elif key in _FACT_IDS and _uuid(item): out[key] = item
        elif key == "effective_hash" and isinstance(item, str) and _HASH.fullmatch(item): out[key] = item
        elif key in _ENUMS and isinstance(item, str) and item in _ENUMS[key]: out[key] = item
    return out


def _diagnostics(value, expected):
    _require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1 and value.get("kind") == "tacticore_redacted_diagnostics", "diagnostics_schema_unsupported")
    _require(value.get("redacted") is True, "diagnostics_not_redacted")
    _require(value.get("run_id") == expected["run_id"], "source_binding_mismatch")
    binding = value.get("binding")
    profile = value.get("effective_profile")
    _require(type(binding) is dict and type(profile) is dict and value.get("effective_profile_available") is True, "diagnostics_binding_unavailable")
    for key in ("session_id", "player_id", "commander_id"):
        _require(type(binding.get(key)) is type(expected[key]) and binding[key] == expected[key], "source_binding_mismatch")
    _require(profile.get("revision") == expected["profile_revision"] and type(profile.get("revision")) is int and profile.get("effective_hash") == expected["effective_hash"], "source_binding_mismatch")
    if "profile_id" in profile:
        _require(profile["profile_id"] == expected["commander_id"], "source_binding_mismatch")
    _require(value.get("binding_hash") == _digest(_canonical(binding)), "diagnostics_binding_hash_mismatch")
    _check_present_binding(value.get("status"), expected)
    if isinstance(value.get("status"), dict) and "profile_id" in value["status"]:
        _require(value["status"]["profile_id"] == expected["commander_id"], "source_binding_mismatch")
    events, timeline = value.get("events"), value.get("timeline")
    _require(type(events) is dict and type(timeline) is list and len(timeline) <= MAX_RECORDS, "diagnostics_events_invalid")
    _require(events.get("truncated") is False, "source_truncated")
    _require(type(events.get("total_count")) is int and events["total_count"] == events.get("exported_count") == len(timeline), "source_count_mismatch")
    _require(events.get("timeline_sha256") == _digest(_canonical(timeline)), "diagnostics_timeline_hash_mismatch")
    seqs = [row.get("seq") if type(row) is dict else None for row in timeline]
    _require(all(type(n) is int and n > 0 for n in seqs) and len(set(seqs)) == len(seqs), "duplicate_or_invalid_record_id")
    if seqs:
        # SQLite seq is global across runs. Per-run windows may have legal gaps.
        _require(seqs == sorted(seqs) and events.get("first_seq") == seqs[0] and events.get("last_seq") == seqs[-1], "source_sequence_order")
    else:
        _require(events.get("first_seq") is None and events.get("last_seq") is None, "source_sequence_gap")
    grouped = {layer: [] for layer in LAYERS}
    commands = {}
    for row in timeline:
        facts = row.get("facts", {})
        _require(type(facts) is dict, "diagnostics_event_shape_invalid")
        _check_present_binding(facts, expected)
        if isinstance(facts, dict):
            _check_present_binding(facts.get("receipt"), expected)
            if isinstance(facts.get("receipt"), dict):
                _check_present_binding(facts["receipt"].get("facts"), expected)
        kind = row.get("event_type")
        command_id = row.get("command_id")
        if kind not in set(_EVENT_LAYERS) | {"command_reserved", "command_outcome", "host_stopped"}:
            continue
        if kind == "command_reserved" and isinstance(facts, dict):
            commands[command_id] = facts.get("operation")
        layer = _EVENT_LAYERS.get(kind)
        if kind in {"command_reserved", "command_outcome"} and commands.get(command_id) in {"produce", "production"}:
            layer = "production"
        projected = _project_facts(facts)
        receipt = facts.get("receipt") if isinstance(facts, dict) else None
        if isinstance(receipt, dict):
            projected.update(_project_facts(receipt))
            projected.update(_project_facts(receipt.get("facts")))
        claim = {"record_seq": row["seq"], "claim_kind": "settlement_candidate" if kind in {"native_result_candidate", "native_result_candidate_after_cleanup"} else "host_event_assertion", "source_claims": projected}
        if layer: grouped[layer].append(claim)
        if "mission_effect_verified" in projected: grouped["effect"].append(claim)
        if "physical_home" in projected: grouped["physical_home"].append(claim)
        if "control_released" in projected or "native_release_verified" in projected:
            grouped["control_release"].append(claim)
    # The final status is also an assertion, never an independent native audit.
    status = value.get("status", {})
    projected = _project_facts(status)
    if "native_release_verified" in projected:
        grouped["control_release"].append({"record_seq": None, "claim_kind": "host_status_release_assertion", "source_claims": projected})
    return grouped, len(timeline)


def _envelope(value, expected, declared_layer):
    _require(type(value) is dict and type(value.get("schema_version")) is int and value["schema_version"] == 1 and value.get("kind") == "tacticore_evidence_envelope", "envelope_schema_unsupported")
    _require(_binding(value.get("binding")) == expected, "source_binding_mismatch")
    _require(value.get("layer") == declared_layer, "source_layer_mismatch")
    records = value.get("records")
    _require(type(records) is list and len(records) <= MAX_RECORDS and value.get("complete") is True, "source_truncated")
    _require(type(value.get("record_count")) is int and value["record_count"] == len(records), "source_count_mismatch")
    ids, projected = set(), []
    for row in records:
        _require(type(row) is dict and _uuid(row.get("event_id")) and row["event_id"] not in ids, "duplicate_or_invalid_record_id")
        ids.add(row["event_id"])
        _check_present_binding(row, expected)
        _check_present_binding(row.get("facts"), expected)
        projected.append({"record_seq": len(projected) + 1, "event_id": row["event_id"], "claim_kind": "collector_envelope_assertion", "source_claims": _project_facts(row.get("facts"))})
    return {declared_layer: projected}, len(records)


def build_review_bundle(run_root, manifest_path, output_directory):
    """Index pinned sources into a NEW directory outside run_root. No game or network IO.

    Returns the public report. Per-source failures become invalid layer records;
    malformed manifests and unsafe output paths raise BundleError with fixed codes.
    """
    root = _not_link(run_root)
    _require(root.is_dir(), "run_root_missing")
    root = root.resolve()
    manifest = _not_link(manifest_path)
    manifest_raw = _read(manifest, 1024 * 1024)
    config = _strict_json(manifest_raw)
    _require(type(config) is dict and set(config) == {"schema_version", "binding", "sources"} and type(config["schema_version"]) is int and config["schema_version"] == 1, "invalid_manifest")
    expected = _binding(config["binding"])
    sources = config["sources"]
    _require(type(sources) is list and 0 < len(sources) <= MAX_SOURCES, "invalid_source_list")
    output = _not_link(output_directory)
    _require(not output.is_relative_to(root) and output != root and not root.is_relative_to(output), "output_overlaps_inputs")
    _require(not manifest.is_relative_to(output), "output_overlaps_manifest")
    _require(not output.exists(), "output_already_exists")
    seen_ids, seen_paths, seen_contents = set(), set(), set()
    diagnostic_sources = 0
    for source in sources:
        _require(type(source) is dict, "invalid_source_spec")
        required = {"source_id", "path", "sha256", "bytes", "adapter"}
        _require(required <= set(source) and not set(source) - required - {"layer"}, "invalid_source_spec")
        ident, path = source["source_id"], source["path"]
        _require(isinstance(ident, str) and _SOURCE_ID.fullmatch(ident) and ident not in seen_ids, "duplicate_or_invalid_source_id")
        _require(isinstance(path, str) and path.casefold() not in seen_paths, "duplicate_source_path")
        _source_path(root, path)
        seen_ids.add(ident); seen_paths.add(path.casefold())
        _require(type(source["bytes"]) is int and 0 <= source["bytes"] <= MAX_FILE_BYTES and isinstance(source["sha256"], str) and _HASH.fullmatch(source["sha256"]), "invalid_source_pin")
        _require(source["adapter"] in {"host_diagnostics_v1", "evidence_envelope_v1"}, "adapter_unsupported")
        _require((source["adapter"] == "evidence_envelope_v1" and source.get("layer") in LAYERS) or (source["adapter"] == "host_diagnostics_v1" and "layer" not in source), "invalid_source_layer")
        content_key = source["adapter"], source["sha256"]
        _require(content_key not in seen_contents, "duplicate_source_content")
        seen_contents.add(content_key)
        diagnostic_sources += source["adapter"] == "host_diagnostics_v1"
        _require(diagnostic_sources <= 1, "overlapping_diagnostics_sources")
    _require(sum(source["bytes"] for source in sources) <= MAX_TOTAL_INPUT_BYTES, "input_budget_exceeded")
    layers = {key: {"status": "missing", "source_ids": [], "records": [], "semantic_verification": "externally_unverified"} for key in LAYERS}
    index, reread, all_event_ids = [], [], set()
    for source in sources:
        row = {key: source[key] for key in ("source_id", "sha256", "bytes", "adapter")}
        try:
            path = _source_path(root, source["path"])
            raw = _read(path, MAX_FILE_BYTES)
            _require(len(raw) == source["bytes"] and _digest(raw) == source["sha256"], "source_pin_mismatch")
            parsed = _strict_json(raw)
            grouped, count = (_diagnostics(parsed, expected) if source["adapter"] == "host_diagnostics_v1"
                              else _envelope(parsed, expected, source["layer"]))
            event_ids = {record["event_id"] for records in grouped.values() for record in records if "event_id" in record}
            _require(not event_ids & all_event_ids, "duplicate_record_id_across_sources")
            all_event_ids.update(event_ids)
            reread.append((path, _digest(raw)))
            row.update(status="provided", record_count=count)
            for layer, records in grouped.items():
                if records:
                    if layers[layer]["status"] != "invalid": layers[layer]["status"] = "provided"
                    layers[layer]["source_ids"].append(source["source_id"])
                    layers[layer]["records"].extend(records)
        except BundleError as error:
            row.update(status="invalid", reason_code=str(error))
            for layer in ([source["layer"]] if "layer" in source else LAYERS):
                layers[layer]["status"] = "invalid"
                layers[layer]["source_ids"].append(source["source_id"])
        index.append(row)
    # Fail closed if any previously validated input changes before publication.
    _require(_read(manifest, 1024 * 1024) == manifest_raw, "manifest_changed")
    for path, digest in reread:
        _require(_digest(_read(path, MAX_FILE_BYTES)) == digest, "source_changed")
    _not_link(output)
    report = dict(schema_version=1, kind="tacticore_public_evidence_index", binding=expected,
                  input_manifest_sha256=_digest(manifest_raw), source_index=index, layers=layers,
                  review_status="structurally_complete" if all(v["status"] == "provided" for v in layers.values()) and all(v["status"] == "provided" for v in index) else "needs_attention",
                  semantic_verification="externally_unverified", full_goal_complete=False,
                  raw_files_included=False, source_paths_included=False,
                  limitations=["Hash and binding checks establish source consistency, not field truth.",
                               "Projected facts are source assertions, not independent game verification.",
                               "Host event sequence numbers are global across runs; completeness counters remain source assertions.",
                               "The original source manifest and raw evidence stay private and are not bundled."])
    # Output is an index only, with no source copying or mutable historical report.
    raw_report = _canonical(report) + b"\n"
    _require(len(raw_report) <= MAX_BUNDLE_BYTES, "output_budget_exceeded")
    output.mkdir(parents=True, exist_ok=False)
    (output / "review.json").write_bytes(raw_report)
    (output / "README.txt").write_text("Read review.json. provided means parsed, pinned, bound source material exists.\nIt does not mean gameplay was verified. Missing/invalid layers require more evidence.\nNo raw logs, input paths or arbitrary source text are included.\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_review_bundle(args.run_root, args.manifest, args.output)
        print(json.dumps({"review_status": report["review_status"], "layers": {k: v["status"] for k, v in report["layers"].items()}, "semantic_verification": "externally_unverified", "full_goal_complete": False}))
        return 0 if report["review_status"] == "structurally_complete" else 2
    except (BundleError, OSError) as error:
        print(json.dumps({"review_status": "rejected", "reason_code": str(error) if isinstance(error, BundleError) else "output_unavailable", "full_goal_complete": False}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
