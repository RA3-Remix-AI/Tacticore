"""Allow one native ReactiveDefense type; retain every strict ownership parser."""
import ast
import hashlib
from pathlib import Path
from verify_area_defense_observer import verify as verify_parent

PARENT_SHA='c23e539d5ac864fa1aacfcbc7c3f9daa19eb2b82afaf30b91b942b79a783b5bb'
ADDITIONS={
    'RUNTIME_VTABLES = {SCOUT_RUNTIME_VTABLE,SIMPLE_ATTACK_RUNTIME_VTABLE,STATIC_DEFENSE_RUNTIME_VTABLE}':
        'REACTIVE_DEFENSE_RUNTIME_VTABLE = 0xc60b54\nRUNTIME_VTABLES = {SCOUT_RUNTIME_VTABLE,SIMPLE_ATTACK_RUNTIME_VTABLE,STATIC_DEFENSE_RUNTIME_VTABLE,REACTIVE_DEFENSE_RUNTIME_VTABLE}',
    'PINS = {':"PINS = {\n    0xc60b5c: '10058800',\n    0x880510: 'b820e9c500c3',\n    0x8cf16a: 'e871f4fdff',\n    0x8cf189: 'c706540bc600',",
    "native_tactic_family='static_defense' if u(0)==STATIC_DEFENSE_RUNTIME_VTABLE else":
        "native_tactic_family='reactive_defense' if u(0)==REACTIVE_DEFENSE_RUNTIME_VTABLE else 'static_defense' if u(0)==STATIC_DEFENSE_RUNTIME_VTABLE else",
}


def expected_source(folder):
    old=Path(folder)/'macro_area_defense_observation.py'
    if hashlib.sha256(old.read_bytes()).hexdigest()!=PARENT_SHA:raise ValueError('qualified_area_observer_changed')
    value=old.read_text(encoding='utf8')
    for before,after in ADDITIONS.items():
        if value.count(before)!=1:raise ValueError('group_observer_extension_anchor')
        value=value.replace(before,after)
    return value


def verify(directory=None):
    folder=Path(directory) if directory else Path(__file__).resolve().parent
    verify_parent(folder);new=folder/'macro_group_role_observation.py'
    if ast.dump(ast.parse(expected_source(folder)))!=ast.dump(ast.parse(new.read_text(encoding='utf8'))):
        raise ValueError('unreviewed_group_observer_change')
    return dict(kind='original_native_reactive_defense_observer_extension',strict_ownership_and_group_parsers_preserved=True,
        parent_sha256=PARENT_SHA,extension_sha256=hashlib.sha256(new.read_bytes()).hexdigest(),
        added_native_type='AIReactiveDefenseTactic',field_layout_qualified=False,execution_capability_granted=False)


if __name__=='__main__':
    import json
    print(json.dumps(verify()))
