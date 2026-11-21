"""Round 2 R1: how soon does the native AI override a command given to one of its own units?

Talks to an injected Ra3-Copilot on 127.0.0.1:17832 (only /objects, /obj and /order). One trial sends one
move or attack order, samples the unit every --interval seconds, classifies the trace and appends one JSON
line to --out. ``summary`` turns those lines into the situation x command table the round-2 doc asks for.

    python -X utf8 benchmark/r1_override.py units --owner 3
    python -X utf8 benchmark/r1_override.py trial --owner 3 --unit 0x1234ABCD --situation idle --act move
    python -X utf8 benchmark/r1_override.py trial --owner 3 --unit 0x... --situation attacking --act attack \\
        --target 0x...
    python -X utf8 benchmark/r1_override.py summary --out r1-trials.jsonl
"""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:17832"
SITUATIONS = ("idle", "attacking", "defending")
ACTS = ("move", "attack")

START_WITHIN_S = 5.0  # the unit must react this soon or the order counts as not started
PROGRESS_EPS = 25.0  # world units of approach that count as reacting
ARRIVE_RADIUS = 60.0  # a move is complete inside this radius of the goal
TURN_AWAY = 80.0  # moving this far back from the closest approach counts as turning away
SUSTAIN_S = 1.5  # ... when it lasts this long
HIT_QUIET_S = 3.0  # an attack is only overridden if the target took no damage in this window


def http(path, params=None, post=False):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    request = urllib.request.Request(url, data=b"" if post else None, method="POST" if post else "GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8", errors="replace")


def get_object(thing):
    """One object's state, or None when it no longer exists."""
    text = http("/obj", dict(addr=thing))
    return json.loads(text) if text.startswith("{") else None


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _first_sustained_turn_away(times, dists, *, from_index=0):
    """Index where the distance first rises TURN_AWAY above its running minimum and stays there SUSTAIN_S."""
    best = math.inf
    for i in range(from_index, len(dists)):
        best = min(best, dists[i])
        if dists[i] - best < TURN_AWAY:
            continue
        end = next((j for j in range(i, len(dists)) if dists[j] - best < TURN_AWAY), len(dists))
        if times[min(end, len(times) - 1)] - times[i] >= SUSTAIN_S or end == len(dists):
            return i
    return None


def classify_move(samples, goal):
    """started / arrived / overridden from a trace of {t, x, y}."""
    times = [s["t"] for s in samples]
    dists = [distance((s["x"], s["y"]), goal) for s in samples]
    started = any(dists[0] - d >= PROGRESS_EPS for t, d in zip(times, dists) if t <= START_WITHIN_S)
    arrived_at = next((t for t, d in zip(times, dists) if d <= ARRIVE_RADIUS), None)
    turn = _first_sustained_turn_away(times, dists)
    overridden_at = (
        times[turn] if started and turn is not None and (arrived_at is None or times[turn] < arrived_at) else None
    )
    left_after_arrival = None
    if arrived_at is not None:
        left_after_arrival = next((t for t, d in zip(times, dists) if t > arrived_at and d > 2 * ARRIVE_RADIUS), None)
    return dict(
        started=started,
        arrived_s=arrived_at,
        overridden_s=overridden_at,
        left_goal_after_arrival_s=left_after_arrival,
        final=(samples[-1]["x"], samples[-1]["y"]) if samples else None,
    )


def classify_attack(samples):
    """started / target_destroyed / overridden from a trace of {t, x, y, target_x, target_y, target_hp}."""
    times = [s["t"] for s in samples]
    alive = [s for s in samples if s.get("target_hp") is not None and s["target_hp"] > 0]
    destroyed_at = next((s["t"] for s in samples if not s.get("target_hp")), None)
    dists = [distance((s["x"], s["y"]), (s["target_x"], s["target_y"])) for s in alive]
    hp = [s["target_hp"] for s in alive]
    hit_times = [alive[i]["t"] for i in range(1, len(alive)) if hp[i] < hp[i - 1]]
    approached = any(dists[0] - d >= PROGRESS_EPS for s, d in zip(alive, dists) if s["t"] <= START_WITHIN_S)
    started = approached or any(t <= START_WITHIN_S for t in hit_times)
    turn = _first_sustained_turn_away([s["t"] for s in alive], dists)
    overridden_at = None
    if started and turn is not None:
        at = alive[turn]["t"]
        if not any(at - HIT_QUIET_S <= t <= at for t in hit_times):
            overridden_at = at
    return dict(
        started=started,
        target_destroyed_s=destroyed_at,
        overridden_s=overridden_at,
        target_hits=len(hit_times),
        final=(samples[-1]["x"], samples[-1]["y"]) if samples else None,
        duration_s=times[-1] if times else 0.0,
    )


def own_unit(thing, owner):
    unit = get_object(thing)
    if unit is None:
        raise SystemExit("error: unit not found: " + thing)
    if unit["ownerIdx"] != owner:
        raise SystemExit("error: unit belongs to owner " + str(unit["ownerIdx"]) + ", not the AI seat " + str(owner))
    return unit


def run_trial(args):
    unit = own_unit(args.unit, args.owner)
    params = dict(unit=args.unit, act=args.act)
    goal = None
    if args.act == "move":
        goal = (unit["x"] + args.dx, unit["y"] + args.dy) if args.x is None else (args.x, args.y)
        params.update(x=goal[0], y=goal[1], z=unit["z"] if args.z is None else args.z)
    else:
        target = get_object(args.target) if args.target else None
        if target is None or target["ownerIdx"] == args.owner:
            raise SystemExit("error: --target must be a live enemy object")
        params.update(target=args.target)
    reply = http("/order", params, post=True)
    started = time.monotonic()
    samples = []
    while time.monotonic() - started < args.duration:
        now = round(time.monotonic() - started, 3)
        current = get_object(args.unit)
        if current is None:
            break
        sample = dict(t=now, x=current["x"], y=current["y"], hp=current["hp"])
        if args.act == "attack":
            victim = get_object(args.target)
            sample.update(
                target_x=victim["x"] if victim else None,
                target_y=victim["y"] if victim else None,
                target_hp=victim["hp"] if victim else 0,
            )
            if victim is None:
                samples.append(sample)
                break
        samples.append(sample)
        time.sleep(args.interval)
    result = classify_move(samples, goal) if args.act == "move" else classify_attack(samples)
    record = dict(
        situation=args.situation,
        act=args.act,
        unit=args.unit,
        unit_name=unit.get("name"),
        order_reply=reply.strip()[:200],
        goal=goal,
        note=args.note,
        **result,
        samples=samples,
    )
    with open(args.out, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in record.items() if k != "samples"}, ensure_ascii=False))
    return 0


def summarize(records):
    """Markdown table: situation x command -> trials, started, overridden ratio and mean seconds."""
    groups = defaultdict(list)
    for record in records:
        groups[(record["situation"], record["act"])].append(record)
    lines = [
        "| 情况 | 命令 | 次数 | 开始执行 | 被覆盖 | 覆盖比例 | 平均覆盖时间（秒） | 完成 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for situation in SITUATIONS:
        for act in ACTS:
            rows = groups.get((situation, act), [])
            if not rows:
                continue
            started = [r for r in rows if r["started"]]
            overridden = [r["overridden_s"] for r in started if r["overridden_s"] is not None]
            done_key = "arrived_s" if act == "move" else "target_destroyed_s"
            done = sum(1 for r in rows if r.get(done_key) is not None)
            ratio = str(round(100 * len(overridden) / len(started))) + "%" if started else "—"
            mean = str(round(sum(overridden) / len(overridden), 1)) if overridden else "—"
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    situation, act, len(rows), len(started), len(overridden), ratio, mean, done
                )
            )
    return "\n".join(lines)


def list_units(args):
    reply = json.loads(http("/objects", dict(owner=args.owner, cat=0, limit=100, fresh=1)))
    for obj in reply.get("objects", []):
        print(obj["thing"], obj["name"], "x=%.0f y=%.0f hp=%.0f/%.0f" % (obj["x"], obj["y"], obj["hp"], obj["hpMax"]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    units = sub.add_parser("units", help="list the AI seat's units")
    units.add_argument("--owner", type=int, required=True)
    trial = sub.add_parser("trial", help="send one order and record what happens")
    trial.add_argument("--owner", type=int, required=True, help="the AI seat's owner index as Ra3-Copilot reports it")
    trial.add_argument("--unit", required=True)
    trial.add_argument("--situation", choices=SITUATIONS, required=True)
    trial.add_argument("--act", choices=ACTS, required=True)
    trial.add_argument("--target", help="enemy Thing address for attack (must be in the AI seat's view)")
    trial.add_argument("--dx", type=float, default=400.0)
    trial.add_argument("--dy", type=float, default=0.0)
    trial.add_argument("--x", type=float)
    trial.add_argument("--y", type=float)
    trial.add_argument("--z", type=float)
    trial.add_argument("--duration", type=float, default=60.0)
    trial.add_argument("--interval", type=float, default=0.25)
    trial.add_argument("--note", default="")
    trial.add_argument("--out", type=Path, default=Path("r1-trials.jsonl"))
    summary = sub.add_parser("summary", help="print the result table")
    summary.add_argument("--out", type=Path, default=Path("r1-trials.jsonl"))
    args = parser.parse_args(argv)
    if args.command == "units":
        return list_units(args)
    if args.command == "trial":
        if args.act == "move" and (args.x is None) != (args.y is None):
            parser.error("--x and --y go together")
        if args.act == "attack" and not args.target:
            parser.error("attack needs --target")
        return run_trial(args)
    records = [json.loads(line) for line in args.out.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(summarize(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
