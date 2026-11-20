/** Shapes returned by the host RPC, shared by the Windows client screens. */
import type {CommanderChoice, Personality} from './commanders';
import type {MacroAdmissionRecord, MacroExpansionRecord, MacroStrategyPublicState} from './nativeRpc';
import type {StrategicClientRecord} from './strategicCommandView';
import type {ModelConsumptionReceipt} from './modelCallView';
import type {AppliedReceipt} from './applicationView';
import type {NativeEvent} from './nativeProcess';

/** A saved AI profile. Older backends send doctrine/custom_traits/preferences; newer ones the commander fields. */
export type Draft = {
  schema_version: 1; profile_id: string; name: string; revision: number; connection_id: string; model: string;
  doctrine?: string; custom_traits?: string; preferences?: unknown;
  commander_id?: CommanderChoice; personality?: Personality; voice_note?: string;
};

export type Profile = {
  profile_id: string; name: string; revision: number; model: string; connection_id: string; draft: Draft; state: string;
  validation: {ok: boolean; reason_code: string};
  effective: null | {
    effective_hash: string; traits: string; traits_bytes: number;
    // Removed with the five-axis style model; older hosts may still send it.
    axis_support?: Record<string, {execution_status: string}>;
  };
};

export type Connection = {
  id: string; name: string; provider: string; endpoint: string; model: string;
  credential_check: string; credential_configured: boolean | null; remember_key: boolean;
};

export type Session = {id: string; map: string; player_name: string; faction: string};
export type Limits = {production_total_budget: number; reserve_floor: number; max_command_budget: number};

export type Capabilities = {
  control_mode?: string; native_macro?: boolean; available_macro_actions?: string[]; base_defense_granted?: boolean;
  group_roles_granted?: string[]; supported_units?: string[]; supported_foci?: string[];
  tactics_supported?: boolean; runtime_tactical_supported?: boolean;
};

export type Ready = {
  ready: boolean; session_id: string; ready_token: string; expires_at: number; reason_code?: string;
  session?: Session; execution_limits?: Limits; capabilities?: Capabilities;
};

export type Task = {
  task_id: string; module?: string; purpose?: string; status?: string; reason_code?: string; stage?: string;
  budget?: {fraction: number}; expires_at_game_seconds?: number; physical_home?: boolean; control_released?: boolean;
};

export type Run = {
  run_id: string; session_id: string; state: string; reason_code?: string; status_age_ms?: number; status_stale?: boolean;
  host_process_alive?: boolean; profile_id?: string; profile_revision?: number; effective_hash?: string;
  native_release_verified?: boolean; no_native_execution_started?: boolean;
  profile_application?: AppliedReceipt; profile_consumption?: ModelConsumptionReceipt;
  session?: Session; execution_limits?: Limits; capabilities?: Capabilities;
  latest_snapshot?: {game_time_seconds?: number; paused?: boolean; resources?: {credits: number}};
  execution?: {remaining_budget?: number; executor_connected?: boolean; enabled?: boolean};
  metrics?: {requests?: number; accepted?: number};
  task_counters?: {dispatches?: number; started?: number; completed?: number; failed?: number; blocked?: number};
  tasks?: Task[]; tasks_cursor?: {total_count: number; truncated: boolean}; events?: NativeEvent[];
  current_plan?: {macro_actions?: string[]; macro_production?: {action: string; additional_count: number}};
  macro_feedback?: {status: string; selected_policy: string | null};
  macro_strategy?: MacroStrategyPublicState; macro_strategy_unavailable?: boolean;
  strategic_client?: StrategicClientRecord; strategic_client_unavailable?: boolean;
  macro_unified_feedback?: unknown; macro_unified_feedback_unavailable?: boolean;
  macro_expansion_feedback?: MacroExpansionRecord; macro_expansion_feedback_unavailable?: boolean;
  macro_resource_feedback?: MacroAdmissionRecord; macro_resource_feedback_unavailable?: boolean;
  macro_expansion_availability?: unknown; macro_expansion_availability_unavailable?: boolean;
  macro_scouting_feedback?: {active_native_tactics: number; moved_native_groups: number; new_legal_contacts_since_intent: number; policy_released: boolean};
  local_preparation?: {state?: string; reason_code?: string; paid_units_available?: number};
  events_cursor?: {first_seq: number | null; last_seq: number | null; total_count: number; overflow: number; truncated: boolean};
};
