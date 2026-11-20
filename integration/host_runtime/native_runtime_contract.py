"""Portable Native7 offline candidate verification; no research-archive IO.

The full companion inventory binds artifacts and dependencies. The compiled
closure separately locks all application Python code/cache plus interpreter
and extension binaries. Toolchain/Native sources are build provenance only.
No schema13 certificate is rewritten or upgraded by this module.
"""
import hashlib
import json
from pathlib import Path
import re

from .native7_paths import plain_local
from .native6_runtime_contract import (sha, canonical, pin_map, read, verify_inventory, locked_inputs)

GAME_SHA = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PACKAGE_SHA = '4128e1a598e12895fd84db3ce52122c696d9905e57e25497bd949a408466a62c'
KIND = 'portable_strategic_native7_offline_candidate'
FIELD_KIND = 'portable_strategic_native7_field_trial_candidate'
FLAG_ACTIONS = ('regroup', 'scout', 'withdraw', 'reinforce', 'budgeteconomy', 'budgetarmy', 'budgettech', 'attackenemy', 'deploydefense', 'expand', 'raideconomy')
FOCUS_ACTIONS = ('focusenemy4', 'focusenemy5')
ACTIONS = FLAG_ACTIONS + FOCUS_ACTIONS
FLAGS = tuple('/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_' + name for name in
              ('build_airfield', 'scout', 'buildtech', 'economyrefinery', 'budgeteconomy', 'budgetarmy', 'budgettech', 'deployattack', 'deploydefense', 'expand', 'raideconomy'))
ARTIFACTS = ('StrategicCommanderV7.dll', 'manager_host.exe')
MAX_PINS = 4093


def closure(pins, provenance, *, field_candidate=False):
    pin_map(pins)
    pin_map(provenance)
    value=dict(protocol_version=7,runtime=pins,build=provenance)
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
    if build != root / 'native/strategic7':
        raise ValueError('native7_fixed_companion_layout_required')
    return _verified_build(build, verify_inventory(root))


def _verified_build(build, inventory):
    """Review build metadata against this operation's fully checked inventory."""
    build = plain_local(build)
    if build != build.parent.parent / 'native/strategic7':
        raise ValueError('native7_fixed_companion_layout_required')
    manifest_pin = inventory['files'].get('native/strategic7/build-manifest.json')
    if manifest_pin is None:
        raise ValueError('native7_companion_entrypoint_missing')
    manifest = read(build / 'build-manifest.json', expected=manifest_pin)
    fields = {'schema_version', 'kind', 'protocol_version', 'compile_only', 'admission_ready',
              'product_capability_granted', 'formal_games', 'game_sha256', 'package_sha256',
              'actions', 'flags', 'input_pins', 'build_source_pins', 'source_closure_sha256', 'artifacts', 'layout'}
    if (type(manifest) is not dict or set(manifest) != fields or type(manifest['schema_version']) is not int
            or manifest['schema_version'] != 1 or manifest['kind'] not in (KIND,FIELD_KIND)
            or type(manifest['protocol_version']) is not int or manifest['protocol_version'] != 7
            or type(manifest['compile_only']) is not bool or type(manifest['admission_ready']) is not bool
            or (manifest['compile_only'],manifest['admission_ready'])!=((True,False) if manifest['kind']==KIND else (False,True))
            or manifest['product_capability_granted'] is not False or type(manifest['formal_games']) is not int
            or manifest['formal_games'] != 0 or manifest['game_sha256'] != GAME_SHA or manifest['package_sha256'] != PACKAGE_SHA
            or manifest['actions'] != list(ACTIONS) or manifest['flags'] != list(FLAGS)):
        raise ValueError('native7_offline_fixed_contract_required')
    pins, provenance = manifest['input_pins'], manifest['build_source_pins']
    pin_map(pins)
    pin_map(provenance)
    field=manifest['kind']==FIELD_KIND
    if pins != locked_inputs(inventory) or manifest['source_closure_sha256'] != closure(pins, provenance,field_candidate=field):
        raise ValueError('native7_code_closure_changed')
    if set(manifest['artifacts']) != set(ARTIFACTS) or any(sha(build / name) != manifest['artifacts'][name] for name in ARTIFACTS):
        raise ValueError('native7_artifact_changed')
    if (build / 'profile.h').read_text(encoding='ascii') != profile(pins, provenance,field_candidate=field):
        raise ValueError('native7_compiled_profile_changed')
    if field and 'qualification/native7-trial.json' not in pins:
        raise ValueError('native7_trial_qualification_required')
    return manifest
