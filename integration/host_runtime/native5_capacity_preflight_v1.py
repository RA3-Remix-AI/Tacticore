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
from .strategic_contract_v5 import STRATEGIC_ACTIONS,GATE_ACTIONS
from http_adapter import system_prompt,ChatAdapter
from tacticore_agent_runtime.factory import NetworkBackend
from host_runtime.profiles import EffectiveProfile
from host_runtime.macro_delegation_boundary_v1 import restrict_context
from host_runtime.strategic_unified_feedback_v5 import compact_model_catalog

LIMIT=16384
MEMORY_RESERVE=1536
KIND='native5_capacity_only_v1'

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
    actions=sorted(STRATEGIC_ACTIONS)
    # The initial sampler only offers budget until the Native qualification.
    # Reserve the fixed next-round14-action syntax without asserting availability.
    value['allowed_macro_actions']=actions
    value['macro_policy_catalog']=compact_model_catalog(catalog)
    memory,declaration=_memory_reserve(actions)
    value['macro_strategy']=memory
    work=['expand','budgeteconomy','advanceconstruction','pauseproduction']
    value['working_memory']['current_strategy']=dict(stance='defend',production_focus='native_baseline',
        economy_policy='expand_if_defensible',tech_policy='advance_if_affordable',
        budget=dict(economy=.25,army=.25,tech=.25,reserve=.25),
        execution_projection=dict(control_mode='macro_native',unit_operation_policy='native_ai',macro_actions=work,
            macro_production=None,effect_verified=False),objective_region=None,
        expires_at_game_seconds='CAPACITY_ONLY_TIME',origin='model',tactical_tasks=[],runtime_task=None,
        macro_actions=work,macro_strategy=declaration)
    # No optional battlefield/history/contacts are promised by this reserve.
    # This private sizing template never replaces the actual request context.
    for key in ('verified_enemy_facts','active_goals','recent_execution_feedback','failure_memory'):
        value['working_memory'][key]=[]
    value['working_memory']['battlefield'].update(regions=[],contacts=[],formations=[])
    value['conversation_tail']=[]
    targets=sorted({d['target_region'] for d in catalog.values() if 'target_region' in d})
    value['allowed_regions']=targets
    # Invalid source/frame sentinels make this explicitly unsuitable as real
    # Native telemetry. Four bounded model feedback rows are reserved, only.
    value['macro_unified_feedback']=dict(source='CAPACITY_ONLY_NOT_NATIVE_OBSERVATION',
        observed_frame='CAPACITY_ONLY_FRAME',observations=[dict(action=a,
            status='native_manager_state_observed' if a in GATE_ACTIONS else 'native_waiting_or_no_effect',
            observed_frame='CAPACITY_ONLY_FRAME',preference_active=False,movement_observed=False,
            state_already_satisfied=False) for a in work],completion_and_exclusive_causality_verified=False)
    value['macro_execution_feedback']=dict(source='CAPACITY_ONLY_NOT_NATIVE_OBSERVATION',status='native_budget_pending',
        actions=['budgeteconomy'],selected_policy=None,observed_frame='CAPACITY_ONLY_FRAME',native_effect_verified=False,
        payment_verified=False,production_queue_observed=False,idle_producers_observed=False,
        own_roles_coverage='audited_templates_only')
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
    if (snapshot.player_id!=3 or snapshot.macro_control is None
            or type(qualified_catalog) is not dict or set(qualified_catalog)!=set(STRATEGIC_ACTIONS)):
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
    fits=max(estimate,encoded_size,_bytes(value))<=LIMIT
    return dict(kind=KIND,capacity_only=True,fits=fits,
        reason_code='model_context_capacity_ready' if fits else 'model_context_capacity_exceeded_shorten_style',
        maximum_bytes=LIMIT,sdk_estimate_bytes=estimate,legacy_encoded_bytes=encoded_size,
        envelope_context_bytes=_bytes(value),reserved_memory_json_bytes=MEMORY_RESERVE,
        reserved_feedback_domains=4,catalog_action_count=14,
        encoding_provider_capacity_assumption=provider,
        measurement='finite_conservative_core_reserve_not_actual_observation_or_future_request_guarantee',
        native_authority_granted=False,model_request_created=False)
