"""Unwired Host delta for CPU review; NEVER imported by product entrypoints.

Only the new pure decision is authoritative about whether this optional path
may be considered. Existing sampler/transport/core validation stays upstream.
This deliberately has no implementation that obtains or retries a native read.
"""
from host_runtime.macro_optional_builder_gap_v1 import assess_optional_builder_gap_v1
from host_runtime.macro_scouting import MacroScoutingController
from host_runtime.macro_regions import MacroRegionalController


def candidate_production_tick_v1(host,native,*,gate_arguments,update_capabilities=True):
    gap=assess_optional_builder_gap_v1(native,strategic_only=host.strategic_only,**gate_arguments)
    seconds=max(host.latest['game_time_seconds'],max(gap.observed_frames)/15)
    # This is the same original clock/expiry path; no deadline is extended.
    host.controller.tick(seconds)
    if isinstance(host.controller,MacroScoutingController):host.controller.observe_snapshot(host.latest)
    host.controller.refresh(native)
    # Explicitly invalidate precision decorations; no empty synthetic builder.
    host.controller.construction_candidate=None
    host.last_infrastructure=None;host.last_production_feedback=None;host.last_construction_feedback=None
    host.last_expansion_feedback=None;host.last_resource_feedback=None
    # This generic existing field carries timing only. Label its new source
    # explicitly; it never becomes builder or financial admission evidence.
    host.capability_sample_frames=gap.observed_frames
    host.capability_sample_kind=gap.kind
    if getattr(host,'strategy_runtime',None) is not None:
        host.strategy_runtime.observe(host.controller,gate_arguments['native_state'],seconds)
    host.controller.tick(seconds)
    if update_capabilities:host.update_macro_control(seconds)
    if isinstance(host.controller,MacroScoutingController):
        host.last_scouting_feedback=host.controller.scouting_feedback()
        if host.last_scouting_feedback:host.event('macro_scouting_feedback',**host.last_scouting_feedback)
    if isinstance(host.controller,MacroRegionalController):
        host.last_regional_feedback=host.controller.regional_feedback()
        if host.last_regional_feedback:host.event('macro_regional_feedback',**host.last_regional_feedback)
    host.event('macro_optional_builder_unknown',sample_kind=gap.kind,reason_code=native['build_observation_error'],
        builder_status='unknown',queue_effect_verified=False,detailed_action_granted=False)
    return True
