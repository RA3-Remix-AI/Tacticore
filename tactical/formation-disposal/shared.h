#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define T_MAGIC 0x464f5231u
#define T_MESSAGE (WM_APP+0x36c)
#define T_CAP 4096
struct Unit {uint32_t thing,id,hash,update,original_team;float initial[3],goal[3],hold[3];uint32_t detach_calls,move_calls,return_calls,arrivals,returned,native_move,native_attack,native_add,native_remove,disposed_verified,disposed_reason,disposed_frame,disposed_list_count;float disposed_hp;};
struct Event {uint32_t seq,kind,tag,stage,frame,tick,thread,caller,unit_id,team,owner,source,arg;float x,y,z;};
struct Tactical {uint32_t magic,version,pid,thread,owner,ai,personality,personality_id,player_template,start_low,start_high,session[4],commander[4],command[4],task[4],token,seq,logic,script_team,default_team,lease_frames,post_frames;Unit units[2];volatile LONG phase,stop_requested,active,count;uint32_t error,restore_mask,callback_thread,issued_frame,returned_frame,stage,stage_frame,goal_samples,support_hold_samples,front_arrival_frame,support_issued_frame,overflow,paused_samples,return_pending;float min_spacing,max_spacing;Event events[T_CAP];};
