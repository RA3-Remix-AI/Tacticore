#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define OBS_MESSAGE (WM_APP+0x32d)
#define OBS_MAGIC 0x50524f44u
#define OBS_CAPACITY 1024
struct BuildEvent {uint32_t tick,thread,interface_address,factory,owner,template_address,template_hash,caller,args[7],queue_before,queue_after,return_value,matched_node,node_cost;uint32_t stack_count,stack[8];};
struct ObserverState {uint32_t magic,version,pid,seconds,window_thread,callback_thread,start_tick,stop_tick;volatile LONG request,ack,state,stop_owner,active,total_calls,event_count;uint32_t error;BOOL restore_verified;BuildEvent events[OBS_CAPACITY];};
