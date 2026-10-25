"""Own-perspective calibration ranking, never an execution capability.

Only fresh, owned, living, independently mobile ground combat units contribute.
The two leased actors cannot count as their own native army support.
"""
import math

def support_evidence(units, target, excluded_ids, frame):
    selected = []
    for unit in units:
        xyz = unit.get('xyz')
        if (unit.get('owner_index') != 3 or unit.get('frame') != frame or
            unit.get('role') not in ('infantry', 'armor') or
            unit.get('independently_movable') is not True or
            unit.get('native_pool') is not True or
            type(unit.get('object_id')) is not int or unit['object_id'] <= 0 or
            unit['object_id'] in excluded_ids or
            type(unit.get('hp')) not in (int, float) or
            not math.isfinite(unit['hp']) or unit['hp'] <= 0 or
            not isinstance(xyz, (list, tuple)) or len(xyz) != 3 or
            not all(type(x) in (int, float) and math.isfinite(x) for x in xyz)):
            continue
        distance = math.dist(xyz[:2], target['xyz'][:2])
        if distance <= 450:
            selected.append(dict(unit, distance_to_target=distance))
    # Duplicate snapshots never manufacture a second supporting unit.
    ids = [u['object_id'] for u in selected]
    if len(ids) != len(set(ids)):
        return dict(ready=False, units=[], frame=frame, reason='duplicate_owned_id')
    armor = sum(u['role'] == 'armor' for u in selected)
    return dict(ready=len(selected) >= 2, units=selected, frame=frame,
        armor=armor, count=len(selected), radius=450,
        semantics='current_owned_native_combat_support_not_route_safety_or_victory')

def priority(evidence):
    return (not evidence['ready'], -evidence.get('armor', 0), -evidence.get('count', 0))
