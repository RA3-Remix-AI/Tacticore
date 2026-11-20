"""One append-only, human-oriented decision log per host run: decisions.jsonl.

Every line is one JSON object with schema_version=1, run_id and a kind:

- run_start: run configuration (prompt version, model, map, difficulty).
- decision: one record per model decision cycle: the situation the model saw,
  what it decided (with its own short reasoning), what happened to that
  decision, and the model call itself.
- effects: later observations for one decision (native AI reaction, own army
  change by the next decision). Readers fold these into that decision's
  outcome.observed_effects, so the file itself stays append-only.
- match_end: the final result, written once when the host stops.

Values come only from what the host already observed; unknown stays null and
nothing is inferred into a success claim. Writing never raises into the host.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

SCHEMA_VERSION = 1
FILE_NAME = 'decisions.jsonl'
REASONING_MAX_CHARS = 300
MAX_TEXT_CHARS = 160
MAX_THREATS = 6
MAX_EFFECTS = 12
MAX_ENEMIES = 8
MAX_INTENTS = 8

OUTCOME_STATUSES = ('applied', 'rejected', 'expired', 'unknown')
RESULTS = ('victory', 'defeat', 'unknown')
# Reason codes that mean "the decision arrived or waited too long to be used".
EXPIRED_REASONS = frozenset({
    'stale_response', 'expired_response', 'expired_or_paused',
    'macro_plan_expired_before_native_dispatch', 'macro_admission_v4_plan_expired_before_native',
})
# Reason codes that mean "delivery to the native AI is not known either way".
UNKNOWN_REASONS = frozenset({'macro_dispatch_outcome_unknown'})
# Host stop reasons that occur only between loop iterations, never mid-dispatch.
ORDERLY_STOP_REASONS = frozenset({'user_stop', 'host_time_limit'})


# ---------------------------------------------------------------------------
# Small value helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _number(value):
    """Return a finite int/float, or None for anything else (including bool)."""
    if type(value) in (int, float) and math.isfinite(value):
        return value
    return None


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _short(value, limit=MAX_TEXT_CHARS):
    if not isinstance(value, str):
        return None
    text = ' '.join(value.split())
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + '…'
    return text or None


def _seconds(value):
    number = _number(value)
    return round(number, 3) if number is not None else None


def _sum_counts(mapping):
    if not isinstance(mapping, dict):
        return None
    values = [value for value in mapping.values() if type(value) is int and value >= 0]
    return sum(values) if values or not mapping else None


def _public_context(context):
    """Undo the reversible prompt packing so field names are the public ones."""
    try:
        from macro_policy import restore_public_defaults
        return restore_public_defaults(context)
    except Exception:
        return context


# ---------------------------------------------------------------------------
# Situation summary (what the model saw)
# ---------------------------------------------------------------------------

def situation_from_context(context):
    """Summarize the exact request context into own/enemies/threats."""
    if not isinstance(context, dict):
        return dict(own=dict(credits=None, income_hint=None, army_count=None, building_count=None),
                    enemies=[], threats=[])
    public = _public_context(context)
    working = public.get('working_memory') if isinstance(public.get('working_memory'), dict) else {}
    return dict(own=_own_summary(public, working), enemies=_enemy_summary(working),
                threats=_threats(public, working))


def _own_summary(public, working):
    economy = working.get('economy') if isinstance(working.get('economy'), dict) else {}
    forces = public.get('own_forces') if isinstance(public.get('own_forces'), dict) else {}
    army = _sum_counts(forces.get('mobile_role_counts'))
    if army is None:
        # Fallback: audited own role counts from the economy section.
        army = _sum_counts(economy.get('own_roles'))
    collectors = None
    if isinstance(forces.get('economic_unit_presence_counts'), dict):
        collectors = _count(forces['economic_unit_presence_counts'].get('ore_collector'))
    return dict(
        credits=_number(economy.get('credits')),
        income_hint=(str(collectors) + ' ore collectors') if collectors is not None else None,
        army_count=army,
        building_count=_sum_counts(forces.get('building_presence_counts')),
        power_balance=_number(economy.get('power_balance')),
    )


def _enemy_groups(battlefield):
    """Yield (owner, newest_seen_s, visible_observations) for enemy contacts."""
    groups = battlefield.get('contact_groups')
    if isinstance(groups, list):
        for row in groups:
            if not isinstance(row, dict) or row.get('relation') != 'enemy':
                continue
            count = _count(row.get('observations')) or 0
            visible = count if row.get('currently_visible') is True else 0
            yield row.get('owner_player_id'), _number(row.get('newest_game_seconds')), visible
        return
    for row in battlefield.get('contacts') or []:
        if not isinstance(row, dict) or row.get('relation') != 'enemy':
            continue
        visible = 1 if row.get('currently_visible') is True else 0
        yield row.get('owner_player_id'), _number(row.get('observed_at_game_seconds')), visible


def _enemy_summary(working):
    match = working.get('match_state') if isinstance(working.get('match_state'), dict) else {}
    opponents = [pid for pid in match.get('opponent_player_ids') or [] if type(pid) is int]
    defeated = {pid for pid in match.get('defeated_opponent_ids') or [] if type(pid) is int}
    humans = {pid for pid in match.get('human_player_ids') or [] if type(pid) is int}
    battlefield = working.get('battlefield') if isinstance(working.get('battlefield'), dict) else {}
    seen = {}
    for owner, newest, visible in _enemy_groups(battlefield):
        key = owner if type(owner) is int else None
        last, count = seen.get(key, (None, 0))
        if newest is not None and (last is None or newest > last):
            last = newest
        seen[key] = (last, count + visible)
    order = opponents + sorted(pid for pid in seen if pid is not None and pid not in opponents)
    if None in seen:
        order.append(None)
    enemies = []
    for pid in order[:MAX_ENEMIES]:
        last, count = seen.get(pid, (None, 0))
        known = pid in opponents
        enemies.append(dict(player_id=pid, last_seen_s=_seconds(last), visible_count=count,
                            defeated=(pid in defeated) if known else None,
                            human=(pid in humans) if known and 'human_player_ids' in match else None))
    return enemies


def _threats(public, working):
    threats = []
    summary = public.get('battlefield_summary')
    if isinstance(summary, dict):
        near_home = _count(summary.get('nearby_home_enemy_mobile_observations'))
        if near_home:
            threats.append(str(near_home) + ' enemy units near home')
        for row in summary.get('mining_regions') or []:
            if not isinstance(row, dict):
                continue
            nearby = _count(row.get('nearby_enemy_mobile_observations'))
            if nearby:
                region = _short(row.get('region_id'), 48) or 'unknown region'
                threats.append(str(nearby) + ' enemy units near mining region ' + region)
    else:
        threats.extend(_threats_in_own_regions(working))
    change = working.get('own_combat_change')
    if isinstance(change, dict) and type(change.get('net_change')) is int and change['net_change'] < 0:
        since = _seconds(change.get('since_game_seconds'))
        suffix = ' since ' + str(since) + 's' if since is not None else ''
        threats.append('own army shrank by ' + str(-change['net_change']) + suffix)
    return threats[:MAX_THREATS]


def _threats_in_own_regions(working):
    """Without a battlefield summary, report visible enemy units in own regions."""
    battlefield = working.get('battlefield') if isinstance(working.get('battlefield'), dict) else {}
    own = {row.get('region_id') for row in battlefield.get('regions') or []
           if isinstance(row, dict) and row.get('relation') == 'self'}
    counts = {}
    for row in battlefield.get('contact_groups') or []:
        if (not isinstance(row, dict) or row.get('relation') != 'enemy' or row.get('currently_visible') is not True
                or row.get('region_id') not in own or row.get('role') in ('structure', 'economy')):
            continue
        counts[row['region_id']] = counts.get(row['region_id'], 0) + (_count(row.get('observations')) or 0)
    return [str(count) + ' enemy units seen in own region ' + str(region)
            for region, count in sorted(counts.items()) if count]


# ---------------------------------------------------------------------------
# Decision and response summaries
# ---------------------------------------------------------------------------

def _plan_decision(plan):
    strategy = plan.macro_strategy if isinstance(plan.macro_strategy, dict) else {}
    return dict(
        intents=list(plan.macro_actions)[:MAX_INTENTS],
        objective=_short(strategy.get('objective'), 48),
        reasoning=_short(getattr(plan, 'reasoning', None), REASONING_MAX_CHARS),
        valid_for_s=_seconds(plan.expires_at_game_seconds - plan.based_on_game_time_seconds),
        objective_region=_short(plan.objective_region, 48),
        plan_id=plan.plan_id,
        source='validated_plan',
    )


def response_decision(response):
    """Bounded summary of an unvalidated model response (used when it was rejected)."""
    if isinstance(response, (str, bytes)):
        try:
            response = json.loads(response)
        except (ValueError, UnicodeError):
            response = None
    if not isinstance(response, dict):
        return dict(intents=[], objective=None, reasoning=None, valid_for_s=None,
                    objective_region=None, plan_id=None, source=None)
    actions = response.get('macro_actions')
    intents = [_short(a, 40) for a in actions if isinstance(a, str)] if isinstance(actions, list) else []
    strategy = response.get('macro_strategy') if isinstance(response.get('macro_strategy'), dict) else {}
    return dict(
        intents=[a for a in intents if a][:MAX_INTENTS],
        objective=_short(strategy.get('objective'), 48),
        reasoning=_short(response.get('reasoning'), REASONING_MAX_CHARS),
        valid_for_s=_seconds(response.get('valid_for_game_seconds')),
        objective_region=_short(response.get('objective_region'), 48),
        plan_id=None,
        source='unvalidated_response',
    )


def outcome_status_for(reason_code):
    """Map a not-applied reason code to rejected/expired/unknown."""
    if reason_code in UNKNOWN_REASONS:
        return 'unknown'
    if reason_code in EXPIRED_REASONS:
        return 'expired'
    return 'rejected'


_FEEDBACK_TEXT = {
    'native_task_active': 'native task active',
    'native_manager_state_observed': 'native builder state changed',
    'native_enemy_priority_observed': 'native enemy priority set',
}


def feedback_effects(observations, actions):
    """Short strings for positive native feedback rows about the given actions."""
    effects = []
    for row in observations or []:
        if not isinstance(row, dict) or row.get('action') not in actions:
            continue
        text = _FEEDBACK_TEXT.get(row.get('status'))
        if text is None:
            continue
        if row.get('status') == 'native_manager_state_observed' and row.get('component_state_adopted') is not True:
            continue
        if row.get('movement_observed') is True:
            text += ', units moving'
        effects.append(row['action'] + ': ' + text)
    return effects


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------

def _role(player, model_player_id, opponent_player_ids):
    if player == str(model_player_id):
        return 'self'
    if opponent_player_ids is None:
        return None
    return 'opponent' if player in {str(pid) for pid in opponent_player_ids} else 'ally'


def match_end_record(run_id, match_result, *, game_time_s=None, model_player_id=3, reason_code=None,
                     opponent_player_ids=None):
    """Build the final record from controlled_match_result() output (or None).

    Only a terminal native result slot yields victory/defeat. A quit, an
    unfinished match or a missing result stays 'unknown'. Native results still
    require visual confirmation; this record says so explicitly.
    """
    result, native_outcome, players = 'unknown', None, {}
    remaining, all_defeated, source = None, None, None
    if isinstance(match_result, dict):
        source = 'native_result_slots'
        for key, row in (match_result.get('players') or {}).items():
            if not isinstance(row, dict):
                continue
            player = str(key)
            players[player] = dict(outcome=_short(row.get('outcome'), 16),
                                   role=_role(player, model_player_id, opponent_player_ids))
        native_outcome = _short(match_result.get('controlled_outcome'), 16)
        if match_result.get('terminal') is True and native_outcome in ('victory', 'defeat'):
            result = native_outcome
        remaining = _count(match_result.get('remaining_opponents'))
        if type(match_result.get('all_opponents_defeated')) is bool:
            all_defeated = match_result['all_opponents_defeated']
    return dict(schema_version=SCHEMA_VERSION, kind='match_end', run_id=run_id, wall_time=_now_iso(),
                result=result, duration_s=_seconds(game_time_s), players=players,
                native_outcome=native_outcome, remaining_opponents=remaining,
                all_opponents_defeated=all_defeated, result_source=source,
                visually_confirmed=False, reason_code=_short(reason_code, 80))


def run_config_from_scenario(scenario):
    """Map, opponent difficulty and teams from a session.json scenario block.

    Uses host_runtime.scenario.MatchScenario (current or legacy shape); fields
    it cannot establish stay None. Lobby difficulty is as configured, not
    verified in memory.
    """
    raw = scenario if isinstance(scenario, dict) else {}
    config = dict(map_id=raw.get('map_id'), opponent_difficulty=raw.get('opponent_difficulty'), mode=None,
                  model_player_id=None, enemy_player_ids=None, ally_player_ids=None, human_player_ids=None)
    try:
        from .scenario import MatchScenario
        match = MatchScenario.from_session(raw)
    except Exception:
        return config
    enemies = match.enemy_player_ids
    levels = sorted({row.difficulty for row in match.players if row.player_id in enemies and row.difficulty})
    config.update(map_id=match.map_id, mode=match.mode, model_player_id=match.model_player_id,
                  enemy_player_ids=list(enemies), ally_player_ids=list(match.ally_player_ids),
                  human_player_ids=list(match.human_player_ids))
    if config['opponent_difficulty'] is None and levels:
        config['opponent_difficulty'] = '/'.join(levels)
    return config


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class DecisionLogWriter:
    """Builds decision records from host events; one instance per host run.

    The host forwards every event to observe_event(), calls decided() with
    each finished agent decision and finish() once when it stops. All public
    methods swallow their own errors (counted in .errors): logging must never
    change what the host does.
    """

    def __init__(self, directory, run_id, *, prompt_version=None, provider=None, model=None,
                 map_id=None, opponent_difficulty=None, player_id=3, opponent_player_ids=None,
                 run_facts=None, response_supplier=None, monotonic=time.monotonic):
        self.path = Path(directory) / FILE_NAME
        self.run_id = run_id
        self.prompt_version = prompt_version
        self.provider = provider
        self.model = model
        self.map_id = map_id
        self.opponent_difficulty = opponent_difficulty
        self.player_id = player_id
        self.opponent_player_ids = list(opponent_player_ids) if opponent_player_ids is not None else None
        # Extra run_start fields (mode, team lists); never overrides the core ones.
        self.run_facts = dict(run_facts or {})
        self._response_supplier = response_supplier
        self._monotonic = monotonic
        self._seq = 0
        self._cycle = None
        self._active = None
        self.errors = 0
        self.finished = False

    # -- host-facing API ----------------------------------------------------

    def start(self):
        record = dict(self.run_facts)
        record.update(schema_version=SCHEMA_VERSION, kind='run_start', run_id=self.run_id, wall_time=_now_iso(),
                      prompt_version=self.prompt_version, provider=self.provider, model=self.model,
                      map_id=self.map_id, opponent_difficulty=self.opponent_difficulty, player_id=self.player_id,
                      opponent_player_ids=self.opponent_player_ids)
        self._guard(self._write, record)

    def observe_event(self, kind, facts):
        self._guard(self._observe_event, kind, facts if isinstance(facts, dict) else {})

    def decided(self, decision):
        self._guard(self._decided, decision)

    def finish(self, *, match_result=None, game_time_s=None, reason_code=None):
        self._guard(self._finish, match_result, game_time_s, reason_code)

    # -- internals ------------------------------------------------------------

    def _guard(self, method, *args):
        if self.finished:
            return
        try:
            method(*args)
        except Exception:
            self.errors += 1

    def _write(self, record):
        line = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')

    def _observe_event(self, kind, facts):
        handler = {
            'model_macro_request_context': self._on_request,
            'commander_model_call_started': self._on_call_started,
            'commander_model_response_returned': self._on_call_returned,
            'commander_model_call_failed': self._on_call_failed,
            'commander_model_call_cancelled': self._on_call_cancelled,
            'macro_policy_acknowledged': self._on_acknowledged,
            'plan_applied': self._on_applied,
            'macro_plan_not_dispatched': self._on_not_dispatched,
            'macro_unified_feedback': self._on_unified_feedback,
            'macro_native_feedback': self._on_budget_feedback,
        }.get(kind)
        if handler is not None:
            handler(facts)

    def _on_request(self, facts):
        context = facts.get('context')
        situation = situation_from_context(context)
        game_time = _seconds(context.get('game_time_seconds')) if isinstance(context, dict) else None
        self._close_cycle('not_dispatched', 'decision_not_observed')
        self._close_active(situation, game_time)
        self._cycle = dict(game_time_s=game_time, wall_time=_now_iso(), situation=situation,
                           input_bytes=_count(facts.get('context_bytes')), output_bytes=None,
                           call_started=None, latency_ms=None, error=None, response=None,
                           plan=None, native_accepted=None)

    def _on_call_started(self, facts):
        if self._cycle is not None:
            self._cycle['call_started'] = self._monotonic()

    def _stop_clock(self):
        started = self._cycle.get('call_started')
        if started is not None:
            self._cycle['latency_ms'] = int(round((self._monotonic() - started) * 1000))

    def _on_call_returned(self, facts):
        if self._cycle is None:
            return
        self._stop_clock()
        receipt = facts.get('transport_receipt')
        if isinstance(receipt, dict):
            self._cycle['input_bytes'] = _count(receipt.get('request_bytes')) or self._cycle['input_bytes']
            self._cycle['output_bytes'] = _count(receipt.get('response_bytes'))
        if self._response_supplier is not None:
            self._cycle['response'] = response_decision(self._response_supplier())

    def _on_call_failed(self, facts):
        if self._cycle is None:
            return
        self._stop_clock()
        diagnostics = facts.get('backend_diagnostics')
        code = diagnostics.get('error_code') if isinstance(diagnostics, dict) else None
        self._cycle['error'] = _short(code, 80) or 'model_call_failed'

    def _on_call_cancelled(self, facts):
        if self._cycle is not None:
            self._stop_clock()
            self._cycle['error'] = 'model_call_cancelled'

    def _decided(self, decision):
        if self._cycle is None or decision is None:
            return
        status = getattr(decision, 'status', None)
        plan = getattr(decision, 'plan', None)
        if status == 'accepted' and plan is not None:
            self._cycle['plan'] = plan
            return
        reason = _short(getattr(decision, 'reason_code', None), 80) or 'decision_not_accepted'
        if self._cycle['error'] is None and reason in ('model_timeout', 'adapter_error', 'adapter_cancelled'):
            self._cycle['error'] = reason
        self._emit_decision(outcome_status_for(reason), reason, native_accepted=False)

    def _plan_matches(self, facts):
        plan = self._cycle.get('plan') if self._cycle is not None else None
        return plan is not None and facts.get('plan_id') == plan.plan_id

    def _on_acknowledged(self, facts):
        if self._plan_matches(facts) and facts.get('native_gate_acknowledged') is True:
            self._cycle['native_accepted'] = True

    def _on_applied(self, facts):
        if not self._plan_matches(facts):
            return
        plan = self._cycle['plan']
        record = self._emit_decision('applied', 'plan_applied', native_accepted=self._cycle['native_accepted'])
        self._active = dict(seq=record['seq'], actions=set(plan.macro_actions),
                            expires_s=_number(plan.expires_at_game_seconds), situation=record['situation'],
                            effects=[])

    def _on_not_dispatched(self, facts):
        if self._plan_matches(facts):
            reason = _short(facts.get('reason_code'), 80) or 'not_dispatched'
            self._emit_decision(outcome_status_for(reason), reason, native_accepted=False)

    def _close_cycle(self, accepted_reason, open_reason, *, status_for_accepted='rejected'):
        """Write a cycle that never reached a dispatch outcome.

        An accepted plan that was never dispatched is 'rejected' (known not
        delivered) unless the caller says delivery is unknown. A cycle without
        any decision is always 'unknown'.
        """
        if self._cycle is None:
            return
        if self._cycle.get('plan') is None:
            self._emit_decision('unknown', open_reason, native_accepted=None)
            return
        delivered = None if status_for_accepted == 'unknown' else False
        self._emit_decision(status_for_accepted, accepted_reason, native_accepted=delivered)

    def _emit_decision(self, status, reason_code, *, native_accepted):
        cycle, self._cycle = self._cycle, None
        plan = cycle.get('plan')
        decision = _plan_decision(plan) if plan is not None else (cycle.get('response') or response_decision(None))
        self._seq += 1
        record = dict(
            schema_version=SCHEMA_VERSION, kind='decision', run_id=self.run_id, seq=self._seq,
            prompt_version=self.prompt_version, game_time_s=cycle['game_time_s'], wall_time=cycle['wall_time'],
            situation=cycle['situation'], decision=decision,
            outcome=dict(status=status, reason_code=reason_code, native_accepted=native_accepted,
                         observed_effects=[]),
            model=dict(provider=self.provider, model=self.model, latency_ms=cycle['latency_ms'],
                       input_bytes=cycle['input_bytes'], output_bytes=cycle['output_bytes'],
                       error=cycle['error']))
        self._write(record)
        return record

    # -- observed effects -----------------------------------------------------

    def _add_effects(self, effects, game_time, *, final=False):
        """Append the full effects list when it grows, or once when tracking ends."""
        new = [text for text in effects if text not in self._active['effects']]
        if not new and not final:
            return
        self._active['effects'] = (self._active['effects'] + new)[:MAX_EFFECTS]
        self._write(dict(schema_version=SCHEMA_VERSION, kind='effects', run_id=self.run_id,
                         seq=self._active['seq'], game_time_s=game_time,
                         observed_effects=list(self._active['effects']), final=final))

    def _within_window(self, game_time):
        expires = self._active.get('expires_s')
        return game_time is None or expires is None or game_time <= expires

    def _on_unified_feedback(self, facts):
        if self._active is None:
            return
        frame = _number(facts.get('observed_frame'))
        game_time = _seconds(frame / 15) if frame is not None else None
        if self._within_window(game_time):
            self._add_effects(feedback_effects(facts.get('observations'), self._active['actions']), game_time)

    def _on_budget_feedback(self, facts):
        if self._active is None:
            return
        selected = facts.get('selected_policy')
        frame = _number(facts.get('observed_frame'))
        game_time = _seconds(frame / 15) if frame is not None else None
        if (facts.get('status') == 'native_budget_adopted' and selected in self._active['actions']
                and self._within_window(game_time)):
            self._add_effects([selected + ': native spending weights adopted'], game_time)

    def _close_active(self, situation, game_time):
        """Record own/enemy changes between the applied decision and the next one."""
        if self._active is None:
            return
        before, after = self._active['situation'], situation
        effects = []
        label = ' (by ' + str(game_time) + 's)' if game_time is not None else ''
        for key, name in (('army_count', 'own army'), ('building_count', 'own buildings')):
            old, new = before['own'].get(key), after['own'].get(key)
            if old is not None and new is not None and old != new:
                effects.append(name + ' ' + str(old) + ' -> ' + str(new) + label)
        was_defeated = {row['player_id'] for row in before['enemies'] if row.get('defeated')}
        for row in after['enemies']:
            if row.get('defeated') and row['player_id'] not in was_defeated:
                effects.append('enemy player ' + str(row['player_id']) + ' defeated' + label)
        self._add_effects(effects, game_time, final=True)
        self._active = None

    def _finish(self, match_result, game_time_s, reason_code):
        reason = _short(reason_code, 80)
        if reason in ORDERLY_STOP_REASONS:
            # The loop stops between iterations, so a pending plan was never sent.
            self._close_cycle('host_stopped_before_dispatch', 'host_stopped_during_model_call')
        else:
            # A fault may interrupt a dispatch: delivery is not known either way.
            self._close_cycle(reason or 'host_stopped', 'host_stopped_during_model_call',
                              status_for_accepted='unknown')
        self._active = None
        self._write(match_end_record(self.run_id, match_result, game_time_s=game_time_s,
                                     model_player_id=self.player_id, reason_code=reason,
                                     opponent_player_ids=self.opponent_player_ids))
        self.finished = True


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def decision_log_path(run_dir):
    """Accept the host output directory or the run directory containing battle-host/."""
    directory = Path(run_dir)
    direct = directory / FILE_NAME
    if direct.exists():
        return direct
    nested = directory / 'battle-host' / FILE_NAME
    return nested if nested.exists() else direct


def read_lines(path):
    """Parse valid schema-1 lines; skip blank, invalid or partially written lines."""
    records, invalid = [], 0
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return records, invalid
    for line in raw.decode('utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError:
            invalid += 1
            continue
        if isinstance(value, dict) and value.get('schema_version') == SCHEMA_VERSION:
            records.append(value)
        else:
            invalid += 1
    return records, invalid


def read_run_log(run_dir):
    """Return {run, decisions, match_end, invalid_lines} with effects folded in."""
    lines, invalid = read_lines(decision_log_path(run_dir))
    run, match_end, decisions, effects, closed = None, None, {}, {}, set()
    for record in lines:
        kind = record.get('kind')
        if kind == 'run_start' and run is None:
            run = record
        elif kind == 'match_end':
            match_end = record
        elif kind == 'decision' and type(record.get('seq')) is int:
            decisions[record['seq']] = record
        elif kind == 'effects' and type(record.get('seq')) is int:
            effects[record['seq']] = record
            if record.get('final') is True:
                closed.add(record['seq'])
    last_seq = max(decisions, default=0)
    merged = []
    for seq in sorted(decisions):
        record = json.loads(json.dumps(decisions[seq]))
        update = effects.get(seq)
        outcome = record.setdefault('outcome', {})
        if update is not None and isinstance(update.get('observed_effects'), list):
            outcome['observed_effects'] = update['observed_effects']
            outcome['effects_through_s'] = update.get('game_time_s')
        # Final: a newer decision exists, the match ended, or the writer closed it.
        record['final'] = seq < last_seq or match_end is not None or seq in closed
        merged.append(record)
    return dict(run=run, decisions=merged, match_end=match_end, invalid_lines=invalid)


def read_decisions(run_dir):
    """Decision records (kind='decision') in seq order, with observed effects merged."""
    return read_run_log(run_dir)['decisions']


def decisions_page(run_dir, *, since_seq=0, max_records=100, max_bytes=48000):
    """One bounded page for live tailing: decisions with seq > since_seq.

    A decision can still gain observed effects until a newer decision or the
    match end exists (final=false). Clients re-request from open_seq - 1 to
    refresh it; next_since_seq continues after the returned page.
    """
    log = read_run_log(run_dir)
    page, used = [], 0
    candidates = [record for record in log['decisions'] if record['seq'] > since_seq]
    for record in candidates:
        size = len(json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if page and (len(page) >= max_records or used + size > max_bytes):
            break
        page.append(record)
        used += size
    open_seq = next((record['seq'] for record in log['decisions'] if not record['final']), None)
    return dict(
        schema_version=SCHEMA_VERSION, run=log['run'], decisions=page,
        last_seq=log['decisions'][-1]['seq'] if log['decisions'] else 0,
        next_since_seq=page[-1]['seq'] if page else since_seq,
        has_more=len(page) < len(candidates), open_seq=open_seq,
        match_end=log['match_end'], complete=log['match_end'] is not None,
        invalid_lines=log['invalid_lines'])
