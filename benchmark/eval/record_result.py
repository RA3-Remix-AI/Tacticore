"""Tag a finished run for evaluation and, for native-only matches, record its result.

Model-commanded runs already end with a match_end record written by the host;
for them this tool only writes eval-tag.json. Native-only baseline matches have
no host, so this tool also writes a minimal decisions.jsonl (run_start +
match_end) from one of:

- --native-state FILE: a native state captured by integration/watch_match.py
  (settlement-watch/result-candidate.json), mapped through
  match_participants.controlled_match_result;
- --result victory|defeat|unknown [--duration-s N]: a manually entered result
  after looking at the game's end screen.

    python benchmark/eval/record_result.py RUN_DIR --arm baseline_native \\
        --map map_mp_2_feasel6 --opponent-difficulty brutal --result victory --duration-s 812
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'integration') not in sys.path:
    sys.path.append(str(ROOT / 'integration'))

from host_runtime.decision_log import (  # noqa: E402
    FILE_NAME, SCHEMA_VERSION, decision_log_path, match_end_record, read_run_log,
)

TAG_FILE = 'eval-tag.json'
ARMS = ('baseline_native', 'model')


def write_tag(run_dir, *, arm, map_id, opponent_difficulty, prompt_version=None, model=None, label=None):
    """Write eval-tag.json; existing values are replaced."""
    tag = dict(arm=arm, map=map_id, opponent_difficulty=opponent_difficulty,
               prompt_version=prompt_version if arm == 'model' else None,
               model=model if arm == 'model' else None, label=label)
    path = Path(run_dir) / TAG_FILE
    path.write_text(json.dumps(tag, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return tag


def result_from_native_state(path, *, player_id=3, opponent_ids=(4,)):
    """(controlled_match_result, game_seconds) from a captured native state file."""
    from match_participants import controlled_match_result
    state = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    frame = state.get('simulation_frame')
    seconds = round(frame / 15, 3) if type(frame) is int and frame > 0 else None
    return controlled_match_result(state, player_id, tuple(opponent_ids)), seconds


def manual_result(result, *, player_id=3):
    """A controlled_match_result-shaped value for a manually confirmed outcome."""
    if result == 'unknown':
        return None
    return dict(terminal=True, controlled_outcome=result, players={str(player_id): dict(outcome=result)})


def record_match_end(run_dir, match_result, *, duration_s, source, visually_confirmed, map_id=None,
                     opponent_difficulty=None, player_id=3):
    """Append match_end to the run's log, creating run_start first when there is no log.

    A host log that already ends with match_end is never changed. A host log
    without one (for example after a crash) gets the recorded result appended.
    """
    existing = decision_log_path(run_dir)
    records = []
    if existing.exists():
        log = read_run_log(run_dir)
        if log['match_end'] is not None:
            raise ValueError('run already has a match_end record: ' + str(existing))
        run_id = (log['run'] or {}).get('run_id') or str(uuid.uuid4())
        path = existing
    else:
        run_id = str(uuid.uuid4())
        path = Path(run_dir) / FILE_NAME
        records.append(dict(schema_version=SCHEMA_VERSION, kind='run_start', run_id=run_id, wall_time=None,
                            prompt_version=None, provider=None, model=None, map_id=map_id,
                            opponent_difficulty=opponent_difficulty, player_id=player_id))
    end = match_end_record(run_id, match_result, game_time_s=duration_s, model_player_id=player_id,
                           reason_code='recorded_after_match')
    end.update(result_source=source, visually_confirmed=visually_confirmed)
    records.append(end)
    with path.open('a', encoding='utf-8') as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')
    return end


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--arm', choices=ARMS, required=True)
    parser.add_argument('--map', dest='map_id', required=True)
    parser.add_argument('--opponent-difficulty', required=True)
    parser.add_argument('--prompt-version', help='model arm only, e.g. v2')
    parser.add_argument('--model', help='model arm only, e.g. deepseek-chat')
    parser.add_argument('--label', help='free text shown nowhere in statistics')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--native-state', type=Path, help='watch_match.py result-candidate.json')
    source.add_argument('--result', choices=('victory', 'defeat', 'unknown'))
    parser.add_argument('--duration-s', type=float)
    parser.add_argument('--player', type=int, default=3)
    parser.add_argument('--opponents', default='4', help='comma separated opponent player ids')
    parser.add_argument('--visually-confirmed', action='store_true',
                        help='the result was checked on the game end screen')
    args = parser.parse_args(argv)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    tag = write_tag(args.run_dir, arm=args.arm, map_id=args.map_id, opponent_difficulty=args.opponent_difficulty,
                    prompt_version=args.prompt_version, model=args.model, label=args.label)
    print(json.dumps(dict(tag=tag), ensure_ascii=False))
    if args.native_state is None and args.result is None:
        return 0
    try:
        if args.native_state is not None:
            opponents = tuple(int(value) for value in args.opponents.split(',') if value.strip())
            result, seconds = result_from_native_state(args.native_state, player_id=args.player,
                                                       opponent_ids=opponents)
            source = 'native_result_slots'
        else:
            result, seconds, source = manual_result(args.result, player_id=args.player), None, 'manual_entry'
        end = record_match_end(args.run_dir, result, duration_s=args.duration_s or seconds, source=source,
                               visually_confirmed=args.visually_confirmed, map_id=args.map_id,
                               opponent_difficulty=args.opponent_difficulty, player_id=args.player)
    except (OSError, ValueError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps(dict(match_end=end), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
