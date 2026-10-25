#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define T_MAGIC 0x52535636u
#define T_MESSAGE (WM_APP+0x39d)
#define T_PULSE_MESSAGE (WM_APP+0x39e)
#define T_PULSE_PERIOD_MS 20u
#define T_PULSE_FALLBACK_MS 100u
#define T_PULSE_ACK_TIMEOUT_MS 1000u
#define T_CAP 1024
struct Sample {
 uint32_t frame,thing,id,type_hash,owner,template_ptr,update,update_vtable,update_backref,team;
 uint32_t stance_module,stance_vtable,stance_backref,stance_data,stance;
 uint32_t stance_enum_list,stance_enum_count,stance_enum_entries[8];
 uint32_t sm,sm_owner,sm_flags,state,state_id,state_vtable,state_owner_sm,path,source;
 uint32_t child_sm,child_sm_vtable,child_state,child_state_id,child_state_vtable,child_state_owner_sm;
 uint32_t holder,status_words[7],height_flags;
 float height,hp,xyz[3];
 uint32_t auto_acquire,auto_acquire_flags_9e,auto_acquire_24,auto_acquire_28,auto_acquire_2c,auto_acquire_70;
};
// Design-stage ABI; no executable Native2/SDK installation is authorized by this header.
// Typed alias of Event.move on73/74/75. These are actual read words, not Move authority.
struct TeamProof {uint32_t magic,team_before,definition_before,owner_before,team_after,definition_after,owner_after,sample_frame,previous_team,previous_count;};
struct MoveProof {
 uint32_t goal_pointer,goal_bits[3],path,limit_bits,intent_seq,facade_seq,generation,flags;
};
struct RallyState {
 // immutable input, source-joined to the original producer receipt/raw sidecar
 uint32_t factory_address,factory_id,factory_owner,factory_template,factory_type_hash,factory_source_frame,factory_x_bits,factory_y_bits;
 // output: actual stopped own point, normalized sideward direction, proposed goal
 float proposal_origin[3],proposal_direction[2],goal[3];
 uint32_t proposal_frame,arrival_samples,last_arrival_frame,rally_issue_frame,rally_reached_frame,rally_stop_verified,rally_stop_frame,move_intents,move_facade_entries,move_private_entries,foreign_move_entries,move_scope_open,move_generation,move_intent_seq;
};
struct Event {
 uint32_t seq,kind,tag,frame,tick,thread,caller,self,arg,source,result,stage,sdk_calls,error;
 uint32_t explicit_stops,private_explicit_stops,automatic_stop2,private_automatic_stop2;
 Sample sample;
 MoveProof move;
};
struct AnchorState {
 uint32_t candidate_samples,last_candidate_frame,candidate_frame,commit_frame;
 uint32_t initial_outside_inner_zone,boundary_crossed,proposal_reached,admission_age_first,admission_age_last;
 float initial_factory_gap,candidate_xyz[3],actual_anchor[3],last_candidate_xyz[3],proposal_distance;
};
struct Probe {
 uint32_t magic,version,pid,thread,start_low,start_high,session[4],commander[4],command[4],task[4],token,seq;
 uint32_t logic,owner,ai,personality,personality_id,player_template;
 uint32_t thing,object_id,type_hash,template_ptr,update,stance_module,original_team,script_team,default_team;
 uint32_t observed_frame,threat_frame,threat_clear,expires_frame,test_stance;
 volatile LONG phase,stop_requested,active,count;
 uint32_t error,restore_mask,callback_thread,stage,issued_frame,returned_frame;
 uint32_t sdk_calls,detach_calls,return_calls,return_verified,stance_calls,explicit_stops,private_explicit_stops;
 uint32_t automatic_stop2,private_automatic_stop2,private_stop_frame,original_stance,stance_changed,stance_restored;
 uint32_t initial_stop_verified,cleanup_stop_verified,hold_verified,hold_started,hold_finished,cleanup_started;
 uint32_t stable_samples,last_sample_frame,stop_issue_frame,paused_samples,overflow,heartbeat_tick;
 uint32_t hold_samples,hold_max_gap,hold_missing_frames,hold_first_frame,hold_last_frame;
 uint32_t restore_before_enum,restore_after_enum,pool_before_enum,pool_after_enum,disposed,scene_changed;
 uint32_t pulse_requested,pulse_acknowledged;
 float stopped_xyz[3],hold_anchor[3],max_hold_drift;
 Sample initial_sample;
 uint32_t production_command[4],production_task[4],production_seq,production_queue_id,production_birth_frame,production_paid,production_receipt_sha256[8];
 uint32_t admission_samples,admission_first_frame,admission_last_frame,admission_verified,admission_max_gap;
 Sample admission_first_sample;
 RallyState rally;
 AnchorState anchor;
 Event events[T_CAP];
};
// Reserve3 canonical: actual outer-anchor objective. No installed field capability yet. Existing Reserve1 common field offsets remain.
// stage0 admission,1 initialStop,6 rallyMove,7 rallyStop,2 hold,3 cleanup,4 restoreReturn,5 terminal.
// new70 candidate sample,71 frozen candidate3,72 actual anchor committed after Stop8 realStop3; kind63 is optional proposal-only15x3 diagnostic.
// new kind69 actual factory 10-word snapshot in MoveProof (not Move flags); new kinds62 proposal,63 actual arrival3,64/65 MoveFacade pre/post,66/67 privateMove pre/post,68 rallyStop3.
// SDK intent order1,2,3,7,8,4,5,6; tags7=rallyMove,8=rallyStop. Eight explicit calls maximum.

// Reserve4:73 stable owned team candidate (result=count BEFORE adding);74 team-only reset1stable change/2within-sample race;75 hard team rejection3zero/4script/5owner.
