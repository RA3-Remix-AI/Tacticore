"""Runtime goal completion; capability sources still use the frozen strict q.

A sourced short burst or kill can achieve its goal and return without proving
sustained firing. All damage, visibility, goal, retreat and release checks stay
mandatory. This module neither attaches to a game nor grants capabilities.
"""
import hashlib
import json
from pathlib import Path
import mission_combat_v6_qualification as strict

HERE=Path(__file__).resolve().parent
control_release=strict.control_release
progress=strict.progress


def runtime_result(result,report):
    checks=dict(result['checks'])
    if 'sustained_source_effect' not in checks:
        raise ValueError('Unknown strict V6 qualification contract')
    sustained_check=checks.pop('sustained_source_effect')
    verified=bool(checks) and all(value is True for value in checks.values())
    # Keep the original factual observation. Never call a one-hit kill a burst.
    return dict(result,checks=checks,
        status='continuous_ak_combat_mission_verified' if verified else 'not_passed',
        qualification_revision='runtime_goal_v6_v1',
        strict_qualification_revision=result.get('qualification_revision'),
        strict_burst_trace_verified=result['status']=='continuous_ak_combat_mission_verified',
        sustained_source_check=sustained_check,
        runtime_goal_verified=verified,
        harass_economy_verified=verified and report.get('request',{}).get('target_role')=='economy',
        fallback_field_effect_verified=verified and result.get('fallback_branch_observed') is True and result.get('fallback_replan_sequence_verified') is True)


def qualify(report):
    return runtime_result(strict.qualify(report),report)


def qualify_path(path):
    path=Path(path)
    result=runtime_result(strict.qualify_path(path),json.loads(path.read_text(encoding='utf-8-sig')))
    sources=list(result.get('supplemental_sources',[]))
    sources.append(dict(path=str(HERE/'mission_combat_v6_qualification.py'),
        sha256=hashlib.sha256((HERE/'mission_combat_v6_qualification.py').read_bytes()).hexdigest(),
        purpose='unchanged_strict_damage_goal_retreat_and_release_checks'))
    result.update(qualifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  supplemental_sources=sources)
    return result
