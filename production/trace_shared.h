#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define TRACE_MESSAGE (WM_APP+0x32f)
#define TRACE_MAGIC 0x50545243u
#define TRACE_CAP 16384
enum Field {KIND,SEQ,WALL_MS,FRAME,THREAD,CALLER,FACTORY,OWNER,MODULE,NODE,QUEUE_ID,TEMPLATE,TEMPLATE_HASH,COST,PAID_BEFORE,PAID_AFTER,RESOURCE,CASH_BEFORE,CASH_AFTER,REQUESTED,ACTUAL,RETURNED,OBJECT,OBJECT_ID,OBJECT_OWNER,OBJECT_HASH,HEAD_BEFORE,HEAD_AFTER,PROGRESS_BEFORE,PROGRESS_AFTER,CONTEXT_VALID,NODE_KIND,OBJECT_X,OBJECT_Y,OBJECT_Z,FACTORY_X,FACTORY_Y,FACTORY_Z,OBJECT_HP,FIELD_COUNT};
struct TraceEvent {volatile LONG ready;uint32_t v[FIELD_COUNT];};
struct TraceState {uint32_t magic,pid,thread,factory,owner,ai,iface,start_low,start_high,seconds,requested_tick;volatile LONG request,ack,state,stop_owner,active,event_count,dropped;uint32_t error,callback_thread,restore_mask;TraceEvent events[TRACE_CAP];};
