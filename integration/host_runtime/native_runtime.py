"""The installed native runtime and the strategic scope one match can use.

The native launcher passes the hash of the runtime's manifest.json in
TACTICORE_RUNTIME_MANIFEST_SHA256. ``current`` verifies every installed file
against that manifest; setup, game launch and each Host start call it once.
The per-session descriptor only points at that runtime; loading it never
re-proves historical qualification evidence.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re

from .contracts import ContractError
from .native_paths import plain_local
from .native_runtime_contract import (BUILD_DIR, FIELD_KIND, FLAG_ACTIONS, FLAGS, PACKAGE_SHA, PROTOCOL,
                                      _verified_build, read, sha, verify_inventory)
from .scenario import MODEL_PLAYER_ID, MatchScenario
from .strategic_contract import FOCUS_ACTIONS as FOCUS_GRAMMAR, GATE_ACTIONS, focus_actions_for

KIND = 'native_runtime_descriptor'
DESCRIPTOR_VERSION = 16
COMMANDER = '57e668b4-4d89-43bd-bc92-0dd436f046ef'
# Data files shipped with the runtime and pinned by its manifest.
REGISTRY = 'qualification/registry.json'
PACKAGE_REPORT = 'qualification/package.json'
VISIBILITY_DATA = 'qualification/native6-trial.json'


def fail():
    raise ContractError('native_runtime_not_verified')


def runtime_root():
    """The runtime directory that contains this installed module."""
    root = Path(__file__).resolve().parents[3]
    if Path(__file__).resolve() != root / 'app/integration/host_runtime/native_runtime.py':
        fail()
    return plain_local(root)


def trusted_pin():
    pin = os.environ.get('TACTICORE_RUNTIME_MANIFEST_SHA256')
    if type(pin) is not str or re.fullmatch('[0-9a-f]{64}', pin) is None:
        fail()
    return pin


def verify_runtime(root, pin):
    """Hash every runtime file against the pinned manifest and check the build."""
    try:
        inventory = verify_inventory(root, expected=pin)
        build = _verified_build(plain_local(root) / BUILD_DIR, inventory)
    except (OSError, ValueError, KeyError, TypeError):
        fail()
    if build['kind'] != FIELD_KIND or build['compile_only'] or not build['admission_ready']:
        fail()
    return inventory, build


def current():
    """Full install/launch verification: (root, pin, inventory, build manifest)."""
    root = runtime_root()
    pin = trusted_pin()
    inventory, build = verify_runtime(root, pin)
    return root, pin, inventory, build


def admitted_build(build):
    """Cheap re-check before attach: same runtime, same pinned build files."""
    root = runtime_root()
    pin = trusted_pin()
    if Path(build) != root / BUILD_DIR:
        fail()
    try:
        if sha(root / 'manifest.json') != pin:
            fail()
        return _verified_build(root / BUILD_DIR, read(root / 'manifest.json'))
    except (OSError, ValueError, KeyError, TypeError):
        fail()


@dataclass(frozen=True)
class NativeScope:
    """What the commander may ask of the native AI in one match."""
    package_sha256: str
    flag_pairs: tuple
    region_pairs: tuple
    evidence: tuple = ()
    required_origin_region: str = 'region_8_3'
    opponent_player_ids: tuple = ()
    withheld_actions: tuple = ()
    runtime_root: Path = Path()
    runtime_manifest_sha256: str = ''
    native_transport_protocol: int = PROTOCOL
    native_transport_client: str = 'native_transport.py'

    @property
    def focus_actions(self):
        """Focus intents for the actual enemies; one enemy needs no preference."""
        if len(self.opponent_player_ids) < 2:
            return ()
        return tuple(focus_actions_for(self.opponent_player_ids))

    @property
    def maximum_model_input_bytes(self):
        return 32768

    @property
    def intent_contract(self):
        from .strategic_contract import INDEPENDENT_DEVELOPMENT_CONTRACT
        return INDEPENDENT_DEVELOPMENT_CONTRACT

    @property
    def minimum_model_game_seconds(self):
        return 0.

    @property
    def available_actions(self):
        actions = FLAG_ACTIONS + self.focus_actions + tuple(GATE_ACTIONS)
        return tuple(action for action in actions if action not in self.withheld_actions)

    @property
    def action_flags(self):
        return dict(self.flag_pairs)

    @property
    def regional_action_regions(self):
        return dict(self.region_pairs)

    @property
    def production_counts(self):
        return {}

    def model_catalog_overrides(self):
        from .macro_group_role_contract import home_strategic_catalog_overrides
        catalog = home_strategic_catalog_overrides(self.required_origin_region)
        for entry in catalog.values():
            entry.pop('exclusive_with_other_construction_or_production', None)
        catalog['expand'].pop('native_expansion_interval_seconds', None)
        catalog['expand']['strategic_timing_owner'] = 'agent'
        catalog['expand']['native_target_and_tactic_preserved'] = True
        catalog['expand']['stock_conditions_preserved'] = False
        catalog['expand']['native_operational_conditions_preserved'] = True
        from native_unified_contract_v5 import additional_catalog
        catalog['raideconomy'] = additional_catalog(('raideconomy',))['raideconomy']
        catalog['raideconomy'].update(native_executor='same_as_attackenemy',
            native_target_policy='safest_ground_harvester', specialized_unit_prerequisite=False,
            execution_policy='qualified_native_attack_executor')
        catalog['pauseconstruction'] = dict(additional_catalog(('pauseconstruction',))['pauseconstruction'],
            scope='all_native_construction_including_economic_recovery')
        catalog['attackenemy'] = dict(additional_catalog(('attackenemy',))['attackenemy'],
            target_policy='native_closest_ground_structure_preferred_enemy')
        for action in self.focus_actions:
            catalog[action] = dict(domain='enemy_focus', goal='prefer_public_enemy_player',
                target_player_id=FOCUS_GRAMMAR[action], maximum_duration_seconds=60, details_owner='native_ai',
                mission_success_verified=False)
        return catalog

    def public(self):
        return dict(available_actions=list(self.available_actions), package_sha256=self.package_sha256,
            native_transport_protocol=self.native_transport_protocol, details_owner='native_ai',
            exact_templates_quantities_or_unit_orders=False,
            construction_and_production='bounded_native_scheduling_gate_with_baseline_return',
            expansion='stock_native_preference_with_stock_guards',
            required_origin_region=self.required_origin_region,
            regional_action_regions=self.regional_action_regions,
            intent_contract=self.intent_contract, maximum_model_input_bytes=self.maximum_model_input_bytes,
            runtime_manifest_sha256=self.runtime_manifest_sha256)


def header(value):
    fields = {'schema_version', 'kind', 'runtime_root', 'runtime_manifest_sha256'}
    if type(value) is not dict or set(value) != fields or value['kind'] != KIND:
        fail()
    if type(value['schema_version']) is not int or value['schema_version'] != DESCRIPTOR_VERSION:
        fail()


def load(path, session=None):
    """The runtime descriptor and the scope for ``session`` (if given)."""
    try:
        value = read(path)
    except (OSError, ValueError):
        fail()
    header(value)
    root = runtime_root()
    pin = trusted_pin()
    if Path(value['runtime_root']) != root or value['runtime_manifest_sha256'] != pin:
        fail()
    bundle = dict(value, build=str(root / BUILD_DIR), visibility=str(root / 'qualification'))
    flags = tuple(zip(FLAG_ACTIONS, FLAGS))
    if session is None:
        return bundle, NativeScope(PACKAGE_SHA, flags, (), runtime_root=root, runtime_manifest_sha256=pin)
    selected = session_scenario(session, root)
    regions = tuple((action, region) for action, region in selected.regional_action_regions
                    if action in FLAG_ACTIONS)
    scope = NativeScope(PACKAGE_SHA, flags, regions, required_origin_region=selected.own_region,
        opponent_player_ids=selected.enemy_player_ids, withheld_actions=selected.withheld_actions,
        runtime_root=root, runtime_manifest_sha256=pin)
    return bundle, scope


def session_scenario(session, root):
    """The session's match scenario, bound to this runtime's package and seat."""
    scenario = session.get('scenario', {})
    try:
        selected = MatchScenario.from_session(scenario)
    except ContractError:
        fail()
    if (session.get('mod_sha256') != PACKAGE_SHA or Path(session.get('registry', '')) != root / REGISTRY
            or scenario.get('commander_id') != COMMANDER or selected.model_player_id != MODEL_PLAYER_ID):
        fail()
    return selected


def create(path):
    """Write the descriptor for the current runtime (exclusive create)."""
    root = runtime_root()
    value = dict(schema_version=DESCRIPTOR_VERSION, kind=KIND, runtime_root=str(root),
                 runtime_manifest_sha256=trusted_pin())
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write('\n')
    return value


def admit_sdk(build, session):
    """Called by the SDK before attach: same runtime build, supported session."""
    manifest = admitted_build(build)
    session_scenario(session, runtime_root())
    return manifest
