#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define T_MAGIC 0x4f415431u
#define T_MESSAGE (WM_APP+0x374)
#define T_CAP 4096
struct Event {uint32_t seq,kind,tag,frame,tick,thread,caller,team,owner,source,arg;float x,y,z;uint32_t target_id,damage_source;float damage_before,damage_after,damage_reported;uint32_t lease_stage,sm,sm_flags,state,state_id,path,holder,arg_shots,arg_source;float requested[3],effective[3];uint32_t stack_count,stack[12],stack_word_count,stack_words_address,stack_words[128];};
struct Tactical {uint32_t magic,version,pid,thread,owner,ai,personality,personality_id,player_template,start_low,start_high,session[4],commander[4],command[4],task[4],token,seq,unit,object_id,type_hash,update,logic,original_team,script_team,default_team,lease_frames,post_frames,target_unit,target_id,target_hash,target_owner,target_template,target_observed_frame,attack_calls,damage_count,weapon_entry,weapon_template,weapon_slot,weapon_ammo,last_ammo,last_limit,limit_before,limit_after,shot_samples,damage_hook_calls,visible_damage_calls;uint32_t commit_hook_calls,commit_visible_calls,commit_own_calls;float damage_total;float target[3];volatile LONG phase,stop_requested,active,count;uint32_t error,restore_mask,callback_thread,issued_frame,returned_frame,move_calls,detach_calls,return_calls,arrival_samples,native_move,native_attack,native_add,native_remove,owner_fail,lifecycle_fail,paused_samples,overflow,return_verified,return_pending;uint32_t stop_calls,private_stop_calls,private_stop_frame,attack_facade_calls,attack_private_calls,attack_issued_frame,stable_samples,stop_gate_samples,last_sample_frame,lease_stage,stop_failed,stop_issue_frame,post_actor_disposed,post_scene_changed;float stopped_xyz[3];Event events[T_CAP];};


