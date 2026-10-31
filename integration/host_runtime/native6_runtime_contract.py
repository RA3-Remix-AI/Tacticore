"""Portable Native6 offline candidate verification; no research-archive IO.

The full companion inventory binds artifacts and dependencies. The compiled
closure separately locks all application Python code/cache plus interpreter
and extension binaries. Toolchain/Native sources are build provenance only.
No schema13 certificate is rewritten or upgraded by this module.
"""
import hashlib
import json
from pathlib import Path
import re

from .native6_paths import plain_local

GAME_SHA = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PACKAGE_SHA = '66025609e788ed18f8eb55b1722e6c197a373f387137b69e6b04118d0a5278f0'
KIND = 'portable_strategic_native6_offline_candidate'
FIELD_KIND = 'portable_strategic_native6_field_trial_candidate'
ACTIONS = ('regroup', 'scout', 'withdraw', 'reinforce', 'budgeteconomy', 'budgetarmy', 'budgettech', 'deployattack', 'deploydefense', 'expand')
FLAGS = tuple('/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_' + name for name in
              ('build_airfield', 'scout', 'buildtech', 'economyrefinery', 'budgeteconomy', 'budgetarmy', 'budgettech', 'deployattack', 'deploydefense', 'expand'))
ARTIFACTS = ('StrategicCommanderV6.dll', 'manager_host.exe')
MAX_PINS = 4093


def sha(path):
    value = hashlib.sha256()
    with plain_local(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            value.update(block)
    return value.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('native6_duplicate_json_key')
        result[key] = value
    return result


def read(path):
    with plain_local(path).open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('native6_manifest_unbounded')
    return json.loads(raw, object_pairs_hook=unique)


def relative(name):
    if type(name) is not str or not name or '\\' in name or ':' in name or '\x00' in name:
        return False
    return all(part not in ('', '.', '..') and not part.endswith((' ', '.')) for part in name.split('/'))


def pin_map(value):
    if type(value) is not dict or not value or len(value) > 100000:
        raise ValueError('native6_pin_inventory_required')
    folded = set()
    for name, digest in value.items():
        if (not relative(name) or name.casefold() in folded or type(digest) is not str
                or re.fullmatch('[0-9a-f]{64}', digest) is None):
            raise ValueError('native6_relative_pin_required')
        folded.add(name.casefold())


def verify_inventory(root, *, expected=None):
    root = plain_local(root)
    manifest = read(root / 'manifest.json')
    if (type(manifest) is not dict or set(manifest) != {'schema_version', 'python', 'working_directory', 'files'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
            or manifest['python'] != 'python/python.exe' or manifest['working_directory'] != 'app/integration'):
        raise ValueError('native6_companion_manifest_required')
    pins = manifest['files']
    pin_map(pins)
    if any(name.casefold() == 'manifest.json' for name in pins):
        raise ValueError('native6_manifest_self_reference')
    if not {'python/python.exe', 'app/integration/host_runtime/bridge_service.py'} <= pins.keys():
        raise ValueError('native6_companion_entrypoint_missing')
    if expected is not None and sha(root / 'manifest.json') != expected:
        raise ValueError('native6_companion_manifest_changed')
    found = set()
    for index, path in enumerate(root.rglob('*')):
        if index >= 150000:
            raise ValueError('native6_companion_inventory_unbounded')
        plain_local(path)
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if name == 'manifest.json':
            continue
        if path.stat().st_size > 256 * 1024 * 1024 or name not in pins or sha(path) != pins[name]:
            raise ValueError('native6_companion_inventory_changed')
        found.add(name)
    if found != pins.keys():
        raise ValueError('native6_companion_inventory_missing')
    return manifest


def locked_inputs(inventory):
    pins = {name: digest for name, digest in inventory['files'].items()
            if (name.startswith('app/') and name.endswith(('.py', '.pyc'))) or name.startswith('qualification/')
            or (name.startswith('python/') and name.lower().endswith(('.py','.pyc','.exe', '.dll', '.pyd', '._pth','.zip')))
            or name=='dependency-container.json'}
    pin_map(pins)
    if not 1 <= len(pins) <= MAX_PINS or any(name.startswith('native/') for name in pins):
        raise ValueError('native6_bounded_code_closure_required')
    return pins


def closure(pins, provenance, *, field_candidate=False):
    pin_map(pins)
    pin_map(provenance)
    value=dict(runtime=pins,build=provenance)
    if field_candidate:value['field_candidate']=True
    return hashlib.sha256(canonical(value).encode('ascii')).hexdigest()


def profile(pins, provenance, *, field_candidate=False):
    pin_map(pins)
    digest = closure(pins, provenance,field_candidate=field_candidate)
    def octets(value):
        return '{' + ','.join(str(v) for v in bytes.fromhex(value)) + '}'
    rows = ','.join('{L' + json.dumps(name, ensure_ascii=True) + ',' + octets(pin) + '}' for name, pin in sorted(pins.items()))
    return ('#pragma once\n#include <stdint.h>\n#include <wchar.h>\n'
            'static const bool FIELD_CANDIDATE='+('true' if field_candidate else 'false')+';\n'
            'static const unsigned HARD_WALL_MS=3600000;\n'
            'static const char* const FLAG_NAMES[]={' + ','.join(json.dumps(flag) for flag in FLAGS) + '};\n'
            'struct SourcePin {const wchar_t* path;uint8_t sha[32];};\n'
            'static const SourcePin SOURCE_PINS[]={' + rows + '};\n'
            'static const unsigned SOURCE_PIN_COUNT=sizeof(SOURCE_PINS)/sizeof(SourcePin);\n'
            'static const uint8_t PACKAGE_SHA[32]=' + octets(PACKAGE_SHA) + ';\n'
            'static const uint8_t GAME_SHA[32]=' + octets(GAME_SHA) + ';\n'
            'static const uint8_t SOURCE_SHA[32]=' + octets(digest) + ';\n')


def verify_build(build):
    build = plain_local(build)
    root = build.parent.parent
    if build != root / 'native/strategic6':
        raise ValueError('native6_fixed_companion_layout_required')
    manifest = read(build / 'build-manifest.json')
    fields = {'schema_version', 'kind', 'protocol_version', 'compile_only', 'admission_ready',
              'product_capability_granted', 'formal_games', 'game_sha256', 'package_sha256',
              'actions', 'flags', 'input_pins', 'build_source_pins', 'source_closure_sha256', 'artifacts', 'layout'}
    if (type(manifest) is not dict or set(manifest) != fields or type(manifest['schema_version']) is not int
            or manifest['schema_version'] != 1 or manifest['kind'] not in (KIND,FIELD_KIND)
            or type(manifest['protocol_version']) is not int or manifest['protocol_version'] != 6
            or type(manifest['compile_only']) is not bool or type(manifest['admission_ready']) is not bool
            or (manifest['compile_only'],manifest['admission_ready'])!=((True,False) if manifest['kind']==KIND else (False,True))
            or manifest['product_capability_granted'] is not False or type(manifest['formal_games']) is not int
            or manifest['formal_games'] != 0 or manifest['game_sha256'] != GAME_SHA or manifest['package_sha256'] != PACKAGE_SHA
            or manifest['actions'] != list(ACTIONS) or manifest['flags'] != list(FLAGS)):
        raise ValueError('native6_offline_fixed_contract_required')
    pins, provenance = manifest['input_pins'], manifest['build_source_pins']
    pin_map(pins)
    pin_map(provenance)
    inventory = verify_inventory(root)
    field=manifest['kind']==FIELD_KIND
    if pins != locked_inputs(inventory) or manifest['source_closure_sha256'] != closure(pins, provenance,field_candidate=field):
        raise ValueError('native6_code_closure_changed')
    if set(manifest['artifacts']) != set(ARTIFACTS) or any(sha(build / name) != manifest['artifacts'][name] for name in ARTIFACTS):
        raise ValueError('native6_artifact_changed')
    if (build / 'profile.h').read_text(encoding='ascii') != profile(pins, provenance,field_candidate=field):
        raise ValueError('native6_compiled_profile_changed')
    if field and 'qualification/native6-trial.json' not in pins:
        raise ValueError('native6_trial_qualification_required')
    return manifest
