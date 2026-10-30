"""Strict, bounded UI projection of the strategy memory's public state.

No command payloads, arbitrary notes, model text, addresses, or extra fields
cross this boundary. A malformed strategy record does not invalidate the rest
of a separately verified Host status.
"""
import math
import re
import uuid

from .contracts import ContractError

_ROLES=frozenset(('anti_air','anti_armor','infantry','naval','air','armor','economy','structure'))
_UNITS=frozenset(('conscript','flak_trooper','hammer_tank','war_bear','sickle','bullfrog'))
_BUILDINGS=frozenset(('construction_yard','power_plant','barracks','war_factory','refinery','super_reactor','battle_lab'))
_OWN=frozenset(('own.credits','own.power_balance','own.queued_count','own.idle_producers','capabilities.actions'))
_PRODUCTION_FIELDS=frozenset(('observed_new_queue_count','new_own_unit_observations','available_producer_count'))
_OUTCOMES=frozenset(('pending','effect_observed','no_effect','failed','cancelled','expired','replaced','unknown'))
_CODE=re.compile(r'[a-z][a-z0-9_]{0,63}\Z')


def _fail():
    raise ContractError('macro_strategy_public_state_invalid')


def _uuid(value):
    if type(value) is not str:_fail()
    try:
        if str(uuid.UUID(value))!=value:_fail()
    except (ValueError,AttributeError):_fail()
    return value


def _time(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=86400:_fail()
    return value


def _code(value):
    if type(value) is not str or _CODE.fullmatch(value) is None:_fail()
    return value


def _count(value):
    if type(value) is not int or not 0<=value<=64:_fail()
    return value


def _public_ref(value):
    from macro_policy import ACTIONS
    if type(value) is not str or len(value)>96:_fail()
    if value in _OWN:return value
    parts=value.split('.')
    if len(parts)==2 and parts[0]=='native':
        from .strategic_contract_v5 import STRATEGIC_ACTIONS
        if parts[1] in STRATEGIC_ACTIONS:return value
    if len(parts)==3 and parts[0]=='own':
        names={'role':_ROLES,'unit':_UNITS,'present':_BUILDINGS}
        if parts[1] in names and parts[2] in names[parts[1]]:return value
    if (len(parts)==3 and parts[0]=='production' and ACTIONS.get(parts[1])=='production'
            and parts[2] in _PRODUCTION_FIELDS):return value
    if (len(parts)==4 and parts[0]=='enemy' and parts[1] in ('visible','last_seen') and parts[2] in _ROLES
            and (parts[3]=='count' or parts[1]=='last_seen' and parts[3]=='age_seconds')):return value
    _fail()


def _outcome(value):
    if type(value) is not dict:_fail()
    outcome=value.get('outcome');effect=value.get('effect_verified')
    if type(outcome) is not str or outcome not in _OUTCOMES or type(effect) is not bool:_fail()
    if outcome=='effect_observed' and not effect or outcome in ('pending','no_effect') and effect:_fail()
    return dict(plan_id=_uuid(value.get('plan_id')),outcome=outcome,
        reason_code=_code(value.get('reason_code')),at_game_seconds=_time(value.get('at_game_seconds')),
        effect_verified=effect)


def _strategy(value):
    from macro_strategy import DECLARATION_FIELDS,validate_strategy_declaration,StrategyError
    if type(value) is not dict or not {'updated_game_seconds','last_outcome'}<=set(value):_fail()
    try:declaration=validate_strategy_declaration({key:value[key] for key in DECLARATION_FIELDS})
    except (KeyError,StrategyError):_fail()
    declaration['strategy_id']=_uuid(declaration['strategy_id'])
    declaration['public_fact_refs']=[_public_ref(ref) for ref in declaration['public_fact_refs']]
    declaration['updated_game_seconds']=_time(value.get('updated_game_seconds'))
    last=value.get('last_outcome')
    declaration['last_outcome']=None if last is None else _outcome(last)
    return declaration


def project_macro_strategy_state(value):
    """Return fresh whitelisted objects or one fixed rejection code."""
    required={'schema_version','kind','current_strategy','recent_outcomes','last_guard_reason',
        'stopped','unknown_command_count','unreleased_command_count'}
    if (type(value) is not dict or not required<=set(value) or type(value.get('schema_version')) is not int or value['schema_version']!=1
            or value.get('kind')!='macro_strategy_public_state' or type(value.get('stopped')) is not bool):_fail()
    current=value.get('current_strategy');recent=value.get('recent_outcomes');reason=value.get('last_guard_reason')
    if type(recent) is not list or len(recent)>4:_fail()
    unknown=_count(value.get('unknown_command_count'));unreleased=_count(value.get('unreleased_command_count'))
    if unknown>unreleased:_fail()
    return dict(schema_version=1,kind='macro_strategy_public_state',
        current_strategy=None if current is None else _strategy(current),
        recent_outcomes=[_outcome(row) for row in recent],last_guard_reason=None if reason is None else _code(reason),
        stopped=value['stopped'],unknown_command_count=unknown,unreleased_command_count=unreleased)
