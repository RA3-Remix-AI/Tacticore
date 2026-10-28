"""Read-only AST equivalence for one added original-native tactic type.

Every qualified parser, owner check, native link and group resolver is retained.
This does not qualify the new tactic's field layout or execution effects.
"""
import ast
import hashlib
from pathlib import Path

LEGACY_SHA='e8fb4f7e3f4c4a19509a599e15c1bb768cf10c8b6cdc12197b0d218014f1d028'


def verify(directory=None):
    folder=Path(directory) if directory else Path(__file__).resolve().parent
    old=folder/'macro_observation.py';new=folder/'macro_area_defense_observation.py'
    if hashlib.sha256(old.read_bytes()).hexdigest()!=LEGACY_SHA:raise ValueError('qualified_observer_changed')
    expected=old.read_text(encoding='utf-8')
    additions={
        'RUNTIME_VTABLES = {SCOUT_RUNTIME_VTABLE,SIMPLE_ATTACK_RUNTIME_VTABLE}':
            'STATIC_DEFENSE_RUNTIME_VTABLE = 0xc60bc4\nRUNTIME_VTABLES = {SCOUT_RUNTIME_VTABLE,SIMPLE_ATTACK_RUNTIME_VTABLE,STATIC_DEFENSE_RUNTIME_VTABLE}',
        'PINS = {':"PINS = {\n    0xc60bcc: '70058800',\n    0x880570: 'b850e9c500c3',",
        "native_tactic_family='simple_attack' if u(0)==SIMPLE_ATTACK_RUNTIME_VTABLE else 'flank_or_defense_avoidance_attack',":
            "native_tactic_family='static_defense' if u(0)==STATIC_DEFENSE_RUNTIME_VTABLE else 'simple_attack' if u(0)==SIMPLE_ATTACK_RUNTIME_VTABLE else 'flank_or_defense_avoidance_attack',",
    }
    for before,after in additions.items():
        if expected.count(before)!=1:raise ValueError('qualified_observer_extension_anchor')
        expected=expected.replace(before,after)
    if ast.dump(ast.parse(expected))!=ast.dump(ast.parse(new.read_text(encoding='utf-8'))):
        raise ValueError('unreviewed_observer_change')
    return dict(kind='one_native_type_read_only_observer_extension',qualified_source_sha256=LEGACY_SHA,
        extension_sha256=hashlib.sha256(new.read_bytes()).hexdigest(),strict_parsers_and_owner_checks_preserved=True,
        added_native_type='AIStaticDefenseTactic',new_tactic_field_layout_verified=False,execution_capability_granted=False)


if __name__=='__main__':
    import json
    print(json.dumps(verify()))
