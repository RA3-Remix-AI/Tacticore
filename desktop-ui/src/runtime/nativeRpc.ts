import { invoke, isTauri } from '@tauri-apps/api/core';

export const nativeAvailable = () => isTauri();
export type HostOperation = 'profiles.list' | 'profiles.get' | 'profiles.save' | 'connections.list'
  | 'session.inspect' | 'session.discover' | 'session.prepare' | 'run.resume' | 'run.check' | 'run.start' | 'run.status' | 'run.stop' | 'diagnostics.export';
export class HostError extends Error {
  constructor(public readonly code: string, public readonly requestId: string) { super(code); }
}
export type InvokeHost = (command: string, args: {request: object}) => Promise<unknown>;
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const codePattern = /^[a-z][a-z0-9_]{0,100}$/;

/** One invocation per request. Uncertain transport results are never retried. */
export function createHostRpc(call: InvokeHost = invoke) {
  return async function request<T extends object>(operation: HostOperation, args: object,
    requestId: string = crypto.randomUUID()): Promise<T> {
    if (!uuid.test(requestId)) throw new HostError('invalid_request_id', requestId);
    let response: unknown;
    try {
      response = await call('host_request', {request: {schema_version: 1, request_id: requestId, operation, args}});
    } catch (error) {
      // Rust emits fixed codes; arbitrary platform exception messages never enter UI/logs.
      const code = typeof error === 'string' && codePattern.test(error) ? error : 'delivery_unknown';
      throw new HostError(code, requestId);
    }
    if (!object(response) || response.schema_version !== 1 || response.request_id !== requestId || typeof response.ok !== 'boolean')
      throw new HostError('delivery_unknown', requestId);
    if (!response.ok) {
      const code = object(response.error) && typeof response.error.code === 'string' && codePattern.test(response.error.code)
        ? response.error.code : 'bridge_operation_failed';
      throw new HostError(code, requestId);
    }
    if (!object(response.result)) throw new HostError('delivery_unknown', requestId);
    return response.result as T;
  };
}

export const hostRpc = createHostRpc();

export type MacroStrategyObjective='economic_stability'|'expand_economy'|'develop_technology'|'build_force'|'scout'|'pressure'|'defend_base'|'recover_force'|'hold';
export type MacroStrategyPhase='prepare'|'execute'|'assess'|'wait';
export type MacroStrategyExpected='resource_recovery'|'construction_queue'|'building_operational'|'production_queue'|'unit_completed'|'technology_unlocked'|'new_lawful_contact'|'force_region_change'|'threat_reduced'|'no_change';
export type MacroStrategyOutcomeKind='pending'|'effect_observed'|'no_effect'|'failed'|'cancelled'|'expired'|'replaced'|'unknown';
export interface MacroStrategyOutcome {
  plan_id:string;outcome:MacroStrategyOutcomeKind;reason_code:string;at_game_seconds:number;effect_verified:boolean;
}
export interface MacroStrategyDeclaration {
  strategy_id:string;objective:MacroStrategyObjective;phase:MacroStrategyPhase;public_fact_refs:string[];
  expected_observation:MacroStrategyExpected;continue_conditions:string[];replan_conditions:string[];
  resource_priorities:Record<'economy'|'army'|'tech'|'reserve',number>;
  updated_game_seconds:number;last_outcome:MacroStrategyOutcome|null;
}
export interface MacroStrategyPublicState {
  schema_version:1;kind:'macro_strategy_public_state';current_strategy:MacroStrategyDeclaration|null;
  recent_outcomes:MacroStrategyOutcome[];last_guard_reason:string|null;stopped:boolean;
  unknown_command_count:number;unreleased_command_count:number;
}

export type MacroExpansionAction='buildpower'|'buildbarracks'|'buildfactory'|'buildrefinery'|'buildbattlelab'|'producesickle'|'producebullfrog';
export interface MacroExpansionAvailabilityRecord {
  schema_version:1;kind:'macro_expansion_availability_record_v1';
  entries:{action:MacroExpansionAction;reason:'insufficient_funds'|'producer_unready'|'previous_request_pending'|'unverified'}[];
  record_only:true;dispatch_authorized:false;automatic_retry:false;payment_verified:false;global_native_release_verified:false;
}
export interface MacroExpansionRecord {
  source:'native_macro_expansion_observation';action:MacroExpansionAction;domain:'construction'|'production';
  status:'native_queue_observed'|'native_producer_unavailable'|'native_expansion_pending';
  release_reason:null|'queue_target_observed'|'producer_unavailable'|'prerequisite_changed'|'expired'|'stopped';
  additional_count_requested:1;observed_new_queue_count:number;new_own_target_observations:number;
  native_completion_edges_observed:number;fully_paid_queue_observations:number;additional_queue_observations_after_window:number;
  available_producer_count:number;positive_native_build_state_observed:boolean;policy_released:boolean;
  builder_frame:number;own_census_frame:number;observed_queue_cost_sum:number;observed_paid_field_sum:number;
  count_control_basis:'new_native_queue_acceptances';overall_production_permitted:null;
  cost_observation_semantics:'last_observed_fields_per_queue_not_total_cash_outflow';resource_reservation_verified:false;
  budget_hard_cap_verified:false;exact_queue_to_object_link_verified:false;payment_verified:false;unit_exit_verified:false;
  technology_unlock_verified:false;exclusive_macro_attribution_verified:false;automatic_retry_allowed:false;
  unit_operation_policy:'native_ai';record_only:true;global_native_release_verified:false;
}
export type MacroAdmissionStatus='reserved'|'delivering'|'acknowledged'|'preference_cleared'|'closed_after_current_state_reconciliation'|'aborted_before_delivery'|'unknown';
export interface MacroAdmissionRecord {
  source:'active_preference_admission_buffer_v4';schema_version:4;status:MacroAdmissionStatus;active_buffer_amount:number;
  known_ack:boolean;independent_clear:boolean;reconciled_credits:number|null;reconciled_production_upgrade_debt_upper:number|null;
  reconciled_frames:[number,number]|null;unverified_outcomes:['actual_cash_payment','refund','no_queue_ever_accepted','exclusive_enqueue_causality','latent_work_cancelled'];
  excluded_spending:['future_unaccepted_work_including_prior_selected_latent','future_native_autonomous_repair_and_ability_spending'];
  hard_spending_cap_verified:false;dispatch_authorized:false;next_requires_fresh_cost_and_state:true;automatic_retry:false;
  reconciliation_waiting:boolean;record_only:true;global_native_release_verified:false;
}
