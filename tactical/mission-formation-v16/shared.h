#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define T_MAGIC 0x4d463136u
#define T_MESSAGE (WM_APP+0x3a5)
#define T_PULSE_MESSAGE (WM_APP+0x3a6)
#define T_PULSE_PERIOD_MS 20u
#define T_CORE_PERIOD_MS 100u
#define T_PULSE_FALLBACK_MS 100u
#define T_PULSE_ACK_TIMEOUT_MS 1000u
#define T_PULSE_MAX_POSTS 20000u
#define T_CAP 8192
#define CRUMB_CAP 128
struct Support {uint32_t thing,id,hash,update,original_team,detach_calls,return_calls,returned,move_calls,native_move,native_attack,native_add,native_remove,native_stop,stop_calls,private_stop_calls,private_stop_frame,stable_samples,gate_samples,last_sample_frame,disposed_verified,absence_samples,last_absence_frame;float stopped_xyz[3];};
struct StanceRole {uint32_t module,vtable,backref,data,definition_list,definition_count,definition_entries[8],original_enum,set_calls,set_return,set_before,set_after,restore_calls,restore_return,restore_before,restore_after,restored,automatic_stop2,private_automatic_stop2,foreign_calls,capture_frame;};
struct Breadcrumb {uint32_t index,role,frame,published_seq,thing,object_id,type_hash,owner,update,holder,status_words[7],height_flags;float height,hp,xyz[3],path_distance;uint32_t mission_stage,surface_verified;};
struct MoveLineage {uint32_t generation,step,issued_frame,mission_stage,goal_kind,goal_event_seq,slot,input_command,output_command,copy_caller,unpack_caller,dispatch_caller,private_caller,delivered,role,invalid_reason,own_facade_seq,private_seq;float goal[3];uint32_t command[23],stored_before[24],stored_after[24],unpacked[23],observed_slot[24];uint32_t observed_this,observed_thing,observed_command;};
struct Event {uint32_t seq,kind,tag,frame,tick,thread,caller,team,owner,source,arg;float x,y,z;uint32_t target_id,damage_source;float damage_before,damage_after,damage_reported;uint32_t lease_stage,sm,sm_flags,state,state_id,path,holder,arg_shots,arg_source;float requested[3],effective[3];uint32_t stack_count,stack[12],stack_word_count,stack_words_address,stack_words[128];uint32_t active_weapon_entry,active_weapon_asset,active_weapon_ammo,status84;uint32_t unit_id,role,mission_stage,route_index,nav_step,target_visible,mission_deadline_frame,mission_reason,native_error;float own_hp,front_goal[3],support_goal[3],command_xyz[3],visible_target_xyz[3];uint32_t argument_path;float argument_limit;uint32_t planning_ready,route_ready,route_generation,route_commit_frame,planning_ready_frame,committed_route_count;float planning_front[3],planning_support[3],committed_route_xyz[3];Breadcrumb breadcrumb;uint32_t leader_role,follower_role,follow_active,follow_crumb_role,follow_crumb_index,motion_state,regroup_count,target_last_seen_frame,memory_wait_started;float actual_gap,last_seen_target[3],leader_hold_xyz[3];MoveLineage lineage;};
// MF16 immutable input and append-only runtime state. No model task is required to arm.
struct ProductionCommand13 {uint32_t seq,id[4],task[4],session[4],commander[4],hash,budget,reserve,expires,queue_limit,requested_tick,factory,factory_id,iface;};
struct ProductionReceipt13 {uint32_t updates,version;ProductionCommand13 command;uint32_t state,error,attempted,frame,queue_id,node,cost,quoted_cost,cash,liability,prior_count,preserved,paid,debit_count,payment_error,created,object,object_id,object_owner,object_hash,completed,completion_frame,live_samples,object_hp_bits,object_x_bits,object_y_bits,factory_x_bits,factory_y_bits;};
struct ProductionHeader13 {uint32_t magic,version,pid,thread,owner,ai,personality,personality_id,player_template,start_low,start_high,session[4],commander[4],total_budget,reserve_floor,min_interval,start_frame,phase,stop_requested,active,heartbeat,request_state;ProductionCommand13 request;uint32_t reply_index,reply_error,last_seq,last_frame,last_accepted_frame,spent,count,restore_mask,error,callback_thread;};
struct ReserveSample13 {
 uint32_t frame,thing,id,type_hash,owner,template_ptr,update,update_vtable,update_backref,team;
 uint32_t stance_module,stance_vtable,stance_backref,stance_data,stance;
 uint32_t stance_enum_list,stance_enum_count,stance_enum_entries[8];
 uint32_t sm,sm_owner,sm_flags,state,state_id,state_vtable,state_owner_sm,path,source;
 uint32_t child_sm,child_sm_vtable,child_state,child_state_id,child_state_vtable,child_state_owner_sm;
 uint32_t holder,status_words[7],height_flags;float height,hp,xyz[3];
 uint32_t auto_acquire,auto_acquire_flags_9e,auto_acquire_24,auto_acquire_28,auto_acquire_2c,auto_acquire_70;
};
struct PaidSlotInput13 {uint32_t role,command[4],task[4],seq,unit_hash,expected_cost,factory,factory_id,factory_template,factory_hash,iface;};
struct ControllerInput13 {
 uint32_t schema,controller[4],lease[4],formation[4],formation_version;
 uint32_t startup_deadline_frame,startup_wall_ms,reserve_duration_frames,lease_duration_frames;
 uint32_t producer_pid,producer_thread,producer_start_low,producer_start_high,producer_owner,producer_ai,producer_personality,producer_personality_id,producer_player_template;
 uint32_t producer_session[4],producer_commander[4],reserve_floor,total_paid_max,slot_count,allocation_scope,force_numerator,force_denominator;
 PaidSlotInput13 slots[2];
};
struct PaidSlotOutput13 {
 uint32_t stage,error,receipt_index,receipt_observed_frame,completion_observed_frame,receipt_version,thing,id,template_ptr,update,admitted_team;
 uint32_t cohort_count,cohort_first_frame,cohort_last_frame,cohort_reset_count,borrow_frame,ready_frame,hold_first_frame,hold_last_frame,hold_samples,hold_max_gap,hold_failed;
 uint32_t observed_path,observed_path_frame,brake_count,brake_frame,anchor_frame,move_issued_frame,stop_issued_frame,cleanup_started,restore_verified,return_verified,disposed_verified;
 float initial_factory_gap,proposal[3],initial_xyz[3],brake_xyz[3],anchor[3],max_hold_drift;
 ReserveSample13 admission_first,admission_last,last_sample;ProductionReceipt13 receipt;
 uint32_t proposal_reference_role,proposal_reference_frame,proposal_policy,proposal_reference_thing;float factory_radial_basis[3],first_role_actual_anchor[3];
};
// generation is the ONLY publisher word: 0 -> 2 once. Body is frozen on first observation.
// status/reason/ack_frame are Native outputs. Exact same body may read the ACK; no new target.
struct MissionCommitBody13 {
 uint32_t controller[4],lease[4],parent_command[4],parent_task[4],command[4],task[4],seq,formation[4],formation_version;
 uint32_t front_id,support_id,module,purpose,allocation_scope,force_numerator,force_denominator;
 uint32_t target_unit,target_id,target_hash,target_owner,target_template,target_observed_frame;
 float visible_target[3];uint32_t visibility_proof_sha256[8],threat_clear,threat_frame;
 uint32_t reserve_start_frame,reserve_deadline_frame,hard_deadline_frame,combat_frames,button,button_schema,command_set,digest_sha256[8];
};
struct MissionCommit13 {volatile uint32_t generation;MissionCommitBody13 body;uint32_t status,reason,ack_frame;};
struct ControllerState13 {
 uint32_t stage,error,reserve_start_frame,reserve_deadline_frame,hard_deadline_frame,lease_issued_frame,pair_ready_frame,mission_commit_frame,approach_frame;
 uint32_t clock_frozen,bound_mask,held_mask,ready_mask,channel_claimed,producer_snapshots,producer_retry_count,scope_verified,untasked_cleanup;
};
struct Tactical {uint32_t magic,version,pid,thread,owner,ai,personality,personality_id,player_template,start_low,start_high,session[4],commander[4],command[4],task[4],token,seq,unit,object_id,type_hash,update,logic,original_team,script_team,default_team,lease_frames,post_frames,target_unit,target_id,target_hash,target_owner,target_template,target_observed_frame,attack_calls,damage_count,weapon_entry,weapon_template,weapon_slot,weapon_ammo,last_ammo,last_limit,limit_before,limit_after,shot_samples,damage_hook_calls,visible_damage_calls;uint32_t commit_hook_calls,commit_visible_calls,commit_own_calls;float damage_total;float target[3];volatile LONG phase,stop_requested,active,count;uint32_t error,restore_mask,callback_thread,issued_frame,returned_frame,move_calls,detach_calls,return_calls,arrival_samples,native_move,native_attack,native_add,native_remove,owner_fail,lifecycle_fail,paused_samples,overflow,return_verified,return_pending;uint32_t stop_calls,private_stop_calls,private_stop_frame,attack_facade_calls,attack_private_calls,attack_issued_frame,stable_samples,stop_gate_samples,last_sample_frame,lease_stage,stop_failed,stop_issue_frame,post_actor_disposed,post_scene_changed;float stopped_xyz[3];uint32_t button,button_schema,command_set,initial_weapon_asset,initial_weapon_entry,toggle_calls,toggle_hook_calls,toggle_frame,ak_samples,last_ak_frame,prepare_reconstituted_stops,observed_weapon_asset,observed_weapon_entry,observed_ammo,total_private_stops,prepare_gate_frame;Support support;uint32_t route_count,mission_stage,route_index,nav_step,nav_frame,nav_arrivals,nav_paired,nav_last_frame,approach_completed,retreat_completed,combat_started,retreat_started,mission_deadline_frame,combat_frames,retreat_reason,native_stop,front_retreat_arrivals,support_retreat_arrivals,combat_geometry_samples,retreat_requested,heartbeat_tick,front_disposed_verified,front_absence_samples,front_last_absence_frame,cleanup_started,cleanup_front_stopped,cleanup_support_stopped;float route[16][3],safe_front[3],safe_support[3],front_goal[3],support_goal[3],front_hold[3],support_hold[3];uint32_t planning_ready,route_ready,planning_ready_frame,planning_ready_tick,route_generation,route_committed_generation,route_commit_frame,planning_timeout_ms,planning_threat_clear,planning_threat_frame,planning_failed;float submitted_front[3],submitted_support[3],planning_front[3],planning_support[3];uint32_t leader_role,follower_role,follow_crumb_role,follow_crumb_index,follow_active,follow_started,follow_last_progress,follow_last_frame,follow_arrivals,lead_move_started,leader_hold_started,leader_hold_settled,regroup_count,leader_move_count,follow_move_count,crumb_count[2],crumb_reject_count,trail_phase,home_arrivals[2],home_last_frame[2],target_last_seen_frame,memory_wait_started,memory_ttl_frames,approach_limit,retreat_limit,hold_timeout_frames,motion_state,motion_frame,motion_last_tick,role_motion_mode[2],hold_repair_count;float last_seen_target[3],leader_hold_xyz[3],actual_gap,initial_target_distance,approach_distance,front_travel,support_travel,retreat_displacement[2],role_last_xyz[2][3],role_crumb_distance[2];Breadcrumb crumbs[2][CRUMB_CAP];volatile uint32_t pulse_requested,pulse_acknowledged;StanceRole stances[2];ControllerInput13 controller_input;ControllerState13 controller;PaidSlotOutput13 slots[2];MissionCommit13 mission_commit;Event events[T_CAP];};


