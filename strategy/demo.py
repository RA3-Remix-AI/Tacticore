"""Offline acceptance demo: never opens a game, endpoint, or credential store."""
import argparse
import asyncio
import json
from pathlib import Path

from engine import StrategyEngine
from fixtures import binding, policy, snapshot


async def run(output: Path, fixture_output: Path | None):
    output.mkdir(parents=True, exist_ok=True)
    engine = StrategyEngine(binding(), timeout_seconds=.02, audit_path=output/"plans.jsonl", status_path=output/"status.json")
    idle = engine.public_status()
    async def valid(context):
        return policy(context)
    accepted = await engine.decide(snapshot(), valid)
    offline = engine.public_status()
    async def invalid(context):
        return policy(context, production_focus="not_a_registered_focus")
    continued = await engine.decide(snapshot(2, 116), invalid)
    async def timeout(_):
        await asyncio.sleep(5)
    fallback = await engine.decide(snapshot(3, 132), timeout)
    if fixture_output:
        fixture_output.mkdir(parents=True, exist_ok=True)
        for name, payload in [("idle-status.json", idle), ("offline-status.json", offline), ("fallback-status.json", engine.public_status()), ("snapshot.json", snapshot())]:
            (fixture_output/name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        context = engine.latest.model_context(engine.binding)
        (fixture_output/"policy.json").write_text(json.dumps(policy(context), ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "scope": "offline_simulation_only", "real_model_called": False, "game_commands_executed": False,
        "accepted": accepted.status, "invalid_response": continued.status, "timeout": fallback.status,
        "metrics": engine.metrics, "status_file": str(output/"status.json"), "audit_file": str(output/"plans.jsonl"),
    }
    (output/"acceptance.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent/"runtime")
    parser.add_argument("--write-fixtures", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.output, args.write_fixtures))
