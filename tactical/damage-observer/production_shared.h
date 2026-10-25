#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define OBS_MESSAGE (WM_APP+0x366)
#define OBS_MAGIC 0x444d4731u
#define OBS_CAPACITY 1024
struct BuildEvent {uint32_t tick,thread,frame,body,thing,object_id,owner,source_id,caller,info;float before,after,calculated,reported;uint32_t info_kind,complete;};
struct ObserverState {uint32_t magic,version,pid,seconds,window_thread,callback_thread,start_tick,stop_tick;volatile LONG request,ack,state,stop_owner,active,total_calls,event_count;uint32_t error;BOOL restore_verified;BuildEvent events[OBS_CAPACITY];};
