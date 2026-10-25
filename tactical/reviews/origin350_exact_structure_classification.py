"""Pure, narrow research classifier. No process, SDK, GUI, file, or guard access.

Input is trusted native reader output plus a current full-footprint visibility
binding. This function is not a capability grant and does not make an origin safe.
Per-instance same-frame observations are independent; no group-frame equality is
required. Exact module multisets come from fresh01's four independent live reads.
"""
from collections import Counter
import math

PACKAGE = '2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665'
EXE = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
EXACT = {
    '0xc16ff13f': 'SovietConstructionYard', '0x80d4ea1e': 'SovietBarracks',
    '0xcf8d9f20': 'SovietPowerPlant', '0xc45aaeab': 'SovietRefinery',
}
# Runtime primary-name getter spellings; duplicates are intentional module counts.
COMMON = ['ActiveBody', 'AIUpdateInterface', 'ObjectSMCHelper', 'ObjectDefectionHelper',
          'AttributeModifierPoolUpdate', 'FireWeaponWhenDeadBehavior', 'StructureSellUpdate',
          'SecondaryDamageTracker', 'SquishCollide', 'PhysicsBehavior', 'RepairUpdate',
          'EngineerContain', 'InfiltratorContain', 'StructureUnpackUpdate', 'DestroyDie']
SIGNATURES = {
    '0xc16ff13f': Counter(COMMON + ['BuildingDestructionBehavior', 'FXListBehavior']
                         + ['FXListBehavior', 'CreateObjectDie', 'CreateObjectDie',
                            'CreateObjectDie', 'CreateObjectDie', 'BuildingBehavior',
                            'ProductionUpdate', 'ProductionUpdate', 'ProductionUpdateInfo',
                            'QueueProductionExitUpdate', 'SpecialPowerModule',
                            'ReplaceSelfSpecialAbility', 'InfiltratorContain', 'LUAEventListBehavior']),
    '0x80d4ea1e': Counter(COMMON + ['BuildingDestructionBehavior', 'FXListBehavior',
                                  'FXListBehavior', 'CreateObjectDie', 'CreateObjectDie',
                                  'CreateObjectDie', 'BuildingBehavior', 'ProductionUpdate',
                                  'QueueProductionExitUpdate', 'StancesBehavior']),
    '0xcf8d9f20': Counter(COMMON + ['BuildingDestructionBehavior', 'BuildingDestructionBehavior',
                                  'FXListBehavior', 'FXListBehavior', 'CreateObjectDie',
                                  'CreateObjectDie', 'CreateObjectDie', 'CreateObjectDie',
                                  'BuildingBehavior', 'BuildingBehavior', 'ProductionUpdate',
                                  'PowerUpgrade']),
    '0xc45aaeab': Counter(COMMON + ['BuildingDestructionBehavior', 'FXListBehavior',
                                  'FXListBehavior', 'CreateObjectDie', 'CreateObjectDie',
                                  'CreateObjectDie', 'CreateObjectDie', 'QueueDockBehavior',
                                  'QueueProductionExitUpdate', 'SpawnBehavior', 'ProductionUpdate',
                                  'AssistedPlacementBehavior', 'StructurePlacementBehavior',
                                  'LUAEventListBehavior']),
}


def facts_from_sample(report, row, current_visibility=None):
    """Adapt one raw row; preserve its independent frame even if group spans frames."""
    return {'schema_version': 1, 'package_sha256': report.get('package_sha256'),
            'executable_sha256': report.get('executable_sha256'),
            'session_id': report.get('session_id'), 'pid': report.get('pid'),
            'session_stable': report.get('session_stable'),
            'package_stable': report.get('package_stable'),
            'logic_stable': report.get('logic_stable'),
            'sample': row, 'current_visibility': current_visibility}


def instance_evidence(facts):
    """Recheck raw per-instance observations. No visibility or exclusion claim."""
    failures = []
    if not isinstance(facts, dict):
        return {'verified': False, 'failures': ['malformed_native_facts'],
                'type_hash': None, 'template_name': None, 'identity': {}}
    def need(value, reason):
        if value is not True:
            failures.append(reason)
    try:
        need(facts.get('schema_version') == 1, 'unknown_facts_schema')
        need(facts.get('package_sha256') == PACKAGE, 'unsupported_package')
        need(facts.get('executable_sha256') == EXE, 'unsupported_executable')
        need(bool(facts.get('session_id')) and type(facts.get('pid')) is int
             and facts['pid'] > 0, 'missing_session_pid')
        need(all(facts.get(k) is True for k in ['session_stable', 'package_stable', 'logic_stable']),
             'session_package_or_logic_changed')
        row = facts['sample']; first = row['first']; second = row['second']; ident = first['identity']
        kind = ident['type_hash']
        need(kind in EXACT, 'unknown_or_mobile_type_kept_threat')
        need(type(row['frame_start']) is int and row['frame_start'] > 0
             and row['frame_start'] == row['frame_end'], 'per_instance_frame_not_stable')
        need(first == second and ident == row['final_identity'], 'double_sample_changed')
        need(ident['vtable'] == '0xc4db60' and type(ident['object_id']) is int
             and ident['object_id'] > 0 and math.isfinite(ident['hp']) and ident['hp'] > 0,
             'identity_or_health_invalid')
        need(row.get('checks', {}).get('expected_identity') is True, 'reader_identity_binding_failed')
        inv = first['module_inventory']; modules = inv['modules']
        need(inv.get('complete') is True and inv.get('nonempty_complete') is True
             and inv.get('terminator_index') == len(modules) and bool(modules), 'module_array_incomplete')
        need(inv.get('array') == ident['module_array'], 'module_array_binding_mismatch')
        names = []
        seen = set()
        for index, module in enumerate(modules):
            need(module.get('index') == index and module.get('module') not in seen,
                 'module_order_or_duplicate')
            seen.add(module.get('module'))
            need(module.get('thing_backpointer') == ident['address']
                 and module.get('backpointer_ok') is True, 'module_owner_binding_mismatch')
            code = bytes.fromhex(module.get('getter_bytes', ''))
            need(len(code) == 6 and code[:1] == b'\xb8' and code[-1:] == b'\xc3'
                 and int.from_bytes(code[1:5], 'little') == int(module.get('name_pointer', '0'), 0)
                 and module.get('verified_constant_name_getter') is True,
                 'complex_or_unverified_name_getter')
            names.append(module.get('native_name'))
        need(kind in SIGNATURES and Counter(names) == SIGNATURES.get(kind),
             'module_class_multiset_not_exact_reviewed_type')
        matrix = first['weapon_matrix']
        need(ident['weapon_container'] == matrix.get('container') == '0x0'
             and 'error' not in matrix, 'registered_weapon_set_present_or_unknown')
        need('WeaponSetUpdate' not in names, 'armed_module_present')
        need({name for name in names if name and 'Contain' in name}
             <= {'EngineerContain', 'InfiltratorContain'}, 'firing_or_unknown_contain_present')
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError) as error:
        failures.append('malformed_native_facts:' + type(error).__name__)
        ident = {}; kind = None
    return {'verified': not failures, 'failures': failures, 'type_hash': kind,
            'template_name': EXACT.get(kind), 'identity': ident,
            'semantics': 'independent_per_instance_module_class_evidence_not_current_visibility'}


def classify(facts):
    """Exclude only immediate autonomous direct fire, with current FOV binding."""
    evidence = instance_evidence(facts)
    failures = list(evidence['failures'])
    if not isinstance(facts, dict):
        facts = {}
    visibility = facts.get('current_visibility') or {}
    try:
        ident = evidence['identity']; row = facts['sample']
        if visibility.get('source') != 'VisibilityCollector.private_targets':
            failures.append('missing_current_collector_visibility')
        if (visibility.get('observer_player_id') != 3 or visibility.get('relation') != 'enemy'
                or type(visibility.get('owner_player_id')) is not int
                or visibility.get('owner_player_id') == 3):
            failures.append('enemy_relationship_or_observer_binding_missing')
        if not all(visibility.get(k) is True for k in ['full_footprint_verified', 'runtime_stealth_safe']):
            failures.append('full_footprint_or_stealth_proof_missing')
        if (visibility.get('session_id') != facts.get('session_id')
                or visibility.get('pid') != facts.get('pid')
                or visibility.get('observed_frame') != row.get('frame_start')
                or any(visibility.get(k) != ident.get(k) for k in
                       ['address', 'object_id', 'owner', 'type_hash', 'template', 'body', 'hp'])):
            failures.append('current_visible_instance_identity_or_frame_mismatch')
    except (KeyError, TypeError, AttributeError):
        failures.append('malformed_visibility_binding')
    good = not failures
    kind = evidence['type_hash']
    hazards = []
    if kind in EXACT:
        hazards = ['CATALYST_death_weapon_EXPLOSIVE_200_radius_100_delay_1.5s',
                   'destruction_or_sale_can_spawn_mobile_unit',
                   'capture_and_infiltration_effects']
        if kind == '0xc16ff13f':
            hazards += ['pack_replace_to_mobile_MCV', 'destruction_sale_spawn_Engineer', 'production']
        if kind == '0xc45aaeab':
            hazards += ['miner_spawn_and_docking', 'moving_miners_and_collision_remain_threats']
        if kind == '0x80d4ea1e':
            hazards += ['normal_paid_unit_production']
    return {'category': 'no_autonomous_direct_fire_or_firing_garrison_verified' if good
            else 'unknown_or_armed_or_mobile_keep_threat',
            'exclude_from_immediate_direct_fire_only': good,
            'immediate_direct_fire_threat': not good,
            'safe_origin_verified': False, 'zero_occupants_proven': False,
            'capability_granted': False, 'radius_unchanged': 350,
            'conditional_hazards': hazards, 'mobile_entities_remain_threats': True,
            'template_name': evidence['template_name'], 'failures': failures,
            'template_instance_evidence': evidence['verified']}
