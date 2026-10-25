#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define OBS_MAGIC 0x52414f42u
#define OBS_MESSAGE (WM_APP+0x38b)
#define OBS_CAPACITY 2048
struct MoveEvent { uint32_t tick,thread,source,ai,caller;float xyz[3];uint32_t stack_count,stack[8]; };
struct ObserverState {
 uint32_t magic,version,pid,seconds,window_thread;
 volatile LONG request,ack,state,active,total_moves,ai_moves,event_count,stop_owner;
 uint32_t callback_thread,start_tick,stop_tick,restore_verified,error;
 MoveEvent events[OBS_CAPACITY];
};
