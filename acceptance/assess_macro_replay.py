"""Compare original native budget adoption with a separately observed plain replay."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
load=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
rows=lambda path:[json.loads(s) for s in path.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','field','watch','original-watch','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_replay_assessment_required')
    archive=load(a.run/'research-settlement.json');replay=a.run/archive['replay']
    latest=ROOT.parent/'Replays/最新录像.RA3Replay';report=load(a.watch/'report.json')
    if sha(replay)!=archive['replay_sha256'] or sha(latest)!=sha(replay) or report['replay_sha256']!=sha(replay):
        raise ValueError('selected_replay_archive_mismatch')
    original=[r['observation'] for r in rows(a.field/'transport/policy-probe.jsonl')
        if r['kind']=='macro_observation' and r.get('observation',{}).get('budget_feedback',{}).get('selected_macro_flag')]
    flag=next(r['budget_feedback']['selected_macro_flag'] for r in original
        if r['budget_feedback']['selected_macro_flag'].endswith('_budgettech'))
    adopted=[r for r in original if r['budget_feedback']['selected_macro_flag']==flag]
    lo=min(r['frame'] for r in adopted);hi=max(r['frame'] for r in adopted)
    observations=rows(a.watch/'replay-native-observations.jsonl')
    comparable=[r for r in observations if lo<=r['frame']<=hi and isinstance(r.get('budget_feedback'),dict)]
    selected=[r for r in comparable if r['budget_feedback']['selected_macro_flag']==flag]
    enabled=[r for r in comparable if any(f['name']==flag and f['present'] and f['value'] is True for f in r['flags']['flags'])]
    original_live=max(r.get('simulation_frame',0) for r in rows(a.original_watch/'native-match-transitions.jsonl'))
    screenshots=[a.run/'replay-loaded.png',a.run/'replay-settlement-fastforward.png',a.run/'replay-settlement-constant.png']
    if not all(path.is_file() for path in screenshots):raise ValueError('reviewed_replay_screenshots_required')
    value=dict(kind='plain_macro_replay_fidelity_assessment',session_id=archive['session_id'],replay_sha256=sha(replay),
        original_technology_adoption_frames=[lo,hi],original_technology_samples=len(adopted),
        replay_comparable_samples=len(comparable),replay_technology_selected_samples=len(selected),
        replay_technology_gate_true_samples=len(enabled),
        technology_gate_not_reproduced=len(comparable)>=2 and not enabled and not selected,
        original_last_live_frame=original_live,replay_last_observed_frame=report['last_frame'],
        replay_native_read_errors=report['read_errors'],replay_ended_before_original_frame=report['last_frame']+30<original_live,
        actual_game_replay_loaded=True,actual_replay_statistics_screen_observed=True,
        selected_latest_still_matches_original_archive=True,
        plain_replay_full_macro_match_verified=False,macro_replay_fidelity_verified=False,
        causal_explanation_verified=False,
        candidate_explanation='Direct native flag setter is outside the recorded command path; additional replay divergence causes remain unqualified.',
        model_calls_during_playback=report['model_calls'],native_commands_during_playback=report['native_commands'],
        process_writes_during_playback=report['process_writes'],formal_goal_complete=False,
        evidence={str(path.resolve()):sha(path) for path in [replay,a.watch/'report.json',
            a.watch/'replay-native-observations.jsonl',a.field/'transport/policy-probe.jsonl',*screenshots]})
    out.mkdir(parents=True);shutil.copy2(__file__,out/'assessor.py');value['assessor_sha256']=sha(out/'assessor.py')
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))


if __name__=='__main__':main()
