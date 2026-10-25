"""Read-only, whole-match tactical audit; dispatch counters are not effects.

Requalifies bound raw records rather than accepting the host's cached summary.
This reports bounded tactical effects, never attributes the match outcome to AI.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from continuous_contract import PROTOCOL
from continuous_evidence import terminal_facts

REQUIRED = {('attack', 'main_attack'), ('raid', 'harass_economy'),
            ('combined_arms', 'coordinate_force')}


def audit(session):
    run = Path(session['run_directory']).resolve()
    output = run / 'battle-host'
    scenario = session.get('scenario', {})
    identity = json.loads((output / 'identity.json').read_text(encoding='utf-8-sig'))
    status = json.loads((output / 'tactical-status.json').read_text(encoding='utf-8-sig'))
    entries = json.loads((output / 'tactical-dispatch-ledger.json').read_text(encoding='utf-8-sig'))
    binding = identity.get('binding', identity)
    commander = scenario['commander_id']
    if (identity.get('session_id') != session['session_id'] or
            identity.get('pid') != session['pid'] or
            binding.get('commander_id') != commander or
            binding.get('personality_binding_verified') is not True or
            identity.get('native', {}).get('player_index') != 3):
        raise ValueError('Match commander identity differs from recorded lobby')
    host = SimpleNamespace(session=session, binding=SimpleNamespace(
        session_id=session['session_id'], commander_id=commander, player_id=3))
    receipts = {r['task_id']: r for r in status.get('ledger', [])}
    effects, failures, unproved = [], [], []
    for task_id, saved in entries.items():
        entry = dict(saved, task_id=task_id)
        receipt = receipts.get(task_id)
        if not receipt:
            unproved.append(dict(task_id=task_id, reason='receipt_missing'))
            continue
        if receipt.get('status') != 'completed':
            failures.append(dict(task_id=task_id, module=entry['module'],
                                 status=receipt.get('status'), started=entry.get('started')))
            continue
        try:
            expected = dict(task_id=task_id, command_id=entry['command_id'],
                            seq=entry['seq'], session_id=session['session_id'],
                            commander_id=commander, player_id=3,
                            module=entry['module'], purpose=entry['purpose'],
                            object_ids=entry['object_ids'])
            if any(receipt.get(k) != v or type(receipt.get(k)) is not type(v)
                   for k, v in expected.items()):
                raise ValueError('Receipt identity mismatch')
            if entry.get('mission_protocol') != PROTOCOL or not entry.get('terminal'):
                raise ValueError('Not a completed continuous mission')
            facts = terminal_facts(host, receipt, entry)
            result = facts['qualification']
            native = facts['report']['native']
            target_hp = facts['report'].get('private_target', {}).get('hp')
            effects.append(dict(task_id=task_id, module=entry['module'],
                purpose=entry['purpose'], source_report=str(facts['path']),
                source_sha256=facts['sha256'],
                source_damage_amount=result['source_damage_amount'],
                qualified_hit_count=len(result.get('qualified_hits', [])),
                sustained_engagement_verified=result.get('sustained_engagement_verified') is True,
                observed_rounds_consumed=result.get('observed_rounds_consumed', 0),
                observed_reload_count=result.get('observed_reload_count', 0),
                damage_goal_reached=result.get('damage_goal_reached') is True,
                engagement_partial=result.get('engagement_partial'),
                remembered_navigation_observed=result.get('navigation_memory', {}).get('hidden_navigation_observed') is True,
                visibility_reacquired=result.get('navigation_memory', {}).get('reacquisition_observed') is True,
                hidden_approach_displacement=result.get('remembered_navigation_evidence', {}).get('maximum_hidden_displacement',0),
                target_hp_at_dispatch=target_hp,
                target_hp_at_engagement=result.get('engagement_initial_target_hp'),
                issued_frame=native['issued_frame'], returned_frame=native['returned_frame'],
                duration_game_seconds=(native['returned_frame']-native['issued_frame'])/15,
                long_approach_verified=result.get('long_approach_verified') is True,
                approach_verified=result.get('approach_verified') is True,
                retreat_verified=result.get('retreat_verified') is True,
                combined_arms_verified=result.get('combined_arms_verified') is True,
                target_role=facts['report']['request'].get('target_role'),
                target_object_id=facts['report']['request'].get('target_object_id')))
            if entry['purpose'] == 'harass_economy' and effects[-1]['target_role'] != 'economy':
                effects.pop()
                raise ValueError('Harassment did not affect an economic target')
        except (KeyError, ValueError, TypeError, OSError) as error:
            unproved.append(dict(task_id=task_id, reason=str(error)))
    covered = {(e['module'], e['purpose']) for e in effects}
    return dict(session_id=session['session_id'], pid=session['pid'], mutations=False,
        all_three_actual_effects_verified=REQUIRED <= covered and not unproved,
        execution_stopped=status.get('state') == 'stopped',
        nonterminal_task_ids=[task for task, entry in entries.items() if not entry.get('terminal')],
        settlement_and_control_release_review_required=True,
        total_verified_damage=sum(e['source_damage_amount'] for e in effects),
        sustained_mission_count=sum(e['sustained_engagement_verified'] for e in effects),
        verified_missions=effects, failed_or_cancelled=failures,
        unproved_completion_claims=unproved,
        missing_purposes=[list(x) for x in sorted(REQUIRED-covered)],
        scope='Actual bounded damage, approach, role geometry and retreat; '
              'does not establish economic suppression, strategic strength or victory causation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.session.read_text(encoding='utf-8-sig'))),
                     ensure_ascii=False, indent=2, allow_nan=False))
