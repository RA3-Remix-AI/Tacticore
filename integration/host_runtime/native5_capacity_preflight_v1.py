"""Capacity-only pre-Native rejection candidate. Not a provider/Native grant.

The private envelope is deliberately NOT an Audit/Native observation. It has
non-frame sentinels and capacity-only padding, is never returned, persisted or
sent, and can only be measured by the repository's pure encoders. Passing this
finite reserve does not guarantee every future lawful battlefield fits.
"""
from copy import deepcopy
from types import SimpleNamespace
import json
from pathlib import Path
import sys

# The desktop bridge runs isolated with only integration on its import path.
# These are fixed, qualified repository modules, never caller-supplied paths.
_ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(_ROOT/'strategy'),str(_ROOT/'agent_runtime/src')]

from engine import Snapshot
from macro_policy import project_strategy_defaults,ACTIONS
from .strategic_contract_v5 import FLAG_ACTIONS,GATE_ACTIONS,FOCUS_ACTIONS,RAID_ACTION,INDEPENDENT_DEVELOPMENT_CONTRACT
from http_adapter import system_prompt,ChatAdapter
from tacticore_agent_runtime.factory import NetworkBackend
from host_runtime.profiles import EffectiveProfile
from host_runtime.macro_delegation_boundary_v1 import restrict_context
from host_runtime.strategic_unified_feedback_v5 import compact_model_catalog

LIMIT=16384
MEMORY_RESERVE=1536
KIND='native5_capacity_only_v1'
LEGACY_ACTIONS=frozenset(FLAG_ACTIONS)|frozenset(GATE_ACTIONS)
NATIVE_TARGET_ACTIONS=(LEGACY_ACTIONS-{'deployattack'})|{'attackenemy'}
# Native7 currently executes focus only for public players 4 and 5.
NATIVE7_FOCUS_ACTIONS=frozenset(('focusenemy4','focusenemy5'))
ENEMY_FOCUS_ACTIONS=NATIVE_TARGET_ACTIONS|NATIVE7_FOCUS_ACTIONS
INDEPENDENT_ACTIONS=ENEMY_FOCUS_ACTIONS|{RAID_ACTION}
DUEL_ACTIONS=NATIVE_TARGET_ACTIONS|{RAID_ACTION}
# A scenario may withhold home-waypoint actions (see host_runtime.scenario).
HOME_WAYPOINT_ACTIONS=frozenset(('regroup','withdraw'))


def _grammar(actions):
    """(core grammar, focus actions) of a qualified catalog, or None.

    The core must be one fixed grammar, optionally without the home-waypoint
    actions. Enemy focus actions follow the match's actual enemies; at least
    two are needed for a choice to exist.
    """
    actions=frozenset(actions)
    focus=frozenset(action for action in actions if action in FOCUS_ACTIONS)
    core=actions-focus
    for base in (LEGACY_ACTIONS,NATIVE_TARGET_ACTIONS,DUEL_ACTIONS):
        if core in (base,base-HOME_WAYPOINT_ACTIONS) and (not focus or len(focus)>=2 and base!=LEGACY_ACTIONS):
            return base,focus
    return None

def _bytes(value):
    return len(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8'))

def _memory_reserve(actions):
    declaration=dict(strategy_id='00000000-0000-4000-8000-000000000001',objective='develop_technology',
        phase='execute',public_fact_refs=['capabilities.actions','own.credits','own.power_balance','own.role.infantry'],
        expected_observation='building_operational',
        continue_conditions=['prerequisite_met','resources_sufficient','capability_available'],
        replan_conditions=['effect_observed','goal_unobserved','facts_changed'],
        resource_priorities=dict(economy=.25,army=.25,tech=.25,reserve=.25))
    summary=dict(plan_id='p'*64,outcome='unknown',reason_code='r'*64,
        at_game_seconds='CAPACITY_ONLY_TIME',effect_verified=False)
    memory=dict(schema_version=1,fact_catalog={'capabilities.actions':actions,'own.credits':1000000000,
        'own.power_balance':None,'own.role.infantry':8192},current_strategy=dict(declaration,
        updated_game_seconds='CAPACITY_ONLY_TIME',last_outcome=summary),recent_outcomes=[],
        last_guard_reason='strategy_unknown_outcome',guard='active',missing_basis_refs=[],
        capacity_only_padding='')
    available=MEMORY_RESERVE-_bytes(memory)
    if available<0:raise ValueError('capacity_template_memory_exceeds_contract')
    memory['capacity_only_padding']='x'*available
    if _bytes(memory)!=MEMORY_RESERVE:raise ValueError('capacity_template_memory_size')
    return memory,declaration

def _capacity_envelope(effective,snapshot,catalog):
    # Do not construct a new BattleAgent from one possibly last-seen snapshot:
    # that would falsely reconstruct visibility history. This is an explicit
    # shape/size reserve, not an observed or executable request.
    value=dict(schema_version=1,agent_protocol='battle_agent_v1',commander_id=effective.profile_id,
        session_id=snapshot.session_id,player_id=snapshot.player_id,snapshot_id=snapshot.snapshot_id,
        game_time_seconds=snapshot.game_time_seconds,paused=snapshot.paused,
        allowed_production_focus=['native_baseline'],allowed_regions=[],
        working_memory=dict(current_strategy=None,verified_enemy_facts=[],
            own_combat_change=dict(since_game_seconds='CAPACITY_ONLY_TIME',previous_count=1000000,
                current_count=1000000,net_change=-1000000),
            economy=dict(credits=snapshot.credits,power_balance=snapshot.power_balance,
                queued_count=snapshot.queued_count,idle_producers=snapshot.idle_producers,own_roles=dict(snapshot.own_roles)),
            active_goals=[],recent_execution_feedback=[],failure_memory=[],
            compressed_history=dict(events_compacted=0,counts_by_kind={},
                completed_tasks=dict(build=0,raid=0,attack=0,combined_arms=0),
                failed_tasks=dict(build=0,raid=0,attack=0,combined_arms=0),last_compacted_game_time=None),
            battlefield=dict(viewer_player_id=3,visibility_verified=False,regions=[],contacts=[],formations=[]),
            unrestored_formation_count=0),
        delta=dict(since_snapshot_id=None,through_event_id=0,verified_events=[dict(
            kind='CAPACITY_ONLY_EVENT_NOT_OBSERVED',at_game_seconds='CAPACITY_ONLY_TIME',event_id=0)],older_events_compressed=0),
        pending_decisions=[dict(module='macro',question='choose_available_macro_policy')],
        capability_manifest=dict(build=dict(state='unavailable',reason_code='not_verified')),
        conversation_tail=[],context_limits=dict(maximum_bytes=LIMIT,regions_omitted=0,contacts_omitted=0,
            formations_omitted=0,details_truncated=True),control_mode='macro_native')
    actions=sorted(catalog)
    # The initial sampler only offers budget until the Native qualification.
    # Reserve the fixed next-round14-action syntax without asserting availability.
    value['allowed_macro_actions']=actions
    value['macro_policy_catalog']=compact_model_catalog(catalog)
    independent=snapshot.macro_intent_contract==INDEPENDENT_DEVELOPMENT_CONTRACT
    if independent:
        value['macro_intent_contract']=snapshot.macro_intent_contract
        value['context_limits']['maximum_bytes']=32768
    memory,_=_memory_reserve(actions)
    value['macro_strategy']=memory
    work=['reinforce','budgeteconomy','advanceconstruction','pauseproduction']
    if independent:work.append('expand')
    focus=sorted((action for action in actions if action in FOCUS_ACTIONS),key=lambda action:FOCUS_ACTIONS[action])
    if focus:
        work.append(focus[-1])
        value['working_memory']['match_state']=dict(schema_version=1,source='CAPACITY_ONLY_NOT_PUBLIC_MATCH',
            observed_frame='CAPACITY_ONLY_FRAME',opponent_player_ids=[FOCUS_ACTIONS[action] for action in focus],
            defeated_opponent_ids=[],opponents_allied=True)
    value['working_memory']['current_strategy']=dict(stance='defend',production_focus='native_baseline',
        economy_policy='expand_if_defensible',tech_policy='advance_if_affordable',
        budget=dict(economy=.25,army=.25,tech=.25,reserve=.25),
        execution_projection=dict(control_mode='macro_native',unit_operation_policy='native_ai',macro_actions=work,
            macro_production=None,effect_verified=False),objective_region=None,
        expires_at_game_seconds='CAPACITY_ONLY_TIME',origin='model',tactical_tasks=[],runtime_task=None,
        macro_actions=work)
    # Own presence is supplied by the normal request audit. Reserve its full
    # bounded shape, including the additional building-presence projection.
    from .macro_forces import MOBILE_ROLES,NAMED_UNITS,NAMED_BUILDINGS,MAX_REGIONS
    value['own_forces']=dict(source='CAPACITY_ONLY_NOT_OWN_OBSERVATION',observed_frame='CAPACITY_ONLY_FRAME',
        own_perspective=True,enemy_details_read=False,
        mobile_role_counts=dict.fromkeys(MOBILE_ROLES,8192),named_unit_counts=dict.fromkeys(NAMED_UNITS,8192),
        building_presence_counts=dict.fromkeys(NAMED_BUILDINGS,8192),
        economic_unit_presence_counts=dict(ore_collector=8192),income_verified=False,
        regions=[dict(region_id='region_127_127',mobile=8192,construction_yards=8192) for _ in range(MAX_REGIONS)],
        omitted_region_count=8192,unclassified_objects=8192,unlocated_classified_objects=8192,
        coverage='audited_template_presence_only',ready_for_combat_verified=False,recruitability_verified=False,
        unit_operation_policy='native_ai',presence_includes_unfinished_foundations=True,building_operation_verified=False)
    if independent:
        value['own_forces'].update(
            unit_type_counts=dict.fromkeys(('SovietAntiInfantryInfantry','SovietAntiVehicleInfantry',
                'SovietScoutInfantry','SovietAntiInfantryVehicle','SovietAntiAirShip_Ground',
                'SovietAntiVehicleVehicleTech1'),8192),
            economic_unit_regions=[dict(region_id='region_127_127',ore_collectors=8192,health_total=999999.) for _ in range(4)],
            omitted_economic_region_count=8192)
    # No optional battlefield/history/contacts are promised by this reserve.
    # This private sizing template never replaces the actual request context.
    for key in ('verified_enemy_facts','active_goals','recent_execution_feedback','failure_memory'):
        value['working_memory'][key]=[]
    value['working_memory']['battlefield'].update(regions=[],contacts=[],formations=[])
    value['conversation_tail']=[]
    targets=sorted({d['target_region'] for d in catalog.values() if 'target_region' in d})
    value['allowed_regions']=targets
    # Invalid source/frame sentinels make this explicitly unsuitable as real
    # Native telemetry. Expansion may remain observed beside four new domains.
    value['macro_unified_feedback']=dict(source='CAPACITY_ONLY_NOT_NATIVE_OBSERVATION',
        observed_frame='CAPACITY_ONLY_FRAME',observations=[dict(action=a,
            status='native_enemy_priority_observed' if a in FOCUS_ACTIONS else 'native_manager_state_observed' if a in GATE_ACTIONS else 'native_waiting_or_no_effect',
            observed_frame='CAPACITY_ONLY_FRAME',preference_active=False,movement_observed=False,
            state_already_satisfied=False) for a in dict.fromkeys([*work,'expand'])],completion_and_exclusive_causality_verified=False)
    value['macro_execution_feedback']=dict(source='CAPACITY_ONLY_NOT_NATIVE_OBSERVATION',status='native_budget_pending',
        actions=['budgeteconomy'],selected_policy=None,observed_frame='CAPACITY_ONLY_FRAME',native_effect_verified=False,
        payment_verified=False,production_queue_observed=False,idle_producers_observed=False,
        own_roles_coverage='audited_templates_only')
    value['macro_execution_feedback']['native_account_shares']=dict(zip(
        ('investment','special_operations','production','defense','technology','slush_fund'),[.1667]*5+[.1665]))
    return project_strategy_defaults(restrict_context(value))

def check_native5_capacity(effective,provider,public_snapshot,qualified_catalog):
    """Return metadata only. Pure/offline; no key/profile-store/transport needed.

    Caller supplies trusted effective style and qualified public catalogue.
    This function is NOT authority to attach, choose an action or send a model
    request. Both callers must retain all existing admission/prepared checks.
    """
    if type(effective) is not EffectiveProfile:raise ValueError('capacity_effective_profile_required')
    if provider not in ('DeepSeek','OpenAI','自定义'):raise ValueError('capacity_provider_required')
    snapshot=Snapshot.from_dict(deepcopy(public_snapshot))
    limit=32768 if snapshot.macro_intent_contract==INDEPENDENT_DEVELOPMENT_CONTRACT else LIMIT
    if (snapshot.player_id!=3 or snapshot.macro_control is None
            or type(qualified_catalog) is not dict
            or _grammar(qualified_catalog) is None
            or RAID_ACTION in qualified_catalog and snapshot.macro_intent_contract!=INDEPENDENT_DEVELOPMENT_CONTRACT):
        raise ValueError('capacity_native5_fixed_grammar_required')
    targets={d.get('target_region') for d in qualified_catalog.values() if type(d) is dict and 'target_region' in d}
    if any(type(d) is not dict for d in qualified_catalog.values()) or not targets<=set(snapshot.regions):
        raise ValueError('capacity_public_catalog_required')
    if any(d.get('domain')!=ACTIONS[a] or ACTIONS[a]=='deployment' and 'target_region' not in d
            for a,d in qualified_catalog.items()):
        raise ValueError('capacity_public_catalog_required')
    value=_capacity_envelope(effective,snapshot,deepcopy(qualified_catalog))
    profile=SimpleNamespace(personality=effective.personality,traits=effective.traits,provider=provider,model=effective.model)
    # __new__ intentionally avoids NetworkBackend's factory/SDK/client/credential
    # construction. input_size is the exact production pure estimator, unchanged.
    measure=NetworkBackend.__new__(NetworkBackend);measure._prompt=lambda c:system_prompt(profile,c)
    legacy=ChatAdapter.__new__(ChatAdapter);legacy.profile=profile;legacy.max_tokens=1536
    estimate=measure.input_size(value);encoded_size=legacy.input_size(value)
    fits=max(estimate,encoded_size,_bytes(value))<=limit
    return dict(kind=KIND,capacity_only=True,fits=fits,
        reason_code='model_context_capacity_ready' if fits else 'model_context_capacity_exceeded_shorten_style',
        maximum_bytes=limit,sdk_estimate_bytes=estimate,legacy_encoded_bytes=encoded_size,
        envelope_context_bytes=_bytes(value),reserved_memory_json_bytes=MEMORY_RESERVE,
        reserved_feedback_domains=6 if _grammar(qualified_catalog)[1] else 5,catalog_action_count=len(qualified_catalog),
        encoding_provider_capacity_assumption=provider,
        measurement='finite_conservative_core_reserve_not_actual_observation_or_future_request_guarantee',
        native_authority_granted=False,model_request_created=False)
