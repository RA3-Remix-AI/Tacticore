"""Manifest-anchored Native7 bounded trials; never an inherited product pass.

The native launcher supplies the compiled companion pin. A descriptor, UI
field or self-reported qualification bit cannot establish that authority.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re

from .contracts import ContractError
from .native7_paths import plain_local
from .native7_runtime_contract import ACTIONS, FLAGS, GAME_SHA, PACKAGE_SHA, FIELD_KIND, FLAG_ACTIONS, FOCUS_ACTIONS, read, sha, _verified_build, verify_inventory
from .strategic_unified_bundle_v5 import UnifiedStrategicScopeV5
from .native6_qualification import session_scenario
from .strategic_contract_v5 import FOCUS_ACTIONS as FOCUS_GRAMMAR, focus_actions_for
from .strategic_contract_v5 import GATE_ACTIONS

KIND='native7_manifest_bound_trial'
COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'
REGISTRY_SHA='e6179743c946e323637161daafda39dcb295a64d05d9eedaee24cb3bb1f3821d'
PACKAGE_REPORT_SHA='44604c659ac1d9f1c15e5926857f0d9499ee9502d9047e793997711e7fba2647'
RAID_AUDIT_SHA='a8655e9131973381a946fd84479f6cda3984a9e5f81e79240cc5ff097efd2bb0'
RAID_PACKAGE_SHA='4811342ec70c153ee8b2328797dc321e62b2770b53d5e6270b7f396c59dff29c'
TIMING_AUDIT_SHA='0efa91dc8e25f2ce357d162877cb0cdbff5a3e83104609f771cbc6a449956b37'
TIMING_PACKAGE_SHA='0c1cf8c501aef75b60d5e6b6419c70c659dd8042474eae2df09f57861a5d75e8'
RAID_TARGET_AUDIT_SHA='8cdb56fb267925ba5aebdae7e259224e4418b013281a148b1debc427711a4d7b'


def fail():raise ContractError('native7_trial_not_qualified')


def runtime_root():
    root=Path(__file__).resolve().parents[3]
    if Path(__file__).resolve()!=root/'app/integration/host_runtime/native7_qualification.py':fail()
    return plain_local(root)


def verify_qualification(root,expected):
    """Pure file verification; no Game, compiler, source XML or old reports."""
    if type(expected) is not str or re.fullmatch('[0-9a-f]{64}',expected) is None:fail()
    root=plain_local(root);inventory=verify_inventory(root,expected=expected)
    build=_verified_build(root/'native/strategic7',inventory)
    if build['kind']!=FIELD_KIND or build['compile_only'] or not build['admission_ready']:fail()
    cap=verify_capsule(root,inventory)
    focus=read(root/'qualification/native7-trial.json')
    if any(build['build_source_pins'].get(name)!=pin for name,pin in focus['source_sha256'].items()):fail()
    return inventory,build,cap


def verify_capsule(root,inventory):
    # Reuse exact-build lawful-view evidence without upgrading its historical
    # Native6 transport or product-acceptance claims.
    from .native6_qualification import verify_capsule as verify_visibility
    audit=read(root/'qualification/strategic-raid-audit.json',expected=RAID_AUDIT_SHA)
    if (audit.get('kind')!='compiled_strategic_raid_derivation_v1' or audit.get('package_sha256')!=RAID_PACKAGE_SHA
            or audit.get('base_package_sha256')!='ef94fe04a8c51d65d24498e37bc40f1cc5f2b28daa5a1acb74f2d54ae89fb1ea'
            or audit.get('native_team_template_and_micro_preserved') is not True
            or audit.get('native_task_readiness_preserved') is not True
            or audit.get('commander_owns_strategic_dispatch_timing') is not True
            or audit.get('preferred_enemy_target_selection') is not True
            or {row['stream'] for row in audit['streams']}!={'mod','mod_M','mod_L'}
            or any(row.get('all_game_object_assets_preserved') is not True
                   or row.get('original_micro_managers_preserved') is not True for row in audit['streams'])):fail()
    timing=read(root/'qualification/strategic-timing-audit.json',expected=TIMING_AUDIT_SHA)
    if (timing.get('kind')!='compiled_strategic_timing_derivation_v1'
            or timing.get('base_package_sha256')!=RAID_PACKAGE_SHA or timing.get('package_sha256')!=TIMING_PACKAGE_SHA
            or timing.get('expansion_target_and_tactic_preserved') is not True
            or timing.get('raid_native_general_tactic_preserved') is not True
            or timing.get('raid_tactic_canonical_sha256')!='794755dd055a6d3f11f4cb209577a6e7b5ea3dad631b9f374597d32564f390d9'
            or {row['stream'] for row in timing['streams']}!={'mod','mod_M','mod_L'}
            or any(row.get('all_game_object_assets_preserved') is not True
                   or row.get('original_autonomous_states_preserved') is not True
                   or row.get('original_micro_managers_preserved') is not True for row in timing['streams'])):fail()
    target=read(root/'qualification/raid-target-audit.json',expected=RAID_TARGET_AUDIT_SHA)
    if (target.get('kind')!='compiled_native_raid_target_derivation_v1'
            or target.get('base_package_sha256')!=TIMING_PACKAGE_SHA or target.get('package_sha256')!=PACKAGE_SHA
            or target.get('qualified_attack_tactic_sha256')!='8579781576b71f82ff944b609fe7b6d6b9458c8c9d4b82e072e75fd644509e41'
            or target.get('native_attack_executor_preserved') is not True
            or target.get('native_economic_target_preserved') is not True
            or target.get('specialized_unit_prerequisite_removed') is not True
            or {row['stream'] for row in target['streams']}!={'mod','mod_M','mod_L'}
            or any(row.get('all_game_object_assets_preserved') is not True
                   or row.get('original_autonomous_states_preserved') is not True
                   or row.get('original_micro_managers_preserved') is not True for row in target['streams'])):fail()
    visibility=verify_visibility(root,inventory,package_sha=PACKAGE_SHA,registry_sha=REGISTRY_SHA,
        package_report_sha=PACKAGE_REPORT_SHA)
    if visibility['provenance'].get('native_raid_derivation',{}).get('audit_sha256')!=RAID_AUDIT_SHA:fail()
    if visibility['provenance'].get('strategic_timing_derivation',{}).get('audit_sha256')!=TIMING_AUDIT_SHA:fail()
    if visibility['provenance'].get('native_raid_target_derivation',{}).get('audit_sha256')!=RAID_TARGET_AUDIT_SHA:fail()
    focus=read(root/'qualification/native7-trial.json')
    fields={'schema_version','kind','game_sha256','package_sha256','boundary','opponent_player_ids',
            'automatic_scheme','native_priority','maximum_game_seconds','maximum_wall_ms',
            'native_api','source_sha256','offline_report_sha256','native_field_verified',
            'product_acceptance_verified','formal_games','intent_contract','raid_derivation_sha256','participant_sets',
            'strategic_timing_derivation_sha256','raid_target_derivation_sha256'}
    if (type(focus) is not dict or set(focus)!=fields or type(focus['schema_version']) is not int
            or focus['schema_version']!=1 or focus['kind']!='native7_bounded_enemy_focus_trial'
            or focus['game_sha256']!=GAME_SHA or focus['package_sha256']!=PACKAGE_SHA
            or focus['boundary']!='native_ai_details_v1' or focus['opponent_player_ids']!=[4,5]
            or focus['participant_sets']!=[[3,4],[3,4,5]]
            or type(focus['automatic_scheme']) is not int or focus['automatic_scheme']!=2
            or type(focus['native_priority']) is not int or focus['native_priority']!=10
            or type(focus['maximum_game_seconds']) is not int or focus['maximum_game_seconds']!=60
            or type(focus['maximum_wall_ms']) is not int or focus['maximum_wall_ms']!=60000
            or focus['native_api']!={'set_priority':'0x8bdb50','automatic_scheme':'0x8bdbc0'}
            or focus['intent_contract']!='native7_independent_development_v1'
            or focus['raid_derivation_sha256']!=RAID_AUDIT_SHA
            or focus['strategic_timing_derivation_sha256']!=TIMING_AUDIT_SHA
            or focus['raid_target_derivation_sha256']!=RAID_TARGET_AUDIT_SHA
            or type(focus['native_field_verified']) is not bool
            or focus['product_acceptance_verified'] is not False
            or type(focus['formal_games']) is not int or focus['formal_games']!=0):fail()
    pins=focus['source_sha256']
    if (type(pins) is not dict or set(pins)!={'strategic_enemy_focus_lease_v1.h','enemy_focus_api.h'}
            or any(type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None for value in pins.values())):fail()
    offline=read(root/'qualification/native7-offline.json',expected=focus['offline_report_sha256'])
    if (offline.get('kind')!='native7_enemy_focus_offline_v1' or offline.get('passed') is not True
            or offline.get('game_access') is not False or type(offline.get('native_calls')) is not int
            or offline['native_calls']!=0 or offline.get('focus_source_sha256')!=pins):fail()
    return visibility


def trusted_pin():
    pin=os.environ.get('TACTICORE_RUNTIME_MANIFEST_SHA256')
    if type(pin) is not str or re.fullmatch('[0-9a-f]{64}',pin) is None:fail()
    return pin


def current():
    root=runtime_root();pin=trusted_pin()
    inventory,build,cap=verify_qualification(root,pin)
    return root,pin,inventory,build,cap


# The compiled enemy-focus lease and its selector snapshot (enemy_focus_api.h)
# accept exactly the combatants {3,4} or {3,4,5}, with 4 and 5 allied, and
# can raise the priority of player 4 or 5 only.
NATIVE7_FOCUS_PLAYER_IDS=tuple(FOCUS_GRAMMAR[action] for action in FOCUS_ACTIONS)


def native7_participants_supported(scenario):
    """Whether the Native7 focus lease can run beside this match's seats."""
    enemies=scenario.enemy_player_ids
    return (scenario.player_ids==tuple(sorted((scenario.model_player_id,)+enemies))
        and enemies in ((4,),(4,5)) and (len(enemies)==1 or scenario.enemies_allied)
        and all(scenario.player(index).kind=='native_ai' for index in enemies))


@dataclass(frozen=True)
class Native7Scope(UnifiedStrategicScopeV5):
    opponent_player_ids:tuple=(4,5)
    withheld_actions:tuple=()
    @property
    def focus_actions(self):
        """Focus intents for actual enemies the native lease can prefer."""
        players=[player for player in self.opponent_player_ids if player in NATIVE7_FOCUS_PLAYER_IDS]
        if len(players)<2:return ()
        return tuple(focus_actions_for(players))
    @property
    def maximum_model_input_bytes(self):return 32768
    @property
    def intent_contract(self):
        from .strategic_contract_v5 import INDEPENDENT_DEVELOPMENT_CONTRACT
        return INDEPENDENT_DEVELOPMENT_CONTRACT
    @property
    def minimum_model_game_seconds(self):return 0.
    native_transport_protocol:int=7
    native_transport_client:str='native7_transport.py'
    runtime_root:Path=Path()
    runtime_manifest_sha256:str=''
    @property
    def available_actions(self):
        actions=FLAG_ACTIONS+self.focus_actions+tuple(GATE_ACTIONS)
        return tuple(action for action in actions if action not in self.withheld_actions)
    def model_catalog_overrides(self):
        from .macro_group_role_contract import native6_strategic_catalog_overrides
        catalog=native6_strategic_catalog_overrides(self.required_origin_region)
        for entry in catalog.values():entry.pop('exclusive_with_other_construction_or_production',None)
        catalog['expand'].pop('native_expansion_interval_seconds',None)
        catalog['expand']['strategic_timing_owner']='agent'
        catalog['expand']['native_target_and_tactic_preserved']=True
        catalog['expand']['stock_conditions_preserved']=False
        catalog['expand']['native_operational_conditions_preserved']=True
        from native_unified_contract_v5 import additional_catalog
        catalog['raideconomy']=additional_catalog(('raideconomy',))['raideconomy']
        catalog['raideconomy'].update(native_executor='same_as_attackenemy',
            native_target_policy='safest_ground_harvester',specialized_unit_prerequisite=False,
            execution_policy='qualified_native_attack_executor')
        catalog['pauseconstruction']=dict(additional_catalog(('pauseconstruction',))['pauseconstruction'],
            scope='all_native_construction_including_economic_recovery')
        catalog['attackenemy']=dict(additional_catalog(('attackenemy',))['attackenemy'],
            target_policy='native_closest_ground_structure_preferred_enemy')
        for action in self.focus_actions:
            catalog[action]=dict(domain='enemy_focus',goal='prefer_public_enemy_player',
                target_player_id=FOCUS_GRAMMAR[action],maximum_duration_seconds=60,details_owner='native_ai',
                mission_success_verified=False)
        return catalog
    def public(self):
        return dict(super().public(),native_transport_protocol=7,bounded_field_trial=True,
                    intent_contract=self.intent_contract,maximum_model_input_bytes=self.maximum_model_input_bytes,
                    runtime_manifest_sha256=self.runtime_manifest_sha256,formal_natural_games=0,
                    product_model_and_client_acceptance_verified=False)


def header(value):
    if (type(value) is not dict or set(value)!={'schema_version','kind','runtime_root','runtime_manifest_sha256'}
            or type(value['schema_version']) is not int or value['schema_version']!=15 or value['kind']!=KIND):fail()


def load(path,session=None,*,_verified=None):
    value=read(path);header(value)
    root,pin,inventory,build,cap=current() if _verified is None else _verified
    if _verified is not None and (root!=runtime_root() or pin!=trusted_pin()):fail()
    if Path(value['runtime_root'])!=root or value['runtime_manifest_sha256']!=pin:fail()
    evidence=tuple(sorted([(str(root/name),digest) for name,digest in inventory['files'].items()]+[(str(root/'manifest.json'),pin)]))
    bundle=dict(value,build=str(root/'native/strategic7'),visibility=str(root/'qualification'),pins=dict(evidence))
    if session is None:
        # File qualification only; a session-bound scope comes from its scenario.
        return bundle,Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),(),evidence,
            runtime_root=root,runtime_manifest_sha256=pin)
    selected=native7_scenario(session,root)
    regions=tuple((action,region) for action,region in selected.regional_action_regions if action in ACTIONS)
    scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),regions,evidence,
        required_origin_region=selected.own_region,runtime_root=root,runtime_manifest_sha256=pin,
        opponent_player_ids=selected.enemy_player_ids,withheld_actions=selected.withheld_actions)
    return bundle,scope


def native7_scenario(session,root):
    try:selected=session_scenario(session,root,package_sha=PACKAGE_SHA)
    except ContractError:fail()
    if not native7_participants_supported(selected):fail()
    return selected


def create(path):
    root,pin,_,_,_=current()
    value=dict(schema_version=15,kind=KIND,runtime_root=str(root),runtime_manifest_sha256=pin)
    import json
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,sort_keys=True);stream.write('\n')
    return value


def admit_sdk(build,session):
    root,_,_,manifest,_=current()
    if Path(build)!=root/'native/strategic7':fail()
    # Descriptor qualification plus live map/own/origin verification remains
    # the Host's job; the SDK independently refuses a different package/owner.
    native7_scenario(session,root)
    return manifest
