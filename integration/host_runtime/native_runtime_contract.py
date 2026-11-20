"""The one native runtime contract: fixed identities, inventory and build checks.

The installed runtime is one directory whose manifest.json lists every file
with its SHA-256. The native launcher passes that manifest's hash; install and
launch verify every file against it. The compiled build manifest records the
locked Python inputs that the DLL re-hashes at attach. Source edits never need
hand-maintained pins: a new build regenerates them.
"""
import hashlib
import json
from pathlib import Path
import re

from .native_paths import plain_local

# Binary contract of the compiled companion (shared.h / portable_paths.h).
PROTOCOL = 7
BUILD_DIR = 'native/strategic7'
MAPPING_PREFIX = 'Local\\RA3StrategicCommanderV7_'
LEASE_PREFIX = 'Local\\RA3MacroPolicyLease_'
SDK_DIR = 'native-ai/strategic-portable-runtime-v7'

GAME_SHA = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PACKAGE_SHA = '4128e1a598e12895fd84db3ce52122c696d9905e57e25497bd949a408466a62c'
KIND = 'portable_strategic_native7_offline_candidate'
FIELD_KIND = 'portable_strategic_native7_field_trial_candidate'
FLAG_ACTIONS = ('regroup', 'scout', 'withdraw', 'reinforce', 'budgeteconomy', 'budgetarmy', 'budgettech', 'attackenemy', 'deploydefense', 'expand', 'raideconomy')
# One focus intent per player id; the native lease checks enmity live.
FOCUS_ACTIONS = tuple('focusenemy' + str(player) for player in range(16))
ACTIONS = FLAG_ACTIONS + FOCUS_ACTIONS
FLAGS = tuple('/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_' + name for name in
              ('build_airfield', 'scout', 'buildtech', 'economyrefinery', 'budgeteconomy', 'budgetarmy', 'budgettech', 'deployattack', 'deploydefense', 'expand', 'raideconomy'))
ARTIFACTS = ('StrategicCommanderV7.dll', 'manager_host.exe')
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
            raise ValueError('native_duplicate_json_key')
        result[key] = value
    return result


def read(path, *, expected=None):
    with plain_local(path).open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('native_manifest_unbounded')
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('native_pinned_file_changed')
    return json.loads(raw, object_pairs_hook=unique)


def relative(name):
    if type(name) is not str or not name or '\\' in name or ':' in name or '\x00' in name:
        return False
    return all(part not in ('', '.', '..') and not part.endswith((' ', '.')) for part in name.split('/'))


def pin_map(value):
    if type(value) is not dict or not value or len(value) > 100000:
        raise ValueError('native_pin_inventory_required')
    folded = set()
    for name, digest in value.items():
        if (not relative(name) or name.casefold() in folded or type(digest) is not str
                or re.fullmatch('[0-9a-f]{64}', digest) is None):
            raise ValueError('native_relative_pin_required')
        folded.add(name.casefold())


def verify_inventory(root, *, expected=None):
    root = plain_local(root)
    manifest = read(root / 'manifest.json')
    if (type(manifest) is not dict or set(manifest) != {'schema_version', 'python', 'working_directory', 'files'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
            or manifest['python'] != 'python/python.exe' or manifest['working_directory'] != 'app/integration'):
        raise ValueError('native_companion_manifest_required')
    pins = manifest['files']
    pin_map(pins)
    if any(name.casefold() == 'manifest.json' for name in pins):
        raise ValueError('native_manifest_self_reference')
    if not {'python/python.exe', 'app/integration/host_runtime/bridge_service.py'} <= pins.keys():
        raise ValueError('native_companion_entrypoint_missing')
    if expected is not None and sha(root / 'manifest.json') != expected:
        raise ValueError('native_companion_manifest_changed')
    found = set()
    for index, path in enumerate(root.rglob('*')):
        if index >= 150000:
            raise ValueError('native_companion_inventory_unbounded')
        if not path.is_file():
            plain_local(path)
            continue
        name = path.relative_to(root).as_posix()
        if name == 'manifest.json':
            continue
        # sha validates this file and every ancestor before opening it.
        if path.stat().st_size > 256 * 1024 * 1024 or name not in pins or sha(path) != pins[name]:
            raise ValueError('native_companion_inventory_changed')
        found.add(name)
    if found != pins.keys():
        raise ValueError('native_companion_inventory_missing')
    return manifest


def locked_inputs(inventory):
    pins = {name: digest for name, digest in inventory['files'].items()
            if (name.startswith('app/') and name.endswith(('.py', '.pyc'))) or name.startswith('qualification/')
            or (name.startswith('python/') and name.lower().endswith(('.py','.pyc','.exe', '.dll', '.pyd', '._pth','.zip')))
            or name=='dependency-container.json'}
    pin_map(pins)
    if not 1 <= len(pins) <= MAX_PINS or any(name.startswith('native/') for name in pins):
        raise ValueError('native_bounded_code_closure_required')
    return pins


def closure(pins, provenance, *, field_candidate=False):
    pin_map(pins)
    pin_map(provenance)
    value=dict(protocol_version=PROTOCOL,runtime=pins,build=provenance)
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
    if build != root / BUILD_DIR:
        raise ValueError('native_fixed_companion_layout_required')
    return _verified_build(build, verify_inventory(root))


def _verified_build(build, inventory):
    """Review build metadata against this operation's fully checked inventory."""
    build = plain_local(build)
    if build != build.parent.parent / BUILD_DIR:
        raise ValueError('native_fixed_companion_layout_required')
    manifest_pin = inventory['files'].get(BUILD_DIR + '/build-manifest.json')
    if manifest_pin is None:
        raise ValueError('native_companion_entrypoint_missing')
    manifest = read(build / 'build-manifest.json', expected=manifest_pin)
    fields = {'schema_version', 'kind', 'protocol_version', 'compile_only', 'admission_ready',
              'product_capability_granted', 'formal_games', 'game_sha256', 'package_sha256',
              'actions', 'flags', 'input_pins', 'build_source_pins', 'source_closure_sha256', 'artifacts', 'layout'}
    if (type(manifest) is not dict or set(manifest) != fields or type(manifest['schema_version']) is not int
            or manifest['schema_version'] != 1 or manifest['kind'] not in (KIND,FIELD_KIND)
            or type(manifest['protocol_version']) is not int or manifest['protocol_version'] != PROTOCOL
            or type(manifest['compile_only']) is not bool or type(manifest['admission_ready']) is not bool
            or (manifest['compile_only'],manifest['admission_ready'])!=((True,False) if manifest['kind']==KIND else (False,True))
            or manifest['product_capability_granted'] is not False or type(manifest['formal_games']) is not int
            or manifest['formal_games'] != 0 or manifest['game_sha256'] != GAME_SHA or manifest['package_sha256'] != PACKAGE_SHA
            or manifest['actions'] != list(ACTIONS) or manifest['flags'] != list(FLAGS)):
        raise ValueError('native_offline_fixed_contract_required')
    pins, provenance = manifest['input_pins'], manifest['build_source_pins']
    pin_map(pins)
    pin_map(provenance)
    field=manifest['kind']==FIELD_KIND
    if pins != locked_inputs(inventory) or manifest['source_closure_sha256'] != closure(pins, provenance,field_candidate=field):
        raise ValueError('native_code_closure_changed')
    if set(manifest['artifacts']) != set(ARTIFACTS) or any(sha(build / name) != manifest['artifacts'][name] for name in ARTIFACTS):
        raise ValueError('native_artifact_changed')
    if (build / 'profile.h').read_text(encoding='ascii') != profile(pins, provenance,field_candidate=field):
        raise ValueError('native_compiled_profile_changed')
    return manifest
