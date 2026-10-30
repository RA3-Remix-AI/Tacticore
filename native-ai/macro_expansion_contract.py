"""Pure, versioned C-line candidate definitions; this grants no live capability.

The original thirteen bit positions are immutable, including their historical
transport aliases. New actions append gates; no old role becomes a build gate.
"""
from copy import deepcopy
import hashlib
import json

COMMANDER = '57e668b4-4d89-43bd-bc92-0dd436f046ef'
PREFIX = '/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_'
LEGACY_FLAG_SUFFIXES = ('build_airfield', 'scout', 'buildreactor', 'buildtech',
    'economyrefinery', 'produceconscript', 'produceflak', 'producetank',
    'budgeteconomy', 'budgetarmy', 'budgettech', 'deployattack', 'deploydefense')
LEGACY_ACTION_ORDER = ('regroup', 'scout', 'buildreactor', 'withdraw', 'reinforce',
    'produceconscript', 'produceflak', 'producetank', 'budgeteconomy', 'budgetarmy',
    'budgettech', 'deployattack', 'deploydefense')
LEGACY_DOMAINS = ('deployment_policy', 'strategic', 'construction', 'deployment_policy',
    'deployment_policy', 'production', 'production', 'production', 'budget', 'budget',
    'budget', 'strategic', 'strategic')
LEGACY_FLAG_ORDER = tuple(PREFIX + name for name in LEGACY_FLAG_SUFFIXES)
EXPANSION_ACTION_ORDER = ('buildpower', 'buildbarracks', 'buildfactory',
    'buildrefinery', 'buildbattlelab', 'producesickle', 'producebullfrog')

_CANDIDATES = (
    dict(action='buildpower', suffix='BuildPower', template='SovietPowerPlant',
        domain='construction', producer='SovietConstructionYard',
        heuristic='POWER', required_own_templates=(), only_if_target_absent=False,
        target_policy='original_native_power_need_and_legal_placement'),
    dict(action='buildbarracks', suffix='BuildBarracks', template='SovietBarracks',
        domain='construction', producer='SovietConstructionYard',
        heuristic='CONSTANT', required_own_templates=(), only_if_target_absent=True,
        target_policy='original_native_legal_placement'),
    dict(action='buildfactory', suffix='BuildFactory', template='SovietWarFactory',
        domain='construction', producer='SovietConstructionYard',
        heuristic='CONSTANT', required_own_templates=('SovietRefinery',),
        only_if_target_absent=True, target_policy='original_native_legal_placement'),
    dict(action='buildrefinery', suffix='BuildRefinery', template='SovietRefinery',
        domain='construction', producer='SovietConstructionYard',
        heuristic='REFINERY', required_own_templates=('SovietPowerPlant',),
        only_if_target_absent=False, target_policy='original_native_open_resource_node'),
    dict(action='buildbattlelab', suffix='BuildBattleLab', template='SovietTechStructure',
        domain='construction', producer='SovietConstructionYard',
        heuristic='CONSTANT', required_own_templates=('SovietPowerPlantAdvanced',),
        only_if_target_absent=True, target_policy='original_native_legal_placement'),
    dict(action='producesickle', suffix='ProduceSickle', template='SovietAntiInfantryVehicle',
        domain='production', producer='SovietWarFactory', heuristic='CONSTANT',
        required_own_templates=('SovietWarFactory',), only_if_target_absent=False,
        target_policy='original_native_vehicle_production'),
    dict(action='producebullfrog', suffix='ProduceBullfrog', template='SovietAntiAirShip_Ground',
        domain='production', producer='SovietWarFactory', heuristic='CONSTANT',
        required_own_templates=('SovietWarFactory',), only_if_target_absent=False,
        target_policy='original_native_vehicle_production'),
)


def candidate_definitions():
    """Return independent, JSON-compatible definitions with explicit unknowns."""
    return [dict(deepcopy(row), required_own_templates=list(row['required_own_templates']),
        control_basis='new_native_queue_acceptances', bounded_expiry_required=True,
        native_dependency_payment_and_placement_required=True,
        existence_is_not_operational=True, field_verified=False, capability_granted=False,
        additional_count_candidates=[1], completed_objects_guaranteed=False,
        payment_verified=False, technology_unlock_verified=False,
        native_ai_selects_and_operates_units=True, unit_orders_exposed=False)
        for row in _CANDIDATES]


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode('utf8')).hexdigest()


def transport_contract(report):
    """Validate fixed identities and bit meaning before generating any transport.

    This is a static profile check, not a field-evidence or binary verifier.
    Consumers remain candidates until an independent same-build field grant.
    """
    if (report.get('variant') != 'expanded_macro_policy_v2'
            or type(report.get('transport_protocol_version')) is not int
            or report['transport_protocol_version'] != 2
            or type(report.get('expansion_schema_version')) is not int
            or report['expansion_schema_version'] != 1):
        raise ValueError('macro_expansion_version_required')
    if report.get('commander_id') != COMMANDER or type(report.get('player_slot')) is not int or report['player_slot'] != 3:
        raise ValueError('macro_expansion_fixed_profile_required')
    flags = report.get('flags')
    expected_flags = list(LEGACY_FLAG_ORDER) + [PREFIX + a for a in EXPANSION_ACTION_ORDER]
    if (type(flags) is not dict or list(flags.values()) != expected_flags
            or len(set(flags)) != 20 or len(set(flags.values())) != 20
            or list(flags) != list(LEGACY_FLAG_SUFFIXES) + list(EXPANSION_ACTION_ORDER)
            or type(report.get('flag_count')) is not int or report['flag_count'] != 20):
        raise ValueError('macro_expansion_flag_order_changed')
    if (report.get('legacy_flag_order') != list(LEGACY_FLAG_ORDER)
            or report.get('legacy_action_order') != list(LEGACY_ACTION_ORDER)
            or report.get('expansion_action_order') != list(EXPANSION_ACTION_ORDER)):
        raise ValueError('macro_expansion_legacy_contract_changed')
    consumers = report.get('consumers')
    if type(consumers) is not list or len(consumers) != 20 or any(type(r) is not dict for r in consumers):
        raise ValueError('macro_expansion_consumer_set')
    by_flag = {r.get('flag'): r for r in consumers}
    actions = list(LEGACY_ACTION_ORDER) + list(EXPANSION_ACTION_ORDER)
    if len(by_flag) != 20 or any(by_flag.get(flag, {}).get('action') != action for flag, action in zip(expected_flags, actions)):
        raise ValueError('macro_expansion_action_bit_changed')
    if any(by_flag[flag].get('domain') != domain for flag, domain in zip(LEGACY_FLAG_ORDER, LEGACY_DOMAINS)):
        raise ValueError('macro_expansion_legacy_domain_changed')
    for action in ('regroup', 'withdraw', 'reinforce', 'deployattack', 'deploydefense'):
        row = next(c for c in consumers if c['action'] == action)
        if row.get('exclusive_group') != 'deployment_policy':
            raise ValueError('macro_expansion_legacy_exclusivity_changed')
    for row in candidate_definitions():
        actual = by_flag[PREFIX + row['action']]
        if any(actual.get(k) != v for k, v in row.items()):
            raise ValueError('macro_expansion_candidate_semantics_changed')
    ordered = [by_flag[f] for f in expected_flags]
    if 'legacy_consumer_definitions' in report:
        legacy = report['legacy_consumer_definitions']
        if legacy != ordered[:13] or canonical_digest(legacy) != report.get('legacy_consumer_semantics_sha256'):
            raise ValueError('macro_expansion_legacy_semantics_pin_changed')
    if 'expansion_candidates' in report and report['expansion_candidates'] != ordered[13:]:
        raise ValueError('macro_expansion_candidate_ledger_changed')
    masks = []
    for domain in ('construction', 'production', 'budget', 'deployment_policy'):
        bits = [i for i, flag in enumerate(expected_flags)
            if by_flag[flag].get('domain') == domain or by_flag[flag].get('exclusive_group') == domain]
        if not bits:
            raise ValueError('macro_expansion_exclusive_group_missing')
        masks.append(sum(1 << i for i in bits))
    masks.append(sum(1 << i for i, flag in enumerate(expected_flags) if by_flag[flag].get('domain') != 'budget'))
    if ('transport_exclusive_masks' in report and report['transport_exclusive_masks'] != masks
            or 'transport_known_mask' in report and report['transport_known_mask'] != (1 << 20) - 1):
        raise ValueError('macro_expansion_declared_mask_changed')
    return dict(protocol_version=2, flag_count=20, flags=expected_flags,
        actions_by_bit=actions, known_mask=(1 << 20) - 1, exclusive_masks=masks,
        max_work_actions=1, field_verified=False, capability_granted=False)


def validate_expansion_profile(report, *, compiled=True):
    """Runtime build API; validates compilation assertions and static semantics.

    The caller must verify actual package/audit files and their pinned hashes.
    A true compiled flag or digest alone is never evidence of field adoption.
    """
    contract = transport_contract(report)
    if compiled:
        if report.get('compiled') is not True:
            raise ValueError('compiled_macro_expansion_required')
        for key in ('big_sha256', 'compiled_expansion_audit_sha256'):
            value = report.get(key)
            if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('macro_expansion_compilation_pin_required')
    return dict(contract, consumers=deepcopy(report['consumers']))


def actions_mask(actions, contract):
    """Pure fixed-profile gate validation; budget plus one work action only."""
    if (type(actions) is not list or len(actions) > 2
            or any(type(a) is not str for a in actions) or len(set(actions)) != len(actions)):
        raise ValueError('macro_expansion_action_bounds')
    allowed = contract['actions_by_bit']
    if any(a not in allowed for a in actions):
        raise ValueError('macro_expansion_action_not_supported')
    mask = sum(1 << allowed.index(a) for a in actions)
    if any(mask & group and (mask & group) & ((mask & group) - 1) for group in contract['exclusive_masks']):
        raise ValueError('macro_expansion_actions_conflict')
    return mask
