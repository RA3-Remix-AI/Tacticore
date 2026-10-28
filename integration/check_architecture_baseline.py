"""Preserve a non-secret source inventory and recheck frozen MF audit inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "strategy/reviews/architecture-iteration-audit-20261026-evidence.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    frozen = {}
    for name, expected in audit["files_at_audit"].items():
        if name.startswith(("acceptance/calibration/paid_pair_controller_v18", "tactical/mission-formation-v18/", "strategy/reviews/mf")):
            actual = digest(ROOT / name)
            frozen[name] = dict(expected_sha256=expected, actual_sha256=actual, unchanged=actual == expected)
    source = audit["mf18"]
    actual = digest(Path(source["raw_path"]))
    frozen[str(Path(source["raw_path"]).relative_to(ROOT)).replace("\\", "/")] = dict(
        expected_sha256=source["raw_sha256"], actual_sha256=actual, unchanged=actual == source["raw_sha256"])
    paths = set()
    for directory in ("integration/host_runtime", "desktop-ui/src", "desktop-ui/src-tauri/src", "tactical/runtime"):
        paths.update(p for p in (ROOT / directory).rglob("*") if p.is_file()
                     and p.suffix in (".py", ".rs", ".ts", ".tsx", ".css", ".h", ".cpp", ".ps1")
                     and "__pycache__" not in p.parts and "bin" not in p.relative_to(ROOT / directory).parts)
    paths.update((ROOT / "integration").glob("test_host_runtime_*.py"))
    paths.update(ROOT / name for name in ("docs/architecture-iteration-plan-20261026.md",
        "docs/architecture-implementation-status.md", "integration/battle_host.py", "strategy/battle_agent.py"))
    inventory = []
    for path in sorted(paths):
        before = path.read_bytes()
        inventory.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=len(before),
            sha256=hashlib.sha256(before).hexdigest(), stable_during_read=before == path.read_bytes()))
    return dict(schema_version=1, kind="architecture_recovery_source_inventory",
        created_at=datetime.now(timezone.utc).isoformat(),
        repository_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        audit_sha256=digest(AUDIT), frozen=frozen, all_frozen_unchanged=all(row["unchanged"] for row in frozen.values()),
        source_inventory=inventory, all_source_reads_stable=all(row["stable_during_read"] for row in inventory),
        game_access=False, model_requests=0, execution_authority_granted=False,
        note="Current recovery snapshot, not a claim that changing implementation files equal the original audit.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = snapshot()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(dict(output=str(args.output), source_files=len(report["source_inventory"]),
        all_frozen_unchanged=report["all_frozen_unchanged"], all_source_reads_stable=report["all_source_reads_stable"])))
    return 0 if report["all_frozen_unchanged"] and report["all_source_reads_stable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
