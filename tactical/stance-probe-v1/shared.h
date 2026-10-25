#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define T_MAGIC 0x53545031u
#define T_MESSAGE (WM_APP+0x38f)
#define T_PULSE_MESSAGE (WM_APP+0x390)
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
struct Event {
 uint32_t seq,kind,tag,frame,tick,thread,caller,self,arg,source,result,stage,sdk_calls,error;
 uint32_t explicit_stops,private_explicit_stops,automatic_stop2,private_automatic_stop2;
 Sample sample;
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
 Event events[T_CAP];
};
// phases: 0 queued, 5 installed, 1 borrowed, 3 terminal success, 4 terminal failure.
// stages: 0 admission, 1 initial Stop, 2 fixed hold, 3 cleanup Stop, 4 restore/Return, 5 terminal.
// kinds: 0 install, 1 borrowed, 3 unique-frame sample, 4 terminal,
// 10/11 Transfer pre/post; 12/13 add pre/post; 14/15 remove pre/post;
// 20/21 setter pre/post; 30/31 Stop facade pre/post; 32/33 Stop private pre/post;
// 40 initialStop3, 41 holdEnd, 42 cleanupStop3, 43 cleanupTimeout, 44 restoreBefore,45 restoreAfter,
// 46 poolBefore,47 poolAfter; 50 explicitSDK intent (arg=1 borrow/2 set/3 stop/4 cleanupStop/5 restore/6 return).
// tags: 0 unrelated/native,1 borrow,2 set,3 explicit initial Stop,4 cleanup Stop,5 restore,6 Return.
