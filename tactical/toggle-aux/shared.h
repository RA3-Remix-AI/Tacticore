#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define T_MAGIC 0x57544731u
#define T_MESSAGE (WM_APP+0x377)
#define T_CAP 4096
struct Event {uint32_t seq,kind,tag,frame,tick,thread,caller,team,owner,source,arg;float x,y,z;uint32_t sm,sm_flags,state,state_id,path,path_node;float requested[3],effective[3],path_xy[2];uint32_t weapon_entry,weapon_asset,weapon_ammo,status84;int32_t cash;};
struct Tactical {uint32_t magic,version,pid,thread,owner,ai,personality,personality_id,player_template,start_low,start_high,session[4],commander[4],command[4],task[4],token,seq,unit,object_id,type_hash,update,logic,original_team,script_team,default_team,lease_frames,post_frames;float target[3];volatile LONG phase,stop_requested,active,count;uint32_t error,restore_mask,callback_thread,issued_frame,returned_frame,move_calls,detach_calls,return_calls,arrival_samples,native_move,native_attack,native_add,native_remove,owner_fail,lifecycle_fail,paused_samples,overflow,return_verified,return_pending;uint32_t stop_calls,private_stop_calls,private_stop_frame,move_issued_frame,stable_samples,stop_gate_samples,last_sample_frame;float stopped_xyz[3];uint32_t button,button_schema,command_set,initial_weapon_asset,initial_weapon_entry,toggle_calls,toggle_hook_calls,toggle_frame,ak_samples,last_ak_frame,observed_weapon_asset,observed_weapon_entry,observed_ammo,cash_before,cash_after,button_result,post_actor_disposed;Event events[T_CAP];};
