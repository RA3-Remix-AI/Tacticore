"""Bounded, non-executing memory for explicitly model-declared macro strategy.

Callers supply already validated public contexts and native outcome assertions.
This module cannot discover facts, authorize a consumer, dispatch, or choose an
action. Long-term strategy survives the short-lived executable plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import uuid

from macro_policy import ACTIONS, restore_public_defaults

OBJECTIVES = ('economic_stability', 'expand_economy', 'develop_technology',
              'build_force', 'scout', 'pressure', 'defend_base', 'recover_force', 'hold')
PHASES = ('prepare', 'execute', 'assess', 'wait')
EXPECTED_OBSERVATIONS = ('resource_recovery', 'construction_queue', 'building_operational',
                         'production_queue', 'unit_completed', 'technology_unlocked',
                         'new_lawful_contact', 'force_region_change', 'threat_reduced', 'no_change')
CONDITIONS = ('capability_available', 'resources_sufficient', 'prerequisite_met',
              'no_new_threat', 'target_valid', 'effect_pending', 'effect_observed',
              'facts_changed', 'goal_unobserved')
RESOURCE_KEYS = ('economy', 'army', 'tech', 'reserve')
DECLARATION_FIELDS = ('strategy_id', 'objective', 'phase', 'public_fact_refs',
                      'expected_observation', 'continue_conditions', 'replan_conditions',
                      'resource_priorities')
STRATEGY_DECLARATION_SCHEMA = dict(
    fields=list(DECLARATION_FIELDS), strategy_id='null_for_new_objective_or_current_uuid',
    objective=list(OBJECTIVES), phase=list(PHASES), public_fact_refs='1_to_4_keys_from_macro_strategy.fact_catalog',
    expected_observation=list(EXPECTED_OBSERVATIONS), condition_values=list(CONDITIONS),
    continue_conditions='1_to_3_unique_condition_values', replan_conditions='1_to_3_unique_condition_values',
    resource_priorities=dict(keys=list(RESOURCE_KEYS), values='finite_0_to_1_sum_1'),
    advisory_only=True, executable_actions='only_the_separately_validated_macro_actions')

_ROLES = ('anti_air', 'anti_armor', 'infantry', 'naval', 'air', 'armor', 'economy', 'structure')
_BUILDINGS = ('construction_yard', 'power_plant', 'barracks', 'war_factory', 'refinery', 'super_reactor', 'battle_lab')
_UNITS = ('conscript', 'flak_trooper', 'hammer_tank', 'war_bear', 'sickle', 'bullfrog')
_TERMINAL = frozenset({'no_effect', 'failed', 'cancelled', 'expired', 'replaced'})
_OUTCOMES = _TERMINAL | {'pending', 'effect_observed', 'unknown'}
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')


class StrategyError(ValueError):
    """Public reason code, without raw model text or native data."""


def validate_strategy_declaration(raw):
    """Validate model shape independently of a live memory or capability grant."""
    if type(raw) is not dict or set(raw) != set(DECLARATION_FIELDS):
        raise StrategyError('strategy_declaration_fields')
    if raw['strategy_id'] is not None:
        _uuid(raw['strategy_id'], 'strategy_declaration_id')
    _enum(raw['objective'], OBJECTIVES, 'strategy_objective')
    _enum(raw['phase'], PHASES, 'strategy_phase')
    _enum(raw['expected_observation'], EXPECTED_OBSERVATIONS, 'strategy_expected_observation')
    refs = raw['public_fact_refs']
    if (type(refs) is not list or not 1 <= len(refs) <= 4
            or any(type(ref) is not str or re.fullmatch(r'[a-z][a-z0-9_.]{0,95}', ref) is None for ref in refs)
            or len(set(refs)) != len(refs)):
        raise StrategyError('strategy_public_fact_refs')
    for name in ('continue_conditions', 'replan_conditions'):
        values = raw[name]
        if (type(values) is not list or not 1 <= len(values) <= 3
                or any(type(v) is not str or v not in CONDITIONS for v in values)
                or len(set(values)) != len(values)):
            raise StrategyError('strategy_conditions')
    priorities = raw['resource_priorities']
    if type(priorities) is not dict or set(priorities) != set(RESOURCE_KEYS):
        raise StrategyError('strategy_priorities')
    if abs(sum(_number(v, 0, 1, 'strategy_priorities') for v in priorities.values())-1) > 1e-6:
        raise StrategyError('strategy_priorities')
    return json.loads(_json(raw))


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def _hash(value):
    return hashlib.sha256(_json(value).encode('utf8')).hexdigest()


def _work_retry_keys(actions, target, quantity):
    """Identity of each native-owned work, independent of unrelated domains.

    Only deployment consumes a qualified region in the existing contract.
    Expansion selects its location natively; own manager gates, scouting and
    action-defined build/production policies do not consume objective_region.
    """
    keys=[]
    for action in actions:
        domain=ACTIONS[action]
        if domain=='budget':continue
        if domain=='deployment':policy='qualified_native_region';region=target
        elif domain=='expansion':policy='native_ai_selects_expansion_location_and_plan';region=None
        elif domain in ('construction_gate','production_gate'):policy='own_native_scheduling_manager';region=None
        else:policy='action_defined_native_policy';region=None
        count=quantity if quantity is not None and quantity['action']==action else None
        keys.append(_hash(dict(action=action,target_policy=policy,target_region=region,quantity=count)))
    return tuple(keys)


def _work_retry_basis(facts):
    # Native preference/status, budget choice and observation age are not new
    # resources, prerequisites or force conditions for retrying failed work.
    return {key:value for key,value in facts.items() if key.startswith(('own.','production.'))
            or key.startswith('enemy.') and key.endswith('.count')}


def _work_retry_basis_changed(previous, current):
    # Loss/expiry of information and known -> unknown are not positive evidence
    # of changed retry conditions. A current trusted known new/different value
    # can support reassessment, including an explicitly observed zero.
    if type(previous) is not dict or type(current) is not dict:return False
    return any(value is not None and (key not in previous or previous[key]!=value)
               for key,value in current.items())


def _number(value, low, high, code):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise StrategyError(code)
    return value


def _identifier(value, code):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise StrategyError(code)
    return value


def _uuid(value, code):
    try:
        if type(value) is not str or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise StrategyError(code) from None
    return value


def _enum(value, values, code):
    if type(value) is not str or value not in values:
        raise StrategyError(code)
    return value


@dataclass(frozen=True)
class StrategyReview:
    allowed: bool
    reason_code: str
    strategy_id: str | None
    plan_id: str
    intent_fingerprint: str
    _token: str = field(repr=False, default='')


class MacroStrategyMemory:
    """One session/profile's bounded strategic memory, independent of plan TTL.

    Outcome assertions are trusted-host inputs, not evidence inferred from ACK.
    A terminal native outcome requires independent release verification. Unknown
    delivery remains unresolved until such verification, including after expiry.
    """

    def __init__(self, *, session_id, commander_id, player_id, profile_revision, effective_hash,
                 min_hold_seconds=20, no_effect_cooldown_seconds=45, maximum_context_bytes=1536):
        self.session_id = _uuid(session_id, 'strategy_session')
        self.commander_id = _uuid(commander_id, 'strategy_commander')
        if type(player_id) is not int or not 1 <= player_id <= 16:
            raise StrategyError('strategy_player')
        if type(profile_revision) is not int or not 1 <= profile_revision <= 2**31-1:
            raise StrategyError('strategy_profile_revision')
        if type(effective_hash) is not str or re.fullmatch('[0-9a-f]{64}', effective_hash) is None:
            raise StrategyError('strategy_effective_hash')
        self.player_id = player_id
        self.profile_revision = profile_revision
        self.effective_hash = effective_hash
        self.min_hold_seconds = _number(min_hold_seconds, 0, 300, 'strategy_hold_bound')
        self.cooldown_seconds = _number(no_effect_cooldown_seconds, 0, 600, 'strategy_cooldown_bound')
        if type(maximum_context_bytes) is not int or not 1024 <= maximum_context_bytes <= 3072:
            raise StrategyError('strategy_context_bound')
        self.maximum_context_bytes = maximum_context_bytes
        self._current = None
        self._basis = {}
        self._held_since = 0
        self._version = 0
        self._reviews = {}
        self._commands = {}
        self._history = []
        self._stopped = False
        self._last_mutation_time = 0
        self._last_review_reason = None

    def _facts(self, context):
        if type(context) is dict and 'macro_default_contract' in context:
            try:context=restore_public_defaults(context)
            except ValueError:raise StrategyError('strategy_public_contract_invalid') from None
        if (type(context) is not dict or context.get('session_id') != self.session_id
                or context.get('commander_id') != self.commander_id
                or type(context.get('player_id')) is not int or context['player_id'] != self.player_id
                or context.get('control_mode') != 'macro_native'):
            raise StrategyError('strategy_context_binding')
        at = _number(context.get('game_time_seconds'), 0, 86400, 'strategy_context_time')
        if type(context.get('paused')) is not bool:
            raise StrategyError('strategy_context_paused')
        for key, expected in (('profile_revision', self.profile_revision), ('effective_hash', self.effective_hash)):
            if key in context and context[key] != expected:
                raise StrategyError('strategy_context_profile')
        actions = context.get('allowed_macro_actions')
        if (type(actions) is not list or len(actions) > 64
                or any(type(a) is not str or a not in ACTIONS for a in actions)
                or len(set(actions)) != len(actions)):
            raise StrategyError('strategy_context_capabilities')
        facts = {'capabilities.actions': sorted(actions)}
        working = context.get('working_memory', {})
        if type(working) is not dict:
            raise StrategyError('strategy_context_memory')
        economy = working.get('economy', context.get('resources', {}))
        if type(economy) is not dict:
            raise StrategyError('strategy_context_economy')
        for name in ('credits', 'power_balance', 'queued_count', 'idle_producers'):
            if name in economy:
                facts['own.'+name] = (None if name == 'power_balance' and economy[name] is None else
                    _number(economy[name], -100000 if name == 'power_balance' else 0, 10**12, 'strategy_context_economy'))
        roles = economy.get('own_roles', {})
        if type(roles) is not dict:
            raise StrategyError('strategy_context_roles')
        for role in _ROLES:
            if role in roles:
                facts['own.role.'+role] = _number(roles[role], 0, 8192, 'strategy_context_count')
        forces = context.get('own_forces')
        if forces is not None:
            self._own_source(forces, at, ('observed_frame',))
            named = forces.get('named_unit_counts', {})
            if type(named) is not dict:
                raise StrategyError('strategy_context_forces')
            for name in _UNITS:
                if name in named:
                    facts['own.unit.'+name] = _number(named[name], 0, 8192, 'strategy_context_count')
        infrastructure = context.get('own_infrastructure')
        if infrastructure is not None:
            self._own_source(infrastructure, at, ('builder_frame', 'own_census_frame'))
            counts = infrastructure.get('own_template_presence_counts', {})
            if type(counts) is not dict:
                raise StrategyError('strategy_context_infrastructure')
            for name in _BUILDINGS:
                if name in counts:
                    facts['own.present.'+name] = _number(counts[name], 0, 8192, 'strategy_context_count')
        production = context.get('macro_production_feedback')
        if production is not None:
            if type(production) is not dict or production.get('source') != 'native_production_observation':
                raise StrategyError('strategy_context_production')
            self._frames(production, at, ('builder_frame', 'own_census_frame'))
            action = _identifier(production.get('action'), 'strategy_context_production')
            for name in ('observed_new_queue_count', 'new_own_unit_observations', 'available_producer_count'):
                if name in production:
                    facts['production.'+action+'.'+name] = _number(production[name], 0, 100000, 'strategy_context_count')
        unified=context.get('macro_unified_feedback')
        if unified is not None:
            if type(unified) is not dict or unified.get('source')!='bound_native_strategy_v5':
                raise StrategyError('strategy_context_unified_source')
            self._frames(unified,at,('observed_frame',))
            rows=unified.get('observations')
            if type(rows) is not list or len(rows)>4:raise StrategyError('strategy_context_unified_bounds')
            for row in rows:
                action=row.get('action') if type(row) is dict else None
                if action not in actions:raise StrategyError('strategy_context_unified_action')
                status=row.get('status')
                if status not in ('native_task_active','native_manager_state_observed','native_waiting_or_no_effect','preference_released'):
                    raise StrategyError('strategy_context_unified_status')
                facts['native.'+action]=status
        # Use only the existing visibility-validated, own-view public memory.
        # No arbitrary enemy arrays, coordinates, native IDs or string notes.
        battlefield = working.get('battlefield', {})
        enemies = working.get('verified_enemy_facts', [])
        if type(battlefield) is dict and battlefield.get('visibility_verified') is True:
            if type(enemies) is not list or len(enemies) > 32:
                raise StrategyError('strategy_context_enemy')
            for row in enemies:
                if type(row) is not dict:
                    raise StrategyError('strategy_context_enemy')
                role = _enum(row.get('role'), _ROLES, 'strategy_context_enemy')
                count = _number(row.get('count'), 0, 100000, 'strategy_context_enemy')
                seen = _number(row.get('observed_at_game_seconds'), 0, at, 'strategy_context_enemy')
                visible = row.get('currently_visible')
                if type(visible) is not bool:
                    raise StrategyError('strategy_context_enemy')
                if at-seen > 120:
                    continue
                prefix = 'enemy.'+('visible.' if visible else 'last_seen.')+role
                facts[prefix+'.count'] = count
                if not visible:
                    facts[prefix+'.age_seconds'] = round(at-seen, 1)
        return at, facts

    @staticmethod
    def _own_source(value, at, frames):
        if (type(value) is not dict or value.get('own_perspective') is not True
                or value.get('enemy_details_read') is not False):
            raise StrategyError('strategy_context_own_source')
        MacroStrategyMemory._frames(value, at, frames)

    @staticmethod
    def _frames(value, at, frames):
        for key in frames:
            frame = value.get(key)
            if type(frame) is not int or not 0 < frame <= 0xffffffff or not -15 <= at*15-frame <= 30:
                raise StrategyError('strategy_context_own_stale')

    def context(self, public_context):
        at, facts = self._facts(public_context)
        if at < self._last_mutation_time:
            raise StrategyError('strategy_context_before_memory')
        pinned = list(self._current['public_fact_refs']) if self._current else []
        priority = pinned + ['own.credits', 'own.power_balance', 'capabilities.actions'] + [key for key in facts if key.startswith('native.')] + [
                             'own.queued_count', 'own.idle_producers'] + list(facts)
        catalog = {key: facts[key] for key in dict.fromkeys(priority) if key in facts}
        result = dict(schema_version=1, fact_catalog=catalog,
                      current_strategy=json.loads(_json(self._current)),
                      recent_outcomes=[dict(v) for v in self._history[-2:]],
                      last_guard_reason=self._last_review_reason,
                      guard='stopped' if self._stopped else 'active',
                      missing_basis_refs=[key for key in pinned if key not in facts])
        # Hard-retain long-term state and its currently available basis; only
        # omit unreferenced directory entries and old outcome summaries.
        while len(_json(result).encode('utf8')) > self.maximum_context_bytes:
            removable = [key for key in catalog if key not in pinned]
            if removable:
                del catalog[removable[-1]]
            elif result['recent_outcomes']:
                result['recent_outcomes'].pop(0)
            else:
                raise StrategyError('strategy_context_budget')
        return result

    def _declaration(self, raw, offered, latest):
        raw = validate_strategy_declaration(raw)
        ident = raw['strategy_id']
        if ident is not None:
            _uuid(ident, 'strategy_declaration_id')
            if self._current is None or ident != self._current['strategy_id']:
                raise StrategyError('strategy_declaration_id')
        objective = raw['objective']
        refs = raw['public_fact_refs']
        if (type(refs) is not list or not 1 <= len(refs) <= 4
                or any(type(ref) is not str or ref not in offered or ref not in latest for ref in refs)
                or len(set(refs)) != len(refs)):
            raise StrategyError('strategy_public_fact_refs')
        if ident is not None and self._current['objective'] != objective:
            raise StrategyError('strategy_objective_requires_new_id')
        return dict(raw, strategy_id=ident or str(uuid.uuid4()))

    def review(self, plan, declaration, request_context, latest_context=None, *, urgent=False):
        requested_at, request_facts = self._facts(request_context)
        at, latest = self._facts(latest_context if latest_context is not None else request_context)
        if at < self._last_mutation_time:
            raise StrategyError('strategy_context_before_memory')
        raw = plan.public() if hasattr(plan, 'public') else plan
        if type(raw) is not dict:
            raise StrategyError('strategy_plan')
        plan_id = _identifier(raw.get('plan_id'), 'strategy_plan_id')
        if (raw.get('origin') != 'model' or raw.get('session_id') != self.session_id
                or raw.get('commander_id') != self.commander_id
                or type(raw.get('player_id')) is not int or raw['player_id'] != self.player_id
                or raw.get('tactical_tasks') or raw.get('runtime_task') is not None):
            raise StrategyError('strategy_plan_binding')
        based = _number(raw.get('based_on_game_time_seconds'), 0, at, 'strategy_plan_time')
        expires = _number(raw.get('expires_at_game_seconds'), based, 86400, 'strategy_plan_time')
        if abs(based-requested_at) > 1e-6 or at < requested_at or not at < expires <= based+60:
            raise StrategyError('strategy_plan_time')
        if type(urgent) is not bool:
            raise StrategyError('strategy_urgent_assertion')
        actions = raw.get('macro_actions')
        if (type(actions) not in (list, tuple) or len(actions) > 5
                or any(type(a) is not str or a not in request_facts['capabilities.actions']
                       or a not in latest['capabilities.actions'] for a in actions)
                or len(set(actions)) != len(actions)):
            raise StrategyError('strategy_plan_capabilities')
        quantity = raw.get('macro_production')
        if hasattr(quantity, 'public'):
            quantity = quantity.public()
        if quantity is not None and (type(quantity) is not dict or set(quantity) != {'action', 'additional_count'}
                or quantity['action'] not in actions or type(quantity['additional_count']) is not int
                or not 1 <= quantity['additional_count'] <= 3):
            raise StrategyError('strategy_plan_quantity')
        target = raw.get('objective_region')
        if target is not None and (type(target) is not str or _ID.fullmatch(target) is None):
            raise StrategyError('strategy_plan_region')
        offered = request_context.get('macro_strategy', {}).get('fact_catalog') if type(request_context.get('macro_strategy')) is dict else None
        if offered is None:
            offered = self.context(request_context)['fact_catalog']
        if type(offered) is not dict or any(k not in request_facts or request_facts[k] != v for k, v in offered.items()):
            raise StrategyError('strategy_fact_catalog_changed')
        candidate = self._declaration(declaration, offered, latest)
        fingerprint = _hash(dict(actions=sorted(actions), target=target, quantity=quantity))
        work_keys=_work_retry_keys(actions,target,quantity)
        work_basis=_work_retry_basis(latest)
        reason = None
        if self._stopped:
            reason = 'strategy_stopped'
        elif request_context['paused'] or (latest_context or request_context)['paused']:
            reason = 'strategy_game_paused'
        elif any(row['plan_id'] == plan_id for row in self._commands.values()):
            reason = 'strategy_plan_already_dispatched'
        elif any(row['outcome'] == 'unknown' for row in self._commands.values()):
            reason = 'strategy_unknown_outcome'
        for row in self._commands.values():
            if reason or row['fingerprint'] != fingerprint:
                continue
            if row['outcome'] == 'unknown':
                reason = 'strategy_unknown_outcome'
            elif row['outcome'] in ('pending', 'effect_observed') and row['released_at'] is None:
                reason = 'strategy_intent_in_flight'
            elif row['outcome'] in ('no_effect', 'failed', 'expired') and not row['had_effect']:
                changed = any(latest.get(ref) != value for ref, value in row['basis'].items())
                if not changed and at < row['outcome_at']+self.cooldown_seconds:
                    reason = 'strategy_no_effect_cooldown'
            elif quantity is not None and row['had_effect']:
                production_keys = {key for key in set(row['facts']) | set(latest)
                                   if key.startswith(('production.', 'own.unit.')) or key == 'own.queued_count'}
                changed = any(row['facts'].get(key) != latest.get(key) for key in production_keys)
                if not changed and at < row['outcome_at']+self.min_hold_seconds:
                    reason = 'strategy_production_renewal_wait'
        if reason is None and work_keys:
            for previous in self._commands.values():
                if (previous['outcome'] in ('no_effect','failed','expired')
                        and previous['released_at'] is not None and not previous['had_effect']
                        and set(work_keys).intersection(previous.get('work_retry_keys', ()))
                        and not _work_retry_basis_changed(previous.get('work_retry_basis'),work_basis)
                        and at < previous['outcome_at']+self.cooldown_seconds):
                    reason='strategy_no_effect_cooldown'
                    break
        if self._current and candidate['strategy_id'] != self._current['strategy_id'] and reason is None:
            changed = any(latest.get(ref) != value for ref, value in self._basis.items())
            if not changed and not urgent and at < self._held_since+self.min_hold_seconds:
                reason = 'strategy_minimum_hold'
        review = StrategyReview(reason is None, reason or 'strategy_allowed', candidate['strategy_id'],
                                plan_id, fingerprint, str(uuid.uuid4()))
        self._last_review_reason = review.reason_code
        # Only the immediately returned transaction can be committed. Bounded
        # storage also prevents unbounded model-generated rejected candidates.
        self._reviews = {review._token: dict(review=review, version=self._version, candidate=candidate,
            facts=latest, basis={ref: latest[ref] for ref in candidate['public_fact_refs']}, at=at,
            expires=expires, actions=list(actions), quantity=quantity,
            work_retry_keys=work_keys,work_retry_basis=work_basis)}
        return review

    def record_dispatch(self, review, *, command_id, game_seconds, outcome='pending'):
        if self._stopped:
            raise StrategyError('strategy_stopped')
        row = self._reviews.get(getattr(review, '_token', None))
        if row is None or row['review'] != review or not review.allowed or row['version'] != self._version:
            raise StrategyError('strategy_review_not_current')
        at = _number(game_seconds, row['at'], row['expires'], 'strategy_dispatch_time')
        if at >= row['expires'] or outcome not in ('pending', 'unknown'):
            raise StrategyError('strategy_dispatch_time_or_outcome')
        if row['actions'] or outcome == 'unknown':
            _identifier(command_id, 'strategy_command_id')
            if command_id in self._commands:
                raise StrategyError('strategy_command_reused')
            if len(self._commands) >= 64:
                # Keep unresolved entries; never evict uncertainty to make room.
                evictable = next((key for key, value in self._commands.items()
                                  if value['released_at'] is not None and value['outcome'] != 'unknown'
                                  and at >= value['outcome_at']+max(self.cooldown_seconds, self.min_hold_seconds)), None)
                if evictable is None:
                    raise StrategyError('strategy_command_capacity')
                del self._commands[evictable]
            for previous in self._commands.values():
                # A later attempt is a conservative effect boundary even when
                # its delivery is unknown. It is NOT a release assertion.
                if previous['released_at'] is None:
                    previous['effect_end'] = min(previous['effect_end'], at)
            self._commands[command_id] = dict(plan_id=review.plan_id, strategy_id=review.strategy_id,
                fingerprint=review.intent_fingerprint, start=at, expires=row['expires'], outcome=outcome,
                effect_end=row['expires'], outcome_at=at, released_at=None, had_effect=False,
                basis=dict(row['basis']), facts=dict(row['facts']),
                work_retry_keys=tuple(row['work_retry_keys']),work_retry_basis=dict(row['work_retry_basis']))
        elif command_id is not None:
            raise StrategyError('strategy_wait_has_no_command')
        changed = self._current is None or self._current['strategy_id'] != review.strategy_id
        previous_outcome = self._current.get('last_outcome') if self._current and not changed else None
        self._current = json.loads(_json(row['candidate']))
        self._current.update(updated_game_seconds=at, last_outcome=previous_outcome)
        if outcome == 'unknown':
            summary = dict(plan_id=review.plan_id, outcome='unknown', reason_code='delivery_unknown',
                           at_game_seconds=at, effect_verified=False)
            self._history = (self._history+[summary])[-4:]
            self._current['last_outcome'] = dict(summary)
            self._last_review_reason = 'strategy_unknown_outcome'
        if changed:
            self._held_since = at
        self._basis = dict(row['basis'])
        self._last_mutation_time = at
        self._version += 1
        self._reviews.clear()

    def record_outcome(self, *, command_id, plan_id, outcome, game_seconds,
                       observed_game_seconds=None, effect_verified=False, release_verified=False,
                       reason_code='observed'):
        if outcome not in _OUTCOMES or type(effect_verified) is not bool or type(release_verified) is not bool:
            raise StrategyError('strategy_outcome_enum')
        _identifier(reason_code, 'strategy_outcome_reason')
        existing = self._commands.get(command_id)
        if existing is None or existing['plan_id'] != plan_id:
            raise StrategyError('strategy_outcome_binding')
        row = dict(existing)
        at = _number(game_seconds, row['outcome_at'], 86400, 'strategy_outcome_time')
        if row['released_at'] is not None:
            raise StrategyError('strategy_outcome_after_release')
        if outcome == 'effect_observed':
            end = row['effect_end']
            seen = _number(observed_game_seconds, row['start'], at, 'strategy_effect_window')
            if not effect_verified or not seen < end:
                raise StrategyError('strategy_effect_window')
            if row['outcome'] == 'unknown':
                raise StrategyError('strategy_unknown_requires_resolution')
            row['had_effect'] = True
        elif effect_verified or observed_game_seconds is not None:
            raise StrategyError('strategy_effect_assertion')
        if outcome == 'pending' and row['outcome'] != 'pending':
            raise StrategyError('strategy_outcome_regression')
        if outcome in _TERMINAL:
            if not release_verified:
                raise StrategyError('strategy_release_required')
            if outcome == 'no_effect' and row['had_effect']:
                raise StrategyError('strategy_effect_cannot_be_erased')
            if outcome == 'expired' and at < row['expires']:
                raise StrategyError('strategy_expiry_before_deadline')
            row['released_at'] = at
        elif release_verified:
            raise StrategyError('strategy_release_outcome')
        if row['outcome'] == 'unknown' and outcome not in _TERMINAL and outcome != 'unknown':
            raise StrategyError('strategy_unknown_requires_resolution')
        row['outcome'] = outcome
        row['outcome_at'] = at
        self._commands[command_id] = row
        self._last_mutation_time = max(self._last_mutation_time, at)
        summary = dict(plan_id=plan_id, outcome=outcome, reason_code=reason_code,
                       at_game_seconds=at, effect_verified=row['had_effect'])
        self._history = (self._history+[summary])[-4:]
        if self._current and row['strategy_id'] == self._current['strategy_id']:
            self._current['last_outcome'] = dict(summary)
        self._version += 1
        self._reviews.clear()

    def stop(self):
        self._stopped = True
        self._version += 1
        self._reviews.clear()

    def public_state(self):
        """Read-only UI/persistence projection, independent of game sampling.

        This is deliberately separate from model context and its wire budget.
        Counts expose unresolved lifecycle state, not private command payloads.
        """
        return json.loads(_json(dict(
            schema_version=1, kind='macro_strategy_public_state',
            current_strategy=self._current, recent_outcomes=self._history[-4:],
            last_guard_reason=self._last_review_reason, stopped=self._stopped,
            unknown_command_count=sum(row['outcome']=='unknown' for row in self._commands.values()),
            unreleased_command_count=sum(row['released_at'] is None for row in self._commands.values()))))
