"""Bounded, deterministic JSON replay. Inputs are explicitly synthetic."""
import json
from dataclasses import asdict

from engine import Binding, ContractError, Snapshot
from missions import MissionObservations, MissionProgress
from .planner import Limits, _digest, plan_for_snapshot


def replay(binding, purpose, rows, *, capability_purposes=(), allowed_roles=(), limits=None, generation=1):
    if not isinstance(rows, list) or len(rows) > 4096:
        raise ContractError("planning_replay_rows")
    memory = None
    output = []
    for row in rows:
        if type(row) is not dict or set(row) - {"snapshot", "game_frame", "monotonic_ms", "feedback", "stop_requested", "unavailable_formations"}:
            raise ContractError("planning_replay_fields")
        feedback = None
        if row.get("feedback") is not None:
            value = dict(row["feedback"])
            value["observations"] = MissionObservations(**value["observations"])
            value["formation_versions"] = tuple(tuple(item) for item in value["formation_versions"])
            feedback = MissionProgress(**value)
        snapshot = Snapshot.from_dict(row["snapshot"])
        if snapshot.source != "simulated":
            raise ContractError("planning_replay_synthetic_required")
        result = plan_for_snapshot(binding, snapshot, purpose, game_frame=row["game_frame"],
            monotonic_ms=row["monotonic_ms"], capability_purposes=capability_purposes,
            allowed_roles=allowed_roles, memory=memory, feedback=feedback, generation=generation,
            stop_requested=row.get("stop_requested", False), limits=limits,
            unavailable_formations=row.get("unavailable_formations", ()))
        output.append(result.public())
        # Never permit a new-generation task to be created by a binding switch.
        if result.action == "discard":
            break
        memory = result.memory
    return {"schema_version": 1, "kind": "synthetic_tactical_planning_replay", "purpose": purpose,
            "recommendations": output, "digest": _digest(output), "execution_authorized": False,
            "field_verified": False, "model_requests": 0, "game_commands": 0}


def main(argv=None):
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    if len(raw) > 8 * 1024 * 1024:
        raise ContractError("planning_replay_size")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:raise ContractError("planning_replay_duplicate_key")
            value[key] = item
        return value
    def invalid(_):raise ContractError("planning_replay_nonfinite")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if set(value) - {"binding", "purpose", "rows", "capability_purposes", "allowed_roles", "limits", "generation"}:
        raise ContractError("planning_replay_document")
    out = replay(Binding(**value["binding"]), value["purpose"], value["rows"],
                 capability_purposes=value.get("capability_purposes", ()), allowed_roles=value.get("allowed_roles", ()),
                 limits=Limits(**value.get("limits", {})), generation=value.get("generation", 1))
    print(json.dumps(out, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
